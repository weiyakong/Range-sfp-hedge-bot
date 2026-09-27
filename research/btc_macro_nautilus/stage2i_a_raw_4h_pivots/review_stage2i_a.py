#!/usr/bin/env python3
"""Diagnostic review of Stage 2I-A raw 4H pivots; no labels or filtering."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


REVIEW_VERSION = "stage2i-a-pivot-structure-review-v1"
EXPECTED_STAGE_A_COMMIT = "71b6158a61503fde9145f3565fe0be3149bbab76"
UTC = timezone.utc


@dataclass(frozen=True)
class Candle:
    index: int
    timestamp: datetime
    end_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int


@dataclass(frozen=True)
class PivotEvent:
    event_id: str
    bar_index: int
    timestamp: datetime
    available_from: datetime
    pivot_type: str
    price: float
    dual: bool
    fields: Mapping[str, Any]


def _utc(value: Any) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value)!r}")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _float(value: Any) -> Optional[float]:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def describe(values: Iterable[float]) -> Dict[str, Optional[float]]:
    array = np.asarray([float(value) for value in values if math.isfinite(float(value))], dtype=float)
    if array.size == 0:
        return {key: None for key in ("count", "min", "p01", "p10", "p25", "median", "p75", "p90", "p99", "max", "mean", "std")}
    quantiles = np.quantile(array, [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99])
    return {
        "count": int(array.size), "min": float(np.min(array)), "p01": float(quantiles[0]),
        "p10": float(quantiles[1]), "p25": float(quantiles[2]), "median": float(quantiles[3]),
        "p75": float(quantiles[4]), "p90": float(quantiles[5]), "p99": float(quantiles[6]),
        "max": float(np.max(array)), "mean": float(np.mean(array)), "std": float(np.std(array)),
    }


def gap_bucket(bar_gap: int) -> str:
    if bar_gap == 0:
        return "same_candle"
    if bar_gap == 1:
        return "adjacent_candles"
    if bar_gap == 2:
        return "one_intervening_bar"
    if bar_gap == 3:
        return "two_intervening_bars"
    if 4 <= bar_gap <= 6:
        return "three_to_five_intervening_bars"
    if 7 <= bar_gap <= 13:
        return "six_to_twelve_intervening_bars"
    return "more_than_twelve_intervening_bars"


def bars_to_breach(candles: Sequence[Candle], pivot_index: int, pivot_type: str,
                   pivot_price: float) -> Optional[int]:
    for offset, candle in enumerate(candles[pivot_index + 1:], start=1):
        if pivot_type == "HIGH" and candle.high > pivot_price:
            return offset
        if pivot_type == "LOW" and candle.low < pivot_price:
            return offset
    return None


def pair_geometry(candles: Sequence[Candle], start_index: int, end_index: int,
                  start_price: float, end_price: float) -> Dict[str, Optional[float]]:
    if end_index <= start_index:
        raise ValueError("Pair geometry requires strictly increasing bar indices")
    window = candles[start_index:end_index + 1]
    closes = [candle.close for candle in window]
    close_path = sum(abs(right - left) for left, right in zip(closes, closes[1:]))
    log_closes = [math.log(value) for value in closes]
    log_path = sum(abs(right - left) for left, right in zip(log_closes, log_closes[1:]))
    signed_move = end_price - start_price
    log_move = math.log(end_price / start_price)
    direction = 1 if signed_move > 0 else -1
    steps = np.diff(np.asarray(log_closes))
    signs = np.sign(steps).astype(int)
    directional_signs = signs * direction
    nonzero = signs[signs != 0]
    changes = int(np.sum(nonzero[1:] != nonzero[:-1])) if nonzero.size > 1 else 0
    body_overlaps = []
    for previous, current in zip(window[:-1], window[1:]):
        previous_low, previous_high = sorted((previous.open, previous.close))
        current_low, current_high = sorted((current.open, current.close))
        body_overlaps.append(max(0.0, min(previous_high, current_high) - max(previous_low, current_low)))
    start_open = window[0].open
    favourable = [max(direction * math.log(candle.high / start_open),
                      direction * math.log(candle.low / start_open)) for candle in window]
    maximum_favourable = max(0.0, max(favourable))
    final_progress = direction * math.log(window[-1].close / start_open)
    return {
        "signed_pivot_move": signed_move,
        "absolute_pivot_move": abs(signed_move),
        "signed_percentage_move": 100.0 * signed_move / start_price,
        "absolute_percentage_move": 100.0 * abs(signed_move) / start_price,
        "signed_log_move": log_move,
        "absolute_log_move": abs(log_move),
        "duration_bars": float(end_index - start_index),
        "duration_hours": 4.0 * (end_index - start_index),
        "duration_days": (end_index - start_index) / 6.0,
        "price_excursion": max(candle.high for candle in window) - min(candle.low for candle in window),
        "price_excursion_pct_start": 100.0 * (max(candle.high for candle in window) - min(candle.low for candle in window)) / start_price,
        "close_path": close_path,
        "log_close_path": log_path,
        "close_path_efficiency": abs(closes[-1] - closes[0]) / close_path if close_path else None,
        "log_close_path_efficiency": abs(log_closes[-1] - log_closes[0]) / log_path if log_path else None,
        "directional_persistence": float(np.mean(directional_signs)),
        "alternation": float(changes / (nonzero.size - 1)) if nonzero.size > 1 else 0.0,
        "body_overlap_mean": float(np.mean(body_overlaps)) if body_overlaps else None,
        "maximum_favourable_excursion_log": maximum_favourable,
        "retracement_from_internal_extreme_log": maximum_favourable - final_progress,
        "end_retention": final_progress / maximum_favourable if maximum_favourable > np.finfo(float).eps else 0.0,
    }


def dual_geometry(candles: Sequence[Candle], center_index: int) -> Dict[str, Optional[float]]:
    if center_index < 2 or center_index + 2 >= len(candles):
        raise ValueError("Dual geometry requires two neighboring candles on each side")
    center = candles[center_index]
    neighbors = [candles[center_index - 2], candles[center_index - 1],
                 candles[center_index + 1], candles[center_index + 2]]
    center_range = center.high - center.low
    neighbor_ranges = [candle.high - candle.low for candle in neighbors]
    neighbor_volume = float(np.mean([candle.volume for candle in neighbors]))
    neighbor_trades = float(np.mean([candle.trade_count for candle in neighbors]))
    return {
        "center_range": center_range,
        "center_range_pct": 100.0 * center_range / center.close,
        "center_body_to_range": abs(center.close - center.open) / center_range if center_range else None,
        "center_upper_wick_to_range": (center.high - max(center.open, center.close)) / center_range if center_range else None,
        "center_lower_wick_to_range": (min(center.open, center.close) - center.low) / center_range if center_range else None,
        "neighbor_mean_range": float(np.mean(neighbor_ranges)),
        "center_to_neighbor_mean_range_ratio": center_range / float(np.mean(neighbor_ranges)) if np.mean(neighbor_ranges) else None,
        "high_extension": center.high - max(candle.high for candle in neighbors),
        "low_extension": min(candle.low for candle in neighbors) - center.low,
        "center_to_neighbor_mean_volume_ratio": center.volume / neighbor_volume if neighbor_volume else None,
        "center_to_neighbor_mean_trade_count_ratio": center.trade_count / neighbor_trades if neighbor_trades else None,
        "open_gap_from_previous_close_pct": 100.0 * (center.open - candles[center_index - 1].close) / candles[center_index - 1].close,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _validate_stage_a_checksums(stage_dir: Path) -> None:
    for line in (stage_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if _sha256(stage_dir / name) != expected:
            raise RuntimeError(f"Stage 2I-A checksum mismatch: {name}")


def _load_candles(data_root: Path) -> Tuple[List[Candle], Dict[str, Any]]:
    source_dir = data_root / "derived" / "BTCUSDT" / "4h"
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candles: List[Candle] = []
    all_rows = 0
    for item in manifest["output_files"]:
        path = Path(item["path"])
        if _sha256(path) != item["sha256"]:
            raise RuntimeError(f"Canonical source checksum mismatch: {path}")
        table = pq.read_table(path, columns=["start_time", "end_time", "open", "high", "low", "close",
                                                   "volume", "trade_count", "complete"])
        if table.num_rows != int(item["rows"]):
            raise RuntimeError(f"Canonical source row-count mismatch: {path}")
        for row in table.to_pylist():
            all_rows += 1
            if not row["complete"]:
                continue
            candles.append(Candle(
                index=len(candles), timestamp=_utc(row["start_time"]), end_time=_utc(row["end_time"]),
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row["volume"]), trade_count=int(row["trade_count"]),
            ))
    if all_rows != int(manifest["total_rows"]) or len(candles) != int(manifest["complete_rows"]):
        raise RuntimeError("Canonical population differs from manifest")
    for left, right in zip(candles, candles[1:]):
        if left.end_time != right.timestamp:
            raise RuntimeError("Unexpected gap inside complete 4H population")
    return candles, {"path": str(manifest_path), "sha256": _sha256(manifest_path),
                     "total_rows": all_rows, "complete_rows": len(candles),
                     "incomplete_rows": all_rows - len(candles)}


def _load_pivots(stage_dir: Path) -> Tuple[List[PivotEvent], Dict[str, Any]]:
    _validate_stage_a_checksums(stage_dir)
    manifest_path = stage_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = str(manifest["git_commit"])
    if not EXPECTED_STAGE_A_COMMIT.startswith(commit):
        raise RuntimeError(f"Unexpected Stage 2I-A commit: {commit}")
    table = pq.read_table(stage_dir / "raw_4h_pivots.parquet")
    required = {
        "event_id", "pivot_bar_index", "pivot_timestamp", "available_from", "pivot_type", "pivot_price",
        "causal__dual_high_low_same_candle", "causal__previous_opposite__event_id",
        "causal__previous_opposite__bar_distance", "causal__previous_opposite__absolute_price_change",
        "causal__previous_opposite__percentage_price_change", "causal__previous_same__pivot_price",
        "postevent__next_opposite__event_id", "postevent__next_opposite__bar_distance",
        "postevent__next_opposite__absolute_price_change", "postevent__next_opposite__percentage_price_change",
        "causal__from_previous_opposite__close_path", "causal__from_previous_opposite__close_efficiency",
    }
    missing = sorted(required - set(table.column_names))
    if missing:
        raise RuntimeError(f"Stage 2I-A schema missing required columns: {missing}")
    events = [PivotEvent(
        event_id=str(row["event_id"]), bar_index=int(row["pivot_bar_index"]),
        timestamp=_utc(row["pivot_timestamp"]), available_from=_utc(row["available_from"]),
        pivot_type=str(row["pivot_type"]), price=float(row["pivot_price"]),
        dual=bool(row["causal__dual_high_low_same_candle"]), fields=row,
    ) for row in table.to_pylist()]
    if len(events) != 4450 or len({event.event_id for event in events}) != len(events):
        raise RuntimeError("Stage 2I-A pivot population/uniqueness mismatch")
    if events != sorted(events, key=lambda event: (event.bar_index, 0 if event.pivot_type == "HIGH" else 1)):
        raise RuntimeError("Stage 2I-A events are not chronologically ordered")
    counts = Counter(event.pivot_type for event in events)
    if counts != {"HIGH": 2243, "LOW": 2207}:
        raise RuntimeError(f"Stage 2I-A type counts mismatch: {counts}")
    return events, {"path": str(stage_dir / "raw_4h_pivots.parquet"),
                    "sha256": _sha256(stage_dir / "raw_4h_pivots.parquet"),
                    "manifest_path": str(manifest_path), "manifest_sha256": _sha256(manifest_path),
                    "git_commit": commit, "rows": len(events), "columns": table.num_columns}


def _consecutive_pairs(events: Sequence[PivotEvent]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for left, right in zip(events, events[1:]):
        gap = right.bar_index - left.bar_index
        rows.append({
            "from_event_id": left.event_id, "to_event_id": right.event_id,
            "from_type": left.pivot_type, "to_type": right.pivot_type,
            "transition": f"{left.pivot_type}_TO_{right.pivot_type}",
            "from_timestamp": left.timestamp, "to_timestamp": right.timestamp,
            "bar_gap": gap, "intervening_bars": max(0, gap - 1),
            "time_gap_hours": (right.timestamp - left.timestamp).total_seconds() / 3600.0,
            "gap_bucket": gap_bucket(gap), "same_candle_dual_pair": gap == 0,
        })
    return rows


def _opposite_pairs(events: Sequence[PivotEvent], candles: Sequence[Candle]) -> List[Dict[str, Any]]:
    by_id = {event.event_id: event for event in events}
    rows: List[Dict[str, Any]] = []
    for event in events:
        next_id = event.fields.get("postevent__next_opposite__event_id")
        if next_id is None or str(next_id) not in by_id:
            continue
        following = by_id[str(next_id)]
        geometry = pair_geometry(candles, event.bar_index, following.bar_index, event.price, following.price)
        rows.append({"pair_id": f"{event.event_id}__{following.event_id}",
                     "from_event_id": event.event_id, "to_event_id": following.event_id,
                     "from_type": event.pivot_type, "to_type": following.pivot_type,
                     "from_timestamp": event.timestamp, "to_timestamp": following.timestamp,
                     "calendar_year": event.timestamp.year, **geometry})
    return rows


def _event_diagnostics(events: Sequence[PivotEvent], candles: Sequence[Candle],
                       opposite_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    outgoing = {str(row["from_event_id"]): row for row in opposite_rows}
    by_id = {event.event_id: event for event in events}
    rows: List[Dict[str, Any]] = []
    for position, event in enumerate(events):
        incoming_abs = _float(event.fields.get("causal__previous_opposite__absolute_price_change"))
        incoming_pct_signed = _float(event.fields.get("causal__previous_opposite__percentage_price_change"))
        incoming_bars = _float(event.fields.get("causal__previous_opposite__bar_distance"))
        out = outgoing.get(event.event_id)
        previous_id = event.fields.get("causal__previous_opposite__event_id")
        previous = by_id.get(str(previous_id)) if previous_id is not None else None
        incoming_geometry = pair_geometry(candles, previous.bar_index, event.bar_index, previous.price, event.price) if previous else None
        outgoing_abs = _float(out.get("absolute_pivot_move")) if out else None
        outgoing_pct = _float(out.get("absolute_percentage_move")) if out else None
        outgoing_bars = _float(out.get("duration_bars")) if out else None
        previous_same_price = _float(event.fields.get("causal__previous_same__pivot_price"))
        if previous_same_price is None:
            extension = None
        elif event.pivot_type == "HIGH":
            extension = event.price - previous_same_price
        else:
            extension = previous_same_price - event.price
        start = max(0, event.bar_index - 2)
        end = min(len(candles), event.bar_index + 3)
        context = candles[start:end]
        context_span = max(candle.high for candle in context) - min(candle.low for candle in context)
        breach = bars_to_breach(candles, event.bar_index, event.pivot_type, event.price)
        three = events[position:position + 3]
        five = events[position:position + 5]
        three_span = max((item.price for item in three), default=event.price) - min((item.price for item in three), default=event.price)
        five_span = max((item.price for item in five), default=event.price) - min((item.price for item in five), default=event.price)
        horizon6_range = _float(event.fields.get("postevent__horizon_6__range_traversed"))
        horizon12_range = _float(event.fields.get("postevent__horizon_12__range_traversed"))
        rows.append({
            "event_id": event.event_id, "pivot_timestamp": event.timestamp, "pivot_type": event.pivot_type,
            "pivot_price": event.price, "dual": event.dual,
            "incoming_opposite_move_abs": incoming_abs,
            "incoming_opposite_move_pct_abs": abs(incoming_pct_signed) if incoming_pct_signed is not None else None,
            "incoming_duration_bars": incoming_bars,
            "incoming_path_efficiency": _float(event.fields.get("causal__from_previous_opposite__close_efficiency")),
            "incoming_path_efficiency_recomputed": _float(incoming_geometry.get("close_path_efficiency")) if incoming_geometry else None,
            "incoming_directional_persistence": _float(incoming_geometry.get("directional_persistence")) if incoming_geometry else None,
            "incoming_alternation": _float(incoming_geometry.get("alternation")) if incoming_geometry else None,
            "incoming_body_overlap_mean": _float(incoming_geometry.get("body_overlap_mean")) if incoming_geometry else None,
            "incoming_retracement_from_internal_extreme_log": _float(incoming_geometry.get("retracement_from_internal_extreme_log")) if incoming_geometry else None,
            "outgoing_opposite_move_abs": outgoing_abs, "outgoing_opposite_move_pct_abs": outgoing_pct,
            "outgoing_duration_bars": outgoing_bars,
            "outgoing_path_efficiency": _float(out.get("close_path_efficiency")) if out else None,
            "outgoing_directional_persistence": _float(out.get("directional_persistence")) if out else None,
            "outgoing_alternation": _float(out.get("alternation")) if out else None,
            "outgoing_body_overlap_mean": _float(out.get("body_overlap_mean")) if out else None,
            "outgoing_retracement_from_internal_extreme_log": _float(out.get("retracement_from_internal_extreme_log")) if out else None,
            "outgoing_to_incoming_move_ratio": _safe_ratio(outgoing_abs, incoming_abs),
            "outgoing_to_incoming_duration_ratio": _safe_ratio(outgoing_bars, incoming_bars),
            "same_type_extension_abs": extension,
            "same_type_extension_pct": 100.0 * extension / previous_same_price if extension is not None and previous_same_price else None,
            "bars_to_strict_pivot_price_breach": breach,
            "center_range_pct": 100.0 * (candles[event.bar_index].high - candles[event.bar_index].low) / event.price,
            "five_bar_context_span_pct": 100.0 * context_span / event.price,
            "postevent_h6_range_pct": 100.0 * horizon6_range / event.price if horizon6_range is not None else None,
            "postevent_h12_range_pct": 100.0 * horizon12_range / event.price if horizon12_range is not None else None,
            "three_consecutive_event_price_span_pct": 100.0 * three_span / event.price if len(three) == 3 else None,
            "five_consecutive_event_price_span_pct": 100.0 * five_span / event.price if len(five) == 5 else None,
            "previous_opposite_event_exists": event.fields.get("causal__previous_opposite__event_id") in by_id,
            "next_opposite_event_exists": event.fields.get("postevent__next_opposite__event_id") in by_id,
        })
    return rows


def _dual_rows(events: Sequence[PivotEvent], candles: Sequence[Candle]) -> List[Dict[str, Any]]:
    indices = sorted({event.bar_index for event in events if event.dual})
    return [{"bar_index": index, "timestamp": candles[index].timestamp, **dual_geometry(candles, index)} for index in indices]


def _pivot_candle_geometry_rows(events: Sequence[PivotEvent], candles: Sequence[Candle]) -> List[Dict[str, Any]]:
    by_index: Dict[int, bool] = {}
    for event in events:
        by_index[event.bar_index] = by_index.get(event.bar_index, False) or event.dual
    return [{"bar_index": index, "timestamp": candles[index].timestamp, "dual": dual,
             **dual_geometry(candles, index)} for index, dual in sorted(by_index.items())]


def _summaries_by_group(rows: Sequence[Mapping[str, Any]], group_field: str,
                        value_fields: Sequence[str]) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group_field])].append(row)
    result: Dict[str, Any] = {}
    for group, group_rows in sorted(grouped.items()):
        result[group] = {field: describe(float(row[field]) for row in group_rows if row.get(field) is not None)
                         for field in value_fields}
    return result


def _continuity_diagnostic(values: Sequence[float]) -> Dict[str, Optional[float]]:
    array = np.sort(np.asarray([float(value) for value in values if math.isfinite(float(value))], dtype=float))
    if array.size < 3:
        return {"central_count": int(array.size), "largest_adjacent_gap": None,
                "gap_lower_value": None, "gap_upper_value": None, "largest_gap_over_iqr": None}
    low, high = np.quantile(array, [0.01, 0.99])
    central = array[(array >= low) & (array <= high)]
    gaps = np.diff(central)
    index = int(np.argmax(gaps))
    iqr = float(np.quantile(array, 0.75) - np.quantile(array, 0.25))
    return {"central_count": int(central.size), "central_p01": float(low), "central_p99": float(high),
            "largest_adjacent_gap": float(gaps[index]), "gap_lower_value": float(central[index]),
            "gap_upper_value": float(central[index + 1]),
            "largest_gap_over_iqr": float(gaps[index] / iqr) if iqr else None}


def _year_rows(candles: Sequence[Candle], events: Sequence[PivotEvent],
               opposite_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    candle_counts = Counter(candle.timestamp.year for candle in candles)
    event_counts = Counter(event.timestamp.year for event in events)
    bearing_counts = Counter((year, index) for year, index in {(event.timestamp.year, event.bar_index) for event in events})
    rows: List[Dict[str, Any]] = []
    for year in sorted(candle_counts):
        year_pairs = [row for row in opposite_rows if int(row["calendar_year"]) == year]
        rows.append({
            "year": year, "complete_candles": candle_counts[year], "pivot_events": event_counts[year],
            "pivot_bearing_candles": sum(1 for key in bearing_counts if key[0] == year),
            "events_per_100_bars": 100.0 * event_counts[year] / candle_counts[year],
            "pivot_candles_per_100_bars": 100.0 * sum(1 for key in bearing_counts if key[0] == year) / candle_counts[year],
            "opposite_abs_move_median": describe(float(row["absolute_pivot_move"]) for row in year_pairs)["median"],
            "opposite_pct_move_median": describe(float(row["absolute_percentage_move"]) for row in year_pairs)["median"],
            "opposite_duration_bars_median": describe(float(row["duration_bars"]) for row in year_pairs)["median"],
            "opposite_close_efficiency_median": describe(float(row["close_path_efficiency"]) for row in year_pairs
                                                           if row["close_path_efficiency"] is not None)["median"],
        })
    return rows


def _window_metrics(candles: Sequence[Candle], events: Sequence[PivotEvent], window: int = 90) -> List[Dict[str, Any]]:
    pivot_indices = [event.bar_index for event in events]
    results: List[Dict[str, Any]] = []
    for start in range(0, len(candles) - window + 1, 6):
        end = start + window
        event_count = sum(start <= index < end for index in pivot_indices)
        bearing_count = len({index for index in pivot_indices if start <= index < end})
        closes = [candle.close for candle in candles[start:end]]
        path = sum(abs(right - left) for left, right in zip(closes, closes[1:]))
        efficiency = abs(closes[-1] - closes[0]) / path if path else 0.0
        pct_move = 100.0 * abs(closes[-1] - closes[0]) / closes[0]
        price_span_pct = 100.0 * (max(c.high for c in candles[start:end]) - min(c.low for c in candles[start:end])) / closes[0]
        results.append({"start_index": start, "end_index_exclusive": end,
                        "start_time": candles[start].timestamp, "end_time_exclusive": candles[end - 1].end_time,
                        "event_count": event_count, "pivot_bearing_candles": bearing_count,
                        "close_path_efficiency": efficiency, "absolute_close_move_pct": pct_move,
                        "price_span_pct": price_span_pct,
                        "directional_selection_score": efficiency * pct_move * math.log1p(event_count),
                        "choppy_selection_score": ((1.0 - efficiency) * price_span_pct * math.log1p(event_count) /
                                                   (1.0 + pct_move))})
    return results


def _select_chart_windows(candles: Sequence[Candle], events: Sequence[PivotEvent],
                          diagnostics: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    windows = _window_metrics(candles, events)
    chosen: List[Dict[str, Any]] = []
    used: set[int] = set()

    def take(label: str, candidates: Sequence[Mapping[str, Any]], reverse: bool, field: str) -> None:
        ordered = sorted(candidates, key=lambda row: float(row[field]), reverse=reverse)
        for candidate in ordered:
            start = int(candidate["start_index"])
            if all(abs(start - existing) >= 45 for existing in used):
                chosen.append({"chart_id": label, "selection_metric": field, **candidate})
                used.add(start)
                return

    take("high_pivot_density", windows, True, "event_count")
    take("low_pivot_density", windows, False, "event_count")
    eligible = [row for row in windows if int(row["event_count"]) >= 6]
    take("high_directional_efficiency_with_raw_pivots", eligible, True, "directional_selection_score")
    take("low_efficiency_high_path_window", eligible, True, "choppy_selection_score")
    two_sided = [row for row in diagnostics if row.get("incoming_opposite_move_pct_abs") is not None and
                 row.get("outgoing_opposite_move_pct_abs") is not None]
    reversal_event = max(two_sided, key=lambda row: min(float(row["incoming_opposite_move_pct_abs"]),
                                                        float(row["outgoing_opposite_move_pct_abs"])))
    center = next(event.bar_index for event in events if event.event_id == reversal_event["event_id"])
    start = max(0, min(len(candles) - 90, center - 45))
    window_row = next(min(windows, key=lambda row: abs(int(row["start_index"]) - start)) for _ in [0])
    chosen.append({"chart_id": "large_two_sided_opposite_move", "selection_metric": "min_incoming_outgoing_pct",
                   "selection_value": min(float(reversal_event["incoming_opposite_move_pct_abs"]),
                                          float(reversal_event["outgoing_opposite_move_pct_abs"])), **window_row})
    start_time = datetime(2026, 6, 1, tzinfo=UTC)
    end_time = datetime(2026, 7, 16, tzinfo=UTC)
    start_idx = next(i for i, candle in enumerate(candles) if candle.timestamp >= start_time)
    end_idx = next(i for i, candle in enumerate(candles) if candle.timestamp >= end_time)
    chosen.append({"chart_id": "2026_human_calibration_area", "selection_metric": "fixed_user_calibration_period",
                   "start_index": start_idx, "end_index_exclusive": end_idx,
                   "start_time": candles[start_idx].timestamp, "end_time_exclusive": candles[end_idx - 1].end_time,
                   "event_count": sum(start_idx <= event.bar_index < end_idx for event in events),
                   "pivot_bearing_candles": len({event.bar_index for event in events if start_idx <= event.bar_index < end_idx}),
                   "close_path_efficiency": None, "absolute_close_move_pct": None, "price_span_pct": None})
    return chosen


def candlestick_svg(candles: Sequence[Candle], pivots: Sequence[PivotEvent], title: str) -> str:
    width, height, left, right, top, bottom = 1400, 560, 68, 24, 42, 42
    if not candles:
        raise ValueError("Cannot plot an empty candle window")
    low, high = min(candle.low for candle in candles), max(candle.high for candle in candles)
    span = high - low or 1.0
    x = lambda i: left + (i + 0.5) * (width - left - right) / len(candles)
    y = lambda price: top + (high - price) * (height - top - bottom) / span
    candle_width = max(1.0, min(7.0, (width - left - right) / len(candles) * 0.65))
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                f'<text x="{left}" y="24" font-family="sans-serif" font-size="16">{html.escape(title)}</text>']
    for level in range(6):
        price = low + span * level / 5
        yy = y(price)
        elements.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{width-right}" y2="{yy:.2f}" stroke="#e5e7eb"/>')
        elements.append(f'<text x="4" y="{yy+4:.2f}" font-family="sans-serif" font-size="11">{price:,.0f}</text>')
    position = {candle.index: i for i, candle in enumerate(candles)}
    for i, candle in enumerate(candles):
        xx = x(i)
        color = "#16a34a" if candle.close >= candle.open else "#dc2626"
        body_top = min(y(candle.open), y(candle.close))
        body_height = max(1.0, abs(y(candle.open) - y(candle.close)))
        elements.append(f'<line x1="{xx:.2f}" y1="{y(candle.high):.2f}" x2="{xx:.2f}" y2="{y(candle.low):.2f}" stroke="{color}"/>')
        elements.append(f'<rect x="{xx-candle_width/2:.2f}" y="{body_top:.2f}" width="{candle_width:.2f}" height="{body_height:.2f}" fill="{color}"/>')
    for event in pivots:
        if event.bar_index not in position:
            continue
        xx = x(position[event.bar_index])
        yy = y(event.price)
        if event.pivot_type == "HIGH":
            points = f"{xx:.2f},{yy-8:.2f} {xx-5:.2f},{yy-1:.2f} {xx+5:.2f},{yy-1:.2f}"
            color = "#7c3aed"
        else:
            points = f"{xx:.2f},{yy+8:.2f} {xx-5:.2f},{yy+1:.2f} {xx+5:.2f},{yy+1:.2f}"
            color = "#0284c7"
        elements.append(f'<polygon points="{points}" fill="{color}"/>')
    elements.append(f'<text x="{left}" y="{height-10}" font-family="sans-serif" font-size="11">Purple=raw HIGH; blue=raw LOW; no structural labels</text>')
    elements.append("</svg>")
    return "".join(elements)


def write_candlestick_svg(path: Path, candles: Sequence[Candle], pivots: Sequence[PivotEvent], title: str) -> None:
    path.write_text(candlestick_svg(candles, pivots, title), encoding="utf-8")


def _write_distribution_svg(path: Path, values: Sequence[float], title: str, x_label: str) -> None:
    clean = np.asarray([float(value) for value in values if math.isfinite(float(value))], dtype=float)
    if clean.size == 0:
        raise ValueError("Cannot plot empty distribution")
    width, height = 1100, 480
    left, right, top, bottom = 58, 24, 42, 46
    hist_right = 530
    counts, edges = np.histogram(clean, bins=min(40, max(10, int(math.sqrt(clean.size)))))
    max_count = max(counts) or 1
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                f'<text x="{left}" y="24" font-family="sans-serif" font-size="16">{html.escape(title)}</text>']
    plot_height = height - top - bottom
    for i, count in enumerate(counts):
        x0 = left + i * (hist_right - left) / len(counts)
        x1 = left + (i + 1) * (hist_right - left) / len(counts)
        bar_height = plot_height * count / max_count
        elements.append(f'<rect x="{x0:.2f}" y="{height-bottom-bar_height:.2f}" width="{max(1,x1-x0-1):.2f}" height="{bar_height:.2f}" fill="#64748b"/>')
    sorted_values = np.sort(clean)
    ecdf_left, ecdf_right = 610, width - right
    vmin, vmax = float(sorted_values[0]), float(sorted_values[-1])
    value_span = vmax - vmin or 1.0
    points = " ".join(f"{ecdf_left+(value-vmin)*(ecdf_right-ecdf_left)/value_span:.2f},{height-bottom-(i+1)*plot_height/len(sorted_values):.2f}"
                      for i, value in enumerate(sorted_values))
    elements.append(f'<polyline fill="none" stroke="#2563eb" stroke-width="1.5" points="{points}"/>')
    elements.extend([f'<text x="{left}" y="{height-12}" font-family="sans-serif" font-size="11">Histogram: {html.escape(x_label)}</text>',
                     f'<text x="{ecdf_left}" y="{height-12}" font-family="sans-serif" font-size="11">Empirical CDF: {html.escape(x_label)}</text>',
                     '</svg>'])
    path.write_text("".join(elements), encoding="utf-8")


def _write_year_svg(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    width, height, left, bottom = 1100, 480, 62, 48
    metrics = ("events_per_100_bars", "opposite_pct_move_median", "opposite_duration_bars_median")
    colors = ("#334155", "#2563eb", "#ea580c")
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                '<text x="62" y="24" font-family="sans-serif" font-size="16">Year comparison (each metric independently scaled)</text>']
    group_width = (width - left - 24) / len(rows)
    for metric_index, (metric, color) in enumerate(zip(metrics, colors)):
        maximum = max(float(row[metric]) for row in rows) or 1.0
        for index, row in enumerate(rows):
            value = float(row[metric])
            bar_width = group_width / 4
            x = left + index * group_width + metric_index * bar_width
            bar_height = value / maximum * 340
            elements.append(f'<rect x="{x:.2f}" y="{height-bottom-bar_height:.2f}" width="{bar_width-2:.2f}" height="{bar_height:.2f}" fill="{color}"/>')
    for index, row in enumerate(rows):
        elements.append(f'<text x="{left+index*group_width:.2f}" y="{height-18}" font-family="sans-serif" font-size="11">{row["year"]}</text>')
    for index, (metric, color) in enumerate(zip(metrics, colors)):
        elements.append(f'<text x="{left+index*300}" y="45" font-family="sans-serif" font-size="11" fill="{color}">{metric}</text>')
    elements.append('</svg>')
    path.write_text("".join(elements), encoding="utf-8")


def _calibration_summary(events: Sequence[PivotEvent], diagnostics: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    diagnostic_by_id = {str(row["event_id"]): row for row in diagnostics}
    areas = ((59000.0, 60500.0), (61500.0, 62500.0), (66500.0, 69000.0))
    result: Dict[str, Any] = {}
    for low, high in areas:
        selected = [event for event in events if event.timestamp.year == 2026 and low <= event.price <= high]
        incoming = [float(diagnostic_by_id[event.event_id]["incoming_opposite_move_pct_abs"]) for event in selected
                    if diagnostic_by_id[event.event_id]["incoming_opposite_move_pct_abs"] is not None]
        outgoing = [float(diagnostic_by_id[event.event_id]["outgoing_opposite_move_pct_abs"]) for event in selected
                    if diagnostic_by_id[event.event_id]["outgoing_opposite_move_pct_abs"] is not None]
        breaches = [float(diagnostic_by_id[event.event_id]["bars_to_strict_pivot_price_breach"]) for event in selected
                    if diagnostic_by_id[event.event_id]["bars_to_strict_pivot_price_breach"] is not None]
        result[f"{low:.0f}_{high:.0f}"] = {
            "price_interval_is_visual_calibration_only": True, "events": len(selected),
            "high_events": sum(event.pivot_type == "HIGH" for event in selected),
            "low_events": sum(event.pivot_type == "LOW" for event in selected),
            "dual_events": sum(event.dual for event in selected),
            "first_timestamp": min((event.timestamp for event in selected), default=None),
            "last_timestamp": max((event.timestamp for event in selected), default=None),
            "incoming_opposite_move_pct_abs": describe(incoming),
            "outgoing_opposite_move_pct_abs": describe(outgoing),
            "bars_to_strict_breach": describe(breaches),
            "sample_event_ids": [event.event_id for event in selected[:10]],
        }
    return result


def _stage_b_designs() -> List[Dict[str, Any]]:
    return [
        {"design": "two_sided_reaction_prominence",
         "idea": "Treat Stage B as retrospective research on incoming versus subsequent opposite-pivot movement and path geometry; do not use the result at pivot time.",
         "stage_a_fields": ["causal__previous_opposite__*", "causal__from_previous_opposite__*", "postevent__next_opposite__*"],
         "advantage": "Directly represents whether a pivot separates two measurable moves and exposes a continuous prominence spectrum.",
         "failure_modes": "Future next-pivot information leaks if used as a live predictor; same-type intervening pivots and dual candles complicate pair identity.",
         "arbitrary_threshold": "Any minimum movement ratio, duration, or efficiency boundary.",
         "scale_dependence": "Low if percentage/log features are used; high for absolute moves.",
         "causality": "Retrospective only until the next opposite pivot is confirmed.",
         "likely_errors": "Slow reactions with delayed departure; large volatile candles that reverse quickly; nested same-type pivots."},
        {"design": "confirmation_window_independence",
         "idea": "Use only the incoming move plus the two right-hand candles already required to confirm the raw pivot, asking whether the early departure is distinct relative to incoming/context geometry.",
         "stage_a_fields": ["causal__previous_opposite__*", "causal__bar_-2__* through causal__bar_+2__*", "causal__center_*"],
         "advantage": "Fully available at Stage A available_from and operationally simple.",
         "failure_modes": "Two 4H bars may be too short for slow reactions and may favor volatility spikes.",
         "arbitrary_threshold": "Departure/incoming ratio or percentile and minimum duration/context conditions.",
         "scale_dependence": "Moderate unless all price distances use causal percentage/log or rolling-scale normalization.",
         "causality": "Causal at available_from.",
         "likely_errors": "Delayed reversals, wick-only pivots, and brief two-bar bounces that immediately fail."},
        {"design": "causal_historical_prominence",
         "idea": "Compare incoming move, duration, efficiency, volatility, and same-type extension with rolling historical distributions available before each pivot.",
         "stage_a_fields": ["available_from", "causal__previous_opposite__*", "causal__previous_same__*", "causal__from_previous_opposite__*", "causal__bar_*"],
         "advantage": "Adapts to price scale and changing volatility while remaining auditable.",
         "failure_modes": "Rolling window choice changes results; early history is sparse; regime shifts make old reference data stale.",
         "arbitrary_threshold": "Historical lookback and percentile boundary.",
         "scale_dependence": "Low to moderate with percentage/log inputs, but reference-window dependence remains.",
         "causality": "Causal if distributions are frozen using data available before available_from.",
         "likely_errors": "First observations, abrupt volatility-regime changes, and structurally meaningful low-volatility turns."},
        {"design": "retrospective_sequence_segmentation",
         "idea": "Model the full raw-pivot chain and merge nested oscillations by an explicit global segmentation objective, then separately study whether a causal approximation can reproduce it.",
         "stage_a_fields": ["pivot_type", "pivot_price", "pivot_bar_index", "previous/next pivot relations", "local path geometry"],
         "advantage": "Directly addresses nested micro-pivots and can enforce coherent movement boundaries across a sequence.",
         "failure_modes": "Objective function can encode the desired answer; global optimization is future-dependent; dual events need explicit treatment.",
         "arbitrary_threshold": "Merge penalty, segment cost, or model complexity penalty.",
         "scale_dependence": "Depends on whether the objective uses absolute, percentage, or normalized movement.",
         "causality": "Retrospective by default; a separate online version would be required.",
         "likely_errors": "Legitimate nested reactions, prolonged sideways structures, and sharp outside bars."},
    ]


def _data_dictionary() -> Dict[str, Any]:
    diagnostic_status = {
        "event_id": "identity", "pivot_timestamp": "event_time", "pivot_type": "identity",
        "pivot_price": "event", "dual": "causal",
        "incoming_opposite_move_abs": "causal", "incoming_opposite_move_pct_abs": "causal",
        "incoming_duration_bars": "causal", "incoming_path_efficiency": "causal",
        "incoming_path_efficiency_recomputed": "causal", "incoming_directional_persistence": "causal",
        "incoming_alternation": "causal", "incoming_body_overlap_mean": "causal",
        "incoming_retracement_from_internal_extreme_log": "causal",
        "same_type_extension_abs": "causal", "same_type_extension_pct": "causal",
        "center_range_pct": "causal", "five_bar_context_span_pct": "causal",
        "previous_opposite_event_exists": "causal",
        "outgoing_opposite_move_abs": "postevent", "outgoing_opposite_move_pct_abs": "postevent",
        "outgoing_duration_bars": "postevent", "outgoing_path_efficiency": "postevent",
        "outgoing_directional_persistence": "postevent", "outgoing_alternation": "postevent",
        "outgoing_body_overlap_mean": "postevent", "outgoing_retracement_from_internal_extreme_log": "postevent",
        "outgoing_to_incoming_move_ratio": "postevent", "outgoing_to_incoming_duration_ratio": "postevent",
        "bars_to_strict_pivot_price_breach": "postevent", "postevent_h6_range_pct": "postevent",
        "postevent_h12_range_pct": "postevent", "three_consecutive_event_price_span_pct": "postevent",
        "five_consecutive_event_price_span_pct": "postevent", "next_opposite_event_exists": "postevent",
    }
    return {
        "review_version": REVIEW_VERSION,
        "causal_contract": {
            "causal": "known by the Stage A event available_from timestamp",
            "postevent": "retrospective diagnostic; prohibited as a pivot-time predictor",
            "aggregate": "retrospective population summary",
        },
        "tables": {
            "consecutive_pivot_pairs.csv": {"row": "one adjacent pair in deterministic Stage A event storage order",
                                            "primary_key": ["from_event_id", "to_event_id"],
                                            "information_status": "postevent",
                                            "dual_warning": "zero-gap HIGH then LOW is storage order, not intrabar chronology"},
            "opposite_pivot_pairs.csv": {"row": "one event linked to its next strictly later opposite-type pivot",
                                         "primary_key": ["pair_id"], "information_status": "postevent",
                                         "path_contract": "close-to-close path; percent move starts at from-pivot price"},
            "pivot_diagnostics.csv": {"row": "one Stage A pivot event", "primary_key": ["event_id"],
                                      "column_information_status": diagnostic_status},
            "dual_candle_diagnostics.csv": {"row": "one unique dual HIGH+LOW pivot candle",
                                            "primary_key": ["bar_index"], "information_status": "causal"},
            "pivot_candle_geometry_reference.csv": {"row": "one unique pivot-bearing candle",
                                                     "primary_key": ["bar_index"], "information_status": "causal"},
            "year_comparison.csv": {"row": "one calendar year or partial year", "primary_key": ["year"],
                                    "information_status": "aggregate"},
            "chart_windows.csv": {"row": "one deterministic visual-QA selection window",
                                  "primary_key": ["chart_id"], "information_status": "aggregate"},
        },
        "canonical_reused_definitions": {
            "directional_persistence": "mean(sign(diff(log(close))) * path direction)",
            "alternation": "share of adjacent nonzero close-step signs that differ",
            "body_overlap_mean": "mean absolute overlap length of consecutive candle bodies",
            "close_path_efficiency": "absolute first-to-last close displacement / sum absolute close steps",
            "retracement_from_internal_extreme_log": "maximum favorable log excursion - final direction-normalized log progress",
        },
    }


def _qa(candles: Sequence[Candle], events: Sequence[PivotEvent], consecutive: Sequence[Mapping[str, Any]],
        opposite: Sequence[Mapping[str, Any]], diagnostics: Sequence[Mapping[str, Any]],
        duals: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    checks = {
        "canonical_complete_candles_15445": len(candles) == 15445,
        "stage_a_events_4450": len(events) == 4450,
        "event_ids_unique": len({event.event_id for event in events}) == len(events),
        "consecutive_pair_count": len(consecutive) == len(events) - 1,
        "consecutive_nonnegative_gaps": all(int(row["bar_gap"]) >= 0 for row in consecutive),
        "zero_gap_pairs_are_dual": all(events[index].dual and events[index + 1].dual and
                                        events[index].pivot_type != events[index + 1].pivot_type
                                        for index, row in enumerate(consecutive) if int(row["bar_gap"]) == 0),
        "opposite_pairs_strictly_forward": all(float(row["duration_bars"]) > 0 for row in opposite),
        "path_efficiency_bounded": all(0 <= float(row["close_path_efficiency"]) <= 1 for row in opposite if row["close_path_efficiency"] is not None),
        "stage_a_path_efficiency_independently_reproduced": all(
            abs(float(row["incoming_path_efficiency"]) - float(row["incoming_path_efficiency_recomputed"])) < 1e-12
            for row in diagnostics if row["incoming_path_efficiency"] is not None and row["incoming_path_efficiency_recomputed"] is not None),
        "dual_candles_150": len(duals) == 150,
        "dual_geometry_positive_extensions": all(float(row["high_extension"]) > 0 and float(row["low_extension"]) > 0 for row in duals),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed]}


def _build(data_root: Path, repo_root: Path, output_subdir: Path, summary_path: Path,
           mode: str, stamp: Optional[str]) -> Dict[str, Any]:
    stage_dir = data_root / "research" / "stage2i_a_raw_4h_pivots"
    candles, candle_source = _load_candles(data_root)
    events, pivot_source = _load_pivots(stage_dir)
    if mode == "smoke":
        candles = candles[:1200]
        events = [event for event in events if event.bar_index < 1200]
    consecutive = _consecutive_pairs(events)
    opposite = _opposite_pairs(events, candles)
    diagnostics = _event_diagnostics(events, candles, opposite)
    duals = _dual_rows(events, candles)
    pivot_candle_geometry = _pivot_candle_geometry_rows(events, candles)
    years = _year_rows(candles, events, opposite)
    chart_windows = _select_chart_windows(candles, events, diagnostics) if mode == "production" else []
    qa = _qa(candles, events, consecutive, opposite, diagnostics, duals) if mode == "production" else {"status": "PASS", "checks": {"smoke_nonempty": bool(events)}, "failures": []}

    gaps = [float(row["bar_gap"]) for row in consecutive]
    positive_pairs = [row for row in consecutive if int(row["bar_gap"]) > 0]
    bucket_counts = Counter(str(row["gap_bucket"]) for row in consecutive)
    exact_counts = Counter(int(row["bar_gap"]) for row in consecutive)
    density_summary = {
        "all_consecutive_event_pairs": {"bar_gap": describe(gaps),
                                        "time_gap_hours": describe(float(row["time_gap_hours"]) for row in consecutive),
                                        "exact_bar_gap_counts": {str(key): value for key, value in sorted(exact_counts.items())},
                                        "explicit_gap_buckets": {key: {"count": bucket_counts[key], "share": bucket_counts[key] / len(consecutive)}
                                                                 for key in sorted(bucket_counts)}},
        "positive_gap_pairs_only": {"bar_gap": describe(float(row["bar_gap"]) for row in positive_pairs),
                                    "time_gap_hours": describe(float(row["time_gap_hours"]) for row in positive_pairs)},
        "by_transition_all": _summaries_by_group(consecutive, "transition", ("bar_gap", "time_gap_hours")),
        "by_transition_positive_gap": _summaries_by_group(positive_pairs, "transition", ("bar_gap", "time_gap_hours")),
        "dual_zero_gap_warning": "HIGH then LOW is a deterministic storage order, not intrabar chronology.",
    }
    opposite_summary = {field: describe(float(row[field]) for row in opposite if row[field] is not None) for field in
                        ("absolute_pivot_move", "absolute_percentage_move", "absolute_log_move", "duration_bars",
                         "duration_hours", "duration_days", "price_excursion", "price_excursion_pct_start",
                         "close_path", "close_path_efficiency", "log_close_path_efficiency",
                         "directional_persistence", "alternation", "body_overlap_mean",
                         "retracement_from_internal_extreme_log", "end_retention")}
    opposite_summary["continuity_diagnostics"] = {
        "absolute_move": _continuity_diagnostic([float(row["absolute_pivot_move"]) for row in opposite]),
        "percentage_move": _continuity_diagnostic([float(row["absolute_percentage_move"]) for row in opposite]),
        "duration_bars": _continuity_diagnostic([float(row["duration_bars"]) for row in opposite]),
    }
    diagnostic_fields = ("incoming_opposite_move_pct_abs", "outgoing_opposite_move_pct_abs", "incoming_duration_bars",
                         "outgoing_duration_bars", "outgoing_to_incoming_move_ratio", "outgoing_to_incoming_duration_ratio",
                         "same_type_extension_pct", "bars_to_strict_pivot_price_breach", "center_range_pct",
                         "five_bar_context_span_pct", "postevent_h6_range_pct", "postevent_h12_range_pct",
                         "three_consecutive_event_price_span_pct", "five_consecutive_event_price_span_pct",
                         "incoming_path_efficiency", "outgoing_path_efficiency",
                         "incoming_directional_persistence", "outgoing_directional_persistence",
                         "incoming_alternation", "outgoing_alternation",
                         "incoming_body_overlap_mean", "outgoing_body_overlap_mean",
                         "incoming_retracement_from_internal_extreme_log",
                         "outgoing_retracement_from_internal_extreme_log")
    diagnostic_summary = {field: describe(float(row[field]) for row in diagnostics if row[field] is not None)
                          for field in diagnostic_fields}
    breaches = [int(row["bars_to_strict_pivot_price_breach"]) for row in diagnostics if row["bars_to_strict_pivot_price_breach"] is not None]
    diagnostic_summary["breach_empirical_cdf"] = {f"within_{horizon}_bars": sum(value <= horizon for value in breaches) / len(diagnostics)
                                                  for horizon in (1, 2, 3, 6, 12, 24)}
    dual_fields = ("center_range_pct", "center_body_to_range", "center_upper_wick_to_range", "center_lower_wick_to_range",
                   "center_to_neighbor_mean_range_ratio", "high_extension", "low_extension",
                   "center_to_neighbor_mean_volume_ratio", "center_to_neighbor_mean_trade_count_ratio",
                   "open_gap_from_previous_close_pct")
    dual_summary = {field: describe(float(row[field]) for row in duals if row[field] is not None) for field in dual_fields}
    nondual_geometry = [row for row in pivot_candle_geometry if not row["dual"]]
    dual_summary["nondual_pivot_candle_reference"] = {
        field: describe(float(row[field]) for row in nondual_geometry if row[field] is not None) for field in dual_fields
    }
    dual_summary["dual_to_nondual_median_ratio"] = {
        field: _safe_ratio(_float(dual_summary[field]["median"]),
                           _float(dual_summary["nondual_pivot_candle_reference"][field]["median"]))
        for field in ("center_range_pct", "center_to_neighbor_mean_range_ratio",
                      "center_to_neighbor_mean_volume_ratio", "center_to_neighbor_mean_trade_count_ratio")
    }
    dual_summary["examples_largest_range_ratio"] = sorted(duals, key=lambda row: float(row["center_to_neighbor_mean_range_ratio"]), reverse=True)[:10]
    year_summary = {str(row["year"]): row for row in years}
    year_distributions = _summaries_by_group(opposite, "calendar_year",
                                             ("absolute_pivot_move", "absolute_percentage_move", "duration_bars"))
    designs = _stage_b_designs()
    open_questions = [
        {"question": "How should dual HIGH+LOW events be represented in a Stage B sequence?",
         "options": ["retain two unordered same-candle events", "introduce a separate outside-bar state", "defer both until later evidence"],
         "consequence": "The choice changes transition counts and any segmentation objective."},
        {"question": "What operational meaning should retracement fraction have for nested raw pivots?",
         "options": ["outgoing/incoming pivot-price move", "close-path displacement ratio", "reference to prior same-type extreme"],
         "consequence": "These denominators answer different structural questions; this review reports raw components only."},
        {"question": "What horizon and price band define locally trapped or rapidly invalidated?",
         "options": ["fixed bars and fixed percent", "rolling causal volatility scale", "next-pivot event time"],
         "consequence": "Any choice creates a threshold and changes scale/regime sensitivity."},
        {"question": "Is Stage B target retrospective movement segmentation or a label available at pivot confirmation?",
         "options": ["retrospective ground-truth research", "strictly causal available_from label", "retrospective target plus causal approximation"],
         "consequence": "Next-pivot and full departure features are valid only for retrospective analysis."},
    ]
    summary = {
        "review_version": REVIEW_VERSION, "mode": mode,
        "source": {"canonical": candle_source, "stage2i_a": pivot_source},
        "population": {"complete_candles": len(candles), "pivot_events": len(events),
                       "high_events": sum(event.pivot_type == "HIGH" for event in events),
                       "low_events": sum(event.pivot_type == "LOW" for event in events),
                       "dual_candles": len(duals)},
        "pivot_density": density_summary, "opposite_pivot_movements": opposite_summary,
        "micro_fluctuation_diagnostics": diagnostic_summary, "dual_candle_analysis": dual_summary,
        "year_comparison": year_summary, "year_distributions": year_distributions,
        "calibration_2026": _calibration_summary(events, diagnostics),
        "chart_windows": chart_windows,
        "facts_supported": [
            "Raw pivots occupy a continuous multiscale distribution; the review does not impose a class boundary.",
            "Absolute movement is strongly price-era dependent and cannot be compared across years without a scale decision.",
            "Dual events are genuine strict-definition outcomes and have no intrabar HIGH/LOW order in 4H data.",
            "Future departure and next-pivot diagnostics are informative retrospectively but are not causal at available_from.",
        ],
        "not_supported": [
            "No micro-versus-independent label is established.", "No cutoff, ATR rule, fixed-percent rule, zone width, trend, or trading rule is established.",
            "Visual calibration price intervals are not structural zones or labels.",
        ],
        "open_methodology_questions": open_questions, "stage_b_design_options_unranked": designs, "qa": qa,
    }

    output_subdir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output_subdir.name + ".tmp.", dir=output_subdir.parent))
    try:
        _json(temporary / "progress.json", {"stage": "statistics_complete", "mode": mode,
                                             "events": len(events), "opposite_pairs": len(opposite)})
        _write_csv(temporary / "consecutive_pivot_pairs.csv", consecutive)
        _write_csv(temporary / "opposite_pivot_pairs.csv", opposite)
        _write_csv(temporary / "pivot_diagnostics.csv", diagnostics)
        _write_csv(temporary / "dual_candle_diagnostics.csv", duals)
        _write_csv(temporary / "pivot_candle_geometry_reference.csv", pivot_candle_geometry)
        _write_csv(temporary / "year_comparison.csv", years)
        _write_csv(temporary / "chart_windows.csv", chart_windows)
        _json(temporary / "review_data_dictionary.json", _data_dictionary())
        if gaps:
            _write_distribution_svg(temporary / "distribution_consecutive_bar_gaps.svg", gaps,
                                    "Consecutive raw pivot event gaps", "bar gap")
        _write_distribution_svg(temporary / "distribution_opposite_move_pct.svg",
                                [float(row["absolute_percentage_move"]) for row in opposite],
                                "Opposite-pivot absolute percentage movement", "absolute move (%)")
        _write_distribution_svg(temporary / "distribution_opposite_duration_bars.svg",
                                [float(row["duration_bars"]) for row in opposite],
                                "Opposite-pivot duration", "bars")
        _write_distribution_svg(temporary / "distribution_move_ratio.svg",
                                [float(row["outgoing_to_incoming_move_ratio"]) for row in diagnostics
                                 if row["outgoing_to_incoming_move_ratio"] is not None],
                                "Outgoing / incoming opposite-pivot move ratio", "ratio")
        _write_distribution_svg(temporary / "distribution_dual_range_ratio.svg",
                                [float(row["center_to_neighbor_mean_range_ratio"]) for row in duals],
                                "Dual candle range / four-neighbor mean range", "ratio")
        _write_year_svg(temporary / "year_regime_comparison.svg", years)
        for window in chart_windows:
            start = int(window["start_index"])
            end = int(window["end_index_exclusive"])
            chart_candles = candles[start:end]
            chart_events = [event for event in events if start <= event.bar_index < end]
            write_candlestick_svg(temporary / f'chart_{window["chart_id"]}.svg', chart_candles, chart_events,
                                  f'{window["chart_id"]}: {chart_candles[0].timestamp.isoformat()} to {chart_candles[-1].end_time.isoformat()}')
        _json(temporary / "review_summary.json", summary)
        git_commit = stamp or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True).strip())
        artifact_names = sorted(path.name for path in temporary.iterdir() if path.name != "progress.json")
        manifest = {"review_version": REVIEW_VERSION, "mode": mode,
                    "run_id": hashlib.sha256((pivot_source["sha256"] + _sha256(Path(__file__)) + mode).encode()).hexdigest()[:16],
                    "git_commit": git_commit, "git_worktree_dirty_at_build": dirty,
                    "pipeline_path": str(Path(__file__).resolve()), "pipeline_sha256": _sha256(Path(__file__)),
                    "inputs": {"stage2i_a_parquet_sha256": pivot_source["sha256"],
                               "stage2i_a_manifest_sha256": pivot_source["manifest_sha256"],
                               "canonical_manifest_sha256": candle_source["sha256"]},
                    "population": summary["population"], "qa": qa,
                    "artifacts": {name: _sha256(temporary / name) for name in artifact_names}}
        _json(temporary / "manifest.json", manifest)
        checksum_names = sorted(path.name for path in temporary.iterdir() if path.name not in {"checksums.sha256", "progress.json"})
        (temporary / "checksums.sha256").write_text("".join(f"{_sha256(temporary/name)}  {name}\n" for name in checksum_names), encoding="utf-8")
        _json(temporary / "progress.json", {"stage": "qa_complete", "mode": mode, "qa_status": qa["status"]})
        if qa["status"] != "PASS":
            raise RuntimeError(f"Review QA failed: {qa['failures']}")
        backup = output_subdir.with_name(output_subdir.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if output_subdir.exists():
            os.replace(output_subdir, backup)
        os.replace(temporary, output_subdir)
        if backup.exists():
            shutil.rmtree(backup)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_temp = summary_path.with_suffix(summary_path.suffix + ".tmp")
        _json(summary_temp, summary)
        os.replace(summary_temp, summary_path)
        return summary
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output-subdir", type=Path)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--mode", choices=("smoke", "production"), default="production")
    parser.add_argument("--stamp-git-commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stage_dir = args.data_root / "research" / "stage2i_a_raw_4h_pivots"
    output_subdir = args.output_subdir or stage_dir / "pivot_structure_review"
    summary_path = args.summary_path or stage_dir / "stage2i_a_pivot_structure_review.json"
    summary = _build(args.data_root, args.repo_root, output_subdir, summary_path, args.mode, args.stamp_git_commit)
    print(json.dumps({"qa": summary["qa"]["status"], "population": summary["population"],
                      "output_subdir": str(output_subdir), "summary": str(summary_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
