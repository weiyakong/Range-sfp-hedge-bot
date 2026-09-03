from __future__ import annotations

import hashlib

import pandas as pd


def _signature(row: pd.Series) -> str:
    payload = "|".join(
        str(row[column])
        for column in ["start_time", "end_time", "start_price", "end_price", "direction", "source_table"]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def canonicalize_legs(source_tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    for source_table, frame in source_tables.items():
        if frame.empty:
            continue
        renamed = frame.rename(columns={"leg_id": "source_leg_id"})
        for row in renamed.to_dict(orient="records"):
            row["source_table"] = source_table
            row["source_status"] = row.get("status", row.get("role", "unknown"))
            rows.append(row)
    members = pd.DataFrame(rows)
    if members.empty:
        return pd.DataFrame(), pd.DataFrame()
    for column in ["start_time", "end_time"]:
        members[column] = pd.to_datetime(members[column], utc=True, errors="coerce", format="mixed")
    members["source_path_signature"] = members.apply(_signature, axis=1)
    key_columns = ["start_time", "end_time", "start_price", "end_price", "direction", "source_path_signature"]
    grouped = members.groupby(key_columns, dropna=False, sort=True)
    canonical_rows: list[dict] = []
    membership_rows: list[dict] = []
    for index, (key, frame) in enumerate(grouped, start=1):
        canonical_leg_id = f"CL{index:05d}"
        record = frame.iloc[0]
        canonical_rows.append(
            {
                "canonical_leg_id": canonical_leg_id,
                "direction": record["direction"],
                "start_time": record["start_time"],
                "end_time": record["end_time"],
                "start_price": record["start_price"],
                "end_price": record["end_price"],
                "source_roles": "|".join(sorted(set(frame.get("role", pd.Series([""])).astype(str)))),
                "source_tables": "|".join(sorted(set(frame["source_table"].astype(str)))),
                "source_statuses": "|".join(sorted(set(frame["source_status"].astype(str)))),
                "segment_levels": "|".join(sorted(set(frame.get("market", frame.get("structural_status", pd.Series(["base"]))).astype(str)))),
                "primary_segment_level": str(record.get("market", record.get("structural_status", "base"))),
                "segment_level_status": "exact",
                "structural_market_source": str(record.get("market", "")),
                "structural_market_source_status": "known" if pd.notna(record.get("market", None)) else "unknown",
            }
        )
        for member in frame.to_dict(orient="records"):
            membership_rows.append(
                {
                    "canonical_leg_id": canonical_leg_id,
                    "source_table": member["source_table"],
                    "source_leg_id": member.get("source_leg_id", member.get("impulse_id", member.get("correction_id", ""))),
                    "direction": member["direction"],
                    "start_time": member["start_time"],
                    "end_time": member["end_time"],
                    "start_price": member["start_price"],
                    "end_price": member["end_price"],
                    "source_status": member["source_status"],
                }
            )
    return pd.DataFrame(canonical_rows), pd.DataFrame(membership_rows)
