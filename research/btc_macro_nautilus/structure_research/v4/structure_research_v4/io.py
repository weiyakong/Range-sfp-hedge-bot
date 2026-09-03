from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


UTC = "UTC"
REQUIRED_OHLCV_COLUMNS = [
    "open_datetime",
    "close_datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_times(frame: pd.DataFrame) -> pd.DataFrame:
    for column in frame.columns:
        lowered = column.lower()
        if "time" in lowered or lowered.endswith("_at") or lowered.endswith("_datetime"):
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    return frame


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    return parse_times(frame)


def save_table(frame: pd.DataFrame, path: Path) -> None:
    ensure_directory(path.parent)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def save_json(payload: dict, path: Path) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def concat_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame()
    return pd.concat(valid, ignore_index=True)


def normalize_15m_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["open_datetime"] = pd.to_datetime(frame["start"], utc=True, errors="coerce", format="mixed")
    frame["close_datetime"] = pd.to_datetime(frame["end"], utc=True, errors="coerce", format="mixed")
    frame["interval"] = "15m"
    return frame[
        [
            "interval",
            "open_datetime",
            "close_datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trade_count",
        ]
    ].copy()
