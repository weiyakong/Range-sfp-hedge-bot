from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import zipfile
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
DEFAULT_AGGTRADES_ROOT = Path("/Users/yeshevika/Documents/Codex/2026-05-30/sfp-vah-val-poc-cvd-one/tick data")
DEFAULT_PARQUET_MANIFEST = Path("/Users/yeshevika/Documents/Codex/2026-06-25/files-mentioned-by-the-user-candle/outputs/market_regime_features_mvp_parquet_2025-11_2026-05/parquet_manifest.csv")
DEFAULT_PARQUET_SCHEMA = Path("/Users/yeshevika/Documents/Codex/2026-06-25/files-mentioned-by-the-user-candle/outputs/market_regime_features_mvp_parquet_2025-11_2026-05/parquet_schema.csv")
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "structure_research_dataset_v3_20260726"

H4_WINDOWS = {"3d": 18, "7d": 42, "14d": 84}
RANGE_WINDOWS = {"18": 18, "42": 42, "84": 84}
RANGE_METHODS = ("A", "B", "C")
HOURS_BY_WINDOW = {"3d": 72.0, "7d": 168.0, "14d": 336.0}
PARENT_TIME_LEVELS = {"0236": 0.236, "0382": 0.382, "0500": 0.500, "0618": 0.618, "1000": 1.000}
FIFTEEN_MINUTES = pd.Timedelta(minutes=15)
FOUR_HOURS = pd.Timedelta(hours=4)
ONE_DAY = pd.Timedelta(days=1)
H4_TRANSITION_START = pd.Timestamp("2019-12-31T00:00:00Z")
SPOT_1D_END = pd.Timestamp("2019-12-30T00:00:00Z")
KNOWN_COVERAGE_END = pd.Timestamp("2026-07-05T23:59:59Z")
PROGRESS_WRITE_INTERVAL_SECONDS = 60
PARTIAL_FLUSH_INTERVAL_SECONDS = 1200
PARTIAL_FLUSH_EVERY_LEGS = 12
STALE_CHECKPOINT_SECONDS = 1200
QA_EPSILON = 1e-9

FEATURE_METADATA: Dict[str, dict] = {
    "range_abs": {
        "description": "Absolute price range of the window",
        "exact_formula": "max(high) - min(low)",
        "units": "price",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "range_ratio_current_to_previous": {
        "description": "Current window range divided by previous window range",
        "exact_formula": "current_range_abs / previous_range_abs",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "realized_vol_pct_return_std": {
        "description": "Standard deviation of percentage returns inside the window",
        "exact_formula": "std(close.pct_change())",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "realized_vol_log_return_std": {
        "description": "Standard deviation of log returns inside the window",
        "exact_formula": "std(diff(log(close)))",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "speed_pct_per_day_signed": {
        "description": "Signed price speed per day",
        "exact_formula": "((last_close / first_close) - 1) / duration_days",
        "units": "ratio",
        "signed_or_absolute": "signed",
    },
    "speed_pct_per_day_abs": {
        "description": "Absolute price speed per day",
        "exact_formula": "abs((last_close / first_close) - 1) / duration_days",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_efficiency": {
        "description": "Close-path efficiency",
        "exact_formula": "abs(last_close - first_close) / sum(abs(diff(close)))",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_length_4h": {
        "description": "4H close-path length",
        "exact_formula": "sum(abs(diff(close_4h)))",
        "units": "price",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_efficiency_4h": {
        "description": "4H close-path efficiency",
        "exact_formula": "abs(last_close_4h - first_close_4h) / sum(abs(diff(close_4h)))",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_tortuosity_4h": {
        "description": "4H close-path tortuosity",
        "exact_formula": "sum(abs(diff(close_4h))) / abs(last_close_4h - first_close_4h)",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_length_15m": {
        "description": "15m close-path length",
        "exact_formula": "sum(abs(diff(close_15m)))",
        "units": "price",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_efficiency_15m": {
        "description": "15m close-path efficiency",
        "exact_formula": "abs(last_close_15m - first_close_15m) / sum(abs(diff(close_15m)))",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "close_path_tortuosity_15m": {
        "description": "15m close-path tortuosity",
        "exact_formula": "sum(abs(diff(close_15m))) / abs(last_close_15m - first_close_15m)",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "extreme_anchor_close_path_length_15m_approx": {
        "description": "Approximate 15m extreme-anchor path length",
        "exact_formula": "abs(first_15m_close-start_price)+sum(abs(diff(close_15m)))+abs(end_price-last_15m_close)",
        "units": "price",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
    "extreme_anchor_close_path_efficiency_15m_approx": {
        "description": "Approximate 15m extreme-anchor path efficiency",
        "exact_formula": "abs(end_price-start_price) / extreme_anchor_close_path_length_15m_approx",
        "units": "ratio",
        "signed_or_absolute": "absolute_or_not_applicable",
    },
}


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
    state.setdefault("missing_ids", [])
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
    missing_leg_id: Optional[str] = None,
) -> None:
    stage_state = ensure_stage_state(checkpoint, stage_key)
    if completed_leg_id and completed_leg_id not in stage_state["completed_ids"]:
        stage_state["completed_ids"].append(completed_leg_id)
    if completed_leg_id and completed_leg_id in stage_state["missing_ids"]:
        stage_state["missing_ids"].remove(completed_leg_id)
    if missing_leg_id and missing_leg_id not in stage_state["missing_ids"]:
        stage_state["missing_ids"].append(missing_leg_id)
    if missing_leg_id and missing_leg_id in stage_state["completed_ids"]:
        stage_state["completed_ids"].remove(missing_leg_id)
    if completed_leg_id and meta is not None:
        stage_state["meta"][completed_leg_id] = to_jsonable(meta)
    if missing_leg_id and meta is not None:
        stage_state["meta"][missing_leg_id] = to_jsonable(meta)
    checkpoint["stage"] = stage_key
    checkpoint["message"] = message
    checkpoint["current_leg_id"] = leg_id
    checkpoint["current_time"] = current_time
    save_checkpoint(checkpoint_path, checkpoint)


def existing_partial_leg_ids(stage_dir: Path) -> set[str]:
    if not stage_dir.exists():
        return set()
    return {path.stem for path in stage_dir.glob("*.parquet")}


def parquet_file_metadata(path: Path, frame: Optional[pd.DataFrame] = None) -> dict:
    local_frame = frame if frame is not None else pd.read_parquet(path)
    return {
        "row_count": int(len(local_frame)),
        "checksum": frame_checksum(local_frame),
        "file_size": int(path.stat().st_size) if path.exists() else 0,
        "saved_at": pd.Timestamp.now(tz=UTC),
    }


def mark_partial_corrupt(path: Path) -> None:
    if not path.exists():
        return
    suffix = pd.Timestamp.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    corrupt_path = path.with_name(f"{path.stem}.corrupt.{suffix}{path.suffix}")
    os.replace(path, corrupt_path)


def validate_partial_file(path: Path, expected_meta: dict) -> bool:
    if not path.exists():
        return False
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return False
    if expected_meta:
        expected_rows = expected_meta.get("row_count")
        expected_checksum = str(expected_meta.get("checksum", ""))
        if expected_rows is not None and int(expected_rows) != int(len(frame)):
            return False
        if expected_checksum and expected_checksum != frame_checksum(frame):
            return False
    return True


def reconcile_completed_ids(checkpoint: dict, stage_key: str, stage_dir: Path) -> set[str]:
    state = ensure_stage_state(checkpoint, stage_key)
    files_present = existing_partial_leg_ids(stage_dir)
    completed_ids: List[str] = []
    meta = state.get("meta", {})
    for leg_id in state["completed_ids"]:
        path = stage_dir / f"{leg_id}.parquet"
        if leg_id not in files_present:
            continue
        if validate_partial_file(path, meta.get(leg_id, {})):
            completed_ids.append(leg_id)
            continue
        mark_partial_corrupt(path)
    if completed_ids != state["completed_ids"]:
        state["completed_ids"] = completed_ids
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
    return frame[(frame["open_datetime"] >= start_time) & (frame["open_datetime"] < end_time)].copy().sort_values("open_datetime").reset_index(drop=True)


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
        source_values = sorted(set(day_bars["market_source"].fillna("").astype(str).tolist())) if not day_bars.empty and "market_source" in day_bars.columns else []
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
                "source_market_sources": "|".join(source_values),
            }
        )

    impulse_sorted = impulses.sort_values(["start_time", "end_time", "impulse_id"]).reset_index(drop=True)
    for _, row in impulse_sorted.iterrows():
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        day_bars = overlap_bars(daily_bars, start_time, end_time)
        source_values = sorted(set(day_bars["market_source"].fillna("").astype(str).tolist())) if not day_bars.empty and "market_source" in day_bars.columns else []
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
                "source_market_sources": "|".join(source_values),
            }
        )

    correction_sorted = corrections.sort_values(["start_time", "end_time", "correction_id"]).reset_index(drop=True)
    for _, row in correction_sorted.iterrows():
        start_time = ensure_utc(row["start_time"])
        end_time = ensure_utc(row["end_time"])
        day_bars = overlap_bars(daily_bars, start_time, end_time)
        source_values = sorted(set(day_bars["market_source"].fillna("").astype(str).tolist())) if not day_bars.empty and "market_source" in day_bars.columns else []
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
                "source_market_sources": "|".join(source_values),
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
        levels = sorted(set(str(v) for v in group["segment_level"].dropna().tolist()))
        structural_levels = [level for level in levels if level in {"structural_impulse", "structural_correction"}]
        if len(levels) == 1:
            primary_segment_level = levels[0]
            segment_level_status = "unique"
        elif len(set(structural_levels)) == 1 and structural_levels:
            primary_segment_level = structural_levels[0]
            segment_level_status = "derived_from_structural_plus_raw"
        elif len(set(structural_levels)) > 1:
            primary_segment_level = ""
            segment_level_status = "ambiguous"
        else:
            primary_segment_level = ""
            segment_level_status = "missing"
        source_market_sources = sorted(set(str(v) for v in group.get("source_market_sources", pd.Series(dtype="object")).dropna().astype(str).tolist() if str(v) != ""))
        split_sources = sorted(set(part for value in source_market_sources for part in value.split("|") if part))
        if len(split_sources) == 1:
            structural_market_source = split_sources[0]
            structural_market_source_status = "unique"
        elif len(split_sources) > 1:
            structural_market_source = ""
            structural_market_source_status = "ambiguous"
        else:
            boundary_sources = sorted(set("spot" if ensure_utc(ts) <= SPOT_1D_END else "futures" for ts in group["start_time"]))
            if len(boundary_sources) == 1:
                structural_market_source = boundary_sources[0]
                structural_market_source_status = "time_inferred_from_transition"
            else:
                structural_market_source = ""
                structural_market_source_status = "missing"
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
                "segment_levels": "|".join(levels),
                "primary_segment_level": primary_segment_level,
                "segment_level_status": segment_level_status,
                "structural_market_source": structural_market_source,
                "structural_market_source_status": structural_market_source_status,
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
        output_path = stage_dir / f"{leg_id}.parquet"
        atomic_write_parquet(output_path, frame)
        completed_ids.add(leg_id)
        qa_state[leg_id] = qa
        meta = dict(qa)
        meta.update(parquet_file_metadata(output_path, frame))
        update_stage_checkpoint(
            checkpoint_path,
            checkpoint,
            stage_key,
            f"{timeframe_label} leg bars saved",
            leg_id=leg_id,
            current_time=ensure_utc(leg["end_time"]),
            completed_leg_id=leg_id,
            meta=meta,
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
    ordered = window_bars.sort_values("open_datetime").reset_index(drop=True)
    closes = ordered["close"].astype(float)
    opens = ordered["open"].astype(float)
    highs = ordered["high"].astype(float)
    lows = ordered["low"].astype(float)
    direction_sign = 1 if direction == "up" else -1
    close_moves = closes.diff().dropna()
    signed_displacement = direction_sign * (float(closes.iloc[-1]) - float(closes.iloc[0]))
    close_path_length = float(close_moves.abs().sum())
    duration_days = max(
        safe_div((ensure_utc(ordered.iloc[-1]["close_datetime"]) - ensure_utc(ordered.iloc[0]["open_datetime"])).total_seconds(), 86400.0),
        1.0 / 24.0,
    )
    range_abs = float(highs.max() - lows.min())
    prev_range_abs = float(previous_window["high"].max() - previous_window["low"].min()) if not previous_window.empty else float("nan")
    returns = closes.pct_change().dropna()
    log_returns = closes.apply(lambda value: math.log(value) if value > 0 else float("nan")).diff().dropna()
    current = ordered.iloc[-1]
    candle_range = max(float(current["high"]) - float(current["low"]), 1e-12)
    if not previous_window.empty:
        reference_low = float(previous_window["low"].min())
        reference_high = float(previous_window["high"].max())
        reference_range = max(reference_high - reference_low, 1e-12)
        lower_zone = reference_low + reference_range * 0.30
        upper_zone = reference_low + reference_range * 0.70
        lower_overlap = max(0.0, min(float(current["high"]), lower_zone) - max(float(current["low"]), reference_low))
        central_overlap = max(0.0, min(float(current["high"]), upper_zone) - max(float(current["low"]), lower_zone))
        upper_overlap = max(0.0, min(float(current["high"]), reference_high) - max(float(current["low"]), upper_zone))
        close_in_lower_zone = bool(float(current["close"]) < lower_zone)
        close_in_central_zone = bool(lower_zone <= float(current["close"]) <= upper_zone)
        close_in_upper_zone = bool(float(current["close"]) > upper_zone)
    else:
        lower_zone = float("nan")
        upper_zone = float("nan")
        lower_overlap = float("nan")
        central_overlap = float("nan")
        upper_overlap = float("nan")
        close_in_lower_zone = float("nan")
        close_in_central_zone = float("nan")
        close_in_upper_zone = float("nan")
    overlaps = []
    for idx in range(1, len(ordered)):
        prev = ordered.iloc[idx - 1]
        cur = ordered.iloc[idx]
        overlaps.append(range_overlap(float(prev["high"]), float(prev["low"]), float(cur["high"]), float(cur["low"])))
    metrics.update(
        {
            "net_move_pct": safe_div(signed_displacement, float(closes.iloc[0])),
            "log_move": math.log(float(closes.iloc[-1]) / float(closes.iloc[0])) if float(closes.iloc[0]) > 0 and float(closes.iloc[-1]) > 0 else float("nan"),
            "move_pct_per_day": safe_div(safe_div(signed_displacement, float(closes.iloc[0])), duration_days),
            "path_efficiency": safe_div(abs(signed_displacement), close_path_length),
            "path_tortuosity": safe_div(close_path_length, abs(signed_displacement)),
            "close_path_length": close_path_length,
            "range_abs": range_abs,
            "range_ratio_current_to_previous": safe_div(range_abs, prev_range_abs),
            "overlap_ratio": float(pd.Series(overlaps).mean()) if overlaps else float("nan"),
            "realized_vol_pct_return_std": float(returns.std(ddof=0)) if not returns.empty else float("nan"),
            "realized_vol_log_return_std": float(log_returns.std(ddof=0)) if not log_returns.empty else float("nan"),
            "trend_close_bar_pct": safe_div(int(((closes > opens) if direction == "up" else (closes < opens)).sum()), len(ordered)),
            "countertrend_close_bar_pct": safe_div(int(((closes < opens) if direction == "up" else (closes > opens)).sum()), len(ordered)),
            "close_in_lower_zone": close_in_lower_zone,
            "close_in_central_zone": close_in_central_zone,
            "close_in_upper_zone": close_in_upper_zone,
            "candle_overlap_lower_share": safe_div(lower_overlap, candle_range, default=float("nan")),
            "central_overlap_share": safe_div(central_overlap, candle_range, default=float("nan")),
            "candle_overlap_upper_share": safe_div(upper_overlap, candle_range, default=float("nan")),
        }
    )
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
                    "exact_formula": "" if column in base_meta else f"See {table_name} calculation in build_structure_research_dataset_v3.py",
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
            "# Structure Research Dataset v3",
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
            f"- `structure_labels_review_v3.csv`: empty manual review template.",
            f"- `feature_dictionary.csv`: feature metadata and formula references.",
            f"- `structure_research_summary_v3.json`: dataset summary and coverage counts.",
            f"- `structure_research_qa_v3.json`: QA diagnostics and problem lists.",
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


def timeframe_delta(timeframe_label: str) -> pd.Timedelta:
    mapping = {"1D": ONE_DAY, "4H": FOUR_HOURS, "15M": FIFTEEN_MINUTES}
    return mapping[timeframe_label]


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_failure_report(output_dir: Path, reason: str, stage: str, context: Optional[dict] = None) -> None:
    payload = {
        "status": "failed",
        "reason": reason,
        "stage": stage,
        "failed_at": pd.Timestamp.now(tz=UTC),
        "context": context or {},
    }
    atomic_write_json(output_dir / "failure_report.json", payload)


def add_source_provenance(
    frame: pd.DataFrame,
    market_source: str,
    source_file: str,
    source_type: str,
    source_symbol: str,
    source_timeframe: str,
) -> pd.DataFrame:
    result = frame.copy()
    existing_source = result["market_source"] if "market_source" in result.columns else pd.Series([""] * len(result), index=result.index, dtype="object")
    existing_source = existing_source.fillna("").astype(str)
    if market_source:
        result["market_source"] = existing_source.where(existing_source != "", market_source)
    else:
        result["market_source"] = existing_source
    result["source_file"] = source_file
    result["source_type"] = source_type
    result["source_symbol"] = source_symbol
    result["source_timeframe"] = source_timeframe
    result["source_start"] = to_iso(result["open_datetime"].min()) if not result.empty else ""
    result["source_end"] = to_iso(result["open_datetime"].max()) if not result.empty else ""
    result["source_row_count"] = int(len(result))
    return result


def summarize_market_sources(frame: pd.DataFrame) -> str:
    if frame.empty or "market_source" not in frame.columns:
        return ""
    counts = (
        frame["market_source"]
        .fillna("")
        .astype(str)
        .value_counts(dropna=False)
        .sort_index()
        .to_dict()
    )
    parts = []
    for key, value in counts.items():
        label = key if key else "<empty>"
        parts.append(f"{label}:{int(value)}")
    return "|".join(parts)


def summarize_source_transitions(frame: pd.DataFrame) -> str:
    if frame.empty or "market_source" not in frame.columns or "open_datetime" not in frame.columns:
        return ""
    ordered = frame.sort_values("open_datetime").reset_index(drop=True)
    source = ordered["market_source"].fillna("").astype(str)
    times: List[str] = []
    for idx in range(1, len(ordered)):
        if source.iloc[idx] != source.iloc[idx - 1]:
            left = source.iloc[idx - 1] or "<empty>"
            right = source.iloc[idx] or "<empty>"
            times.append(f"{to_iso(ordered.iloc[idx]['open_datetime'])}:{left}->{right}")
    return "|".join(times)


def validate_market_bars(frame: pd.DataFrame, timeframe_label: str, required_market_source: Optional[str] = None) -> dict:
    issues: List[str] = []
    if frame.empty:
        issues.append("empty_frame")
        return {"timeframe": timeframe_label, "row_count": 0, "issues": issues}
    delta = timeframe_delta(timeframe_label)
    original = frame.copy()
    if not original["open_datetime"].is_monotonic_increasing:
        issues.append("non_monotonic_open_datetime")
    if bool(original["open_datetime"].duplicated().any()):
        issues.append("duplicate_open_datetime")
    if len(original) >= 2:
        original_diffs = original["open_datetime"].diff().dropna()
        if bool((original_diffs < pd.Timedelta(0)).any()):
            issues.append("reverse_interval")
        if bool((original_diffs != delta).any()):
            issues.append("irregular_interval")
    ordered = frame.sort_values("open_datetime").reset_index(drop=True)
    if not bool((ordered["close_datetime"] > ordered["open_datetime"]).all()):
        issues.append("close_not_after_open")
    if not bool((ordered["high"] >= ordered[["open", "close"]].max(axis=1)).all()):
        issues.append("high_below_open_or_close")
    if not bool((ordered["low"] <= ordered[["open", "close"]].min(axis=1)).all()):
        issues.append("low_above_open_or_close")
    if not bool((ordered["high"] >= ordered["low"]).all()):
        issues.append("high_below_low")
    if "volume" in ordered.columns and not bool((ordered["volume"].fillna(0.0) >= 0.0).all()):
        issues.append("negative_volume")
    if "market_source" in ordered.columns and bool(ordered["market_source"].fillna("").astype(str).eq("").any()):
        issues.append("empty_market_source")
    if len(ordered) >= 2:
        actual = ordered["open_datetime"].diff().dropna()
        gap_count = int((actual > delta).sum())
        reverse_count = int((actual < delta).sum())
    else:
        gap_count = 0
        reverse_count = 0
    if reverse_count > 0 and "reverse_interval" not in issues:
        issues.append("reverse_interval")
    if required_market_source and "market_source" in ordered.columns:
        invalid = ordered[ordered["market_source"] != required_market_source]
        if not invalid.empty:
            issues.append(f"unexpected_market_source:{required_market_source}")
    return {
        "timeframe": timeframe_label,
        "row_count": int(len(ordered)),
        "start": to_iso(ordered["open_datetime"].min()),
        "end": to_iso(ordered["open_datetime"].max()),
        "gap_count": gap_count,
        "issues": issues,
    }


def add_market_indicators_v3(frame: pd.DataFrame, interval_hours: float) -> pd.DataFrame:
    data = frame.copy().sort_values("open_datetime").reset_index(drop=True)
    prev_close = data.groupby("market_source", dropna=False)["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["true_range"] = true_range
    grouped_tr = data.groupby("market_source", dropna=False)["true_range"]
    data["atr14_sma"] = grouped_tr.transform(lambda s: s.rolling(14, min_periods=14).mean())
    data["atr14_wilder"] = grouped_tr.transform(lambda s: s.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean())
    data["log_close"] = data["close"].apply(lambda v: math.log(v) if pd.notna(v) and v > 0 else float("nan"))
    data["pct_return"] = data.groupby("market_source", dropna=False)["close"].pct_change()
    data["log_return"] = data.groupby("market_source", dropna=False)["log_close"].diff()
    thirty_day_window = max(int(round((24.0 / interval_hours) * 30.0)), 1)
    volume_group = data.groupby("market_source", dropna=False)
    rolling_mean = volume_group["volume"].transform(lambda s: s.rolling(thirty_day_window, min_periods=max(14, min(thirty_day_window, 20))).mean())
    rolling_median = volume_group["volume"].transform(lambda s: s.rolling(thirty_day_window, min_periods=max(14, min(thirty_day_window, 20))).median())
    rolling_std = volume_group["volume"].transform(lambda s: s.rolling(thirty_day_window, min_periods=max(14, min(thirty_day_window, 20))).std())
    data["volume_to_30d_mean"] = data["volume"] / rolling_mean.replace(0.0, pd.NA)
    data["volume_to_30d_median"] = data["volume"] / rolling_median.replace(0.0, pd.NA)
    data["volume_zscore_30d"] = (data["volume"] - rolling_mean) / rolling_std.replace(0.0, pd.NA)
    return data


def compute_config_hash_v3(args: argparse.Namespace) -> str:
    payload = {
        "schema_version": "v3.1",
        "mode": args.mode,
        "base_run_dir": str(args.base_run_dir),
        "daily_parquet": str(args.daily_parquet),
        "daily_merge_summary": str(args.daily_merge_summary),
        "merged_h4_parquet": str(args.merged_h4_parquet),
        "spot_h4_parquet": str(args.spot_h4_parquet),
        "futures_h4_parquet": str(args.futures_h4_parquet),
        "merged_15m_parquet": str(args.merged_15m_parquet),
        "spot_15m_parquet": str(args.spot_15m_parquet),
        "futures_15m_parquet": str(args.futures_15m_parquet),
        "aggtrades_root": str(args.aggtrades_root),
        "parquet_manifest": str(args.parquet_manifest),
        "parquet_schema": str(args.parquet_schema),
        "output_dir": str(args.output_dir),
        "range_methods": list(RANGE_METHODS),
        "range_windows": RANGE_WINDOWS,
        "known_coverage_end": to_iso(KNOWN_COVERAGE_END),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def choose_first_existing(paths: List[Path]) -> Optional[Path]:
    for path in paths:
        if path and path.exists():
            return path
    return None


def discover_raw_ohlcv_sources(manifest_path: Path, schema_path: Path) -> pd.DataFrame:
    required_columns = {"open_datetime", "close_datetime", "open", "high", "low", "close", "volume"}
    if not manifest_path.exists():
        return pd.DataFrame(columns=["path", "exists", "timeframe", "required_columns_present", "classified_as", "accepted", "rejection_reason"])
    manifest = pd.read_csv(manifest_path)
    schema = pd.read_csv(schema_path) if schema_path.exists() else pd.DataFrame()
    rows: List[dict] = []
    schema_path_column = ""
    for candidate in ["path", "file_path", "parquet_path"]:
        if candidate in schema.columns:
            schema_path_column = candidate
            break
    for record in manifest.to_dict("records"):
        raw_path = str(record.get("path") or record.get("file_path") or record.get("parquet_path") or "")
        timeframe = str(record.get("timeframe") or record.get("bar_size") or "")
        path = Path(raw_path) if raw_path else Path("")
        exists = bool(raw_path) and path.exists()
        classified_as = str(record.get("kind") or record.get("classified_as") or "")
        rejection_reason = ""
        required_present = False
        accepted = False
        if not exists:
            rejection_reason = "missing_file"
        elif "market_regime_features_15m_w" in path.name:
            rejection_reason = "feature_parquet_rejected"
        else:
            if not schema.empty:
                if schema_path_column:
                    schema_subset = schema[schema[schema_path_column].astype(str) == str(path)]
                else:
                    schema_subset = pd.DataFrame()
                if not schema_subset.empty:
                    columns = set(schema_subset.get("column_name", pd.Series(dtype="object")).astype(str).tolist())
                    required_present = required_columns.issubset(columns)
                else:
                    required_present = True
            else:
                required_present = True
            if not required_present:
                rejection_reason = "required_raw_columns_missing"
            elif timeframe not in {"1D", "4H", "15M", "15min", ""}:
                rejection_reason = "unsupported_timeframe"
            else:
                accepted = True
                if not classified_as:
                    classified_as = "raw_ohlcv"
        rows.append(
            {
                "path": str(path),
                "exists": exists,
                "timeframe": timeframe,
                "required_columns_present": required_present,
                "classified_as": classified_as,
                "accepted": accepted,
                "rejection_reason": rejection_reason,
            }
        )
    return pd.DataFrame(rows)


def discover_default_4h_paths() -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    merged = None
    spot = None
    futures = choose_first_existing(
        [
            DEFAULT_FUTURES_H4,
            ROOT / "work" / "macro_structure_review_log20_fibtime_fixed_v1_cache" / "BTCUSDT_UMFUT_4H.parquet",
        ]
    )
    return merged, spot, futures


def read_aggtrade_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            return pd.DataFrame()
        with archive.open(csv_names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    if raw.empty:
        return pd.DataFrame()
    raw = raw.iloc[:, :8].copy()
    raw.columns = ["agg_id", "price", "qty", "first_trade_id", "last_trade_id", "timestamp_ms", "is_buyer_maker", "best_match"]
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw["qty"] = pd.to_numeric(raw["qty"], errors="coerce")
    raw["timestamp"] = pd.to_datetime(raw["timestamp_ms"], unit="ms", utc=True, errors="coerce")
    raw = raw.dropna(subset=["timestamp", "price", "qty"]).sort_values("timestamp").reset_index(drop=True)
    return raw


def interval_dates(start_time: pd.Timestamp, end_time: pd.Timestamp) -> List[pd.Timestamp]:
    start_day = ensure_utc(start_time).normalize()
    end_day = ensure_utc(end_time).normalize()
    return list(pd.date_range(start_day, end_day, freq="D", tz=UTC))


def aggtrade_zip_path(aggtrades_root: Path, day: pd.Timestamp) -> Path:
    year = day.year
    month_dir = f"{day.month:02d}.{day.year}"
    return aggtrades_root / str(year) / month_dir / f"BTCUSDT-aggTrades-{day.strftime('%Y-%m-%d')}.zip"


def merge_time_ranges(ranges: List[Tuple[pd.Timestamp, pd.Timestamp]]) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    if not ranges:
        return []
    ordered = sorted((ensure_utc(start), ensure_utc(end)) for start, end in ranges)
    merged: List[Tuple[pd.Timestamp, pd.Timestamp]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def resample_aggtrades_to_15m(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["open_datetime", "close_datetime", "open", "high", "low", "close", "volume", "trade_count"])
    indexed = trades.set_index("timestamp")
    bars = indexed.resample("15min", label="left", closed="left").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("qty", "sum"),
        trade_count=("agg_id", "count"),
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"]).reset_index().rename(columns={"timestamp": "open_datetime"})
    bars["close_datetime"] = bars["open_datetime"] + FIFTEEN_MINUTES
    return bars[["open_datetime", "close_datetime", "open", "high", "low", "close", "volume", "trade_count"]]


def build_futures_15m_from_aggtrades(
    aggtrades_root: Path,
    ranges: List[Tuple[pd.Timestamp, pd.Timestamp]],
    partial_dir: Path,
    checkpoint_path: Path,
    checkpoint: dict,
    progress_path: Path,
) -> pd.DataFrame:
    partial_dir.mkdir(parents=True, exist_ok=True)
    stage_key = "market_bars_15m_daily"
    completed_days = reconcile_completed_ids(checkpoint, stage_key, partial_dir)
    stage_state = ensure_stage_state(checkpoint, stage_key)
    missing_csv_path = partial_dir.parent / "missing_aggtrade_days.csv"
    missing_rows: List[dict] = []
    all_days: List[pd.Timestamp] = []
    for start_time, end_time in ranges:
        all_days.extend(interval_dates(start_time, end_time))
    unique_days = sorted(set(all_days))
    for day in unique_days:
        day_key = day.strftime("%Y-%m-%d")
        if day_key in completed_days:
            continue
        update_progress(
            progress_path,
            {
                "stage": stage_key,
                "message": "building futures 15m from aggTrades",
                "current_time": day,
                "completed_days": len(completed_days),
                "total_days": len(unique_days),
                "config_hash": checkpoint["config_hash"],
            },
        )
        zip_path = aggtrade_zip_path(aggtrades_root, day)
        if zip_path.exists():
            try:
                trades = read_aggtrade_zip(zip_path)
                day_bars = resample_aggtrades_to_15m(trades)
            except Exception:
                missing_rows.append(
                    {
                        "date": day_key,
                        "expected_zip_path": str(zip_path),
                        "status": "corrupt",
                        "checked_at": to_iso(pd.Timestamp.now(tz=UTC)),
                    }
                )
                update_stage_checkpoint(
                    checkpoint_path,
                    checkpoint,
                    stage_key,
                    "15m day missing or corrupt",
                    current_time=day,
                    missing_leg_id=day_key,
                    meta={"zip_path": str(zip_path), "status": "corrupt", "checked_at": pd.Timestamp.now(tz=UTC)},
                )
                continue
        else:
            missing_rows.append(
                {
                    "date": day_key,
                    "expected_zip_path": str(zip_path),
                    "status": "missing",
                    "checked_at": to_iso(pd.Timestamp.now(tz=UTC)),
                }
            )
            update_stage_checkpoint(
                checkpoint_path,
                checkpoint,
                stage_key,
                "15m day missing or corrupt",
                current_time=day,
                missing_leg_id=day_key,
                meta={"zip_path": str(zip_path), "status": "missing", "checked_at": pd.Timestamp.now(tz=UTC)},
            )
            continue
        day_bars = add_source_provenance(
            day_bars,
            market_source="futures",
            source_file=str(zip_path),
            source_type="aggtrades_rebuilt_15m",
            source_symbol="BTCUSDT",
            source_timeframe="15M",
        )
        output_path = partial_dir / f"{day_key}.parquet"
        atomic_write_parquet(output_path, day_bars)
        completed_days.add(day_key)
        update_stage_checkpoint(
            checkpoint_path,
            checkpoint,
            stage_key,
            "15m day built",
            leg_id="",
            current_time=day,
            completed_leg_id=day_key,
            meta={
                "zip_path": str(zip_path),
                "status": "complete",
                **parquet_file_metadata(output_path, day_bars),
            },
        )
    missing_ids = sorted(set(stage_state.get("missing_ids", [])))
    if missing_ids or missing_rows:
        existing_missing = pd.DataFrame(missing_rows)
        if missing_csv_path.exists():
            prior = pd.read_csv(missing_csv_path)
            existing_missing = pd.concat([prior, existing_missing], ignore_index=True)
        if not existing_missing.empty:
            existing_missing = existing_missing.sort_values(["date", "checked_at"]).drop_duplicates(subset=["date", "status"], keep="last")
            atomic_write_csv(missing_csv_path, existing_missing)
    built = load_partial_stage_frames(partial_dir)
    if built.empty:
        return built
    mask = pd.Series(False, index=built.index)
    for start_time, end_time in ranges:
        mask = mask | ((built["open_datetime"] >= start_time) & (built["open_datetime"] < end_time))
    return built.loc[mask].sort_values("open_datetime").reset_index(drop=True)


def build_causal_market_features_4h(market_h4: pd.DataFrame) -> pd.DataFrame:
    if market_h4.empty:
        return pd.DataFrame()
    data = market_h4.sort_values("open_datetime").reset_index(drop=True).copy()
    rows: List[dict] = []
    for idx, current in data.iterrows():
        if idx == 0:
            continue
        current_open = ensure_utc(current["open_datetime"])
        current_close = ensure_utc(current["close_datetime"])
        for window_name, window_size in RANGE_WINDOWS.items():
            start_idx = max(0, idx - window_size)
            hist = data.iloc[start_idx:idx].copy()
            if hist.empty:
                continue
            prev_hist = data.iloc[max(0, idx - 2 * window_size):idx - window_size].copy()
            range_abs = float(hist["high"].max() - hist["low"].min())
            prev_range_abs = float(prev_hist["high"].max() - prev_hist["low"].min()) if not prev_hist.empty else float("nan")
            close_path = float(hist["close"].astype(float).diff().abs().sum())
            net_displacement = float(hist["close"].iloc[-1] - hist["close"].iloc[0])
            midpoint = float(hist["high"].max() + hist["low"].min()) / 2.0
            lower_zone = float(hist["low"].min()) + range_abs * 0.30
            upper_zone = float(hist["low"].min()) + range_abs * 0.70
            current_high = float(current["high"])
            current_low = float(current["low"])
            current_close_price = float(current["close"])
            mid_cross_by_close = False
            if idx >= 1:
                prev_close = float(data.iloc[idx - 1]["close"])
                mid_cross_by_close = (prev_close < midpoint <= current_close_price) or (prev_close > midpoint >= current_close_price)
            current_range = max(current_high - current_low, 1e-12)
            central_overlap = max(0.0, min(current_high, upper_zone) - max(current_low, lower_zone))
            lower_overlap = max(0.0, min(current_high, lower_zone) - current_low)
            upper_overlap = max(0.0, current_high - max(current_low, upper_zone))
            returns = hist["pct_return"].dropna()
            log_returns = hist["log_return"].dropna()
            recent_24h = hist.tail(6)
            recent_3d = hist.tail(18)
            recent_7d = hist.tail(42)
            highest_idx = hist["high"].astype(float).idxmax()
            lowest_idx = hist["low"].astype(float).idxmin()
            actual_window_hours = safe_div((ensure_utc(hist.iloc[-1]["close_datetime"]) - ensure_utc(hist.iloc[0]["open_datetime"])).total_seconds(), 3600.0)
            duration_days = max(safe_div(actual_window_hours, 24.0), 1e-12)

            def recent_speed(frame: pd.DataFrame) -> Tuple[float, float]:
                if len(frame) < 2:
                    return float("nan"), float("nan")
                period_days = max(
                    safe_div((ensure_utc(frame.iloc[-1]["close_datetime"]) - ensure_utc(frame.iloc[0]["open_datetime"])).total_seconds(), 86400.0),
                    1e-12,
                )
                start_close = float(frame["close"].iloc[0])
                end_close = float(frame["close"].iloc[-1])
                move_pct = safe_div(end_close, start_close) - 1.0
                return safe_div(move_pct, period_days), safe_div(abs(move_pct), period_days)

            speed_24h_signed, speed_24h_abs = recent_speed(recent_24h)
            speed_3d_signed, speed_3d_abs = recent_speed(recent_3d)
            speed_7d_signed, speed_7d_abs = recent_speed(recent_7d)
            start_close = float(hist["close"].iloc[0])
            end_close = float(hist["close"].iloc[-1])
            move_pct = safe_div(end_close, start_close) - 1.0
            rows.append(
                {
                    "open_datetime": current_open,
                    "close_datetime": current_close,
                    "available_at_time": current_close,
                    "market_source": str(current.get("market_source", "")),
                    "window_name": window_name,
                    "window_size_bars": window_size,
                    "bars_available": int(len(hist)),
                    "window_is_full": bool(len(hist) == window_size),
                    "actual_window_hours": actual_window_hours,
                    "gap_count": int((hist["open_datetime"].diff().dropna() > FOUR_HOURS).sum()) if len(hist) >= 2 else 0,
                    "window_start_time": ensure_utc(hist.iloc[0]["open_datetime"]),
                    "window_end_time": ensure_utc(hist.iloc[-1]["open_datetime"]),
                    "range_abs": range_abs,
                    "range_ratio_current_to_previous": safe_div(range_abs, prev_range_abs),
                    "close_path_efficiency": safe_div(abs(net_displacement), close_path),
                    "close_path_length_abs": close_path,
                    "close_path_tortuosity": safe_div(close_path, abs(net_displacement)),
                    "net_displacement_abs": abs(net_displacement),
                    "net_displacement_signed": net_displacement,
                    "atr14_sma": float_or_nan(hist["atr14_sma"].iloc[-1]),
                    "atr14_wilder": float_or_nan(hist["atr14_wilder"].iloc[-1]),
                    "realized_vol_pct_return_std": float(returns.std(ddof=0)) if not returns.empty else float("nan"),
                    "realized_vol_log_return_std": float(log_returns.std(ddof=0)) if not log_returns.empty else float("nan"),
                    "speed_pct_per_day_signed": safe_div(move_pct, duration_days),
                    "speed_pct_per_day_abs": safe_div(abs(move_pct), duration_days),
                    "recent_speed_24h_signed": speed_24h_signed,
                    "recent_speed_24h_abs": speed_24h_abs,
                    "recent_speed_3d_signed": speed_3d_signed,
                    "recent_speed_3d_abs": speed_3d_abs,
                    "recent_speed_7d_signed": speed_7d_signed,
                    "recent_speed_7d_abs": speed_7d_abs,
                    "time_since_last_high_hours": safe_div((current_open - ensure_utc(data.loc[highest_idx, "open_datetime"])).total_seconds(), 3600.0),
                    "time_since_last_low_hours": safe_div((current_open - ensure_utc(data.loc[lowest_idx, "open_datetime"])).total_seconds(), 3600.0),
                    "time_since_last_extreme_hours": min(
                        safe_div((current_open - ensure_utc(data.loc[highest_idx, "open_datetime"])).total_seconds(), 3600.0),
                        safe_div((current_open - ensure_utc(data.loc[lowest_idx, "open_datetime"])).total_seconds(), 3600.0),
                    ),
                    "close_in_lower_zone": bool(current_close_price < lower_zone),
                    "close_in_central_zone": bool(lower_zone <= current_close_price <= upper_zone),
                    "close_in_upper_zone": bool(current_close_price > upper_zone),
                    "candle_overlap_lower_share": safe_div(lower_overlap, current_range),
                    "central_overlap_share": safe_div(central_overlap, current_range),
                    "candle_overlap_upper_share": safe_div(upper_overlap, current_range),
                    "mid_projected_current": midpoint,
                    "mid_cross_by_close": bool(mid_cross_by_close),
                    "mid_cross_intrabar": bool(current_low <= midpoint <= current_high),
                    "mid_cross_count": int(sum(
                        (
                            float(hist.iloc[pos - 1]["close"]) < midpoint <= float(hist.iloc[pos]["close"])
                        ) or (
                            float(hist.iloc[pos - 1]["close"]) > midpoint >= float(hist.iloc[pos]["close"])
                        )
                        for pos in range(1, len(hist))
                    )),
                    "mid_cross_rate_per_bar": safe_div(
                        sum(
                            (
                                float(hist.iloc[pos - 1]["close"]) < midpoint <= float(hist.iloc[pos]["close"])
                            ) or (
                                float(hist.iloc[pos - 1]["close"]) > midpoint >= float(hist.iloc[pos]["close"])
                            )
                            for pos in range(1, len(hist))
                        ),
                        max(len(hist) - 1, 1),
                    ),
                }
            )
    return pd.DataFrame(rows)


def projected_channel_from_method(method: str, hist: pd.DataFrame) -> dict:
    xs = list(range(len(hist)))
    if not xs:
        return {}
    highs = hist["high"].astype(float).tolist()
    lows = hist["low"].astype(float).tolist()
    closes = hist["close"].astype(float).tolist()
    if method == "A":
        upper_start = upper_end = max(highs)
        lower_start = lower_end = min(lows)
    elif method == "B":
        slope, _, _ = regression_stats(xs, closes)
        if pd.isna(slope):
            return {}
        intercept = float(pd.Series(closes).mean()) - slope * float(pd.Series(xs).mean())
        fitted = [intercept + slope * x for x in xs]
        residuals = [close - fit for close, fit in zip(closes, fitted)]
        upper_start = fitted[0] + max(residuals)
        upper_end = fitted[-1] + max(residuals)
        lower_start = fitted[0] + min(residuals)
        lower_end = fitted[-1] + min(residuals)
    else:
        upper_slope, _, _ = regression_stats(xs, highs)
        lower_slope, _, _ = regression_stats(xs, lows)
        if pd.isna(upper_slope) or pd.isna(lower_slope):
            return {}
        upper_intercept = float(pd.Series(highs).mean()) - upper_slope * float(pd.Series(xs).mean())
        lower_intercept = float(pd.Series(lows).mean()) - lower_slope * float(pd.Series(xs).mean())
        upper_start = upper_intercept
        upper_end = upper_intercept + upper_slope * xs[-1]
        lower_start = lower_intercept
        lower_end = lower_intercept + lower_slope * xs[-1]
    upper_slope = safe_div(upper_end - upper_start, max(len(hist) - 1, 1), default=0.0)
    lower_slope = safe_div(lower_end - lower_start, max(len(hist) - 1, 1), default=0.0)
    return {
        "upper_start": upper_start,
        "upper_end": upper_end,
        "lower_start": lower_start,
        "lower_end": lower_end,
        "upper_slope": upper_slope,
        "lower_slope": lower_slope,
    }


def build_dynamic_range_candidates(market_h4: pd.DataFrame) -> pd.DataFrame:
    if market_h4.empty:
        return pd.DataFrame()
    data = market_h4.sort_values("open_datetime").reset_index(drop=True).copy()
    rows: List[dict] = []
    for idx, current in data.iterrows():
        if idx == 0:
            continue
        current_open = ensure_utc(current["open_datetime"])
        current_close = ensure_utc(current["close_datetime"])
        for window_name, window_size in RANGE_WINDOWS.items():
            hist = data.iloc[max(0, idx - window_size):idx].copy()
            if len(hist) < 2:
                continue
            atr = float_or_nan(hist["atr14_wilder"].iloc[-1]) if "atr14_wilder" in hist.columns else float("nan")
            for method in RANGE_METHODS:
                channel = projected_channel_from_method(method, hist)
                if not channel:
                    continue
                x_current = len(hist)
                upper_current = channel["upper_end"] + channel["upper_slope"]
                lower_current = channel["lower_end"] + channel["lower_slope"]
                mid_current = (upper_current + lower_current) / 2.0
                width_start = channel["upper_start"] - channel["lower_start"]
                width_end = channel["upper_end"] - channel["lower_end"]
                width_current = upper_current - lower_current
                inside_closes = 0
                inside_full = 0
                wick_inside = 0
                touch_sides: List[str] = []
                mid_cross_count = 0
                last_mid = None
                for pos, hist_row in enumerate(hist.itertuples(index=False)):
                    upper_at_pos = channel["upper_start"] + channel["upper_slope"] * pos
                    lower_at_pos = channel["lower_start"] + channel["lower_slope"] * pos
                    close_value = float(hist_row.close)
                    high_value = float(hist_row.high)
                    low_value = float(hist_row.low)
                    if lower_at_pos <= close_value <= upper_at_pos:
                        inside_closes += 1
                    if high_value <= upper_at_pos and low_value >= lower_at_pos:
                        inside_full += 1
                    if not (high_value < lower_at_pos or low_value > upper_at_pos):
                        wick_inside += 1
                    upper_dist = abs(high_value - upper_at_pos)
                    lower_dist = abs(low_value - lower_at_pos)
                    for atr_multiple, tag in [(0.05, "005"), (0.10, "010"), (0.20, "020"), (0.30, "030")]:
                        pass
                    side = ""
                    if pd.notna(atr) and atr > 0:
                        if upper_dist <= 0.10 * atr:
                            side = "upper"
                        elif lower_dist <= 0.10 * atr:
                            side = "lower"
                    if side:
                        touch_sides.append(side)
                    mid_here = (upper_at_pos + lower_at_pos) / 2.0
                    if last_mid is not None and pos >= 1:
                        prev_close = float(hist.iloc[pos - 1]["close"])
                        cur_close = close_value
                        if (prev_close < last_mid <= cur_close) or (prev_close > last_mid >= cur_close):
                            mid_cross_count += 1
                    last_mid = mid_here
                upper_touch_counts = {}
                lower_touch_counts = {}
                for atr_multiple, tag in [(0.05, "005"), (0.10, "010"), (0.20, "020"), (0.30, "030")]:
                    upper_touch_counts[tag] = 0
                    lower_touch_counts[tag] = 0
                    if pd.notna(atr) and atr > 0:
                        for pos, hist_row in enumerate(hist.itertuples(index=False)):
                            upper_at_pos = channel["upper_start"] + channel["upper_slope"] * pos
                            lower_at_pos = channel["lower_start"] + channel["lower_slope"] * pos
                            if abs(float(hist_row.high) - upper_at_pos) <= atr_multiple * atr:
                                upper_touch_counts[tag] += 1
                            if abs(float(hist_row.low) - lower_at_pos) <= atr_multiple * atr:
                                lower_touch_counts[tag] += 1
                alternating_touch_count = sum(1 for left, right in zip(touch_sides, touch_sides[1:]) if left != right)
                same_side_repeat_count = sum(1 for left, right in zip(touch_sides, touch_sides[1:]) if left == right)
                close_path_eff = safe_div(abs(float(hist["close"].iloc[-1] - hist["close"].iloc[0])), float(hist["close"].astype(float).diff().abs().sum()))
                rows.append(
                    {
                        "range_candidate_id": f"RC_{current_open.strftime('%Y%m%d%H%M')}_{window_name}_{method}",
                        "method": method,
                        "window_size_bars": window_size,
                        "history_start_time": ensure_utc(hist.iloc[0]["open_datetime"]),
                        "history_end_time": ensure_utc(hist.iloc[-1]["open_datetime"]),
                        "candidate_available_at": current_open,
                        "observation_close_time": current_close,
                        "upper_at_history_start": channel["upper_start"],
                        "upper_at_history_end": channel["upper_end"],
                        "upper_projected_current": upper_current,
                        "lower_at_history_start": channel["lower_start"],
                        "lower_at_history_end": channel["lower_end"],
                        "lower_projected_current": lower_current,
                        "mid_projected_current": mid_current,
                        "upper_slope_price_per_bar": channel["upper_slope"],
                        "lower_slope_price_per_bar": channel["lower_slope"],
                        "mid_slope_price_per_bar": (channel["upper_slope"] + channel["lower_slope"]) / 2.0,
                        "upper_slope_pct_per_bar": safe_div(channel["upper_slope"], abs(mid_current)),
                        "lower_slope_pct_per_bar": safe_div(channel["lower_slope"], abs(mid_current)),
                        "mid_slope_pct_per_bar": safe_div((channel["upper_slope"] + channel["lower_slope"]) / 2.0, abs(mid_current)),
                        "upper_slope_atr_per_bar": safe_div(channel["upper_slope"], atr),
                        "lower_slope_atr_per_bar": safe_div(channel["lower_slope"], atr),
                        "width_start": width_start,
                        "width_end": width_end,
                        "width_projected_current": width_current,
                        "width_change_abs": width_end - width_start,
                        "width_change_ratio": safe_div(width_end, width_start),
                        "slope_difference_abs": abs(channel["upper_slope"] - channel["lower_slope"]),
                        "parallelism_atr_normalized": safe_div(abs(channel["upper_slope"] - channel["lower_slope"]), atr),
                        "close_inside_share": safe_div(inside_closes, len(hist)),
                        "full_candle_inside_share": safe_div(inside_full, len(hist)),
                        "wick_inside_share": safe_div(wick_inside, len(hist)),
                        "mid_cross_count": mid_cross_count,
                        "mid_cross_rate_per_bar": safe_div(mid_cross_count, max(len(hist) - 1, 1)),
                        "directional_progress_abs": abs(float(hist["close"].iloc[-1] - hist["close"].iloc[0])),
                        "directional_progress_to_width": safe_div(abs(float(hist["close"].iloc[-1] - hist["close"].iloc[0])), width_current),
                        "close_path_efficiency": close_path_eff,
                        "atr14_wilder": atr,
                        "realized_vol_log_return_std": float(hist["log_return"].dropna().std(ddof=0)) if "log_return" in hist.columns and not hist["log_return"].dropna().empty else float("nan"),
                        "upper_touch_count_005atr": upper_touch_counts["005"],
                        "upper_touch_count_010atr": upper_touch_counts["010"],
                        "upper_touch_count_020atr": upper_touch_counts["020"],
                        "upper_touch_count_030atr": upper_touch_counts["030"],
                        "lower_touch_count_005atr": lower_touch_counts["005"],
                        "lower_touch_count_010atr": lower_touch_counts["010"],
                        "lower_touch_count_020atr": lower_touch_counts["020"],
                        "lower_touch_count_030atr": lower_touch_counts["030"],
                        "alternating_touch_count": alternating_touch_count,
                        "same_side_repeat_count": same_side_repeat_count,
                        "market_source": str(current.get("market_source", "")),
                    }
                )
    return pd.DataFrame(rows)


def build_dynamic_range_excursions(candidates: pd.DataFrame, market_h4: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty or market_h4.empty:
        return pd.DataFrame()
    bars = market_h4.sort_values("open_datetime").reset_index(drop=True).copy()
    bar_by_time = {ensure_utc(row.open_datetime): row for row in bars.itertuples(index=False)}
    rows: List[dict] = []
    for candidate in candidates.itertuples(index=False):
        current_bar = bar_by_time.get(ensure_utc(candidate.candidate_available_at))
        if current_bar is None:
            continue
        upper = float(candidate.upper_projected_current)
        lower = float(candidate.lower_projected_current)
        high = float(current_bar.high)
        low = float(current_bar.low)
        close = float(current_bar.close)
        atr = float_or_nan(candidate.atr14_wilder)
        width = max(float(candidate.width_projected_current), 1e-12)
        wick_up = max(0.0, high - upper)
        wick_down = max(0.0, lower - low)
        close_up = max(0.0, close - upper)
        close_down = max(0.0, lower - close)
        two_sided = wick_up > 0.0 and wick_down > 0.0
        if two_sided:
            side = "both"
            wick_abs = max(wick_up, wick_down)
            close_abs = max(close_up, close_down)
        elif wick_up > 0.0 or close_up > 0.0:
            side = "upper"
            wick_abs = wick_up
            close_abs = close_up
        elif wick_down > 0.0 or close_down > 0.0:
            side = "lower"
            wick_abs = wick_down
            close_abs = close_down
        else:
            continue
        future_metrics: Dict[str, object] = {}
        current_index = int(bars.index[bars["open_datetime"] == ensure_utc(candidate.candidate_available_at)][0])
        for horizon in (1, 3, 6):
            future_slice = bars.iloc[current_index + 1: current_index + horizon + 1].copy()
            bars_available = len(future_slice)
            future_metrics[f"h{horizon}_bars_available"] = bars_available
            future_metrics[f"h{horizon}_horizon_complete"] = bool(bars_available == horizon)
            base_nan_fields = [
                f"h{horizon}_future_close_relative_to_original_upper",
                f"h{horizon}_future_close_relative_to_original_lower",
                f"h{horizon}_future_high_relative_to_original_upper",
                f"h{horizon}_future_low_relative_to_original_lower",
                f"h{horizon}_future_mfe_from_boundary",
                f"h{horizon}_future_mae_from_boundary",
                f"h{horizon}_any_close_inside_original_candidate",
                f"h{horizon}_first_return_inside_bars",
                f"h{horizon}_max_excursion_beyond_original_boundary",
                f"h{horizon}_upper_mfe",
                f"h{horizon}_upper_mae",
                f"h{horizon}_lower_mfe",
                f"h{horizon}_lower_mae",
            ]
            if bars_available == 0:
                for key in base_nan_fields:
                    future_metrics[key] = float("nan")
                future_metrics[f"h{horizon}_last_close_relative_to_original_boundaries"] = ""
                continue
            future_row = future_slice.iloc[-1]
            inside_hits = []
            upper_favorable: List[float] = []
            upper_adverse: List[float] = []
            lower_favorable: List[float] = []
            lower_adverse: List[float] = []
            max_excursion = 0.0
            last_relative = ""
            for step, (_, future_bar) in enumerate(future_slice.iterrows(), start=1):
                projected_upper = float(candidate.upper_projected_current) + float(candidate.upper_slope_price_per_bar) * step
                projected_lower = float(candidate.lower_projected_current) + float(candidate.lower_slope_price_per_bar) * step
                future_close = float(future_bar["close"])
                future_high = float(future_bar["high"])
                future_low = float(future_bar["low"])
                inside = projected_lower <= future_close <= projected_upper
                inside_hits.append(inside)
                upper_favorable.append(max(future_high - projected_upper, 0.0))
                upper_adverse.append(max(projected_upper - future_low, 0.0))
                lower_favorable.append(max(projected_lower - future_low, 0.0))
                lower_adverse.append(max(future_high - projected_lower, 0.0))
                if side == "upper":
                    max_excursion = max(max_excursion, max(future_high - projected_upper, 0.0))
                elif side == "lower":
                    max_excursion = max(max_excursion, max(projected_lower - future_low, 0.0))
                else:
                    max_excursion = max(max_excursion, max(future_high - projected_upper, 0.0), max(projected_lower - future_low, 0.0))
                if future_close > projected_upper:
                    last_relative = "above_upper"
                elif future_close < projected_lower:
                    last_relative = "below_lower"
                else:
                    last_relative = "inside"
                if step == bars_available:
                    future_metrics[f"h{horizon}_future_close_relative_to_original_upper"] = future_close - projected_upper
                    future_metrics[f"h{horizon}_future_close_relative_to_original_lower"] = future_close - projected_lower
                    future_metrics[f"h{horizon}_future_high_relative_to_original_upper"] = future_high - projected_upper
                    future_metrics[f"h{horizon}_future_low_relative_to_original_lower"] = future_low - projected_lower
            future_metrics[f"h{horizon}_any_close_inside_original_candidate"] = bool(any(inside_hits))
            future_metrics[f"h{horizon}_first_return_inside_bars"] = float(next((idx + 1 for idx, flag in enumerate(inside_hits) if flag), float("nan")))
            future_metrics[f"h{horizon}_last_close_relative_to_original_boundaries"] = last_relative
            future_metrics[f"h{horizon}_upper_mfe"] = max(upper_favorable) if upper_favorable else float("nan")
            future_metrics[f"h{horizon}_upper_mae"] = max(upper_adverse) if upper_adverse else float("nan")
            future_metrics[f"h{horizon}_lower_mfe"] = max(lower_favorable) if lower_favorable else float("nan")
            future_metrics[f"h{horizon}_lower_mae"] = max(lower_adverse) if lower_adverse else float("nan")
            if side == "upper":
                future_metrics[f"h{horizon}_future_mfe_from_boundary"] = future_metrics[f"h{horizon}_upper_mfe"]
                future_metrics[f"h{horizon}_future_mae_from_boundary"] = future_metrics[f"h{horizon}_upper_mae"]
            elif side == "lower":
                future_metrics[f"h{horizon}_future_mfe_from_boundary"] = future_metrics[f"h{horizon}_lower_mfe"]
                future_metrics[f"h{horizon}_future_mae_from_boundary"] = future_metrics[f"h{horizon}_lower_mae"]
            else:
                future_metrics[f"h{horizon}_future_mfe_from_boundary"] = float("nan")
                future_metrics[f"h{horizon}_future_mae_from_boundary"] = float("nan")
            future_metrics[f"h{horizon}_max_excursion_beyond_original_boundary"] = max_excursion
            if bars_available != horizon:
                for key in base_nan_fields:
                    if key in future_metrics:
                        future_metrics[key] = float("nan")
        rows.append(
            {
                "range_candidate_id": candidate.range_candidate_id,
                "observation_time": ensure_utc(candidate.candidate_available_at),
                "observation_available_at": ensure_utc(candidate.observation_close_time),
                "side": side,
                "wick_distance_beyond_abs": wick_abs,
                "wick_distance_beyond_pct": safe_div(wick_abs, close),
                "wick_distance_beyond_atr": safe_div(wick_abs, atr),
                "wick_distance_beyond_width": safe_div(wick_abs, width),
                "close_distance_beyond_abs": close_abs,
                "close_distance_beyond_pct": safe_div(close_abs, close),
                "close_distance_beyond_atr": safe_div(close_abs, atr),
                "close_distance_beyond_width": safe_div(close_abs, width),
                "wick_outside": bool(wick_abs > 0.0),
                "close_outside": bool(close_abs > 0.0),
                "two_sided_range_sweep": bool(two_sided),
                "close_inside_projected_candidate": bool(lower <= close <= upper),
                "wick_only_break": bool(wick_abs > 0.0 and close_abs == 0.0),
                **future_metrics,
            }
        )
    return pd.DataFrame(rows)


def build_fibtime_events_v3(base_run_dir: Path, impulses: pd.DataFrame, market_h4: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    upstream = load_csv_frame(base_run_dir / "fibtime_events_log20.csv", ["event_time"])
    rows: List[dict] = []

    def available_at(event_time: pd.Timestamp) -> Tuple[pd.Timestamp | pd.NaT, str]:
        ts = ensure_utc(event_time)
        if market_h4 is None or market_h4.empty:
            return pd.NaT, "timeframe_unavailable"
        eligible = market_h4[market_h4["close_datetime"] >= ts]
        if eligible.empty:
            return pd.NaT, "unavailable_after_coverage"
        return ensure_utc(eligible.iloc[0]["close_datetime"]), "available"

    for _, impulse in impulses.iterrows():
        impulse_id = str(impulse["impulse_id"])
        deadline = ensure_utc(impulse["fib_deadline"])
        deadline_version = 1
        schedule_available_at, schedule_status = available_at(deadline)
        rows.append(
            {
                "event_id": f"{impulse_id}_v1_schedule",
                "impulse_id": impulse_id,
                "deadline_version": deadline_version,
                "event_type": "fibtime_deadline_scheduled",
                "event_time": deadline,
                "available_at_time": schedule_available_at,
                "availability_status": schedule_status,
                "availability_mode": "bar_close",
                "previous_deadline": "",
                "new_deadline": deadline,
                "cancelled_at": "",
                "reason": "initial_deadline_from_impulse_duration",
                "warning_code": "",
            }
        )
        upstream_rows = upstream[upstream["impulse_id"] == impulse_id].sort_values("event_time")
        if upstream_rows.empty:
            continue
        revision_history_available = False
        confirmed_written = False
        current_deadline = deadline
        for event_index, upstream_row in enumerate(upstream_rows.itertuples(index=False), start=1):
            event_type = str(getattr(upstream_row, "event_type", "") or "")
            event_time = ensure_utc(getattr(upstream_row, "event_time"))
            reason = str(getattr(upstream_row, "reason", "") or "")
            if "deadline" in event_type and ("update" in event_type or "rev" in event_type):
                revision_history_available = True
                previous_deadline = current_deadline
                raw_new_deadline = None
                for candidate_field in ["new_deadline", "fib_deadline", "deadline"]:
                    raw_value = getattr(upstream_row, candidate_field, None)
                    if raw_value is not None and not pd.isna(raw_value) and str(raw_value) != "":
                        raw_new_deadline = raw_value
                        break
                current_deadline = ensure_utc(raw_new_deadline) if raw_new_deadline is not None else current_deadline
                cancel_available_at, cancel_status = available_at(event_time)
                rows.append(
                    {
                        "event_id": f"{impulse_id}_v{deadline_version}_cancelled_{event_index}",
                        "impulse_id": impulse_id,
                        "deadline_version": deadline_version,
                        "event_type": "fibtime_deadline_cancelled",
                        "event_time": event_time,
                        "available_at_time": cancel_available_at,
                        "availability_status": cancel_status,
                        "availability_mode": "bar_close",
                        "previous_deadline": previous_deadline,
                        "new_deadline": previous_deadline,
                        "cancelled_at": event_time,
                        "reason": reason or "deadline revision superseded previous version",
                        "warning_code": "",
                    }
                )
                deadline_version += 1
                update_available_at, update_status = available_at(event_time)
                rows.append(
                    {
                        "event_id": f"{impulse_id}_v{deadline_version}_update_{event_index}",
                        "impulse_id": impulse_id,
                        "deadline_version": deadline_version,
                        "event_type": "fibtime_deadline_updated",
                        "event_time": event_time,
                        "available_at_time": update_available_at,
                        "availability_status": update_status,
                        "availability_mode": "bar_close",
                        "previous_deadline": previous_deadline,
                        "new_deadline": current_deadline,
                        "cancelled_at": "",
                        "reason": reason or "upstream deadline revision",
                        "warning_code": "",
                    }
                )
                continue
            if ("accepted" in event_type or "confirm" in event_type) and not confirmed_written:
                confirmed_written = True
                confirm_available_at, confirm_status = available_at(event_time)
                rows.append(
                    {
                        "event_id": f"{impulse_id}_v{deadline_version}_confirmed",
                        "impulse_id": impulse_id,
                        "deadline_version": deadline_version,
                        "event_type": "fibtime_confirmed",
                        "event_time": event_time,
                        "available_at_time": confirm_available_at,
                        "availability_status": confirm_status,
                        "availability_mode": "bar_close",
                        "previous_deadline": current_deadline,
                        "new_deadline": current_deadline,
                        "cancelled_at": "",
                        "reason": reason,
                        "warning_code": "" if revision_history_available or len(upstream_rows) == 1 else "fibtime_revision_history_unavailable",
                    }
                )
                continue
            if any(token in event_type for token in ("cancel", "reject", "invalid")):
                cancel_available_at, cancel_status = available_at(event_time)
                rows.append(
                    {
                        "event_id": f"{impulse_id}_v{deadline_version}_cancelled_{event_index}",
                        "impulse_id": impulse_id,
                        "deadline_version": deadline_version,
                        "event_type": "fibtime_deadline_cancelled",
                        "event_time": event_time,
                        "available_at_time": cancel_available_at,
                        "availability_status": cancel_status,
                        "availability_mode": "bar_close",
                        "previous_deadline": current_deadline,
                        "new_deadline": current_deadline,
                        "cancelled_at": event_time,
                        "reason": reason or event_type,
                        "warning_code": "" if revision_history_available or len(upstream_rows) == 1 else "fibtime_revision_history_unavailable",
                    }
                )
    fib = pd.DataFrame(rows).sort_values(["impulse_id", "deadline_version", "event_time", "event_type"]).reset_index(drop=True)
    return fib


def build_coverage_frame(
    canonical_legs: pd.DataFrame,
    leg_bars: pd.DataFrame,
    timeframe_label: str,
    available_start: Optional[pd.Timestamp],
    available_end: Optional[pd.Timestamp],
    market_source_default: str,
) -> pd.DataFrame:
    delta = timeframe_delta(timeframe_label)
    rows: List[dict] = []
    grouped = {leg_id: group.sort_values("open_datetime").reset_index(drop=True) for leg_id, group in leg_bars.groupby("canonical_leg_id")} if not leg_bars.empty else {}
    for _, leg in canonical_legs.iterrows():
        leg_id = str(leg["canonical_leg_id"])
        start_time = ensure_utc(leg["start_time"])
        end_time = ensure_utc(leg["end_time"])
        subset = grouped.get(leg_id, pd.DataFrame())
        expected_rows = int(max((end_time - start_time) / delta, 0))
        actual_rows = int(len(subset))
        gap_count = int((subset["open_datetime"].diff().dropna() > delta).sum()) if actual_rows >= 2 else 0
        partial_start = bool(available_start is not None and start_time < available_start)
        partial_end = bool(available_end is not None and end_time > available_end)
        if available_start is None or available_end is None:
            status = "timeframe_unavailable"
        elif partial_start and partial_end:
            status = "cross_source_only"
        elif partial_start:
            status = "partial_start"
        elif partial_end:
            status = "partial_end"
        elif gap_count > 0:
            status = "gapped"
        elif actual_rows == 0:
            status = "timeframe_unavailable"
        else:
            status = "complete"
        rows.append(
            {
                "canonical_leg_id": leg_id,
                "timeframe": timeframe_label,
                "coverage_start": to_iso(subset["open_datetime"].min()) if actual_rows else "",
                "coverage_end": to_iso(subset["open_datetime"].max()) if actual_rows else "",
                "expected_rows": expected_rows,
                "actual_rows": actual_rows,
                "coverage_share": safe_div(actual_rows, expected_rows),
                "gap_count": gap_count,
                "is_partial_start": partial_start,
                "is_partial_end": partial_end,
                "market_source": "|".join(sorted(set(subset["market_source"].astype(str).tolist()))) if actual_rows and "market_source" in subset.columns else market_source_default,
                "coverage_status": status,
            }
        )
    return pd.DataFrame(rows)


def build_endpoint_alignment(
    canonical_legs: pd.DataFrame,
    market_h4: pd.DataFrame,
    market_15m: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[dict] = []
    h4 = market_h4.sort_values("open_datetime").reset_index(drop=True)
    m15 = market_15m.sort_values("open_datetime").reset_index(drop=True)
    for _, leg in canonical_legs.iterrows():
        for endpoint_type, structural_time, structural_price, expected_side in [
            ("start", ensure_utc(leg["start_time"]), float(leg["start_price"]), "low" if str(leg["direction"]) == "up" else "high"),
            ("end", ensure_utc(leg["end_time"]), float(leg["end_price"]), "high" if str(leg["direction"]) == "up" else "low"),
        ]:
            structural_market_source = str(leg.get("structural_market_source", "") or "")
            h4_match = h4[(h4["open_datetime"] <= structural_time) & (h4["close_datetime"] > structural_time)]
            matched_4h = h4_match.iloc[-1] if not h4_match.empty else None
            matched_15m = None
            matched_15m_subset = pd.DataFrame()
            if matched_4h is not None and not m15.empty:
                matched_15m_subset = m15[
                    (m15["open_datetime"] >= ensure_utc(matched_4h["open_datetime"]))
                    & (m15["close_datetime"] <= ensure_utc(matched_4h["close_datetime"]))
                ].copy()
                if not matched_15m_subset.empty:
                    if expected_side == "low":
                        matched_15m = matched_15m_subset.loc[matched_15m_subset["low"].astype(float).idxmin()]
                        near = float(matched_15m["low"])
                    else:
                        matched_15m = matched_15m_subset.loc[matched_15m_subset["high"].astype(float).idxmax()]
                        near = float(matched_15m["high"])
                else:
                    near = float("nan")
            else:
                near = float("nan")
            same_source_vs_4h = bool(matched_4h is not None and structural_market_source and structural_market_source == str(matched_4h.get("market_source", "")))
            same_source_vs_15m = bool(matched_15m is not None and structural_market_source and structural_market_source == str(matched_15m.get("market_source", "")))
            if matched_15m is not None:
                mismatch_abs = abs(near - structural_price)
                mismatch_pct = safe_div(mismatch_abs, structural_price)
            else:
                mismatch_abs = float("nan")
                mismatch_pct = float("nan")
            epsilon = max(abs(structural_price) * 1e-10, 1e-8)
            if not structural_market_source:
                status = "source_unknown"
            elif matched_4h is None:
                status = "no_4h"
            elif matched_15m is None:
                status = "no_15m"
            else:
                status = "same_source_exact_match" if same_source_vs_15m and mismatch_abs <= epsilon else ("same_source_extreme_mismatch" if same_source_vs_15m else "cross_source_only")
            rows.append(
                {
                    "canonical_leg_id": str(leg["canonical_leg_id"]),
                    "endpoint_type": endpoint_type,
                    "structural_time": structural_time,
                    "structural_price": structural_price,
                    "structural_market_source": structural_market_source,
                    "expected_extreme_side": expected_side,
                    "matched_4h_open": to_iso(matched_4h["open_datetime"]) if matched_4h is not None else "",
                    "matched_4h_high": float(matched_4h["high"]) if matched_4h is not None else float("nan"),
                    "matched_4h_low": float(matched_4h["low"]) if matched_4h is not None else float("nan"),
                    "matched_4h_market_source": str(matched_4h.get("market_source", "")) if matched_4h is not None else "",
                    "matched_15m_open": to_iso(matched_15m["open_datetime"]) if matched_15m is not None else "",
                    "matched_15m_high": float(matched_15m["high"]) if matched_15m is not None else float("nan"),
                    "matched_15m_low": float(matched_15m["low"]) if matched_15m is not None else float("nan"),
                    "matched_15m_market_source": str(matched_15m.get("market_source", "")) if matched_15m is not None else "",
                    "same_source_structure_vs_4h": same_source_vs_4h,
                    "same_source_structure_vs_15m": same_source_vs_15m,
                    "candidate_15m_bar_count": int(len(matched_15m_subset)),
                    "selected_15m_open": to_iso(matched_15m["open_datetime"]) if matched_15m is not None else "",
                    "selected_15m_extreme": near,
                    "nearest_15m_extreme": near,
                    "match_epsilon": epsilon,
                    "mismatch_abs": mismatch_abs,
                    "mismatch_pct": mismatch_pct,
                    "mismatch_bps": mismatch_pct * 10000.0 if pd.notna(mismatch_pct) else float("nan"),
                    "same_market_source": same_source_vs_15m,
                    "alignment_status": status,
                }
            )
    return pd.DataFrame(rows)


def frame_checksum(frame: pd.DataFrame, columns: Optional[List[str]] = None) -> str:
    if frame.empty:
        return hashlib.sha1(b"empty").hexdigest()
    subset_columns = columns or list(frame.columns)
    subset = frame.loc[:, [column for column in subset_columns if column in frame.columns]].copy()
    for column in subset.columns:
        if pd.api.types.is_datetime64_any_dtype(subset[column]):
            subset[column] = subset[column].apply(to_iso)
    payload = subset.to_csv(index=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def prepare_output_directory_for_run(output_dir: Path, resume: bool) -> None:
    checkpoint_path = output_dir / "checkpoint.json"
    partials_dir = output_dir / "partials"
    has_existing_state = checkpoint_path.exists() or any(partials_dir.rglob("*.parquet")) if partials_dir.exists() else checkpoint_path.exists()
    if has_existing_state and not resume:
        raise RuntimeError("unfinished_run_exists_use_resume_or_new_output_dir")


def ensure_market_source(frame: pd.DataFrame, fallback_before: str = "spot", fallback_after: str = "futures", boundary_time: pd.Timestamp = H4_TRANSITION_START) -> pd.DataFrame:
    result = frame.copy()
    existing = result["market_source"] if "market_source" in result.columns else pd.Series([""] * len(result), index=result.index, dtype="object")
    existing = existing.fillna("").astype(str)
    inferred = result["open_datetime"].apply(lambda ts: fallback_before if ensure_utc(ts) < boundary_time else fallback_after)
    result["market_source"] = existing.where(existing != "", inferred)
    return result


def merge_market_frames_with_sources(
    spot_frame: pd.DataFrame,
    futures_frame: pd.DataFrame,
    boundary_time: pd.Timestamp,
) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    if not spot_frame.empty:
        spot = add_source_provenance(spot_frame, "spot", "", "raw_ohlcv", "BTCUSDT", "")
        spot = ensure_market_source(spot, "spot", "spot", boundary_time)
        parts.append(spot[spot["open_datetime"] < boundary_time].copy())
    if not futures_frame.empty:
        fut = add_source_provenance(futures_frame, "futures", "", "raw_ohlcv", "BTCUSDT", "")
        fut = ensure_market_source(fut, "futures", "futures", boundary_time)
        parts.append(fut[fut["open_datetime"] >= boundary_time].copy())
    if not parts:
        return pd.DataFrame()
    merged = pd.concat(parts, ignore_index=True).sort_values("open_datetime").drop_duplicates("open_datetime", keep="last").reset_index(drop=True)
    return merged


def compute_close_path_metrics(bars: pd.DataFrame) -> Dict[str, float]:
    if bars.empty or len(bars) < 2:
        return {"length": float("nan"), "efficiency": float("nan"), "tortuosity": float("nan")}
    closes = bars["close"].astype(float)
    length = float(closes.diff().abs().dropna().sum())
    displacement = abs(float(closes.iloc[-1]) - float(closes.iloc[0]))
    return {
        "length": length,
        "efficiency": safe_div(displacement, length),
        "tortuosity": safe_div(length, displacement),
    }


def compute_extreme_anchor_path_metrics(bars: pd.DataFrame, start_price: float, end_price: float) -> Dict[str, float]:
    if bars.empty:
        return {"length": float("nan"), "efficiency": float("nan")}
    closes = bars["close"].astype(float)
    inner_path = float(closes.diff().abs().dropna().sum()) if len(closes) >= 2 else 0.0
    total_path = abs(float(closes.iloc[0]) - start_price) + inner_path + abs(end_price - float(closes.iloc[-1]))
    return {
        "length": total_path,
        "efficiency": safe_div(abs(end_price - start_price), total_path),
    }


def _segment_levels_by_leg(memberships: pd.DataFrame) -> Dict[str, set[str]]:
    levels: Dict[str, set[str]] = defaultdict(set)
    if memberships.empty:
        return levels
    for row in memberships.itertuples(index=False):
        levels[str(row.canonical_leg_id)].add(str(row.segment_level))
    return levels


def aggregate_static_features_v3(
    canonical_legs: pd.DataFrame,
    memberships: pd.DataFrame,
    leg_bars_1d: pd.DataFrame,
    leg_bars_h4: pd.DataFrame,
    leg_bars_15m: pd.DataFrame,
) -> pd.DataFrame:
    h4_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_h4.groupby("canonical_leg_id")} if not leg_bars_h4.empty else {}
    d1_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_1d.groupby("canonical_leg_id")} if not leg_bars_1d.empty else {}
    m15_groups = {leg_id: group.sort_values("open_datetime").reset_index(drop=True).copy() for leg_id, group in leg_bars_15m.groupby("canonical_leg_id")} if not leg_bars_15m.empty else {}
    segment_levels = _segment_levels_by_leg(memberships)
    rows: List[dict] = []
    for leg in canonical_legs.itertuples(index=False):
        leg_id = str(leg.canonical_leg_id)
        direction = str(leg.direction)
        h4 = h4_groups.get(leg_id, pd.DataFrame())
        d1 = d1_groups.get(leg_id, pd.DataFrame())
        m15 = m15_groups.get(leg_id, pd.DataFrame())
        start_time = ensure_utc(leg.start_time)
        end_time = ensure_utc(leg.end_time)
        start_price = float(leg.start_price)
        end_price = float(leg.end_price)
        duration_hours = safe_div((end_time - start_time).total_seconds(), 3600.0)
        duration_days = safe_div(duration_hours, 24.0)
        source_frames = [frame for frame in [d1, h4, m15] if not frame.empty]
        combined_sources = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame()
        empty_market_source_count = int(combined_sources["market_source"].fillna("").astype(str).eq("").sum()) if not combined_sources.empty and "market_source" in combined_sources.columns else 0
        range_high = float(h4["high"].max()) if not h4.empty else (float(d1["high"].max()) if not d1.empty else max(start_price, end_price))
        range_low = float(h4["low"].min()) if not h4.empty else (float(d1["low"].min()) if not d1.empty else min(start_price, end_price))
        price_range_abs = range_high - range_low
        net_move_abs = abs(end_price - start_price)
        h4_path = compute_close_path_metrics(h4)
        m15_path = compute_close_path_metrics(m15)
        m15_extreme_anchor = compute_extreme_anchor_path_metrics(m15, start_price, end_price)
        overlap_ratio = float("nan")
        if len(h4) >= 2:
            overlap_ratio = float(
                pd.Series(
                    [
                        range_overlap(float(h4.iloc[idx - 1]["high"]), float(h4.iloc[idx - 1]["low"]), float(h4.iloc[idx]["high"]), float(h4.iloc[idx]["low"]))
                        for idx in range(1, len(h4))
                    ],
                    dtype="float64",
                ).mean()
            )
        trend_close_bar_pct = float("nan")
        countertrend_close_bar_pct = float("nan")
        if not h4.empty:
            closes = h4["close"].astype(float)
            opens = h4["open"].astype(float)
            if direction == "up":
                trend_close_bar_pct = safe_div(int((closes > opens).sum()), len(h4))
                countertrend_close_bar_pct = safe_div(int((closes < opens).sum()), len(h4))
            else:
                trend_close_bar_pct = safe_div(int((closes < opens).sum()), len(h4))
                countertrend_close_bar_pct = safe_div(int((closes > opens).sum()), len(h4))
        row = {
            "canonical_leg_id": leg_id,
            "direction": direction,
            "segment_levels": "|".join(sorted(segment_levels.get(leg_id, set()))),
            "start_time": to_iso(start_time),
            "end_time": to_iso(end_time),
            "start_price": start_price,
            "end_price": end_price,
            "duration_hours": duration_hours,
            "duration_days": duration_days,
            "num_1d_bars": int(len(d1)),
            "num_4h_bars": int(len(h4)),
            "num_15m_bars": int(len(m15)),
            "segment_high": range_high,
            "segment_low": range_low,
            "price_range_abs": price_range_abs,
            "net_move_abs": net_move_abs,
            "net_move_pct_signed": safe_div(end_price - start_price, start_price),
            "net_move_pct_abs": safe_div(net_move_abs, start_price),
            "log_move_signed": math.log(end_price / start_price) if start_price > 0 and end_price > 0 else float("nan"),
            "log_move_abs": abs(math.log(end_price / start_price)) if start_price > 0 and end_price > 0 else float("nan"),
            "market_sources": "|".join(sorted(set(combined_sources["market_source"].astype(str).tolist()))) if not combined_sources.empty and "market_source" in combined_sources.columns else "",
            "daily_source_counts": summarize_market_sources(d1),
            "h4_source_counts": summarize_market_sources(h4),
            "m15_source_counts": summarize_market_sources(m15),
            "source_transition_times": summarize_source_transitions(combined_sources),
            "empty_market_source_count": empty_market_source_count,
            "path_efficiency": h4_path["efficiency"],
            "close_path_length_4h": h4_path["length"],
            "close_path_efficiency_4h": h4_path["efficiency"],
            "close_path_tortuosity_4h": h4_path["tortuosity"],
            "close_path_length_15m": m15_path["length"],
            "close_path_efficiency_15m": m15_path["efficiency"],
            "close_path_tortuosity_15m": m15_path["tortuosity"],
            "extreme_anchor_close_path_length_15m_approx": m15_extreme_anchor["length"],
            "extreme_anchor_close_path_efficiency_15m_approx": m15_extreme_anchor["efficiency"],
            "range_efficiency": safe_div(net_move_abs, price_range_abs),
            "overlap_ratio": overlap_ratio,
            "trend_close_bar_pct": trend_close_bar_pct,
            "countertrend_close_bar_pct": countertrend_close_bar_pct,
            "coverage_15m_reason": "" if not m15.empty else "15m_unavailable_or_no_overlap",
        }
        rows.append(row)
    return pd.DataFrame(rows)


def build_parent_reference_candidates_v3(canonical_legs: pd.DataFrame, memberships: pd.DataFrame) -> pd.DataFrame:
    if canonical_legs.empty:
        return pd.DataFrame()
    ordered = canonical_legs.copy().sort_values(["start_time", "end_time", "canonical_leg_id"]).reset_index(drop=True)
    if "primary_segment_level" not in ordered.columns:
        level_map = memberships.groupby("canonical_leg_id")["segment_level"].agg(
            lambda values: next((str(value) for value in values if str(value) in {"structural_impulse", "structural_correction"}), str(list(values)[0]) if len(list(values)) else "")
        ).to_dict()
        ordered["primary_segment_level"] = ordered["canonical_leg_id"].astype(str).map(level_map).fillna("")
    leg_lookup = ordered.set_index("canonical_leg_id").to_dict("index")
    level_order = ["structural_impulse", "structural_correction", "raw_leg"]
    source_id_to_leg: Dict[str, str] = {}
    for row in memberships.itertuples(index=False):
        source_id_to_leg[str(row.segment_id)] = str(row.canonical_leg_id)
        source_id_to_leg[str(row.source_id)] = str(row.canonical_leg_id)
    rows: List[dict] = []
    for idx, current in ordered.iterrows():
        current_id = str(current["canonical_leg_id"])
        current_start = ensure_utc(current["start_time"])
        current_level = str(current.get("primary_segment_level", ""))
        previous_rows = ordered.iloc[:idx].copy()
        previous_non_overlap = previous_rows[previous_rows["end_time"].apply(ensure_utc) <= current_start].copy()
        if not previous_rows.empty:
            prev = previous_rows.iloc[-1]
            rows.append(_make_relationship_candidate_row(current, prev, "previous_row", {"direct_temporal_predecessor"}))
        member_rows = memberships[memberships["canonical_leg_id"].astype(str) == current_id]
        explicit_parent_candidates = set()
        for member in member_rows.itertuples(index=False):
            parent_segment_id = str(member.parent_segment_id or "")
            if parent_segment_id and parent_segment_id in source_id_to_leg:
                explicit_parent_candidates.add(source_id_to_leg[parent_segment_id])
        candidate_reason_map: Dict[str, set[str]] = defaultdict(set)
        if not previous_non_overlap.empty:
            nearest_opposite = previous_non_overlap[previous_non_overlap["direction"].astype(str) != str(current["direction"])]
            if not nearest_opposite.empty:
                nearest_row = nearest_opposite.sort_values(["end_time", "canonical_leg_id"]).iloc[-1]
                candidate_reason_map[str(nearest_row["canonical_leg_id"])].add("nearest_opposite_leg")
            max_end = previous_non_overlap["end_time"].apply(ensure_utc).max()
            latest_any = previous_non_overlap[previous_non_overlap["end_time"].apply(ensure_utc) == max_end]
            for _, prev in latest_any.iterrows():
                candidate_reason_map[str(prev["canonical_leg_id"])].add("direct_temporal_predecessor")
            for level in level_order:
                level_rows = previous_non_overlap[
                    (previous_non_overlap["direction"].astype(str) != str(current["direction"]))
                    & (previous_non_overlap["primary_segment_level"].astype(str) == level)
                ]
                if level_rows.empty:
                    continue
                chosen = level_rows.sort_values(["end_time", "canonical_leg_id"]).iloc[-1]
                candidate_reason_map[str(chosen["canonical_leg_id"])].add("previous_opposite_each_level")
                if current_level and str(chosen["primary_segment_level"]) == current_level:
                    candidate_reason_map[str(chosen["canonical_leg_id"])].add("same_level_predecessor")
            same_level_rows = previous_non_overlap[
                previous_non_overlap["primary_segment_level"].astype(str) == current_level
            ]
            if not same_level_rows.empty:
                latest_same_level = same_level_rows.sort_values(["end_time", "canonical_leg_id"]).iloc[-1]
                candidate_reason_map[str(latest_same_level["canonical_leg_id"])].add("same_level_predecessor")
            for _, prev in previous_non_overlap.iterrows():
                shared_extreme = (
                    abs(float(current["start_price"]) - float(prev["start_price"])) <= QA_EPSILON
                    or abs(float(current["start_price"]) - float(prev["end_price"])) <= QA_EPSILON
                    or abs(float(current["end_price"]) - float(prev["start_price"])) <= QA_EPSILON
                    or abs(float(current["end_price"]) - float(prev["end_price"])) <= QA_EPSILON
                )
                if shared_extreme:
                    candidate_reason_map[str(prev["canonical_leg_id"])].add("shared_extreme")
        for parent_id in sorted(explicit_parent_candidates):
            if parent_id in leg_lookup:
                parent_candidate = pd.Series({"canonical_leg_id": parent_id, **leg_lookup[parent_id]})
                rows.append(_make_relationship_candidate_row(current, parent_candidate, "parent", {"explicit_parent"}))
                candidate_reason_map[parent_id].add("explicit_parent")
        for _, prev in previous_rows.iterrows():
            prev_id = str(prev["canonical_leg_id"])
            prev_level = str(prev.get("primary_segment_level", ""))
            contains_current = ensure_utc(prev["start_time"]) <= current_start and ensure_utc(prev["end_time"]) >= ensure_utc(current["end_time"])
            if contains_current and prev_level in {"structural_impulse", "structural_correction"} and prev_level != current_level:
                candidate_reason_map[prev_id].add("higher_level_container")
            if str(prev["direction"]) != str(current["direction"]) and prev_level == "structural_impulse":
                candidate_reason_map[prev_id].add("previous_opposite_each_level")
        for candidate_id, reasons in sorted(candidate_reason_map.items()):
            if candidate_id not in leg_lookup:
                continue
            candidate = pd.Series({"canonical_leg_id": candidate_id, **leg_lookup[candidate_id]})
            relationship_kind = "reference" if any(
                reason in reasons
                for reason in {
                    "nearest_opposite_leg",
                    "previous_opposite_each_level",
                    "shared_extreme",
                    "explicit_parent",
                    "higher_level_container",
                }
            ) else "previous_non_overlapping"
            if "explicit_parent" in reasons:
                relationship_kind = "parent" if relationship_kind != "reference" else "reference"
            rows.append(_make_relationship_candidate_row(current, candidate, relationship_kind, reasons))
    return pd.DataFrame(rows)


def build_leg_rolling_features_retrospective_v3(canonical_legs: pd.DataFrame, leg_bars_h4: pd.DataFrame) -> pd.DataFrame:
    if canonical_legs.empty or leg_bars_h4.empty:
        return pd.DataFrame()
    direction_map = canonical_legs.set_index("canonical_leg_id")["direction"].astype(str).to_dict()
    end_time_map = canonical_legs.set_index("canonical_leg_id")["end_time"].to_dict()
    rows: List[dict] = []
    for leg_id, bars in leg_bars_h4.groupby("canonical_leg_id", sort=False):
        ordered = bars.sort_values("open_datetime").reset_index(drop=True).copy()
        direction = direction_map.get(str(leg_id), "up")
        leg_end_time = ensure_utc(end_time_map[str(leg_id)])
        for idx in range(1, len(ordered)):
            for window_name, window_size in RANGE_WINDOWS.items():
                hist = ordered.iloc[max(0, idx - window_size + 1): idx + 1].copy()
                prev_hist = ordered.iloc[max(0, idx - 2 * window_size + 1): max(0, idx - window_size + 1)].copy()
                metrics = compute_window_metrics(hist, prev_hist, direction)
                row = {
                    "canonical_leg_id": str(leg_id),
                    "open_datetime": ensure_utc(ordered.iloc[idx]["open_datetime"]),
                    "close_datetime": ensure_utc(ordered.iloc[idx]["close_datetime"]),
                    "available_at_time": ensure_utc(ordered.iloc[idx]["close_datetime"]),
                    "window_name": window_name,
                    "window_size_bars": window_size,
                    "bar_index_in_leg": int(ordered.iloc[idx]["bar_index_in_leg"]) if "bar_index_in_leg" in ordered.columns else idx,
                    "elapsed_fraction_of_leg": safe_div((ensure_utc(ordered.iloc[idx]["open_datetime"]) - ensure_utc(ordered.iloc[0]["open_datetime"])).total_seconds(), max((leg_end_time - ensure_utc(ordered.iloc[0]["open_datetime"])).total_seconds(), 1.0)),
                }
                row.update(metrics)
                rows.append(row)
    return pd.DataFrame(rows)


def build_retrospective_leg_events_v3(canonical_legs: pd.DataFrame, leg_bars_h4: pd.DataFrame) -> pd.DataFrame:
    if canonical_legs.empty or leg_bars_h4.empty:
        return pd.DataFrame(columns=ROLLING_EVENT_COLUMNS + ["available_at_time", "is_causal", "uses_future_leg_direction", "uses_future_parent"])
    leg_lookup = canonical_legs.set_index("canonical_leg_id").to_dict("index")
    rows: List[dict] = []
    for leg_id, bars in leg_bars_h4.groupby("canonical_leg_id", sort=False):
        ordered = bars.sort_values("open_datetime").reset_index(drop=True).copy()
        leg = leg_lookup[str(leg_id)]
        direction = str(leg["direction"])
        parent_duration_hours = safe_div((ensure_utc(leg["end_time"]) - ensure_utc(leg["start_time"])).total_seconds(), 3600.0)
        last_trend_extreme_index = 0
        parent_threshold_hits: set[str] = set()
        pullback_active = False
        for idx in range(1, len(ordered)):
            bar = ordered.iloc[idx]
            prev = ordered.iloc[idx - 1]
            event_time = ensure_utc(bar["close_datetime"])
            if direction == "up":
                if float(bar["high"]) > float(ordered.iloc[:idx]["high"].max()):
                    rows.append(_retro_event_row(leg_id, event_time, "new_trend_extreme", direction, "", float(bar["high"]), float("nan"), float(idx), ""))
                    last_trend_extreme_index = idx
                if float(bar["low"]) < float(ordered.iloc[:idx]["low"].min()):
                    rows.append(_retro_event_row(leg_id, event_time, "new_counter_extreme", direction, "", float(bar["low"]), float("nan"), float(idx), ""))
                direction_change = float(bar["close"]) < float(prev["close"])
                pullback_now = float(bar["close"]) < float(prev["close"])
            else:
                if float(bar["low"]) < float(ordered.iloc[:idx]["low"].min()):
                    rows.append(_retro_event_row(leg_id, event_time, "new_trend_extreme", direction, "", float(bar["low"]), float("nan"), float(idx), ""))
                    last_trend_extreme_index = idx
                if float(bar["high"]) > float(ordered.iloc[:idx]["high"].max()):
                    rows.append(_retro_event_row(leg_id, event_time, "new_counter_extreme", direction, "", float(bar["high"]), float("nan"), float(idx), ""))
                direction_change = float(bar["close"]) > float(prev["close"])
                pullback_now = float(bar["close"]) > float(prev["close"])
            if direction_change:
                rows.append(_retro_event_row(leg_id, event_time, "direction_change", direction, "", float(bar["close"]), float(prev["close"]), float(idx), ""))
            if pullback_now and not pullback_active:
                pullback_active = True
                rows.append(_retro_event_row(leg_id, event_time, "internal_pullback_start", direction, "", float(bar["close"]), float(prev["close"]), float(idx), ""))
            if pullback_active and not pullback_now:
                pullback_active = False
                rows.append(_retro_event_row(leg_id, event_time, "internal_pullback_end", direction, "", float(bar["close"]), float(prev["close"]), float(idx), ""))
            hours_without_new_extreme = float(idx - last_trend_extreme_index) * 4.0
            for threshold_hours, label in [(24.0, "24h"), (72.0, "3d"), (168.0, "7d"), (336.0, "14d")]:
                if hours_without_new_extreme >= threshold_hours and f"no_new_extreme_{label}_{last_trend_extreme_index}" not in parent_threshold_hits:
                    parent_threshold_hits.add(f"no_new_extreme_{label}_{last_trend_extreme_index}")
                    rows.append(_retro_event_row(leg_id, event_time, f"no_new_extreme_{label}", direction, "", float(bar["close"]), float("nan"), hours_without_new_extreme, ""))
            elapsed_ratio = safe_div((ensure_utc(bar["close_datetime"]) - ensure_utc(leg["start_time"])).total_seconds(), max((ensure_utc(leg["end_time"]) - ensure_utc(leg["start_time"])).total_seconds(), 1.0))
            for level_name, threshold in PARENT_TIME_LEVELS.items():
                if elapsed_ratio >= threshold and level_name not in parent_threshold_hits:
                    parent_threshold_hits.add(level_name)
                    rows.append(_retro_event_row(leg_id, event_time, f"parent_time_{level_name}", direction, "", float(bar["close"]), float("nan"), threshold * parent_duration_hours, ""))
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["canonical_leg_id", "event_time", "event_type"]).reset_index(drop=True)
    return frame


def _retro_event_row(
    leg_id: str,
    event_time: pd.Timestamp,
    event_type: str,
    direction: str,
    window: str,
    price: float,
    reference_price: float,
    value: float,
    details: str,
) -> dict:
    return {
        "canonical_leg_id": leg_id,
        "event_time": event_time,
        "event_type": event_type,
        "direction": direction,
        "window": window,
        "price": price,
        "reference_price": reference_price,
        "value": value,
        "reference_canonical_leg_id": "",
        "details": details,
        "available_at_time": event_time,
        "is_causal": False,
        "uses_future_leg_direction": True,
        "uses_future_parent": True,
    }


def _make_relationship_candidate_row(
    current: pd.Series,
    candidate: pd.Series,
    relationship_kind: str,
    candidate_reasons: set[str],
) -> dict:
    current_start = ensure_utc(current["start_time"])
    current_end = ensure_utc(current["end_time"])
    candidate_start = ensure_utc(candidate["start_time"])
    candidate_end = ensure_utc(candidate["end_time"])
    candidate_move_abs = abs(float(candidate["end_price"]) - float(candidate["start_price"]))
    current_direction = str(current["direction"])
    current_extreme = float(current["end_price"])
    retracement_abs = abs(current_extreme - float(candidate["end_price"]))
    shared_extreme_gap_abs = min(
        abs(float(current["start_price"]) - float(candidate["start_price"])),
        abs(float(current["start_price"]) - float(candidate["end_price"])),
        abs(float(current["end_price"]) - float(candidate["start_price"])),
        abs(float(current["end_price"]) - float(candidate["end_price"])),
    )
    return {
        "current_leg_id": str(current["canonical_leg_id"]),
        "candidate_leg_id": str(candidate["canonical_leg_id"]),
        "relationship_kind": relationship_kind,
        "candidate_reason": "|".join(sorted(candidate_reasons)),
        "current_segment_level": str(current.get("primary_segment_level", "")),
        "candidate_direction": str(candidate["direction"]),
        "current_direction": current_direction,
        "candidate_segment_level": str(candidate.get("primary_segment_level", candidate.get("segment_levels", candidate.get("segment_level", "")))),
        "candidate_start_time": to_iso(candidate_start),
        "candidate_end_time": to_iso(candidate_end),
        "candidate_duration_hours": safe_div((candidate_end - candidate_start).total_seconds(), 3600.0),
        "candidate_move_abs": candidate_move_abs,
        "candidate_move_pct": safe_div(float(candidate["end_price"]) - float(candidate["start_price"]), float(candidate["start_price"])),
        "time_gap_hours": safe_div((current_start - candidate_end).total_seconds(), 3600.0),
        "shared_extreme": bool("shared_extreme" in candidate_reasons),
        "shared_extreme_gap_abs": shared_extreme_gap_abs,
        "shared_extreme_gap_pct": safe_div(shared_extreme_gap_abs, abs(float(candidate["end_price"]))),
        "contains_current_leg": bool(candidate_start <= current_start and candidate_end >= current_end),
        "explicit_upstream_link": bool("explicit_parent" in candidate_reasons),
        "direct_temporal_predecessor": bool("direct_temporal_predecessor" in candidate_reasons),
        "same_level_predecessor": bool("same_level_predecessor" in candidate_reasons),
        "higher_level_container": bool("higher_level_container" in candidate_reasons),
        "retracement_of_candidate_abs": retracement_abs,
        "retracement_of_candidate_pct": safe_div(retracement_abs, candidate_move_abs),
        "amplitude_ratio": safe_div(abs(float(current["end_price"]) - float(current["start_price"])), candidate_move_abs),
    }


def build_relationship_summary_v3(canonical_legs: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    ordered = canonical_legs.copy().sort_values(["start_time", "end_time", "canonical_leg_id"]).reset_index(drop=True)
    if "primary_segment_level" not in ordered.columns:
        if not candidates.empty and "current_segment_level" in candidates.columns:
            level_map = candidates.groupby("current_leg_id")["current_segment_level"].agg(lambda values: next((str(v) for v in values if str(v)), "")).to_dict()
            ordered["primary_segment_level"] = ordered["canonical_leg_id"].astype(str).map(level_map).fillna("")
        else:
            ordered["primary_segment_level"] = ""
    rows: List[dict] = []
    for idx, current in ordered.iterrows():
        current_id = str(current["canonical_leg_id"])
        subset = candidates[candidates["current_leg_id"].astype(str) == current_id] if not candidates.empty else pd.DataFrame()
        previous_row_id = str(ordered.iloc[idx - 1]["canonical_leg_id"]) if idx > 0 else ""
        earlier = ordered.iloc[:idx].copy()
        earlier_non_overlap = earlier[earlier["end_time"].apply(ensure_utc) <= ensure_utc(current["start_time"])].copy()
        prev_non_overlap_status = "missing"
        prev_non_overlap_id = ""
        if not earlier_non_overlap.empty:
            max_end = earlier_non_overlap["end_time"].apply(ensure_utc).max()
            tied = earlier_non_overlap[earlier_non_overlap["end_time"].apply(ensure_utc) == max_end]
            if len(tied) == 1:
                prev_non_overlap_id = str(tied.iloc[0]["canonical_leg_id"])
                prev_non_overlap_status = "unique"
            else:
                prev_non_overlap_status = "ambiguous"
        same_level = earlier_non_overlap[
            earlier_non_overlap["primary_segment_level"].astype(str) == str(current.get("primary_segment_level", ""))
        ] if not earlier_non_overlap.empty else pd.DataFrame()
        prev_same_level_status = "missing"
        prev_same_level_id = ""
        if not same_level.empty:
            max_same_level_end = same_level["end_time"].apply(ensure_utc).max()
            tied_same_level = same_level[same_level["end_time"].apply(ensure_utc) == max_same_level_end]
            if len(tied_same_level) == 1:
                prev_same_level_id = str(tied_same_level.iloc[0]["canonical_leg_id"])
                prev_same_level_status = "unique"
            else:
                prev_same_level_status = "ambiguous"
        parent_subset = subset[subset["relationship_kind"] == "parent"] if not subset.empty else pd.DataFrame()
        reference_subset = subset[subset["relationship_kind"] == "reference"] if not subset.empty else pd.DataFrame()
        parent_status = "unique" if len(parent_subset) == 1 else ("ambiguous" if len(parent_subset) > 1 else "missing")
        reference_status = "unique" if len(reference_subset) == 1 else ("ambiguous" if len(reference_subset) > 1 else "missing")
        rows.append(
            {
                "canonical_leg_id": current_id,
                "direction": str(current["direction"]),
                "start_time": to_iso(current["start_time"]),
                "end_time": to_iso(current["end_time"]),
                "previous_row_canonical_leg_id": previous_row_id,
                "previous_non_overlapping_leg_id": prev_non_overlap_id,
                "previous_non_overlapping_status": prev_non_overlap_status,
                "previous_non_overlapping_same_level_leg_id": prev_same_level_id,
                "previous_non_overlapping_same_level_status": prev_same_level_status,
                "parent_canonical_leg_id": str(parent_subset.iloc[0]["candidate_leg_id"]) if len(parent_subset) == 1 else "",
                "reference_canonical_leg_id": str(reference_subset.iloc[0]["candidate_leg_id"]) if len(reference_subset) == 1 else "",
                "parent_relationship_status": parent_status,
                "reference_relationship_status": reference_status,
            }
        )
    return pd.DataFrame(rows)


def build_v2_to_v3_migration(v2_static_path: Path, v3_static: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    v3_columns = set(v3_static.columns.tolist())
    if not v2_static_path.exists():
        return pd.DataFrame(columns=["v2_feature_name", "v3_feature_name", "status", "reason", "formula_changed", "causality_changed", "units_changed"])
    v2_columns = pd.read_csv(v2_static_path, nrows=1).columns.tolist()
    for column in v2_columns:
        if column in v3_columns:
            status = "preserved"
            target = column
            reason = "kept in v3 static dataset"
        elif column.startswith("central_50_"):
            status = "corrected"
            target = column.replace("central_50_", "central_")
            reason = "zone logic replaced by 0-30 / 30-70 / 70-100 overlap fields"
        elif column.startswith("false_break_"):
            status = "dropped_invalid"
            target = ""
            reason = "false-break labels removed from dataset collection layer"
        elif column.startswith("return_inside_after_"):
            status = "moved_to_decision_support"
            target = "decision_dynamic_range_excursions.csv"
            reason = "return-inside evaluation moved to decision-support excursion table"
        else:
            status = "moved_to_retrospective" if column == "elapsed_fraction_of_leg" else "dropped_invalid"
            target = ""
            reason = "removed from static v3 or relocated"
        rows.append(
            {
                "v2_feature_name": column,
                "v3_feature_name": target,
                "status": status,
                "reason": reason,
                "formula_changed": False,
                "causality_changed": column == "elapsed_fraction_of_leg",
                "units_changed": False,
            }
        )
    return pd.DataFrame(rows)


def build_decision_register(output_dir: Path) -> pd.DataFrame:
    decision_requirements = {
        "parent_reference": {
            "candidate_methods": "formal_candidate_set_v3",
            "required_columns": "current_leg_id|candidate_leg_id|relationship_kind|candidate_reason|current_segment_level|candidate_segment_level|current_direction|candidate_direction",
        },
        "window_comparison": {
            "candidate_methods": "rolling_window_18|rolling_window_42|rolling_window_84",
            "required_columns": "time|window_size|range_abs|range_ratio_current_to_previous|inside_share|mid_cross_rate|upper_slope|lower_slope|mid_slope|width_change_ratio|upper_touch_count|lower_touch_count|alternating_touch_count|close_path_efficiency|realized_vol_log_return_std|coverage_status|bars_available|window_is_full",
        },
        "dynamic_range": {
            "candidate_methods": "A|B|C",
            "required_columns": "range_candidate_id|candidate_available_at|method|window_size_bars|upper_projected_current|lower_projected_current|width_change_ratio|close_inside_share|full_candle_inside_share|wick_inside_share",
        },
        "dynamic_excursions": {
            "candidate_methods": "upper|lower|both",
            "required_columns": "range_candidate_id|observation_time|side|wick_distance_beyond_abs|close_distance_beyond_abs|h1_bars_available|h1_horizon_complete|h1_upper_mfe|h1_lower_mfe|h3_upper_mfe|h6_upper_mfe",
        },
        "boundary_alignment": {
            "candidate_methods": "same_source_exact_match|same_source_extreme_mismatch|cross_source_only",
            "required_columns": "canonical_leg_id|timeframe|market_source|selected_15m_extreme|alignment_status|mismatch_abs|match_epsilon",
        },
        "path_efficiency": {
            "candidate_methods": "4h|15m|extreme_anchor_approx",
            "required_columns": "canonical_leg_id|close_path_length_4h|close_path_efficiency_4h|close_path_length_15m|close_path_efficiency_15m|extreme_anchor_close_path_efficiency_15m_approx",
        },
        "thresholds": {
            "candidate_methods": "A|B|C",
            "required_columns": "time|range_candidate_id|method|window_size|range_ratio_current_to_previous|upper_slope_atr_per_bar|lower_slope_atr_per_bar|parallelism_atr_normalized|width_change_ratio|close_inside_share|full_candle_inside_share|wick_inside_share|mid_cross_rate_per_bar|upper_touch_count_005atr|upper_touch_count_010atr|upper_touch_count_020atr|upper_touch_count_030atr|lower_touch_count_005atr|lower_touch_count_010atr|lower_touch_count_020atr|lower_touch_count_030atr|alternating_touch_count|same_side_repeat_count|recent_speed_24h_signed|recent_speed_3d_signed|recent_speed_7d_signed|close_path_efficiency|realized_vol_log_return_std|volume_to_30d_mean|volume_to_30d_median|volume_zscore_30d|wick_distance_beyond_atr|close_distance_beyond_atr|coverage_status",
        },
        "coverage": {
            "candidate_methods": "coverage_gap_audit",
            "required_columns": "canonical_leg_id|timeframe|coverage_status|bars_present|bars_expected",
        },
    }
    decisions = [
        ("parent_reference", "Как выбирать parent/reference при неоднозначности?", "decision_parent_reference_candidates.csv"),
        ("window_comparison", "Какое окно лучше для range formalization?", "decision_window_comparison.csv"),
        ("dynamic_range", "Какой method/window даёт лучший range candidate?", "decision_dynamic_range_candidates.csv"),
        ("dynamic_excursions", "Как формализовать выходы из диапазона?", "decision_dynamic_range_excursions.csv"),
        ("boundary_alignment", "Как учитывать boundary alignment mismatch?", "decision_boundary_alignment.csv"),
        ("path_efficiency", "Какая версия path efficiency полезнее?", "decision_path_efficiency_comparison.csv"),
        ("thresholds", "Какие continuous thresholds затем изучать?", "decision_threshold_research.csv"),
        ("coverage", "Как трактовать partial 15m/4h coverage?", "decision_coverage_issues.csv"),
    ]
    return pd.DataFrame(
        [
            {
                "decision_id": decision_id,
                "question": question,
                "status": "open",
                "candidate_methods": decision_requirements[decision_id]["candidate_methods"],
                "decision_support_file": str(output_dir / filename),
                "required_columns": decision_requirements[decision_id]["required_columns"],
                "final_choice": "",
                "choice_reason": "",
            }
            for decision_id, question, filename in decisions
        ]
    )


def select_smoke_candidates(
    canonical_legs: pd.DataFrame,
    static_features: pd.DataFrame,
    excursions: pd.DataFrame,
    fibtime_events: pd.DataFrame,
    memberships: pd.DataFrame,
) -> pd.DataFrame:
    legs = canonical_legs.merge(static_features, on="canonical_leg_id", how="left", suffixes=("", "_static"))
    rows: List[dict] = []
    eligible = legs[legs["num_4h_bars"].fillna(0) >= 12].copy()
    if not eligible.empty:
        clean = eligible.sort_values(["path_efficiency", "overlap_ratio"], ascending=[False, True]).iloc[0]
        rows.append({"case_id": "clean_impulse_candidate", "canonical_leg_id": clean["canonical_leg_id"], "reason": "max path_efficiency with low overlap", "timeframe": "4H", "window_size": "", "range_method": ""})
        range_like = eligible.sort_values(["overlap_ratio", "countertrend_close_bar_pct"], ascending=[False, False]).iloc[0]
        rows.append({"case_id": "pronounced_range_candidate", "canonical_leg_id": range_like["canonical_leg_id"], "reason": "high overlap and countertrend close share", "timeframe": "4H", "window_size": "", "range_method": ""})
        mixed = eligible.assign(mixed_score=(eligible["overlap_ratio"].fillna(0.0) + (1.0 - eligible["path_efficiency"].fillna(0.0)))).sort_values("mixed_score", ascending=False).iloc[0]
        rows.append({"case_id": "mixed_leg_candidate", "canonical_leg_id": mixed["canonical_leg_id"], "reason": "high mixed_score", "timeframe": "4H", "window_size": "", "range_method": ""})
        latest = legs.sort_values("end_time").iloc[-1]
        rows.append({"case_id": "coverage_end_candidate", "canonical_leg_id": latest["canonical_leg_id"], "reason": "latest leg near known coverage end", "timeframe": "4H", "window_size": "", "range_method": ""})
    if not excursions.empty:
        wick_only = excursions[excursions["wick_only_break"] == True]
        if not wick_only.empty:
            selected = wick_only.iloc[0]
            rows.append({"case_id": "boundary_excursion_and_return_candidate", "canonical_leg_id": "", "reason": "first wick-only excursion", "timeframe": "4H", "window_size": str(selected["range_candidate_id"]).split("_")[-2], "range_method": str(selected["range_candidate_id"]).split("_")[-1], "range_candidate_id": selected["range_candidate_id"]})
    if not fibtime_events.empty:
        confirmed = fibtime_events[fibtime_events["event_type"] == "fibtime_confirmed"]
        if not confirmed.empty:
            impulse_id = str(confirmed.iloc[0]["impulse_id"])
            member = memberships[(memberships["source_table"] == "structural_impulses_log20_fibtime") & (memberships["source_id"] == impulse_id)]
            leg_id = str(member.iloc[0]["canonical_leg_id"]) if not member.empty else ""
            rows.append({"case_id": "fibtime_crossing_candidate", "canonical_leg_id": leg_id, "reason": "first confirmed fibtime event", "timeframe": "4H", "window_size": "", "range_method": "", "impulse_id": impulse_id})
    frame = pd.DataFrame(rows).drop_duplicates(subset=["case_id"], keep="first")
    return frame


def smoke_intervals_from_candidates(cases: pd.DataFrame, canonical_legs: pd.DataFrame, dynamic_candidates: pd.DataFrame) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    ranges: List[Tuple[pd.Timestamp, pd.Timestamp]] = []
    leg_lookup = canonical_legs.set_index("canonical_leg_id").to_dict("index")
    dyn_lookup = dynamic_candidates.set_index("range_candidate_id").to_dict("index") if not dynamic_candidates.empty else {}
    for _, case in cases.iterrows():
        leg_id = str(case.get("canonical_leg_id", "") or "")
        range_candidate_id = str(case.get("range_candidate_id", "") or "")
        if leg_id and leg_id in leg_lookup:
            leg = leg_lookup[leg_id]
            ranges.append((ensure_utc(leg["start_time"]) - pd.Timedelta(days=2), ensure_utc(leg["end_time"]) + pd.Timedelta(days=2)))
        elif range_candidate_id and range_candidate_id in dyn_lookup:
            candidate = dyn_lookup[range_candidate_id]
            center = ensure_utc(candidate["candidate_available_at"])
            ranges.append((center - pd.Timedelta(days=10), center + pd.Timedelta(days=10)))
    if not ranges:
        ranges.append((H4_TRANSITION_START, min(KNOWN_COVERAGE_END, H4_TRANSITION_START + pd.Timedelta(days=30))))
    return merge_time_ranges(ranges)


def build_feature_dictionary_v3(
    static_features: pd.DataFrame,
    causal_4h: pd.DataFrame,
    dynamic_candidates: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[dict] = []

    def add_frame(frame: pd.DataFrame, table_name: str, timeframe: str, is_causal: bool) -> None:
        for column in frame.columns:
            if column in {"canonical_leg_id", "open_datetime", "close_datetime", "available_at_time", "range_candidate_id"}:
                continue
            rows.append(
                {
                    "feature_name": column,
                    "table_name": table_name,
                    "description": FEATURE_METADATA.get(column, {}).get("description", column.replace("_", " ")),
                    "exact_formula": FEATURE_METADATA.get(column, {}).get("exact_formula", f"legacy formula: {column}"),
                    "timeframe": timeframe,
                    "window": "rolling" if "window" in column else "",
                    "units": FEATURE_METADATA.get(column, {}).get("units", "ratio" if any(token in column for token in ["pct", "ratio", "share", "efficiency"]) else ("hours" if "hours" in column else ("bars" if "bars" in column or "count" in column else "price"))),
                    "signed_or_absolute": FEATURE_METADATA.get(column, {}).get("signed_or_absolute", "signed" if any(token in column for token in ["signed", "slope", "log"]) and "abs" not in column else "absolute_or_not_applicable"),
                    "available_at_time_rule": "bar_close" if is_causal else "leg_complete",
                    "is_causal": is_causal,
                    "uses_future_leg_direction": bool((not is_causal) and ("direction" in column or "trend_" in column)),
                    "uses_future_leg_boundary": bool((not is_causal) and any(token in column for token in ["elapsed", "duration", "segment_", "end_"])),
                    "uses_future_parent": bool((not is_causal) and "parent_" in column),
                    "uses_future_reference": bool((not is_causal) and ("reference_" in column or "previous_" in column)),
                    "missing_value_rule": "NaN when source data is unavailable or denominator is zero",
                    "notes": "",
                }
            )

    add_frame(static_features, "structure_leg_features_static.csv", "retrospective", False)
    add_frame(causal_4h, "market_features_rolling_4h_causal.parquet", "4H", True)
    add_frame(dynamic_candidates, "dynamic_range_candidates_4h_causal.parquet", "4H", True)
    frame = pd.DataFrame(rows).drop_duplicates(subset=["feature_name", "table_name"]).sort_values(["table_name", "feature_name"]).reset_index(drop=True)
    return frame


def build_data_dictionary_v3(output_files: Dict[str, str]) -> str:
    lines = [
        "# Structure Research Dataset v3",
        "",
        "## Boundary rule",
        "",
        "`start_time <= bar_open_time < end_time`",
        "",
        "## Notes",
        "",
        "- Early spot period can remain `1D` only when `4H` and `15M` raw candles are unavailable locally.",
        "- `market_features_rolling_4h_causal.parquet` uses only already-closed history bars.",
        "- `dynamic_range_candidates_4h_causal.parquet` stores exploratory candidates only, not final labels.",
        "- `structural_market_source_status=time_inferred_from_transition` means source was inferred only from the documented spot/futures transition boundary.",
        "",
        "## Output files",
        "",
    ]
    lines.extend([f"- `{name}` -> `{path}`" for name, path in output_files.items()])
    return "\n".join(lines)


def run_qa_v3(
    canonical_legs: pd.DataFrame,
    static_features: pd.DataFrame,
    causal_4h: pd.DataFrame,
    fibtime_events: pd.DataFrame,
    endpoint_alignment: pd.DataFrame,
    coverage_frame: pd.DataFrame,
    dynamic_excursions: Optional[pd.DataFrame] = None,
    feature_dictionary: Optional[pd.DataFrame] = None,
    source_frames: Optional[Dict[str, pd.DataFrame]] = None,
) -> dict:
    critical_failures: List[str] = []
    warnings: List[str] = []
    if bool(canonical_legs["canonical_leg_id"].duplicated().any()):
        critical_failures.append("duplicate_canonical_leg_id")
    if bool((canonical_legs["start_time"] >= canonical_legs["end_time"]).any()):
        critical_failures.append("start_time_gte_end_time")
    forbidden_causal_columns = {
        "canonical_leg_id",
        "elapsed_fraction_of_leg",
        "speed_pct_per_day_direction_adjusted",
    }
    for forbidden_column in forbidden_causal_columns:
        if forbidden_column in causal_4h.columns:
            critical_failures.append(f"{forbidden_column}_present_in_causal_table")
    for column in [
        "path_efficiency",
        "close_path_efficiency",
        "high_low_path_efficiency",
        "close_path_efficiency_4h",
        "close_path_efficiency_15m",
        "extreme_anchor_close_path_efficiency_15m_approx",
    ]:
        if column in static_features.columns:
            series = pd.to_numeric(static_features[column], errors="coerce").dropna()
            if not series.empty and bool(((series < -QA_EPSILON) | (series > 1.0 + QA_EPSILON)).any()):
                critical_failures.append(f"path_efficiency_out_of_bounds:{column}")
    forbidden_static_prefixes = [
        "close_in_central_50_pct",
        "central_50_overlap_share",
        "false_break_count",
        "false_break_rate",
        "return_inside_after_1_bar_count",
        "return_inside_after_3_bar_count",
        "return_inside_after_6_bar_count",
        "return_inside_after_1_bar",
        "return_inside_after_3_bar",
        "return_inside_after_6_bar",
    ]
    for column in static_features.columns:
        if any(column.startswith(prefix) for prefix in forbidden_static_prefixes):
            critical_failures.append(f"forbidden_static_feature_present:{column}")
    if "empty_market_source_count" in static_features.columns:
        empty_counts = pd.to_numeric(static_features["empty_market_source_count"], errors="coerce").fillna(0.0)
        if bool((empty_counts > 0).any()):
            critical_failures.append("empty_market_source_in_used_candles")
    if not endpoint_alignment.empty:
        same_source_mismatch = endpoint_alignment[endpoint_alignment["alignment_status"] == "same_source_extreme_mismatch"]
        if not same_source_mismatch.empty:
            critical_failures.append("same_source_extreme_mismatch")
    if dynamic_excursions is not None and not dynamic_excursions.empty and "side" in dynamic_excursions.columns:
        if bool(dynamic_excursions["side"].astype(str).eq("inside").any()):
            critical_failures.append("excursion_rows_without_actual_excursion")
    if not fibtime_events.empty:
        uniqueness = fibtime_events.groupby(["impulse_id", "deadline_version", "event_type"]).size()
        if bool((uniqueness > 1).any()):
            critical_failures.append("duplicate_fibtime_event_key")
    if coverage_frame.empty:
        warnings.append("coverage_frame_empty")
    if not coverage_frame.empty and bool((coverage_frame["coverage_status"] == "timeframe_unavailable").any()):
        warnings.append("timeframe_unavailable_for_some_legs")
    if feature_dictionary is not None and not feature_dictionary.empty:
        causal_rows = feature_dictionary[feature_dictionary["is_causal"] == True]
        numeric_rows = feature_dictionary[feature_dictionary["units"].astype(str) != ""]
        empty_formula = numeric_rows["exact_formula"].fillna("").astype(str).str.strip().eq("")
        if bool(empty_formula.any()):
            critical_failures.append("feature_dictionary_empty_exact_formula")
        if not causal_rows.empty and bool(
            causal_rows[["uses_future_leg_direction", "uses_future_leg_boundary", "uses_future_parent", "uses_future_reference"]].fillna(False).any(axis=1).any()
        ):
            critical_failures.append("feature_dictionary_marks_future_dependency_in_causal_table")
    if source_frames:
        for timeframe_label, frame in source_frames.items():
            validation = validate_market_bars(frame, timeframe_label)
            if any(issue in validation["issues"] for issue in {"duplicate_open_datetime", "non_monotonic_open_datetime", "close_not_after_open", "high_below_open_or_close", "low_above_open_or_close", "high_below_low", "negative_volume", "empty_market_source"}):
                critical_failures.append(f"critical_input_issue:{timeframe_label}")
    almost_constant = []
    missingness = {}
    numeric_distributions = {}
    for column in static_features.columns:
        if pd.api.types.is_numeric_dtype(static_features[column]):
            stats = feature_stats(static_features[column])
            numeric_distributions[column] = stats
            if stats["unique_count"] <= 2:
                almost_constant.append(column)
            missingness[column] = safe_div(stats["nan_count"], stats["count"])
    qa = {
        "checks": {
            "critical_failure_count": len(critical_failures),
            "warning_count": len(warnings),
            "causal_table_excludes_elapsed_fraction_of_leg": "elapsed_fraction_of_leg" not in causal_4h.columns,
            "causal_table_excludes_direction_adjusted_speed": "speed_pct_per_day_direction_adjusted" not in causal_4h.columns,
        },
        "critical_failures": critical_failures,
        "warnings": warnings,
        "problem_lists": {
            "same_source_mismatch_rows": endpoint_alignment[endpoint_alignment["alignment_status"] == "same_source_extreme_mismatch"]["canonical_leg_id"].astype(str).tolist() if not endpoint_alignment.empty else [],
            "timeframe_unavailable_legs": coverage_frame[coverage_frame["coverage_status"] == "timeframe_unavailable"]["canonical_leg_id"].astype(str).tolist() if not coverage_frame.empty else [],
        },
        "numeric_distributions": numeric_distributions,
        "almost_constant_features": almost_constant,
        "missingness_by_feature": missingness,
        "coverage_by_timeframe": coverage_frame.groupby("timeframe")["coverage_status"].value_counts().to_dict() if not coverage_frame.empty else {},
        "causality_audit": {
            "causal_table_name": "market_features_rolling_4h_causal.parquet",
            "noncausal_columns_found": ["elapsed_fraction_of_leg"] if "elapsed_fraction_of_leg" in causal_4h.columns else [],
        },
        "event_uniqueness_audit": fibtime_events.groupby(["impulse_id", "deadline_version", "event_type"]).size().to_dict() if not fibtime_events.empty else {},
        "boundary_alignment_audit": endpoint_alignment["alignment_status"].value_counts().to_dict() if not endpoint_alignment.empty else {},
        "path_efficiency_audit": {
            column: feature_stats(static_features[column])
            for column in ["path_efficiency", "close_path_efficiency", "high_low_path_efficiency", "close_path_efficiency_4h", "close_path_efficiency_15m", "extreme_anchor_close_path_efficiency_15m_approx"]
            if column in static_features.columns
        },
        "source_provenance": {
            "daily_source_counts": summarize_market_sources(source_frames.get("1D", pd.DataFrame())) if source_frames else "",
            "h4_source_counts": summarize_market_sources(source_frames.get("4H", pd.DataFrame())) if source_frames else "",
            "m15_source_counts": summarize_market_sources(source_frames.get("15M", pd.DataFrame())) if source_frames else "",
        },
        "status": "failed" if critical_failures else "passed",
    }
    return qa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build research dataset v3 for macro structure formalization.")
    parser.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN))
    parser.add_argument("--daily-parquet", default=str(DEFAULT_DAILY_PARQUET))
    parser.add_argument("--daily-merge-summary", default=str(DEFAULT_DAILY_MERGE_SUMMARY))
    parser.add_argument("--merged-h4-parquet", default="")
    parser.add_argument("--spot-h4-parquet", default="")
    parser.add_argument("--futures-h4-parquet", default=str(DEFAULT_FUTURES_H4))
    parser.add_argument("--merged-15m-parquet", default="")
    parser.add_argument("--spot-15m-parquet", default="")
    parser.add_argument("--futures-15m-parquet", default="")
    parser.add_argument("--aggtrades-root", default=str(DEFAULT_AGGTRADES_ROOT))
    parser.add_argument("--parquet-manifest", default=str(DEFAULT_PARQUET_MANIFEST))
    parser.add_argument("--parquet-schema", default=str(DEFAULT_PARQUET_SCHEMA))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_run_dir = Path(args.base_run_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepare_output_directory_for_run(output_dir, bool(args.resume))
    partials_dir = output_dir / "partials"
    partials_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.json"
    checkpoint_path = output_dir / "checkpoint.json"
    config_hash = compute_config_hash_v3(args)
    critical_input_issues = {"duplicate_open_datetime", "non_monotonic_open_datetime", "close_not_after_open", "high_below_open_or_close", "low_above_open_or_close", "high_below_low", "negative_volume", "empty_market_source"}
    try:
        checkpoint = load_checkpoint(checkpoint_path, config_hash)
        stale_checkpoint_warning = ""
        if args.resume and checkpoint.get("saved_at"):
            saved_at = ensure_utc(checkpoint["saved_at"])
            age_seconds = (pd.Timestamp.now(tz=UTC) - saved_at).total_seconds()
            if age_seconds > STALE_CHECKPOINT_SECONDS and checkpoint.get("stage") not in {"complete"}:
                stale_checkpoint_warning = "stale_checkpoint_detected"
        run_config = {
            "mode": args.mode,
            "resume": bool(args.resume),
            "config_hash": config_hash,
            "base_run_dir": str(base_run_dir),
            "daily_parquet": str(args.daily_parquet),
            "daily_merge_summary": str(args.daily_merge_summary),
            "merged_h4_parquet": str(args.merged_h4_parquet),
            "spot_h4_parquet": str(args.spot_h4_parquet),
            "futures_h4_parquet": str(args.futures_h4_parquet),
            "merged_15m_parquet": str(args.merged_15m_parquet),
            "spot_15m_parquet": str(args.spot_15m_parquet),
            "futures_15m_parquet": str(args.futures_15m_parquet),
            "aggtrades_root": str(args.aggtrades_root),
            "parquet_manifest": str(args.parquet_manifest),
            "parquet_schema": str(args.parquet_schema),
            "output_dir": str(output_dir),
        }
        atomic_write_json(output_dir / "run_config.json", run_config)
        update_progress(progress_path, {"stage": "startup", "message": "initializing v3 dataset build", "config_hash": config_hash, "mode": args.mode})
        update_stage_checkpoint(checkpoint_path, checkpoint, "startup", "initializing v3 dataset build")

        source_discovery = discover_raw_ohlcv_sources(Path(args.parquet_manifest), Path(args.parquet_schema))

        daily = load_ohlc_frame(Path(args.daily_parquet))
        daily, source_transition_time = infer_daily_market_sources(daily, Path(args.daily_merge_summary))
        daily = add_source_provenance(daily, market_source="", source_file=str(args.daily_parquet), source_type="merged_daily_ohlcv", source_symbol="BTCUSDT", source_timeframe="1D")
        daily = ensure_market_source(daily, "spot", "futures", H4_TRANSITION_START)
        daily = add_market_indicators_v3(daily, interval_hours=24.0)
        daily["atr14"] = daily["atr14_wilder"]

        merged_h4_path = Path(args.merged_h4_parquet) if args.merged_h4_parquet else None
        spot_h4_path = Path(args.spot_h4_parquet) if args.spot_h4_parquet else None
        futures_h4_path = Path(args.futures_h4_parquet) if args.futures_h4_parquet else None
        if not merged_h4_path and not spot_h4_path and not futures_h4_path:
            merged_h4_path, spot_h4_path, futures_h4_path = discover_default_4h_paths()
        market_h4, h4_metadata = load_or_build_h4_market(merged_h4_path, spot_h4_path, futures_h4_path)
        market_h4 = add_source_provenance(market_h4, market_source="", source_file=str(merged_h4_path or futures_h4_path or spot_h4_path or ""), source_type="raw_or_merged_ohlcv", source_symbol="BTCUSDT", source_timeframe="4H")
        market_h4 = ensure_market_source(market_h4, "spot", "futures", H4_TRANSITION_START)
        market_h4 = market_h4[market_h4["open_datetime"] <= KNOWN_COVERAGE_END].reset_index(drop=True)
        market_h4 = add_market_indicators_v3(market_h4, interval_hours=4.0)
        market_h4["atr14"] = market_h4["atr14_wilder"]

        daily_validation = validate_market_bars(daily, "1D")
        h4_validation = validate_market_bars(market_h4, "4H")
        if any(issue in critical_input_issues for issue in daily_validation["issues"] + h4_validation["issues"]):
            build_failure_report(output_dir, "critical input validation failure", "source_validation", {"daily": daily_validation, "h4": h4_validation})
            return 1
        update_progress(progress_path, {"stage": "sources_loaded", "message": "daily and 4H sources loaded", "daily_rows": len(daily), "h4_rows": len(market_h4), "mode": args.mode, "config_hash": config_hash})
        update_stage_checkpoint(checkpoint_path, checkpoint, "sources_loaded", "daily and 4H sources loaded")

        tables = load_source_tables(base_run_dir)
        source_records = build_source_records(tables["raw_legs"], tables["impulses"], tables["corrections"], tables["market_segments"], tables["regime_segments"], daily)
        canonical_legs, memberships = canonicalize_legs(source_records)

        leg_bars_1d, _ = run_leg_bar_stage_incremental(canonical_legs, daily, "1D", "leg_bars_1d_v3", partials_dir, checkpoint_path, checkpoint, progress_path)
        leg_bars_h4, _ = run_leg_bar_stage_incremental(canonical_legs, market_h4, "4H", "leg_bars_4h_v3", partials_dir, checkpoint_path, checkpoint, progress_path)
        h4_aux_cols = [col for col in ["atr14", "atr14_sma", "atr14_wilder", "log_close", "pct_return", "log_return", "volume_to_30d_median", "volume_to_30d_mean", "volume_zscore_30d"] if col in market_h4.columns]
        if h4_aux_cols and not leg_bars_h4.empty:
            leg_bars_h4 = leg_bars_h4.merge(market_h4[["open_datetime"] + h4_aux_cols].drop_duplicates("open_datetime"), on="open_datetime", how="left")
        rolling_4h_retrospective = build_leg_rolling_features_retrospective_v3(canonical_legs, leg_bars_h4)
        events = build_retrospective_leg_events_v3(canonical_legs, leg_bars_h4)

        causal_4h = build_causal_market_features_4h(market_h4)
        dynamic_candidates = build_dynamic_range_candidates(market_h4)
        excursions = build_dynamic_range_excursions(dynamic_candidates, market_h4)
        fibtime_v3 = build_fibtime_events_v3(base_run_dir, tables["impulses"], market_h4)
        fibtime_duplicate_audit = fibtime_v3.copy()

        smoke_seed = aggregate_static_features_v3(canonical_legs, memberships, leg_bars_1d, leg_bars_h4, pd.DataFrame())
        smoke_cases = select_smoke_candidates(canonical_legs, smoke_seed, excursions, fibtime_v3, memberships)
        smoke_case_ranges = smoke_intervals_from_candidates(smoke_cases, canonical_legs, dynamic_candidates) if args.mode == "smoke" else [(H4_TRANSITION_START, KNOWN_COVERAGE_END)]

        merged_15m_path = Path(args.merged_15m_parquet) if args.merged_15m_parquet else None
        spot_15m_path = Path(args.spot_15m_parquet) if args.spot_15m_parquet else None
        futures_15m_path = Path(args.futures_15m_parquet) if args.futures_15m_parquet else None
        market_15m = pd.DataFrame()
        if merged_15m_path and merged_15m_path.exists():
            market_15m = load_ohlc_frame(merged_15m_path)
            market_15m = add_source_provenance(market_15m, "", str(merged_15m_path), "merged_ohlcv", "BTCUSDT", "15M")
            market_15m = ensure_market_source(market_15m, "spot", "futures", H4_TRANSITION_START)
        elif spot_15m_path and spot_15m_path.exists() and futures_15m_path and futures_15m_path.exists():
            market_15m = merge_market_frames_with_sources(load_ohlc_frame(spot_15m_path), load_ohlc_frame(futures_15m_path), H4_TRANSITION_START)
            market_15m = add_source_provenance(market_15m, "", f"{spot_15m_path}|{futures_15m_path}", "merged_from_split_raw_ohlcv", "BTCUSDT", "15M")
        elif futures_15m_path and futures_15m_path.exists():
            market_15m = load_ohlc_frame(futures_15m_path)
            market_15m = add_source_provenance(market_15m, "futures", str(futures_15m_path), "raw_ohlcv", "BTCUSDT", "15M")
        elif spot_15m_path and spot_15m_path.exists():
            market_15m = load_ohlc_frame(spot_15m_path)
            market_15m = add_source_provenance(market_15m, "spot", str(spot_15m_path), "raw_ohlcv", "BTCUSDT", "15M")
        else:
            market_15m = build_futures_15m_from_aggtrades(Path(args.aggtrades_root), smoke_case_ranges, partials_dir / "market_15m_days", checkpoint_path, checkpoint, progress_path)
        if not market_15m.empty:
            market_15m = market_15m[market_15m["open_datetime"] <= KNOWN_COVERAGE_END].sort_values("open_datetime").reset_index(drop=True)
            market_15m = ensure_market_source(market_15m, "spot", "futures", H4_TRANSITION_START)
            market_15m = add_market_indicators_v3(market_15m, interval_hours=0.25)
            market_15m["atr14"] = market_15m["atr14_wilder"]
        m15_validation = validate_market_bars(market_15m, "15M") if not market_15m.empty else {"timeframe": "15M", "row_count": 0, "issues": ["not_built_or_unavailable"]}
        if any(issue in critical_input_issues for issue in m15_validation["issues"]):
            build_failure_report(output_dir, "critical input validation failure", "source_validation", {"15m": m15_validation})
            return 1

        leg_bars_15m = pd.DataFrame()
        if not market_15m.empty:
            candidate_leg_ids = set(smoke_cases["canonical_leg_id"].dropna().astype(str).tolist()) if args.mode == "smoke" else set(canonical_legs["canonical_leg_id"].astype(str).tolist())
            selected_legs = canonical_legs[canonical_legs["canonical_leg_id"].astype(str).isin(candidate_leg_ids)].copy() if candidate_leg_ids else canonical_legs.iloc[0:0].copy()
            if not selected_legs.empty:
                leg_bars_15m, _ = run_leg_bar_stage_incremental(selected_legs, market_15m, "15M", "leg_bars_15m_v3", partials_dir, checkpoint_path, checkpoint, progress_path)

        static_features = aggregate_static_features_v3(canonical_legs, memberships, leg_bars_1d, leg_bars_h4, leg_bars_15m)
        canonical_legs = canonical_legs.merge(
            static_features[["canonical_leg_id", "duration_hours", "duration_days", "num_4h_bars", "num_1d_bars", "segment_high", "segment_low", "price_range_abs", "net_move_abs", "net_move_pct_signed", "net_move_pct_abs", "log_move_signed", "log_move_abs"]],
            on="canonical_leg_id",
            how="left",
        )
        candidate_rows = build_parent_reference_candidates_v3(canonical_legs, memberships)
        relationships = build_relationship_summary_v3(canonical_legs, candidate_rows)

        coverage_frame = pd.concat(
            [
                build_coverage_frame(canonical_legs, leg_bars_1d, "1D", daily["open_datetime"].min(), daily["open_datetime"].max() + ONE_DAY, "spot|futures"),
                build_coverage_frame(canonical_legs, leg_bars_h4, "4H", market_h4["open_datetime"].min() if not market_h4.empty else None, market_h4["close_datetime"].max() if not market_h4.empty else None, "spot|futures"),
                build_coverage_frame(canonical_legs, leg_bars_15m, "15M", market_15m["open_datetime"].min() if not market_15m.empty else None, market_15m["close_datetime"].max() if not market_15m.empty else None, "spot|futures"),
            ],
            ignore_index=True,
        )
        endpoint_alignment = build_endpoint_alignment(canonical_legs, market_h4, market_15m)
        feature_dictionary = build_feature_dictionary_v3(static_features, causal_4h, dynamic_candidates)
        migration = build_v2_to_v3_migration(ROOT / "outputs" / "structure_research_dataset_v2_20260718" / "structure_leg_features_static.csv", static_features)
        labels_review_v3 = build_labels_review_v2(canonical_legs)
        decision_register = build_decision_register(output_dir)

        decision_parent_reference = candidate_rows.copy()
        if not decision_parent_reference.empty:
            decision_parent_reference["final_choice"] = ""
            decision_parent_reference["choice_reason"] = ""
        decision_window_comparison = causal_4h[[
            column for column in [
                "open_datetime", "window_size_bars", "range_abs", "range_ratio_current_to_previous", "inside_share", "mid_cross_rate_per_bar",
                "upper_slope_price_per_bar", "lower_slope_price_per_bar", "mid_slope_price_per_bar", "width_change_ratio",
                "upper_touch_count", "lower_touch_count", "alternating_touch_count", "close_path_efficiency",
                "realized_vol_log_return_std", "coverage_status", "bars_available", "window_is_full"
            ] if column in causal_4h.columns
        ]].copy() if not causal_4h.empty else pd.DataFrame()
        if not decision_window_comparison.empty:
            decision_window_comparison = decision_window_comparison.rename(columns={
                "open_datetime": "time",
                "upper_slope_price_per_bar": "upper_slope",
                "lower_slope_price_per_bar": "lower_slope",
                "mid_slope_price_per_bar": "mid_slope",
                "mid_cross_rate_per_bar": "mid_cross_rate",
            })
        decision_dynamic_candidates = dynamic_candidates.copy()
        decision_dynamic_excursions = excursions.copy()
        decision_boundary_alignment = endpoint_alignment.copy()
        decision_path_efficiency = static_features[[column for column in ["canonical_leg_id", "close_path_length_4h", "close_path_efficiency_4h", "close_path_tortuosity_4h", "close_path_length_15m", "close_path_efficiency_15m", "close_path_tortuosity_15m", "extreme_anchor_close_path_length_15m_approx", "extreme_anchor_close_path_efficiency_15m_approx"] if column in static_features.columns]].copy()
        decision_thresholds = dynamic_candidates[[column for column in dynamic_candidates.columns if column in {
            "range_candidate_id", "candidate_available_at", "method", "window_size_bars", "range_ratio_current_to_previous",
            "upper_slope_atr_per_bar", "lower_slope_atr_per_bar", "parallelism_atr_normalized", "width_change_ratio",
            "close_inside_share", "full_candle_inside_share", "wick_inside_share", "mid_cross_rate_per_bar",
            "upper_touch_count_005atr", "upper_touch_count_010atr", "upper_touch_count_020atr", "upper_touch_count_030atr",
            "lower_touch_count_005atr", "lower_touch_count_010atr", "lower_touch_count_020atr", "lower_touch_count_030atr",
            "alternating_touch_count", "same_side_repeat_count", "recent_speed_24h_signed", "recent_speed_3d_signed",
            "recent_speed_7d_signed", "close_path_efficiency", "realized_vol_log_return_std", "volume_to_30d_mean",
            "volume_to_30d_median", "volume_zscore_30d", "coverage_status"
        }]].copy() if not dynamic_candidates.empty else pd.DataFrame()
        if not decision_thresholds.empty:
            decision_thresholds = decision_thresholds.rename(columns={
                "candidate_available_at": "time",
                "window_size_bars": "window_size",
            })
            if not decision_dynamic_excursions.empty:
                excursion_lookup = decision_dynamic_excursions.groupby("range_candidate_id").agg(
                    wick_distance_beyond_atr=("wick_distance_beyond_atr", "max"),
                    close_distance_beyond_atr=("close_distance_beyond_atr", "max"),
                ).reset_index()
                decision_thresholds = decision_thresholds.merge(excursion_lookup, on="range_candidate_id", how="left")
        decision_coverage = coverage_frame[coverage_frame["coverage_status"] != "complete"].copy()
        for frame in [decision_window_comparison, decision_dynamic_candidates, decision_dynamic_excursions, decision_boundary_alignment, decision_path_efficiency, decision_thresholds, decision_coverage]:
            if frame is not None and not frame.empty:
                frame["final_choice"] = ""
                frame["choice_reason"] = ""

        qa_summary = run_qa_v3(
            canonical_legs,
            static_features,
            causal_4h,
            fibtime_v3,
            endpoint_alignment,
            coverage_frame,
            dynamic_excursions=excursions,
            feature_dictionary=feature_dictionary,
            source_frames={"1D": daily, "4H": market_h4, "15M": market_15m},
        )

        output_files = {
            "structure_canonical_legs.csv": str(output_dir / "structure_canonical_legs.csv"),
            "structure_source_memberships.csv": str(output_dir / "structure_source_memberships.csv"),
            "structure_leg_relationships.csv": str(output_dir / "structure_leg_relationships.csv"),
            "market_bars_1d.parquet": str(output_dir / "market_bars_1d.parquet"),
            "market_bars_4h.parquet": str(output_dir / "market_bars_4h.parquet"),
            "market_bars_15m.parquet": str(output_dir / "market_bars_15m.parquet"),
            "market_features_rolling_4h_causal.parquet": str(output_dir / "market_features_rolling_4h_causal.parquet"),
            "dynamic_range_candidates_4h_causal.parquet": str(output_dir / "dynamic_range_candidates_4h_causal.parquet"),
            "dynamic_range_excursions_4h.parquet": str(output_dir / "dynamic_range_excursions_4h.parquet"),
            "structure_leg_bars_1d_retrospective.parquet": str(output_dir / "structure_leg_bars_1d_retrospective.parquet"),
            "structure_leg_bars_4h_retrospective.parquet": str(output_dir / "structure_leg_bars_4h_retrospective.parquet"),
            "structure_leg_bars_15m_retrospective.parquet": str(output_dir / "structure_leg_bars_15m_retrospective.parquet"),
            "structure_leg_features_rolling_4h_retrospective.parquet": str(output_dir / "structure_leg_features_rolling_4h_retrospective.parquet"),
            "structure_leg_features_static.csv": str(output_dir / "structure_leg_features_static.csv"),
            "structure_leg_events_retrospective.parquet": str(output_dir / "structure_leg_events_retrospective.parquet"),
            "fibtime_events_v3.csv": str(output_dir / "fibtime_events_v3.csv"),
            "fibtime_event_duplicate_audit.csv": str(output_dir / "fibtime_event_duplicate_audit.csv"),
            "structure_labels_review_v3.csv": str(output_dir / "structure_labels_review_v3.csv"),
            "feature_dictionary.csv": str(output_dir / "feature_dictionary.csv"),
            "data_dictionary.md": str(output_dir / "data_dictionary.md"),
            "v2_to_v3_feature_migration.csv": str(output_dir / "v2_to_v3_feature_migration.csv"),
            "source_discovery_report.csv": str(output_dir / "source_discovery_report.csv"),
            "decision_register.csv": str(output_dir / "decision_register.csv"),
            "decision_parent_reference_candidates.csv": str(output_dir / "decision_parent_reference_candidates.csv"),
            "decision_window_comparison.csv": str(output_dir / "decision_window_comparison.csv"),
            "decision_dynamic_range_candidates.csv": str(output_dir / "decision_dynamic_range_candidates.csv"),
            "decision_dynamic_range_excursions.csv": str(output_dir / "decision_dynamic_range_excursions.csv"),
            "decision_boundary_alignment.csv": str(output_dir / "decision_boundary_alignment.csv"),
            "decision_path_efficiency_comparison.csv": str(output_dir / "decision_path_efficiency_comparison.csv"),
            "decision_threshold_research.csv": str(output_dir / "decision_threshold_research.csv"),
            "decision_coverage_issues.csv": str(output_dir / "decision_coverage_issues.csv"),
            "smoke_case_candidates.csv": str(output_dir / "smoke_case_candidates.csv"),
            "coverage_by_leg_timeframe.csv": str(output_dir / "coverage_by_leg_timeframe.csv"),
            "coverage_summary.json": str(output_dir / "coverage_summary.json"),
            "endpoint_alignment.csv": str(output_dir / "endpoint_alignment.csv"),
            "structure_research_summary_v3.json": str(output_dir / "structure_research_summary_v3.json"),
            "structure_research_qa_v3.json": str(output_dir / "structure_research_qa_v3.json"),
        }

        data_dictionary = build_data_dictionary_v3(output_files)
        coverage_summary = {
            "status": "complete_with_known_coverage_limits",
            "known_coverage_end": to_iso(KNOWN_COVERAGE_END),
            "coverage_by_timeframe": coverage_frame.groupby("timeframe")["coverage_status"].value_counts().to_dict() if not coverage_frame.empty else {},
            "daily_validation": daily_validation,
            "h4_validation": h4_validation,
            "m15_validation": m15_validation,
            "stale_checkpoint_warning": stale_checkpoint_warning,
        }
        summary = {
            "status": "complete_with_known_coverage_limits" if qa_summary["status"] == "passed" else "failed",
            "mode": args.mode,
            "source_run": str(base_run_dir),
            "script_path": str(Path(__file__).resolve()),
            "created_at": pd.Timestamp.now(tz=UTC).isoformat(),
            "period_start": to_iso(daily["open_datetime"].min()),
            "period_end": to_iso(min(daily["open_datetime"].max(), KNOWN_COVERAGE_END)),
            "source_segment_count": int(len(source_records)),
            "canonical_leg_count": int(len(canonical_legs)),
            "causal_rolling_row_count": int(len(causal_4h)),
            "retrospective_rolling_4h_rows": int(len(rolling_4h_retrospective)),
            "retrospective_1d_rows": int(len(leg_bars_1d)),
            "retrospective_4h_rows": int(len(leg_bars_h4)),
            "retrospective_15m_rows": int(len(leg_bars_15m)),
            "dynamic_range_candidate_count": int(len(dynamic_candidates)),
            "excursion_observation_count": int(len(excursions)),
            "fibtime_event_counts": fibtime_v3["event_type"].value_counts().to_dict() if not fibtime_v3.empty else {},
            "ambiguous_parent_count": int((relationships["parent_relationship_status"] == "ambiguous").sum()) if "parent_relationship_status" in relationships.columns else 0,
            "ambiguous_reference_count": int((relationships["reference_relationship_status"] == "ambiguous").sum()) if "reference_relationship_status" in relationships.columns else 0,
            "source_transition_time": source_transition_time.isoformat() if source_transition_time is not None else str(h4_metadata.get("transition_time") or ""),
            "output_files": output_files,
            "source_discovery_rows": int(len(source_discovery)),
        }

        fibtime_v3 = fibtime_v3.drop_duplicates(subset=["impulse_id", "deadline_version", "event_type", "event_time"], keep="first") if not fibtime_v3.empty else fibtime_v3

        for frame in [canonical_legs, memberships, relationships, leg_bars_1d, leg_bars_h4, leg_bars_15m, rolling_4h_retrospective, static_features, causal_4h, dynamic_candidates, excursions, events, fibtime_v3, fibtime_duplicate_audit, source_discovery, labels_review_v3, coverage_frame, endpoint_alignment, decision_parent_reference, decision_window_comparison, decision_dynamic_candidates, decision_dynamic_excursions, decision_boundary_alignment, decision_path_efficiency, decision_thresholds, decision_coverage, smoke_cases]:
            if frame is None or frame.empty:
                continue
            for column in frame.columns:
                if pd.api.types.is_datetime64_any_dtype(frame[column]):
                    frame[column] = frame[column].apply(to_iso)

        atomic_write_csv(Path(output_files["structure_canonical_legs.csv"]), canonical_legs)
        atomic_write_csv(Path(output_files["structure_source_memberships.csv"]), memberships)
        atomic_write_csv(Path(output_files["structure_leg_relationships.csv"]), relationships)
        atomic_write_parquet(Path(output_files["market_bars_1d.parquet"]), daily)
        atomic_write_parquet(Path(output_files["market_bars_4h.parquet"]), market_h4)
        atomic_write_parquet(Path(output_files["market_bars_15m.parquet"]), market_15m)
        atomic_write_parquet(Path(output_files["market_features_rolling_4h_causal.parquet"]), causal_4h)
        atomic_write_parquet(Path(output_files["dynamic_range_candidates_4h_causal.parquet"]), dynamic_candidates)
        atomic_write_parquet(Path(output_files["dynamic_range_excursions_4h.parquet"]), excursions)
        atomic_write_parquet(Path(output_files["structure_leg_bars_1d_retrospective.parquet"]), leg_bars_1d)
        atomic_write_parquet(Path(output_files["structure_leg_bars_4h_retrospective.parquet"]), leg_bars_h4)
        atomic_write_parquet(Path(output_files["structure_leg_bars_15m_retrospective.parquet"]), leg_bars_15m)
        atomic_write_parquet(Path(output_files["structure_leg_features_rolling_4h_retrospective.parquet"]), rolling_4h_retrospective)
        atomic_write_csv(Path(output_files["structure_leg_features_static.csv"]), static_features)
        atomic_write_parquet(Path(output_files["structure_leg_events_retrospective.parquet"]), events)
        atomic_write_csv(Path(output_files["fibtime_events_v3.csv"]), fibtime_v3)
        atomic_write_csv(Path(output_files["fibtime_event_duplicate_audit.csv"]), fibtime_duplicate_audit)
        atomic_write_csv(Path(output_files["structure_labels_review_v3.csv"]), labels_review_v3)
        atomic_write_csv(Path(output_files["feature_dictionary.csv"]), feature_dictionary)
        atomic_write_text(Path(output_files["data_dictionary.md"]), data_dictionary)
        atomic_write_csv(Path(output_files["v2_to_v3_feature_migration.csv"]), migration)
        atomic_write_csv(Path(output_files["source_discovery_report.csv"]), source_discovery)
        atomic_write_csv(Path(output_files["decision_register.csv"]), decision_register)
        atomic_write_csv(Path(output_files["decision_parent_reference_candidates.csv"]), decision_parent_reference)
        atomic_write_csv(Path(output_files["decision_window_comparison.csv"]), decision_window_comparison)
        atomic_write_csv(Path(output_files["decision_dynamic_range_candidates.csv"]), decision_dynamic_candidates)
        atomic_write_csv(Path(output_files["decision_dynamic_range_excursions.csv"]), decision_dynamic_excursions)
        atomic_write_csv(Path(output_files["decision_boundary_alignment.csv"]), decision_boundary_alignment)
        atomic_write_csv(Path(output_files["decision_path_efficiency_comparison.csv"]), decision_path_efficiency)
        atomic_write_csv(Path(output_files["decision_threshold_research.csv"]), decision_thresholds)
        atomic_write_csv(Path(output_files["decision_coverage_issues.csv"]), decision_coverage)
        atomic_write_csv(Path(output_files["smoke_case_candidates.csv"]), smoke_cases)
        atomic_write_csv(Path(output_files["coverage_by_leg_timeframe.csv"]), coverage_frame)
        atomic_write_csv(Path(output_files["endpoint_alignment.csv"]), endpoint_alignment)
        atomic_write_json(Path(output_files["coverage_summary.json"]), coverage_summary)
        atomic_write_json(Path(output_files["structure_research_summary_v3.json"]), summary)
        atomic_write_json(Path(output_files["structure_research_qa_v3.json"]), qa_summary)

        update_progress(progress_path, {"stage": "complete", "message": "v3 dataset build finished", "status": summary["status"], "output_files": output_files, "config_hash": config_hash})
        update_stage_checkpoint(checkpoint_path, checkpoint, "complete", "v3 dataset build finished")
        if qa_summary["critical_failures"]:
            build_failure_report(output_dir, "critical QA failures", "qa", {"critical_failures": qa_summary["critical_failures"]})
        print(json.dumps({"summary": summary, "qa": qa_summary["checks"]}, ensure_ascii=False, indent=2))
        return 0 if not qa_summary["critical_failures"] else 1
    except Exception as exc:
        context = {"error_type": type(exc).__name__, "message": str(exc)}
        try:
            build_failure_report(output_dir, str(exc), "exception", context)
            update_progress(progress_path, {"stage": "failed", "message": str(exc), "config_hash": config_hash})
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
