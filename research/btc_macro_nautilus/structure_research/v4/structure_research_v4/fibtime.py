from __future__ import annotations

import pandas as pd


def audit_duplicates(raw_fibtime: pd.DataFrame) -> pd.DataFrame:
    frame = raw_fibtime.reset_index().rename(columns={"index": "raw_row_index"})
    grouped = frame.groupby(["impulse_id", "event_type", "event_time"], dropna=False)
    rows = []
    for key, chunk in grouped:
        if len(chunk) < 2:
            continue
        impulse_id, event_type, event_time = key
        rows.append(
            {
                "impulse_id": impulse_id,
                "event_type": event_type,
                "event_time": event_time,
                "duplicate_count": len(chunk),
                "raw_row_indexes": "|".join(str(value) for value in chunk["raw_row_index"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def build_fibtime_events(raw_fibtime: pd.DataFrame, impulses: pd.DataFrame, coverage_end: pd.Timestamp) -> pd.DataFrame:
    rows = []
    impulse_lookup = impulses.set_index("impulse_id") if not impulses.empty and "impulse_id" in impulses.columns else pd.DataFrame()
    for event in raw_fibtime.to_dict(orient="records"):
        event_time = pd.Timestamp(event["event_time"])
        event_time = event_time.tz_localize("UTC") if event_time.tzinfo is None else event_time.tz_convert("UTC")
        available_at_time = pd.NaT
        availability_status = "unavailable_after_coverage"
        if event_time <= coverage_end:
            bucket = event_time.ceil("4h")
            available_at_time = bucket
            availability_status = "available"
        rows.append(
            {
                "fib_event_id": event.get("fib_event_id", ""),
                "impulse_id": event.get("impulse_id", ""),
                "event_type": event["event_type"],
                "event_time": event_time,
                "available_at_time": available_at_time,
                "availability_status": availability_status,
                "warning_code": "" if event.get("reason") else "fibtime_revision_history_unavailable",
                "reason": event.get("reason", ""),
            }
        )
    return pd.DataFrame(rows)
