from __future__ import annotations

import math

import pandas as pd


def compute_previous_relationships(canonical_legs: pd.DataFrame) -> pd.DataFrame:
    frame = canonical_legs.sort_values(["start_time", "end_time"]).reset_index(drop=True)
    rows: list[dict] = []
    for index, current in frame.iterrows():
        previous_rows = frame.iloc[:index]
        non_overlapping = previous_rows[previous_rows["end_time"] <= current["start_time"]]
        same_level = non_overlapping[non_overlapping["primary_segment_level"] == current["primary_segment_level"]]
        rows.append(
            {
                "current_leg_id": current["canonical_leg_id"],
                "previous_row_canonical_leg_id": previous_rows.iloc[-1]["canonical_leg_id"] if not previous_rows.empty else "",
                "previous_non_overlapping_leg_id": non_overlapping.iloc[-1]["canonical_leg_id"] if not non_overlapping.empty else "",
                "previous_non_overlapping_same_level_leg_id": same_level.iloc[-1]["canonical_leg_id"] if not same_level.empty else "",
            }
        )
    return pd.DataFrame(rows)


def build_parent_reference_tables(canonical_legs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    legs = canonical_legs.sort_values("start_time").reset_index(drop=True)
    candidate_rows: list[dict] = []
    relation_rows: list[dict] = []
    epsilon_factor = 1e-10
    for _, current in legs.iterrows():
        candidates = []
        for _, candidate in legs.iterrows():
            if candidate["canonical_leg_id"] == current["canonical_leg_id"]:
                continue
            contains = candidate["start_time"] <= current["start_time"] and candidate["end_time"] >= current["end_time"]
            opposite = candidate["direction"] != current["direction"]
            shared = abs(float(candidate["end_price"]) - float(current["start_price"])) <= max(abs(float(current["start_price"])) * epsilon_factor, 1e-8)
            temporal = candidate["end_time"] <= current["start_time"]
            if contains or temporal:
                kind = "parent" if contains else "reference"
                if kind == "reference" and not opposite:
                    continue
                reason = "higher_level_container" if contains else "shared_extreme_opposite_predecessor" if shared else "previous_opposite_leg"
                amplitude = abs(float(candidate["end_price"]) - float(candidate["start_price"]))
                retracement = abs(float(current["end_price"]) - float(candidate["end_price"]))
                row = {
                    "current_leg_id": current["canonical_leg_id"],
                    "candidate_leg_id": candidate["canonical_leg_id"],
                    "relationship_kind": kind,
                    "candidate_reason": reason,
                    "current_segment_level": current["primary_segment_level"],
                    "candidate_segment_level": candidate["primary_segment_level"],
                    "current_direction": current["direction"],
                    "candidate_direction": candidate["direction"],
                    "candidate_start_time": candidate["start_time"],
                    "candidate_end_time": candidate["end_time"],
                    "candidate_duration_hours": (candidate["end_time"] - candidate["start_time"]).total_seconds() / 3600.0,
                    "candidate_move_abs": amplitude,
                    "candidate_move_pct": amplitude / abs(float(candidate["start_price"])) if candidate["start_price"] else math.nan,
                    "time_gap_hours": (current["start_time"] - candidate["end_time"]).total_seconds() / 3600.0,
                    "reference_origin_shared_extreme": shared,
                    "reference_origin_gap_abs": abs(float(candidate["end_price"]) - float(current["start_price"])),
                    "reference_origin_gap_pct": abs(float(candidate["end_price"]) - float(current["start_price"])) / abs(float(current["start_price"])) if current["start_price"] else math.nan,
                    "explicit_upstream_link": False,
                    "direct_temporal_predecessor": temporal,
                    "same_level_predecessor": candidate["primary_segment_level"] == current["primary_segment_level"],
                    "higher_level_container": contains,
                    "contains_current_leg": contains,
                    "amplitude_ratio": abs(float(current["end_price"]) - float(current["start_price"])) / amplitude if amplitude else math.nan,
                    "retracement_of_candidate_abs": retracement,
                    "retracement_of_candidate_pct": retracement / amplitude if amplitude else math.nan,
                }
                candidates.append(row)
                candidate_rows.append(row)
        parent_candidates = [row for row in candidates if row["relationship_kind"] == "parent"]
        reference_candidates = [row for row in candidates if row["relationship_kind"] == "reference"]
        relation_rows.append(
            {
                "current_leg_id": current["canonical_leg_id"],
                "parent_relationship_status": "unique" if len(parent_candidates) == 1 else "ambiguous" if len(parent_candidates) > 1 else "missing",
                "parent_canonical_leg_id": parent_candidates[0]["candidate_leg_id"] if len(parent_candidates) == 1 else "",
                "reference_relationship_status": "unique" if len(reference_candidates) == 1 else "ambiguous" if len(reference_candidates) > 1 else "missing",
                "reference_canonical_leg_id": reference_candidates[0]["candidate_leg_id"] if len(reference_candidates) == 1 else "",
            }
        )
    return pd.DataFrame(candidate_rows), pd.DataFrame(relation_rows)
