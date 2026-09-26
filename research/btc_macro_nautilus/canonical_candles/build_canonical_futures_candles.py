#!/usr/bin/env python3
"""Build and validate canonical BTCUSDT futures candles from strict 1-minute data."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import pyarrow as pa
import pyarrow.parquet as pq


AGGREGATION_VERSION = "strict-1m-direct-v1"
SCHEMA_VERSION = "canonical-futures-candles-v1"
MARKET = "binance_usdt_m_futures"
INSTRUMENT = "BTCUSDT"
MINUTE_MS = 60_000
KNOWN_GAP_MS = 1_567_970_400_000  # 2019-09-08T19:00:00Z
NUMERIC_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)
ADDITIVE_FIELDS = (
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)
TIMEFRAMES = {
    "4h": 240,
    "12h": 720,
    "1d": 1440,
}
RAW_FIELDS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)


def utc_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    partial = path.with_name(path.name + ".partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def month_starts(start_ms: int, end_ms: int) -> Iterator[datetime]:
    current = datetime.fromtimestamp(start_ms / 1000, timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    while current <= end:
        yield current
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def day_starts(start_ms: int, end_ms: int) -> Iterator[datetime]:
    current = datetime.fromtimestamp(start_ms / 1000, timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    while current <= end:
        yield current
        current += timedelta(days=1)


def expand_segment_files(segment: dict) -> list[Path]:
    if "path" in segment:
        return [Path(segment["path"])]
    pattern = segment["path_pattern"]
    start_ms = parse_utc(segment["start_utc"])
    end_ms = parse_utc(segment["end_utc"])
    if "YYYY-MM" in pattern:
        return [Path(pattern.replace("YYYY-MM", dt.strftime("%Y-%m"))) for dt in month_starts(start_ms, end_ms)]
    if "DD" in pattern:
        return [Path(pattern.replace("DD", dt.strftime("%d"))) for dt in day_starts(start_ms, end_ms)]
    brace = re.search(r"\{([^{}]+)\}", pattern)
    if brace:
        return [Path(pattern[: brace.start()] + value + pattern[brace.end() :]) for value in brace.group(1).split(",")]
    raise ValueError(f"Unsupported manifest path pattern: {pattern}")


def segment_bounds(segment: dict) -> tuple[int, int]:
    start = segment.get("selection_start_utc", segment.get("start_utc"))
    end = segment.get("selection_end_utc", segment.get("end_utc"))
    return parse_utc(start), parse_utc(end)


def file_bounds(path: Path, fallback: tuple[int, int]) -> tuple[int, int]:
    match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", path.name)
    if match:
        start = datetime(*map(int, match.groups()), tzinfo=timezone.utc)
        return int(start.timestamp() * 1000), int((start + timedelta(days=1)).timestamp() * 1000) - MINUTE_MS
    match = re.search(r"(20\d{2})-(\d{2})", path.name)
    if match:
        year, month = map(int, match.groups())
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return int(start.timestamp() * 1000), int(next_month.timestamp() * 1000) - MINUTE_MS
    return fallback


def row_from_sequence(values: Sequence[object]) -> tuple:
    return (
        int(values[0]),
        float(values[1]),
        float(values[2]),
        float(values[3]),
        float(values[4]),
        float(values[5]),
        float(values[7]),
        int(values[8]),
        float(values[9]),
        float(values[10]),
    )


def read_zip(path: Path) -> Iterator[tuple]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"Expected one data member in {path}, got {members}")
        with archive.open(members[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
            for values in csv.reader(text):
                if not values or not values[0].isdigit():
                    continue
                yield row_from_sequence(values)


def read_gzip_csv(path: Path) -> Iterator[tuple]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            yield (
                int(row["open_time"]),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
                float(row["quote_volume"]),
                int(row["trade_count"]),
                float(row.get("taker_buy_base_volume", row.get("taker_buy_volume"))),
                float(row["taker_buy_quote_volume"]),
            )


def read_parquet(path: Path) -> Iterator[tuple]:
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=100_000, columns=columns):
        values = batch.to_pydict()
        for index in range(batch.num_rows):
            yield tuple(values[column][index] for column in columns)


def read_json(path: Path) -> Iterator[tuple]:
    with path.open(encoding="utf-8") as handle:
        for values in json.load(handle):
            yield row_from_sequence(values)


def read_file(path: Path, source_format: str) -> Iterator[tuple]:
    if source_format == "parquet":
        yield from read_parquet(path)
    elif source_format == "zip/csv":
        yield from read_zip(path)
    elif source_format == "csv.gz":
        yield from read_gzip_csv(path)
    elif source_format == "json":
        yield from read_json(path)
    else:
        raise ValueError(f"Unsupported source format: {source_format}")


def iter_source_rows(
    manifest: dict, windows: Sequence[tuple[int, int]] | None = None
) -> Iterator[tuple]:
    for segment in manifest["logical_source_chain"]:
        selection_start, selection_end = segment_bounds(segment)
        for path in expand_segment_files(segment):
            if not path.is_file():
                raise FileNotFoundError(path)
            coarse_start, coarse_end = file_bounds(path, (selection_start, selection_end))
            if windows and not any(coarse_start <= end and coarse_end >= start for start, end in windows):
                continue
            for row in read_file(path, segment["format"]):
                timestamp = int(row[0])
                if timestamp < selection_start or timestamp > selection_end:
                    continue
                if windows and not any(start <= timestamp <= end for start, end in windows):
                    continue
                yield row


def bucket_start_ms(timestamp_ms: int, expected_count: int) -> int:
    duration_ms = expected_count * MINUTE_MS
    return timestamp_ms // duration_ms * duration_ms


@dataclass
class CandleAccumulator:
    resolution: str
    expected_count: int
    source_start_ms: int
    known_gaps_ms: set[int]
    rows: list[dict]
    current: dict | None = None
    first_constituent_ms: int | None = None
    last_constituent_ms: int | None = None

    def add(self, source: tuple) -> None:
        timestamp = int(source[0])
        bucket = bucket_start_ms(timestamp, self.expected_count)
        if self.current is None or bucket != self.current["start_time_ms"]:
            if self.current is not None:
                self.flush()
            self.current = {
                "start_time_ms": bucket,
                "end_time_ms": bucket + self.expected_count * MINUTE_MS,
                "open": float(source[1]),
                "high": float(source[2]),
                "low": float(source[3]),
                "close": float(source[4]),
                "volume": float(source[5]),
                "quote_volume": float(source[6]),
                "trade_count": int(source[7]),
                "taker_buy_base_volume": float(source[8]),
                "taker_buy_quote_volume": float(source[9]),
                "constituent_count": 1,
            }
            self.first_constituent_ms = timestamp
            self.last_constituent_ms = timestamp
            return
        current = self.current
        current["high"] = max(current["high"], float(source[2]))
        current["low"] = min(current["low"], float(source[3]))
        current["close"] = float(source[4])
        current["volume"] += float(source[5])
        current["quote_volume"] += float(source[6])
        current["trade_count"] += int(source[7])
        current["taker_buy_base_volume"] += float(source[8])
        current["taker_buy_quote_volume"] += float(source[9])
        current["constituent_count"] += 1
        self.last_constituent_ms = timestamp

    def flush(self) -> None:
        if self.current is None:
            return
        current = self.current
        start = current["start_time_ms"]
        end = current["end_time_ms"]
        complete = (
            current["constituent_count"] == self.expected_count
            and self.first_constituent_ms == start
            and self.last_constituent_ms == end - MINUTE_MS
        )
        reasons = []
        if start < self.source_start_ms:
            reasons.append("dataset_start")
        if any(start <= gap < end for gap in self.known_gaps_ms):
            reasons.append("known_gap:2019-09-08T19:00:00Z")
        if not complete and not reasons:
            raise ValueError(
                f"Unexplained incomplete {self.resolution} interval {utc_iso(start)}: "
                f"{current['constituent_count']}/{self.expected_count}"
            )
        current.update(
            {
                "expected_constituent_count": self.expected_count,
                "complete": complete,
                "incomplete_reason": ";".join(reasons) if reasons else None,
                "market": MARKET,
                "instrument": INSTRUMENT,
                "resolution": self.resolution,
            }
        )
        self.rows.append(current)
        self.current = None
        self.first_constituent_ms = None
        self.last_constituent_ms = None


ARROW_SCHEMA = pa.schema(
    [
        pa.field("start_time", pa.timestamp("ms", tz="UTC"), nullable=False),
        pa.field("end_time", pa.timestamp("ms", tz="UTC"), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.float64(), nullable=False),
        pa.field("quote_volume", pa.float64(), nullable=False),
        pa.field("trade_count", pa.int64(), nullable=False),
        pa.field("taker_buy_base_volume", pa.float64(), nullable=False),
        pa.field("taker_buy_quote_volume", pa.float64(), nullable=False),
        pa.field("constituent_count", pa.int32(), nullable=False),
        pa.field("expected_constituent_count", pa.int32(), nullable=False),
        pa.field("complete", pa.bool_(), nullable=False),
        pa.field("incomplete_reason", pa.string()),
        pa.field("market", pa.string(), nullable=False),
        pa.field("instrument", pa.string(), nullable=False),
        pa.field("resolution", pa.string(), nullable=False),
    ]
)


def rows_to_table(rows: Sequence[dict]) -> pa.Table:
    columns = {name: [] for name in ARROW_SCHEMA.names}
    for row in rows:
        for name in ARROW_SCHEMA.names:
            if name == "start_time":
                value = datetime.fromtimestamp(row["start_time_ms"] / 1000, timezone.utc)
            elif name == "end_time":
                value = datetime.fromtimestamp(row["end_time_ms"] / 1000, timezone.utc)
            else:
                value = row[name]
            columns[name].append(value)
    return pa.Table.from_pydict(columns, schema=ARROW_SCHEMA)


def write_timeframe(
    rows: list[dict],
    resolution: str,
    output_root: Path,
    source_manifest_path: Path,
    source_manifest_sha: str,
    source_manifest: dict,
    repo_root: Path,
    build_timestamp: str,
) -> dict:
    final_dir = output_root / resolution
    if final_dir.exists():
        existing_manifest = final_dir / "manifest.json"
        if existing_manifest.is_file():
            existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
            if existing.get("source_manifest_sha256") == source_manifest_sha:
                checksums_valid = all(
                    Path(item["path"]).is_file() and sha256_file(Path(item["path"])) == item["sha256"]
                    for item in existing.get("output_files", [])
                )
                if checksums_valid:
                    return {"status": "reused", "manifest": existing}
        raise FileExistsError(f"Existing output is not a validated reusable build: {final_dir}")

    temp_dir = output_root / f".{resolution}.build-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True)
    output_files = []
    try:
        years = sorted({datetime.fromtimestamp(row["start_time_ms"] / 1000, timezone.utc).year for row in rows})
        for year in years:
            year_rows = [
                row
                for row in rows
                if datetime.fromtimestamp(row["start_time_ms"] / 1000, timezone.utc).year == year
            ]
            temp_file = temp_dir / f"part-{year}.parquet"
            pq.write_table(
                rows_to_table(year_rows),
                temp_file,
                compression="zstd",
                compression_level=9,
                use_dictionary=["market", "instrument", "resolution", "incomplete_reason"],
                write_statistics=True,
            )
            final_file = final_dir / temp_file.name
            output_files.append(
                {
                    "path": str(final_file),
                    "year": year,
                    "rows": len(year_rows),
                    "bytes": temp_file.stat().st_size,
                    "sha256": sha256_file(temp_file),
                }
            )

        complete = sum(bool(row["complete"]) for row in rows)
        derived_manifest = {
            "schema_version": SCHEMA_VERSION,
            "aggregation_version": AGGREGATION_VERSION,
            "build_timestamp_utc": build_timestamp,
            "market": MARKET,
            "instrument": INSTRUMENT,
            "resolution": resolution,
            "source_manifest_path": str(source_manifest_path),
            "source_manifest_sha256": source_manifest_sha,
            "source_coverage": {
                "start_utc": source_manifest["dataset"]["strict_start_utc"],
                "end_utc": source_manifest["dataset"]["strict_end_utc"],
                "observed_rows": source_manifest["dataset"]["observed_rows"],
            },
            "output_coverage": {
                "start_utc": utc_iso(rows[0]["start_time_ms"]),
                "end_utc_exclusive": utc_iso(rows[-1]["end_time_ms"]),
            },
            "total_rows": len(rows),
            "complete_rows": complete,
            "incomplete_rows": len(rows) - complete,
            "known_gaps": source_manifest["dataset"]["known_real_gaps"],
            "partitioning": "year",
            "parquet_compression": "zstd",
            "output_files": output_files,
            "code_version": {
                "git_commit_at_build": git_commit(repo_root),
                "pipeline_sha256": sha256_file(Path(__file__)),
            },
        }
        atomic_json(temp_dir / "manifest.json", derived_manifest)
        output_root.mkdir(parents=True, exist_ok=True)
        os.replace(temp_dir, final_dir)
        return {"status": "built", "manifest": derived_manifest}
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def read_derived(tf_dir: Path) -> list[dict]:
    files = sorted(tf_dir.glob("part-*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Parquet partitions in {tf_dir}")
    table = pq.read_table(files)
    result = []
    for row in table.to_pylist():
        row["start_time_ms"] = int(row.pop("start_time").timestamp() * 1000)
        row["end_time_ms"] = int(row.pop("end_time").timestamp() * 1000)
        result.append(row)
    return result


def structural_qa(rows: list[dict], resolution: str, expected: int, source_end_ms: int) -> dict:
    starts = [row["start_time_ms"] for row in rows]
    duration = expected * MINUTE_MS
    errors = []
    if starts != sorted(starts):
        errors.append("non_monotonic")
    if len(starts) != len(set(starts)):
        errors.append("duplicates")
    if any(start % duration for start in starts):
        errors.append("off_grid")
    for row in rows:
        numeric = [float(row[field]) for field in NUMERIC_FIELDS]
        if not all(math.isfinite(value) for value in numeric):
            errors.append(f"non_finite:{utc_iso(row['start_time_ms'])}")
        if row["high"] < max(row["open"], row["close"]) or row["low"] > min(row["open"], row["close"]):
            errors.append(f"invalid_ohlc:{utc_iso(row['start_time_ms'])}")
        if row["high"] < row["low"]:
            errors.append(f"high_below_low:{utc_iso(row['start_time_ms'])}")
        if row["volume"] < 0 or row["quote_volume"] < 0 or row["trade_count"] < 0:
            errors.append(f"negative_additive:{utc_iso(row['start_time_ms'])}")
        if row["complete"] and row["constituent_count"] != expected:
            errors.append(f"bad_complete_count:{utc_iso(row['start_time_ms'])}")
        if not row["complete"] and not row["incomplete_reason"]:
            errors.append(f"unexplained_incomplete:{utc_iso(row['start_time_ms'])}")
    last_expected = bucket_start_ms(source_end_ms, expected)
    if starts[-1] != last_expected:
        errors.append("missing_last_interval")
    if not rows[-1]["complete"]:
        errors.append("last_interval_incomplete")
    return {
        "resolution": resolution,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "rows": len(rows),
        "complete": sum(bool(row["complete"]) for row in rows),
        "incomplete": sum(not row["complete"] for row in rows),
    }


def aggregate_selected_rows(
    manifest: dict, selected: dict[str, set[int]]
) -> dict[str, dict[int, dict]]:
    windows = []
    for resolution, starts in selected.items():
        duration = TIMEFRAMES[resolution] * MINUTE_MS
        windows.extend((start, start + duration - MINUTE_MS) for start in starts)
    source_start_ms = parse_utc(manifest["dataset"]["strict_start_utc"])
    accumulators = {
        resolution: {
            start: CandleAccumulator(resolution, TIMEFRAMES[resolution], source_start_ms, {KNOWN_GAP_MS}, [])
            for start in starts
        }
        for resolution, starts in selected.items()
    }
    for row in iter_source_rows(manifest, windows):
        timestamp = int(row[0])
        for resolution, expected in TIMEFRAMES.items():
            start = bucket_start_ms(timestamp, expected)
            target = accumulators[resolution].get(start)
            if target is not None:
                target.add(row)
    result: dict[str, dict[int, dict]] = {}
    for resolution, by_start in accumulators.items():
        result[resolution] = {}
        for start, accumulator in by_start.items():
            accumulator.flush()
            if len(accumulator.rows) != 1:
                raise AssertionError(f"Golden source interval missing: {resolution} {utc_iso(start)}")
            result[resolution][start] = accumulator.rows[0]
    return result


def values_match(left: dict, right: dict, *, tolerant: bool = False) -> bool:
    exact_fields = ("open", "high", "low", "close", "trade_count", "constituent_count")
    if any(left[field] != right[field] for field in exact_fields):
        return False
    for field in ("volume", "quote_volume", "taker_buy_base_volume", "taker_buy_quote_volume"):
        if tolerant:
            if not math.isclose(float(left[field]), float(right[field]), rel_tol=1e-12, abs_tol=1e-8):
                return False
        elif left[field] != right[field]:
            return False
    return True


def golden_qa(manifest: dict, derived: dict[str, list[dict]]) -> dict:
    selected: dict[str, set[int]] = {}
    for resolution, expected in TIMEFRAMES.items():
        selected[resolution] = {
            bucket_start_ms(parse_utc("2020-01-01T00:00:00Z"), expected),
            bucket_start_ms(KNOWN_GAP_MS, expected),
            bucket_start_ms(parse_utc("2024-01-01T00:00:00Z"), expected),
            derived[resolution][-1]["start_time_ms"],
        }
    fresh = aggregate_selected_rows(manifest, selected)
    errors = []
    checks = []
    for resolution, starts in selected.items():
        stored = {row["start_time_ms"]: row for row in derived[resolution]}
        for start in sorted(starts):
            match = values_match(stored[start], fresh[resolution][start])
            checks.append({"resolution": resolution, "start_utc": utc_iso(start), "match": match})
            if not match:
                errors.append(f"{resolution}:{utc_iso(start)}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "checks": checks}


def aggregate_children(children: list[dict], start: int, duration_ms: int) -> dict:
    return {
        "open": children[0]["open"],
        "high": max(row["high"] for row in children),
        "low": min(row["low"] for row in children),
        "close": children[-1]["close"],
        "volume": sum(row["volume"] for row in children),
        "quote_volume": sum(row["quote_volume"] for row in children),
        "trade_count": sum(row["trade_count"] for row in children),
        "taker_buy_base_volume": sum(row["taker_buy_base_volume"] for row in children),
        "taker_buy_quote_volume": sum(row["taker_buy_quote_volume"] for row in children),
        "constituent_count": sum(row["constituent_count"] for row in children),
        "start_time_ms": start,
        "end_time_ms": start + duration_ms,
    }


def cross_timeframe_qa(derived: dict[str, list[dict]]) -> dict:
    errors_4h_12h = []
    errors_12h_1d = []
    by_4h = {row["start_time_ms"]: row for row in derived["4h"]}
    by_12h = {row["start_time_ms"]: row for row in derived["12h"]}
    for parent in derived["12h"]:
        if not parent["complete"]:
            continue
        start = parent["start_time_ms"]
        children = [by_4h.get(start + index * 4 * 60 * MINUTE_MS) for index in range(3)]
        if any(child is None or not child["complete"] for child in children):
            errors_4h_12h.append(f"children:{utc_iso(start)}")
            continue
        aggregate = aggregate_children(children, start, 12 * 60 * MINUTE_MS)
        if not values_match(parent, aggregate, tolerant=True):
            errors_4h_12h.append(f"values:{utc_iso(start)}")
    for parent in derived["1d"]:
        if not parent["complete"]:
            continue
        start = parent["start_time_ms"]
        children = [by_12h.get(start + index * 12 * 60 * MINUTE_MS) for index in range(2)]
        if any(child is None or not child["complete"] for child in children):
            errors_12h_1d.append(f"children:{utc_iso(start)}")
            continue
        aggregate = aggregate_children(children, start, 24 * 60 * MINUTE_MS)
        if not values_match(parent, aggregate, tolerant=True):
            errors_12h_1d.append(f"values:{utc_iso(start)}")
    return {
        "4h_to_12h": {"status": "PASS" if not errors_4h_12h else "FAIL", "errors": errors_4h_12h},
        "12h_to_1d": {"status": "PASS" if not errors_12h_1d else "FAIL", "errors": errors_12h_1d},
    }


def build_and_validate(source_manifest_path: Path, data_root: Path, repo_root: Path) -> dict:
    total_started = time.perf_counter()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_sha = sha256_file(source_manifest_path)
    source_start_ms = parse_utc(source_manifest["dataset"]["strict_start_utc"])
    source_end_ms = parse_utc(source_manifest["dataset"]["strict_end_utc"])
    build_started = time.perf_counter()
    accumulators = {
        resolution: CandleAccumulator(resolution, expected, source_start_ms, {KNOWN_GAP_MS}, [])
        for resolution, expected in TIMEFRAMES.items()
    }
    previous_timestamp = None
    source_rows = 0
    for row in iter_source_rows(source_manifest):
        timestamp = int(row[0])
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise ValueError(f"Source order/duplicate violation at {utc_iso(timestamp)}")
        if timestamp % MINUTE_MS:
            raise ValueError(f"Off-grid source timestamp: {utc_iso(timestamp)}")
        previous_timestamp = timestamp
        source_rows += 1
        for accumulator in accumulators.values():
            accumulator.add(row)
    for accumulator in accumulators.values():
        accumulator.flush()
    if source_rows != source_manifest["dataset"]["observed_rows"]:
        raise ValueError(f"Source row count mismatch: {source_rows}")
    build_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output_root = data_root / "derived/BTCUSDT"
    write_results = {
        resolution: write_timeframe(
            accumulator.rows,
            resolution,
            output_root,
            source_manifest_path,
            source_sha,
            source_manifest,
            repo_root,
            build_timestamp,
        )
        for resolution, accumulator in accumulators.items()
    }
    build_seconds = time.perf_counter() - build_started

    qa_started = time.perf_counter()
    derived = {resolution: read_derived(output_root / resolution) for resolution in TIMEFRAMES}
    structural = {
        resolution: structural_qa(derived[resolution], resolution, expected, source_end_ms)
        for resolution, expected in TIMEFRAMES.items()
    }
    golden = golden_qa(source_manifest, derived)
    cross = cross_timeframe_qa(derived)
    qa_seconds = time.perf_counter() - qa_started
    passed = (
        all(result["status"] == "PASS" for result in structural.values())
        and golden["status"] == "PASS"
        and cross["4h_to_12h"]["status"] == "PASS"
        and cross["12h_to_1d"]["status"] == "PASS"
    )
    report = {
        "status": "PASS" if passed else "FAIL",
        "source_manifest_path": str(source_manifest_path),
        "source_manifest_sha256": source_sha,
        "source_rows": source_rows,
        "outputs": {
            resolution: {
                "path": str(output_root / resolution),
                "status": write_results[resolution]["status"],
                "rows": len(derived[resolution]),
                "complete": sum(row["complete"] for row in derived[resolution]),
                "incomplete": sum(not row["complete"] for row in derived[resolution]),
                "bytes": sum(item["bytes"] for item in write_results[resolution]["manifest"]["output_files"]),
                "first_interval_utc": utc_iso(derived[resolution][0]["start_time_ms"]),
                "first_complete_interval_utc": utc_iso(next(row["start_time_ms"] for row in derived[resolution] if row["complete"])),
                "last_complete_interval_utc": utc_iso(next(row["start_time_ms"] for row in reversed(derived[resolution]) if row["complete"])),
                "last_interval_utc": utc_iso(derived[resolution][-1]["start_time_ms"]),
                "incomplete_intervals": [
                    {"start_utc": utc_iso(row["start_time_ms"]), "reason": row["incomplete_reason"]}
                    for row in derived[resolution]
                    if not row["complete"]
                ],
            }
            for resolution in TIMEFRAMES
        },
        "qa": {"structural": structural, "golden": golden, "cross_timeframe": cross},
        "runtime_seconds": {
            "build": round(build_seconds, 3),
            "validation": round(qa_seconds, 3),
            "total": round(time.perf_counter() - total_started, 3),
        },
    }
    atomic_json(data_root / "manifests/canonical_futures_candles_build_report.json", report)
    if not passed:
        raise RuntimeError("Canonical candle QA failed; see build report")
    return report


def stamp_git_commit(data_root: Path, commit: str) -> None:
    for resolution in TIMEFRAMES:
        path = data_root / f"derived/BTCUSDT/{resolution}/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["code_version"]["git_commit"] = commit
        atomic_json(path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp-git-commit")
    args = parser.parse_args()
    if args.stamp_git_commit:
        stamp_git_commit(args.data_root, args.stamp_git_commit)
        print(json.dumps({"stamped_git_commit": args.stamp_git_commit}, indent=2))
        return
    if args.source_manifest is None:
        parser.error("--source-manifest is required for a build")
    report = build_and_validate(args.source_manifest, args.data_root, args.repo_root)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
