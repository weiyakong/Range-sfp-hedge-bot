#!/usr/bin/env python3
"""Build the Stage 2I-A strict raw 4H pivot and context dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq


STAGE_VERSION = "stage2i-a-v1"
BAR_DURATION = timedelta(hours=4)
HORIZONS = (1, 2, 3, 6, 12, 24)
TYPE_ORDER = {"HIGH": 0, "LOW": 1}
UTC = timezone.utc


@dataclass(frozen=True)
class Candle:
    source_row_index: int
    pivot_bar_index: int
    run_id: int
    start_time: datetime
    end_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    constituent_count: int
    expected_constituent_count: int
    market: str
    instrument: str
    resolution: str


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    arrow_type: pa.DataType
    definition: str
    units: str
    information_status: str
    nullable: bool


def _utc(value: Any) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, received {type(value)!r}")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def complete_population(rows: Iterable[Mapping[str, Any]]) -> List[Candle]:
    """Return complete candles, indexed deterministically and split at source gaps."""
    result: List[Candle] = []
    previous_end: Optional[datetime] = None
    run_id = -1
    for fallback_index, row in enumerate(rows):
        if not bool(row.get("complete", False)):
            previous_end = None
            continue
        start = _utc(row["start_time"])
        end = _utc(row["end_time"])
        if previous_end is None or start != previous_end or end - start != BAR_DURATION:
            run_id += 1
        result.append(
            Candle(
                source_row_index=int(row.get("source_row_index", fallback_index)),
                pivot_bar_index=len(result),
                run_id=run_id,
                start_time=start,
                end_time=end,
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row["volume"]),
                quote_volume=float(row["quote_volume"]), trade_count=int(row["trade_count"]),
                taker_buy_base_volume=float(row["taker_buy_base_volume"]),
                taker_buy_quote_volume=float(row["taker_buy_quote_volume"]),
                constituent_count=int(row["constituent_count"]),
                expected_constituent_count=int(row["expected_constituent_count"]),
                market=str(row["market"]), instrument=str(row["instrument"]),
                resolution=str(row["resolution"]),
            )
        )
        previous_end = end
    return result


def _same_run(window: Sequence[Candle]) -> bool:
    return bool(window) and len({bar.run_id for bar in window}) == 1


def _pivot_types(candles: Sequence[Candle], index: int) -> List[str]:
    if index < 2 or index + 2 >= len(candles) or not _same_run(candles[index - 2:index + 3]):
        return []
    center = candles[index]
    others = [candles[index - 2], candles[index - 1], candles[index + 1], candles[index + 2]]
    types: List[str] = []
    if all(center.high > bar.high for bar in others):
        types.append("HIGH")
    if all(center.low < bar.low for bar in others):
        types.append("LOW")
    return types


def _signed(value: float, pivot_type: str) -> float:
    return value if pivot_type == "HIGH" else -value


def _direction(open_price: float, close_price: float) -> str:
    if close_price > open_price:
        return "UP"
    if close_price < open_price:
        return "DOWN"
    return "DOJI"


def _immediate_context(row: Dict[str, Any], candles: Sequence[Candle], index: int) -> None:
    center = candles[index]
    for offset in (-2, -1, 0, 1, 2):
        bar = candles[index + offset]
        prefix = f"causal__bar_{offset:+d}__"
        row[prefix + "start_time"] = bar.start_time
        row[prefix + "end_time"] = bar.end_time
        for field in ("open", "high", "low", "close", "volume", "quote_volume", "trade_count"):
            row[prefix + field] = getattr(bar, field)
        row[prefix + "range"] = bar.high - bar.low
        row[prefix + "body"] = bar.close - bar.open
        row[prefix + "absolute_body"] = abs(bar.close - bar.open)
        row[prefix + "upper_wick"] = bar.high - max(bar.open, bar.close)
        row[prefix + "lower_wick"] = min(bar.open, bar.close) - bar.low
        row[prefix + "direction"] = _direction(bar.open, bar.close)
    row["causal__center_range"] = center.high - center.low
    row["causal__center_body"] = center.close - center.open
    row["causal__center_upper_wick"] = center.high - max(center.open, center.close)
    row["causal__center_lower_wick"] = min(center.open, center.close) - center.low


def _event_base(candles: Sequence[Candle], index: int, pivot_type: str, manifest_sha: str,
                dual: bool) -> Dict[str, Any]:
    bar = candles[index]
    confirmation = candles[index + 2].end_time
    row: Dict[str, Any] = {
        "event_id": f"P4H_{index:06d}_{pivot_type}",
        "source_manifest_sha256": manifest_sha,
        "pivot_bar_index": index,
        "source_row_index": bar.source_row_index,
        "run_id": bar.run_id,
        "pivot_timestamp": bar.start_time,
        "pivot_candle_close_timestamp": bar.end_time,
        "confirmation_timestamp": confirmation,
        "available_from": confirmation,
        "pivot_type": pivot_type,
        "pivot_price": bar.high if pivot_type == "HIGH" else bar.low,
        "open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close,
        "volume": bar.volume, "quote_volume": bar.quote_volume,
        "trade_count": bar.trade_count,
        "taker_buy_base_volume": bar.taker_buy_base_volume,
        "taker_buy_quote_volume": bar.taker_buy_quote_volume,
        "constituent_count": bar.constituent_count,
        "expected_constituent_count": bar.expected_constituent_count,
        "market": bar.market, "instrument": bar.instrument, "resolution": bar.resolution,
        "causal__dual_high_low_same_candle": dual,
    }
    _immediate_context(row, candles, index)
    return row


def _add_horizons(row: Dict[str, Any], candles: Sequence[Candle], index: int) -> None:
    pivot_price = float(row["pivot_price"])
    for horizon in HORIZONS:
        candidates = list(candles[index + 1:min(len(candles), index + horizon + 1)])
        window: List[Candle] = []
        for bar in candidates:
            if bar.run_id != candles[index].run_id:
                break
            window.append(bar)
        prefix = f"postevent__horizon_{horizon}__"
        row[prefix + "bars_available"] = len(window)
        row[prefix + "window_complete"] = len(window) == horizon
        if len(window) != horizon:
            for suffix in ("highest_high", "lowest_low", "max_upward_excursion", "max_downward_excursion",
                           "last_close_displacement", "absolute_last_close_displacement", "range_traversed"):
                row[prefix + suffix] = None
            continue
        highest = max(bar.high for bar in window)
        lowest = min(bar.low for bar in window)
        displacement = window[-1].close - pivot_price
        row[prefix + "highest_high"] = highest
        row[prefix + "lowest_low"] = lowest
        row[prefix + "max_upward_excursion"] = max(0.0, highest - pivot_price)
        row[prefix + "max_downward_excursion"] = max(0.0, pivot_price - lowest)
        row[prefix + "last_close_displacement"] = displacement
        row[prefix + "absolute_last_close_displacement"] = abs(displacement)
        row[prefix + "range_traversed"] = highest - lowest


def _relation(row: Dict[str, Any], other: Optional[Dict[str, Any]], prefix: str, forward: bool) -> None:
    fields = ("event_id", "pivot_type", "pivot_timestamp", "pivot_price", "bar_distance", "time_distance_hours",
              "price_change", "absolute_price_change", "percentage_price_change", "normalized_price_change", "direction")
    if other is None:
        for field in fields:
            row[prefix + field] = None
        return
    earlier, later = (row, other) if forward else (other, row)
    delta = float(later["pivot_price"]) - float(earlier["pivot_price"])
    bar_distance = int(later["pivot_bar_index"]) - int(earlier["pivot_bar_index"])
    hours = (later["pivot_timestamp"] - earlier["pivot_timestamp"]).total_seconds() / 3600.0
    row[prefix + "event_id"] = other["event_id"]
    row[prefix + "pivot_type"] = other["pivot_type"]
    row[prefix + "pivot_timestamp"] = other["pivot_timestamp"]
    row[prefix + "pivot_price"] = other["pivot_price"]
    row[prefix + "bar_distance"] = bar_distance
    row[prefix + "time_distance_hours"] = hours
    row[prefix + "price_change"] = delta
    row[prefix + "absolute_price_change"] = abs(delta)
    normalized = delta / float(earlier["pivot_price"]) if earlier["pivot_price"] else None
    row[prefix + "percentage_price_change"] = 100.0 * normalized if normalized is not None else None
    row[prefix + "normalized_price_change"] = normalized
    row[prefix + "direction"] = "UP" if delta > 0 else "DOWN" if delta < 0 else "FLAT"


def _add_neighbors(events: List[Dict[str, Any]]) -> None:
    for index, row in enumerate(events):
        prior = [event for event in events[:index] if event["pivot_bar_index"] < row["pivot_bar_index"]]
        future = [event for event in events[index + 1:] if event["pivot_bar_index"] > row["pivot_bar_index"]]
        previous_any = prior[-1] if prior else None
        next_any = future[0] if future else None
        previous_same = next((event for event in reversed(prior) if event["pivot_type"] == row["pivot_type"]), None)
        previous_opposite = next((event for event in reversed(prior) if event["pivot_type"] != row["pivot_type"]), None)
        next_same = next((event for event in future if event["pivot_type"] == row["pivot_type"]), None)
        next_opposite = next((event for event in future if event["pivot_type"] != row["pivot_type"]), None)
        _relation(row, previous_any, "causal__previous_any__", False)
        _relation(row, previous_same, "causal__previous_same__", False)
        _relation(row, previous_opposite, "causal__previous_opposite__", False)
        _relation(row, next_any, "postevent__next_any__", True)
        _relation(row, next_same, "postevent__next_same__", True)
        _relation(row, next_opposite, "postevent__next_opposite__", True)


def _add_geometry(events: List[Dict[str, Any]], candles: Sequence[Candle]) -> None:
    event_by_id = {str(event["event_id"]): event for event in events}
    for row in events:
        previous_id = row.get("causal__previous_opposite__event_id")
        previous = event_by_id.get(str(previous_id)) if previous_id else None
        prefix = "causal__from_previous_opposite__"
        if previous is None or previous["run_id"] != row["run_id"]:
            for suffix in ("endpoint_move", "absolute_endpoint_move", "bar_count", "duration_hours", "close_path",
                           "percentage_move", "log_return", "direction", "log_close_path", "close_efficiency",
                           "log_close_efficiency", "signed_endpoint_move"):
                row[prefix + suffix] = None
            continue
        start = int(previous["pivot_bar_index"])
        end = int(row["pivot_bar_index"])
        path = candles[start:end + 1]
        closes = [bar.close for bar in path]
        close_path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
        log_closes = [math.log(value) for value in closes]
        log_path = sum(abs(b - a) for a, b in zip(log_closes, log_closes[1:]))
        endpoint = float(row["pivot_price"]) - float(previous["pivot_price"])
        log_endpoint = abs(log_closes[-1] - log_closes[0])
        row[prefix + "endpoint_move"] = endpoint
        row[prefix + "absolute_endpoint_move"] = abs(endpoint)
        row[prefix + "bar_count"] = end - start
        row[prefix + "duration_hours"] = (row["pivot_timestamp"] - previous["pivot_timestamp"]).total_seconds() / 3600.0
        row[prefix + "percentage_move"] = 100.0 * endpoint / float(previous["pivot_price"])
        row[prefix + "log_return"] = math.log(float(row["pivot_price"]) / float(previous["pivot_price"]))
        row[prefix + "direction"] = "UP" if endpoint > 0 else "DOWN" if endpoint < 0 else "FLAT"
        row[prefix + "close_path"] = close_path
        row[prefix + "log_close_path"] = log_path
        row[prefix + "close_efficiency"] = abs(closes[-1] - closes[0]) / close_path if close_path > 0 else None
        row[prefix + "log_close_efficiency"] = log_endpoint / log_path if log_path > 0 else None
        row[prefix + "signed_endpoint_move"] = _signed(endpoint, str(row["pivot_type"]))


def build_raw_pivot_rows(candles: Sequence[Candle], manifest_sha: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for index in range(len(candles)):
        types = _pivot_types(candles, index)
        for pivot_type in types:
            events.append(_event_base(candles, index, pivot_type, manifest_sha, len(types) == 2))
    events.sort(key=lambda event: (int(event["pivot_bar_index"]), TYPE_ORDER[str(event["pivot_type"])]))
    _add_neighbors(events)
    _add_geometry(events, candles)
    for event in events:
        _add_horizons(event, candles, int(event["pivot_bar_index"]))
    return events


def _column_definitions() -> List[ColumnDefinition]:
    timestamp = pa.timestamp("us", tz="UTC")
    definitions = [
        ColumnDefinition("event_id", pa.string(), "Stable raw pivot event identifier.", "id", "identity", False),
        ColumnDefinition("source_manifest_sha256", pa.string(), "SHA256 of canonical 4H manifest.", "sha256", "provenance", False),
        ColumnDefinition("pivot_bar_index", pa.int64(), "Zero-based index in complete-candle population.", "bars", "identity", False),
        ColumnDefinition("source_row_index", pa.int64(), "Zero-based index in complete+incomplete canonical source.", "rows", "provenance", False),
        ColumnDefinition("run_id", pa.int32(), "Contiguous complete-candle run identifier.", "id", "identity", False),
        ColumnDefinition("pivot_timestamp", timestamp, "Pivot candle open timestamp.", "UTC", "event_time", False),
        ColumnDefinition("pivot_candle_close_timestamp", timestamp, "Pivot candle close timestamp.", "UTC", "event_time", False),
        ColumnDefinition("confirmation_timestamp", timestamp, "Close of second right-hand candle.", "UTC", "causal", False),
        ColumnDefinition("available_from", timestamp, "Earliest time strict five-bar pivot is known.", "UTC", "causal", False),
        ColumnDefinition("pivot_type", pa.string(), "Strict five-bar HIGH or LOW.", "category", "identity", False),
        ColumnDefinition("pivot_price", pa.float64(), "High for HIGH pivots; low for LOW pivots.", "USDT", "event", False),
    ]
    for field, arrow, units in (("open", pa.float64(), "USDT"), ("high", pa.float64(), "USDT"),
                                ("low", pa.float64(), "USDT"), ("close", pa.float64(), "USDT"),
                                ("volume", pa.float64(), "BTC"), ("quote_volume", pa.float64(), "USDT"),
                                ("trade_count", pa.int64(), "trades"),
                                ("taker_buy_base_volume", pa.float64(), "BTC"),
                                ("taker_buy_quote_volume", pa.float64(), "USDT"),
                                ("constituent_count", pa.int32(), "1m candles"),
                                ("expected_constituent_count", pa.int32(), "1m candles")):
        definitions.append(ColumnDefinition(field, arrow, f"Canonical pivot-candle {field}.", units, "event", False))
    for field in ("market", "instrument", "resolution"):
        definitions.append(ColumnDefinition(field, pa.string(), f"Canonical {field}.", "category", "provenance", False))
    definitions.append(ColumnDefinition("causal__dual_high_low_same_candle", pa.bool_(), "Both strict tests pass on center candle.", "boolean", "causal", False))
    for offset in (-2, -1, 0, 1, 2):
        prefix = f"causal__bar_{offset:+d}__"
        definitions.extend([
            ColumnDefinition(prefix + "start_time", timestamp, f"Offset {offset} candle open.", "UTC", "causal", False),
            ColumnDefinition(prefix + "end_time", timestamp, f"Offset {offset} candle close.", "UTC", "causal", False),
        ])
        for field, arrow, units in (("open", pa.float64(), "USDT"), ("high", pa.float64(), "USDT"),
                                    ("low", pa.float64(), "USDT"), ("close", pa.float64(), "USDT"),
                                    ("volume", pa.float64(), "BTC"), ("quote_volume", pa.float64(), "USDT"),
                                    ("trade_count", pa.int64(), "trades"), ("range", pa.float64(), "USDT"),
                                    ("body", pa.float64(), "USDT"), ("absolute_body", pa.float64(), "USDT"),
                                    ("upper_wick", pa.float64(), "USDT"), ("lower_wick", pa.float64(), "USDT"),
                                    ("direction", pa.string(), "category")):
            definitions.append(ColumnDefinition(prefix + field, arrow, f"Offset {offset} candle {field}.", units, "causal", False))
    for field in ("center_range", "center_body", "center_upper_wick", "center_lower_wick"):
        definitions.append(ColumnDefinition("causal__" + field, pa.float64(), f"Pivot candle {field}.", "USDT", "causal", False))
    relation_fields = (("event_id", pa.string(), "id"), ("pivot_type", pa.string(), "category"),
                       ("pivot_timestamp", timestamp, "UTC"), ("pivot_price", pa.float64(), "USDT"),
                       ("bar_distance", pa.int64(), "bars"), ("time_distance_hours", pa.float64(), "hours"),
                       ("price_change", pa.float64(), "USDT"), ("absolute_price_change", pa.float64(), "USDT"),
                       ("percentage_price_change", pa.float64(), "percent"),
                       ("normalized_price_change", pa.float64(), "ratio"), ("direction", pa.string(), "category"))
    for namespace, relation in (("causal", "previous_any"), ("causal", "previous_same"),
                                ("causal", "previous_opposite"), ("postevent", "next_any"),
                                ("postevent", "next_same"), ("postevent", "next_opposite")):
        for field, arrow, units in relation_fields:
            definitions.append(ColumnDefinition(f"{namespace}__{relation}__{field}", arrow,
                                                f"{relation} pivot {field}; same-bar dual counterpart excluded.", units,
                                                namespace, True))
    for field, arrow, units in (("endpoint_move", pa.float64(), "USDT"),
                                ("absolute_endpoint_move", pa.float64(), "USDT"),
                                ("bar_count", pa.int64(), "bars"), ("duration_hours", pa.float64(), "hours"),
                                ("percentage_move", pa.float64(), "percent"),
                                ("log_return", pa.float64(), "log units"), ("direction", pa.string(), "category"),
                                ("close_path", pa.float64(), "USDT"), ("log_close_path", pa.float64(), "log units"),
                                ("close_efficiency", pa.float64(), "ratio"),
                                ("log_close_efficiency", pa.float64(), "ratio"),
                                ("signed_endpoint_move", pa.float64(), "USDT")):
        definitions.append(ColumnDefinition("causal__from_previous_opposite__" + field, arrow,
                                            f"Geometry from prior opposite pivot: {field}.", units, "causal", True))
    for horizon in HORIZONS:
        prefix = f"postevent__horizon_{horizon}__"
        definitions.extend([
            ColumnDefinition(prefix + "bars_available", pa.int32(), "Contiguous future bars available.", "bars", "postevent", False),
            ColumnDefinition(prefix + "window_complete", pa.bool_(), "Full horizon exists in same run.", "boolean", "postevent", False),
        ])
        for field in ("highest_high", "lowest_low", "max_upward_excursion", "max_downward_excursion",
                      "last_close_displacement", "absolute_last_close_displacement", "range_traversed"):
            definitions.append(ColumnDefinition(prefix + field, pa.float64(), f"Future horizon diagnostic: {field}.",
                                                "USDT", "postevent", True))
    return definitions


def write_pivot_parquet(path: Path, events: Sequence[Mapping[str, Any]]) -> None:
    definitions = _column_definitions()
    arrays = [pa.array([event.get(definition.name) for event in events], type=definition.arrow_type)
              for definition in definitions]
    table = pa.Table.from_arrays(arrays, names=[definition.name for definition in definitions])
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", use_dictionary=False, write_statistics=True,
                   version="2.6", data_page_version="1.0")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n", encoding="utf-8")


def _load_source(data_root: Path) -> Tuple[List[Candle], Dict[str, Any]]:
    source_dir = data_root / "derived" / "BTCUSDT" / "4h"
    manifest_path = source_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    rows: List[Dict[str, Any]] = []
    verified_files: List[Dict[str, Any]] = []
    source_schema: Optional[str] = None
    for entry in manifest["output_files"]:
        recorded_path = Path(entry["path"])
        path = recorded_path if recorded_path.is_absolute() else source_dir / recorded_path
        actual_sha = _sha256(path)
        if actual_sha != entry["sha256"]:
            raise RuntimeError(f"Canonical checksum mismatch: {path}")
        table = pq.read_table(path)
        if source_schema is None:
            source_schema = str(table.schema)
        if table.num_rows != int(entry["rows"]):
            raise RuntimeError(f"Canonical row-count mismatch: {path}")
        batch = table.to_pylist()
        for row in batch:
            row["source_row_index"] = len(rows)
            rows.append(row)
        verified_files.append({"path": str(path), "rows": table.num_rows, "sha256": actual_sha})
    complete = complete_population(rows)
    if len(rows) != int(manifest["total_rows"]) or len(complete) != int(manifest["complete_rows"]):
        raise RuntimeError("Canonical manifest population counts do not match loaded rows")
    info = {
        "manifest_path": str(manifest_path), "manifest_sha256": manifest_sha,
        "schema_version": manifest["schema_version"], "aggregation_version": manifest["aggregation_version"],
        "total_rows": len(rows), "complete_rows": len(complete), "incomplete_rows": len(rows) - len(complete),
        "coverage_start": manifest["output_coverage"]["start_utc"],
        "coverage_end_exclusive": manifest["output_coverage"]["end_utc_exclusive"],
        "schema": source_schema,
        "files": verified_files,
    }
    return complete, info


def _independent_pivot_keys(candles: Sequence[Candle]) -> List[Tuple[int, str]]:
    keys: List[Tuple[int, str]] = []
    for i in range(2, len(candles) - 2):
        if not _same_run(candles[i - 2:i + 3]):
            continue
        local_highs = [candles[j].high for j in (i - 2, i - 1, i + 1, i + 2)]
        local_lows = [candles[j].low for j in (i - 2, i - 1, i + 1, i + 2)]
        if candles[i].high > max(local_highs): keys.append((i, "HIGH"))
        if candles[i].low < min(local_lows): keys.append((i, "LOW"))
    return keys


def _qa(candles: Sequence[Candle], events: Sequence[Mapping[str, Any]], parquet_path: Path) -> Dict[str, Any]:
    keys = [(int(event["pivot_bar_index"]), str(event["pivot_type"])) for event in events]
    expected = _independent_pivot_keys(candles)
    checks = {
        "strict_definition_independent_recompute": keys == expected,
        "event_ids_unique": len({event["event_id"] for event in events}) == len(events),
        "ordered": keys == sorted(keys, key=lambda item: (item[0], TYPE_ORDER[item[1]])),
        "no_edge_or_cross_gap_pivots": all(_same_run(candles[i - 2:i + 3]) for i, _ in keys),
        "confirmation_is_right2_close": all(event["available_from"] == candles[int(event["pivot_bar_index"]) + 2].end_time and
                                             event["confirmation_timestamp"] == event["available_from"] for event in events),
        "source_rows_complete": all(candles[int(event["pivot_bar_index"])].source_row_index == event["source_row_index"] for event in events),
        "postevent_namespace": all(name.startswith("postevent__") for name in events[0] if "next_" in name or "horizon_" in name) if events else True,
        "parquet_rows": pq.read_metadata(parquet_path).num_rows == len(events),
        "parquet_columns": pq.read_schema(parquet_path).names == [definition.name for definition in _column_definitions()],
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _summary(values: Sequence[float]) -> Dict[str, Optional[float]]:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean: return {"min": None, "median": None, "max": None, "mean": None}
    mid = len(clean) // 2
    median = clean[mid] if len(clean) % 2 else (clean[mid - 1] + clean[mid]) / 2
    return {"min": clean[0], "median": median, "max": clean[-1], "mean": sum(clean) / len(clean)}


def _event_excerpt(event: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: event[key] for key in ("event_id", "pivot_timestamp", "pivot_type", "pivot_price",
                                        "pivot_bar_index", "available_from")}


def _event_sequences(events: Sequence[Mapping[str, Any]]) -> List[List[Dict[str, Any]]]:
    if not events:
        return []
    starts = sorted({0, max(0, len(events) // 3 - 2), max(0, 2 * len(events) // 3 - 2), max(0, len(events) - 5)})
    return [[_event_excerpt(event) for event in events[start:start + 5]] for start in starts]


def _largest(events: Sequence[Mapping[str, Any]], field: str, count: int = 10) -> List[Dict[str, Any]]:
    available = [event for event in events if event.get(field) is not None]
    ordered = sorted(available, key=lambda event: abs(float(event[field])), reverse=True)[:count]
    return [{**_event_excerpt(event), field: event[field]} for event in ordered]


def _svg_plot(path: Path, candles: Sequence[Candle], events: Sequence[Mapping[str, Any]], start: datetime,
              end: datetime, title: str) -> None:
    bars = [bar for bar in candles if start <= bar.start_time < end]
    if not bars: return
    width, height, pad = 1200, 420, 45
    minimum, maximum = min(bar.low for bar in bars), max(bar.high for bar in bars)
    span = maximum - minimum or 1.0
    x = lambda idx: pad + idx * (width - 2 * pad) / max(1, len(bars) - 1)
    y = lambda price: height - pad - (price - minimum) * (height - 2 * pad) / span
    index_by_time = {bar.start_time: i for i, bar in enumerate(bars)}
    body_width = max(1.0, min(5.0, (width - 2 * pad) / max(1, len(bars)) * 0.65))
    candle_marks: List[str] = []
    for i, bar in enumerate(bars):
        center_x = x(i)
        color = "#2ca02c" if bar.close >= bar.open else "#d62728"
        top = min(y(bar.open), y(bar.close))
        body_height = max(1.0, abs(y(bar.open) - y(bar.close)))
        candle_marks.append(f'<line x1="{center_x:.2f}" y1="{y(bar.high):.2f}" x2="{center_x:.2f}" y2="{y(bar.low):.2f}" stroke="{color}" stroke-width="1"/>')
        candle_marks.append(f'<rect x="{center_x-body_width/2:.2f}" y="{top:.2f}" width="{body_width:.2f}" height="{body_height:.2f}" fill="{color}"/>')
    marks: List[str] = []
    for event in events:
        idx = index_by_time.get(event["pivot_timestamp"])
        if idx is None: continue
        color = "#d62728" if event["pivot_type"] == "HIGH" else "#2ca02c"
        marks.append(f'<circle cx="{x(idx):.2f}" cy="{y(float(event["pivot_price"])):.2f}" r="4" fill="{color}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f'<rect width="100%" height="100%" fill="white"/><text x="{pad}" y="24" font-family="sans-serif" font-size="16">{title}</text>'
           f'{"".join(candle_marks)}{"".join(marks)}'
           f'<text x="{pad}" y="{height-10}" font-family="sans-serif" font-size="11">Red=HIGH, green=LOW; all strict raw pivots</text></svg>')
    path.write_text(svg, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo_root, check=True, text=True, capture_output=True).stdout.strip()


def _write_outputs(output_dir: Path, candles: Sequence[Candle], events: List[Dict[str, Any]], source: Dict[str, Any],
                   repo_root: Path, mode: str, stamp: Optional[str]) -> Dict[str, Any]:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=output_dir.name + ".tmp.", dir=output_dir.parent))
    try:
        _json(temp_dir / "progress.json", {"stage": "events_built", "candles": len(candles), "events": len(events)})
        parquet_path = temp_dir / "raw_4h_pivots.parquet"
        write_pivot_parquet(parquet_path, events)
        definitions = _column_definitions()
        schema = {"schema_version": "raw-4h-pivots-v1", "stage_version": STAGE_VERSION,
                  "causal_contract": {"available_from": "close of second right-hand 4H candle",
                                      "causal_prefix": "causal__", "postevent_prefix": "postevent__",
                                      "postevent_policy": "diagnostic/outcome only; never predictors at pivot time"},
                  "columns": [{**asdict(item), "arrow_type": str(item.arrow_type)} for item in definitions]}
        _json(temp_dir / "raw_4h_pivots_schema.json", schema)
        qa = _qa(candles, events, parquet_path)
        null_counts = {definition.name: sum(event.get(definition.name) is None for event in events) for definition in definitions}
        counts = {"candles_analyzed": len(candles), "pivots_total": len(events),
                  "high_pivots": sum(event["pivot_type"] == "HIGH" for event in events),
                  "low_pivots": sum(event["pivot_type"] == "LOW" for event in events),
                  "dual_event_candles": len({event["pivot_bar_index"] for event in events if event["causal__dual_high_low_same_candle"]}),
                  "contiguous_runs": len({bar.run_id for bar in candles})}
        years: Dict[str, Dict[str, int]] = {}
        for event in events:
            year = str(event["pivot_timestamp"].year)
            years.setdefault(year, {"HIGH": 0, "LOW": 0, "total": 0})
            years[year][str(event["pivot_type"])] += 1
            years[year]["total"] += 1
        event_bar_gaps = [float(events[i]["pivot_bar_index"] - events[i - 1]["pivot_bar_index"])
                          for i in range(1, len(events)) if events[i]["pivot_bar_index"] > events[i - 1]["pivot_bar_index"]]
        event_time_gaps = [(events[i]["pivot_timestamp"] - events[i - 1]["pivot_timestamp"]).total_seconds() / 3600.0
                           for i in range(1, len(events)) if events[i]["pivot_timestamp"] > events[i - 1]["pivot_timestamp"]]
        prev_opp_bars = [float(event["causal__previous_opposite__bar_distance"]) for event in events
                         if event["causal__previous_opposite__bar_distance"] is not None]
        next_opp_bars = [float(event["postevent__next_opposite__bar_distance"]) for event in events
                         if event["postevent__next_opposite__bar_distance"] is not None]
        prev_opp_move = [float(event["causal__from_previous_opposite__absolute_endpoint_move"]) for event in events
                         if event["causal__from_previous_opposite__absolute_endpoint_move"] is not None]
        prev_opp_duration = [float(event["causal__from_previous_opposite__duration_hours"]) for event in events
                             if event["causal__from_previous_opposite__duration_hours"] is not None]
        report = {"stage_version": STAGE_VERSION, "mode": mode, "source": source, "counts": counts,
                  "pivots_per_year": years,
                  "pivot_frequency": {"events_per_100_complete_bars": 100.0 * len(events) / len(candles) if candles else None,
                                      "consecutive_distinct_pivot_bar_gap": _summary(event_bar_gaps),
                                      "consecutive_distinct_pivot_time_gap_hours": _summary(event_time_gaps)},
                  "pivot_price_summary": _summary([float(event["pivot_price"]) for event in events]),
                  "neighbor_opposite_distributions": {"previous_bar_distance": _summary(prev_opp_bars),
                                                      "next_bar_distance": _summary(next_opp_bars),
                                                      "absolute_move": _summary(prev_opp_move),
                                                      "duration_hours": _summary(prev_opp_duration)},
                  "null_counts": null_counts,
                  "outliers": {"largest_previous_opposite_move": _largest(events, "causal__from_previous_opposite__absolute_endpoint_move"),
                               "longest_previous_opposite_duration": _largest(events, "causal__from_previous_opposite__duration_hours")},
                  "sample_sequences": _event_sequences(events), "qa_failures": [name for name, passed in qa["checks"].items() if not passed],
                  "qa": qa}
        _json(temp_dir / "stage2i_a_report.json", report)
        windows = (("2020-03-01", "2020-04-15"), ("2021-04-15", "2021-06-01"),
                   ("2022-05-01", "2022-06-15"), ("2024-02-15", "2024-04-01"),
                   ("2026-07-15", "2026-09-27"))
        for start_text, end_text in windows:
            start = datetime.fromisoformat(start_text).replace(tzinfo=UTC)
            end = datetime.fromisoformat(end_text).replace(tzinfo=UTC)
            _svg_plot(temp_dir / f"qa_pivots_{start_text}_{end_text}.svg", candles, events, start, end,
                      f"BTCUSDT raw 4H pivots: {start_text} to {end_text}")
        code_path = Path(__file__).resolve()
        git_head = stamp or _git(repo_root, "rev-parse", "HEAD")
        dirty = bool(_git(repo_root, "status", "--porcelain"))
        artifacts = sorted(path.name for path in temp_dir.iterdir() if path.name != "progress.json")
        artifact_hashes = {name: _sha256(temp_dir / name) for name in artifacts}
        manifest = {"stage_version": STAGE_VERSION, "mode": mode, "run_id": hashlib.sha256(
                        (source["manifest_sha256"] + _sha256(code_path) + mode).encode()).hexdigest()[:16],
                    "git_commit": git_head, "git_worktree_dirty_at_build": dirty,
                    "pipeline_path": str(code_path), "pipeline_sha256": _sha256(code_path),
                    "source_manifest_path": source["manifest_path"], "source_manifest_sha256": source["manifest_sha256"],
                    "config": {"strict_window": 5, "left_bars": 2, "right_bars": 2,
                               "horizons": list(HORIZONS), "incomplete_candles": "excluded"},
                    "counts": counts, "qa_status": qa["status"], "artifacts": artifact_hashes}
        _json(temp_dir / "manifest.json", manifest)
        checksum_names = sorted(path.name for path in temp_dir.iterdir() if path.name not in {"checksums.sha256", "progress.json"})
        (temp_dir / "checksums.sha256").write_text("".join(f"{_sha256(temp_dir / name)}  {name}\n" for name in checksum_names), encoding="utf-8")
        _json(temp_dir / "progress.json", {"stage": "qa_complete", "qa_status": qa["status"], "counts": counts})
        if qa["status"] != "PASS": raise RuntimeError("Stage 2I-A QA failed")
        backup = output_dir.with_name(output_dir.name + ".previous")
        if backup.exists(): shutil.rmtree(backup)
        if output_dir.exists(): os.replace(output_dir, backup)
        os.replace(temp_dir, output_dir)
        if backup.exists(): shutil.rmtree(backup)
        return report
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--mode", choices=("smoke", "production"), default="production")
    parser.add_argument("--stamp-git-commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candles, source = _load_source(args.data_root)
    if args.mode == "smoke": candles = candles[:600]
    events = build_raw_pivot_rows(candles, source["manifest_sha256"])
    output = args.output_dir or args.data_root / "research" / "stage2i_a_raw_4h_pivots"
    report = _write_outputs(output, candles, events, source, args.repo_root, args.mode, args.stamp_git_commit)
    print(json.dumps({"output": str(output), "counts": report["counts"], "qa": report["qa"]["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
