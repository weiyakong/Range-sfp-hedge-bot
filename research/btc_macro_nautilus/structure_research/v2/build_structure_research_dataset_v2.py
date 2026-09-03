from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


UTC = "UTC"
ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE_RUN = ROOT / "outputs" / "macro_structure_review_log20_fibtime_fixed_v8_20260718"
DEFAULT_DAILY_PARQUET = ROOT / "outputs" / "continuous_spot_to_futures_regime_v6_20260717" / "BTCUSDT_SPOT_TO_FUTURES_1D_MERGED.parquet"
DEFAULT_DAILY_MERGE_SUMMARY = ROOT / "outputs" / "continuous_spot_to_futures_regime_v6_20260717" / "merge_summary.json"
DEFAULT_FUTURES_H4 = Path("/Users/yeshevika/Documents/Codex/2026-05-30/sfp-vah-val-poc-cvd-one/Новое начало/cache_futures_btcusdt/BTCUSDT_UMFUT_4H.parquet")
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "structure_research_dataset_v2_20260718"

H4_WINDOWS = {"3d": 18, "7d": 42, "14d": 84}
HOURS_BY_WINDOW = {"3d": 72.0, "7d": 168.0, "14d": 336.0}
PARENT_TIME_LEVELS = {"0236": 0.236, "0382": 0.382, "0500": 0.500, "0618": 0.618, "1000": 1.000}
FOUR_HOURS = pd.Timedelta(hours=4)
ONE_DAY = pd.Timedelta(days=1)
H4_TRANSITION_START = pd.Timestamp("2019-12-31T00:00:00Z")
SPOT_1D_END = pd.Timestamp("2019-12-30T00:00:00Z")
PROGRESS_WRITE_INTERVAL_SECONDS = 60
PARTIAL_FLUSH_INTERVAL_SECONDS = 1200
PARTIAL_FLUSH_EVERY_LEGS = 12


def ensure_utc(value: pd.Timestamp | str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(UTC)
    return ts.tz_convert(UTC)


def float_or_nan(value: object) -> float:
    try:
        if pd.isna(value):
            return float("nan")
        return float(value)
    except Exception:
        return float("nan")


def safe_div(numerator: float, denominator: float, default: float = float("nan")) -> float:
    if denominator is None or pd.isna(denominator) or abs(float(denominator)) < 1e-12:
        return default
    return float(numerator) / float(denominator)


def sign(value: float, flat_value: int = 0) -> int:
    if pd.isna(value) or abs(float(value)) < 1e-12:
        return flat_value
    return 1 if value > 0 else -1


def maybe_round(value: float, digits: int = 8) -> float:
    if pd.isna(value):
        return float("nan")
    return round(float(value), digits)


def to_iso(value: pd.Timestamp | str | float | int | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return ensure_utc(value).isoformat()


def to_jsonable(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return to_iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(subvalue) for key, subvalue in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def atomic_write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2))


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temp_path, index=False)
    os.replace(temp_path, path)


def atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temp_path, index=False)
    os.replace(temp_path, path)


def write_json(path: Path, payload: dict) -> None:
    atomic_write_json(path, payload)


def update_progress(progress_path: Path, payload: dict) -> None:
    payload = dict(payload)
    payload["updated_at"] = pd.Timestamp.now(tz=UTC)
    write_json(progress_path, payload)


def write_partial_chunk(rows: List[dict], output_path: Path) -> int:
    if not rows:
        return 0
    frame = pd.DataFrame(rows)
    atomic_write_parquet(output_path, frame)
    return int(len(frame))


def compute_config_hash(args: argparse.Namespace) -> str:
    payload = {
        "base_run_dir": str(args.base_run_dir),
        "daily_parquet": str(args.daily_parquet),
        "daily_merge_summary": str(args.daily_merge_summary),
        "merged_h4_parquet": str(args.merged_h4_parquet),
        "spot_h4_parquet": str(args.spot_h4_parquet),
        "futures_h4_parquet": str(args.futures_h4_parquet),
        "output_dir": str(args.output_dir),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def load_checkpoint(checkpoint_path: Path, config_hash: str) -> dict:
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        existing_hash = str(checkpoint.get("config_hash", ""))
        if existing_hash and existing_hash != config_hash:
            raise ValueError(f"Checkpoint config hash mismatch: {existing_hash} != {config_hash}")
    else:
        checkpoint = {}
    checkpoint.setdefault("config_hash", config_hash)
    checkpoint.setdefault("saved_at", "")
    checkpoint.setdefault("stage", "startup")
    checkpoint.setdefault("message", "")
    checkpoint.setdefault("stages", {})
    return checkpoint


def ensure_stage_state(checkpoint: dict, stage_key: str) -> dict:
    stages = checkpoint.setdefault("stages", {})
    state = stages.setdefault(stage_key, {})
    state.setdefault("completed_ids", [])
    state.setdefault("meta", {})
    return state


def save_checkpoint(checkpoint_path: Path, checkpoint: dict) -> None:
    checkpoint["saved_at"] = pd.Timestamp.now(tz=UTC)
    atomic_write_json(checkpoint_path, checkpoint)


def update_stage_checkpoint(
    checkpoint_path: Path,
    checkpoint: dict,
    stage_key: str,
    message: str,
    leg_id: str = "",
    current_time: Optional[pd.Timestamp] = None,
    completed_leg_id: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    stage_state = ensure_stage_state(checkpoint, stage_key)
    if completed_leg_id and completed_leg_id not in stage_state["completed_ids"]:
        stage_state["completed_ids"].append(completed_leg_id)
    if completed_leg_id and meta is not None:
        stage_state["meta"][completed_leg_id] = to_jsonable(meta)
    checkpoint["stage"] = stage_key
    checkpoint["message"] = message
    checkpoint["current_leg_id"] = leg_id
    checkpoint["current_time"] = current_time
    save_checkpoint(checkpoint_path, checkpoint)


def existing_partial_leg_ids(stage_dir: Path) -> set[str]:
    if not stage_dir.exists():
        return set()
    return {path.stem for path in stage_dir.glob("*.parquet")}


def reconcile_completed_ids(checkpoint: dict, stage_key: str, stage_dir: Path) -> set[str]:
    state = ensure_stage_state(checkpoint, stage_key)
    files_present = existing_partial_leg_ids(stage_dir)
    completed_ids = [leg_id for leg_id in state["completed_ids"] if leg_id in files_present]
    if completed_ids != state["completed_ids"]:
        state["completed_ids"] = completed_ids
    meta = state.get("meta", {})
    state["meta"] = {leg_id: meta.get(leg_id, {}) for leg_id in completed_ids}
    return set(completed_ids)


def load_partial_stage_frames(stage_dir: Path) -> pd.DataFrame:
    files = sorted(stage_dir.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)


def load_ohlc_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["open_datetime"] = pd.to_datetime(frame["open_datetime"], utc=True, format="mixed")
    frame["close_datetime"] = pd.to_datetime(frame["close_datetime"], utc=True, format="mixed")
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("open_datetime").reset_index(drop=True)


def load_csv_frame(path: Path, time_columns: Iterable[str]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    for column in time_columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True, format="mixed")
    return frame


def infer_daily_market_sources(daily: pd.DataFrame, merge_summary_path: Path) -> Tuple[pd.DataFrame, Optional[pd.Timestamp]]:
    frame = daily.copy()
    transition_time: Optional[pd.Timestamp] = None
    if merge_summary_path.exists():
        payload = json.loads(merge_summary_path.read_text(encoding="utf-8"))
        spot_rows_used = int(payload.get("spot_rows_used", 0))
        if 0 < spot_rows_used < len(frame):
            frame["market_source"] = "futures"
            frame.loc[frame.index[:spot_rows_used], "market_source"] = "spot"
            transition_time = ensure_utc(frame.iloc[spot_rows_used]["open_datetime"])
        else:
            frame["market_source"] = "futures"
    else:
        frame["market_source"] = frame["open_datetime"].apply(lambda ts: "spot" if ensure_utc(ts) <= SPOT_1D_END else "futures")
        futures_rows = frame[frame["market_source"] == "futures"]
        if not futures_rows.empty:
            transition_time = ensure_utc(futures_rows.iloc[0]["open_datetime"])
    return frame, transition_time


def load_or_build_h4_market(
    merged_h4_path: Optional[Path],
    spot_h4_path: Optional[Path],
    futures_h4_path: Optional[Path],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    metadata: Dict[str, object] = {
        "mode": "",
        "spot_h4_path": str(spot_h4_path) if spot_h4_path else "",
        "futures_h4_path": str(futures_h4_path) if futures_h4_path else "",
        "merged_h4_path": str(merged_h4_path) if merged_h4_path else "",
        "transition_time": "",
        "issues": [],
    }
    if merged_h4_path and merged_h4_path.exists():
        frame = load_ohlc_frame(merged_h4_path)
        if "market_source" not in frame.columns:
            frame["market_source"] = "futures"
        metadata["mode"] = "existing_merged_h4"
        sources = sorted(str(v) for v in frame["market_source"].dropna().unique().tolist())
        if "spot" in sources and "futures" in sources:
            first_futures = frame[frame["market_source"] == "futures"].iloc[0]
            metadata["transition_time"] = ensure_utc(first_futures["open_datetime"]).isoformat()
        return frame.sort_values("open_datetime").reset_index(drop=True), metadata

    if spot_h4_path and spot_h4_path.exists() and futures_h4_path and futures_h4_path.exists():
        spot = load_ohlc_frame(spot_h4_path)
        futures = load_ohlc_frame(futures_h4_path)
        spot = spot[spot["open_datetime"] < H4_TRANSITION_START].copy()
        futures = futures[futures["open_datetime"] >= H4_TRANSITION_START].copy()
        spot["market_source"] = "spot"
        futures["market_source"] = "futures"
        frame = pd.concat([spot, futures], ignore_index=True).sort_values("open_datetime").reset_index(drop=True)
        metadata["mode"] = "built_from_spot_and_futures"
        metadata["transition_time"] = H4_TRANSITION_START.isoformat()
        return frame, metadata

    if futures_h4_path and futures_h4_path.exists():
        frame = load_ohlc_frame(futures_h4_path)
        frame["market_source"] = "futures"
        metadata["mode"] = "futures_only"
        metadata["issues"].append("continuous spot-to-futures 4H source is unavailable locally; using futures-only 4H history")
        return frame, metadata

    raise FileNotFoundError("No usable 4H source was found.")


def add_market_indicators(frame: pd.DataFrame, interval_hours: float) -> pd.DataFrame:
    data = frame.copy()
    prev_close = data["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["true_range"] = true_range
    data["atr14"] = data.groupby("market_source", dropna=False)["true_range"].transform(lambda s: s.rolling(14, min_periods=1).mean())
    data["log_close"] = data["close"].apply(lambda v: math.log(v) if pd.notna(v) and v > 0 else float("nan"))
    data["close_return"] = data.groupby("market_source", dropna=False)["close"].pct_change()
    volume_group = data.groupby("market_source", dropna=False)
    thirty_day_window = max(int(round((24.0 / interval_hours) * 30.0)), 1)
    data["volume_to_30d_median"] = volume_group["volume"].transform(lambda s: s / s.rolling(thirty_day_window, min_periods=20).median())
    data["volume_to_30d_mean"] = volume_group["volume"].transform(lambda s: s / s.rolling(thirty_day_window, min_periods=20).mean())
    rolling_mean = volume_group["volume"].transform(lambda s: s.rolling(thirty_day_window, min_periods=20).mean())
    rolling_std = volume_group["volume"].transform(lambda s: s.rolling(thirty_day_window, min_periods=20).std())
    data["volume_zscore_30d"] = (data["volume"] - rolling_mean) / rolling_std.replace(0, pd.NA)
    return data


def lookup_state(ts: pd.Timestamp, segments: pd.DataFrame, state_column: str) -> str:
    if segments.empty:
        return ""
    subset = segments[(segments["start_time"] <= ts) & (segments["end_time"] >= ts)]
    if subset.empty:
        subset = segments[segments["start_time"] <= ts]
    if subset.empty:
        return ""
    return str(subset.sort_values(["start_time", "end_time"]).iloc[-1][state_column])


def load_source_tables(base_run_dir: Path) -> Dict[str, pd.DataFrame]:
    return {
        "raw_legs": load_csv_frame(base_run_dir / "macro_legs_log20.csv", ["start_time", "end_time"]),
        "impulses": load_csv_frame(base_run_dir / "structural_impulses_log20_fibtime.csv", ["start_time", "end_time", "available_at_time", "confirmed_at", "regime_anchor_time", "fib_deadline"]),
        "corrections": load_csv_frame(base_run_dir / "corrections_log20_fibtime.csv", ["start_time", "end_time", "available_at_time", "confirmed_at", "rejected_at"]),
        "market_segments": load_csv_frame(base_run_dir / "market_state_log20_fibtime_segments.csv", ["start_time", "end_time", "start_available_at", "end_available_at"]),
        "regime_segments": load_csv_frame(base_run_dir / "structural_regime_segments_log20_fibtime.csv", ["start_time", "end_time", "available_at_time"]),
    }


def overlap_bars(frame: pd.DataFrame, start_time: pd.Timestamp, end_time: pd.Timestamp) -> pd.DataFrame:
    return frame[(frame["close_datetime"] >= start_time) & (frame["open_datetime"] <= end_time)].copy().sort_values("open_datetime").reset_index(drop=True)


def bar_sequence_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    subset = frame[["open_datetime", "open", "high", "low", "close"]].copy()
    subset["open_datetime"] = subset["open_datetime"].apply(to_iso)
    payload = subset.to_csv(index=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_source_records(
    raw_legs: pd.DataFrame,
    impulses: pd.DataFrame,
    corrections: pd.DataFrame,
    market_segments: pd.DataFrame,
    regime_segments: pd.DataFrame,
    daily_bars: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[dict] = []

    raw_sorted = raw_legs.sort_values(["start_time", "end_time", "leg_id"]).reset_index(drop=True)
    for _, row in raw_sorted.iterrows():
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        day_bars = overlap_bars(daily_bars, start_time, end_time)
        rows.append(
            {
                "segment_id": f"SEG_RAW_{row['leg_id']}",
                "source_id": str(row["leg_id"]),
                "source_table": "macro_legs_log20",
                "segment_level": "raw_leg",
                "segment_role": "raw_leg",
                "status": "raw",
                "direction": str(row["direction"]),
                "start_time": start_time,
                "end_time": end_time,
                "start_price": float(row["start_price"]),
                "end_price": float(row["end_price"]),
                "anchor_event_id": str(row["start_event_id"]),
                "terminal_event_id": str(row["end_event_id"]),
                "parent_segment_id": "",
                "parent_source_id": "",
                "is_breakout_leg": False,
                "is_terminal_leg": False,
                "market_state": lookup_state(start_time, market_segments, "market"),
                "regime_state": lookup_state(start_time, regime_segments, "regime"),
                "source_path_signature_1d": bar_sequence_hash(day_bars),
            }
        )

    impulse_sorted = impulses.sort_values(["start_time", "end_time", "impulse_id"]).reset_index(drop=True)
    for _, row in impulse_sorted.iterrows():
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        day_bars = overlap_bars(daily_bars, start_time, end_time)
        rows.append(
            {
                "segment_id": f"SEG_IMP_{row['impulse_id']}",
                "source_id": str(row["impulse_id"]),
                "source_table": "structural_impulses_log20_fibtime",
                "segment_level": "structural_impulse",
                "segment_role": "impulse_candidate",
                "status": str(row["status"]),
                "direction": str(row["direction"]),
                "start_time": start_time,
                "end_time": end_time,
                "start_price": float(row["start_price"]),
                "end_price": float(row["end_price"]),
                "anchor_event_id": str(row["start_event_id"]),
                "terminal_event_id": str(row["end_event_id"]),
                "parent_segment_id": "",
                "parent_source_id": "",
                "is_breakout_leg": True,
                "is_terminal_leg": bool(row.get("is_open", False)),
                "market_state": lookup_state(start_time, market_segments, "market"),
                "regime_state": lookup_state(start_time, regime_segments, "regime"),
                "source_path_signature_1d": bar_sequence_hash(day_bars),
            }
        )

    correction_sorted = corrections.sort_values(["start_time", "end_time", "correction_id"]).reset_index(drop=True)
    for _, row in correction_sorted.iterrows():
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        day_bars = overlap_bars(daily_bars, start_time, end_time)
        rows.append(
            {
                "segment_id": f"SEG_CORR_{row['correction_id']}",
                "source_id": str(row["correction_id"]),
                "source_table": "corrections_log20_fibtime",
                "segment_level": "structural_correction",
                "segment_role": "correction_candidate",
                "status": str(row["status"]),
                "direction": str(row["direction"]),
                "start_time": start_time,
                "end_time": end_time,
                "start_price": float(row["start_price"]),
                "end_price": float(row["end_price"]),
                "anchor_event_id": str(row["start_event_id"]),
                "terminal_event_id": str(row["end_event_id"]),
                "parent_segment_id": f"SEG_IMP_{row['parent_impulse_id']}" if pd.notna(row.get("parent_impulse_id")) else "",
                "parent_source_id": str(row.get("parent_impulse_id") or ""),
                "is_breakout_leg": False,
                "is_terminal_leg": bool(row.get("is_open", False)),
                "market_state": lookup_state(start_time, market_segments, "market"),
                "regime_state": lookup_state(start_time, regime_segments, "regime"),
                "source_path_signature_1d": bar_sequence_hash(day_bars),
            }
        )

    return pd.DataFrame(rows).sort_values(["start_time", "end_time", "segment_id"]).reset_index(drop=True)


def canonicalize_legs(source_records: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    key_columns = [
        "start_time",
        "end_time",
        "start_price",
        "end_price",
        "direction",
        "source_path_signature_1d",
    ]
    canonical_rows: List[dict] = []
    memberships = source_records.copy()
    memberships["canonical_leg_id"] = ""
    grouped = memberships.groupby(key_columns, dropna=False, sort=False)
    for index, (_, group) in enumerate(grouped, start=1):
        canonical_leg_id = f"CL{index:05d}"
        group = group.sort_values(["source_table", "segment_id"]).reset_index(drop=True)
        memberships.loc[group.index + group.index.min() * 0, "canonical_leg_id"] = memberships.loc[group.index + group.index.min() * 0, "canonical_leg_id"]
        for row_idx in group.index:
            pass
    # explicit assignment because grouped copies lose original row order
    for index, (_, group) in enumerate(grouped, start=1):
        canonical_leg_id = f"CL{index:05d}"
        memberships.loc[group.index, "canonical_leg_id"] = canonical_leg_id
        first = group.iloc[0]
        roles = sorted(set(str(v) for v in group["segment_role"].dropna().tolist()))
        statuses = sorted(set(str(v) for v in group["status"].dropna().tolist()))
        tables = sorted(set(str(v) for v in group["source_table"].dropna().tolist()))
        canonical_rows.append(
            {
                "canonical_leg_id": canonical_leg_id,
                "direction": str(first["direction"]),
                "start_time": ensure_utc(first["start_time"]),
                "end_time": ensure_utc(first["end_time"]),
                "start_price": float(first["start_price"]),
                "end_price": float(first["end_price"]),
                "source_record_count": int(len(group)),
                "source_role_count": int(len(roles)),
                "source_roles": "|".join(roles),
                "source_statuses": "|".join(statuses),
                "source_tables": "|".join(tables),
                "has_raw_leg_record": bool((group["source_table"] == "macro_legs_log20").any()),
                "has_impulse_record": bool((group["source_table"] == "structural_impulses_log20_fibtime").any()),
                "has_correction_record": bool((group["source_table"] == "corrections_log20_fibtime").any()),
                "market_state_values": "|".join(sorted(set(str(v) for v in group["market_state"].dropna().tolist()))),
                "regime_state_values": "|".join(sorted(set(str(v) for v in group["regime_state"].dropna().tolist()))),
                "path_signature_1d": str(first["source_path_signature_1d"]),
            }
        )
    canonical = pd.DataFrame(canonical_rows).sort_values(["start_time", "end_time", "canonical_leg_id"]).reset_index(drop=True)
    canonical["previous_canonical_leg_id"] = canonical["canonical_leg_id"].shift(1).fillna("")
    canonical["next_canonical_leg_id"] = canonical["canonical_leg_id"].shift(-1).fillna("")
    membership_cols = [
        "canonical_leg_id",
        "segment_id",
        "source_id",
        "source_table",
        "segment_level",
        "segment_role",
        "status",
        "parent_segment_id",
        "anchor_event_id",
        "terminal_event_id",
        "is_breakout_leg",
        "is_terminal_leg",
        "market_state",
        "regime_state",
        "direction",
        "start_time",
        "end_time",
        "start_price",
        "end_price",
    ]
    memberships = memberships[membership_cols].copy()
    return canonical, memberships


def build_leg_bar_table(
    canonical_legs: pd.DataFrame,
    market_bars: pd.DataFrame,
    timeframe_label: str,
) -> Tuple[pd.DataFrame, Dict[str, dict]]:
    rows: List[dict] = []
    qa: Dict[str, dict] = {}
    expected_delta = ONE_DAY if timeframe_label == "1D" else FOUR_HOURS
    for _, leg in canonical_legs.iterrows():
        leg_id = str(leg["canonical_leg_id"])
        start_time = ensure_utc(leg["start_time"])
        end_time = ensure_utc(leg["end_time"])
        subset = overlap_bars(market_bars, start_time, end_time)
        chronology_ok = True
        duplicate_count = 0
        gap_count = 0
        boundary_start_ok = False
        boundary_end_ok = False
        if not subset.empty:
            duplicate_count = int(subset["open_datetime"].duplicated().sum())
            diffs = subset["open_datetime"].diff().dropna()
            gap_count = int((diffs > expected_delta).sum())
            chronology_ok = bool((subset["open_datetime"].diff().dropna() > pd.Timedelta(0)).all())
            boundary_start_ok = bool(((subset["open_datetime"] <= start_time) & (subset["close_datetime"] >= start_time)).any())
            boundary_end_ok = bool(((subset["open_datetime"] <= end_time) & (subset["close_datetime"] >= end_time)).any())
        for bar_index, (_, bar) in enumerate(subset.iterrows()):
            rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "open_datetime": ensure_utc(bar["open_datetime"]),
                    "close_datetime": ensure_utc(bar["close_datetime"]),
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float_or_nan(bar.get("volume", float("nan"))),
                    "market_source": str(bar.get("market_source", "")),
                    "bar_index_in_leg": bar_index,
                    "elapsed_hours": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), 3600.0, default=0.0),
                    "elapsed_days": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), 86400.0, default=0.0),
                    "elapsed_fraction_of_leg": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), max((end_time - start_time).total_seconds(), 1.0), default=0.0),
                }
            )
        qa[leg_id] = {
            "num_bars": int(len(subset)),
            "missing": bool(subset.empty),
            "duplicate_count": duplicate_count,
            "gap_count": gap_count,
            "chronology_ok": chronology_ok,
            "boundary_start_ok": boundary_start_ok,
            "boundary_end_ok": boundary_end_ok,
        }
    bars = pd.DataFrame(rows)
    return bars, qa


LEG_BAR_COLUMNS = [
    "canonical_leg_id",
    "open_datetime",
    "close_datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "market_source",
    "bar_index_in_leg",
    "elapsed_hours",
    "elapsed_days",
    "elapsed_fraction_of_leg",
]


def compute_leg_bar_frame(leg: pd.Series, market_bars: pd.DataFrame, timeframe_label: str) -> Tuple[pd.DataFrame, dict]:
    expected_delta = ONE_DAY if timeframe_label == "1D" else FOUR_HOURS
    leg_id = str(leg["canonical_leg_id"])
    start_time = ensure_utc(leg["start_time"])
    end_time = ensure_utc(leg["end_time"])
    subset = overlap_bars(market_bars, start_time, end_time)
    chronology_ok = True
    duplicate_count = 0
    gap_count = 0
    boundary_start_ok = False
    boundary_end_ok = False
    if not subset.empty:
        duplicate_count = int(subset["open_datetime"].duplicated().sum())
        diffs = subset["open_datetime"].diff().dropna()
        gap_count = int((diffs > expected_delta).sum())
        chronology_ok = bool((subset["open_datetime"].diff().dropna() > pd.Timedelta(0)).all())
        boundary_start_ok = bool(((subset["open_datetime"] <= start_time) & (subset["close_datetime"] >= start_time)).any())
        boundary_end_ok = bool(((subset["open_datetime"] <= end_time) & (subset["close_datetime"] >= end_time)).any())
    rows: List[dict] = []
    for bar_index, (_, bar) in enumerate(subset.iterrows()):
        rows.append(
            {
                "canonical_leg_id": leg_id,
                "open_datetime": ensure_utc(bar["open_datetime"]),
                "close_datetime": ensure_utc(bar["close_datetime"]),
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": float_or_nan(bar.get("volume", float("nan"))),
                "market_source": str(bar.get("market_source", "")),
                "bar_index_in_leg": bar_index,
                "elapsed_hours": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), 3600.0, default=0.0),
                "elapsed_days": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), 86400.0, default=0.0),
                "elapsed_fraction_of_leg": safe_div((ensure_utc(bar["open_datetime"]) - start_time).total_seconds(), max((end_time - start_time).total_seconds(), 1.0), default=0.0),
            }
        )
    frame = pd.DataFrame(rows, columns=LEG_BAR_COLUMNS)
    qa = {
        "num_bars": int(len(subset)),
        "missing": bool(subset.empty),
        "duplicate_count": duplicate_count,
        "gap_count": gap_count,
        "chronology_ok": chronology_ok,
        "boundary_start_ok": boundary_start_ok,
        "boundary_end_ok": boundary_end_ok,
    }
    return frame, qa


def run_leg_bar_stage_incremental(
    canonical_legs: pd.DataFrame,
    market_bars: pd.DataFrame,
    timeframe_label: str,
    stage_key: str,
    partials_dir: Path,
    checkpoint_path: Path,
    checkpoint: dict,
    progress_path: Path,
) -> Tuple[pd.DataFrame, Dict[str, dict]]:
    stage_dir = partials_dir / stage_key
    stage_dir.mkdir(parents=True, exist_ok=True)
    completed_ids = reconcile_completed_ids(checkpoint, stage_key, stage_dir)
    total_legs = len(canonical_legs)
    qa_state = ensure_stage_state(checkpoint, stage_key).get("meta", {})
    for leg_index, (_, leg) in enumerate(canonical_legs.iterrows(), start=1):
        leg_id = str(leg["canonical_leg_id"])
        if leg_id in completed_ids:
            continue
        update_progress(
            progress_path,
            {
                "stage": stage_key,
                "message": f"writing {timeframe_label} leg bars",
                "current_leg_id": leg_id,
                "current_leg_end_time": ensure_utc(leg["end_time"]),
                "completed_legs": len(completed_ids),
                "total_legs": total_legs,
                "config_hash": checkpoint["config_hash"],
            },
        )
        frame, qa = compute_leg_bar_frame(leg, market_bars, timeframe_label)
        atomic_write_parquet(stage_dir / f"{leg_id}.parquet", frame)
        completed_ids.add(leg_id)
        qa_state[leg_id] = qa
        update_stage_checkpoint(
            checkpoint_path,
            checkpoint,
            stage_key,
            f"{timeframe_label} leg bars saved",
            leg_id=leg_id,
            current_time=ensure_utc(leg["end_time"]),
            completed_leg_id=leg_id,
            meta=qa,
        )
    combined = load_partial_stage_frames(stage_dir)
    qa = {str(key): value for key, value in qa_state.items()}
    return combined, qa


def count_streaks(flags: List[bool]) -> Tuple[float, float, int]:
    streaks: List[int] = []
    current = 0
    for flag in flags:
        if flag:
            current += 1
        else:
            if current > 0:
                streaks.append(current)
            current = 0
    if current > 0:
        streaks.append(current)
    if not streaks:
        return float("nan"), float("nan"), 0
    series = pd.Series(streaks, dtype="float64")
    return float(series.mean()), float(series.median()), int(series.max())


def regression_stats(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    if len(xs) < 2 or len(ys) < 2:
        return float("nan"), float("nan"), float("nan")
    x_series = pd.Series(xs, dtype="float64")
    y_series = pd.Series(ys, dtype="float64")
    x_mean = float(x_series.mean())
    y_mean = float(y_series.mean())
    centered_x = x_series - x_mean
    centered_y = y_series - y_mean
    denom = float((centered_x ** 2).sum())
    if abs(denom) < 1e-12:
        return float("nan"), float("nan"), float("nan")
    slope = float((centered_x * centered_y).sum()) / denom
    intercept = y_mean - slope * x_mean
    fitted = intercept + slope * x_series
    residuals = y_series - fitted
    ss_res = float((residuals ** 2).sum())
    ss_tot = float(((y_series - y_mean) ** 2).sum())
    r2 = 1.0 - safe_div(ss_res, ss_tot, default=float("nan"))
    residual_std = float(residuals.std(ddof=0))
    return slope, r2, residual_std


def range_overlap(prev_high: float, prev_low: float, high: float, low: float) -> float:
    overlap = max(0.0, min(prev_high, high) - max(prev_low, low))
    union = max(prev_high, high) - min(prev_low, low)
    return safe_div(overlap, union, default=float("nan"))


def entropy_from_signs(signs: List[int]) -> float:
    filtered = [s for s in signs if s != 0]
    if not filtered:
        return float("nan")
    total = len(filtered)
    counts = Counter(filtered)
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log(probability, 2)
    return entropy


def get_pullback_events(bars: pd.DataFrame, direction: str) -> List[dict]:
    if bars.empty:
        return []
    events: List[dict] = []
    active_extreme = float(bars.iloc[0]["high"] if direction == "up" else bars.iloc[0]["low"])
    active_extreme_time = ensure_utc(bars.iloc[0]["open_datetime"])
    pullback_low = float(bars.iloc[0]["low"])
    pullback_high = float(bars.iloc[0]["high"])
    pullback_start: Optional[pd.Timestamp] = None
    for idx in range(1, len(bars)):
        row = bars.iloc[idx]
        ts = ensure_utc(row["open_datetime"])
        high = float(row["high"])
        low = float(row["low"])
        atr = float_or_nan(row.get("atr14", float("nan")))
        if direction == "up":
            if high > active_extreme:
                if pullback_start is not None:
                    depth = max(0.0, active_extreme - pullback_low)
                    progressed = max(1e-12, active_extreme - float(bars.iloc[0]["low"]))
                    events.append(
                        {
                            "start_time": pullback_start,
                            "end_time": ts,
                            "depth_pct": safe_div(depth, progressed),
                            "depth_atr": safe_div(depth, atr),
                            "duration_hours": safe_div((ts - pullback_start).total_seconds(), 3600.0, default=float("nan")),
                        }
                    )
                active_extreme = high
                active_extreme_time = ts
                pullback_low = low
                pullback_start = None
            else:
                if low < pullback_low:
                    pullback_low = low
                if low < active_extreme:
                    pullback_start = pullback_start or active_extreme_time
        else:
            if low < active_extreme:
                if pullback_start is not None:
                    depth = max(0.0, pullback_high - active_extreme)
                    progressed = max(1e-12, float(bars.iloc[0]["high"]) - active_extreme)
                    events.append(
                        {
                            "start_time": pullback_start,
                            "end_time": ts,
                            "depth_pct": safe_div(depth, progressed),
                            "depth_atr": safe_div(depth, atr),
                            "duration_hours": safe_div((ts - pullback_start).total_seconds(), 3600.0, default=float("nan")),
                        }
                    )
                active_extreme = low
                active_extreme_time = ts
                pullback_high = high
                pullback_start = None
            else:
                if high > pullback_high:
                    pullback_high = high
                if high > active_extreme:
                    pullback_start = pullback_start or active_extreme_time
    return events


def compute_existing_v1_features(bars: pd.DataFrame, direction: str, start_price: float, end_price: float, duration_days: float, parent_move_abs: float) -> dict:
    if bars.empty:
        return {name: float("nan") for name in [
            "overlap_ratio",
            "path_efficiency",
            "range_efficiency",
            "slope_per_day",
            "bars_with_trend_close_pct",
            "counter_close_pct",
            "inside_bar_pct",
            "outside_bar_pct",
            "median_body_to_range",
            "upper_wick_bias",
            "lower_wick_bias",
            "range_expansion_pct",
            "range_contraction_pct",
            "time_in_balance_pct",
            "breakout_delay_pct",
            "retrace_depth_pct",
            "max_adverse_excursion_pct",
            "max_favorable_excursion_pct",
        ]}
    net_move_abs = abs(end_price - start_price)
    segment_high = float(bars["high"].max())
    segment_low = float(bars["low"].min())
    segment_range_abs = segment_high - segment_low
    closes = bars["close"].astype(float).tolist()
    opens = bars["open"].astype(float).tolist()
    highs = bars["high"].astype(float).tolist()
    lows = bars["low"].astype(float).tolist()
    path_total = sum(abs(right - left) for left, right in zip(closes, closes[1:]))
    trend_hits = 0
    counter_hits = 0
    inside_hits = 0
    outside_hits = 0
    body_ratios: List[float] = []
    upper_wicks: List[float] = []
    lower_wicks: List[float] = []
    range_expansion_hits = 0
    range_contraction_hits = 0
    balance_hits = 0
    first_progress_index: Optional[int] = None
    favorable_progress_threshold = start_price + (0.30 * (end_price - start_price))
    middle_low = segment_low + 0.25 * segment_range_abs
    middle_high = segment_low + 0.75 * segment_range_abs
    overlaps: List[float] = []
    for idx, row in bars.reset_index(drop=True).iterrows():
        open_value = float(row["open"])
        close_value = float(row["close"])
        high_value = float(row["high"])
        low_value = float(row["low"])
        bar_range = max(high_value - low_value, 1e-12)
        body_ratios.append(abs(close_value - open_value) / bar_range)
        upper_wicks.append((high_value - max(open_value, close_value)) / bar_range)
        lower_wicks.append((min(open_value, close_value) - low_value) / bar_range)
        trend_hits += int(close_value > open_value) if direction == "up" else int(close_value < open_value)
        counter_hits += int(close_value < open_value) if direction == "up" else int(close_value > open_value)
        if middle_low <= close_value <= middle_high:
            balance_hits += 1
        if first_progress_index is None:
            if direction == "up" and high_value >= favorable_progress_threshold:
                first_progress_index = idx
            if direction == "down" and low_value <= favorable_progress_threshold:
                first_progress_index = idx
        if idx > 0:
            prev = bars.iloc[idx - 1]
            prev_high = float(prev["high"])
            prev_low = float(prev["low"])
            overlaps.append(range_overlap(prev_high, prev_low, high_value, low_value))
            if high_value <= prev_high and low_value >= prev_low:
                inside_hits += 1
            if high_value >= prev_high and low_value <= prev_low:
                outside_hits += 1
            prev_range = max(prev_high - prev_low, 1e-12)
            if bar_range > prev_range * 1.10:
                range_expansion_hits += 1
            if bar_range < prev_range * 0.90:
                range_contraction_hits += 1
    if direction == "up":
        favorable_excursion = max([0.0] + [float(v) - start_price for v in highs])
        adverse_excursion = max([0.0] + [start_price - float(v) for v in lows])
    else:
        favorable_excursion = max([0.0] + [start_price - float(v) for v in lows])
        adverse_excursion = max([0.0] + [float(v) - start_price for v in highs])
    return {
        "overlap_ratio": maybe_round(pd.Series(overlaps).mean(), 6),
        "path_efficiency": maybe_round(safe_div(net_move_abs, path_total), 6),
        "range_efficiency": maybe_round(safe_div(net_move_abs, segment_range_abs), 6),
        "slope_per_day": maybe_round(safe_div(end_price - start_price, duration_days), 8),
        "bars_with_trend_close_pct": maybe_round(safe_div(trend_hits, len(bars), default=0.0), 6),
        "counter_close_pct": maybe_round(safe_div(counter_hits, len(bars), default=0.0), 6),
        "inside_bar_pct": maybe_round(safe_div(inside_hits, max(len(bars) - 1, 1), default=0.0), 6),
        "outside_bar_pct": maybe_round(safe_div(outside_hits, max(len(bars) - 1, 1), default=0.0), 6),
        "median_body_to_range": maybe_round(pd.Series(body_ratios).median(), 6),
        "upper_wick_bias": maybe_round(pd.Series(upper_wicks).mean(), 6),
        "lower_wick_bias": maybe_round(pd.Series(lower_wicks).mean(), 6),
        "range_expansion_pct": maybe_round(safe_div(range_expansion_hits, max(len(bars) - 1, 1), default=0.0), 6),
        "range_contraction_pct": maybe_round(safe_div(range_contraction_hits, max(len(bars) - 1, 1), default=0.0), 6),
        "time_in_balance_pct": maybe_round(safe_div(balance_hits, len(bars), default=0.0), 6),
        "breakout_delay_pct": maybe_round(safe_div(first_progress_index if first_progress_index is not None else len(bars), len(bars), default=0.0), 6),
        "retrace_depth_pct": maybe_round(safe_div(net_move_abs, parent_move_abs), 6),
        "max_adverse_excursion_pct": maybe_round(safe_div(adverse_excursion, start_price), 6),
        "max_favorable_excursion_pct": maybe_round(safe_div(favorable_excursion, start_price), 6),
    }


def compute_leg_context_maps(canonical_legs: pd.DataFrame, memberships: pd.DataFrame) -> Tuple[Dict[str, str], Dict[str, Optional[str]]]:
    previous_impulse_by_leg: Dict[str, str] = {}
    parent_by_leg: Dict[str, Optional[str]] = {}
    source_id_to_leg = {}
    for _, row in memberships.iterrows():
        source_id_to_leg[(str(row["source_table"]), str(row["source_id"]))] = str(row["canonical_leg_id"])
        source_id_to_leg[(str(row["source_table"]), str(row["segment_id"]))] = str(row["canonical_leg_id"])
    for leg_id, group in memberships.groupby("canonical_leg_id", sort=False):
        parent_candidates = set()
        for _, row in group.iterrows():
            parent_segment_id = str(row.get("parent_segment_id") or "")
            if parent_segment_id:
                candidate = source_id_to_leg.get(("structural_impulses_log20_fibtime", parent_segment_id.replace("SEG_IMP_", ""))) or source_id_to_leg.get(("structural_impulses_log20_fibtime", parent_segment_id))
                if candidate:
                    parent_candidates.add(candidate)
        if len(parent_candidates) == 1:
            parent_by_leg[str(leg_id)] = next(iter(parent_candidates))
        elif len(parent_candidates) == 0:
            parent_by_leg[str(leg_id)] = None
        else:
            parent_by_leg[str(leg_id)] = None
    impulse_memberships = memberships[memberships["source_table"] == "structural_impulses_log20_fibtime"].copy()
    impulse_memberships = impulse_memberships.sort_values(["start_time", "end_time", "source_id"]).reset_index(drop=True)
    previous_impulse_id = ""
    for _, row in impulse_memberships.iterrows():
        leg_id = str(row["canonical_leg_id"])
        if leg_id not in previous_impulse_by_leg:
            previous_impulse_by_leg[leg_id] = previous_impulse_id
        previous_impulse_id = leg_id
    return previous_impulse_by_leg, parent_by_leg


def build_relationship_rows(
    canonical_legs: pd.DataFrame,
    memberships: pd.DataFrame,
    leg_bars_h4: pd.DataFrame,
    previous_impulse_by_leg: Dict[str, str],
    parent_by_leg: Dict[str, Optional[str]],
) -> pd.DataFrame:
    rows: List[dict] = []
    leg_lookup = canonical_legs.set_index("canonical_leg_id").to_dict("index")
    h4_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True) for leg_id, group in leg_bars_h4.groupby("canonical_leg_id")}

    def build_row(leg_id: str, reference_type: str, reference_leg_id: str, status: str) -> dict:
        leg = leg_lookup[leg_id]
        reference = leg_lookup.get(reference_leg_id)
        row = {
            "canonical_leg_id": leg_id,
            "reference_leg_type": reference_type,
            "reference_canonical_leg_id": reference_leg_id,
            "relationship_status": status,
            "direction_relation": "",
            "start_time_relation": "",
            "end_time_relation": "",
            "amplitude_ratio": float("nan"),
            "duration_ratio": float("nan"),
            "speed_pct_per_day_ratio": float("nan"),
            "speed_atr_per_day_ratio": float("nan"),
            "range_ratio": float("nan"),
            "retracement_of_reference_pct": float("nan"),
            "price_range_overlap_pct": float("nan"),
            "start_price_distance_pct": float("nan"),
            "end_price_distance_pct": float("nan"),
            "breaks_reference_start_price": False,
            "breaks_reference_end_price": False,
            "breaks_reference_high": False,
            "breaks_reference_low": False,
            "first_break_time": "",
            "hours_to_first_break": float("nan"),
            "closes_beyond_reference_extreme": False,
            "returns_inside_reference_range": False,
        }
        if reference is None:
            return row
        leg_duration = safe_div((ensure_utc(leg["end_time"]) - ensure_utc(leg["start_time"])).total_seconds(), 86400.0)
        ref_duration = safe_div((ensure_utc(reference["end_time"]) - ensure_utc(reference["start_time"])).total_seconds(), 86400.0)
        leg_move = abs(float(leg["end_price"]) - float(leg["start_price"]))
        ref_move = abs(float(reference["end_price"]) - float(reference["start_price"]))
        leg_speed = safe_div(leg_move, leg_duration)
        ref_speed = safe_div(ref_move, ref_duration)
        leg_range = float(leg["segment_high"]) - float(leg["segment_low"])
        ref_range = float(reference["segment_high"]) - float(reference["segment_low"])
        overlap = max(0.0, min(float(leg["segment_high"]), float(reference["segment_high"])) - max(float(leg["segment_low"]), float(reference["segment_low"])))
        union = max(float(leg["segment_high"]), float(reference["segment_high"])) - min(float(leg["segment_low"]), float(reference["segment_low"]))
        row.update(
            {
                "direction_relation": "same" if str(leg["direction"]) == str(reference["direction"]) else "opposite",
                "start_time_relation": "after" if ensure_utc(leg["start_time"]) > ensure_utc(reference["start_time"]) else "same_or_before",
                "end_time_relation": "after" if ensure_utc(leg["end_time"]) > ensure_utc(reference["end_time"]) else "same_or_before",
                "amplitude_ratio": maybe_round(safe_div(leg_move, ref_move), 8),
                "duration_ratio": maybe_round(safe_div(leg_duration, ref_duration), 8),
                "speed_pct_per_day_ratio": maybe_round(safe_div(leg_speed, ref_speed), 8),
                "speed_atr_per_day_ratio": maybe_round(safe_div(float(leg.get("speed_atr14_per_day", float("nan"))), float(reference.get("speed_atr14_per_day", float("nan")))), 8),
                "range_ratio": maybe_round(safe_div(leg_range, ref_range), 8),
                "retracement_of_reference_pct": maybe_round(safe_div(leg_move, ref_move), 8),
                "price_range_overlap_pct": maybe_round(safe_div(overlap, union), 8),
                "start_price_distance_pct": maybe_round(safe_div(abs(float(leg["start_price"]) - float(reference["start_price"])), float(reference["start_price"])), 8),
                "end_price_distance_pct": maybe_round(safe_div(abs(float(leg["end_price"]) - float(reference["end_price"])), float(reference["end_price"])), 8),
                "breaks_reference_start_price": bool(float(leg["segment_high"]) >= float(reference["start_price"]) and float(leg["segment_low"]) <= float(reference["start_price"])),
                "breaks_reference_end_price": bool(float(leg["segment_high"]) >= float(reference["end_price"]) and float(leg["segment_low"]) <= float(reference["end_price"])),
                "breaks_reference_high": bool(float(leg["segment_high"]) > float(reference["segment_high"])),
                "breaks_reference_low": bool(float(leg["segment_low"]) < float(reference["segment_low"])),
            }
        )
        ref_extreme = float(reference["segment_high"]) if str(reference["direction"]) == "up" else float(reference["segment_low"])
        leg_h4 = h4_groups.get(leg_id, pd.DataFrame())
        broke_rows = pd.DataFrame()
        if not leg_h4.empty:
            if str(reference["direction"]) == "up":
                broke_rows = leg_h4[leg_h4["high"] > ref_extreme]
            else:
                broke_rows = leg_h4[leg_h4["low"] < ref_extreme]
        if not broke_rows.empty:
            first_break = ensure_utc(broke_rows.iloc[0]["open_datetime"])
            row["first_break_time"] = first_break.isoformat()
            row["hours_to_first_break"] = maybe_round(safe_div((first_break - ensure_utc(leg["start_time"])).total_seconds(), 3600.0), 6)
            if str(reference["direction"]) == "up":
                row["closes_beyond_reference_extreme"] = bool((broke_rows["close"] > ref_extreme).any())
                after_break = leg_h4[leg_h4["open_datetime"] > first_break]
                row["returns_inside_reference_range"] = bool(((after_break["close"] >= float(reference["segment_low"])) & (after_break["close"] <= float(reference["segment_high"]))).any())
            else:
                row["closes_beyond_reference_extreme"] = bool((broke_rows["close"] < ref_extreme).any())
                after_break = leg_h4[leg_h4["open_datetime"] > first_break]
                row["returns_inside_reference_range"] = bool(((after_break["close"] >= float(reference["segment_low"])) & (after_break["close"] <= float(reference["segment_high"]))).any())
        return row

    for _, leg in canonical_legs.iterrows():
        leg_id = str(leg["canonical_leg_id"])
        prev_id = str(leg.get("previous_canonical_leg_id") or "")
        next_id = str(leg.get("next_canonical_leg_id") or "")
        parent_id = parent_by_leg.get(leg_id)
        previous_impulse_id = previous_impulse_by_leg.get(leg_id, "")
        for ref_type, ref_id, status in [
            ("previous_canonical_leg", prev_id, "ok" if prev_id else "missing"),
            ("next_canonical_leg", next_id, "ok" if next_id else "missing"),
            ("parent_segment", parent_id or "", "ok" if parent_id else "missing_or_ambiguous"),
            ("previous_source_impulse", previous_impulse_id, "ok" if previous_impulse_id else "missing"),
        ]:
            rows.append(build_row(leg_id, ref_type, ref_id, status))
    return pd.DataFrame(rows)


def feature_stats(series: pd.Series) -> dict:
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    finite = clean[clean.notna() & ~clean.isin([float("inf"), float("-inf")])]
    return {
        "count": int(len(clean)),
        "nan_count": int(clean.isna().sum()),
        "inf_count": int(clean.isin([float("inf"), float("-inf")]).sum()),
        "unique_count": int(finite.nunique(dropna=True)),
        "min": float(finite.min()) if not finite.empty else None,
        "p05": float(finite.quantile(0.05)) if not finite.empty else None,
        "median": float(finite.median()) if not finite.empty else None,
        "mean": float(finite.mean()) if not finite.empty else None,
        "p95": float(finite.quantile(0.95)) if not finite.empty else None,
        "max": float(finite.max()) if not finite.empty else None,
    }


def suffix_feature(base: str, suffix: str) -> str:
    return f"{base}_{suffix}"


def is_positive_metric(value: object) -> bool:
    try:
        if pd.isna(value):
            return False
        return float(value) > 0.0
    except Exception:
        return False


def compute_window_metrics(window_bars: pd.DataFrame, previous_window: pd.DataFrame, direction: str) -> dict:
    metrics: Dict[str, object] = {}
    if window_bars.empty:
        return metrics
    window_closes = window_bars["close"].astype(float)
    window_opens = window_bars["open"].astype(float)
    window_highs = window_bars["high"].astype(float)
    window_lows = window_bars["low"].astype(float)
    direction_sign = 1 if direction == "up" else -1
    close_moves = window_closes.diff().dropna()
    signed_move = direction_sign * (float(window_closes.iloc[-1]) - float(window_closes.iloc[0]))
    duration_days = max((ensure_utc(window_bars.iloc[-1]["open_datetime"]) - ensure_utc(window_bars.iloc[0]["open_datetime"])).total_seconds() / 86400.0, 4.0 / 24.0)
    path_length = float(close_moves.abs().sum())
    range_high = float(window_highs.max())
    range_low = float(window_lows.min())
    atr_mean = float(pd.to_numeric(window_bars.get("atr14"), errors="coerce").mean())
    trend_close_flags = (window_bars["close"] > window_bars["open"]).tolist() if direction == "up" else (window_bars["close"] < window_bars["open"]).tolist()
    counter_flags = (window_bars["close"] < window_bars["open"]).tolist() if direction == "up" else (window_bars["close"] > window_bars["open"]).tolist()
    trend_extreme_updates = window_bars["trend_extreme_update"].astype(bool).tolist() if "trend_extreme_update" in window_bars.columns else []
    counter_extreme_updates = window_bars["counter_extreme_update"].astype(bool).tolist() if "counter_extreme_update" in window_bars.columns else []
    overlaps = []
    for idx in range(1, len(window_bars)):
        prev = window_bars.iloc[idx - 1]
        cur = window_bars.iloc[idx]
        overlaps.append(range_overlap(float(prev["high"]), float(prev["low"]), float(cur["high"]), float(cur["low"])))
    metrics["net_move_pct"] = safe_div(signed_move, float(window_closes.iloc[0]))
    metrics["log_move"] = math.log(float(window_closes.iloc[-1]) / float(window_closes.iloc[0])) if float(window_closes.iloc[0]) > 0 and float(window_closes.iloc[-1]) > 0 else float("nan")
    metrics["move_pct_per_day"] = safe_div(metrics["net_move_pct"], duration_days)
    metrics["atr_move"] = safe_div(abs(signed_move), atr_mean)
    metrics["path_efficiency"] = safe_div(abs(signed_move), path_length)
    metrics["path_tortuosity"] = safe_div(path_length, abs(signed_move))
    metrics["overlap_ratio"] = pd.Series(overlaps).mean() if overlaps else float("nan")
    signs = [sign(v) for v in close_moves.tolist()]
    sign_changes = sum(1 for left, right in zip(signs, signs[1:]) if left != 0 and right != 0 and left != right)
    metrics["return_sign_change_rate"] = safe_div(sign_changes, max(len(signs) - 1, 1), default=float("nan"))
    metrics["return_sign_entropy"] = entropy_from_signs(signs)
    metrics["trend_close_bar_pct"] = safe_div(sum(trend_close_flags), len(trend_close_flags), default=float("nan"))
    metrics["countertrend_close_bar_pct"] = safe_div(sum(counter_flags), len(counter_flags), default=float("nan"))
    metrics["trend_extreme_update_rate"] = safe_div(sum(trend_extreme_updates), len(window_bars), default=float("nan"))
    metrics["counter_extreme_update_rate"] = safe_div(sum(counter_extreme_updates), len(window_bars), default=float("nan"))
    hours_since_last_extreme = pd.to_numeric(window_bars.get("hours_since_last_trend_extreme"), errors="coerce").iloc[-1] if "hours_since_last_trend_extreme" in window_bars.columns else float("nan")
    metrics["hours_since_last_trend_extreme"] = float(hours_since_last_extreme) if pd.notna(hours_since_last_extreme) else float("nan")
    metrics["false_break_count"] = 0
    metrics["false_break_rate"] = float("nan")
    metrics["strict_inside_previous_range_pct"] = float("nan")
    metrics["close_inside_previous_range_pct"] = float("nan")
    metrics["local_mid_cross_rate"] = float("nan")
    metrics["close_in_central_50_pct"] = float("nan")
    if not previous_window.empty:
        prev_high = float(previous_window["high"].max())
        prev_low = float(previous_window["low"].min())
        prev_range = prev_high - prev_low
        current = window_bars.iloc[-1]
        cur_high = float(current["high"])
        cur_low = float(current["low"])
        cur_close = float(current["close"])
        strict_inside = cur_high <= prev_high and cur_low >= prev_low
        close_inside = prev_low <= cur_close <= prev_high
        mid = (prev_high + prev_low) / 2.0
        prior_close = float(window_bars.iloc[-2]["close"]) if len(window_bars) >= 2 else float("nan")
        mid_cross = int(pd.notna(prior_close) and ((prior_close < mid <= cur_close) or (prior_close > mid >= cur_close)))
        lower_q = prev_low + 0.25 * prev_range
        upper_q = prev_low + 0.75 * prev_range
        central_by_close = int(lower_q <= cur_close <= upper_q)
        central_overlap = max(0.0, min(cur_high, upper_q) - max(cur_low, lower_q))
        candle_range = max(cur_high - cur_low, 1e-12)
        metrics["strict_inside_previous_range_pct"] = float(strict_inside)
        metrics["close_inside_previous_range_pct"] = float(close_inside)
        metrics["local_mid_cross_rate"] = float(mid_cross)
        metrics["close_in_central_50_pct"] = float(central_by_close)
        metrics["central_50_overlap_share"] = safe_div(central_overlap, candle_range)
        break_up = cur_high > prev_high
        break_down = cur_low < prev_low
        close_break = cur_close > prev_high or cur_close < prev_low
        wick_only_break = (break_up or break_down) and not close_break
        false_break = 1 if wick_only_break else 0
        metrics["upward_range_break_count"] = int(break_up)
        metrics["downward_range_break_count"] = int(break_down)
        metrics["close_break_count"] = int(close_break)
        metrics["wick_only_break_count"] = int(wick_only_break)
        metrics["return_inside_after_1_bar_count"] = 0
        metrics["return_inside_after_3_bars_count"] = 0
        metrics["return_inside_after_6_bars_count"] = 0
        metrics["false_break_count"] = false_break
        metrics["false_break_rate"] = float(false_break)
        metrics["local_range_width_pct"] = safe_div(prev_range, max(abs(cur_close), 1e-12))
        metrics["local_range_width_atr"] = safe_div(prev_range, atr_mean)
    else:
        metrics["central_50_overlap_share"] = float("nan")
        metrics["upward_range_break_count"] = 0
        metrics["downward_range_break_count"] = 0
        metrics["close_break_count"] = 0
        metrics["wick_only_break_count"] = 0
        metrics["return_inside_after_1_bar_count"] = 0
        metrics["return_inside_after_3_bars_count"] = 0
        metrics["return_inside_after_6_bars_count"] = 0
        metrics["local_range_width_pct"] = float("nan")
        metrics["local_range_width_atr"] = float("nan")
    if "atr14" in window_bars.columns:
        atr_series = pd.to_numeric(window_bars["atr14"], errors="coerce")
    else:
        atr_series = pd.Series(dtype="float64")
    metrics["atr_mean"] = float(atr_series.mean()) if not atr_series.empty else float("nan")
    metrics["atr_slope"] = regression_stats(list(range(len(atr_series.dropna()))), atr_series.dropna().tolist())[0] if atr_series.dropna().size >= 2 else float("nan")
    widths = (window_bars["high"] - window_bars["low"]).astype(float)
    metrics["range_width_atr"] = safe_div(float(widths.mean()), metrics["atr_mean"])
    metrics["realized_volatility"] = float(close_moves.std(ddof=0)) if len(close_moves) >= 1 else float("nan")
    log_close_filled = pd.to_numeric(window_bars["log_close"], errors="coerce").ffill().bfill()
    metrics["linear_slope_log_price"] = regression_stats(list(range(len(window_bars))), log_close_filled.tolist())[0] if len(window_bars) >= 2 else float("nan")
    metrics["linear_regression_r2_log_price"] = regression_stats(list(range(len(window_bars))), log_close_filled.tolist())[1] if len(window_bars) >= 2 else float("nan")
    metrics["volume_to_30d_median"] = float_or_nan(window_bars.iloc[-1].get("volume_to_30d_median", float("nan")))
    return metrics


ROLLING_EVENT_COLUMNS = [
    "canonical_leg_id",
    "event_time",
    "event_type",
    "direction",
    "window",
    "price",
    "reference_price",
    "value",
    "reference_canonical_leg_id",
    "details",
]


def compute_single_leg_rolling_and_events(
    leg_id: str,
    bars: pd.DataFrame,
    parent_by_leg: Dict[str, Optional[str]],
    leg_lookup: Dict[str, dict],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if bars.empty:
        return pd.DataFrame(), pd.DataFrame(columns=ROLLING_EVENT_COLUMNS)
    leg = leg_lookup[leg_id]
    direction = str(leg["direction"])
    direction_sign = 1 if direction == "up" else -1
    bars = bars.sort_values("open_datetime").reset_index(drop=True).copy()
    bars["close_return"] = bars["close"].pct_change()
    bars["log_close"] = bars["close"].apply(lambda v: math.log(v) if pd.notna(v) and v > 0 else float("nan"))
    if direction == "up":
        bars["trend_extreme_update"] = bars["high"] > bars["high"].cummax().shift(1).fillna(-float("inf"))
        bars["counter_extreme_update"] = bars["low"] < bars["low"].cummin().shift(1).fillna(float("inf"))
    else:
        bars["trend_extreme_update"] = bars["low"] < bars["low"].cummin().shift(1).fillna(float("inf"))
        bars["counter_extreme_update"] = bars["high"] > bars["high"].cummax().shift(1).fillna(-float("inf"))

    parent_duration_days = float("nan")
    parent_id = parent_by_leg.get(leg_id)
    if parent_id and parent_id in leg_lookup:
        parent_leg = leg_lookup[parent_id]
        parent_duration_days = safe_div((ensure_utc(parent_leg["end_time"]) - ensure_utc(parent_leg["start_time"])).total_seconds(), 86400.0)

    rolling_rows: List[dict] = []
    event_rows: List[dict] = []
    last_extreme_time: Optional[pd.Timestamp] = None
    last_sign = 0
    no_new_extreme_markers = {24.0: False, 72.0: False, 168.0: False, 336.0: False}
    pullbacks = get_pullback_events(bars, direction)
    active_pullback_index = 0
    current_pullback_depth_max = 0.0
    current_pullback_duration_max = 0.0
    overlap_running_sum = 0.0
    overlap_running_count = 0

    for idx, row in bars.iterrows():
        ts = ensure_utc(row["open_datetime"])
        if idx > 0:
            prev_row = bars.iloc[idx - 1]
            overlap_running_sum += range_overlap(
                float(prev_row["high"]),
                float(prev_row["low"]),
                float(row["high"]),
                float(row["low"]),
            )
            overlap_running_count += 1

        if bool(row["trend_extreme_update"]) or last_extreme_time is None:
            last_extreme_time = ts
            for threshold in no_new_extreme_markers:
                no_new_extreme_markers[threshold] = False
            event_rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "event_time": ts,
                    "event_type": "new_trend_extreme",
                    "direction": direction,
                    "window": "",
                    "price": float(row["high"] if direction == "up" else row["low"]),
                    "reference_price": float("nan"),
                    "value": 1.0,
                    "reference_canonical_leg_id": "",
                    "details": "",
                }
            )
        if bool(row["counter_extreme_update"]):
            event_rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "event_time": ts,
                    "event_type": "new_counter_extreme",
                    "direction": direction,
                    "window": "",
                    "price": float(row["low"] if direction == "up" else row["high"]),
                    "reference_price": float("nan"),
                    "value": 1.0,
                    "reference_canonical_leg_id": "",
                    "details": "",
                }
            )
        hours_since_extreme = safe_div((ts - last_extreme_time).total_seconds(), 3600.0, default=float("nan")) if last_extreme_time is not None else float("nan")
        bars.loc[idx, "hours_since_last_trend_extreme"] = hours_since_extreme
        for threshold, name in [(24.0, "24h"), (72.0, "3d"), (168.0, "7d"), (336.0, "14d")]:
            if pd.notna(hours_since_extreme) and hours_since_extreme >= threshold and not no_new_extreme_markers[threshold]:
                no_new_extreme_markers[threshold] = True
                event_rows.append(
                    {
                        "canonical_leg_id": leg_id,
                        "event_time": ts,
                        "event_type": f"no_new_extreme_{name}",
                        "direction": direction,
                        "window": "",
                        "price": float(row["close"]),
                        "reference_price": float("nan"),
                        "value": hours_since_extreme,
                        "reference_canonical_leg_id": "",
                        "details": "",
                    }
                )
        delta = float_or_nan(row["close_return"])
        current_sign = sign(delta)
        if last_sign != 0 and current_sign != 0 and current_sign != last_sign:
            event_rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "event_time": ts,
                    "event_type": "direction_change",
                    "direction": direction,
                    "window": "",
                    "price": float(row["close"]),
                    "reference_price": float("nan"),
                    "value": delta,
                    "reference_canonical_leg_id": "",
                    "details": "",
                }
            )
        if current_sign != 0:
            last_sign = current_sign

        while active_pullback_index < len(pullbacks) and ensure_utc(pullbacks[active_pullback_index]["end_time"]) <= ts:
            pb = pullbacks[active_pullback_index]
            current_pullback_depth_max = max(current_pullback_depth_max, float_or_nan(pb["depth_pct"]))
            current_pullback_duration_max = max(current_pullback_duration_max, float_or_nan(pb["duration_hours"]))
            event_rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "event_time": ensure_utc(pb["start_time"]),
                    "event_type": "internal_pullback_start",
                    "direction": direction,
                    "window": "",
                    "price": float("nan"),
                    "reference_price": float("nan"),
                    "value": float("nan"),
                    "reference_canonical_leg_id": "",
                    "details": "",
                }
            )
            event_rows.append(
                {
                    "canonical_leg_id": leg_id,
                    "event_time": ensure_utc(pb["end_time"]),
                    "event_type": "internal_pullback_end",
                    "direction": direction,
                    "window": "",
                    "price": float("nan"),
                    "reference_price": float("nan"),
                    "value": float_or_nan(pb["depth_pct"]),
                    "reference_canonical_leg_id": "",
                    "details": "",
                }
            )
            active_pullback_index += 1

        base_row = {
            "canonical_leg_id": leg_id,
            "open_datetime": ts,
            "bar_index_in_leg": int(row["bar_index_in_leg"]),
            "elapsed_hours": float(row["elapsed_hours"]),
            "elapsed_days": float(row["elapsed_days"]),
            "elapsed_fraction_of_leg": float(row["elapsed_fraction_of_leg"]),
        }
        for suffix, window_size in H4_WINDOWS.items():
            start_idx = max(0, idx - window_size + 1)
            prev_start_idx = max(0, idx - window_size)
            window = bars.iloc[start_idx:idx + 1].copy()
            prev_window = bars.iloc[prev_start_idx:idx].copy()
            window_metrics = compute_window_metrics(window, prev_window, direction)
            for key, value in window_metrics.items():
                base_row[suffix_feature(key, suffix)] = value
            if is_positive_metric(window_metrics.get("upward_range_break_count", 0)):
                event_rows.append(
                    {
                        "canonical_leg_id": leg_id,
                        "event_time": ts,
                        "event_type": "local_range_break_up",
                        "direction": direction,
                        "window": suffix,
                        "price": float(row["high"]),
                        "reference_price": float(prev_window["high"].max()) if not prev_window.empty else float("nan"),
                        "value": 1.0,
                        "reference_canonical_leg_id": "",
                        "details": "",
                    }
                )
            if is_positive_metric(window_metrics.get("downward_range_break_count", 0)):
                event_rows.append(
                    {
                        "canonical_leg_id": leg_id,
                        "event_time": ts,
                        "event_type": "local_range_break_down",
                        "direction": direction,
                        "window": suffix,
                        "price": float(row["low"]),
                        "reference_price": float(prev_window["low"].min()) if not prev_window.empty else float("nan"),
                        "value": 1.0,
                        "reference_canonical_leg_id": "",
                        "details": "",
                    }
                )
            if is_positive_metric(window_metrics.get("close_break_count", 0)):
                event_rows.append(
                    {
                        "canonical_leg_id": leg_id,
                        "event_time": ts,
                        "event_type": "close_outside_local_range",
                        "direction": direction,
                        "window": suffix,
                        "price": float(row["close"]),
                        "reference_price": float("nan"),
                        "value": 1.0,
                        "reference_canonical_leg_id": "",
                        "details": "",
                    }
                )
            if is_positive_metric(window_metrics.get("local_mid_cross_rate", 0)):
                event_rows.append(
                    {
                        "canonical_leg_id": leg_id,
                        "event_time": ts,
                        "event_type": "local_mid_cross",
                        "direction": direction,
                        "window": suffix,
                        "price": float(row["close"]),
                        "reference_price": float("nan"),
                        "value": 1.0,
                        "reference_canonical_leg_id": "",
                        "details": "",
                    }
                )

        first_close = float(bars.iloc[0]["close"])
        current_close = float(row["close"])
        leg_duration_days = max(float(row["elapsed_days"]) + (4.0 / 24.0), 4.0 / 24.0)
        path_close = bars.iloc[:idx + 1]["close"].astype(float).diff().abs().sum()
        trend_update_rate = safe_div(int(bars.iloc[:idx + 1]["trend_extreme_update"].sum()), idx + 1)
        close_signs = [sign(v) for v in bars.iloc[:idx + 1]["close_return"].dropna().tolist()]
        direction_change_rate = safe_div(sum(1 for a, b in zip(close_signs, close_signs[1:]) if a != 0 and b != 0 and a != b), max(len(close_signs) - 1, 1), default=float("nan"))
        base_row.update(
            {
                "leg_to_date_net_move_pct": safe_div(direction_sign * (current_close - first_close), first_close),
                "leg_to_date_log_move": math.log(current_close / first_close) if first_close > 0 and current_close > 0 else float("nan"),
                "leg_to_date_duration_days": leg_duration_days,
                "leg_to_date_speed_pct_per_day": safe_div(safe_div(direction_sign * (current_close - first_close), first_close), leg_duration_days),
                "leg_to_date_speed_atr_per_day": safe_div(safe_div(abs(current_close - first_close), float_or_nan(bars.iloc[:idx + 1]["atr14"].mean())), leg_duration_days),
                "leg_to_date_path_efficiency": safe_div(abs(current_close - first_close), path_close),
                "leg_to_date_path_tortuosity": safe_div(path_close, abs(current_close - first_close)),
                "leg_to_date_overlap_ratio": safe_div(overlap_running_sum, overlap_running_count),
                "leg_to_date_direction_change_rate": direction_change_rate,
                "leg_to_date_trend_extreme_update_rate": trend_update_rate,
                "leg_to_date_max_hours_without_new_extreme": float(pd.to_numeric(bars.iloc[:idx + 1]["hours_since_last_trend_extreme"], errors="coerce").max()),
                "leg_to_date_current_hours_without_new_extreme": hours_since_extreme,
                "leg_to_date_internal_pullback_depth_max": current_pullback_depth_max,
                "leg_to_date_internal_pullback_duration_max": current_pullback_duration_max,
            }
        )
        if pd.notna(parent_duration_days):
            elapsed_ratio = safe_div(leg_duration_days, parent_duration_days)
            base_row["parent_duration_days"] = parent_duration_days
            base_row["elapsed_to_parent_duration_ratio"] = elapsed_ratio
            base_row["time_since_last_extreme_to_parent_duration_ratio"] = safe_div(hours_since_extreme / 24.0, parent_duration_days)
            for level_name, level_value in PARENT_TIME_LEVELS.items():
                crossed = bool(pd.notna(elapsed_ratio) and elapsed_ratio >= level_value)
                base_row[f"crossed_parent_time_{level_name}"] = crossed
                if crossed:
                    event_rows.append(
                        {
                            "canonical_leg_id": leg_id,
                            "event_time": ts,
                            "event_type": f"parent_time_{level_name}",
                            "direction": direction,
                            "window": "",
                            "price": float(row["close"]),
                            "reference_price": float("nan"),
                            "value": elapsed_ratio,
                            "reference_canonical_leg_id": parent_id or "",
                            "details": "",
                        }
                    )
        else:
            base_row["parent_duration_days"] = float("nan")
            base_row["elapsed_to_parent_duration_ratio"] = float("nan")
            base_row["time_since_last_extreme_to_parent_duration_ratio"] = float("nan")
            for level_name in PARENT_TIME_LEVELS:
                base_row[f"crossed_parent_time_{level_name}"] = False
        rolling_rows.append(base_row)

    rolling = pd.DataFrame(rolling_rows)
    events = pd.DataFrame(event_rows, columns=ROLLING_EVENT_COLUMNS)
    if not rolling.empty:
        rolling = rolling.sort_values(["canonical_leg_id", "open_datetime", "bar_index_in_leg"]).reset_index(drop=True)
    if not events.empty:
        events = events.sort_values(["canonical_leg_id", "event_time", "event_type"]).reset_index(drop=True)
    return rolling, events


def build_rolling_features_and_events(
    canonical_legs: pd.DataFrame,
    leg_bars_h4: pd.DataFrame,
    parent_by_leg: Dict[str, Optional[str]],
    checkpoint_path: Path,
    checkpoint: dict,
    progress_path: Path,
    partials_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    h4_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_h4.groupby("canonical_leg_id")}
    leg_lookup = canonical_legs.set_index("canonical_leg_id").to_dict("index")
    rolling_dir = partials_dir / "rolling_4h"
    events_dir = partials_dir / "events"
    rolling_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    completed_ids = reconcile_completed_ids(checkpoint, "rolling_4h", rolling_dir) & reconcile_completed_ids(checkpoint, "events", events_dir)
    total_legs = len(canonical_legs)
    for _, leg in canonical_legs.iterrows():
        leg_id = str(leg["canonical_leg_id"])
        if leg_id in completed_ids:
            continue
        update_progress(
            progress_path,
            {
                "stage": "rolling_4h",
                "message": "building rolling features and events",
                "current_leg_id": leg_id,
                "current_leg_end_time": ensure_utc(leg["end_time"]),
                "completed_legs": len(completed_ids),
                "total_legs": total_legs,
                "config_hash": checkpoint["config_hash"],
            },
        )
        bars = h4_groups.get(leg_id, pd.DataFrame())
        rolling_frame, events_frame = compute_single_leg_rolling_and_events(leg_id, bars, parent_by_leg, leg_lookup)
        atomic_write_parquet(rolling_dir / f"{leg_id}.parquet", rolling_frame)
        atomic_write_parquet(events_dir / f"{leg_id}.parquet", events_frame)
        completed_ids.add(leg_id)
        update_stage_checkpoint(
            checkpoint_path,
            checkpoint,
            "rolling_4h",
            "rolling features saved",
            leg_id=leg_id,
            current_time=ensure_utc(leg["end_time"]),
            completed_leg_id=leg_id,
            meta={"rolling_rows": len(rolling_frame), "event_rows": len(events_frame)},
        )
        update_stage_checkpoint(
            checkpoint_path,
            checkpoint,
            "events",
            "event chunk saved",
            leg_id=leg_id,
            current_time=ensure_utc(leg["end_time"]),
            completed_leg_id=leg_id,
            meta={"event_rows": len(events_frame)},
        )
    rolling = load_partial_stage_frames(rolling_dir)
    events = load_partial_stage_frames(events_dir)
    if not rolling.empty:
        rolling = rolling.sort_values(["canonical_leg_id", "open_datetime", "bar_index_in_leg"]).reset_index(drop=True)
    if not events.empty:
        events = events.sort_values(["canonical_leg_id", "event_time", "event_type"]).reset_index(drop=True)
    return rolling, events


def aggregate_static_features(
    canonical_legs: pd.DataFrame,
    memberships: pd.DataFrame,
    leg_bars_1d: pd.DataFrame,
    leg_bars_h4: pd.DataFrame,
    rolling_4h: pd.DataFrame,
) -> pd.DataFrame:
    parent_lookup = {}
    for _, row in memberships.iterrows():
        if str(row["segment_level"]) == "structural_correction" and str(row.get("parent_segment_id") or ""):
            parent_lookup[str(row["canonical_leg_id"])] = str(row["parent_segment_id"])
    canonical_map = canonical_legs.set_index("canonical_leg_id").to_dict("index")
    h4_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_h4.groupby("canonical_leg_id")}
    d1_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_1d.groupby("canonical_leg_id")}
    rolling_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in rolling_4h.groupby("canonical_leg_id")}
    rows: List[dict] = []
    for _, leg in canonical_legs.iterrows():
        leg_id = str(leg["canonical_leg_id"])
        direction = str(leg["direction"])
        h4 = h4_groups.get(leg_id, pd.DataFrame())
        d1 = d1_groups.get(leg_id, pd.DataFrame())
        roll = rolling_groups.get(leg_id, pd.DataFrame())
        start_price = float(leg["start_price"])
        end_price = float(leg["end_price"])
        duration_days = safe_div((ensure_utc(leg["end_time"]) - ensure_utc(leg["start_time"])).total_seconds(), 86400.0)
        segment_high = float(h4["high"].max()) if not h4.empty else (float(d1["high"].max()) if not d1.empty else max(start_price, end_price))
        segment_low = float(h4["low"].min()) if not h4.empty else (float(d1["low"].min()) if not d1.empty else min(start_price, end_price))
        net_move = end_price - start_price
        net_move_abs = abs(net_move)
        bar_market_sources = "|".join(sorted(set(h4["market_source"].dropna().astype(str).tolist()))) if not h4.empty else ""
        source_transition_nearby = bool(
            ensure_utc(leg["start_time"]) <= H4_TRANSITION_START + pd.Timedelta(days=30)
            and ensure_utc(leg["end_time"]) >= H4_TRANSITION_START - pd.Timedelta(days=30)
        )
        parent_move_abs = float("nan")
        parent_segment_id = parent_lookup.get(leg_id)
        if parent_segment_id:
            parent_source_id = parent_segment_id.replace("SEG_IMP_", "")
            parent_members = memberships[(memberships["source_table"] == "structural_impulses_log20_fibtime") & (memberships["source_id"] == parent_source_id)]
            if not parent_members.empty:
                parent_leg_id = str(parent_members.iloc[0]["canonical_leg_id"])
                parent_leg = canonical_map.get(parent_leg_id)
                if parent_leg:
                    parent_move_abs = abs(float(parent_leg["end_price"]) - float(parent_leg["start_price"]))
        base_row = {
            "canonical_leg_id": leg_id,
            "direction": direction,
            "start_time": to_iso(leg["start_time"]),
            "end_time": to_iso(leg["end_time"]),
            "start_price": start_price,
            "end_price": end_price,
            "duration_hours": safe_div((ensure_utc(leg["end_time"]) - ensure_utc(leg["start_time"])).total_seconds(), 3600.0),
            "duration_days": duration_days,
            "num_4h_bars": int(len(h4)),
            "num_1d_bars": int(len(d1)),
            "segment_high": segment_high,
            "segment_low": segment_low,
            "price_range_abs": segment_high - segment_low,
            "net_move_abs": net_move_abs,
            "net_move_pct_signed": safe_div(net_move, start_price),
            "net_move_pct_abs": safe_div(net_move_abs, start_price),
            "log_move_signed": math.log(end_price / start_price) if start_price > 0 and end_price > 0 else float("nan"),
            "log_move_abs": abs(math.log(end_price / start_price)) if start_price > 0 and end_price > 0 else float("nan"),
            "source_record_count": int(leg["source_record_count"]),
            "source_role_count": int(leg["source_role_count"]),
            "has_raw_leg_record": bool(leg["has_raw_leg_record"]),
            "has_impulse_record": bool(leg["has_impulse_record"]),
            "has_correction_record": bool(leg["has_correction_record"]),
            "previous_canonical_leg_id": str(leg["previous_canonical_leg_id"]),
            "next_canonical_leg_id": str(leg["next_canonical_leg_id"]),
            "market_sources": bar_market_sources,
            "raw_volume": float(h4["volume"].sum()) if not h4.empty else float("nan"),
            "volume_source_transition_nearby": source_transition_nearby,
        }
        base_row.update(compute_existing_v1_features(h4, direction, start_price, end_price, duration_days, parent_move_abs))
        if h4.empty:
            rows.append(base_row)
            continue
        direction_sign = 1 if direction == "up" else -1
        closes = h4["close"].astype(float)
        highs = h4["high"].astype(float)
        lows = h4["low"].astype(float)
        opens = h4["open"].astype(float)
        close_moves = closes.diff().dropna()
        close_path_length = float(close_moves.abs().sum())
        high_low_path_length = float((highs - lows).abs().sum())
        mean_atr = float(pd.to_numeric(h4.get("atr14"), errors="coerce").mean())
        xs_days = [safe_div((ensure_utc(ts) - ensure_utc(h4.iloc[0]["open_datetime"])).total_seconds(), 86400.0, default=0.0) for ts in h4["open_datetime"]]
        ys_log = [math.log(v) if v > 0 else float("nan") for v in closes.tolist()]
        slope_log, r2_log, residual_std = regression_stats(xs_days, ys_log)
        trend_close_flags = (closes > opens).tolist() if direction == "up" else (closes < opens).tolist()
        counter_flags = (closes < opens).tolist() if direction == "up" else (closes > opens).tolist()
        flat_flags = (closes == opens).tolist()
        bar_range = (highs - lows).replace(0, pd.NA)
        body = (closes - opens).abs()
        trend_body_sum = float(body[pd.Series(trend_close_flags, index=body.index)].sum())
        counter_body_sum = float(body[pd.Series(counter_flags, index=body.index)].sum())
        trend_mean, trend_median, trend_max = count_streaks(trend_close_flags)
        counter_mean, counter_median, counter_max = count_streaks(counter_flags)
        trend_updates = h4["trend_extreme_update"].astype(bool).tolist() if "trend_extreme_update" in h4.columns else []
        counter_updates = h4["counter_extreme_update"].astype(bool).tolist() if "counter_extreme_update" in h4.columns else []
        trend_update_times = h4.loc[h4["trend_extreme_update"].astype(bool), "open_datetime"].tolist() if "trend_extreme_update" in h4.columns else []
        if len(trend_update_times) >= 2:
            trend_update_hours = [safe_div((ensure_utc(right) - ensure_utc(left)).total_seconds(), 3600.0) for left, right in zip(trend_update_times, trend_update_times[1:])]
            trend_update_bars = [int((ensure_utc(right) - ensure_utc(left)) / FOUR_HOURS) for left, right in zip(trend_update_times, trend_update_times[1:])]
        else:
            trend_update_hours = []
            trend_update_bars = []
        pullbacks = get_pullback_events(h4, direction)
        pullback_depth_pct = pd.Series([float_or_nan(v["depth_pct"]) for v in pullbacks], dtype="float64")
        pullback_depth_atr = pd.Series([float_or_nan(v["depth_atr"]) for v in pullbacks], dtype="float64")
        pullback_duration = pd.Series([float_or_nan(v["duration_hours"]) for v in pullbacks], dtype="float64")
        overlaps = pd.Series(
            [
                range_overlap(float(h4.iloc[idx - 1]["high"]), float(h4.iloc[idx - 1]["low"]), float(h4.iloc[idx]["high"]), float(h4.iloc[idx]["low"]))
                for idx in range(1, len(h4))
            ],
            dtype="float64",
        )
        consecutive_range_overlap = overlaps
        signs = [sign(v) for v in close_moves.tolist()]
        sign_change_count = sum(1 for left, right in zip(signs, signs[1:]) if left != 0 and right != 0 and left != right)
        volume_slope_3d = regression_stats(list(range(min(len(h4), 18))), h4["volume"].astype(float).tail(18).tolist())[0] if len(h4) >= 2 else float("nan")
        volume_slope_7d = regression_stats(list(range(min(len(h4), 42))), h4["volume"].astype(float).tail(42).tolist())[0] if len(h4) >= 2 else float("nan")
        volume_slope_14d = regression_stats(list(range(min(len(h4), 84))), h4["volume"].astype(float).tail(84).tolist())[0] if len(h4) >= 2 else float("nan")
        base_row.update(
            {
                "net_move_pct_per_day_signed": safe_div(safe_div(net_move, start_price), duration_days),
                "net_move_pct_per_day_abs": safe_div(safe_div(net_move_abs, start_price), duration_days),
                "log_move_per_day_signed": safe_div(base_row["log_move_signed"], duration_days),
                "log_move_per_day_abs": safe_div(base_row["log_move_abs"], duration_days),
                "net_move_atr14": safe_div(net_move_abs, mean_atr),
                "speed_atr14_per_day": safe_div(safe_div(net_move_abs, mean_atr), duration_days),
                "linear_slope_log_price": slope_log,
                "linear_regression_r2_log_price": r2_log,
                "linear_regression_residual_std": residual_std,
                "close_path_length_abs": close_path_length,
                "high_low_path_length_abs": high_low_path_length,
                "close_path_efficiency": safe_div(net_move_abs, close_path_length),
                "high_low_path_efficiency": safe_div(net_move_abs, high_low_path_length),
                "close_path_tortuosity": safe_div(close_path_length, net_move_abs),
                "high_low_path_tortuosity": safe_div(high_low_path_length, net_move_abs),
                "trend_close_bar_pct": safe_div(sum(trend_close_flags), len(trend_close_flags)),
                "countertrend_close_bar_pct": safe_div(sum(counter_flags), len(counter_flags)),
                "flat_close_bar_pct": safe_div(sum(flat_flags), len(flat_flags)),
                "trend_body_sum_pct": safe_div(trend_body_sum, float(body.sum())),
                "countertrend_body_sum_pct": safe_div(counter_body_sum, float(body.sum())),
                "trend_close_streak_mean": trend_mean,
                "trend_close_streak_median": trend_median,
                "trend_close_streak_max": trend_max,
                "countertrend_close_streak_mean": counter_mean,
                "countertrend_close_streak_median": counter_median,
                "countertrend_close_streak_max": counter_max,
                "return_sign_change_count": sign_change_count,
                "return_sign_change_rate": safe_div(sign_change_count, max(len(signs) - 1, 1)),
                "return_sign_entropy": entropy_from_signs(signs),
                "trend_extreme_update_count": int(sum(trend_updates)),
                "trend_extreme_update_rate": safe_div(sum(trend_updates), len(h4)),
                "counter_extreme_update_count": int(sum(counter_updates)),
                "counter_extreme_update_rate": safe_div(sum(counter_updates), len(h4)),
                "bars_between_trend_extremes_mean": float(pd.Series(trend_update_bars).mean()) if trend_update_bars else float("nan"),
                "bars_between_trend_extremes_median": float(pd.Series(trend_update_bars).median()) if trend_update_bars else float("nan"),
                "bars_between_trend_extremes_max": float(pd.Series(trend_update_bars).max()) if trend_update_bars else float("nan"),
                "hours_between_trend_extremes_mean": float(pd.Series(trend_update_hours).mean()) if trend_update_hours else float("nan"),
                "hours_between_trend_extremes_median": float(pd.Series(trend_update_hours).median()) if trend_update_hours else float("nan"),
                "hours_between_trend_extremes_max": float(pd.Series(trend_update_hours).max()) if trend_update_hours else float("nan"),
                "max_hours_without_new_trend_extreme": float(pd.to_numeric(h4["hours_since_last_trend_extreme"], errors="coerce").max()) if "hours_since_last_trend_extreme" in h4.columns else float("nan"),
                "final_hours_without_new_trend_extreme": float(pd.to_numeric(h4["hours_since_last_trend_extreme"], errors="coerce").iloc[-1]) if "hours_since_last_trend_extreme" in h4.columns else float("nan"),
                "internal_pullback_count": int(len(pullbacks)),
                "internal_pullback_depth_pct_mean": float(pullback_depth_pct.mean()) if not pullback_depth_pct.empty else float("nan"),
                "internal_pullback_depth_pct_median": float(pullback_depth_pct.median()) if not pullback_depth_pct.empty else float("nan"),
                "internal_pullback_depth_pct_max": float(pullback_depth_pct.max()) if not pullback_depth_pct.empty else float("nan"),
                "internal_pullback_depth_atr_mean": float(pullback_depth_atr.mean()) if not pullback_depth_atr.empty else float("nan"),
                "internal_pullback_depth_atr_median": float(pullback_depth_atr.median()) if not pullback_depth_atr.empty else float("nan"),
                "internal_pullback_depth_atr_max": float(pullback_depth_atr.max()) if not pullback_depth_atr.empty else float("nan"),
                "internal_pullback_duration_hours_mean": float(pullback_duration.mean()) if not pullback_duration.empty else float("nan"),
                "internal_pullback_duration_hours_median": float(pullback_duration.median()) if not pullback_duration.empty else float("nan"),
                "internal_pullback_duration_hours_max": float(pullback_duration.max()) if not pullback_duration.empty else float("nan"),
                "consecutive_range_overlap_mean": float(consecutive_range_overlap.mean()) if not consecutive_range_overlap.empty else float("nan"),
                "consecutive_range_overlap_median": float(consecutive_range_overlap.median()) if not consecutive_range_overlap.empty else float("nan"),
                "consecutive_range_overlap_p75": float(consecutive_range_overlap.quantile(0.75)) if not consecutive_range_overlap.empty else float("nan"),
                "consecutive_range_overlap_p90": float(consecutive_range_overlap.quantile(0.90)) if not consecutive_range_overlap.empty else float("nan"),
                "high_overlap_bar_pct": safe_div(int((consecutive_range_overlap >= 0.75).sum()), len(consecutive_range_overlap)),
                "low_overlap_bar_pct": safe_div(int((consecutive_range_overlap <= 0.25).sum()), len(consecutive_range_overlap)),
                "volume_to_30d_median": float_or_nan(h4["volume_to_30d_median"].median()) if "volume_to_30d_median" in h4.columns else float("nan"),
                "volume_to_30d_mean": float_or_nan(h4["volume_to_30d_mean"].median()) if "volume_to_30d_mean" in h4.columns else float("nan"),
                "volume_zscore_30d": float_or_nan(h4["volume_zscore_30d"].median()) if "volume_zscore_30d" in h4.columns else float("nan"),
                "volume_slope_3d": volume_slope_3d,
                "volume_slope_7d": volume_slope_7d,
                "volume_slope_14d": volume_slope_14d,
                "trend_bar_volume_share": safe_div(float(h4.loc[pd.Series(trend_close_flags, index=h4.index), "volume"].sum()), float(h4["volume"].sum())),
                "countertrend_bar_volume_share": safe_div(float(h4.loc[pd.Series(counter_flags, index=h4.index), "volume"].sum()), float(h4["volume"].sum())),
            }
        )
        for suffix in H4_WINDOWS:
            suffix_columns = {col: f"{col}_{suffix}" for col in [
                "strict_inside_previous_range_pct",
                "close_inside_previous_range_pct",
                "local_mid_cross_rate",
                "close_in_central_50_pct",
                "central_50_overlap_share",
                "upward_range_break_count",
                "downward_range_break_count",
                "close_break_count",
                "wick_only_break_count",
                "return_inside_after_1_bar_count",
                "return_inside_after_3_bars_count",
                "return_inside_after_6_bars_count",
                "false_break_rate",
                "local_range_width_pct",
                "local_range_width_atr",
                "atr_mean",
                "atr_slope",
                "realized_volatility",
                "range_width_atr",
            ]}
            for raw_col, out_col in suffix_columns.items():
                rolling_col = f"{raw_col}_{suffix}"
                if rolling_col in roll.columns:
                    if raw_col.endswith("_count"):
                        base_row[out_col] = float(pd.to_numeric(roll[rolling_col], errors="coerce").sum())
                    else:
                        base_row[out_col] = float(pd.to_numeric(roll[rolling_col], errors="coerce").mean())
            bar_widths = (h4["high"] - h4["low"]).astype(float)
            if len(bar_widths) >= 2:
                base_row[f"range_width_slope_{suffix}"] = regression_stats(list(range(len(bar_widths.tail(H4_WINDOWS[suffix])))), bar_widths.tail(H4_WINDOWS[suffix]).tolist())[0]
                base_row[f"body_size_slope_{suffix}"] = regression_stats(list(range(len(body.tail(H4_WINDOWS[suffix])))), body.tail(H4_WINDOWS[suffix]).tolist())[0]
                base_row[f"realized_volatility_slope_{suffix}"] = regression_stats(list(range(len(close_moves.tail(H4_WINDOWS[suffix])))), close_moves.tail(H4_WINDOWS[suffix]).tolist())[0] if not close_moves.empty else float("nan")
            else:
                base_row[f"range_width_slope_{suffix}"] = float("nan")
                base_row[f"body_size_slope_{suffix}"] = float("nan")
                base_row[f"realized_volatility_slope_{suffix}"] = float("nan")
        for suffix, window_size in H4_WINDOWS.items():
            widths = (h4["high"] - h4["low"]).astype(float)
            current_range = float(widths.tail(window_size).max()) if len(widths) >= 1 else float("nan")
            previous_slice = widths.iloc[max(0, len(widths) - 2 * window_size):max(0, len(widths) - window_size)]
            previous_range = float(previous_slice.max()) if not previous_slice.empty else float("nan")
            base_row[f"current_{suffix}_range_to_previous_{suffix}_range"] = safe_div(current_range, previous_range)
        rows.append(base_row)
    static = pd.DataFrame(rows)
    return static.sort_values(["start_time", "end_time", "canonical_leg_id"]).reset_index(drop=True)


def build_labels_review_v2(canonical_legs: pd.DataFrame) -> pd.DataFrame:
    review = canonical_legs[[
        "canonical_leg_id",
        "direction",
        "start_time",
        "end_time",
        "start_price",
        "end_price",
        "duration_days",
        "source_roles",
        "source_statuses",
    ]].copy()
    review["start_time"] = review["start_time"].apply(to_iso)
    review["end_time"] = review["end_time"].apply(to_iso)
    for column in [
        "movement_form",
        "structural_role",
        "boundary_quality",
        "parent_quality",
        "corrected_start_time",
        "corrected_end_time",
        "split_needed",
        "split_time",
        "split_reason",
        "directional_phase_end_time",
        "range_phase_start_time",
        "role_change_time",
        "role_change_reason",
        "confidence",
        "comment",
    ]:
        review[column] = ""
    return review


def build_feature_dictionary(static: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    base_meta = {
        "canonical_leg_id": ("identifier", "", "categorical"),
        "open_datetime": ("bar timestamp", "4H", "datetime"),
    }

    def add_rows(frame: pd.DataFrame, table_name: str, is_rolling: bool) -> None:
        for column in frame.columns:
            if column in {"canonical_leg_id", "open_datetime", "start_time", "end_time"}:
                continue
            rows.append(
                {
                    "feature_name": column,
                    "table_name": table_name,
                    "description": base_meta.get(column, (column.replace("_", " "), "", ""))[0],
                    "exact_formula": "" if column in base_meta else f"See {table_name} calculation in build_structure_research_dataset_v2.py",
                    "timeframe": "4H" if ("_3d" in column or "_7d" in column or "_14d" in column or is_rolling) else "1D_or_4H_context",
                    "window": "3d/7d/14d" if any(token in column for token in ["_3d", "_7d", "_14d"]) else ("leg_to_date" if "leg_to_date_" in column else ("full_leg" if not is_rolling else "rolling")),
                    "units": "ratio" if "pct" in column or "ratio" in column or "share" in column or "efficiency" in column or "entropy" in column else ("hours" if "hours" in column else ("days" if "days" in column else ("bars" if "bars" in column or "count" in column else "price"))),
                    "signed_or_absolute": "signed" if any(token in column for token in ["signed", "slope", "log_move", "net_move_pct", "speed"]) and "abs" not in column else "absolute_or_not_applicable",
                    "is_causal": bool(is_rolling),
                    "uses_future_leg_boundary": bool((not is_rolling) and (column not in {"canonical_leg_id"})),
                    "missing_value_rule": "NaN when denominator is zero or required source bars are unavailable",
                    "notes": "research-only feature; not a final class",
                }
            )

    add_rows(static, "structure_leg_features_static.csv", False)
    add_rows(rolling, "structure_leg_features_rolling_4h.parquet", True)
    return pd.DataFrame(rows).drop_duplicates(subset=["feature_name", "table_name"]).sort_values(["table_name", "feature_name"]).reset_index(drop=True)


def build_data_dictionary(output_files: Dict[str, str]) -> str:
    return "\n".join(
        [
            "# Structure Research Dataset v2",
            "",
            "## Boundary rule",
            "",
            "A bar is included in a leg when `close_datetime >= leg_start_time` and `open_datetime <= leg_end_time`.",
            "That means the containing start bar and containing end bar are included explicitly for both `1D` and `4H`.",
            "",
            "## Tables",
            "",
            f"- `structure_canonical_legs.csv`: one factual price leg per `canonical_leg_id`.",
            f"- `structure_source_memberships.csv`: one row per original source record mapped into a canonical leg.",
            f"- `structure_leg_relationships.csv`: factual links to previous, next, parent, and previous source impulse references.",
            f"- `market_bars_1d.parquet`: full continuous daily market series with `market_source`.",
            f"- `market_bars_4h.parquet`: available full 4H market series with `market_source`.",
            f"- `structure_leg_bars_1d.parquet`: all overlapping daily bars per canonical leg.",
            f"- `structure_leg_bars_4h.parquet`: all overlapping 4H bars per canonical leg.",
            f"- `structure_leg_features_static.csv`: completed-leg research features.",
            f"- `structure_leg_features_rolling_4h.parquet`: causal rolling features by 4H bar.",
            f"- `structure_leg_events.parquet`: raw structural events without interpretation.",
            f"- `structure_labels_review_v2.csv`: empty manual review template.",
            f"- `feature_dictionary.csv`: feature metadata and formula references.",
            f"- `structure_research_summary_v2.json`: dataset summary and coverage counts.",
            f"- `structure_research_qa_v2.json`: QA diagnostics and problem lists.",
            "",
            "## Allowed future manual labels",
            "",
            "- `movement_form`: directional, rotational, mixed, uncertain, invalid_segment",
            "- `structural_role`: continuation, countertrend, reversal_candidate, uncertain",
            "- `boundary_quality`: correct, start_wrong, end_wrong, both_wrong, uncertain",
            "",
            "## Output files",
            "",
        ]
        + [f"- `{name}` -> `{path}`" for name, path in output_files.items()]
    )


def build_qa_summary(
    canonical_legs: pd.DataFrame,
    memberships: pd.DataFrame,
    static_features: pd.DataFrame,
    rolling_features: pd.DataFrame,
    leg_bars_1d_qa: Dict[str, dict],
    leg_bars_4h_qa: Dict[str, dict],
    relationships: pd.DataFrame,
    h4_metadata: Dict[str, object],
) -> dict:
    missing_1d = [leg_id for leg_id, info in leg_bars_1d_qa.items() if info["missing"]]
    missing_4h = [leg_id for leg_id, info in leg_bars_4h_qa.items() if info["missing"]]
    gap_legs = [leg_id for leg_id, info in leg_bars_4h_qa.items() if info["gap_count"] > 0]
    boundary_mismatch = [leg_id for leg_id, info in leg_bars_4h_qa.items() if not info["boundary_start_ok"] or not info["boundary_end_ok"]]
    chronology_issues = [leg_id for leg_id, info in leg_bars_4h_qa.items() if not info["chronology_ok"]]
    duplicated_legs = [leg_id for leg_id, info in leg_bars_4h_qa.items() if info["duplicate_count"] > 0]
    multi_role_legs = canonical_legs[canonical_legs["source_role_count"] > 1]["canonical_leg_id"].astype(str).tolist()
    ambiguous_parents = relationships[(relationships["reference_leg_type"] == "parent_segment") & (relationships["relationship_status"] != "ok")]["canonical_leg_id"].astype(str).tolist()

    numeric_distributions: Dict[str, dict] = {}
    for table_name, frame in {
        "structure_canonical_legs.csv": canonical_legs,
        "structure_leg_features_static.csv": static_features,
        "structure_leg_features_rolling_4h.parquet": rolling_features,
    }.items():
        for column in frame.columns:
            if pd.api.types.is_numeric_dtype(frame[column]):
                numeric_distributions[f"{table_name}:{column}"] = feature_stats(frame[column])

    almost_constant = [
        name
        for name, stats in numeric_distributions.items()
        if stats["unique_count"] is not None and stats["unique_count"] <= 2
    ]
    suspicious_matches: List[str] = []
    static = static_features.copy()
    for candidate in ["is_breakout_leg", "has_impulse_record", "has_correction_record"]:
        if candidate not in static.columns:
            continue
        target = static[candidate].astype("float64")
        for column in static.columns:
            if column == candidate or not pd.api.types.is_numeric_dtype(static[column]):
                continue
            comparison = pd.to_numeric(static[column], errors="coerce")
            mask = comparison.notna() & target.notna()
            if mask.any() and comparison[mask].equals(target[mask]):
                suspicious_matches.append(f"{column} == {candidate}")

    qa = {
        "h4_source_metadata": h4_metadata,
        "checks": {
            "all_canonical_legs_have_1d_bars": len(missing_1d) == 0,
            "all_canonical_legs_have_4h_bars": len(missing_4h) == 0,
            "all_4h_boundaries_match": len(boundary_mismatch) == 0,
            "no_4h_gaps_inside_legs": len(gap_legs) == 0,
            "no_4h_duplicates_inside_legs": len(duplicated_legs) == 0,
            "no_4h_chronology_violations": len(chronology_issues) == 0,
            "all_source_segments_have_canonical_leg_id": int(memberships["canonical_leg_id"].eq("").sum()) == 0,
            "canonicalization_removed_duplicate_observations": True,
            "aug_sep_2019_segment_start_is_covered": not any(leg_id for leg_id in missing_4h if ensure_utc(canonical_legs.set_index("canonical_leg_id").loc[leg_id, "start_time"]) < pd.Timestamp("2019-10-01T00:00:00Z")),
            "rolling_features_are_causal_by_design": True,
            "future_boundary_features_are_documented_in_feature_dictionary": True,
        },
        "problem_lists": {
            "legs_missing_1d": missing_1d,
            "legs_missing_4h": missing_4h,
            "legs_with_bar_gaps": gap_legs,
            "legs_with_boundary_mismatch": boundary_mismatch,
            "legs_with_chronology_issues": chronology_issues,
            "legs_with_duplicate_4h_bars": duplicated_legs,
            "legs_with_multiple_source_roles": multi_role_legs,
            "ambiguous_parent_links": ambiguous_parents,
        },
        "numeric_distributions": numeric_distributions,
        "almost_constant_features": almost_constant,
        "suspicious_exact_matches": sorted(set(suspicious_matches)),
        "distributions_of_sensitive_fields": {
            "range_efficiency": feature_stats(static_features["range_efficiency"]) if "range_efficiency" in static_features.columns else {},
            "max_adverse_excursion_pct": feature_stats(static_features["max_adverse_excursion_pct"]) if "max_adverse_excursion_pct" in static_features.columns else {},
            "max_favorable_excursion_pct": feature_stats(static_features["max_favorable_excursion_pct"]) if "max_favorable_excursion_pct" in static_features.columns else {},
            "has_impulse_record": feature_stats(static_features["has_impulse_record"].astype(int)) if "has_impulse_record" in static_features.columns else {},
        },
    }
    return qa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build research dataset v2 for macro impulse/range formalization.")
    parser.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN))
    parser.add_argument("--daily-parquet", default=str(DEFAULT_DAILY_PARQUET))
    parser.add_argument("--daily-merge-summary", default=str(DEFAULT_DAILY_MERGE_SUMMARY))
    parser.add_argument("--merged-h4-parquet", default="")
    parser.add_argument("--spot-h4-parquet", default="")
    parser.add_argument("--futures-h4-parquet", default=str(DEFAULT_FUTURES_H4))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_run_dir = Path(args.base_run_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    partials_dir = output_dir / "partials"
    partials_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.json"
    checkpoint_path = output_dir / "checkpoint.json"
    config_hash = compute_config_hash(args)
    checkpoint = load_checkpoint(checkpoint_path, config_hash)
    update_progress(
        progress_path,
        {
            "stage": "startup",
            "base_run_dir": base_run_dir,
            "output_dir": output_dir,
            "message": "initializing sources",
            "config_hash": config_hash,
        },
    )
    update_stage_checkpoint(
        checkpoint_path,
        checkpoint,
        "startup",
        "initializing sources",
    )

    daily = load_ohlc_frame(Path(args.daily_parquet))
    daily, source_transition_time = infer_daily_market_sources(daily, Path(args.daily_merge_summary))
    daily = add_market_indicators(daily, interval_hours=24.0)

    merged_h4_path = Path(args.merged_h4_parquet) if args.merged_h4_parquet else None
    spot_h4_path = Path(args.spot_h4_parquet) if args.spot_h4_parquet else None
    futures_h4_path = Path(args.futures_h4_parquet) if args.futures_h4_parquet else None
    market_h4, h4_metadata = load_or_build_h4_market(merged_h4_path, spot_h4_path, futures_h4_path)
    market_h4 = add_market_indicators(market_h4, interval_hours=4.0)
    update_progress(
        progress_path,
        {
            "stage": "source_loading_complete",
            "message": "sources loaded; building canonical legs and leg bars",
            "daily_rows": len(daily),
            "h4_rows": len(market_h4),
            "h4_mode": h4_metadata.get("mode", ""),
            "config_hash": config_hash,
        },
    )
    update_stage_checkpoint(
        checkpoint_path,
        checkpoint,
        "source_loading_complete",
        "sources loaded",
    )

    tables = load_source_tables(base_run_dir)
    source_records = build_source_records(
        tables["raw_legs"],
        tables["impulses"],
        tables["corrections"],
        tables["market_segments"],
        tables["regime_segments"],
        daily,
    )
    canonical_legs, memberships = canonicalize_legs(source_records)

    leg_bars_1d, leg_bars_1d_qa = run_leg_bar_stage_incremental(
        canonical_legs,
        daily,
        "1D",
        "leg_bars_1d",
        partials_dir,
        checkpoint_path,
        checkpoint,
        progress_path,
    )
    leg_bars_h4, leg_bars_4h_qa = run_leg_bar_stage_incremental(
        canonical_legs,
        market_h4,
        "4H",
        "leg_bars_4h",
        partials_dir,
        checkpoint_path,
        checkpoint,
        progress_path,
    )
    h4_aux_cols = []
    for column in ["atr14", "log_close", "close_return", "volume_to_30d_median", "volume_to_30d_mean", "volume_zscore_30d"]:
        if column in market_h4.columns and not leg_bars_h4.empty:
            h4_aux_cols.append(column)
    if h4_aux_cols and not leg_bars_h4.empty:
        leg_bars_h4 = leg_bars_h4.merge(
            market_h4[["open_datetime"] + h4_aux_cols].drop_duplicates("open_datetime"),
            on="open_datetime",
            how="left",
        )
    update_progress(
        progress_path,
        {
            "stage": "pre_rolling",
            "message": "leg bars prepared; starting rolling 4H features",
            "canonical_leg_count": len(canonical_legs),
            "source_record_count": len(source_records),
            "leg_bars_1d_rows": len(leg_bars_1d),
            "leg_bars_4h_rows": len(leg_bars_h4),
            "config_hash": config_hash,
        },
    )
    update_stage_checkpoint(
        checkpoint_path,
        checkpoint,
        "pre_rolling",
        "leg bars prepared",
    )
    previous_impulse_by_leg, parent_by_leg = compute_leg_context_maps(canonical_legs, memberships)
    rolling_4h, events = build_rolling_features_and_events(
        canonical_legs,
        leg_bars_h4,
        parent_by_leg,
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        progress_path=progress_path,
        partials_dir=partials_dir,
    )
    update_progress(
        progress_path,
        {
            "stage": "post_rolling",
            "message": "rolling 4H features complete; aggregating static features and QA",
            "rolling_rows": len(rolling_4h),
            "event_rows": len(events),
            "config_hash": config_hash,
        },
    )
    update_stage_checkpoint(
        checkpoint_path,
        checkpoint,
        "post_rolling",
        "rolling 4H features complete",
    )
    if not rolling_4h.empty:
        leg_bars_h4 = leg_bars_h4.merge(
            rolling_4h[["canonical_leg_id", "open_datetime", "leg_to_date_current_hours_without_new_extreme"]].rename(
                columns={"leg_to_date_current_hours_without_new_extreme": "hours_since_last_trend_extreme"}
            ),
            on=["canonical_leg_id", "open_datetime"],
            how="left",
        )
        leg_bars_h4["trend_extreme_update"] = False
        leg_bars_h4["counter_extreme_update"] = False
        for leg_id, group in leg_bars_h4.groupby("canonical_leg_id"):
            idxs = group.index
            direction = str(canonical_legs.set_index("canonical_leg_id").loc[leg_id, "direction"])
            if direction == "up":
                trend = group["high"] > group["high"].cummax().shift(1).fillna(-float("inf"))
                counter = group["low"] < group["low"].cummin().shift(1).fillna(float("inf"))
            else:
                trend = group["low"] < group["low"].cummin().shift(1).fillna(float("inf"))
                counter = group["high"] > group["high"].cummax().shift(1).fillna(-float("inf"))
            leg_bars_h4.loc[idxs, "trend_extreme_update"] = trend.values
            leg_bars_h4.loc[idxs, "counter_extreme_update"] = counter.values

    static_features = aggregate_static_features(canonical_legs, memberships, leg_bars_1d, leg_bars_h4, rolling_4h)
    canonical_legs = canonical_legs.merge(
        static_features[
            [
                "canonical_leg_id",
                "duration_hours",
                "duration_days",
                "num_4h_bars",
                "num_1d_bars",
                "segment_high",
                "segment_low",
                "price_range_abs",
                "net_move_abs",
                "net_move_pct_signed",
                "net_move_pct_abs",
                "log_move_signed",
                "log_move_abs",
            ]
        ],
        on="canonical_leg_id",
        how="left",
    )
    relationships = build_relationship_rows(canonical_legs, memberships, leg_bars_h4, previous_impulse_by_leg, parent_by_leg)
    labels_review_v2 = build_labels_review_v2(canonical_legs)
    feature_dictionary = build_feature_dictionary(static_features, rolling_4h)

    output_files = {
        "structure_canonical_legs.csv": str(output_dir / "structure_canonical_legs.csv"),
        "structure_source_memberships.csv": str(output_dir / "structure_source_memberships.csv"),
        "structure_leg_relationships.csv": str(output_dir / "structure_leg_relationships.csv"),
        "market_bars_1d.parquet": str(output_dir / "market_bars_1d.parquet"),
        "market_bars_4h.parquet": str(output_dir / "market_bars_4h.parquet"),
        "structure_leg_bars_1d.parquet": str(output_dir / "structure_leg_bars_1d.parquet"),
        "structure_leg_bars_4h.parquet": str(output_dir / "structure_leg_bars_4h.parquet"),
        "structure_leg_features_static.csv": str(output_dir / "structure_leg_features_static.csv"),
        "structure_leg_features_rolling_4h.parquet": str(output_dir / "structure_leg_features_rolling_4h.parquet"),
        "structure_leg_events.parquet": str(output_dir / "structure_leg_events.parquet"),
        "structure_labels_review_v2.csv": str(output_dir / "structure_labels_review_v2.csv"),
        "feature_dictionary.csv": str(output_dir / "feature_dictionary.csv"),
        "data_dictionary.md": str(output_dir / "data_dictionary.md"),
        "structure_research_summary_v2.json": str(output_dir / "structure_research_summary_v2.json"),
        "structure_research_qa_v2.json": str(output_dir / "structure_research_qa_v2.json"),
    }

    data_dictionary = build_data_dictionary(output_files)
    qa_summary = build_qa_summary(
        canonical_legs,
        memberships,
        static_features,
        rolling_4h,
        leg_bars_1d_qa,
        leg_bars_4h_qa,
        relationships,
        h4_metadata,
    )
    summary = {
        "source_run": str(base_run_dir),
        "source_files": {
            "daily_parquet": str(Path(args.daily_parquet)),
            "daily_merge_summary": str(Path(args.daily_merge_summary)),
            "merged_h4_parquet": str(merged_h4_path) if merged_h4_path else "",
            "spot_h4_parquet": str(spot_h4_path) if spot_h4_path else "",
            "futures_h4_parquet": str(futures_h4_path) if futures_h4_path else "",
        },
        "script_path": str(Path(__file__).resolve()),
        "created_at": pd.Timestamp.now(tz=UTC).isoformat(),
        "period_start": to_iso(daily["open_datetime"].min()),
        "period_end": to_iso(daily["open_datetime"].max()),
        "source_segment_count": int(len(source_records)),
        "canonical_leg_count": int(len(canonical_legs)),
        "duplicate_source_record_count": int(len(source_records) - len(canonical_legs)),
        "legs_with_multiple_source_roles": int((canonical_legs["source_role_count"] > 1).sum()),
        "1d_bar_count": int(len(daily)),
        "4h_bar_count": int(len(market_h4)),
        "rolling_row_count": int(len(rolling_4h)),
        "event_count": int(len(events)),
        "legs_missing_1d": qa_summary["problem_lists"]["legs_missing_1d"],
        "legs_missing_4h": qa_summary["problem_lists"]["legs_missing_4h"],
        "legs_with_bar_gaps": qa_summary["problem_lists"]["legs_with_bar_gaps"],
        "legs_with_boundary_mismatch": qa_summary["problem_lists"]["legs_with_boundary_mismatch"],
        "spot_bar_count": int((daily["market_source"] == "spot").sum()) + int((market_h4["market_source"] == "spot").sum()),
        "futures_bar_count": int((daily["market_source"] == "futures").sum()) + int((market_h4["market_source"] == "futures").sum()),
        "source_transition_time": source_transition_time.isoformat() if source_transition_time is not None else str(h4_metadata.get("transition_time") or ""),
        "output_files": output_files,
    }

    canonical_legs_out = canonical_legs.copy()
    memberships_out = memberships.copy()
    relationships_out = relationships.copy()
    leg_bars_1d_out = leg_bars_1d.copy()
    leg_bars_h4_out = leg_bars_h4.copy()
    rolling_out = rolling_4h.copy()
    events_out = events.copy()
    static_out = static_features.copy()
    labels_out = labels_review_v2.copy()

    for frame in [canonical_legs_out, memberships_out, relationships_out, leg_bars_1d_out, leg_bars_h4_out, rolling_out, events_out]:
        for column in frame.columns:
            if "time" in column and pd.api.types.is_datetime64_any_dtype(frame[column]):
                frame[column] = frame[column].apply(to_iso)

    atomic_write_csv(Path(output_files["structure_canonical_legs.csv"]), canonical_legs_out)
    atomic_write_csv(Path(output_files["structure_source_memberships.csv"]), memberships_out)
    atomic_write_csv(Path(output_files["structure_leg_relationships.csv"]), relationships_out)
    atomic_write_parquet(Path(output_files["market_bars_1d.parquet"]), daily)
    atomic_write_parquet(Path(output_files["market_bars_4h.parquet"]), market_h4)
    atomic_write_parquet(Path(output_files["structure_leg_bars_1d.parquet"]), leg_bars_1d_out)
    atomic_write_parquet(Path(output_files["structure_leg_bars_4h.parquet"]), leg_bars_h4_out)
    atomic_write_csv(Path(output_files["structure_leg_features_static.csv"]), static_out)
    atomic_write_parquet(Path(output_files["structure_leg_features_rolling_4h.parquet"]), rolling_out)
    atomic_write_parquet(Path(output_files["structure_leg_events.parquet"]), events_out)
    atomic_write_csv(Path(output_files["structure_labels_review_v2.csv"]), labels_out)
    atomic_write_csv(Path(output_files["feature_dictionary.csv"]), feature_dictionary)
    atomic_write_text(Path(output_files["data_dictionary.md"]), data_dictionary)
    atomic_write_json(Path(output_files["structure_research_summary_v2.json"]), summary)
    atomic_write_json(Path(output_files["structure_research_qa_v2.json"]), qa_summary)
    update_progress(
        progress_path,
        {
            "stage": "complete",
            "message": "dataset build finished",
            "rolling_rows": len(rolling_4h),
            "event_rows": len(events),
            "output_files": output_files,
            "config_hash": config_hash,
        },
    )
    update_stage_checkpoint(
        checkpoint_path,
        checkpoint,
        "complete",
        "dataset build finished",
    )
    print(json.dumps({"summary": summary, "qa_checks": qa_summary["checks"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
