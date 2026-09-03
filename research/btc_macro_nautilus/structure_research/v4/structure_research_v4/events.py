from __future__ import annotations

import pandas as pd


def build_retrospective_events(leg_bars_4h: pd.DataFrame, relationships: pd.DataFrame) -> pd.DataFrame:
    if leg_bars_4h.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for leg_id, frame in leg_bars_4h.groupby("canonical_leg_id"):
        frame = frame.sort_values("open_datetime")
        last_extreme_time = None
        last_sign = None
        for row in frame.itertuples(index=False):
            if last_extreme_time is None:
                rows.append(_event_row(leg_id, row.close_datetime, "new_trend_extreme"))
                last_extreme_time = row.close_datetime
            change = row.close - row.open
            sign = 1 if change > 0 else -1 if change < 0 else 0
            if sign != 0 and last_sign not in (None, sign):
                rows.append(_event_row(leg_id, row.close_datetime, "direction_change"))
            last_sign = sign if sign != 0 else last_sign
            elapsed = row.close_datetime - last_extreme_time
            if elapsed >= pd.Timedelta(days=1):
                rows.append(_event_row(leg_id, row.close_datetime, "no_new_extreme_24h"))
            if elapsed >= pd.Timedelta(days=3):
                rows.append(_event_row(leg_id, row.close_datetime, "no_new_extreme_3d"))
            if elapsed >= pd.Timedelta(days=7):
                rows.append(_event_row(leg_id, row.close_datetime, "no_new_extreme_7d"))
            if elapsed >= pd.Timedelta(days=14):
                rows.append(_event_row(leg_id, row.close_datetime, "no_new_extreme_14d"))
        relation = relationships[relationships["current_leg_id"] == leg_id]
        if not relation.empty and relation.iloc[0]["parent_relationship_status"] == "unique" and not frame.empty:
            start = frame["open_datetime"].min()
            end = frame["close_datetime"].max()
            duration = end - start
            for ratio, label in [(0.236, "0236"), (0.382, "0382"), (0.5, "0500"), (0.618, "0618"), (1.0, "1000")]:
                rows.append(_event_row(leg_id, start + duration * ratio, f"parent_time_{label}"))
    result = pd.DataFrame(rows).drop_duplicates(subset=["canonical_leg_id", "event_type", "event_time"])
    result["is_causal"] = False
    result["uses_future_leg_direction"] = True
    return result.sort_values(["canonical_leg_id", "event_time"]).reset_index(drop=True)


def _event_row(leg_id: str, event_time: pd.Timestamp, event_type: str) -> dict:
    return {
        "canonical_leg_id": leg_id,
        "event_time": event_time,
        "event_type": event_type,
    }
