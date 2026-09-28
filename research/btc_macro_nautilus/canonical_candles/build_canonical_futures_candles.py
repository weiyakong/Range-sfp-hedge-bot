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
KNOWN_GAP_MS = 1_567_969_200_000  # 2019-09-08T19:00:00Z
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
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "4h": 240,
    "12h": 720,
    "1d": 1440,
}
SOURCE_CONTRACT = {
    "market": "USDT-M perpetual futures",
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "strict_start_utc": "2019-09-08T17:57:00Z",
    "strict_end_utc": "2026-09-25T23:59:00Z",
    "observed_rows": 3_706_922,
    "known_real_gaps": ["2019-09-08T19:00:00Z"],
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
    manifest: dict, selected: dict[str, set[int]], timeframes: dict[str, int]
) -> dict[str, dict[int, dict]]:
    windows = []
    for resolution, starts in selected.items():
        duration = timeframes[resolution] * MINUTE_MS
        windows.extend((start, start + duration - MINUTE_MS) for start in starts)
    source_start_ms = parse_utc(manifest["dataset"]["strict_start_utc"])
    accumulators = {
        resolution: {
            start: CandleAccumulator(resolution, timeframes[resolution], source_start_ms, {KNOWN_GAP_MS}, [])
            for start in starts
        }
        for resolution, starts in selected.items()
    }
    for row in iter_source_rows(manifest, windows):
        timestamp = int(row[0])
        for resolution, expected in timeframes.items():
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


def golden_qa(manifest: dict, derived: dict[str, list[dict]], timeframes: dict[str, int]) -> dict:
    selected: dict[str, set[int]] = {}
    for resolution, expected in timeframes.items():
        selected[resolution] = {
            bucket_start_ms(parse_utc("2020-01-01T00:00:00Z"), expected),
            bucket_start_ms(KNOWN_GAP_MS, expected),
            bucket_start_ms(parse_utc("2024-01-01T00:00:00Z"), expected),
            derived[resolution][-1]["start_time_ms"],
        }
    fresh = aggregate_selected_rows(manifest, selected, timeframes)
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


def cross_timeframe_qa(derived: dict[str, list[dict]], relationships: Sequence[tuple[str, str]]) -> dict:
    result = {}
    for child_resolution, parent_resolution in relationships:
        errors = []
        child_minutes = TIMEFRAMES[child_resolution]
        parent_minutes = TIMEFRAMES[parent_resolution]
        if parent_minutes % child_minutes:
            raise ValueError(f"Non-nested cross-timeframe relationship: {child_resolution}->{parent_resolution}")
        child_count = parent_minutes // child_minutes
        by_child = {row["start_time_ms"]: row for row in derived[child_resolution]}
        for parent in derived[parent_resolution]:
            if not parent["complete"]:
                continue
            start = parent["start_time_ms"]
            children = [by_child.get(start + index * child_minutes * MINUTE_MS) for index in range(child_count)]
            if any(child is None or not child["complete"] for child in children):
                errors.append(f"children:{utc_iso(start)}")
                continue
            aggregate = aggregate_children(children, start, parent_minutes * MINUTE_MS)
            if not values_match(parent, aggregate, tolerant=True):
                errors.append(f"values:{utc_iso(start)}")
        result[f"{child_resolution}_to_{parent_resolution}"] = {
            "status": "PASS" if not errors else "FAIL", "errors": errors
        }
    return result


def verify_source_contract(manifest: dict, rows: int, first_timestamp: int | None, last_timestamp: int | None,
                           gaps: list[dict], errors: list[str]) -> dict:
    dataset = manifest.get("dataset", {})
    for field, expected in SOURCE_CONTRACT.items():
        if dataset.get(field) != expected:
            errors.append(f"manifest_{field}")
    if rows != SOURCE_CONTRACT["observed_rows"]:
        errors.append("observed_row_count")
    if first_timestamp != parse_utc(SOURCE_CONTRACT["strict_start_utc"]):
        errors.append("first_timestamp")
    if last_timestamp != parse_utc(SOURCE_CONTRACT["strict_end_utc"]):
        errors.append("last_timestamp")
    expected_gap = {
        "previous": "2019-09-08T18:59:00Z",
        "next": "2019-09-08T19:01:00Z",
        "missing": 1,
    }
    if gaps != [expected_gap]:
        errors.append("unexpected_gaps")
    return {
        "status": "PASS" if not errors else "FAIL",
        "rows": rows,
        "first_utc": utc_iso(first_timestamp) if first_timestamp is not None else None,
        "last_utc": utc_iso(last_timestamp) if last_timestamp is not None else None,
        "gaps": gaps,
        "errors": errors,
    }


def audit_source(manifest: dict) -> dict:
    previous_timestamp = None
    first_timestamp = None
    source_rows = 0
    source_gaps = []
    source_errors = []
    for row in iter_source_rows(manifest):
        timestamp = int(row[0])
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            source_errors.append(f"source_order_or_duplicate:{utc_iso(timestamp)}")
        if timestamp % MINUTE_MS:
            source_errors.append(f"source_off_grid:{utc_iso(timestamp)}")
        if previous_timestamp is not None and timestamp - previous_timestamp != MINUTE_MS:
            source_gaps.append({
                "previous": utc_iso(previous_timestamp), "next": utc_iso(timestamp),
                "missing": (timestamp - previous_timestamp) // MINUTE_MS - 1,
            })
        if first_timestamp is None:
            first_timestamp = timestamp
        previous_timestamp = timestamp
        source_rows += 1
    return verify_source_contract(manifest, source_rows, first_timestamp, previous_timestamp,
                                  source_gaps, source_errors)


def write_streamed_timeframe(manifest: dict, source_manifest_path: Path, source_manifest_sha: str,
                             resolution: str, output_root: Path, repo_root: Path,
                             build_timestamp: str) -> dict:
    """Aggregate one resolution with one calendar-year buffer, then atomically publish it."""
    final_dir = output_root / resolution
    if final_dir.exists():
        existing_manifest = final_dir / "manifest.json"
        if existing_manifest.is_file():
            existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
            if existing.get("source_manifest_sha256") == source_manifest_sha:
                valid = all(Path(item["path"]).is_file() and sha256_file(Path(item["path"])) == item["sha256"]
                            for item in existing.get("output_files", []))
                if valid:
                    expected = TIMEFRAMES[resolution]
                    existing["timestamp_contract"] = {
                        "start_time": "UTC bar open", "end_time": "UTC exclusive bar end"
                    }
                    existing["known_gap_affected_bar_count"] = sum(
                        bucket_start_ms(parse_utc(gap), expected)
                        >= bucket_start_ms(parse_utc(manifest["dataset"]["strict_start_utc"]), expected)
                        for gap in manifest["dataset"]["known_real_gaps"]
                    )
                    atomic_json(existing_manifest, existing)
                    return {"status": "reused", "manifest": existing}
        raise FileExistsError(f"Existing output is not a validated reusable build: {final_dir}")

    expected = TIMEFRAMES[resolution]
    source_start_ms = parse_utc(manifest["dataset"]["strict_start_utc"])
    temp_dir = output_root / f".{resolution}.build-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True)
    accumulator = CandleAccumulator(resolution, expected, source_start_ms, {KNOWN_GAP_MS}, [])
    output_files = []
    incomplete_intervals = []
    total_rows = complete_rows = 0

    def write_year_buffer() -> None:
        nonlocal total_rows, complete_rows
        rows = accumulator.rows
        if not rows:
            return
        year = datetime.fromtimestamp(rows[0]["start_time_ms"] / 1000, timezone.utc).year
        if any(datetime.fromtimestamp(row["start_time_ms"] / 1000, timezone.utc).year != year for row in rows):
            raise AssertionError(f"Mixed-year buffer for {resolution} {year}")
        path = temp_dir / f"part-{year}.parquet"
        pq.write_table(rows_to_table(rows), path, compression="zstd", compression_level=9,
                       use_dictionary=["market", "instrument", "resolution", "incomplete_reason"],
                       write_statistics=True)
        output_files.append({"path": str(final_dir / path.name), "year": year, "rows": len(rows),
                             "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        total_rows += len(rows)
        complete_rows += sum(bool(row["complete"]) for row in rows)
        incomplete_intervals.extend(
            {"start_utc": utc_iso(row["start_time_ms"]), "reason": row["incomplete_reason"]}
            for row in rows if not row["complete"]
        )
        rows.clear()

    try:
        for source in iter_source_rows(manifest):
            source_year = datetime.fromtimestamp(int(source[0]) / 1000, timezone.utc).year
            accumulator.add(source)
            if accumulator.rows:
                buffered_year = datetime.fromtimestamp(
                    accumulator.rows[0]["start_time_ms"] / 1000, timezone.utc
                ).year
                if buffered_year < source_year:
                    write_year_buffer()
        accumulator.flush()
        write_year_buffer()
        if not output_files:
            raise AssertionError(f"No output rows for {resolution}")
        derived_manifest = {
            "schema_version": SCHEMA_VERSION,
            "aggregation_version": AGGREGATION_VERSION,
            "build_timestamp_utc": build_timestamp,
            "market": MARKET,
            "instrument": INSTRUMENT,
            "resolution": resolution,
            "timestamp_contract": {"start_time": "UTC bar open", "end_time": "UTC exclusive bar end"},
            "source_manifest_path": str(source_manifest_path),
            "source_manifest_sha256": source_manifest_sha,
            "source_coverage": {
                "start_utc": manifest["dataset"]["strict_start_utc"],
                "end_utc": manifest["dataset"]["strict_end_utc"],
                "observed_rows": manifest["dataset"]["observed_rows"],
            },
            "output_coverage": {
                "start_utc": utc_iso(parse_utc(manifest["dataset"]["strict_start_utc"]) // (expected * MINUTE_MS) * (expected * MINUTE_MS)),
                "end_utc_exclusive": utc_iso(bucket_start_ms(parse_utc(manifest["dataset"]["strict_end_utc"]), expected) + expected * MINUTE_MS),
            },
            "total_rows": total_rows,
            "complete_rows": complete_rows,
            "incomplete_rows": total_rows - complete_rows,
            "incomplete_intervals": incomplete_intervals,
            "known_gaps": manifest["dataset"]["known_real_gaps"],
            "partitioning": "year",
            "parquet_compression": "zstd",
            "output_files": output_files,
            "code_version": {"git_commit_at_build": git_commit(repo_root), "pipeline_sha256": sha256_file(Path(__file__))},
        }
        atomic_json(temp_dir / "manifest.json", derived_manifest)
        output_root.mkdir(parents=True, exist_ok=True)
        os.replace(temp_dir, final_dir)
        return {"status": "built", "manifest": derived_manifest}
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def iter_derived_rows(tf_dir: Path) -> Iterator[dict]:
    for path in sorted(tf_dir.glob("part-*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=100_000):
            for row in batch.to_pylist():
                row["start_time_ms"] = int(row.pop("start_time").timestamp() * 1000)
                row["end_time_ms"] = int(row.pop("end_time").timestamp() * 1000)
                yield row


def structural_qa_stream(tf_dir: Path, resolution: str, expected: int, source_end_ms: int) -> dict:
    errors, starts = [], set()
    previous_start = None
    rows = complete = 0
    last = None
    duration = expected * MINUTE_MS
    for row in iter_derived_rows(tf_dir):
        start = row["start_time_ms"]
        if previous_start is not None and start <= previous_start:
            errors.append("non_monotonic_or_duplicates")
        if start in starts:
            errors.append("duplicates")
        starts.add(start)
        if start % duration:
            errors.append(f"off_grid:{utc_iso(start)}")
        numeric = [float(row[field]) for field in NUMERIC_FIELDS]
        if not all(math.isfinite(value) for value in numeric):
            errors.append(f"non_finite:{utc_iso(start)}")
        if row["high"] < max(row["open"], row["close"]) or row["low"] > min(row["open"], row["close"]):
            errors.append(f"invalid_ohlc:{utc_iso(start)}")
        if row["high"] < row["low"] or any(row[field] < 0 for field in ADDITIVE_FIELDS):
            errors.append(f"invalid_additive_or_range:{utc_iso(start)}")
        if row["complete"] and row["constituent_count"] != expected:
            errors.append(f"bad_complete_count:{utc_iso(start)}")
        if not row["complete"] and not row["incomplete_reason"]:
            errors.append(f"unexplained_incomplete:{utc_iso(start)}")
        previous_start, last = start, row
        rows += 1
        complete += bool(row["complete"])
    if last is None or last["start_time_ms"] != bucket_start_ms(source_end_ms, expected):
        errors.append("missing_last_interval")
    elif not last["complete"]:
        errors.append("last_interval_incomplete")
    return {"resolution": resolution, "status": "PASS" if not errors else "FAIL", "errors": errors,
            "rows": rows, "complete": complete, "incomplete": rows - complete}


def selected_derived_rows(tf_dir: Path, starts: set[int]) -> dict[int, dict]:
    return {row["start_time_ms"]: row for row in iter_derived_rows(tf_dir) if row["start_time_ms"] in starts}


def golden_qa_stream(manifest: dict, output_root: Path, timeframes: dict[str, int]) -> dict:
    selected = {
        resolution: {bucket_start_ms(parse_utc(manifest["dataset"]["strict_start_utc"]), expected),
                     bucket_start_ms(parse_utc("2020-01-01T00:00:00Z"), expected),
                     bucket_start_ms(KNOWN_GAP_MS, expected),
                     bucket_start_ms(parse_utc("2024-01-01T00:00:00Z"), expected),
                     bucket_start_ms(parse_utc(manifest["dataset"]["strict_end_utc"]), expected)}
        for resolution, expected in timeframes.items()
    }
    fresh = aggregate_selected_rows(manifest, selected, timeframes)
    errors, checks = [], []
    for resolution, starts in selected.items():
        stored = selected_derived_rows(output_root / resolution, starts)
        for start in sorted(starts):
            match = start in stored and values_match(stored[start], fresh[resolution][start])
            checks.append({"resolution": resolution, "start_utc": utc_iso(start), "match": match})
            if not match:
                errors.append(f"{resolution}:{utc_iso(start)}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "checks": checks}


def cross_timeframe_qa_stream(output_root: Path, relationships: Sequence[tuple[str, str]]) -> dict:
    result = {}
    for child_resolution, parent_resolution in relationships:
        errors = []
        child_minutes, parent_minutes = TIMEFRAMES[child_resolution], TIMEFRAMES[parent_resolution]
        child_count = parent_minutes // child_minutes
        child_iter = iter_derived_rows(output_root / child_resolution)
        child = next(child_iter, None)
        for parent in iter_derived_rows(output_root / parent_resolution):
            children = []
            while child is not None and child["start_time_ms"] < parent["end_time_ms"]:
                if child["start_time_ms"] >= parent["start_time_ms"]:
                    children.append(child)
                child = next(child_iter, None)
            if not parent["complete"]:
                continue
            if len(children) != child_count or any(not row["complete"] for row in children):
                errors.append(f"children:{utc_iso(parent['start_time_ms'])}")
            elif not values_match(parent, aggregate_children(children, parent["start_time_ms"], parent_minutes * MINUTE_MS), tolerant=True):
                errors.append(f"values:{utc_iso(parent['start_time_ms'])}")
        result[f"{child_resolution}_to_{parent_resolution}"] = {
            "status": "PASS" if not errors else "FAIL", "errors": errors
        }
    return result


def build_and_validate(source_manifest_path: Path, data_root: Path, repo_root: Path,
                       resolutions: Sequence[str] | None = None) -> dict:
    total_started = time.perf_counter()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_sha = sha256_file(source_manifest_path)
    source_start_ms = parse_utc(source_manifest["dataset"]["strict_start_utc"])
    source_end_ms = parse_utc(source_manifest["dataset"]["strict_end_utc"])
    selected = tuple(resolutions or ("4h", "12h", "1d"))
    unknown = sorted(set(selected) - set(TIMEFRAMES))
    if not selected or unknown:
        raise ValueError(f"Unsupported resolutions: {unknown}")
    selected_timeframes = {resolution: TIMEFRAMES[resolution] for resolution in selected}
    source_qa = audit_source(source_manifest)
    if source_qa["status"] != "PASS":
        raise RuntimeError(f"Canonical 1m source contract failed: {source_qa}")
    build_started = time.perf_counter()
    build_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output_root = data_root / "derived/BTCUSDT"
    write_results = {
        resolution: write_streamed_timeframe(source_manifest, source_manifest_path, source_sha, resolution,
                                             output_root, repo_root, build_timestamp)
        for resolution in selected
    }
    build_seconds = time.perf_counter() - build_started

    qa_started = time.perf_counter()
    structural = {
        resolution: structural_qa_stream(output_root / resolution, resolution, expected, source_end_ms)
        for resolution, expected in selected_timeframes.items()
    }
    golden = golden_qa_stream(source_manifest, output_root, selected_timeframes)
    relationships = [pair for pair in (("3m", "15m"), ("5m", "15m"), ("4h", "12h"), ("12h", "1d"))
                     if set(pair).issubset(selected)]
    cross = cross_timeframe_qa_stream(output_root, relationships)
    qa_seconds = time.perf_counter() - qa_started
    passed = (
        all(result["status"] == "PASS" for result in structural.values())
        and golden["status"] == "PASS"
        and all(result["status"] == "PASS" for result in cross.values())
    )
    report = {
        "status": "PASS" if passed else "FAIL",
        "source_manifest_path": str(source_manifest_path),
        "source_manifest_sha256": source_sha,
        "source_rows": source_qa["rows"],
        "source_qa": source_qa,
        "outputs": {
            resolution: {
                "path": str(output_root / resolution),
                "status": write_results[resolution]["status"],
                "rows": structural[resolution]["rows"],
                "complete": structural[resolution]["complete"],
                "incomplete": structural[resolution]["incomplete"],
                "bytes": sum(item["bytes"] for item in write_results[resolution]["manifest"]["output_files"]),
                "first_interval_utc": write_results[resolution]["manifest"]["output_coverage"]["start_utc"],
                "last_interval_utc": utc_iso(source_end_ms // (selected_timeframes[resolution] * MINUTE_MS) * (selected_timeframes[resolution] * MINUTE_MS)),
                "incomplete_intervals": write_results[resolution]["manifest"].get("incomplete_intervals", []),
            }
            for resolution in selected
        },
        "qa": {"structural": structural, "golden": golden, "cross_timeframe": cross},
        "runtime_seconds": {
            "build": round(build_seconds, 3),
            "validation": round(qa_seconds, 3),
            "total": round(time.perf_counter() - total_started, 3),
        },
    }
    report_name = "canonical_futures_candles_build_report.json" if selected == ("4h", "12h", "1d") else (
        "canonical_futures_candles_" + "_".join(selected) + "_build_report.json"
    )
    atomic_json(data_root / f"manifests/{report_name}", report)
    if not passed:
        raise RuntimeError("Canonical candle QA failed; see build report")
    return report


def stamp_git_commit(data_root: Path, commit: str, resolutions: Sequence[str]) -> None:
    for resolution in resolutions:
        path = data_root / f"derived/BTCUSDT/{resolution}/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["code_version"]["git_commit"] = commit
        atomic_json(path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--resolutions", nargs="+", choices=sorted(TIMEFRAMES))
    parser.add_argument("--stamp-git-commit")
    args = parser.parse_args()
    if args.stamp_git_commit:
        if not args.resolutions:
            parser.error("--resolutions is required with --stamp-git-commit")
        stamp_git_commit(args.data_root, args.stamp_git_commit, args.resolutions)
        print(json.dumps({"stamped_git_commit": args.stamp_git_commit}, indent=2))
        return
    if args.source_manifest is None:
        parser.error("--source-manifest is required for a build")
    report = build_and_validate(args.source_manifest, args.data_root, args.repo_root, args.resolutions)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
