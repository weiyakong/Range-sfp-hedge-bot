from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .io import REQUIRED_OHLCV_COLUMNS, load_table


DERIVED_PREFIX = "market_regime_features_15m_w"


@dataclass(frozen=True)
class SourceDescriptor:
    path: Path
    timeframe: str
    market_type: str
    source_type: str


def read_manifest(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "file" not in frame.columns:
        for candidate in ["path", "file_path", "parquet_path"]:
            if candidate in frame.columns:
                frame["file"] = frame[candidate]
                break
    return frame


def read_schema(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "column" not in frame.columns and "column_name" in frame.columns:
        frame["column"] = frame["column_name"]
    return frame


def classify_source(path: Path, timeframe: str) -> tuple[str, bool, str]:
    name = path.name
    if DERIVED_PREFIX in name:
        return "derived_feature", False, "derived_feature_parquet"
    if not path.exists():
        return "missing", False, "missing_path"
    frame = load_table(path)
    required = set(REQUIRED_OHLCV_COLUMNS).issubset(frame.columns)
    if not required:
        return "invalid_raw", False, "missing_required_column"
    interval = str(frame.get("interval", pd.Series([timeframe])).iloc[0]).lower()
    if timeframe not in interval:
        return "invalid_raw", False, "timeframe_mismatch"
    return "raw_ohlcv", True, ""


def build_source_discovery_report(
    manifest: pd.DataFrame,
    schema: pd.DataFrame,
    descriptors: list[SourceDescriptor],
) -> pd.DataFrame:
    rows: list[dict] = []
    manifest_dir = Path(".")
    for descriptor in descriptors:
        if descriptor.path.is_absolute():
            resolved = descriptor.path
        else:
            resolved = manifest_dir / descriptor.path
        classified_as, accepted, rejection = classify_source(resolved, descriptor.timeframe)
        source_start = pd.NaT
        source_end = pd.NaT
        row_count = 0
        required_columns_present = False
        if resolved.exists() and accepted:
            frame = load_table(resolved)
            required_columns_present = set(REQUIRED_OHLCV_COLUMNS).issubset(frame.columns)
            source_start = frame["open_datetime"].min()
            source_end = frame["close_datetime"].max()
            row_count = len(frame)
        rows.append(
            {
                "path": str(resolved),
                "exists": resolved.exists(),
                "timeframe": descriptor.timeframe,
                "market_type": descriptor.market_type,
                "required_columns_present": required_columns_present,
                "classified_as": classified_as,
                "accepted": accepted,
                "rejection_reason": rejection,
                "source_start": source_start,
                "source_end": source_end,
                "row_count": row_count,
            }
        )
    return pd.DataFrame(rows)


def validate_source_bars(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues: list[str] = []
    ordered = frame.copy()
    if ordered.empty:
        issues.append("empty_market_source")
        return ordered, issues
    if ordered["open_datetime"].duplicated().any():
        issues.append("duplicate_open_datetime")
    if not ordered["open_datetime"].is_monotonic_increasing:
        issues.append("non_monotonic_open_datetime")
    if (ordered["close_datetime"] <= ordered["open_datetime"]).any():
        issues.append("close_not_after_open")
    if (ordered["high"] < ordered[["open", "close"]].max(axis=1)).any():
        issues.append("high_below_open_or_close")
    if (ordered["low"] > ordered[["open", "close"]].min(axis=1)).any():
        issues.append("low_above_open_or_close")
    if (ordered["high"] < ordered["low"]).any():
        issues.append("high_below_low")
    if (ordered["volume"] < 0).any():
        issues.append("negative_volume")
    ordered = ordered.sort_values("open_datetime").reset_index(drop=True)
    return ordered, issues


def compute_gap_metrics(frame: pd.DataFrame, expected_hours: int) -> tuple[int, float]:
    if len(frame) < 2:
        return 0, float(expected_hours)
    diffs = frame["open_datetime"].diff().dropna().dt.total_seconds() / 3600.0
    gap_count = int((diffs > expected_hours * 1.5).sum())
    return gap_count, float(diffs.median()) if not diffs.empty else float(expected_hours)
