from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import macro_structure_review as old
except ImportError as exc:  # pragma: no cover - runtime guard for the user's project folder
    raise SystemExit(
        "Place this file in the same directory as the original macro_structure_review.py. "
        "The original file is imported and is not overwritten."
    ) from exc


ROOT = Path(__file__).resolve().parent
UTC = "UTC"


def ensure_utc(value: pd.Timestamp) -> pd.Timestamp:
    value = pd.Timestamp(value)
    if value.tzinfo is None:
        return value.tz_localize(UTC)
    return value.tz_convert(UTC)


def normalize_iso_timestamp_columns(frame: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            continue
        parsed = out[column].apply(
            lambda value: pd.NaT
            if value in ("", None) or pd.isna(value)
            else ensure_utc(pd.Timestamp(value))
        )
        out[column] = parsed.apply(
            lambda value: ""
            if pd.isna(value)
            else value.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
        )
    return out


def prices_equal(left: float, right: float) -> bool:
    scale = max(abs(float(left)), abs(float(right)), 1.0)
    return abs(float(left) - float(right)) <= max(1e-8, scale * 1e-10)


def refine_day_extreme_with_meta(
    h4: pd.DataFrame,
    day_open: pd.Timestamp,
    side: str,
    fallback_price: float,
) -> Tuple[pd.Timestamp, float, str]:
    start = ensure_utc(day_open)
    end = start + pd.Timedelta(days=1)
    subset = h4[(h4["open_datetime"] >= start) & (h4["open_datetime"] < end)]
    if subset.empty:
        return start, float(fallback_price), "1D"
    if side == "high":
        idx = subset["high"].idxmax()
        return ensure_utc(subset.loc[idx, "open_datetime"]), float(subset.loc[idx, "high"]), "4H"
    idx = subset["low"].idxmin()
    return ensure_utc(subset.loc[idx, "open_datetime"]), float(subset.loc[idx, "low"]), "4H"


def event_side(event_type: str) -> str:
    if event_type == "confirmed_macro_high":
        return "high"
    if event_type == "confirmed_macro_low":
        return "low"
    raise ValueError(f"Unsupported event type: {event_type}")


def opposite_direction(direction: str) -> str:
    if direction == "up":
        return "down"
    if direction == "down":
        return "up"
    raise ValueError(f"Unknown direction: {direction}")


def more_extreme_side(side: str, new_price: float, old_price: float) -> bool:
    if side == "high":
        return float(new_price) >= float(old_price)
    if side == "low":
        return float(new_price) <= float(old_price)
    raise ValueError(f"Unknown side: {side}")


def build_chronological_log20_legs(events_df: pd.DataFrame, log_threshold: float) -> Tuple[pd.DataFrame, dict]:
    if events_df.empty:
        return pd.DataFrame(), {"chronology_dropped": 0, "same_side_replaced": 0, "below_threshold_after_filter": 0}

    candidates = events_df[
        events_df["event_type"].isin(["confirmed_macro_high", "confirmed_macro_low"])
    ].copy()
    candidates["event_num"] = candidates["event_id"].str[1:].astype(int)
    candidates["side"] = candidates["event_type"].map(event_side)
    candidates["pivot_time"] = pd.to_datetime(candidates["refined_timestamp_4h"], utc=True)
    candidates["pivot_price"] = pd.to_numeric(candidates["refined_price_4h"], errors="raise")
    candidates["available_at"] = pd.to_datetime(candidates["available_at"], utc=True)
    candidates = candidates.sort_values(["event_num"]).reset_index(drop=True)

    kept: List[dict] = []
    chronology_dropped = 0
    same_side_replaced = 0
    for _, row in candidates.iterrows():
        current = {
            "event_id": str(row["event_id"]),
            "side": str(row["side"]),
            "pivot_time": ensure_utc(row["pivot_time"]),
            "pivot_price": float(row["pivot_price"]),
            "available_at": ensure_utc(row["available_at"]),
            "source_timeframe": str(row["source_timeframe"]),
        }
        if not kept:
            kept.append(current)
            continue
        last = kept[-1]
        if current["side"] == last["side"]:
            if more_extreme_side(current["side"], current["pivot_price"], last["pivot_price"]):
                kept[-1] = current
                same_side_replaced += 1
            continue
        if current["pivot_time"] > last["pivot_time"]:
            kept.append(current)
            continue
        chronology_dropped += 1

    legs: List[dict] = []
    below_threshold_after_filter = 0
    for left, right in zip(kept, kept[1:]):
        if left["side"] == "low" and right["side"] == "high":
            direction = "up"
        elif left["side"] == "high" and right["side"] == "low":
            direction = "down"
        else:
            continue
        signed_log = math.log(float(right["pivot_price"]) / float(left["pivot_price"]))
        if abs(signed_log) + 1e-12 < log_threshold:
            below_threshold_after_filter += 1
            continue
        duration_hours = (right["pivot_time"] - left["pivot_time"]).total_seconds() / 3600.0
        precise_intraday = left["source_timeframe"] == "4H" and right["source_timeframe"] == "4H"
        factor = float(right["pivot_price"]) / float(left["pivot_price"])
        legs.append(
            {
                "leg_id": f"L{len(legs)+1:05d}",
                "direction": direction,
                "start_event_id": left["event_id"],
                "end_event_id": right["event_id"],
                "start_time": left["pivot_time"].isoformat(),
                "end_time": right["pivot_time"].isoformat(),
                "start_price": round(float(left["pivot_price"]), 8),
                "end_price": round(float(right["pivot_price"]), 8),
                "move_pct": round((factor - 1.0) if direction == "up" else (float(right["pivot_price"]) - float(left["pivot_price"])) / float(left["pivot_price"]), 6),
                "price_factor": round(max(factor, 1.0 / factor), 10),
                "log_move": round(signed_log, 10),
                "abs_log_move": round(abs(signed_log), 10),
                "duration_days": round(duration_hours / 24.0, 6),
                "duration_hours": round(duration_hours, 6),
                "duration_precision": "4H" if precise_intraday else "1D_fallback",
                "is_subday_known": precise_intraday,
                "is_subday": bool(precise_intraday and duration_hours < 24.0),
            }
        )
    summary = {
        "chronology_dropped": chronology_dropped,
        "same_side_replaced": same_side_replaced,
        "below_threshold_after_filter": below_threshold_after_filter,
    }
    return pd.DataFrame(legs), summary


def build_macro_structure_log20(
    daily: pd.DataFrame,
    h4: pd.DataFrame,
    config: old.MacroConfig,
    log_factor: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    if log_factor <= 1.0:
        raise ValueError("log_factor must be greater than 1.0")

    log_threshold = math.log(log_factor)
    atr = old.compute_atr(daily, config.atr_length)
    events: List[dict] = []
    event_seq = [0]

    current_ath_price: Optional[float] = None
    state = "seeking_macro_high"
    cycle_high_price: Optional[float] = None
    cycle_high_time: Optional[pd.Timestamp] = None
    cycle_low_price: Optional[float] = None
    cycle_low_time: Optional[pd.Timestamp] = None
    latest_confirmed_macro_high_event: Optional[dict] = None

    for idx, row in daily.iterrows():
        day_open = ensure_utc(row["open_datetime"])
        day_close = ensure_utc(row["close_datetime"])
        day_high = float(row["high"])
        day_low = float(row["low"])
        atr_value = float(atr.iloc[idx]) if not pd.isna(atr.iloc[idx]) else 0.0

        if current_ath_price is None or day_high > current_ath_price:
            current_ath_price = day_high
            refined_ts, refined_price, precision = refine_day_extreme_with_meta(h4, day_open, "high", day_high)
            old.add_event(
                events,
                event_seq,
                "ath_update",
                day_open,
                refined_ts,
                day_high,
                refined_price,
                drawdown_pct=0.0,
                rebound_pct=None,
                atr_1d=atr_value,
                atr_multiple=0.0,
                confirmation_reason="high_gt_all_previous_high",
                available_at=day_close,
                source_timeframe=precision,
            )

        if state == "seeking_macro_high":
            if cycle_high_price is None or day_high >= cycle_high_price:
                cycle_high_price = day_high
                cycle_high_time = day_open
            if cycle_high_price is None or cycle_high_time is None:
                continue
            log_drawdown = math.log(cycle_high_price / day_low) if day_low > 0 else float("inf")
            if log_drawdown >= log_threshold:
                refined_ts, refined_price, precision = refine_day_extreme_with_meta(h4, cycle_high_time, "high", cycle_high_price)
                event_id = old.add_event(
                    events,
                    event_seq,
                    "confirmed_macro_high",
                    cycle_high_time,
                    refined_ts,
                    cycle_high_price,
                    refined_price,
                    drawdown_pct=(cycle_high_price - day_low) / cycle_high_price if cycle_high_price > 0 else 0.0,
                    rebound_pct=None,
                    atr_1d=atr_value,
                    atr_multiple=None,
                    confirmation_reason=f"log_drawdown>=ln({log_factor:.8f})|log_drawdown={log_drawdown:.10f}",
                    available_at=day_close,
                    source_timeframe=precision,
                )
                latest_confirmed_macro_high_event = {
                    "event_id": event_id,
                    "time": cycle_high_time,
                    "price": cycle_high_price,
                }
                state = "seeking_macro_low"
                cycle_low_price = None
                cycle_low_time = None
                continue

        if state == "seeking_macro_low" and latest_confirmed_macro_high_event is not None:
            if cycle_low_price is None or day_low <= cycle_low_price:
                cycle_low_price = day_low
                cycle_low_time = day_open
                refined_ts, refined_price, precision = refine_day_extreme_with_meta(h4, day_open, "low", day_low)
                old.add_event(
                    events,
                    event_seq,
                    "candidate_macro_low",
                    day_open,
                    refined_ts,
                    day_low,
                    refined_price,
                    drawdown_pct=(latest_confirmed_macro_high_event["price"] - day_low) / latest_confirmed_macro_high_event["price"] if latest_confirmed_macro_high_event["price"] > 0 else 0.0,
                    rebound_pct=0.0,
                    atr_1d=atr_value,
                    atr_multiple=None,
                    confirmation_reason="new_low_after_confirmed_macro_high",
                    available_at=day_close,
                    source_timeframe=precision,
                )
            if cycle_low_price is None or cycle_low_time is None:
                continue
            log_rebound = math.log(day_high / cycle_low_price) if cycle_low_price > 0 else float("inf")
            if log_rebound >= log_threshold:
                refined_ts, refined_price, precision = refine_day_extreme_with_meta(h4, cycle_low_time, "low", cycle_low_price)
                old.add_event(
                    events,
                    event_seq,
                    "confirmed_macro_low",
                    cycle_low_time,
                    refined_ts,
                    cycle_low_price,
                    refined_price,
                    drawdown_pct=(latest_confirmed_macro_high_event["price"] - cycle_low_price) / latest_confirmed_macro_high_event["price"] if latest_confirmed_macro_high_event["price"] > 0 else 0.0,
                    rebound_pct=(day_high - cycle_low_price) / cycle_low_price if cycle_low_price > 0 else 0.0,
                    atr_1d=atr_value,
                    atr_multiple=None,
                    confirmation_reason=f"log_rebound>=ln({log_factor:.8f})|log_rebound={log_rebound:.10f}",
                    available_at=day_close,
                    source_timeframe=precision,
                )
                state = "seeking_macro_high"
                cycle_high_price = day_high
                cycle_high_time = day_open

    events_df = pd.DataFrame(events)
    legs_df, leg_summary = build_chronological_log20_legs(events_df, log_threshold)
    summary = {
        "log_factor": log_factor,
        "log_threshold": log_threshold,
        "strict_log20_only": True,
        "ath_update_count": int((events_df["event_type"] == "ath_update").sum()) if not events_df.empty else 0,
        "confirmed_macro_high_count": int((events_df["event_type"] == "confirmed_macro_high").sum()) if not events_df.empty else 0,
        "confirmed_macro_low_count": int((events_df["event_type"] == "confirmed_macro_low").sum()) if not events_df.empty else 0,
        "raw_leg_count": int(len(legs_df)),
        **leg_summary,
    }
    return events_df, legs_df, summary


def build_analysis_stream(daily: pd.DataFrame, h4: pd.DataFrame) -> pd.DataFrame:
    if h4.empty:
        return daily[["open_datetime", "high", "low"]].copy().assign(stream="1D").sort_values("open_datetime").reset_index(drop=True)
    h4_start = ensure_utc(h4["open_datetime"].min())
    daily_part = daily[daily["open_datetime"] < h4_start][["open_datetime", "high", "low"]].copy()
    h4_part = h4[["open_datetime", "high", "low"]].copy()
    return (
        pd.concat(
            [
                daily_part.assign(stream="1D"),
                h4_part.assign(stream="4H"),
            ],
            ignore_index=True,
        )
        .sort_values("open_datetime")
        .reset_index(drop=True)
    )


def find_parent_extreme_break(
    stream: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    parent_direction: str,
    parent_end_price: float,
) -> Optional[dict]:
    window = stream[
        (stream["open_datetime"] > ensure_utc(start_time))
        & (stream["open_datetime"] <= ensure_utc(end_time))
    ]
    if window.empty:
        return None
    if parent_direction == "down":
        hits = window[window["low"] < float(parent_end_price)]
        if hits.empty:
            return None
        row = hits.iloc[0]
        return {"time": ensure_utc(row["open_datetime"]), "price": float(row["low"])}
    hits = window[window["high"] > float(parent_end_price)]
    if hits.empty:
        return None
    row = hits.iloc[0]
    return {"time": ensure_utc(row["open_datetime"]), "price": float(row["high"])}


def build_structural_impulses_log20_fibtime_fixed(
    macro_events_df: pd.DataFrame,
    macro_legs_df: pd.DataFrame,
    *,
    daily: pd.DataFrame,
    h4: pd.DataFrame,
    fib_ratio: float,
    min_fib_days: float,
    analysis_end_time: pd.Timestamp,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    if fib_ratio <= 0:
        raise ValueError("fib_ratio must be positive")
    if min_fib_days < 0:
        raise ValueError("min_fib_days cannot be negative")

    events = macro_events_df.copy()
    events["available_at"] = pd.to_datetime(events["available_at"], utc=True, format="mixed")
    event_lookup = events.set_index("event_id").to_dict("index")

    raw_legs = macro_legs_df.copy()
    required = {
        "leg_id",
        "direction",
        "start_event_id",
        "end_event_id",
        "start_time",
        "end_time",
        "start_price",
        "end_price",
        "duration_days",
    }
    missing = sorted(required - set(raw_legs.columns))
    if missing:
        raise ValueError(f"macro_legs_df is missing columns: {missing}")

    raw_legs["start_time"] = pd.to_datetime(raw_legs["start_time"], utc=True, format="mixed")
    raw_legs["end_time"] = pd.to_datetime(raw_legs["end_time"], utc=True, format="mixed")
    raw_legs["available_at_time"] = raw_legs["end_event_id"].map(
        lambda event_id: ensure_utc(pd.Timestamp(event_lookup[event_id]["available_at"]))
    )
    raw_legs = raw_legs.sort_values(["start_time", "end_time", "leg_id"]).reset_index(drop=True)

    stream = build_analysis_stream(daily, h4)
    stream["open_datetime"] = pd.to_datetime(stream["open_datetime"], utc=True, format="mixed")

    impulses: List[dict] = []
    corrections: List[dict] = []
    fib_events: List[dict] = []
    movement_segments = raw_legs.copy()
    movement_segments["role"] = "raw_leg"
    movement_segments["is_subday"] = movement_segments.get("is_subday", False)

    def fib_wait_days(duration_days: float) -> float:
        return max(float(min_fib_days), float(fib_ratio) * max(float(duration_days), 0.0))

    for idx, parent in raw_legs.iterrows():
        duration_days = float(parent["duration_days"])
        wait_days = fib_wait_days(duration_days)
        deadline = ensure_utc(parent["end_time"]) + pd.Timedelta(days=wait_days)
        next_leg = raw_legs.iloc[idx + 1] if idx + 1 < len(raw_legs) else None
        correction_direction = opposite_direction(str(parent["direction"]))
        if next_leg is None or str(next_leg["direction"]) != correction_direction:
            continue

        scan_end = min(ensure_utc(analysis_end_time), deadline)
        breach = find_parent_extreme_break(
            stream,
            ensure_utc(parent["end_time"]),
            scan_end,
            str(parent["direction"]),
            float(parent["end_price"]),
        )

        cluster = raw_legs.iloc[idx + 1 :].copy()
        if breach is not None:
            cluster = cluster[cluster["start_time"] < breach["time"]]
        else:
            cluster = cluster[cluster["start_time"] < scan_end]

        if cluster.empty:
            continue

        if correction_direction == "up":
            extreme_idx = cluster["end_price"].astype(float).idxmax()
        else:
            extreme_idx = cluster["end_price"].astype(float).idxmin()
        extreme_row = raw_legs.loc[extreme_idx]
        correction_available = pd.to_datetime(cluster["available_at_time"], utc=True, format="mixed").max()
        status = "pending"
        reason = "awaiting_fib_deadline"
        confirmed_at = pd.NaT
        rejected_at = pd.NaT
        is_open = True

        if breach is not None:
            status = "rejected"
            reason = "new_parent_extreme_before_fib_deadline"
            rejected_at = breach["time"]
            is_open = False
        elif ensure_utc(analysis_end_time) >= deadline:
            status = "accepted"
            reason = "fib_deadline_reached_without_new_parent_extreme"
            confirmed_at = deadline
            is_open = False

        corrections.append(
            {
                "correction_id": f"SFC{len(corrections)+1:04d}",
                "parent_impulse_id": f"SFI{len(impulses)+1:04d}",
                "direction": correction_direction,
                "start_event_id": str(parent["end_event_id"]),
                "end_event_id": str(extreme_row["end_event_id"]),
                "start_time": ensure_utc(parent["end_time"]).isoformat(),
                "start_price": round(float(parent["end_price"]), 8),
                "end_time": ensure_utc(extreme_row["end_time"]).isoformat(),
                "end_price": round(float(extreme_row["end_price"]), 8),
                "available_at_time": ensure_utc(correction_available).isoformat(),
                "status": status,
                "structural_status": f"correction_{status}",
                "confirmed_at": "" if pd.isna(confirmed_at) else ensure_utc(confirmed_at).isoformat(),
                "rejected_at": "" if pd.isna(rejected_at) else ensure_utc(rejected_at).isoformat(),
                "reason": reason,
                "is_open": bool(is_open),
                "correction_duration": round((ensure_utc(extreme_row["end_time"]) - ensure_utc(parent["end_time"])).total_seconds() / 86400.0, 8),
                "parent_duration": round(duration_days, 8),
                "time_ratio": round(((ensure_utc(extreme_row["end_time"]) - ensure_utc(parent["end_time"])).total_seconds() / 86400.0) / duration_days, 8) if duration_days > 0 else 0.0,
                "merged_into_parent_id": "" if status != "rejected" else f"SFI{len(impulses)+1:04d}",
                "rejection_or_acceptance_reason": reason,
            }
        )

        fib_events.append(
            {
                "fib_event_id": f"FTE{len(fib_events)+1:05d}",
                "event_type": f"correction_{status}",
                "event_time": ensure_utc(deadline if status == 'accepted' else (rejected_at if not pd.isna(rejected_at) else analysis_end_time)).isoformat(),
                "impulse_id": f"SFI{len(impulses)+1:04d}",
                "correction_id": f"SFC{len(corrections):04d}",
                "reason": reason,
            }
        )

        if status in {"accepted", "pending"}:
            impulses.append(
                {
                    "impulse_id": f"SFI{len(impulses)+1:04d}",
                    "direction": str(parent["direction"]),
                    "start_event_id": str(parent["start_event_id"]),
                    "end_event_id": str(parent["end_event_id"]),
                    "start_time": ensure_utc(parent["start_time"]).isoformat(),
                    "start_price": round(float(parent["start_price"]), 8),
                    "end_time": ensure_utc(parent["end_time"]).isoformat(),
                    "end_price": round(float(parent["end_price"]), 8),
                    "available_at_time": ensure_utc(max(pd.Timestamp(parent["available_at_time"]), confirmed_at) if not pd.isna(confirmed_at) else parent["available_at_time"]).isoformat(),
                    "regime_anchor_time": ensure_utc(parent["start_time"]).isoformat(),
                    "regime_anchor_price": round(float(parent["start_price"]), 8),
                    "status": "finished_confirmed" if status == "accepted" else "open_active",
                    "structural_status": "impulse_finished_confirmed" if status == "accepted" else "impulse_active",
                    "confirmed_at": "" if pd.isna(confirmed_at) else ensure_utc(confirmed_at).isoformat(),
                    "is_open": bool(status == "pending"),
                    "duration_days": round(duration_days, 8),
                    "fib_wait_days": round(wait_days, 8),
                    "fib_deadline": ensure_utc(deadline).isoformat(),
                    "duration": round(duration_days, 8),
                }
            )

    impulses_df = pd.DataFrame(impulses)
    corrections_df = pd.DataFrame(corrections)
    movement_segments_df = movement_segments
    fib_events_df = pd.DataFrame(fib_events)

    summary = {
        "raw_leg_count": int(len(raw_legs)),
        "subday_leg_count": int(macro_legs_df.get("is_subday", pd.Series(dtype=bool)).sum()) if "is_subday" in macro_legs_df else 0,
        "structural_impulse_count": int(len(impulses_df)),
        "confirmed_impulse_count": int((impulses_df.get("status", pd.Series(dtype=str)) == "finished_confirmed").sum()) if not impulses_df.empty else 0,
        "accepted_correction_count": int((corrections_df.get("status", pd.Series(dtype=str)) == "accepted").sum()) if not corrections_df.empty else 0,
        "rejected_correction_count": int((corrections_df.get("status", pd.Series(dtype=str)) == "rejected").sum()) if not corrections_df.empty else 0,
        "pending_correction_count": int((corrections_df.get("status", pd.Series(dtype=str)) == "pending").sum()) if not corrections_df.empty else 0,
        "fib_ratio": fib_ratio,
        "min_fib_days": min_fib_days,
    }
    return impulses_df, corrections_df, movement_segments_df, fib_events_df, summary


def build_structural_regime_segments(impulses_df: pd.DataFrame) -> pd.DataFrame:
    if impulses_df.empty:
        return pd.DataFrame(
            columns=[
                "segment_id",
                "regime",
                "start_time",
                "end_time",
                "start_price",
                "end_price",
                "available_at_time",
                "source_impulse_id",
                "status",
            ]
        )

    impulses = impulses_df.copy()
    for column in ("start_time", "end_time", "available_at_time", "confirmed_at"):
        if column in impulses.columns:
            impulses[column] = pd.to_datetime(impulses[column], utc=True, format="mixed")
    impulses = impulses.sort_values(["available_at_time", "start_time", "end_time", "impulse_id"]).reset_index(drop=True)

    segments: List[dict] = []
    for _, row in impulses.iterrows():
        regime = "bull" if str(row["direction"]) == "up" else "bear"
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        if end_time < start_time:
            continue
        segments.append(
            {
                "segment_id": f"SRG{len(segments)+1:04d}",
                "regime": regime,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "start_price": round(float(row["start_price"]), 8),
                "end_price": round(float(row["end_price"]), 8),
                "available_at_time": ensure_utc(row["available_at_time"]).isoformat(),
                "source_impulse_id": str(row["impulse_id"]),
                "status": str(row["status"]),
            }
        )
    return pd.DataFrame(segments)


def build_market_state_from_macro_swings(
    daily: pd.DataFrame,
    macro_events_df: pd.DataFrame,
    *,
    bear_candidate_drawdown_pct: float,
    bear_candidate_rebound_pct: float,
    bull_candidate_rebound_pct: float,
    high_correction_drawdown_pct: float,
    deep_correction_drawdown_pct: float,
    break_extension_pct: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    events = macro_events_df.copy()
    events["timestamp_1d"] = pd.to_datetime(events["timestamp_1d"], utc=True, format="mixed")
    events["available_at"] = pd.to_datetime(events["available_at"], utc=True, format="mixed")
    macro_high_lookup = {
        pd.Timestamp(row["timestamp_1d"]): row
        for _, row in events[events["event_type"] == "confirmed_macro_high"].iterrows()
    }
    macro_low_lookup = {
        pd.Timestamp(row["timestamp_1d"]): row
        for _, row in events[events["event_type"] == "confirmed_macro_low"].iterrows()
    }

    cycle_events: List[dict] = []
    market_segments: List[dict] = []
    candidate_diagnostics: List[dict] = []
    market_daily_rows: List[dict] = []
    event_seq = 0
    segment_seq = 0
    candidate_seq = 0
    highest_cycle_high_seen = float("-inf")

    def next_cycle_id() -> str:
        nonlocal event_seq
        event_seq += 1
        return f"MKT{event_seq:04d}"

    def next_segment_id() -> str:
        nonlocal segment_seq
        segment_seq += 1
        return f"MKS{segment_seq:04d}"

    def next_candidate_id(prefix: str) -> str:
        nonlocal candidate_seq
        candidate_seq += 1
        return f"{prefix}_{candidate_seq:04d}"

    def point(ts: pd.Timestamp, available_at: pd.Timestamp, price: float, source_row: Optional[pd.Series]) -> dict:
        return {
            "event_time": ensure_utc(ts),
            "available_at": ensure_utc(available_at),
            "price": float(price),
            "source_row": source_row,
        }

    def label_cycle_high(price: float, event_time: pd.Timestamp) -> str:
        nonlocal highest_cycle_high_seen
        year = pd.Timestamp(event_time).year
        is_ath = price >= highest_cycle_high_seen
        highest_cycle_high_seen = max(highest_cycle_high_seen, price)
        return f"ATH {year}" if is_ath else f"Cycle High {year}"

    def add_cycle_event(
        *,
        event_type: str,
        event_point: dict,
        label: str,
        reason: str,
        market_after: str,
    ) -> dict:
        source_row = event_point.get("source_row")
        payload = {
            "event_id": next_cycle_id(),
            "event_type": event_type,
            "event_label": label,
            "event_time": ensure_utc(event_point["event_time"]).isoformat(),
            "available_at": ensure_utc(event_point["available_at"]).isoformat(),
            "price": round(float(event_point["price"]), 8),
            "source_macro_event_id": "" if source_row is None else str(source_row["event_id"]),
            "source_macro_event_type": "" if source_row is None else str(source_row["event_type"]),
            "confirmation_reason": reason,
            "market_after": market_after,
        }
        cycle_events.append(payload)
        return payload

    def add_market_segment(start_event: dict, end_event: dict, market: str, reason: str, is_open: bool = False) -> None:
        start_time = pd.Timestamp(start_event["event_time"])
        end_time = pd.Timestamp(end_event["event_time"])
        if end_time < start_time:
            return
        market_segments.append(
            {
                "segment_id": next_segment_id(),
                "market": market,
                "start_event_id": start_event["event_id"],
                "end_event_id": end_event["event_id"],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "start_available_at": start_event["available_at"],
                "end_available_at": end_event["available_at"],
                "start_price": round(float(start_event["price"]), 8),
                "end_price": round(float(end_event["price"]), 8),
                "move_pct": round((float(end_event["price"]) - float(start_event["price"])) / float(start_event["price"]), 6) if float(start_event["price"]) else 0.0,
                "duration_days": round((end_time - start_time).total_seconds() / 86400.0, 6),
                "confirmation_reason": reason,
                "is_open": bool(is_open),
            }
        )

    def make_event_payload(event_id: str, ts: pd.Timestamp, available_at: pd.Timestamp, price: float) -> dict:
        return {
            "event_id": event_id,
            "event_time": ensure_utc(ts).isoformat(),
            "available_at": ensure_utc(available_at).isoformat(),
            "price": round(float(price), 8),
        }

    def drawdown_from(anchor_point: dict, low_point: dict) -> float:
        anchor_price = float(anchor_point["price"])
        return (anchor_price - float(low_point["price"])) / anchor_price if anchor_price > 0 else 0.0

    def rebound_from(low_point: dict, high_point: dict) -> float:
        low_price = float(low_point["price"])
        return (float(high_point["price"]) - low_price) / low_price if low_price > 0 else 0.0

    def new_bear_candidate(anchor_point: dict, low_point: dict) -> dict:
        return {
            "candidate_id": next_candidate_id("bear"),
            "candidate_type": "bear_candidate",
            "status": "open",
            "reason_not_confirmed": "",
            "anchor_time": ensure_utc(anchor_point["event_time"]),
            "anchor_price": float(anchor_point["price"]),
            "lowA_time": ensure_utc(low_point["event_time"]),
            "lowA_price": float(low_point["price"]),
            "lowerHighB_time": None,
            "lowerHighB_price": None,
            "confirmation_break_date": None,
            "threshold_drawdown_pct": bear_candidate_drawdown_pct,
            "threshold_rebound_pct": bear_candidate_rebound_pct,
        }

    def new_bull_candidate(low_point: dict, rebound_point: dict) -> dict:
        return {
            "candidate_id": next_candidate_id("bull"),
            "candidate_type": "bull_candidate",
            "status": "open",
            "reason_not_confirmed": "",
            "anchor_time": ensure_utc(low_point["event_time"]),
            "anchor_price": float(low_point["price"]),
            "reboundHighA_time": ensure_utc(rebound_point["event_time"]),
            "reboundHighA_price": float(rebound_point["price"]),
            "higherLowB_time": None,
            "higherLowB_price": None,
            "confirmation_break_date": None,
            "threshold_rebound_pct": bull_candidate_rebound_pct,
        }

    def finalize_candidate(candidate: Optional[dict], status: str, reason: str, confirmation_break_date: Optional[pd.Timestamp]) -> None:
        if candidate is None:
            return
        payload = candidate.copy()
        payload["status"] = status
        payload["reason_not_confirmed"] = reason
        payload["confirmation_break_date"] = (
            "" if confirmation_break_date is None else ensure_utc(confirmation_break_date).isoformat()
        )
        for key in (
            "anchor_time",
            "lowA_time",
            "lowerHighB_time",
            "reboundHighA_time",
            "higherLowB_time",
        ):
            value = payload.get(key)
            payload[key] = "" if value in (None, "") or pd.isna(value) else ensure_utc(pd.Timestamp(value)).isoformat()
        if payload["candidate_type"] == "bear_candidate":
            if payload.get("lowA_price") not in (None, ""):
                payload["actual_drawdown_pct"] = round(
                    (float(payload["anchor_price"]) - float(payload["lowA_price"])) / float(payload["anchor_price"]),
                    6,
                )
            else:
                payload["actual_drawdown_pct"] = None
            if payload.get("lowerHighB_price") not in (None, "") and payload.get("lowA_price") not in (None, ""):
                payload["actual_rebound_pct"] = round(
                    (float(payload["lowerHighB_price"]) - float(payload["lowA_price"])) / float(payload["lowA_price"]),
                    6,
                )
            else:
                payload["actual_rebound_pct"] = None
        else:
            if payload.get("reboundHighA_price") not in (None, ""):
                payload["actual_rebound_pct"] = round(
                    (float(payload["reboundHighA_price"]) - float(payload["anchor_price"])) / float(payload["anchor_price"]),
                    6,
                )
            else:
                payload["actual_rebound_pct"] = None
            if payload.get("higherLowB_price") not in (None, ""):
                payload["actual_pullback_retention_pct"] = round(
                    (float(payload["higherLowB_price"]) - float(payload["anchor_price"])) / float(payload["anchor_price"]),
                    6,
                )
            else:
                payload["actual_pullback_retention_pct"] = None
        candidate_diagnostics.append(payload)

    if daily.empty:
        empty = pd.DataFrame()
        summary = {
            "market_cycle_high_count": 0,
            "market_cycle_low_count": 0,
            "deep_correction_low_count": 0,
            "high_correction_low_count": 0,
            "bull_market_segment_count": 0,
            "bear_market_segment_count": 0,
        }
        return empty, empty, empty, empty, summary

    first_row = daily.iloc[0]
    initial_market_event = {
        "event_id": "INITIAL_BULL",
        "event_time": ensure_utc(pd.Timestamp(first_row["open_datetime"])).isoformat(),
        "available_at": ensure_utc(pd.Timestamp(first_row["close_datetime"])).isoformat(),
        "price": round(float(first_row["close"]), 8),
    }
    state = "bull"
    bull_segment_start_event: dict = initial_market_event
    bear_segment_start_event: Optional[dict] = None
    active_ath = point(
        pd.Timestamp(first_row["open_datetime"]),
        pd.Timestamp(first_row["close_datetime"]),
        float(first_row["high"]),
        None,
    )
    correction_low_since_ath: Optional[dict] = None
    bear_candidate: Optional[dict] = None
    current_bear_low: Optional[dict] = None
    bull_candidate: Optional[dict] = None
    confirmed_cycle_high_event: Optional[dict] = None

    for _, day in daily.iterrows():
        ts = ensure_utc(pd.Timestamp(day["open_datetime"]))
        close_ts = ensure_utc(pd.Timestamp(day["close_datetime"]))
        day_high = float(day["high"])
        day_low = float(day["low"])
        day_close_price = float(day["close"])
        day_high_point = point(ts, close_ts, day_high, None)
        day_low_point = point(ts, close_ts, day_low, None)
        macro_high_row = macro_high_lookup.get(ts)
        macro_low_row = macro_low_lookup.get(ts)
        macro_high_point = (
            point(pd.Timestamp(macro_high_row["timestamp_1d"]), pd.Timestamp(macro_high_row["available_at"]), float(macro_high_row["price_1d"]), macro_high_row)
            if macro_high_row is not None
            else None
        )
        macro_low_point = (
            point(pd.Timestamp(macro_low_row["timestamp_1d"]), pd.Timestamp(macro_low_row["available_at"]), float(macro_low_row["price_1d"]), macro_low_row)
            if macro_low_row is not None
            else None
        )

        if state == "bull":
            if macro_low_point is not None and macro_low_point["event_time"] > active_ath["event_time"]:
                if correction_low_since_ath is None or float(macro_low_point["price"]) < float(correction_low_since_ath["price"]):
                    correction_low_since_ath = macro_low_point
                current_drawdown = drawdown_from(active_ath, correction_low_since_ath)
                if current_drawdown >= bear_candidate_drawdown_pct:
                    if bear_candidate is None:
                        bear_candidate = new_bear_candidate(active_ath, correction_low_since_ath)
                    elif bear_candidate.get("lowerHighB_time") is None and float(correction_low_since_ath["price"]) < float(bear_candidate["lowA_price"]):
                        bear_candidate["lowA_time"] = ensure_utc(correction_low_since_ath["event_time"])
                        bear_candidate["lowA_price"] = float(correction_low_since_ath["price"])

            if day_high > float(active_ath["price"]):
                if correction_low_since_ath is not None:
                    correction_drawdown = drawdown_from(active_ath, correction_low_since_ath)
                    if correction_drawdown >= deep_correction_drawdown_pct:
                        add_cycle_event(
                            event_type="deep_correction_low",
                            event_point=correction_low_since_ath,
                            label=f"Deep Correction {pd.Timestamp(correction_low_since_ath['event_time']).year}",
                            reason="new_ath_before_bear_market_confirmation",
                            market_after="bull",
                        )
                    elif correction_drawdown >= high_correction_drawdown_pct:
                        add_cycle_event(
                            event_type="high_correction_low",
                            event_point=correction_low_since_ath,
                            label=f"High Correction {pd.Timestamp(correction_low_since_ath['event_time']).year}",
                            reason="new_ath_before_bear_market_confirmation",
                            market_after="bull",
                        )
                if bear_candidate is not None:
                    finalize_candidate(bear_candidate, "cancelled", "new_ath_before_confirmation", None)
                active_ath = day_high_point
                correction_low_since_ath = None
                bear_candidate = None
            else:
                if bear_candidate is not None and macro_high_point is not None:
                    if macro_high_point["event_time"] > ensure_utc(pd.Timestamp(bear_candidate["lowA_time"])):
                        if float(macro_high_point["price"]) >= float(bear_candidate["anchor_price"]):
                            if correction_low_since_ath is not None:
                                correction_drawdown = drawdown_from(active_ath, correction_low_since_ath)
                                if correction_drawdown >= deep_correction_drawdown_pct:
                                    add_cycle_event(
                                        event_type="deep_correction_low",
                                        event_point=correction_low_since_ath,
                                        label=f"Deep Correction {pd.Timestamp(correction_low_since_ath['event_time']).year}",
                                        reason="candidate_invalidated_by_recovery_to_ath",
                                        market_after="bull",
                                    )
                                elif correction_drawdown >= high_correction_drawdown_pct:
                                    add_cycle_event(
                                        event_type="high_correction_low",
                                        event_point=correction_low_since_ath,
                                        label=f"High Correction {pd.Timestamp(correction_low_since_ath['event_time']).year}",
                                        reason="candidate_invalidated_by_recovery_to_ath",
                                        market_after="bull",
                                    )
                            finalize_candidate(bear_candidate, "cancelled", "recovery_to_ath_before_bear_confirmation", None)
                            bear_candidate = None
                        else:
                            rebound_pct = rebound_from(
                                point(
                                    pd.Timestamp(bear_candidate["lowA_time"]),
                                    pd.Timestamp(bear_candidate["lowA_time"]),
                                    float(bear_candidate["lowA_price"]),
                                    None,
                                ),
                                macro_high_point,
                            )
                            if rebound_pct >= bear_candidate_rebound_pct:
                                if bear_candidate["lowerHighB_price"] is None or float(macro_high_point["price"]) > float(bear_candidate["lowerHighB_price"]):
                                    bear_candidate["lowerHighB_time"] = ensure_utc(macro_high_point["event_time"])
                                    bear_candidate["lowerHighB_price"] = float(macro_high_point["price"])
                    if (
                        bear_candidate is not None
                        and
                        bear_candidate.get("lowerHighB_time") is not None
                        and (
                            day_close_price < float(bear_candidate["lowA_price"])
                            or day_low <= float(bear_candidate["lowA_price"]) * (1.0 - break_extension_pct)
                        )
                    ):
                        confirmed_cycle_high_event = add_cycle_event(
                            event_type="confirmed_cycle_high",
                            event_point=active_ath,
                            label=label_cycle_high(float(active_ath["price"]), pd.Timestamp(active_ath["event_time"])),
                            reason="ath -> protected_low_A -> rebound_B -> break_below_A",
                            market_after="bear",
                        )
                        add_market_segment(
                            bull_segment_start_event,
                            confirmed_cycle_high_event,
                            "bull",
                            "confirmed_bull_market_until_structural_bear_break",
                        )
                        current_bear_low = point(
                            ts if day_low < float(bear_candidate["lowA_price"]) else pd.Timestamp(bear_candidate["lowA_time"]),
                            close_ts,
                            min(day_low, float(bear_candidate["lowA_price"])),
                            None,
                        )
                        bear_segment_start_event = confirmed_cycle_high_event
                        finalize_candidate(bear_candidate, "confirmed", "confirmed_bear_market", ts)
                        state = "bear"
                        bear_candidate = None
                        bull_candidate = None
                        correction_low_since_ath = None

        else:
            if current_bear_low is None:
                current_bear_low = day_low_point
            elif day_low < float(current_bear_low["price"]):
                current_bear_low = day_low_point
                if bull_candidate is not None:
                    finalize_candidate(bull_candidate, "cancelled", "new_lower_low_before_confirmation", None)
                    bull_candidate = None

            if macro_high_point is not None and current_bear_low is not None and macro_high_point["event_time"] > current_bear_low["event_time"]:
                rebound_pct = rebound_from(current_bear_low, macro_high_point)
                if rebound_pct >= bull_candidate_rebound_pct:
                    if bull_candidate is None:
                        bull_candidate = new_bull_candidate(current_bear_low, macro_high_point)
                    elif bull_candidate.get("higherLowB_time") is None and float(macro_high_point["price"]) > float(bull_candidate["reboundHighA_price"]):
                        bull_candidate["reboundHighA_time"] = ensure_utc(macro_high_point["event_time"])
                        bull_candidate["reboundHighA_price"] = float(macro_high_point["price"])
            if bull_candidate is not None and macro_low_point is not None:
                if (
                    macro_low_point["event_time"] > ensure_utc(pd.Timestamp(bull_candidate["reboundHighA_time"]))
                    and float(macro_low_point["price"]) > float(bull_candidate["anchor_price"])
                ):
                    if bull_candidate["higherLowB_price"] is None or float(macro_low_point["price"]) > float(bull_candidate["higherLowB_price"]):
                        bull_candidate["higherLowB_time"] = ensure_utc(macro_low_point["event_time"])
                        bull_candidate["higherLowB_price"] = float(macro_low_point["price"])
                if (
                    bull_candidate.get("higherLowB_time") is not None
                    and (
                        day_close_price > float(bull_candidate["reboundHighA_price"])
                        or day_high >= float(bull_candidate["reboundHighA_price"]) * (1.0 + break_extension_pct)
                    )
                ):
                    confirmed_cycle_low_event = add_cycle_event(
                        event_type="confirmed_cycle_low",
                        event_point=current_bear_low,
                        label=f"Bear Market Low {pd.Timestamp(current_bear_low['event_time']).year}",
                        reason="bear_low -> rebound_A -> higher_low_B -> break_above_A",
                        market_after="bull",
                    )
                    if bear_segment_start_event is not None:
                        add_market_segment(
                            bear_segment_start_event,
                            confirmed_cycle_low_event,
                            "bear",
                            "confirmed_bear_market_until_structural_bull_break",
                        )
                    finalize_candidate(bull_candidate, "confirmed", "confirmed_bull_market", ts)
                    state = "bull"
                    bull_segment_start_event = confirmed_cycle_low_event
                    active_ath = point(ts, close_ts, day_high, None)
                    correction_low_since_ath = None
                    bull_candidate = None
                    current_bear_low = None

        market_daily_rows.append(
            {
                "open_datetime": ts.isoformat(),
                "close_datetime": close_ts.isoformat(),
                "close": float(day_close_price),
                "market": state,
                "active_reference_time": (
                    active_ath["event_time"].isoformat()
                    if state == "bull"
                    else ("" if current_bear_low is None else current_bear_low["event_time"].isoformat())
                ),
                "active_reference_price": (
                    round(float(active_ath["price"]), 8)
                    if state == "bull"
                    else ("" if current_bear_low is None else round(float(current_bear_low["price"]), 8))
                ),
            }
        )

    last_row = daily.iloc[-1]
    tail_event = {
        "event_id": "TAIL",
        "event_time": ensure_utc(pd.Timestamp(last_row["open_datetime"])).isoformat(),
        "available_at": ensure_utc(pd.Timestamp(last_row["close_datetime"])).isoformat(),
        "price": round(float(last_row["close"]), 8),
    }
    if bear_candidate is not None:
        finalize_candidate(bear_candidate, "open", "open_bear_candidate_at_data_end", None)
    if bull_candidate is not None:
        finalize_candidate(bull_candidate, "open", "open_bull_candidate_at_data_end", None)
    if state == "bull":
        active_ath_event: Optional[dict] = None
        if float(active_ath["price"]) >= highest_cycle_high_seen:
            active_ath_event = add_cycle_event(
                event_type="active_ath",
                event_point=active_ath,
                label=f"ATH {pd.Timestamp(active_ath['event_time']).year}",
                reason="open_bull_market_current_ath",
                market_after="bull",
            )
        if (
            bear_candidate is not None
            and bear_candidate.get("lowerHighB_time") is not None
            and active_ath_event is not None
        ):
            add_market_segment(
                bull_segment_start_event,
                active_ath_event,
                "bull",
                "open_bull_market_until_current_ath",
                is_open=False,
            )
            open_bear_reference_price = min(float(bear_candidate["lowA_price"]), float(last_row["close"]))
            open_bear_event = make_event_payload(
                "OPEN_BEAR_TAIL",
                pd.Timestamp(last_row["open_datetime"]),
                pd.Timestamp(last_row["close_datetime"]),
                open_bear_reference_price,
            )
            add_cycle_event(
                event_type="current_bear_market_low",
                event_point=point(
                    pd.Timestamp(bear_candidate["lowA_time"]),
                    pd.Timestamp(last_row["close_datetime"]),
                    float(bear_candidate["lowA_price"]),
                    None,
                ),
                label=f"Bear Market Low {pd.Timestamp(bear_candidate['lowA_time']).year}",
                reason="open_bear_market_candidate_low",
                market_after="bear",
            )
            add_market_segment(
                active_ath_event,
                open_bear_event,
                "bear",
                "open_bear_market_candidate_tail",
                is_open=True,
            )
        else:
            add_market_segment(bull_segment_start_event, tail_event, "bull", "open_bull_market_tail", is_open=True)
    elif bear_segment_start_event is not None:
        if current_bear_low is not None:
            add_cycle_event(
                event_type="current_bear_market_low",
                event_point=current_bear_low,
                label=f"Bear Market Low {pd.Timestamp(current_bear_low['event_time']).year}",
                reason="open_bear_market_current_low",
                market_after="bear",
            )
        add_market_segment(bear_segment_start_event, tail_event, "bear", "open_bear_market_tail", is_open=True)

    cycle_events_df = pd.DataFrame(cycle_events)
    market_segments_df = pd.DataFrame(market_segments)
    market_daily_df = pd.DataFrame(market_daily_rows)
    candidate_diagnostics_df = pd.DataFrame(candidate_diagnostics)
    summary = {
        "market_cycle_high_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "confirmed_cycle_high").sum()) if not cycle_events_df.empty else 0,
        "market_cycle_low_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "confirmed_cycle_low").sum()) if not cycle_events_df.empty else 0,
        "deep_correction_low_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "deep_correction_low").sum()) if not cycle_events_df.empty else 0,
        "high_correction_low_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "high_correction_low").sum()) if not cycle_events_df.empty else 0,
        "current_bear_low_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "current_bear_market_low").sum()) if not cycle_events_df.empty else 0,
        "active_ath_count": int((cycle_events_df.get("event_type", pd.Series(dtype=str)) == "active_ath").sum()) if not cycle_events_df.empty else 0,
        "bull_market_segment_count": int((market_segments_df.get("market", pd.Series(dtype=str)) == "bull").sum()) if not market_segments_df.empty else 0,
        "bear_market_segment_count": int((market_segments_df.get("market", pd.Series(dtype=str)) == "bear").sum()) if not market_segments_df.empty else 0,
        "bear_candidate_count": int((candidate_diagnostics_df.get("candidate_type", pd.Series(dtype=str)) == "bear_candidate").sum()) if not candidate_diagnostics_df.empty else 0,
        "bull_candidate_count": int((candidate_diagnostics_df.get("candidate_type", pd.Series(dtype=str)) == "bull_candidate").sum()) if not candidate_diagnostics_df.empty else 0,
        "thresholds": {
            "bear_candidate_drawdown_pct": bear_candidate_drawdown_pct,
            "bear_candidate_rebound_pct": bear_candidate_rebound_pct,
            "bull_candidate_rebound_pct": bull_candidate_rebound_pct,
            "high_correction_drawdown_pct": high_correction_drawdown_pct,
            "deep_correction_drawdown_pct": deep_correction_drawdown_pct,
            "break_extension_pct": break_extension_pct,
        },
    }
    return cycle_events_df, market_segments_df, market_daily_df, candidate_diagnostics_df, summary


def render_log20_fibtime_html(
    daily: pd.DataFrame,
    regime_segments_df: pd.DataFrame,
    corrections_df: pd.DataFrame,
    market_segments_df: pd.DataFrame,
    market_events_df: pd.DataFrame,
    output_path: Path,
    symbol: str,
) -> None:
    """Render accepted-only structural regime plus separate bull/bear market overlay."""
    plotly_bundle_path = ROOT / "vendor" / "plotly-2.35.2.min.js"
    if not plotly_bundle_path.exists():
        plotly_bundle_path = old.ROOT / "vendor" / "plotly-2.35.2.min.js"
    plotly_bundle = plotly_bundle_path.read_text(encoding="utf-8")

    def line_points(frame: pd.DataFrame) -> Tuple[List[Optional[str]], List[Optional[float]]]:
        xs: List[Optional[str]] = []
        ys: List[Optional[float]] = []
        if frame.empty:
            return xs, ys
        for _, row in frame.iterrows():
            start_time = pd.Timestamp(row["start_time"])
            end_time = pd.Timestamp(row["end_time"])
            if end_time < start_time:
                continue
            xs.extend([start_time.isoformat(), end_time.isoformat(), None])
            ys.extend([float(row["start_price"]), float(row["end_price"]), None])
        return xs, ys

    accepted_impulses = regime_segments_df[regime_segments_df["status"] == "finished_confirmed"].copy() if not regime_segments_df.empty else pd.DataFrame()
    open_impulses = regime_segments_df[regime_segments_df["status"] != "finished_confirmed"].copy() if not regime_segments_df.empty else pd.DataFrame()
    bull_impulses = accepted_impulses[accepted_impulses["regime"] == "bull"].copy() if not accepted_impulses.empty else pd.DataFrame()
    bear_impulses = accepted_impulses[accepted_impulses["regime"] == "bear"].copy() if not accepted_impulses.empty else pd.DataFrame()
    bull_regime_x, bull_regime_y = line_points(bull_impulses)
    bear_regime_x, bear_regime_y = line_points(bear_impulses)
    open_regime_x, open_regime_y = line_points(open_impulses)

    accepted_corrections = corrections_df[corrections_df["status"] == "accepted"].copy() if not corrections_df.empty else pd.DataFrame()
    correction_x, correction_y = line_points(accepted_corrections)

    bull_market_x: List[Optional[str]] = []
    bull_market_y: List[Optional[float]] = []
    bear_market_x: List[Optional[str]] = []
    bear_market_y: List[Optional[float]] = []
    market_offset = max(float(daily["high"].max()) * 0.015, 300.0)
    bull_market = market_segments_df[market_segments_df["market"] == "bull"].copy() if not market_segments_df.empty else pd.DataFrame()
    bear_market = market_segments_df[market_segments_df["market"] == "bear"].copy() if not market_segments_df.empty else pd.DataFrame()
    for _, segment in bull_market.iterrows():
        start_time = pd.Timestamp(segment["start_time"])
        end_time = pd.Timestamp(segment["end_time"])
        if end_time < start_time:
            continue
        bull_market_x.extend([start_time.isoformat(), end_time.isoformat(), None])
        bull_market_y.extend([float(segment["start_price"]) + market_offset, float(segment["end_price"]) + market_offset, None])
    for _, segment in bear_market.iterrows():
        start_time = pd.Timestamp(segment["start_time"])
        end_time = pd.Timestamp(segment["end_time"])
        if end_time < start_time:
            continue
        bear_market_x.extend([start_time.isoformat(), end_time.isoformat(), None])
        bear_market_y.extend([float(segment["start_price"]) - market_offset, float(segment["end_price"]) - market_offset, None])

    market_cycle = market_events_df[
        market_events_df["event_type"].isin(["confirmed_cycle_high", "confirmed_cycle_low"])
    ].copy() if not market_events_df.empty else pd.DataFrame()
    active_ath_events = market_events_df[market_events_df["event_type"] == "active_ath"].copy() if not market_events_df.empty else pd.DataFrame()
    deep_corrections = market_events_df[market_events_df["event_type"] == "deep_correction_low"].copy() if not market_events_df.empty else pd.DataFrame()
    high_corrections = market_events_df[market_events_df["event_type"] == "high_correction_low"].copy() if not market_events_df.empty else pd.DataFrame()
    current_bear_lows = market_events_df[market_events_df["event_type"] == "current_bear_market_low"].copy() if not market_events_df.empty else pd.DataFrame()

    market_annotations: List[dict] = []
    if not market_events_df.empty:
        for _, event in market_events_df.iterrows():
            market_annotations.append(
                {
                    "x": pd.Timestamp(event["event_time"]).isoformat(),
                    "y": float(event["price"]),
                    "text": str(event["event_label"]),
                    "showarrow": True,
                    "arrowhead": 2,
                    "ax": 0,
                    "ay": -24,
                    "font": {"size": 11, "color": "#e8edf4"},
                    "arrowcolor": "#aab6c3",
                    "bgcolor": "rgba(11,15,20,0.72)",
                    "bordercolor": "rgba(170,182,195,0.35)",
                    "borderwidth": 1,
                }
            )

    data_payload: List[dict] = [
        {
            "type": "candlestick",
            "x": [pd.Timestamp(ts).isoformat() for ts in daily["open_datetime"]],
            "open": [float(v) for v in daily["open"]],
            "high": [float(v) for v in daily["high"]],
            "low": [float(v) for v in daily["low"]],
            "close": [float(v) for v in daily["close"]],
            "name": symbol,
            "increasing": {"line": {"color": "#2ecc71"}, "fillcolor": "#2ecc71"},
            "decreasing": {"line": {"color": "#e74c3c"}, "fillcolor": "#e74c3c"},
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "bull_regime",
            "x": bull_regime_x,
            "y": bull_regime_y,
            "line": {"color": "#34d399", "width": 5},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "type": "scatter",
            "mode": "lines",
            "name": "bear_regime",
            "x": bear_regime_x,
            "y": bear_regime_y,
            "line": {"color": "#ff6b6b", "width": 5},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "open_regime",
            "x": open_regime_x,
            "y": open_regime_y,
            "line": {"color": "#67e8f9", "width": 3, "dash": "dot"},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "accepted_corrections",
            "x": correction_x,
            "y": correction_y,
            "line": {"color": "#ffd166", "width": 3},
            "marker": {"color": "#ffd166", "size": 7},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "bull_market",
            "x": bull_market_x,
            "y": bull_market_y,
            "line": {"color": "#7cf29a", "width": 7, "dash": "solid"},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "bear_market",
            "x": bear_market_x,
            "y": bear_market_y,
            "line": {"color": "#ff4d6d", "width": 7, "dash": "solid"},
            "hoverinfo": "skip",
        },
        {
            "type": "scatter",
            "mode": "markers+lines",
            "name": "market_cycle",
            "x": market_cycle["event_time"].tolist() if not market_cycle.empty else [],
            "y": market_cycle["price"].astype(float).tolist() if not market_cycle.empty else [],
            "text": market_cycle["event_label"].tolist() if not market_cycle.empty else [],
            "marker": {"color": "#f8fafc", "size": 10, "symbol": "diamond"},
            "line": {"color": "#dfe7f1", "width": 2},
            "hovertemplate": "market cycle<br>%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>",
        },
        {
            "type": "scatter",
            "mode": "markers",
            "name": "active_ath",
            "x": active_ath_events["event_time"].tolist() if not active_ath_events.empty else [],
            "y": active_ath_events["price"].astype(float).tolist() if not active_ath_events.empty else [],
            "text": active_ath_events["event_label"].tolist() if not active_ath_events.empty else [],
            "marker": {"color": "#f59e0b", "size": 12, "symbol": "star"},
            "hovertemplate": "active ath<br>%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>",
        },
        {
            "type": "scatter",
            "mode": "markers",
            "name": "deep_correction",
            "x": deep_corrections["event_time"].tolist() if not deep_corrections.empty else [],
            "y": deep_corrections["price"].astype(float).tolist() if not deep_corrections.empty else [],
            "text": deep_corrections["event_label"].tolist() if not deep_corrections.empty else [],
            "marker": {"color": "#60a5fa", "size": 10, "symbol": "circle"},
            "hovertemplate": "deep correction<br>%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>",
        },
        {
            "type": "scatter",
            "mode": "markers",
            "name": "high_correction",
            "x": high_corrections["event_time"].tolist() if not high_corrections.empty else [],
            "y": high_corrections["price"].astype(float).tolist() if not high_corrections.empty else [],
            "text": high_corrections["event_label"].tolist() if not high_corrections.empty else [],
            "marker": {"color": "#c084fc", "size": 10, "symbol": "circle-open"},
            "hovertemplate": "high correction<br>%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>",
        },
        {
            "type": "scatter",
            "mode": "markers",
            "name": "bear_market_lows",
            "x": current_bear_lows["event_time"].tolist() if not current_bear_lows.empty else [],
            "y": current_bear_lows["price"].astype(float).tolist() if not current_bear_lows.empty else [],
            "text": current_bear_lows["event_label"].tolist() if not current_bear_lows.empty else [],
            "marker": {"color": "#fda4af", "size": 9, "symbol": "x"},
            "hovertemplate": "bear market low<br>%{x}<br>%{y:,.2f}<br>%{text}<extra></extra>",
            "hoverinfo": "skip",
        },
    ]

    layout = {
        "template": "plotly_dark",
        "title": f"{symbol} accepted-only structure with separate regime and market",
        "xaxis": {
            "rangeslider": {"visible": True, "thickness": 0.09},
            "rangeselector": {
                "buttons": [
                    {"count": 1, "label": "1y", "step": "year", "stepmode": "backward"},
                    {"count": 3, "label": "3y", "step": "year", "stepmode": "backward"},
                    {"count": 5, "label": "5y", "step": "year", "stepmode": "backward"},
                    {"step": "all", "label": "All"},
                ]
            },
            "automargin": True,
        },
        "yaxis": {"title": "Price", "automargin": True},
        "hovermode": "x unified",
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        "annotations": [],
        "dragmode": "pan",
        "margin": {"l": 60, "r": 20, "t": 92, "b": 70},
    }

    html = "\n".join(
        [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'><title>Log20 FibTime Fixed</title>",
            (
                "<style>"
                ":root{--plot-width:100vw;--plot-height:calc(100vh - 62px);}"
                "html,body{height:100%;}"
                "body{margin:0;background:#0b0f14;color:#d9e1ea;font-family:Arial,sans-serif;overflow:hidden;}"
                ".toolbar{position:sticky;top:0;z-index:10;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 16px;background:rgba(11,15,20,0.92);border-bottom:1px solid rgba(170,182,195,0.18);}"
                ".toolbar button{background:#17202b;color:#d9e1ea;border:1px solid rgba(170,182,195,0.28);border-radius:8px;padding:8px 12px;cursor:pointer;font-size:14px;}"
                ".toolbar button:hover{background:#223041;}"
                ".toolbar .hint{font-size:13px;color:#9fb0c3;}"
                "#chart-wrap{width:100vw;height:calc(100vh - 62px);overflow:auto;overscroll-behavior:contain;background:#0b0f14;}"
                "#chart-surface{width:var(--plot-width);height:var(--plot-height);min-width:100%;min-height:100%;}"
                "#chart{width:100%;height:100%;}"
                "</style>"
            ),
            f"<script>{plotly_bundle}</script>",
            (
                "</head><body>"
                "<div class='toolbar'>"
                "<button id='fit-all'>Ves grafik</button>"
                "<button id='toggle-labels'>Podpisi: off</button>"
                "<button id='scale-down'>Menshe</button>"
                "<button id='scale-up'>Bolshe</button>"
                "<span class='hint'>Koleso myshi = zoom osey, a bolshaya kartinka dvigaetsya obychnym scroll ili trackpad vnutri oblasti s grafikom.</span>"
                "</div>"
                "<div id='chart-wrap'><div id='chart-surface'><div id='chart'></div></div></div><script>"
            ),
            f"const data = {json.dumps(data_payload, ensure_ascii=False)};",
            f"const layout = {json.dumps(layout, ensure_ascii=False)};",
            f"const labelAnnotations = {json.dumps(market_annotations, ensure_ascii=False)};",
            "const chart = document.getElementById('chart');",
            "const chartWrap = document.getElementById('chart-wrap');",
            "const chartSurface = document.getElementById('chart-surface');",
            "const root = document.documentElement;",
            "let labelsVisible = false;",
            "let plotScale = 1.0;",
            "const config = {responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true, doubleClick:'reset+autosize'};",
            "function fitAll(){Plotly.relayout(chart, {'xaxis.autorange': true, 'yaxis.autorange': true});}",
            "function setLabels(nextVisible){labelsVisible = nextVisible; Plotly.relayout(chart, {annotations: labelsVisible ? labelAnnotations : []}); document.getElementById('toggle-labels').textContent = labelsVisible ? 'Podpisi: on' : 'Podpisi: off';}",
            "function basePlotWidth(){return Math.max(chartWrap.clientWidth, 320);}",
            "function basePlotHeight(){return Math.max(chartWrap.clientHeight, 320);}",
            "function applyScale(){const width=Math.round(basePlotWidth()*plotScale); const height=Math.round(basePlotHeight()*plotScale); root.style.setProperty('--plot-width', width + 'px'); root.style.setProperty('--plot-height', height + 'px'); Plotly.Plots.resize(chart);}",
            "function setScale(nextScale){plotScale = Math.max(1.0, Math.min(3.0, nextScale)); applyScale(); if(plotScale === 1.0){chartWrap.scrollTop = 0; chartWrap.scrollLeft = 0;}}",
            "Plotly.newPlot(chart, data, layout, config).then(() => {fitAll(); setLabels(false); applyScale(); chartWrap.scrollTop = 0; chartWrap.scrollLeft = 0;});",
            "document.getElementById('fit-all').addEventListener('click', () => fitAll());",
            "document.getElementById('toggle-labels').addEventListener('click', () => setLabels(!labelsVisible));",
            "document.getElementById('scale-up').addEventListener('click', () => setScale(plotScale + 0.25));",
            "document.getElementById('scale-down').addEventListener('click', () => setScale(plotScale - 0.25));",
            "window.addEventListener('resize', () => applyScale());",
            "</script></body></html>",
        ]
    )
    output_path.write_text(html, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the original macro_structure_review architecture with log-factor 1.20 "
            "and the five agreed FibTime fixes."
        )
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--cache-dir", default=str(ROOT / "cache_futures_btcusdt"))
    parser.add_argument("--daily-parquet", default="")
    parser.add_argument("--h4-parquet", default="")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs_futures_btcusdt" / "macro_structure_log20_fibtime_fixed"),
    )
    parser.add_argument("--start-date", default="2017-08-17")
    parser.add_argument("--end-date", default="2026-07-07")
    parser.add_argument("--log-factor", type=float, default=1.20)
    parser.add_argument("--fib-ratio", type=float, default=0.382)
    parser.add_argument("--min-fib-days", type=float, default=10.0)
    parser.add_argument("--drawdown-atr-multiple", type=float, default=8.0)
    parser.add_argument("--rebound-atr-multiple", type=float, default=8.0)
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--swing-left", type=int, default=3)
    parser.add_argument("--swing-right", type=int, default=3)
    parser.add_argument("--break-extension-pct", type=float, default=0.02)
    parser.add_argument("--bear-candidate-drawdown-pct", type=float, default=0.40)
    parser.add_argument("--bear-candidate-rebound-pct", type=float, default=0.18)
    parser.add_argument("--bull-candidate-rebound-pct", type=float, default=0.25)
    parser.add_argument("--high-correction-drawdown-pct", type=float, default=0.18)
    parser.add_argument("--deep-correction-drawdown-pct", type=float, default=0.30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cache_dir = Path(args.cache_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_ts = pd.Timestamp(args.start_date, tz=UTC)
    end_ts = pd.Timestamp(args.end_date, tz=UTC)

    daily_path = Path(args.daily_parquet) if args.daily_parquet else (cache_dir / f"{args.symbol}_UMFUT_1D.parquet")
    h4_path = Path(args.h4_parquet) if args.h4_parquet else (cache_dir / f"{args.symbol}_UMFUT_4H.parquet")
    daily_raw = pd.read_parquet(daily_path)
    h4_raw = pd.read_parquet(h4_path)
    daily = old.clean_and_filter(daily_raw, start_ts, end_ts)
    h4 = old.clean_and_filter(
        h4_raw,
        start_ts,
        end_ts + pd.Timedelta(hours=23, minutes=59, seconds=59),
    )
    if daily.empty:
        raise RuntimeError("No 1D rows in the requested date range")

    gap_count_1d = old.count_gap_issues(daily, old.ONE_DAY_MS)
    gap_count_4h = old.count_gap_issues(h4, old.FOUR_HOURS_MS)

    config = old.MacroConfig(
        drawdown_pct=0.20,
        drawdown_atr_multiple=args.drawdown_atr_multiple,
        rebound_pct=0.20,
        rebound_atr_multiple=args.rebound_atr_multiple,
        atr_length=args.atr_length,
        swing_left=args.swing_left,
        swing_right=args.swing_right,
    )

    macro_events_df, macro_legs_df, macro_summary = build_macro_structure_log20(
        daily=daily,
        h4=h4,
        config=config,
        log_factor=args.log_factor,
    )

    macro_events_path = output_dir / "macro_events_log20.csv"
    macro_legs_path = output_dir / "macro_legs_log20.csv"
    raw_html_path = output_dir / "macro_structure_review_log20.html"
    macro_events_df.to_csv(macro_events_path, index=False)
    macro_legs_df.to_csv(macro_legs_path, index=False)
    old.render_html(
        daily,
        macro_events_df,
        macro_legs_df,
        raw_html_path,
        args.symbol,
        macro_summary,
        args.start_date,
        args.end_date,
        preset_label="log_factor_1.20",
    )

    analysis_end_time = ensure_utc(pd.Timestamp(daily["close_datetime"].iloc[-1]))
    (
        impulses_df,
        corrections_df,
        movement_segments_df,
        fib_events_df,
        structural_summary,
    ) = build_structural_impulses_log20_fibtime_fixed(
        macro_events_df,
        macro_legs_df,
        daily=daily,
        h4=h4,
        fib_ratio=args.fib_ratio,
        min_fib_days=args.min_fib_days,
        analysis_end_time=analysis_end_time,
    )

    impulses_path = output_dir / "structural_impulses_log20_fibtime.csv"
    corrections_path = output_dir / "corrections_log20_fibtime.csv"
    movement_segments_path = output_dir / "movement_segments_log20_fibtime.csv"
    fib_events_path = output_dir / "fibtime_events_log20.csv"
    regime_segments_path = output_dir / "structural_regime_segments_log20_fibtime.csv"
    impulses_df.to_csv(impulses_path, index=False)
    corrections_df.to_csv(corrections_path, index=False)
    movement_segments_df.to_csv(movement_segments_path, index=False)
    fib_events_df.to_csv(fib_events_path, index=False)

    regime_segments_df = build_structural_regime_segments(impulses_df)
    regime_segments_df.to_csv(regime_segments_path, index=False)

    market_events_df, market_segments_df, market_daily_df, candidate_diagnostics_df, market_summary = build_market_state_from_macro_swings(
        daily=daily,
        macro_events_df=macro_events_df,
        bear_candidate_drawdown_pct=args.bear_candidate_drawdown_pct,
        bear_candidate_rebound_pct=args.bear_candidate_rebound_pct,
        bull_candidate_rebound_pct=args.bull_candidate_rebound_pct,
        high_correction_drawdown_pct=args.high_correction_drawdown_pct,
        deep_correction_drawdown_pct=args.deep_correction_drawdown_pct,
        break_extension_pct=args.break_extension_pct,
    )

    regime_events_path = output_dir / "market_state_log20_fibtime_events.csv"
    market_segments_path = output_dir / "market_state_log20_fibtime_segments.csv"
    regime_daily_path = output_dir / "market_state_log20_fibtime_daily.csv"
    candidate_diagnostics_path = output_dir / "market_state_candidate_diagnostics_log20_fibtime.csv"
    regime_html_path = output_dir / "macro_structure_with_market_regime_log20_fibtime_fixed.html"
    market_events_df.to_csv(regime_events_path, index=False)
    market_segments_df.to_csv(market_segments_path, index=False)
    market_daily_df.to_csv(regime_daily_path, index=False)
    candidate_diagnostics_df.to_csv(candidate_diagnostics_path, index=False)
    render_log20_fibtime_html(
        daily=daily,
        regime_segments_df=regime_segments_df,
        corrections_df=corrections_df,
        market_segments_df=market_segments_df,
        market_events_df=market_events_df,
        output_path=regime_html_path,
        symbol=args.symbol,
    )

    summary = {
        "params": {
            "log_factor": args.log_factor,
            "log_threshold": math.log(args.log_factor),
            "fib_ratio": args.fib_ratio,
            "min_fib_days": args.min_fib_days,
            "bear_candidate_drawdown_pct": args.bear_candidate_drawdown_pct,
            "bear_candidate_rebound_pct": args.bear_candidate_rebound_pct,
            "bull_candidate_rebound_pct": args.bull_candidate_rebound_pct,
            "high_correction_drawdown_pct": args.high_correction_drawdown_pct,
            "deep_correction_drawdown_pct": args.deep_correction_drawdown_pct,
            "break_extension_pct": args.break_extension_pct,
            "speed_filter_enabled": False,
            "v_rejection_enabled": False,
        },
        "data_range": {
            "daily_first": ensure_utc(daily["open_datetime"].iloc[0]).isoformat(),
            "daily_last": ensure_utc(daily["open_datetime"].iloc[-1]).isoformat(),
            "h4_first": ensure_utc(h4["open_datetime"].iloc[0]).isoformat() if not h4.empty else "",
            "h4_last": ensure_utc(h4["open_datetime"].iloc[-1]).isoformat() if not h4.empty else "",
            "daily_source": str(daily_path),
            "h4_source": str(h4_path),
        },
        "gap_count_1d": gap_count_1d,
        "gap_count_4h": gap_count_4h,
        "macro_summary": macro_summary,
        "structural_summary": structural_summary,
        "market_summary": market_summary,
        "outputs": {
            "macro_events": str(macro_events_path),
            "macro_legs": str(macro_legs_path),
            "raw_html": str(raw_html_path),
            "structural_impulses": str(impulses_path),
            "corrections": str(corrections_path),
            "movement_segments": str(movement_segments_path),
            "fibtime_events": str(fib_events_path),
            "structural_regime_segments": str(regime_segments_path),
            "market_events": str(regime_events_path),
            "market_segments": str(market_segments_path),
            "market_daily": str(regime_daily_path),
            "market_candidate_diagnostics": str(candidate_diagnostics_path),
            "regime_html": str(regime_html_path),
        },
    }
    summary_path = output_dir / "summary_log20_fibtime_fixed.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
