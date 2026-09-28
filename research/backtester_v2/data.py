import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .models import Bar
from research.btc_macro_nautilus.canonical_candles.build_canonical_futures_candles import (
    iter_source_rows,
)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _utc_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def iter_canonical_1m_bars(
    manifest_path: Path,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> Iterator[Bar]:
    manifest = load_manifest(manifest_path)
    dataset = manifest["dataset"]
    dataset_start = _utc_ms(dataset["strict_start_utc"])
    dataset_end = _utc_ms(dataset["strict_end_utc"])
    lo = dataset_start if start_ms is None else int(start_ms)
    hi = dataset_end if end_ms is None else int(end_ms)
    if lo > hi:
        raise ValueError("start_ms must be <= end_ms")

    windows = None
    if start_ms is not None or end_ms is not None:
        windows = [(lo, hi)]

    for row in iter_source_rows(manifest, windows=windows):
        yield Bar(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
