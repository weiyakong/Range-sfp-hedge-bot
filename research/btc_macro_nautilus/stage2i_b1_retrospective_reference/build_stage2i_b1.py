#!/usr/bin/env python3
"""Build the Stage 2I-B1 retrospective, multiscale pivot reference study.

This module is deliberately offline. Every quantity that uses the realized path is
named ``reference__`` or ``postevent__`` and is prohibited as a Stage 2I-B2 input.
The study preserves continuous diagnostics and complete scale sweeps; it does not
create MICRO/INDEPENDENT labels or choose a final reference contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


STAGE_VERSION = "stage2i-b1-v1"
STAGE_A_COMMIT = "71b6158a61503fde9145f3565fe0be3149bbab76"
STAGE_A_REVIEW_COMMIT = "b38aff90e2d6d056ebd14ae9bbecece1fefe0bb8"
CANONICAL_ARCHITECTURE_COMMIT = "02b82c0b8622483a55c23c01af606b1904d332f4"
LOCAL_VOL_LOOKBACK = 42
DESIGN_B_LOG_SCALES = (0.0, 0.005, 0.010, 0.015, 0.020, 0.030, 0.050, 0.075, 0.100, 0.150, 0.250)
DESIGN_C_RATIO_SCALES = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
DESIGN_C_LOG_SCALES = (0.005, 0.010, 0.015, 0.020, 0.030, 0.050, 0.075, 0.100, 0.150, 0.250)
DESIGN_C_VOL_SCALES = (0.50, 1.00, 1.50, 2.00, 3.00, 4.00, 6.00, 8.00, 12.00)
IDENTITY_COLUMNS = {
    "event_id", "pivot_id", "pivot_bar_index", "pivot_timestamp", "pivot_type",
    "pivot_price", "year", "source_manifest_sha256", "dual_flag", "row_status",
}


@dataclass(frozen=True)
class PivotEvent:
    event_id: str
    bar_index: int
    timestamp: datetime
    pivot_type: str
    price: float
    is_dual: bool


@dataclass(frozen=True)
class Candle:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class PreparedSequence:
    sequence: Tuple[PivotEvent, ...]
    prepass_removed: Mapping[str, str]
    deferred_duals: Tuple[str, ...]


@dataclass(frozen=True)
class RemovalRecord:
    reference__removal_iteration: Optional[int]
    reference__removal_log_scale: Optional[float]
    reference__edge_censored: bool
    reference__removal_reason: str


@dataclass(frozen=True, order=True)
class SweepRow:
    parameter: float
    event_id: str
    retained: bool
    previous_event_id: Optional[str]
    next_event_id: Optional[str]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".incomplete")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n")


def write_deterministic_parquet(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty Parquet artifact: {path}")
    columns = sorted({column for row in rows for column in row})
    normalized = [{column: row.get(column) for column in columns} for row in rows]
    table = pa.Table.from_pylist(normalized)
    temporary = path.with_name(path.name + ".incomplete")
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        temporary,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    os.replace(temporary, path)


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV artifact: {path}")
    columns = sorted({column for row in rows for column in row})
    temporary = path.with_name(path.name + ".incomplete")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def validate_checksums(directory: Path) -> None:
    checksum_path = directory / "checksums.sha256"
    if not checksum_path.exists():
        raise FileNotFoundError(f"Missing checksums: {checksum_path}")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = directory / relative
        if sha256(target) != expected:
            raise ValueError(f"Checksum mismatch: {target}")


def validate_source_identity(expected_ids: Sequence[str], actual_ids: Sequence[str]) -> None:
    if list(expected_ids) != list(actual_ids):
        raise ValueError("Stage 2I-A source pivot identity/order changed")
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("Duplicate pivot IDs in source/output")


def assert_reference_namespace(columns: Iterable[str]) -> None:
    for column in columns:
        if column in IDENTITY_COLUMNS:
            continue
        if column.startswith("reference__") or column.startswith("postevent__"):
            continue
        raise ValueError(f"B1 derived field lacks reference/postevent namespace: {column}")


def _more_extreme(left: PivotEvent, right: PivotEvent) -> PivotEvent:
    if left.pivot_type != right.pivot_type:
        raise ValueError("Extreme comparison requires the same pivot type")
    if left.pivot_type == "HIGH":
        return left if (left.price, -left.bar_index, left.event_id) >= (right.price, -right.bar_index, right.event_id) else right
    return left if (left.price, left.bar_index, left.event_id) <= (right.price, right.bar_index, right.event_id) else right


def prepare_sequence(events: Sequence[PivotEvent], dual_mode: str = "deferred") -> PreparedSequence:
    if dual_mode not in {"deferred", "unordered_diagnostic"}:
        raise ValueError(f"Unsupported dual mode: {dual_mode}")
    ordered = sorted(events, key=lambda event: (event.bar_index, event.timestamp, event.event_id))
    deferred = tuple(event.event_id for event in ordered if event.is_dual)
    candidates = [event for event in ordered if not event.is_dual]
    sequence: List[PivotEvent] = []
    removed: Dict[str, str] = {}
    for event in candidates:
        if sequence and event.bar_index <= sequence[-1].bar_index:
            raise ValueError("Primary sequence contains non-increasing pivot bars")
        if sequence and event.pivot_type == sequence[-1].pivot_type:
            kept = _more_extreme(sequence[-1], event)
            dropped = event if kept is sequence[-1] else sequence[-1]
            removed[dropped.event_id] = "same_type_less_extreme"
            if kept is event:
                sequence[-1] = event
        else:
            sequence.append(event)
    if any(left.pivot_type == right.pivot_type for left, right in zip(sequence, sequence[1:])):
        raise ValueError("Prepared primary sequence is not alternating")
    return PreparedSequence(tuple(sequence), removed, deferred)


def _log_excursion(left: PivotEvent, right: PivotEvent) -> float:
    if left.price <= 0 or right.price <= 0:
        raise ValueError("Pivot prices must be positive")
    return abs(math.log(right.price / left.price))


def hierarchical_simplification(
    prepared: PreparedSequence,
    cost_mode: str = "minimum_log_excursion",
) -> Dict[str, RemovalRecord]:
    if cost_mode not in {"minimum_log_excursion", "geometric_mean_log_excursion"}:
        raise ValueError(f"Unknown hierarchy cost mode: {cost_mode}")
    work = list(prepared.sequence)
    result: Dict[str, RemovalRecord] = {}
    for event_id in sorted(prepared.prepass_removed):
        result[event_id] = RemovalRecord(0, 0.0, False, prepared.prepass_removed[event_id])
    iteration = 0
    last_effective_cost = 0.0
    while len(work) > 2:
        scored: List[Tuple[float, int, str, int]] = []
        for index in range(1, len(work) - 1):
            left = _log_excursion(work[index - 1], work[index])
            right = _log_excursion(work[index], work[index + 1])
            cost = min(left, right) if cost_mode == "minimum_log_excursion" else math.sqrt(left * right)
            scored.append((cost, work[index].bar_index, work[index].event_id, index))
        raw_cost, _, _, selected = min(scored)
        effective_cost = max(raw_cost, last_effective_cost)
        last_effective_cost = effective_cost
        iteration += 1
        removed = work.pop(selected)
        result[removed.event_id] = RemovalRecord(iteration, effective_cost, False, "interior_lowest_cost")
        if 0 < selected < len(work) and work[selected - 1].pivot_type == work[selected].pivot_type:
            left = work[selected - 1]
            right = work[selected]
            kept = _more_extreme(left, right)
            dropped = right if kept is left else left
            drop_index = selected if dropped is right else selected - 1
            work.pop(drop_index)
            result[dropped.event_id] = RemovalRecord(iteration, effective_cost, False, "same_type_after_merge")
    for survivor in work:
        result[survivor.event_id] = RemovalRecord(None, None, True, "left_or_right_boundary_survivor")
    return result


def _support(
    left: PivotEvent,
    center: PivotEvent,
    right: PivotEvent,
    family: str,
    local_scale_by_id: Mapping[str, float],
) -> float:
    incoming_log = _log_excursion(left, center)
    outgoing_log = _log_excursion(center, right)
    if family == "log_price":
        return min(incoming_log, outgoing_log)
    if family == "retracement_ratio":
        return outgoing_log / incoming_log if incoming_log > 0 else math.inf
    if family == "local_volatility":
        scale = local_scale_by_id.get(center.event_id)
        if scale is None or scale <= 0:
            return math.inf
        return min(abs(center.price - left.price), abs(right.price - center.price)) / scale
    raise ValueError(f"Unknown sweep family: {family}")


def _retained_at_threshold(
    sequence: Sequence[PivotEvent],
    threshold: float,
    family: str,
    local_scale_by_id: Mapping[str, float],
) -> List[PivotEvent]:
    work = list(sequence)
    while len(work) > 2:
        candidates: List[Tuple[float, int, str, int]] = []
        for index in range(1, len(work) - 1):
            support = _support(work[index - 1], work[index], work[index + 1], family, local_scale_by_id)
            if support < threshold:
                candidates.append((support, work[index].bar_index, work[index].event_id, index))
        if not candidates:
            break
        _, _, _, selected = min(candidates)
        work.pop(selected)
        if 0 < selected < len(work) and work[selected - 1].pivot_type == work[selected].pivot_type:
            kept = _more_extreme(work[selected - 1], work[selected])
            work.pop(selected if kept is work[selected - 1] else selected - 1)
    return work


def threshold_sweep(
    prepared: PreparedSequence,
    scales: Sequence[float],
    family: str,
    local_scale_by_id: Mapping[str, float],
) -> List[SweepRow]:
    removal_scale: Dict[str, Optional[float]] = {
        event_id: 0.0 for event_id in prepared.prepass_removed
    }
    work = list(prepared.sequence)
    last_effective_support = 0.0
    while len(work) > 2:
        candidates: List[Tuple[float, int, str, int]] = []
        for index in range(1, len(work) - 1):
            support = _support(
                work[index - 1], work[index], work[index + 1], family, local_scale_by_id
            )
            candidates.append((support, work[index].bar_index, work[index].event_id, index))
        raw_support, _, _, selected = min(candidates)
        effective_support = max(raw_support, last_effective_support)
        last_effective_support = effective_support
        removed = work.pop(selected)
        removal_scale[removed.event_id] = effective_support
        if 0 < selected < len(work) and work[selected - 1].pivot_type == work[selected].pivot_type:
            kept = _more_extreme(work[selected - 1], work[selected])
            dropped = work[selected] if kept is work[selected - 1] else work[selected - 1]
            work.pop(selected if dropped is work[selected] else selected - 1)
            removal_scale[dropped.event_id] = effective_support
    for survivor in work:
        removal_scale[survivor.event_id] = None

    rows: List[SweepRow] = []
    all_ids = sorted(event.event_id for event in prepared.sequence)
    sequence_order = [event.event_id for event in prepared.sequence]
    for parameter in sorted(float(value) for value in scales):
        retained_ids = [
            event_id for event_id in sequence_order
            if removal_scale[event_id] is None or float(removal_scale[event_id]) >= parameter
        ]
        positions = {event_id: index for index, event_id in enumerate(retained_ids)}
        for event_id in all_ids:
            index = positions.get(event_id)
            rows.append(SweepRow(
                parameter=parameter,
                event_id=event_id,
                retained=index is not None,
                previous_event_id=retained_ids[index - 1] if index is not None and index > 0 else None,
                next_event_id=retained_ids[index + 1] if index is not None and index + 1 < len(retained_ids) else None,
            ))
    return sorted(rows)


def empirical_rank(values: Mapping[str, Optional[float]], censored_ids: Iterable[str] = ()) -> Dict[str, Optional[float]]:
    censored = set(censored_ids)
    finite = sorted(float(value) for value in values.values() if value is not None and math.isfinite(float(value)))
    result: Dict[str, Optional[float]] = {}
    for event_id, value in values.items():
        if event_id in censored:
            result[event_id] = 1.0
        elif value is None or not math.isfinite(float(value)) or not finite:
            result[event_id] = None
        else:
            result[event_id] = float(np.searchsorted(finite, float(value), side="right") / len(finite))
    return result


def chronological_boundary_flags(prepared: PreparedSequence, event_id: str) -> Tuple[bool, bool]:
    if not prepared.sequence:
        return False, False
    return event_id == prepared.sequence[0].event_id, event_id == prepared.sequence[-1].event_id


def _path_geometry(candles: Sequence[Candle], left: PivotEvent, right: PivotEvent) -> Mapping[str, float]:
    if right.bar_index <= left.bar_index:
        raise ValueError("Path geometry requires positive time")
    window = candles[left.bar_index:right.bar_index + 1]
    closes = np.asarray([candle.close for candle in window], dtype=float)
    log_closes = np.log(closes)
    endpoint = math.log(right.price / left.price)
    path = abs(math.log(closes[0] / left.price))
    if log_closes.size > 1:
        path += float(np.sum(np.abs(np.diff(log_closes))))
    path += abs(math.log(right.price / closes[-1]))
    efficiency = min(1.0, abs(endpoint) / path) if path > 0 else 0.0
    direction = 1.0 if endpoint >= 0 else -1.0
    steps = np.diff(log_closes)
    persistence = float(np.mean(np.sign(steps) * direction)) if steps.size else 0.0
    nonzero = np.sign(steps[steps != 0])
    alternation = float(np.mean(nonzero[1:] != nonzero[:-1])) if nonzero.size > 1 else 0.0
    return {
        "log_path": path,
        "efficiency": efficiency,
        "directional_persistence": persistence,
        "alternation": alternation,
    }


def design_a_metrics(prepared: PreparedSequence, candles: Sequence[Candle]) -> Dict[str, Mapping[str, Optional[float]]]:
    result: Dict[str, Mapping[str, Optional[float]]] = {}
    sequence = prepared.sequence
    for index, event in enumerate(sequence):
        if index == 0 or index + 1 == len(sequence):
            result[event.event_id] = {
                "incoming_log": None, "outgoing_log": None, "minimum_log": None,
                "geometric_log": None, "harmonic_log": None, "balance": None,
                "incoming_bars": None, "outgoing_bars": None,
                "incoming_efficiency": None, "outgoing_efficiency": None,
                "incoming_persistence": None, "outgoing_persistence": None,
                "incoming_alternation": None, "outgoing_alternation": None,
            }
            continue
        left, right = sequence[index - 1], sequence[index + 1]
        incoming = _log_excursion(left, event)
        outgoing = _log_excursion(event, right)
        minimum = min(incoming, outgoing)
        maximum = max(incoming, outgoing)
        incoming_path = _path_geometry(candles, left, event)
        outgoing_path = _path_geometry(candles, event, right)
        result[event.event_id] = {
            "incoming_log": incoming,
            "outgoing_log": outgoing,
            "minimum_log": minimum,
            "geometric_log": math.sqrt(incoming * outgoing),
            "harmonic_log": 2.0 * incoming * outgoing / (incoming + outgoing) if incoming + outgoing > 0 else 0.0,
            "balance": minimum / maximum if maximum > 0 else 0.0,
            "incoming_bars": float(event.bar_index - left.bar_index),
            "outgoing_bars": float(right.bar_index - event.bar_index),
            "incoming_efficiency": incoming_path["efficiency"],
            "outgoing_efficiency": outgoing_path["efficiency"],
            "incoming_persistence": incoming_path["directional_persistence"],
            "outgoing_persistence": outgoing_path["directional_persistence"],
            "incoming_alternation": incoming_path["alternation"],
            "outgoing_alternation": outgoing_path["alternation"],
        }
    return result


def unordered_dual_design_a_metrics(
    events: Sequence[PivotEvent], candles: Sequence[Candle]
) -> Dict[str, Mapping[str, float]]:
    """Measure dual extrema independently without inventing their within-bar order."""
    nondual = [event for event in events if not event.is_dual]
    result: Dict[str, Mapping[str, float]] = {}
    for event in (item for item in events if item.is_dual):
        opposite = [item for item in nondual if item.pivot_type != event.pivot_type]
        previous = [item for item in opposite if item.bar_index < event.bar_index]
        following = [item for item in opposite if item.bar_index > event.bar_index]
        if not previous or not following:
            continue
        left = max(previous, key=lambda item: item.bar_index)
        right = min(following, key=lambda item: item.bar_index)
        incoming = _log_excursion(left, event)
        outgoing = _log_excursion(event, right)
        result[event.event_id] = {
            "minimum_log": min(incoming, outgoing),
            "geometric_log": math.sqrt(incoming * outgoing),
            "incoming_bars": float(event.bar_index - left.bar_index),
            "outgoing_bars": float(right.bar_index - event.bar_index),
            "incoming_efficiency": _path_geometry(candles, left, event)["efficiency"],
            "outgoing_efficiency": _path_geometry(candles, event, right)["efficiency"],
        }
    return result


def _load_candles(data_root: Path) -> Tuple[List[Candle], str]:
    source_dir = data_root / "derived" / "BTCUSDT" / "4h"
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candles: List[Candle] = []
    for item in manifest["output_files"]:
        path = Path(item["path"])
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Canonical candle checksum mismatch: {path}")
        table = pq.read_table(path, columns=["start_time", "open", "high", "low", "close", "complete"])
        if table.num_rows != int(item["rows"]):
            raise ValueError(f"Canonical candle row count mismatch: {path}")
        for row in table.to_pylist():
            if not row["complete"]:
                continue
            candles.append(Candle(
                index=len(candles), timestamp=row["start_time"], open=float(row["open"]),
                high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
            ))
    if len(candles) != 15445:
        raise ValueError(f"Expected 15,445 complete candles, found {len(candles)}")
    if any(right.timestamp <= left.timestamp for left, right in zip(candles, candles[1:])):
        raise ValueError("Canonical candles are not strictly chronological")
    return candles, sha256(manifest_path)


def _load_pivots(stage_a_dir: Path) -> Tuple[List[PivotEvent], List[Mapping[str, object]], str]:
    validate_checksums(stage_a_dir)
    review_dir = stage_a_dir / "pivot_structure_review"
    validate_checksums(review_dir)
    path = stage_a_dir / "raw_4h_pivots.parquet"
    columns = ["event_id", "pivot_bar_index", "pivot_timestamp", "pivot_type", "pivot_price", "causal__dual_high_low_same_candle", "source_manifest_sha256"]
    rows = pq.read_table(path, columns=columns).to_pylist()
    events = [PivotEvent(
        event_id=str(row["event_id"]), bar_index=int(row["pivot_bar_index"]),
        timestamp=row["pivot_timestamp"], pivot_type=str(row["pivot_type"]),
        price=float(row["pivot_price"]), is_dual=bool(row["causal__dual_high_low_same_candle"]),
    ) for row in rows]
    if len(events) != 4450 or len({event.event_id for event in events}) != 4450:
        raise ValueError("Frozen Stage 2I-A population mismatch")
    if sum(event.is_dual for event in events) != 300:
        raise ValueError("Frozen dual-event population mismatch")
    return events, rows, sha256(path)


def local_volatility_scales(candles: Sequence[Candle], events: Sequence[PivotEvent]) -> Dict[str, float]:
    true_ranges: List[float] = []
    for index, candle in enumerate(candles):
        previous_close = candles[index - 1].close if index else candle.close
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
    result: Dict[str, float] = {}
    for event in events:
        start = max(0, event.bar_index - LOCAL_VOL_LOOKBACK)
        history = true_ranges[start:event.bar_index]
        if len(history) >= 10:
            result[event.event_id] = float(np.median(np.asarray(history, dtype=float)))
    return result


def _sweep_survival(rows: Sequence[SweepRow]) -> Dict[str, float]:
    totals: Dict[str, int] = {}
    retained: Dict[str, int] = {}
    for row in rows:
        totals[row.event_id] = totals.get(row.event_id, 0) + 1
        retained[row.event_id] = retained.get(row.event_id, 0) + int(row.retained)
    return {event_id: retained[event_id] / totals[event_id] for event_id in totals}


def _rank_correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    if len(left) < 2:
        return None
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if float(np.std(left_array)) == 0.0 or float(np.std(right_array)) == 0.0:
        return None
    return float(np.corrcoef(left_array, right_array)[0, 1])


def _describe(values: Iterable[Optional[float]]) -> Mapping[str, Optional[float]]:
    array = np.asarray([float(value) for value in values if value is not None and math.isfinite(float(value))], dtype=float)
    if array.size == 0:
        return {"count": 0, "p10": None, "p25": None, "median": None, "p75": None, "p90": None}
    quantiles = np.quantile(array, [0.10, 0.25, 0.50, 0.75, 0.90])
    return {"count": int(array.size), "p10": float(quantiles[0]), "p25": float(quantiles[1]), "median": float(quantiles[2]), "p75": float(quantiles[3]), "p90": float(quantiles[4])}


def _metric_comparison(diagnostics: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
    metrics = [
        "reference__design_a_min_prominence_rank",
        "reference__design_b_primary_survival_rank",
        "reference__design_b_geometric_survival_rank",
        "reference__design_c_ratio_survival_fraction",
        "reference__design_c_log_survival_fraction",
        "reference__design_c_local_vol_survival_fraction",
    ]
    rows: List[Mapping[str, object]] = []
    for left_index, left_name in enumerate(metrics):
        for right_name in metrics[left_index + 1:]:
            pairs = [(float(row[left_name]), float(row[right_name])) for row in diagnostics if row.get(left_name) is not None and row.get(right_name) is not None]
            left_values = [pair[0] for pair in pairs]
            right_values = [pair[1] for pair in pairs]
            left_top = {index for index, value in enumerate(left_values) if value >= 0.75}
            right_top = {index for index, value in enumerate(right_values) if value >= 0.75}
            union = left_top | right_top
            rows.append({
                "reference__left_metric": left_name,
                "reference__right_metric": right_name,
                "reference__matched_count": len(pairs),
                "reference__pearson_on_normalized_scores": _rank_correlation(left_values, right_values),
                "reference__mean_absolute_difference": float(np.mean(np.abs(np.asarray(left_values) - np.asarray(right_values)))) if pairs else None,
                "reference__top_quartile_jaccard": len(left_top & right_top) / len(union) if union else None,
            })
    return rows


def price_scale_diagnostics(diagnostics: Sequence[Mapping[str, object]]) -> Mapping[str, Optional[float]]:
    metric_names = (
        "reference__design_a_min_prominence_rank",
        "reference__design_b_primary_survival_rank",
        "reference__design_c_log_survival_fraction",
        "reference__design_c_local_vol_survival_fraction",
    )
    eligible = [
        row for row in diagnostics
        if bool(row.get("reference__primary_sequence_eligible"))
        and all(row.get(name) is not None for name in metric_names)
    ]
    log_prices = [math.log(float(row["pivot_price"])) for row in eligible]
    return {
        "corr_log_price_design_a_rank": _rank_correlation(log_prices, [float(row[metric_names[0]]) for row in eligible]),
        "corr_log_price_design_b_rank": _rank_correlation(log_prices, [float(row[metric_names[1]]) for row in eligible]),
        "corr_log_price_design_c_log_survival": _rank_correlation(log_prices, [float(row[metric_names[2]]) for row in eligible]),
        "corr_log_price_design_c_local_vol_survival": _rank_correlation(log_prices, [float(row[metric_names[3]]) for row in eligible]),
    }


def _long_rows(
    events: Sequence[PivotEvent],
    prepared: PreparedSequence,
    hierarchies: Mapping[str, Mapping[str, RemovalRecord]],
    sweeps: Mapping[str, Sequence[SweepRow]],
) -> List[Mapping[str, object]]:
    event_by_id = {event.event_id: event for event in events}
    sequence_ids = [event.event_id for event in prepared.sequence]
    rows: List[Mapping[str, object]] = []
    for variant, hierarchy in sorted(hierarchies.items()):
        for scale in DESIGN_B_LOG_SCALES:
            retained_ids = [event_id for event_id in sequence_ids if hierarchy[event_id].reference__removal_log_scale is None or float(hierarchy[event_id].reference__removal_log_scale) > scale]
            positions = {event_id: index for index, event_id in enumerate(retained_ids)}
            for event in events:
                if event.is_dual:
                    retained: Optional[bool] = None
                    status = "deferred_dual_no_temporal_order"
                    previous = next_id = None
                else:
                    index = positions.get(event.event_id)
                    retained = index is not None
                    status = "evaluated"
                    previous = retained_ids[index - 1] if index is not None and index > 0 else None
                    next_id = retained_ids[index + 1] if index is not None and index + 1 < len(retained_ids) else None
                rows.append({
                    "pivot_id": event.event_id,
                    "reference__method": "design_b_hierarchical_simplification",
                    "reference__method_variant": variant,
                    "reference__parameter": scale,
                    "reference__parameter_units": "absolute_log_price",
                    "reference__retained": retained,
                    "reference__removed": None if retained is None else not retained,
                    "reference__previous_structural_pivot_id": previous,
                    "reference__next_structural_pivot_id": next_id,
                    "reference__row_status": status,
                })
    family_units = {
        "retracement_ratio": "ratio",
        "log_price": "absolute_log_price",
        "local_volatility": "trailing_42_bar_median_true_range_multiples",
    }
    for family, sweep_rows in sorted(sweeps.items()):
        lookup = {(row.parameter, row.event_id): row for row in sweep_rows}
        parameters = sorted({row.parameter for row in sweep_rows})
        for parameter in parameters:
            for event in events:
                sweep = lookup.get((parameter, event.event_id))
                rows.append({
                    "pivot_id": event.event_id,
                    "reference__method": "design_c_reversal_scale_sweep",
                    "reference__method_variant": family,
                    "reference__parameter": parameter,
                    "reference__parameter_units": family_units[family],
                    "reference__retained": sweep.retained if sweep is not None else None,
                    "reference__removed": not sweep.retained if sweep is not None else None,
                    "reference__previous_structural_pivot_id": sweep.previous_event_id if sweep is not None else None,
                    "reference__next_structural_pivot_id": sweep.next_event_id if sweep is not None else None,
                    "reference__row_status": "evaluated" if sweep is not None else "deferred_dual_or_prepass_removed",
                })
    for event_id in prepared.deferred_duals:
        event = event_by_id[event_id]
        rows.append({
            "pivot_id": event.event_id,
            "reference__method": "dual_sensitivity",
            "reference__method_variant": "unordered_same_bar_event",
            "reference__parameter": None,
            "reference__parameter_units": "not_applicable",
            "reference__retained": None,
            "reference__removed": None,
            "reference__previous_structural_pivot_id": None,
            "reference__next_structural_pivot_id": None,
            "reference__row_status": "preserved_without_intrabar_order",
        })
    return rows


def _svg_chart(
    candles: Sequence[Candle],
    events: Sequence[PivotEvent],
    diagnostics_by_id: Mapping[str, Mapping[str, object]],
    hierarchy: Mapping[str, RemovalRecord],
    c_log_rows: Sequence[SweepRow],
    start: int,
    end: int,
    title: str,
) -> str:
    width, height = 1500, 900
    left, right, top, price_bottom = 80, 1450, 70, 610
    window = candles[start:end]
    window_events = [event for event in events if start <= event.bar_index < end]
    low = min(candle.low for candle in window)
    high = max(candle.high for candle in window)
    span = max(high - low, 1.0)
    def x(bar_index: int) -> float:
        return left + (bar_index - start + 0.5) * (right - left) / max(1, end - start)
    def y(price: float) -> float:
        return top + (high - price) / span * (price_bottom - top)
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{left + 20}" y="35" font-family="sans-serif" font-size="22" font-weight="bold">{title}</text>',
        f'<text x="{left + 20}" y="58" font-family="sans-serif" font-size="13" fill="#444">Canonical BTCUSDT futures 4H · retrospective reference diagnostics · no trading signals</text>',
    ]
    candle_width = max(1.0, (right - left) / max(1, end - start) * 0.55)
    for candle in window:
        color = "#16856b" if candle.close >= candle.open else "#c44e52"
        cx = x(candle.index)
        pieces.append(f'<line x1="{cx:.2f}" x2="{cx:.2f}" y1="{y(candle.high):.2f}" y2="{y(candle.low):.2f}" stroke="{color}" stroke-width="1"/>')
        body_y = min(y(candle.open), y(candle.close))
        body_h = max(1.0, abs(y(candle.open) - y(candle.close)))
        pieces.append(f'<rect x="{cx-candle_width/2:.2f}" y="{body_y:.2f}" width="{candle_width:.2f}" height="{body_h:.2f}" fill="{color}" opacity="0.72"/>')
    for event in window_events:
        diagnostic = diagnostics_by_id[event.event_id]
        rank = diagnostic.get("reference__design_a_min_prominence_rank")
        radius = 3.0 if rank is None else 3.0 + 7.0 * float(rank)
        color = "#7f7f7f" if event.is_dual else ("#d62728" if event.pivot_type == "HIGH" else "#1f77b4")
        pieces.append(f'<circle cx="{x(event.bar_index):.2f}" cy="{y(event.price):.2f}" r="{radius:.2f}" fill="none" stroke="{color}" stroke-width="1.4" opacity="0.85"/>')
    pieces.append(f'<text x="{left}" y="{price_bottom+25}" font-family="sans-serif" font-size="13">Raw pivots; circle radius = Design A minimum two-sided prominence percentile. Grey = unordered dual event.</text>')
    rows_y = [680, 730, 780, 830]
    labels = ["B ≥1%", "B ≥3%", "B ≥7.5%", "C log ≥3%"]
    b_scales = [0.01, 0.03, 0.075]
    for row_y, label in zip(rows_y, labels):
        pieces.append(f'<line x1="{left}" x2="{right}" y1="{row_y}" y2="{row_y}" stroke="#dddddd"/>')
        pieces.append(f'<text x="10" y="{row_y+4}" font-family="sans-serif" font-size="12">{label}</text>')
    for scale, row_y in zip(b_scales, rows_y[:3]):
        for event in window_events:
            record = hierarchy.get(event.event_id)
            if record is None or event.is_dual:
                continue
            retained = record.reference__removal_log_scale is None or float(record.reference__removal_log_scale) > scale
            if retained:
                pieces.append(f'<circle cx="{x(event.bar_index):.2f}" cy="{row_y}" r="3.2" fill="#9467bd"/>')
    c_lookup = {(row.parameter, row.event_id): row for row in c_log_rows}
    for event in window_events:
        row = c_lookup.get((0.03, event.event_id))
        if row is not None and row.retained:
            pieces.append(f'<circle cx="{x(event.bar_index):.2f}" cy="{rows_y[3]}" r="3.2" fill="#ff7f0e"/>')
    pieces.append(f'<text x="{left}" y="875" font-family="sans-serif" font-size="12" fill="#555">Design B uses deterministic removal hierarchy; Design C re-extracts at each scale. Dots are retained pivots; absent duals are deferred, not ordered.</text>')
    pieces.append("</svg>\n")
    return "".join(pieces)


def _chart_windows() -> Sequence[Tuple[str, int, int, str]]:
    return (
        ("directional_many_micro", 2832, 2922, "Strong directional move with many raw micro-pivots"),
        ("choppy_sideways", 3816, 3906, "Choppy / low-efficiency high-path window"),
        ("major_reversal", 1074, 1164, "Large reversal window"),
        ("high_density", 13686, 13776, "High raw-pivot density window"),
        ("low_density", 10476, 10566, "Low raw-pivot density window"),
        ("calibration_2026", 14743, 15013, "2026 human-calibration window (non-label)"),
    )


def _git_state(repo_root: Path) -> Tuple[str, bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True)
    return commit, bool(status.strip())


def build(data_root: Path, repo_root: Path, output_dir: Path, mode: str, stamped_commit: Optional[str]) -> Mapping[str, object]:
    stage_a_dir = data_root / "research" / "stage2i_a_raw_4h_pivots"
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.json"
    atomic_json(progress_path, {"stage": STAGE_VERSION, "mode": mode, "status": "loading_sources"})
    candles, candle_manifest_sha = _load_candles(data_root)
    events, source_rows, pivot_sha = _load_pivots(stage_a_dir)
    if mode == "smoke":
        events = [event for event in events if 14743 <= event.bar_index < 15013]
        if not events:
            raise ValueError("Smoke window contains no pivots")
    prepared = prepare_sequence(events, dual_mode="deferred")
    if any(left.bar_index >= right.bar_index for left, right in zip(prepared.sequence, prepared.sequence[1:])):
        raise ValueError("Fabricated or non-increasing primary sequence")
    atomic_json(progress_path, {"stage": STAGE_VERSION, "mode": mode, "status": "design_a_complete", "source_events": len(events)})
    design_a = design_a_metrics(prepared, candles)
    dual_design_a = unordered_dual_design_a_metrics(events, candles)
    hierarchy_min = hierarchical_simplification(prepared, "minimum_log_excursion")
    hierarchy_geo = hierarchical_simplification(prepared, "geometric_mean_log_excursion")
    local_scales = local_volatility_scales(candles, events)
    sweeps = {
        "retracement_ratio": threshold_sweep(prepared, DESIGN_C_RATIO_SCALES, "retracement_ratio", local_scales),
        "log_price": threshold_sweep(prepared, DESIGN_C_LOG_SCALES, "log_price", local_scales),
        "local_volatility": threshold_sweep(prepared, DESIGN_C_VOL_SCALES, "local_volatility", local_scales),
    }
    if mode == "smoke":
        if hierarchy_min != hierarchical_simplification(prepared, "minimum_log_excursion"):
            raise ValueError("Design B is not deterministic")
        for family, rows in sweeps.items():
            scales = {"retracement_ratio": DESIGN_C_RATIO_SCALES, "log_price": DESIGN_C_LOG_SCALES, "local_volatility": DESIGN_C_VOL_SCALES}[family]
            if list(rows) != threshold_sweep(prepared, scales, family, local_scales):
                raise ValueError(f"Design C {family} is not deterministic")
    atomic_json(progress_path, {"stage": STAGE_VERSION, "mode": mode, "status": "designs_b_c_complete", "source_events": len(events)})

    a_values = {event_id: values["minimum_log"] for event_id, values in design_a.items()}
    a_ranks = empirical_rank(a_values)
    b_min_values = {event_id: record.reference__removal_log_scale for event_id, record in hierarchy_min.items()}
    b_geo_values = {event_id: record.reference__removal_log_scale for event_id, record in hierarchy_geo.items()}
    b_min_ranks = empirical_rank(b_min_values, [event_id for event_id, record in hierarchy_min.items() if record.reference__edge_censored])
    b_geo_ranks = empirical_rank(b_geo_values, [event_id for event_id, record in hierarchy_geo.items() if record.reference__edge_censored])
    c_survival = {family: _sweep_survival(rows) for family, rows in sweeps.items()}
    event_by_id = {event.event_id: event for event in events}
    source_manifest_value = str(source_rows[0]["source_manifest_sha256"])
    local_volatility_pct_values = sorted(
        scale / event_by_id[event_id].price
        for event_id, scale in local_scales.items()
        if event_id in event_by_id
    )
    volatility_cutpoints = np.quantile(np.asarray(local_volatility_pct_values, dtype=float), [1 / 3, 2 / 3])
    diagnostics: List[Mapping[str, object]] = []
    for event in sorted(events, key=lambda item: (item.bar_index, item.event_id)):
        a = design_a.get(event.event_id, {})
        b_min = hierarchy_min.get(event.event_id)
        b_geo = hierarchy_geo.get(event.event_id)
        dual_a = dual_design_a.get(event.event_id, {})
        local_volatility_pct = local_scales.get(event.event_id, 0.0) / event.price if event.event_id in local_scales else None
        if local_volatility_pct is None:
            volatility_regime = None
        elif local_volatility_pct <= float(volatility_cutpoints[0]):
            volatility_regime = "low"
        elif local_volatility_pct <= float(volatility_cutpoints[1]):
            volatility_regime = "middle"
        else:
            volatility_regime = "high"
        ranks = [value for value in (
            a_ranks.get(event.event_id), b_min_ranks.get(event.event_id),
            c_survival["retracement_ratio"].get(event.event_id), c_survival["log_price"].get(event.event_id),
            c_survival["local_volatility"].get(event.event_id),
        ) if value is not None]
        stable_core = len(ranks) == 5 and min(float(value) for value in ranks) >= 0.75
        fragile_core = len(ranks) == 5 and max(float(value) for value in ranks) <= 0.25
        left_boundary, right_boundary = chronological_boundary_flags(prepared, event.event_id)
        row: Dict[str, object] = {
            "event_id": event.event_id,
            "pivot_bar_index": event.bar_index,
            "pivot_timestamp": event.timestamp,
            "pivot_type": event.pivot_type,
            "pivot_price": event.price,
            "year": event.timestamp.year,
            "source_manifest_sha256": source_manifest_value,
            "dual_flag": event.is_dual,
            "reference__primary_sequence_eligible": event.event_id in {item.event_id for item in prepared.sequence},
            "reference__dual_treatment_primary": "deferred" if event.is_dual else "not_dual",
            "reference__dual_unordered_event_preserved": event.is_dual,
            "reference__dual_unordered_design_a_min_log_prominence": dual_a.get("minimum_log"),
            "reference__dual_unordered_design_a_geometric_log_prominence": dual_a.get("geometric_log"),
            "reference__dual_unordered_incoming_duration_bars": dual_a.get("incoming_bars"),
            "reference__dual_unordered_outgoing_duration_bars": dual_a.get("outgoing_bars"),
            "reference__design_a_incoming_log_excursion": a.get("incoming_log"),
            "reference__design_a_outgoing_log_excursion": a.get("outgoing_log"),
            "reference__design_a_min_log_prominence": a.get("minimum_log"),
            "reference__design_a_geometric_log_prominence": a.get("geometric_log"),
            "reference__design_a_harmonic_log_prominence": a.get("harmonic_log"),
            "reference__design_a_balance_ratio": a.get("balance"),
            "reference__design_a_incoming_duration_bars": a.get("incoming_bars"),
            "reference__design_a_outgoing_duration_bars": a.get("outgoing_bars"),
            "reference__design_a_incoming_path_efficiency": a.get("incoming_efficiency"),
            "reference__design_a_outgoing_path_efficiency": a.get("outgoing_efficiency"),
            "reference__design_a_incoming_directional_persistence": a.get("incoming_persistence"),
            "reference__design_a_outgoing_directional_persistence": a.get("outgoing_persistence"),
            "reference__design_a_incoming_alternation": a.get("incoming_alternation"),
            "reference__design_a_outgoing_alternation": a.get("outgoing_alternation"),
            "reference__design_a_min_prominence_rank": a_ranks.get(event.event_id),
            "reference__design_b_primary_removal_iteration": b_min.reference__removal_iteration if b_min else None,
            "reference__design_b_primary_removal_log_scale": b_min.reference__removal_log_scale if b_min else None,
            "reference__design_b_primary_edge_censored": b_min.reference__edge_censored if b_min else None,
            "reference__design_b_primary_removal_reason": b_min.reference__removal_reason if b_min else "deferred_dual",
            "reference__design_b_primary_survival_rank": b_min_ranks.get(event.event_id),
            "reference__design_b_geometric_removal_log_scale": b_geo.reference__removal_log_scale if b_geo else None,
            "reference__design_b_geometric_survival_rank": b_geo_ranks.get(event.event_id),
            "reference__design_c_ratio_survival_fraction": c_survival["retracement_ratio"].get(event.event_id),
            "reference__design_c_log_survival_fraction": c_survival["log_price"].get(event.event_id),
            "reference__design_c_local_vol_survival_fraction": c_survival["local_volatility"].get(event.event_id),
            "reference__local_volatility_scale_usdt": local_scales.get(event.event_id),
            "reference__local_volatility_scale_fraction": local_volatility_pct,
            "reference__volatility_regime_tertile": volatility_regime,
            "reference__cross_design_mean_stability": float(np.mean(np.asarray(ranks, dtype=float))) if ranks else None,
            "reference__cross_design_range": max(ranks) - min(ranks) if ranks else None,
            "reference__descriptor_stable_core_top_quartile_all": stable_core,
            "reference__descriptor_fragile_core_bottom_quartile_all": fragile_core,
            "reference__descriptor_high_disagreement": (max(ranks) - min(ranks) >= 0.50) if ranks else None,
            "reference__right_boundary_unresolved": right_boundary,
            "reference__left_boundary_censored": left_boundary,
        }
        diagnostics.append(row)
    assert_reference_namespace(diagnostics[0].keys())
    if mode == "production":
        validate_source_identity([str(row["event_id"]) for row in source_rows], [str(row["event_id"]) for row in diagnostics])

    long_rows = _long_rows(events, prepared, {
        "minimum_log_excursion": hierarchy_min,
        "geometric_mean_log_excursion": hierarchy_geo,
    }, sweeps)
    assert_reference_namespace(long_rows[0].keys())
    comparisons = _metric_comparison(diagnostics)
    assert_reference_namespace(comparisons[0].keys())

    diagnostics_by_id = {str(row["event_id"]): row for row in diagnostics}
    charts_dir = output_dir / "plots"
    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_files: List[str] = []
    for chart_id, start, end, title in _chart_windows():
        if mode == "smoke" and chart_id != "calibration_2026":
            continue
        svg = _svg_chart(candles, events, diagnostics_by_id, hierarchy_min, sweeps["log_price"], start, end, title)
        name = f"b1_{chart_id}.svg"
        atomic_text(charts_dir / name, svg)
        chart_files.append(f"plots/{name}")

    stable = [row for row in diagnostics if row["reference__descriptor_stable_core_top_quartile_all"]]
    fragile = [row for row in diagnostics if row["reference__descriptor_fragile_core_bottom_quartile_all"]]
    disagreement = [row for row in diagnostics if row["reference__descriptor_high_disagreement"]]
    nondual = [row for row in diagnostics if not row["dual_flag"]]
    years: Dict[str, object] = {}
    for year in sorted({int(row["year"]) for row in diagnostics}):
        year_rows = [row for row in diagnostics if int(row["year"]) == year]
        eligible = [row for row in year_rows if row["reference__primary_sequence_eligible"]]
        years[str(year)] = {
            "raw_events": len(year_rows), "primary_eligible": len(eligible),
            "median_price": float(np.median([float(row["pivot_price"]) for row in year_rows])),
            "design_a_min_prominence": _describe([row["reference__design_a_min_log_prominence"] for row in eligible]),
            "design_b_survival_rank": _describe([row["reference__design_b_primary_survival_rank"] for row in eligible]),
            "design_c_mean_survival": _describe([row["reference__cross_design_mean_stability"] for row in eligible]),
            "stable_core_count": sum(bool(row["reference__descriptor_stable_core_top_quartile_all"]) for row in year_rows),
            "fragile_core_count": sum(bool(row["reference__descriptor_fragile_core_bottom_quartile_all"]) for row in year_rows),
        }
    volatility_regimes: Dict[str, object] = {}
    for regime in ("low", "middle", "high"):
        regime_rows = [row for row in diagnostics if row["reference__volatility_regime_tertile"] == regime and row["reference__primary_sequence_eligible"]]
        volatility_regimes[regime] = {
            "events": len(regime_rows),
            "design_a_min_prominence": _describe([row["reference__design_a_min_log_prominence"] for row in regime_rows]),
            "design_b_survival_rank": _describe([row["reference__design_b_primary_survival_rank"] for row in regime_rows]),
            "design_c_local_vol_survival": _describe([row["reference__design_c_local_vol_survival_fraction"] for row in regime_rows]),
            "cross_design_stability": _describe([row["reference__cross_design_mean_stability"] for row in regime_rows]),
        }
    absolute_price_scale_diagnostics = price_scale_diagnostics(diagnostics)
    calibration: Dict[str, object] = {}
    for low, high in ((59000.0, 60500.0), (61500.0, 62500.0), (66500.0, 69000.0)):
        selected = [row for row in diagnostics if int(row["year"]) == 2026 and low <= float(row["pivot_price"]) <= high]
        calibration[f"{int(low)}_{int(high)}"] = {
            "events": len(selected),
            "high": sum(row["pivot_type"] == "HIGH" for row in selected),
            "low": sum(row["pivot_type"] == "LOW" for row in selected),
            "stable_core": sum(bool(row["reference__descriptor_stable_core_top_quartile_all"]) for row in selected),
            "fragile_core": sum(bool(row["reference__descriptor_fragile_core_bottom_quartile_all"]) for row in selected),
            "high_disagreement": sum(bool(row["reference__descriptor_high_disagreement"]) for row in selected),
            "stability_distribution": _describe([row["reference__cross_design_mean_stability"] for row in selected]),
        }
    iteration_one = sum(record.reference__removal_iteration == 1 for record in hierarchy_min.values())
    lightest_scale_removed = sum(
        record.reference__removal_log_scale is not None and float(record.reference__removal_log_scale) <= 0.005
        for record in hierarchy_min.values()
    )
    summary: Dict[str, object] = {
        "stage": STAGE_VERSION,
        "status": "RESEARCH_COMPLETE_REFERENCE_CONTRACT_OPEN",
        "mode": mode,
        "source_population": {
            "raw_pivots": len(events), "high": sum(event.pivot_type == "HIGH" for event in events),
            "low": sum(event.pivot_type == "LOW" for event in events),
            "dual_events": sum(event.is_dual for event in events),
            "dual_candles": len({event.bar_index for event in events if event.is_dual}),
            "primary_nondual_alternating_sequence": len(prepared.sequence),
            "same_type_prepass_removed": len(prepared.prepass_removed),
        },
        "designs": {
            "a": "two-sided log prominence with minimum/geometric/harmonic formulations and path components",
            "b": "deterministic alternating-sequence hierarchy with minimum and geometric local costs",
            "c": "full retracement-ratio, log-price, and trailing-volatility-normalized threshold sweeps",
        },
        "descriptive_populations_not_labels": {
            "hierarchy_iteration_one_removed": iteration_one,
            "hierarchy_removed_by_0_5pct_log_scale": lightest_scale_removed,
            "stable_core_top_quartile_all_designs": len(stable),
            "fragile_core_bottom_quartile_all_designs": len(fragile),
            "high_cross_design_range_ge_0_50": len(disagreement),
            "eligible_nondual_count": len(nondual),
        },
        "pairwise_design_comparison": comparisons,
        "year_stability": years,
        "volatility_regime_stability": volatility_regimes,
        "absolute_price_scale_diagnostics": absolute_price_scale_diagnostics,
        "calibration_2026_non_label": calibration,
        "dual_sensitivity": {
            "primary": "deferred from alternating sequence",
            "sensitivity": "both same-bar extrema preserved as unordered diagnostic events",
            "events": len(prepared.deferred_duals),
            "fabricated_same_bar_transitions": 0,
            "unordered_design_a_events_with_two_sided_support": len(dual_design_a),
            "unordered_design_a_min_prominence": _describe([row["minimum_log"] for row in dual_design_a.values()]),
        },
        "methodology_conclusion": "Continuous/multiscale evidence retained; no binary reference contract selected.",
        "open_methodology_questions": [
            "Whether the future B1 contract should be continuous, ordinal, confidence-weighted, or partially binary.",
            "Whether minimum or geometric two-sided support should be primary.",
            "Whether dual outside bars should remain deferred or become a separate structural state.",
            "Whether a scale family should be preferred after explicit user review; current study preserves all variants.",
        ],
    }

    diagnostics_path = output_dir / "b1_pivot_reference_diagnostics.parquet"
    long_path = output_dir / "b1_segmentations_long.parquet"
    comparison_csv = output_dir / "b1_design_comparison.csv"
    comparison_parquet = output_dir / "b1_design_comparison.parquet"
    write_deterministic_parquet(diagnostics_path, diagnostics)
    write_deterministic_parquet(long_path, long_rows)
    write_csv(comparison_csv, comparisons)
    write_deterministic_parquet(comparison_parquet, comparisons)
    atomic_json(output_dir / "b1_summary.json", summary)

    schema = {
        "stage": STAGE_VERSION,
        "information_contract": {
            "reference__": "retrospective/offline; may use realized future; prohibited as B2/live predictor",
            "postevent__": "future-relative diagnostic; prohibited as B2/live predictor",
            "identity": "source identity/provenance only",
        },
        "tables": {},
    }
    for name, path, key in (
        ("b1_pivot_reference_diagnostics.parquet", diagnostics_path, ["event_id"]),
        ("b1_segmentations_long.parquet", long_path, ["reference__method", "reference__method_variant", "reference__parameter", "pivot_id"]),
        ("b1_design_comparison.parquet", comparison_parquet, ["reference__left_metric", "reference__right_metric"]),
    ):
        arrow_schema = pq.read_schema(path)
        schema["tables"][name] = {
            "rows": pq.ParquetFile(path).metadata.num_rows,
            "primary_key": key,
            "columns": [{"name": field.name, "arrow_type": str(field.type), "information_status": "reference" if field.name.startswith("reference__") else "identity"} for field in arrow_schema],
        }
    atomic_json(output_dir / "b1_schema.json", schema)
    atomic_text(output_dir / "README.md", (
        "# Stage 2I-B1 generated artifacts\n\n"
        "Offline retrospective reference research only. Fields prefixed `reference__` or `postevent__` "
        "use realized structure and are forbidden as Stage 2I-B2/live predictors. No binary structural "
        "label or final B1 reference contract is created. See `b1_schema.json` and `b1_summary.json`.\n"
    ))

    current_commit, dirty = _git_state(repo_root)
    pipeline_path = Path(__file__).resolve()
    artifacts = [diagnostics_path, long_path, comparison_csv, comparison_parquet, output_dir / "b1_summary.json", output_dir / "b1_schema.json", output_dir / "README.md"] + [output_dir / name for name in chart_files]
    manifest = {
        "stage": STAGE_VERSION,
        "mode": mode,
        "qa_status": "PASS",
        "source": {
            "stage_a_commit": STAGE_A_COMMIT,
            "stage_a_review_commit": STAGE_A_REVIEW_COMMIT,
            "canonical_architecture_commit": CANONICAL_ARCHITECTURE_COMMIT,
            "raw_pivots_sha256": pivot_sha,
            "canonical_candle_manifest_sha256": candle_manifest_sha,
        },
        "config": {
            "local_volatility_lookback_bars": LOCAL_VOL_LOOKBACK,
            "design_b_log_scales": DESIGN_B_LOG_SCALES,
            "design_c_ratio_scales": DESIGN_C_RATIO_SCALES,
            "design_c_log_scales": DESIGN_C_LOG_SCALES,
            "design_c_volatility_scales": DESIGN_C_VOL_SCALES,
            "dual_primary": "deferred",
            "dual_sensitivity": "unordered_same_bar_events",
        },
        "pipeline_path": str(pipeline_path),
        "pipeline_sha256": sha256(pipeline_path),
        "git_commit_at_build": stamped_commit or current_commit,
        "git_worktree_dirty_at_build": dirty,
        "artifacts": {str(path.relative_to(output_dir)): sha256(path) for path in sorted(artifacts)},
        "row_counts": {name: table["rows"] for name, table in schema["tables"].items()},
    }
    atomic_json(output_dir / "manifest.json", manifest)
    checksum_targets = artifacts + [output_dir / "manifest.json"]
    checksum_lines = [f"{sha256(path)}  {path.relative_to(output_dir)}" for path in sorted(checksum_targets)]
    atomic_text(output_dir / "checksums.sha256", "\n".join(checksum_lines) + "\n")
    validate_checksums(output_dir)
    atomic_json(progress_path, {
        "stage": STAGE_VERSION, "mode": mode, "status": "complete", "qa_status": "PASS",
        "source_events": len(events), "artifact_count": len(checksum_targets),
    })
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("smoke", "production"), default="production")
    parser.add_argument("--stamp-git-commit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.data_root / "research" / "stage2i_b1_retrospective_reference"
    output_dir = root / "smoke" if args.mode == "smoke" else root
    summary = build(args.data_root, args.repo_root, output_dir, args.mode, args.stamp_git_commit)
    print(json.dumps({
        "status": summary["status"],
        "mode": args.mode,
        "source_population": summary["source_population"],
        "descriptive_populations_not_labels": summary["descriptive_populations_not_labels"],
        "output_dir": str(output_dir),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
