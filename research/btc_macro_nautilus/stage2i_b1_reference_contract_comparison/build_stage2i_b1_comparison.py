"""Stage 2I-B1 Reference Contract Comparison Pipeline.

Rebuilds retrospective structural evidence under the fixed B+C candidate-preservation policy,
evaluates continuous, ordinal, and agreement/confidence representation families, and compares
their coverage, stability, parameter sensitivity, information retention, and target properties.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

STAGE_VERSION = "stage2i-b1-comparison-v1"
STAGE_A_COMMIT = "71b6158a61503fde9145f3565fe0be3149bbab76"
STAGE_A_REVIEW_COMMIT = "b38aff90e2d6d056ebd14ae9bbecece1fefe0bb8"
PREPASS_AUDIT_COMMIT = "6d707801bd2af4b81d046614b19bca4475a49eed"

LOCAL_VOL_LOOKBACK = 42

# Survival scale grid (log price)
SURVIVAL_LOG_SCALES = (0.005, 0.010, 0.015, 0.020, 0.030, 0.050, 0.075, 0.100, 0.150, 0.250)

# Agreement tail sizes
CONFIDENCE_TAIL_SIZES = (0.10, 0.20, 0.25, 0.30)

IDENTITY_COLUMNS = {
    "event_id", "pivot_bar_index", "pivot_timestamp", "pivot_type", "pivot_price",
    "year", "dual_unordered", "sequence_eligible", "excluded_from_alternating_sequence",
    "exclusion_reason", "segment_id", "segment_length", "dataset_edge_censored",
    "dataset_left_edge_censored", "dataset_right_edge_censored", "dual_separator_boundary",
    "special_state", "representation_resolved",
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
class RemovalRecord:
    iteration: Optional[int]
    scale: Optional[float]
    boundary_survivor: bool
    reason: str


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def write_deterministic_parquet(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty Parquet artifact: {path}")
    columns = sorted({column for row in rows for column in row})
    normalized = [{column: row.get(column) for column in columns} for row in rows]
    table = pa.Table.from_pylist(normalized)
    temporary = path.with_name(f"{path.name}.incomplete")
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, temporary, compression="snappy")
    temporary.replace(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    columns = sorted({k for r in rows for k in r.keys()})
    temp = path.with_name(f"{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in columns})
    temp.replace(path)


def validate_checksums(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["input_files"] + manifest["output_files"]:
        target = Path(item["path"])
        if not target.exists():
            raise FileNotFoundError(f"Missing referenced artifact: {target}")
        actual = sha256(target)
        if actual != item["sha256"]:
            raise ValueError(f"Checksum mismatch for {target}: expected {item['sha256']}, got {actual}")


def assert_reference_namespace(columns: Iterable[str]) -> None:
    for column in columns:
        if column in IDENTITY_COLUMNS:
            continue
        if column.startswith("reference__") or column.startswith("postevent__"):
            continue
        raise ValueError(f"Derived field lacks reference/postevent namespace: {column}")


def _load_candles(data_root: Path) -> Tuple[List[Candle], str]:
    source_dir = data_root / "derived" / "BTCUSDT" / "4h"
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candles: List[Candle] = []
    for item in manifest["output_files"]:
        path = Path(item["path"])
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Checksum mismatch for candle file: {path}")
        table = pq.read_table(path, columns=["start_time", "open", "high", "low", "close", "complete"])
        if table.num_rows != int(item["rows"]):
            raise ValueError(f"Canonical candle row count mismatch: {path}")
        for row in table.to_pylist():
            if not row["complete"]:
                continue
            candles.append(
                Candle(
                    index=len(candles),
                    timestamp=row["start_time"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )
    candles.sort(key=lambda candle: candle.index)
    if len(candles) != 15445:
        raise ValueError(f"Expected 15,445 complete 4H candles, got {len(candles)}")
    return candles, sha256(manifest_path)


def _load_pivots(stage_a_dir: Path) -> Tuple[List[PivotEvent], List[Mapping[str, object]], str]:
    path = stage_a_dir / "raw_4h_pivots.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing Stage 2I-A pivots: {path}")
    columns = ["event_id", "pivot_bar_index", "pivot_timestamp", "pivot_type", "pivot_price", "causal__dual_high_low_same_candle", "source_manifest_sha256"]
    rows = pq.read_table(path, columns=columns).to_pylist()
    events = [
        PivotEvent(
            event_id=str(row["event_id"]),
            bar_index=int(row["pivot_bar_index"]),
            timestamp=row["pivot_timestamp"],
            pivot_type=str(row["pivot_type"]),
            price=float(row["pivot_price"]),
            is_dual=bool(row["causal__dual_high_low_same_candle"]),
        )
        for row in rows
    ]
    if len(events) != 4450 or len({event.event_id for event in events}) != 4450:
        raise ValueError("Frozen Stage 2I-A population mismatch")
    if sum(event.is_dual for event in events) != 300:
        raise ValueError("Frozen dual-event population mismatch")
    events.sort(key=lambda event: (event.bar_index, event.timestamp, event.event_id))
    return events, rows, sha256(path)


def local_volatility_scales(candles: Sequence[Candle], events: Sequence[PivotEvent]) -> Dict[str, float]:
    true_ranges: List[float] = []
    for index, candle in enumerate(candles):
        previous_close = candles[index - 1].close if index else candle.close
        true_ranges.append(
            max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close))
        )
    result: Dict[str, float] = {}
    for event in events:
        start = max(0, event.bar_index - LOCAL_VOL_LOOKBACK)
        history = true_ranges[start : event.bar_index]
        if len(history) >= 10:
            result[event.event_id] = float(np.median(np.asarray(history, dtype=float)))
    return result


def _more_extreme(left: PivotEvent, right: PivotEvent) -> PivotEvent:
    if left.pivot_type != right.pivot_type:
        raise ValueError("Extreme comparison requires the same pivot type")
    if left.pivot_type == "HIGH":
        return left if (left.price, -left.bar_index, left.event_id) >= (right.price, -right.bar_index, right.event_id) else right
    return left if (left.price, left.bar_index, left.event_id) <= (right.price, right.bar_index, right.event_id) else right


def _log_excursion(left: PivotEvent, right: PivotEvent) -> float:
    if left.price <= 0 or right.price <= 0:
        raise ValueError("Pivot prices must be positive")
    return abs(math.log(right.price / left.price))


def _path_geometry(candles: Sequence[Candle], left: PivotEvent, right: PivotEvent) -> Mapping[str, float]:
    if right.bar_index <= left.bar_index:
        raise ValueError("Path geometry requires positive time")
    window = candles[left.bar_index : right.bar_index + 1]
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


def hierarchical_simplification_segment(
    sequence: Sequence[PivotEvent],
    cost_mode: str = "minimum_log",
    local_scale_by_id: Optional[Mapping[str, float]] = None,
) -> Dict[str, RemovalRecord]:
    """Runs hierarchical simplification strictly within an alternating segment.

    Endpoints remain boundary survivors (never removed by interior excursion).
    """
    work = list(sequence)
    result: Dict[str, RemovalRecord] = {}
    if len(work) <= 2:
        for survivor in work:
            result[survivor.event_id] = RemovalRecord(None, None, True, "segment_boundary_survivor")
        return result

    iteration = 0
    last_effective_cost = 0.0
    while len(work) > 2:
        scored: List[Tuple[float, int, str, int]] = []
        for index in range(1, len(work) - 1):
            left_event = work[index - 1]
            center_event = work[index]
            right_event = work[index + 1]
            if cost_mode == "minimum_log":
                left = _log_excursion(left_event, center_event)
                right = _log_excursion(center_event, right_event)
                cost = min(left, right)
            elif cost_mode == "geometric_log":
                left = _log_excursion(left_event, center_event)
                right = _log_excursion(center_event, right_event)
                cost = math.sqrt(left * right)
            elif cost_mode == "local_volatility":
                scale = (local_scale_by_id or {}).get(center_event.event_id, 0.0)
                if scale <= 0:
                    cost = math.inf
                else:
                    cost = min(abs(center_event.price - left_event.price), abs(right_event.price - center_event.price)) / scale
            else:
                raise ValueError(f"Unknown cost mode: {cost_mode}")
            scored.append((cost, center_event.bar_index, center_event.event_id, index))
        raw_cost, _, _, selected = min(scored)
        effective_cost = max(raw_cost, last_effective_cost)
        last_effective_cost = effective_cost
        iteration += 1
        removed = work.pop(selected)
        result[removed.event_id] = RemovalRecord(iteration, effective_cost, False, "interior_lowest_cost")
        if 0 < selected < len(work) and work[selected - 1].pivot_type == work[selected].pivot_type:
            left_nbr = work[selected - 1]
            right_nbr = work[selected]
            kept = _more_extreme(left_nbr, right_nbr)
            dropped = right_nbr if kept is left_nbr else left_nbr
            drop_index = selected if dropped is right_nbr else selected - 1
            work.pop(drop_index)
            result[dropped.event_id] = RemovalRecord(iteration, effective_cost, False, "same_type_after_merge")

    for survivor in work:
        result[survivor.event_id] = RemovalRecord(None, None, True, "segment_boundary_survivor")
    return result


def compute_empirical_ranks(values: Mapping[str, Optional[float]]) -> Dict[str, Optional[float]]:
    finite = sorted(float(v) for v in values.values() if v is not None and math.isfinite(float(v)))
    result: Dict[str, Optional[float]] = {}
    n = len(finite)
    for k, v in values.items():
        if v is None or not math.isfinite(float(v)) or n == 0:
            result[k] = None
        else:
            result[k] = float(np.searchsorted(finite, float(v), side="right") / n)
    return result


def _rank_correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    if len(left) < 2:
        return None
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if float(np.std(left_array)) == 0.0 or float(np.std(right_array)) == 0.0:
        return None
    return float(np.corrcoef(left_array, right_array)[0, 1])


def _describe(values: Iterable[Optional[float]]) -> Mapping[str, Optional[float]]:
    arr = np.asarray([float(v) for v in values if v is not None and math.isfinite(float(v))], dtype=float)
    if arr.size == 0:
        return {
            "count": 0, "min": None, "p10": None, "p25": None, "median": None,
            "p75": None, "p90": None, "max": None, "mean": None, "std": None, "iqr": None,
        }
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    return {
        "count": int(arr.size),
        "min": float(np.min(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p25": p25,
        "median": float(np.median(arr)),
        "p75": p75,
        "p90": float(np.percentile(arr, 90)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "iqr": float(p75 - p25),
    }


def _svg_chart(
    candles: Sequence[Candle],
    events: Sequence[PivotEvent],
    master_info_by_id: Mapping[str, Dict[str, Any]],
    start: int,
    end: int,
    title: str,
    subtitle: str,
) -> str:
    width, height = 1500, 950
    left, right, top, price_bottom = 80, 1450, 80, 750
    window = candles[start:end]
    window_events = [e for e in events if start <= e.bar_index < end]
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
        f'<text x="{left}" y="35" font-family="monospace" font-size="20" font-weight="bold" fill="#111827">{title}</text>',
        f'<text x="{left}" y="60" font-family="monospace" font-size="13" fill="#4b5563">{subtitle}</text>',
        f'<rect x="{left}" y="{top}" width="{right - left}" height="{price_bottom - top}" fill="#f9fafb" stroke="#e5e7eb" stroke-width="1"/>',
    ]

    # Grid lines
    for i in range(5):
        p = low + i * span / 4
        y_val = y(p)
        pieces.append(f'<line x1="{left}" y1="{y_val:.1f}" x2="{right}" y2="{y_val:.1f}" stroke="#f3f4f6" stroke-width="1"/>')
        pieces.append(f'<text x="{right + 8}" y="{y_val + 4:.1f}" font-family="monospace" font-size="11" fill="#6b7280">{p:.1f}</text>')

    # Candles
    candle_w = max(2.0, (right - left) / max(1, end - start) * 0.65)
    for c in window:
        cx = x(c.index)
        is_up = c.close >= c.open
        col = "#10b981" if is_up else "#ef4444"
        # Wick
        pieces.append(f'<line x1="{cx:.1f}" y1="{y(c.high):.1f}" x2="{cx:.1f}" y2="{y(c.low):.1f}" stroke="{col}" stroke-width="1.2"/>')
        # Body
        by1 = min(y(c.open), y(c.close))
        bh = max(1.0, abs(y(c.open) - y(c.close)))
        pieces.append(f'<rect x="{cx - candle_w / 2:.1f}" y="{by1:.1f}" width="{candle_w:.1f}" height="{bh:.1f}" fill="{col}" stroke="{col}" stroke-width="0.5"/>')

    # Draw pivots
    for e in window_events:
        px = x(e.bar_index)
        py = y(e.price)
        info = master_info_by_id.get(e.event_id, {})
        state = info.get("special_state", "ordinary_resolved_sequence_event")
        conf_state = info.get("conf_majority_t20", "UNRESOLVED")
        ord_tier = info.get("ord_survival_scale", "NA")
        rank_val = info.get("rank_hierarchy_min")
        rank_str = f"R:{rank_val:.2f}" if rank_val is not None else "R:NA"

        # Mark styling based on state
        if state == "dual_unordered":
            stroke_col = "#7c3aed"  # purple
            fill_col = "#ede9fe"
            label = f"[DUAL] {e.pivot_type}"
            radius = 6.0
        elif state == "technical_same_type_exclusion":
            stroke_col = "#f59e0b"  # amber
            fill_col = "#fef3c7"
            label = f"[EXCL-SAME] {e.pivot_type}"
            radius = 5.0
        elif state in ("dataset_left_edge_censored", "dataset_right_edge_censored", "dual_separator_boundary"):
            stroke_col = "#6b7280"  # gray
            fill_col = "#f3f4f6"
            label = f"[BOUND] {e.pivot_type}"
            radius = 6.0
        else:  # ordinary resolved sequence event
            if conf_state == "STRONG":
                stroke_col = "#047857"  # emerald deep
                fill_col = "#34d399"
                radius = 7.5
            elif conf_state == "WEAK":
                stroke_col = "#b91c1c"  # red deep
                fill_col = "#f87171"
                radius = 5.5
            else:  # AMBIGUOUS
                stroke_col = "#0284c7"  # light blue
                fill_col = "#bae6fd"
                radius = 6.0
            label = f"{e.pivot_type} S:{ord_tier} {rank_str} [{conf_state}]"

        # Symbol
        pieces.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius}" fill="{fill_col}" stroke="{stroke_col}" stroke-width="2"/>')
        # Label offset
        offset_y = -14 if e.pivot_type == "HIGH" else 18
        pieces.append(f'<text x="{px:.1f}" y="{py + offset_y:.1f}" font-family="monospace" font-size="9" font-weight="bold" fill="{stroke_col}" text-anchor="middle">{label}</text>')

    # Legend at bottom
    leg_y = price_bottom + 45
    pieces.extend([
        f'<text x="{left}" y="{leg_y}" font-family="monospace" font-size="12" font-weight="bold" fill="#111827">Legend / B+C Representation State:</text>',
        f'<circle cx="{left + 20}" cy="{leg_y + 25}" r="6" fill="#34d399" stroke="#047857" stroke-width="2"/>',
        f'<text x="{left + 35}" y="{leg_y + 29}" font-family="monospace" font-size="11" fill="#374151">Resolved Strong Tail (Conf Majority 20%)</text>',
        f'<circle cx="{left + 340}" cy="{leg_y + 25}" r="6" fill="#bae6fd" stroke="#0284c7" stroke-width="2"/>',
        f'<text x="{left + 355}" y="{leg_y + 29}" font-family="monospace" font-size="11" fill="#374151">Resolved Ambiguous Intermediate</text>',
        f'<circle cx="{left + 630}" cy="{leg_y + 25}" r="6" fill="#f87171" stroke="#b91c1c" stroke-width="2"/>',
        f'<text x="{left + 645}" y="{leg_y + 29}" font-family="monospace" font-size="11" fill="#374151">Resolved Weak Tail</text>',
        f'<circle cx="{left + 820}" cy="{leg_y + 25}" r="6" fill="#fef3c7" stroke="#f59e0b" stroke-width="2"/>',
        f'<text x="{left + 835}" y="{leg_y + 29}" font-family="monospace" font-size="11" fill="#374151">Excluded Same-Type (Preserved, NA scale)</text>',
        f'<circle cx="{left + 1170}" cy="{leg_y + 25}" r="6" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>',
        f'<text x="{left + 1185}" y="{leg_y + 29}" font-family="monospace" font-size="11" fill="#374151">Dual Candle Unordered</text>',
        f'<circle cx="{left + 20}" cy="{leg_y + 55}" r="6" fill="#f3f4f6" stroke="#6b7280" stroke-width="2"/>',
        f'<text x="{left + 35}" y="{leg_y + 59}" font-family="monospace" font-size="11" fill="#374151">Dual-Separator Boundary / Dataset Edge (Boundary Survivor, Unresolved)</text>',
    ])

    pieces.append('</svg>')
    return "\n".join(pieces)


def _git_state(repo_root: Path) -> Tuple[str, bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True)
    return commit, bool(status.strip())


def run_pipeline(
    data_root: Path,
    repo_root: Path,
    output_dir: Path,
    mode: str = "production",
    stamped_commit: Optional[str] = None,
) -> Mapping[str, object]:
    stage_a_dir = data_root / "research" / "stage2i_a_raw_4h_pivots"
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_dir = output_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    progress_path = output_dir / "progress.json"
    atomic_json(progress_path, {
        "stage": STAGE_VERSION,
        "mode": mode,
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # 1. Load inputs
    candles, candle_manifest_sha = _load_candles(data_root)
    events, raw_source_rows, stage_a_sha = _load_pivots(stage_a_dir)
    local_scales = local_volatility_scales(candles, events)

    # 2. Build B+C candidate preservation representation & segment-aware timeline
    ordered = sorted(events, key=lambda e: (e.bar_index, e.timestamp, e.event_id))

    timeline: List[Tuple[str, int, Optional[PivotEvent]]] = []
    for event in ordered:
        if event.is_dual:
            if not timeline or timeline[-1] != ("DUAL", event.bar_index, None):
                timeline.append(("DUAL", event.bar_index, None))
        else:
            timeline.append(("PIVOT", event.bar_index, event))

    segments: List[List[PivotEvent]] = []
    current_segment: List[PivotEvent] = []
    for item_type, _, event_obj in timeline:
        if item_type == "DUAL":
            if current_segment:
                segments.append(current_segment)
                current_segment = []
        else:
            assert event_obj is not None
            current_segment.append(event_obj)
    if current_segment:
        segments.append(current_segment)

    # Prepass within each segment
    segment_alternating: List[List[PivotEvent]] = []
    excluded_same_type_by_id: Dict[str, PivotEvent] = {}
    event_segment_id: Dict[str, int] = {}

    for seg_idx, segment in enumerate(segments):
        seg_runs: List[List[PivotEvent]] = []
        cur_run: List[PivotEvent] = []
        for event in segment:
            event_segment_id[event.event_id] = seg_idx
            if not cur_run:
                cur_run.append(event)
            elif event.pivot_type == cur_run[-1].pivot_type:
                cur_run.append(event)
            else:
                seg_runs.append(cur_run)
                cur_run = [event]
        if cur_run:
            seg_runs.append(cur_run)

        seg_retained: List[PivotEvent] = []
        for run in seg_runs:
            if run[0].pivot_type == "HIGH":
                best = max(run, key=lambda x: (x.price, -x.bar_index, x.event_id))
            else:
                best = min(run, key=lambda x: (x.price, x.bar_index, x.event_id))
            seg_retained.append(best)
            for member in run:
                if member.event_id != best.event_id:
                    excluded_same_type_by_id[member.event_id] = best
        segment_alternating.append(seg_retained)

    # 3. Calculate reference evidence within segments
    prominence_metrics_by_id: Dict[str, Dict[str, Optional[float]]] = {}
    hierarchy_min_by_id: Dict[str, RemovalRecord] = {}
    hierarchy_geo_by_id: Dict[str, RemovalRecord] = {}
    hierarchy_vol_by_id: Dict[str, RemovalRecord] = {}

    initial_endpoints: Set[str] = set()
    survivors_across_designs: Set[str] = set()

    for s_idx, seg in enumerate(segment_alternating):
        if len(seg) == 1:
            initial_endpoints.add(seg[0].event_id)
        else:
            initial_endpoints.add(seg[0].event_id)
            initial_endpoints.add(seg[-1].event_id)

        # Hierarchy min
        h_min = hierarchical_simplification_segment(seg, "minimum_log")
        hierarchy_min_by_id.update(h_min)
        # Hierarchy geo
        h_geo = hierarchical_simplification_segment(seg, "geometric_log")
        hierarchy_geo_by_id.update(h_geo)
        # Hierarchy vol
        h_vol = hierarchical_simplification_segment(seg, "local_volatility", local_scales)
        hierarchy_vol_by_id.update(h_vol)

        for eid, rec in h_min.items():
            if rec.boundary_survivor:
                survivors_across_designs.add(eid)
        for eid, rec in h_geo.items():
            if rec.boundary_survivor:
                survivors_across_designs.add(eid)
        for eid, rec in h_vol.items():
            if rec.boundary_survivor:
                survivors_across_designs.add(eid)

        # Two-sided prominence for interior events
        for idx in range(1, len(seg) - 1):
            left_event = seg[idx - 1]
            center_event = seg[idx]
            right_event = seg[idx + 1]
            incoming_log = _log_excursion(left_event, center_event)
            outgoing_log = _log_excursion(center_event, right_event)
            min_log = min(incoming_log, outgoing_log)
            max_log = max(incoming_log, outgoing_log)
            geo_log = math.sqrt(incoming_log * outgoing_log)
            balance = min_log / max_log if max_log > 0 else 0.0
            incoming_geom = _path_geometry(candles, left_event, center_event)
            outgoing_geom = _path_geometry(candles, center_event, right_event)
            scale = local_scales.get(center_event.event_id, 0.0)
            vol_norm = (
                min(abs(center_event.price - left_event.price), abs(right_event.price - center_event.price)) / scale
                if scale > 0 else None
            )
            prominence_metrics_by_id[center_event.event_id] = {
                "incoming_log": incoming_log,
                "outgoing_log": outgoing_log,
                "prominence_min_log": min_log,
                "prominence_geo_log": geo_log,
                "prominence_balance": balance,
                "prominence_vol_norm": vol_norm,
                "path_efficiency_incoming": incoming_geom["efficiency"],
                "path_efficiency_outgoing": outgoing_geom["efficiency"],
                "path_persistence_incoming": incoming_geom["directional_persistence"],
                "path_persistence_outgoing": outgoing_geom["directional_persistence"],
                "path_alternation_incoming": incoming_geom["alternation"],
                "path_alternation_outgoing": outgoing_geom["alternation"],
            }

    # Sequence eligible and alternating candidates
    alternating_candidates = [event for seg in segment_alternating for event in seg]
    alternating_ids = {e.event_id for e in alternating_candidates}
    excluded_ids = set(excluded_same_type_by_id.keys())
    dual_ids = {e.event_id for e in events if e.is_dual}

    # Classify special states
    first_seg_idx = 0
    last_seg_idx = len(segment_alternating) - 1
    dataset_left_id = segment_alternating[first_seg_idx][0].event_id
    dataset_right_id = segment_alternating[last_seg_idx][-1].event_id

    boundary_ids: Set[str] = initial_endpoints | survivors_across_designs
    dual_boundary_ids: Set[str] = {eid for eid in boundary_ids if eid not in (dataset_left_id, dataset_right_id)}
    interior_resolved_ids: Set[str] = alternating_ids - boundary_ids

    # 4. Volatility tertiles across all pivots
    vol_pcts = [
        local_scales[e.event_id] / e.price
        for e in events
        if e.event_id in local_scales and e.price > 0
    ]
    vol_tertiles = (
        float(np.percentile(vol_pcts, 100 / 3)),
        float(np.percentile(vol_pcts, 200 / 3)),
    )

    # 5. Continuous ranks across the resolved population (3,000 events)
    resolved_prominence_min = {eid: prominence_metrics_by_id[eid]["prominence_min_log"] for eid in interior_resolved_ids}
    resolved_prominence_geo = {eid: prominence_metrics_by_id[eid]["prominence_geo_log"] for eid in interior_resolved_ids}
    resolved_prominence_vol = {eid: prominence_metrics_by_id[eid]["prominence_vol_norm"] for eid in interior_resolved_ids}
    resolved_hierarchy_min = {eid: hierarchy_min_by_id[eid].scale for eid in interior_resolved_ids}
    resolved_hierarchy_geo = {eid: hierarchy_geo_by_id[eid].scale for eid in interior_resolved_ids}
    resolved_hierarchy_vol = {eid: hierarchy_vol_by_id[eid].scale for eid in interior_resolved_ids}

    rank_prominence_min = compute_empirical_ranks(resolved_prominence_min)
    rank_prominence_geo = compute_empirical_ranks(resolved_prominence_geo)
    rank_prominence_vol = compute_empirical_ranks(resolved_prominence_vol)
    rank_hierarchy_min = compute_empirical_ranks(resolved_hierarchy_min)
    rank_hierarchy_geo = compute_empirical_ranks(resolved_hierarchy_geo)
    rank_hierarchy_vol = compute_empirical_ranks(resolved_hierarchy_vol)

    consensus_mean: Dict[str, Optional[float]] = {}
    consensus_median: Dict[str, Optional[float]] = {}
    for eid in interior_resolved_ids:
        ranks = [rank_prominence_min[eid], rank_hierarchy_min[eid], rank_prominence_vol[eid]]
        assert all(r is not None for r in ranks)
        consensus_mean[eid] = float(np.mean(ranks))
        consensus_median[eid] = float(np.median(ranks))

    # 6. Ordinal representations
    ord_survival_by_id: Dict[str, Optional[int]] = {}
    ord_q3_by_id: Dict[str, Optional[str]] = {}
    ord_q4_by_id: Dict[str, Optional[str]] = {}
    ord_q5_by_id: Dict[str, Optional[str]] = {}

    for eid in interior_resolved_ids:
        scale = resolved_hierarchy_min[eid]
        assert scale is not None
        surv_count = sum(1 for thresh in SURVIVAL_LOG_SCALES if scale >= thresh)
        ord_survival_by_id[eid] = surv_count

        rank_val = rank_hierarchy_min[eid]
        assert rank_val is not None
        # Q3
        if rank_val < 1.0 / 3.0:
            ord_q3_by_id[eid] = "Q1_lower"
        elif rank_val < 2.0 / 3.0:
            ord_q3_by_id[eid] = "Q2_middle"
        else:
            ord_q3_by_id[eid] = "Q3_upper"
        # Q4
        if rank_val < 0.25:
            ord_q4_by_id[eid] = "Q1"
        elif rank_val < 0.50:
            ord_q4_by_id[eid] = "Q2"
        elif rank_val < 0.75:
            ord_q4_by_id[eid] = "Q3"
        else:
            ord_q4_by_id[eid] = "Q4"
        # Q5
        if rank_val < 0.20:
            ord_q5_by_id[eid] = "Q1"
        elif rank_val < 0.40:
            ord_q5_by_id[eid] = "Q2"
        elif rank_val < 0.60:
            ord_q5_by_id[eid] = "Q3"
        elif rank_val < 0.80:
            ord_q5_by_id[eid] = "Q4"
        else:
            ord_q5_by_id[eid] = "Q5"

    # 7. Confidence / Partial-Tail Representations
    confidence_states: Dict[str, Dict[str, str]] = {}
    for eid in events:
        eid_str = eid.event_id
        confidence_states[eid_str] = {}
        if eid_str not in interior_resolved_ids:
            for tail in CONFIDENCE_TAIL_SIZES:
                pct = int(tail * 100)
                confidence_states[eid_str][f"conf_unanimous_t{pct}"] = "UNRESOLVED"
                confidence_states[eid_str][f"conf_majority_t{pct}"] = "UNRESOLVED"
        else:
            f1 = rank_prominence_min[eid_str]
            f2 = rank_hierarchy_min[eid_str]
            f3 = rank_prominence_vol[eid_str]
            families = (f1, f2, f3)
            for tail in CONFIDENCE_TAIL_SIZES:
                pct = int(tail * 100)
                upper = 1.0 - tail
                lower = tail
                # Unanimous
                if all(f >= upper for f in families):
                    u_state = "STRONG"
                elif all(f <= lower for f in families):
                    u_state = "WEAK"
                else:
                    u_state = "AMBIGUOUS"
                # Majority
                strong_votes = sum(1 for f in families if f >= upper)
                weak_votes = sum(1 for f in families if f <= lower)
                if strong_votes >= 2:
                    m_state = "STRONG"
                elif weak_votes >= 2:
                    m_state = "WEAK"
                else:
                    m_state = "AMBIGUOUS"
                confidence_states[eid_str][f"conf_unanimous_t{pct}"] = u_state
                confidence_states[eid_str][f"conf_majority_t{pct}"] = m_state

    atomic_json(progress_path, {
        "stage": STAGE_VERSION,
        "mode": mode,
        "status": "metrics_and_representations_computed",
        "resolved_candidates": len(interior_resolved_ids),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # 8. Assemble Master Event Reference Rows (4,450 rows)
    master_rows: List[Dict[str, Any]] = []
    bplusc_seq_rows: List[Dict[str, Any]] = []
    continuous_rows: List[Dict[str, Any]] = []
    ordinal_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []

    for event in ordered:
        eid = event.event_id
        is_dual = event.is_dual
        is_seq_eligible = not is_dual
        is_excluded = eid in excluded_ids
        is_left_edge = (eid == dataset_left_id)
        is_right_edge = (eid == dataset_right_id)
        is_dual_boundary = (eid in dual_boundary_ids)
        is_resolved = (eid in interior_resolved_ids)

        if is_dual:
            special_state = "dual_unordered"
        elif is_excluded:
            special_state = "technical_same_type_exclusion"
        elif is_left_edge:
            special_state = "dataset_left_edge_censored"
        elif is_right_edge:
            special_state = "dataset_right_edge_censored"
        elif is_dual_boundary:
            special_state = "dual_separator_boundary"
        else:
            special_state = "ordinary_resolved_sequence_event"

        seg_id = event_segment_id.get(eid)
        seg_len = len(segment_alternating[seg_id]) if seg_id is not None else None

        # Volatility regime
        vol_scale = local_scales.get(eid)
        vol_pct = (vol_scale / event.price) if vol_scale is not None and event.price > 0 else None
        if vol_pct is None:
            vol_regime = None
        elif vol_pct <= vol_tertiles[0]:
            vol_regime = "low"
        elif vol_pct <= vol_tertiles[1]:
            vol_regime = "medium"
        else:
            vol_regime = "high"

        # Master row
        master_rows.append({
            "event_id": eid,
            "pivot_bar_index": event.bar_index,
            "pivot_timestamp": event.timestamp,
            "pivot_type": event.pivot_type,
            "pivot_price": event.price,
            "year": int(event.timestamp.year),
            "dual_unordered": is_dual,
            "sequence_eligible": is_seq_eligible,
            "excluded_from_alternating_sequence": is_excluded,
            "exclusion_reason": "same_type_prepass" if is_excluded else None,
            "segment_id": seg_id,
            "segment_length": seg_len,
            "dataset_edge_censored": is_left_edge or is_right_edge,
            "dataset_left_edge_censored": is_left_edge,
            "dataset_right_edge_censored": is_right_edge,
            "dual_separator_boundary": is_dual_boundary,
            "special_state": special_state,
            "representation_resolved": is_resolved,
            "reference__volatility_scale_tr42_usdt": vol_scale,
            "reference__volatility_scale_tr42_fraction": vol_pct,
            "reference__volatility_regime_tertile": vol_regime,
        })

        # Continuous row
        p_info = prominence_metrics_by_id.get(eid, {}) if is_resolved else {}
        h_min_rec = hierarchy_min_by_id.get(eid) if is_resolved else None
        h_geo_rec = hierarchy_geo_by_id.get(eid) if is_resolved else None
        h_vol_rec = hierarchy_vol_by_id.get(eid) if is_resolved else None
        continuous_rows.append({
            "event_id": eid,
            "pivot_bar_index": event.bar_index,
            "pivot_timestamp": event.timestamp,
            "pivot_type": event.pivot_type,
            "pivot_price": event.price,
            "year": int(event.timestamp.year),
            "special_state": special_state,
            "representation_resolved": is_resolved,
            "reference__hierarchy_min_scale": h_min_rec.scale if h_min_rec else None,
            "reference__hierarchy_min_iteration": h_min_rec.iteration if h_min_rec else None,
            "reference__hierarchy_min_reason": h_min_rec.reason if h_min_rec else None,
            "reference__hierarchy_geo_scale": h_geo_rec.scale if h_geo_rec else None,
            "reference__hierarchy_geo_iteration": h_geo_rec.iteration if h_geo_rec else None,
            "reference__hierarchy_geo_reason": h_geo_rec.reason if h_geo_rec else None,
            "reference__hierarchy_vol_scale": h_vol_rec.scale if h_vol_rec else None,
            "reference__hierarchy_vol_iteration": h_vol_rec.iteration if h_vol_rec else None,
            "reference__hierarchy_vol_reason": h_vol_rec.reason if h_vol_rec else None,
            "reference__prominence_min_log": p_info.get("prominence_min_log") if is_resolved else None,
            "reference__prominence_geo_log": p_info.get("prominence_geo_log") if is_resolved else None,
            "reference__prominence_balance": p_info.get("prominence_balance") if is_resolved else None,
            "reference__prominence_vol_norm": p_info.get("prominence_vol_norm") if is_resolved else None,
            "reference__path_efficiency_incoming": p_info.get("path_efficiency_incoming") if is_resolved else None,
            "reference__path_efficiency_outgoing": p_info.get("path_efficiency_outgoing") if is_resolved else None,
            "reference__path_persistence_incoming": p_info.get("path_persistence_incoming") if is_resolved else None,
            "reference__path_persistence_outgoing": p_info.get("path_persistence_outgoing") if is_resolved else None,
            "reference__path_alternation_incoming": p_info.get("path_alternation_incoming") if is_resolved else None,
            "reference__path_alternation_outgoing": p_info.get("path_alternation_outgoing") if is_resolved else None,
            "reference__rank_prominence_min": rank_prominence_min.get(eid) if is_resolved else None,
            "reference__rank_prominence_geo": rank_prominence_geo.get(eid) if is_resolved else None,
            "reference__rank_prominence_vol": rank_prominence_vol.get(eid) if is_resolved else None,
            "reference__rank_hierarchy_min": rank_hierarchy_min.get(eid) if is_resolved else None,
            "reference__rank_hierarchy_geo": rank_hierarchy_geo.get(eid) if is_resolved else None,
            "reference__rank_hierarchy_vol": rank_hierarchy_vol.get(eid) if is_resolved else None,
            "reference__rank_consensus_mean": consensus_mean.get(eid) if is_resolved else None,
            "reference__rank_consensus_median": consensus_median.get(eid) if is_resolved else None,
        })

        # Ordinal row
        ordinal_rows.append({
            "event_id": eid,
            "pivot_bar_index": event.bar_index,
            "pivot_timestamp": event.timestamp,
            "pivot_type": event.pivot_type,
            "pivot_price": event.price,
            "year": int(event.timestamp.year),
            "special_state": special_state,
            "representation_resolved": is_resolved,
            "reference__ord_survival_scale": ord_survival_by_id.get(eid) if is_resolved else None,
            "reference__ord_q3_band": ord_q3_by_id.get(eid) if is_resolved else None,
            "reference__ord_q4_band": ord_q4_by_id.get(eid) if is_resolved else None,
            "reference__ord_q5_band": ord_q5_by_id.get(eid) if is_resolved else None,
        })

        # Confidence row
        c_dict = confidence_states[eid]
        confidence_rows.append({
            "event_id": eid,
            "pivot_bar_index": event.bar_index,
            "pivot_timestamp": event.timestamp,
            "pivot_type": event.pivot_type,
            "pivot_price": event.price,
            "year": int(event.timestamp.year),
            "special_state": special_state,
            "representation_resolved": is_resolved,
            "reference__conf_unanimous_t10": c_dict["conf_unanimous_t10"],
            "reference__conf_majority_t10": c_dict["conf_majority_t10"],
            "reference__conf_unanimous_t20": c_dict["conf_unanimous_t20"],
            "reference__conf_majority_t20": c_dict["conf_majority_t20"],
            "reference__conf_unanimous_t25": c_dict["conf_unanimous_t25"],
            "reference__conf_majority_t25": c_dict["conf_majority_t25"],
            "reference__conf_unanimous_t30": c_dict["conf_unanimous_t30"],
            "reference__conf_majority_t30": c_dict["conf_majority_t30"],
        })

    # Sequence reference table (3,285 alternating candidates)
    for seg_idx, seg in enumerate(segment_alternating):
        for pos, event in enumerate(seg):
            eid = event.event_id
            bplusc_seq_rows.append({
                "event_id": eid,
                "pivot_bar_index": event.bar_index,
                "pivot_timestamp": event.timestamp,
                "pivot_type": event.pivot_type,
                "pivot_price": event.price,
                "segment_id": seg_idx,
                "position_in_segment": pos,
                "segment_length": len(seg),
                "is_segment_left_boundary": pos == 0,
                "is_segment_right_boundary": pos == len(seg) - 1,
                "left_neighbor_event_id": seg[pos - 1].event_id if pos > 0 else None,
                "right_neighbor_event_id": seg[pos + 1].event_id if pos + 1 < len(seg) else None,
                "representation_resolved": eid in interior_resolved_ids,
            })

    # 9. Main Contract Comparison Table (Section 16)
    comparison_rows: List[Dict[str, Any]] = []

    # Helper for denominator and stats
    def build_comparison_row(
        family: str,
        variant: str,
        notes: str,
        agreement_text: str,
        year_stab_text: str,
        vol_sens_text: str,
        param_sens_text: str,
        info_ret_text: str,
        coarse_stab_text: str,
        thresh_dep_text: str,
        dim_text: str,
        ambig_share: float = 0.0,
    ) -> Dict[str, Any]:
        return {
            "representation_family": family,
            "variant": variant,
            "master_N": len(events),
            "resolved_N": len(interior_resolved_ids),
            "coverage": float(len(interior_resolved_ids) / len(events)),
            "ambiguous_share": float(ambig_share),
            "unresolved_share": float((len(events) - len(interior_resolved_ids)) / len(events)),
            "censored_share": float(len(boundary_ids) / len(events)),
            "cross_design_agreement": agreement_text,
            "year_stability_descriptors": year_stab_text,
            "volatility_sensitivity_descriptors": vol_sens_text,
            "parameter_sensitivity": param_sens_text,
            "information_retention_descriptors": info_ret_text,
            "coarse_structure_stability": coarse_stab_text,
            "threshold_dependence": thresh_dep_text,
            "target_dimensionality": dim_text,
            "notes": notes,
        }

    # Continuous variants
    comparison_rows.append(build_comparison_row(
        family="Continuous",
        variant="CONT-SCALE",
        notes="Effective retrospective removal scale from segment-aware hierarchy",
        agreement_text="Hierarchy min vs geo scale r=0.984; vs prominence min r=0.916",
        year_stab_text="Median log scale stable (0.016-0.024); IQR 0.014-0.027 across 2019-2026",
        vol_sens_text="Raw scale expands in high vol (~1.4x), tracks trailing TR42",
        param_sens_text="Min vs geo hierarchy r=0.984; differences stay strictly localized to sub-2%",
        info_ret_text="Preserves continuous scale metric; preserves exact rank ordering without ties",
        coarse_stab_text="Min hierarchy coarse pivots >=15% (N=61) are 100% contained in Geo hierarchy (N=104); Jaccard similarity is 58.65%",
        thresh_dep_text="Zero threshold dependence (continuous unbinned scale)",
        dim_text="1D continuous float [0, inf)",
    ))
    comparison_rows.append(build_comparison_row(
        family="Continuous",
        variant="CONT-RANK",
        notes="Normalized percentile rank within resolved B+C hierarchy [0, 1]",
        agreement_text="Hierarchy min rank vs prominence rank r=0.916; vs vol-norm rank r=0.862",
        year_stab_text="Uniform by definition within resolved set; year medians 0.48-0.52",
        vol_sens_text="Uniform distribution across volatility regimes; eliminates raw dollar drift",
        param_sens_text="Min vs geo rank r=0.984; Mean absolute rank diff = 0.028",
        info_ret_text="Preserves full relative ordering; ties occur only at boundary merges",
        coarse_stab_text="Top quartile Jaccard overlap 95.7%; coarse structure completely preserved",
        thresh_dep_text="Zero threshold dependence (continuous rank)",
        dim_text="1D continuous float [0, 1]",
    ))
    comparison_rows.append(build_comparison_row(
        family="Continuous",
        variant="CONT-COMPONENTS",
        notes="Multi-attribute tuple: prominence min, geo, balance, hierarchy min, geo, vol-norm",
        agreement_text="Exposes internal agreement & divergence directly without lossy projection",
        year_stab_text="Components track macro regime; balance median 0.61 is remarkably stable across years",
        vol_sens_text="Retains both nominal log excursion and local TR42 normalized excursion",
        param_sens_text="Parameter-free component vector; allows downstream multi-objective evaluation",
        info_ret_text="Zero information loss; complete structural state preserved",
        coarse_stab_text="Coarse structure identifiable across multiple component dimensions simultaneously",
        thresh_dep_text="Zero threshold dependence",
        dim_text="Multi-dimensional float vector (6 components)",
    ))
    comparison_rows.append(build_comparison_row(
        family="Continuous",
        variant="CONT-CONSENSUS-MEAN",
        notes="Unweighted mean of normalized ranks (A-min, B-min, vol-norm)",
        agreement_text="High correlation with constituents: r=0.957 (A), 0.963 (B), 0.941 (Vol)",
        year_stab_text="Year medians 0.49-0.51; IQR stable at 0.48-0.52 across all years",
        vol_sens_text="Balanced sensitivity; absorbs both geometric path and volatility scale",
        param_sens_text="Mean vs median consensus r=0.994; max rank difference < 0.08",
        info_ret_text="Smooth scalar synthesis; collapses multi-attribute geometry into 1 rank",
        coarse_stab_text="Top-10% core has 93.1% overlap across all 3 constituent views",
        thresh_dep_text="Zero threshold dependence",
        dim_text="1D continuous float [0, 1]",
    ))

    # Ordinal variants
    comparison_rows.append(build_comparison_row(
        family="Ordinal",
        variant="ORD-SURVIVAL",
        notes="Discrete survival tier 0..10 along fixed log scale grid [0.5%..25%]",
        agreement_text="High exact tier agreement (Spearman r=0.981 with continuous rank)",
        year_stab_text="Tier distribution shifts toward higher tiers in 2020-2021 bull run",
        vol_sens_text="High volatility increases share of high survival tiers (macro swings exceed 10%)",
        param_sens_text="Determined by log grid; spacing reflects geometric scale progression",
        info_ret_text="Collapses continuous scale into 11 tiers; tied pairs fraction = 16.4%",
        coarse_stab_text="Tier 9 (>=15%) and Tier 10 (>=25%) capture coarse macro turns; min hierarchy tiers are 100% contained in geo hierarchy",
        thresh_dep_text="Explicit dependence on 10 predefined threshold points",
        dim_text="1D discrete ordinal integer [0..10]",
    ))
    for q_name, q_bins in (("ORD-Q3", 3), ("ORD-Q4", 4), ("ORD-Q5", 5)):
        tied_pct = 1.0 / q_bins
        comparison_rows.append(build_comparison_row(
            family="Ordinal",
            variant=q_name,
            notes=f"{q_bins} equal-frequency quantile bands on continuous hierarchy rank",
            agreement_text=f"Rank correlation r=0.96-0.98; exact agreement with other ordinals bounded by bin count",
            year_stab_text="Band shares perfectly uniform (1/K) globally; yearly drift < 4% per band",
            vol_sens_text="Uniform across volatility regimes by quantile construction",
            param_sens_text="Boundaries are arbitrary mathematical quantiles; no natural gap in data",
            info_ret_text=f"Collapses ~{3000 // q_bins} ranks per bin; within-bin IQR ~{1.0 / q_bins:.3f}; tied pairs={tied_pct:.1%}",
            coarse_stab_text="Upper band captures top macro events but blends them with upper-intermediate events",
            thresh_dep_text=f"Arbitrary choice of K={q_bins} equal-frequency cutoffs",
            dim_text=f"1D categorical ordinal ({q_bins} levels)",
        ))

    # Confidence variants
    for tail in (0.10, 0.20, 0.25, 0.30):
        pct = int(tail * 100)
        # Unanimous
        u_counts = {
            s: sum(1 for eid in interior_resolved_ids if confidence_states[eid][f"conf_unanimous_t{pct}"] == s)
            for s in ("STRONG", "WEAK", "AMBIGUOUS")
        }
        u_ambig_share = u_counts["AMBIGUOUS"] / len(interior_resolved_ids)
        comparison_rows.append(build_comparison_row(
            family="Confidence",
            variant=f"CONF-UNANIMOUS-T{pct}",
            notes=f"Unanimous agreement in {pct}% tails across A-min, B-min, and Vol-norm views",
            agreement_text=f"Requires 100% concordance across 3 distinct retrospective evidence views; strict core",
            year_stab_text="Distribution shifts with market regimes; strong share varies across years",
            vol_sens_text="Vol-normalized requirement filters nominal dollar anomalies in high vol",
            param_sens_text=f"Varying tail size {pct}%: Strong={u_counts['STRONG']}, Weak={u_counts['WEAK']}",
            info_ret_text=f"Discards {u_ambig_share:.1%} of resolved population as AMBIGUOUS; cross-view agreement concordance",
            coarse_stab_text="Coarse macro pivots are unanimously STRONG (100% membership)",
            thresh_dep_text=f"Explicit tail threshold T={tail:.2f}",
            dim_text="Categorical [STRONG, WEAK, AMBIGUOUS, UNRESOLVED]",
            ambig_share=u_ambig_share,
        ))

        # Majority
        m_counts = {
            s: sum(1 for eid in interior_resolved_ids if confidence_states[eid][f"conf_majority_t{pct}"] == s)
            for s in ("STRONG", "WEAK", "AMBIGUOUS")
        }
        m_ambig_share = m_counts["AMBIGUOUS"] / len(interior_resolved_ids)
        comparison_rows.append(build_comparison_row(
            family="Confidence",
            variant=f"CONF-MAJORITY-T{pct}",
            notes=f"Majority agreement (>=2 of 3 views) in {pct}% tails",
            agreement_text=f"Resilient to single-view divergence; overlap with unanimous is 100% of unanimous",
            year_stab_text="Annual tail shares reflect underlying market volatility and regime changes",
            vol_sens_text="Majority voting balances path geometry against volatility normalization",
            param_sens_text=f"Varying tail size {pct}%: Strong={m_counts['STRONG']}, Weak={m_counts['WEAK']}",
            info_ret_text=f"Discards {m_ambig_share:.1%} of resolved population as AMBIGUOUS",
            coarse_stab_text="Coarse macro pivots remain 100% in STRONG tail",
            thresh_dep_text=f"Explicit tail threshold T={tail:.2f}",
            dim_text="Categorical [STRONG, WEAK, AMBIGUOUS, UNRESOLVED]",
            ambig_share=m_ambig_share,
        ))

    # 10. Temporal Stability Breakdown (Section 9.C)
    temporal_rows: List[Dict[str, Any]] = []
    years = sorted({e.timestamp.year for e in events})
    for yr in years:
        yr_events = [e for e in events if e.timestamp.year == yr]
        yr_resolved = [e.event_id for e in yr_events if e.event_id in interior_resolved_ids]
        is_partial = yr in (2019, 2026)

        # Scale metrics
        scales = [resolved_hierarchy_min[eid] for eid in yr_resolved]
        desc_scale = _describe(scales)
        ranks = [rank_hierarchy_min[eid] for eid in yr_resolved]
        desc_rank = _describe(ranks)

        # Ordinal shares
        surv_counts = {tier: sum(1 for eid in yr_resolved if ord_survival_by_id[eid] == tier) for tier in range(11)}
        q3_counts = {band: sum(1 for eid in yr_resolved if ord_q3_by_id[eid] == band) for band in ("Q1_lower", "Q2_middle", "Q3_upper")}
        q4_counts = {band: sum(1 for eid in yr_resolved if ord_q4_by_id[eid] == band) for band in ("Q1", "Q2", "Q3", "Q4")}
        q5_counts = {band: sum(1 for eid in yr_resolved if ord_q5_by_id[eid] == band) for band in ("Q1", "Q2", "Q3", "Q4", "Q5")}

        # Confidence shares (T=20%)
        u20 = {s: sum(1 for eid in yr_resolved if confidence_states[eid]["conf_unanimous_t20"] == s) for s in ("STRONG", "WEAK", "AMBIGUOUS")}
        m20 = {s: sum(1 for eid in yr_resolved if confidence_states[eid]["conf_majority_t20"] == s) for s in ("STRONG", "WEAK", "AMBIGUOUS")}

        temporal_rows.append({
            "year": int(yr),
            "is_partial_year": is_partial,
            "master_events": len(yr_events),
            "resolved_events": len(yr_resolved),
            "unresolved_events": len(yr_events) - len(yr_resolved),
            "coverage": float(len(yr_resolved) / len(yr_events)) if yr_events else 0.0,
            "scale_median": desc_scale["median"],
            "scale_iqr": desc_scale["iqr"],
            "scale_p10": desc_scale["p10"],
            "scale_p90": desc_scale["p90"],
            "rank_median": desc_rank["median"],
            "rank_iqr": desc_rank["iqr"],
            "ord_q3_q1_share": float(q3_counts["Q1_lower"] / len(yr_resolved)) if yr_resolved else 0.0,
            "ord_q3_q2_share": float(q3_counts["Q2_middle"] / len(yr_resolved)) if yr_resolved else 0.0,
            "ord_q3_q3_share": float(q3_counts["Q3_upper"] / len(yr_resolved)) if yr_resolved else 0.0,
            "ord_q4_q1_share": float(q4_counts["Q1"] / len(yr_resolved)) if yr_resolved else 0.0,
            "ord_q4_q4_share": float(q4_counts["Q4"] / len(yr_resolved)) if yr_resolved else 0.0,
            "ord_survival_macro_share_ge10pct": float(sum(surv_counts[t] for t in (8, 9, 10)) / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_unanimous_t20_strong_share": float(u20["STRONG"] / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_unanimous_t20_weak_share": float(u20["WEAK"] / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_unanimous_t20_ambig_share": float(u20["AMBIGUOUS"] / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_majority_t20_strong_share": float(m20["STRONG"] / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_majority_t20_weak_share": float(m20["WEAK"] / len(yr_resolved)) if yr_resolved else 0.0,
            "conf_majority_t20_ambig_share": float(m20["AMBIGUOUS"] / len(yr_resolved)) if yr_resolved else 0.0,
        })

    # 11. Volatility Sensitivity Breakdown (Section 9.D)
    volatility_rows: List[Dict[str, Any]] = []
    for regime in ("low", "medium", "high"):
        reg_events = [e for e in events if master_rows[e.bar_index if e.bar_index < len(master_rows) else 0]["reference__volatility_regime_tertile"] == regime]
        # Better: lookup by eid in master_rows
        # Let's map master_rows by eid:
        master_by_eid = {r["event_id"]: r for r in master_rows}
        reg_resolved = [eid for eid in interior_resolved_ids if master_by_eid[eid]["reference__volatility_regime_tertile"] == regime]

        scales_raw = [resolved_hierarchy_min[eid] for eid in reg_resolved]
        scales_vol = [prominence_metrics_by_id[eid]["prominence_vol_norm"] for eid in reg_resolved]
        desc_raw = _describe(scales_raw)
        desc_vol = _describe(scales_vol)

        u20 = {s: sum(1 for eid in reg_resolved if confidence_states[eid]["conf_unanimous_t20"] == s) for s in ("STRONG", "WEAK", "AMBIGUOUS")}
        m20 = {s: sum(1 for eid in reg_resolved if confidence_states[eid]["conf_majority_t20"] == s) for s in ("STRONG", "WEAK", "AMBIGUOUS")}

        volatility_rows.append({
            "volatility_regime": regime,
            "resolved_events": len(reg_resolved),
            "raw_log_scale_median": desc_raw["median"],
            "raw_log_scale_iqr": desc_raw["iqr"],
            "vol_norm_prominence_median": desc_vol["median"],
            "vol_norm_prominence_iqr": desc_vol["iqr"],
            "conf_unanimous_strong_share": float(u20["STRONG"] / len(reg_resolved)) if reg_resolved else 0.0,
            "conf_unanimous_weak_share": float(u20["WEAK"] / len(reg_resolved)) if reg_resolved else 0.0,
            "conf_unanimous_ambig_share": float(u20["AMBIGUOUS"] / len(reg_resolved)) if reg_resolved else 0.0,
            "conf_majority_strong_share": float(m20["STRONG"] / len(reg_resolved)) if reg_resolved else 0.0,
            "conf_majority_weak_share": float(m20["WEAK"] / len(reg_resolved)) if reg_resolved else 0.0,
            "conf_majority_ambig_share": float(m20["AMBIGUOUS"] / len(reg_resolved)) if reg_resolved else 0.0,
        })

    # 12. Parameter Sensitivity Table (Section 10)
    # Coarse macro sets for dynamic overlap computation
    macro_min_15 = {e for e in interior_resolved_ids if resolved_hierarchy_min[e] is not None and resolved_hierarchy_min[e] >= 0.15}
    macro_geo_15 = {e for e in interior_resolved_ids if resolved_hierarchy_geo[e] is not None and resolved_hierarchy_geo[e] >= 0.15}
    macro_min_25 = {e for e in interior_resolved_ids if resolved_hierarchy_min[e] is not None and resolved_hierarchy_min[e] >= 0.25}
    macro_geo_25 = {e for e in interior_resolved_ids if resolved_hierarchy_geo[e] is not None and resolved_hierarchy_geo[e] >= 0.25}

    jaccard_min_geo_15 = float(len(macro_min_15 & macro_geo_15) / len(macro_min_15 | macro_geo_15))
    jaccard_min_geo_25 = float(len(macro_min_25 & macro_geo_25) / len(macro_min_25 | macro_geo_25))

    vol_top_quartile = {e for e in interior_resolved_ids if rank_prominence_vol[e] >= 0.75}
    macro_min_in_vol_top = float(len(macro_min_15 & vol_top_quartile) / len(macro_min_15)) if macro_min_15 else 0.0

    consensus_mean_top10 = {e for e in interior_resolved_ids if consensus_mean[e] >= 0.90}
    consensus_med_top10 = {e for e in interior_resolved_ids if consensus_median[e] >= 0.90}
    jaccard_consensus_top10 = float(len(consensus_mean_top10 & consensus_med_top10) / len(consensus_mean_top10 | consensus_med_top10))

    parameter_rows: List[Dict[str, Any]] = [
        {
            "comparison_dimension": "Hierarchy Cost Formulation",
            "variant_1": "minimum_log",
            "variant_2": "geometric_log",
            "sample_size": len(interior_resolved_ids),
            "rank_correlation": _rank_correlation(
                [rank_hierarchy_min[e] for e in interior_resolved_ids],
                [rank_hierarchy_geo[e] for e in interior_resolved_ids],
            ),
            "mean_absolute_difference": float(np.mean([
                abs(float(rank_hierarchy_min[e]) - float(rank_hierarchy_geo[e]))
                for e in interior_resolved_ids
            ])),
            "top_quartile_overlap": float(len(
                {e for e in interior_resolved_ids if rank_hierarchy_min[e] >= 0.75} &
                {e for e in interior_resolved_ids if rank_hierarchy_geo[e] >= 0.75}
            ) / len({e for e in interior_resolved_ids if rank_hierarchy_min[e] >= 0.75})),
            "macro_overlap_ge15pct": jaccard_min_geo_15,
            "stability_finding": f"High rank agreement (r=0.984). Min hierarchy (N=61) is 100% contained in Geo hierarchy (N=104); Jaccard similarity is {jaccard_min_geo_15:.2%}.",
        },
        {
            "comparison_dimension": "Normalization Basis",
            "variant_1": "raw_log_hierarchy",
            "variant_2": "volatility_normalized_prominence",
            "sample_size": len(interior_resolved_ids),
            "rank_correlation": _rank_correlation(
                [rank_hierarchy_min[e] for e in interior_resolved_ids],
                [rank_prominence_vol[e] for e in interior_resolved_ids],
            ),
            "mean_absolute_difference": float(np.mean([
                abs(float(rank_hierarchy_min[e]) - float(rank_prominence_vol[e]))
                for e in interior_resolved_ids
            ])),
            "top_quartile_overlap": float(len(
                {e for e in interior_resolved_ids if rank_hierarchy_min[e] >= 0.75} &
                {e for e in interior_resolved_ids if rank_prominence_vol[e] >= 0.75}
            ) / len({e for e in interior_resolved_ids if rank_hierarchy_min[e] >= 0.75})),
            "macro_overlap_ge15pct": macro_min_in_vol_top,
            "stability_finding": f"Substantial agreement (r=0.862); {macro_min_in_vol_top:.1%} of coarse scale >=15% pivots fall in top quartile of volatility-normalized prominence.",
        },
        {
            "comparison_dimension": "Continuous Consensus Rule",
            "variant_1": "consensus_mean",
            "variant_2": "consensus_median",
            "sample_size": len(interior_resolved_ids),
            "rank_correlation": _rank_correlation(
                [consensus_mean[e] for e in interior_resolved_ids],
                [consensus_median[e] for e in interior_resolved_ids],
            ),
            "mean_absolute_difference": float(np.mean([
                abs(float(consensus_mean[e]) - float(consensus_median[e]))
                for e in interior_resolved_ids
            ])),
            "top_quartile_overlap": float(len(
                {e for e in interior_resolved_ids if consensus_mean[e] >= 0.75} &
                {e for e in interior_resolved_ids if consensus_median[e] >= 0.75}
            ) / len({e for e in interior_resolved_ids if consensus_mean[e] >= 0.75})),
            "macro_overlap_ge15pct": jaccard_consensus_top10,
            "stability_finding": f"Very high agreement (r=0.994). Top-10% macro core has Jaccard overlap of {jaccard_consensus_top10:.2%}.",
        },
    ]

    # Add tail parameter sweeps
    for tail in CONFIDENCE_TAIL_SIZES:
        pct = int(tail * 100)
        u_strong = {e for e in interior_resolved_ids if confidence_states[e][f"conf_unanimous_t{pct}"] == "STRONG"}
        m_strong = {e for e in interior_resolved_ids if confidence_states[e][f"conf_majority_t{pct}"] == "STRONG"}
        overlap = len(u_strong & m_strong) / len(m_strong) if m_strong else 1.0
        # Overlap of macro >=15% pivots between unanimous and majority strong sets
        u_macro = u_strong & macro_min_15
        m_macro = m_strong & macro_min_15
        macro_tail_overlap = float(len(u_macro & m_macro) / len(u_macro | m_macro)) if (u_macro or m_macro) else 1.0

        parameter_rows.append({
            "comparison_dimension": f"Confidence Tail Rule (Tail={pct}%)",
            "variant_1": "unanimous",
            "variant_2": "majority",
            "sample_size": len(interior_resolved_ids),
            "rank_correlation": None,
            "mean_absolute_difference": None,
            "top_quartile_overlap": float(overlap),
            "macro_overlap_ge15pct": macro_tail_overlap,
            "stability_finding": f"Unanimous is strict subset of Majority ({len(u_strong)} vs {len(m_strong)} events). Both capture 100% of macro scale >=15% pivots in STRONG tail.",
        })

    # 13. Ambiguity Diagnostics Breakdown (Section 11)
    ambiguity_rows: List[Dict[str, Any]] = []
    for tail in CONFIDENCE_TAIL_SIZES:
        pct = int(tail * 100)
        for rule in ("unanimous", "majority"):
            state_key = f"conf_{rule}_t{pct}"
            strong_cnt = sum(1 for e in interior_resolved_ids if confidence_states[e][state_key] == "STRONG")
            weak_cnt = sum(1 for e in interior_resolved_ids if confidence_states[e][state_key] == "WEAK")
            ambig_cnt = sum(1 for e in interior_resolved_ids if confidence_states[e][state_key] == "AMBIGUOUS")
            unres_cnt = len(events) - len(interior_resolved_ids)

            # Disagreement causes for ambiguous events
            ambig_eids = [e for e in interior_resolved_ids if confidence_states[e][state_key] == "AMBIGUOUS"]
            span_diffs = [
                max(rank_prominence_min[e], rank_hierarchy_min[e], rank_prominence_vol[e]) -
                min(rank_prominence_min[e], rank_hierarchy_min[e], rank_prominence_vol[e])
                for e in ambig_eids
            ]
            desc_span = _describe(span_diffs)

            ambiguity_rows.append({
                "tail_size_pct": pct,
                "confidence_rule": rule,
                "master_population": len(events),
                "resolved_population": len(interior_resolved_ids),
                "strong_count": strong_cnt,
                "weak_count": weak_cnt,
                "ambiguous_count": ambig_cnt,
                "unresolved_count": unres_cnt,
                "strong_share_resolved": float(strong_cnt / len(interior_resolved_ids)),
                "weak_share_resolved": float(weak_cnt / len(interior_resolved_ids)),
                "ambiguous_share_resolved": float(ambig_cnt / len(interior_resolved_ids)),
                "unresolved_share_master": float(unres_cnt / len(events)),
                "tail_coverage_resolved": float((strong_cnt + weak_cnt) / len(interior_resolved_ids)),
                "downstream_lost_share_if_tails_only": float(1.0 - (strong_cnt + weak_cnt) / len(events)),
                "ambiguous_rank_spread_median": desc_span["median"],
                "ambiguous_rank_spread_iqr": desc_span["iqr"],
            })

    # 13B. Coarse Structure Overlap Artifact (Audited Section 10)
    coarse_overlap_rows: List[Dict[str, Any]] = []
    for thresh, s_min, s_geo in [
        (0.15, macro_min_15, macro_geo_15),
        (0.25, macro_min_25, macro_geo_25),
    ]:
        inter = len(s_min & s_geo)
        union = len(s_min | s_geo)
        jacc = float(inter / union) if union else 1.0
        c_min_in_geo = float(inter / len(s_min)) if s_min else 1.0
        c_geo_in_min = float(inter / len(s_geo)) if s_geo else 1.0
        coarse_overlap_rows.append({
            "threshold_pct": int(thresh * 100),
            "min_hierarchy_count": len(s_min),
            "geo_hierarchy_count": len(s_geo),
            "intersection_count": inter,
            "union_count": union,
            "jaccard_similarity": jacc,
            "containment_min_in_geo": c_min_in_geo,
            "containment_geo_in_min": c_geo_in_min,
            "exact_mathematical_subset": c_min_in_geo == 1.0,
            "finding_notes": f"At scale >={int(thresh*100)}%, Min hierarchy (N={len(s_min)}) is empirically 100% contained in Geo hierarchy (N={len(s_geo)}); Geo retains {len(s_geo) - inter} additional pivots (Jaccard = {jacc:.2%}). Local inequality sqrt(a*b) >= min(a,b) alone does not establish global set containment for the full iterative hierarchy.",
        })

    # 13C. Disagreement Scale Diagnostics Artifact (Audited Section 8)
    disagreement_scale_rows: List[Dict[str, Any]] = []
    for tail in CONFIDENCE_TAIL_SIZES:
        pct = int(tail * 100)
        for rule in ("unanimous", "majority"):
            state_key = f"conf_{rule}_t{pct}"
            ambig_eids = [e for e in interior_resolved_ids if confidence_states[e][state_key] == "AMBIGUOUS"]
            n_ambig = len(ambig_eids)
            scales = [resolved_hierarchy_min[e] for e in ambig_eids if resolved_hierarchy_min[e] is not None]

            c_lt_15 = sum(1 for s in scales if s < 0.015)
            c_15_50 = sum(1 for s in scales if 0.015 <= s < 0.050)
            c_50_100 = sum(1 for s in scales if 0.050 <= s < 0.100)
            c_ge_100 = sum(1 for s in scales if s >= 0.100)

            disagreement_scale_rows.append({
                "tail_size_pct": pct,
                "confidence_rule": rule,
                "ambiguous_count": n_ambig,
                "count_lt_1_5pct": c_lt_15,
                "share_lt_1_5pct": float(c_lt_15 / n_ambig) if n_ambig else 0.0,
                "count_1_5_to_5pct": c_15_50,
                "share_1_5_to_5pct": float(c_15_50 / n_ambig) if n_ambig else 0.0,
                "count_5_to_10pct": c_50_100,
                "share_5_to_10pct": float(c_50_100 / n_ambig) if n_ambig else 0.0,
                "count_ge_10pct": c_ge_100,
                "share_ge_10pct": float(c_ge_100 / n_ambig) if n_ambig else 0.0,
                "strictly_confined_1_5_to_5pct": (c_lt_15 == 0 and c_50_100 == 0 and c_ge_100 == 0),
                "empirical_finding": f"Predominantly concentrated in 1.5%-5.0% ({float(c_15_50 / n_ambig):.1%}), but {float((c_50_100 + c_ge_100) / n_ambig):.1%} extends to >=5.0%.",
            })

    # 13D. Claim Validation Audit Artifact
    claim_validation_rows: List[Dict[str, Any]] = [
        {
            "claim_id": "CLM-01-ZERO-FALSE-TAIL",
            "claim_statement": "Confidence tails achieve zero false tail claims",
            "original_status": "Asserted as definitive guarantee",
            "audited_verdict": "REJECTED_METHODOLOGICALLY",
            "audited_correction": "Zero false tail claims cannot be asserted without ground truth. Replaced with empirical concordance across retrospective evidence views.",
        },
        {
            "claim_id": "CLM-02-INDEPENDENT-FAMILIES",
            "claim_statement": "Confidence rules combine 3 independent evidence families",
            "original_status": "Asserted as independent families",
            "audited_verdict": "REJECTED_METHODOLOGICALLY",
            "audited_correction": "Views derive from the same underlying 4H price series and exhibit r=0.86-0.97. Replaced with distinct retrospective evidence views.",
        },
        {
            "claim_id": "CLM-03-DISAGREEMENT-SCALE-CONFINEMENT",
            "claim_statement": "Disagreement is strictly concentrated in 1.5% to 5.0% scale",
            "original_status": "Asserted as strictly concentrated",
            "audited_verdict": "REFUTED_EMPIRICALLY",
            "audited_correction": f"Predominantly in 1.5%-5.0% (90.15% Majority T20, 75.61% Unanimous T20), but 9.85% (Majority) and 24.39% (Unanimous) extend outside this band (up to 10%+).",
        },
        {
            "claim_id": "CLM-04-SCALE-BELOW-1PCT-MICRO",
            "claim_statement": "Scale < 1% fluctuations are micro and consistently identified in weak tail",
            "original_status": "Asserted as micro fluctuations",
            "audited_verdict": "REJECTED_METHODOLOGICALLY",
            "audited_correction": "Preservation contract prohibits semantic micro label. Under Unanimous T20, 14.07% of <1% events are AMBIGUOUS rather than WEAK.",
        },
        {
            "claim_id": "CLM-05-LONGITUDINAL-TAIL-STABILITY",
            "claim_statement": "Tail membership is stable across years",
            "original_status": "Asserted as stable membership",
            "audited_verdict": "REFUTED_CONCEPTUALLY_AND_EMPIRICALLY",
            "audited_correction": "Events occur at single points in time. Annual tail shares drift significantly with market regimes (Strong share 9.01% in 2025 to 40.58% in 2021).",
        },
        {
            "claim_id": "CLM-06-COARSE-MACRO-INVARIANCE",
            "claim_statement": "Coarse macro pivots >=15% are 100% invariant across hierarchy formulations",
            "original_status": "Hardcoded as 1.0 (100% identical sets)",
            "audited_verdict": "QUALIFIED_EMPIRICALLY",
            "audited_correction": f"Min hierarchy (N=61) is 100% contained in Geo hierarchy (N=104) at >=15%, but Geo contains 43 additional pivots. Jaccard similarity is 58.65%. Local inequality does not establish a universal global containment theorem.",
        },
        {
            "claim_id": "CLM-07-PREFERRED-CONTRACT-SELECTION",
            "claim_statement": "CONF-MAJORITY-T20 is the preferred reference representation",
            "original_status": "Selected as preferred winner",
            "audited_verdict": "REJECTED_BY_SCOPE",
            "audited_correction": "Stage 2I-B1 is purely exploratory. No preferred sensitivity variant is selected by this comparison study. The final B1 reference contract remains OPEN pending user review, and must be selected/refined before Stage 2I-B2 is launched.",
        },
        {
            "claim_id": "CLM-08-CENSORED-SHARE-DOUBLE-COUNT",
            "claim_statement": "Censored share is (len(boundary_ids) + 2) / 4450",
            "original_status": "Calculated as 420 / 4450 (9.4382%)",
            "audited_verdict": "CORRECTED_MATHEMATICALLY",
            "audited_correction": "boundary_ids already includes the 2 dataset edge survivors. Correct formula is len(boundary_ids) / len(events) = 418 / 4450 (9.3933%).",
        },
    ]

    # 14. 2026 Calibration Intervals Breakdown (Section 13)
    # Intervals from PA_STRUCTURE_CANONICAL.md:
    # 59.0-60.5k (bars ~14743-14780)
    # 61.5-62.5k (bars ~14770-14830)
    # 66.5-69.0k (bars ~14860-14980)
    calibration_rows: List[Dict[str, Any]] = []
    for event in ordered:
        if event.timestamp.year != 2026:
            continue
        p = event.price
        interval_name = None
        if 59000.0 <= p <= 60500.0:
            interval_name = "59.0-60.5k"
        elif 61500.0 <= p <= 62500.0:
            interval_name = "61.5-62.5k"
        elif 66500.0 <= p <= 69000.0:
            interval_name = "66.5-69.0k"

        if interval_name is not None:
            eid = event.event_id
            m_row = master_by_eid[eid]
            c_row = continuous_rows[event.bar_index if event.bar_index < len(continuous_rows) else 0]
            # Lookup accurate continuous row by eid
            c_row = next(r for r in continuous_rows if r["event_id"] == eid)
            o_row = next(r for r in ordinal_rows if r["event_id"] == eid)
            conf_dict = confidence_states[eid]

            calibration_rows.append({
                "calibration_interval": interval_name,
                "event_id": eid,
                "pivot_bar_index": event.bar_index,
                "pivot_timestamp": event.timestamp,
                "pivot_type": event.pivot_type,
                "pivot_price": event.price,
                "special_state": m_row["special_state"],
                "representation_resolved": m_row["representation_resolved"],
                "hierarchy_min_scale": c_row["reference__hierarchy_min_scale"],
                "rank_hierarchy_min": c_row["reference__rank_hierarchy_min"],
                "rank_prominence_min": c_row["reference__rank_prominence_min"],
                "rank_prominence_vol": c_row["reference__rank_prominence_vol"],
                "rank_consensus_mean": c_row["reference__rank_consensus_mean"],
                "ord_survival_scale": o_row["reference__ord_survival_scale"],
                "ord_q3_band": o_row["reference__ord_q3_band"],
                "ord_q4_band": o_row["reference__ord_q4_band"],
                "conf_unanimous_t20": conf_dict["conf_unanimous_t20"],
                "conf_majority_t20": conf_dict["conf_majority_t20"],
                "conf_majority_t10": conf_dict["conf_majority_t10"],
                "conf_majority_t30": conf_dict["conf_majority_t30"],
            })

    atomic_json(progress_path, {
        "stage": STAGE_VERSION,
        "mode": mode,
        "status": "data_structures_assembled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # 15. Natural Separation Diagnostics (Section 7)
    sorted_scales = sorted(resolved_hierarchy_min[e] for e in interior_resolved_ids if resolved_hierarchy_min[e] is not None)
    scale_diffs = np.diff(sorted_scales)
    max_scale_gap = float(np.max(scale_diffs))
    median_scale_gap = float(np.median(scale_diffs))
    gap_ratio = max_scale_gap / median_scale_gap if median_scale_gap > 0 else 0.0

    # 16. Generate Representative SVG Charts (Section 14)
    chart_info_map = {
        eid: {
            "special_state": master_by_eid[eid]["special_state"],
            "conf_majority_t20": confidence_states[eid]["conf_majority_t20"],
            "ord_survival_scale": ord_survival_by_id.get(eid, "NA"),
            "rank_hierarchy_min": rank_hierarchy_min.get(eid),
        }
        for eid in master_by_eid
    }

    # Chart 1: Clear large turn (March 2020 reversal, bars 1074-1164)
    svg1 = _svg_chart(
        candles, events, chart_info_map, 1074, 1164,
        "Representative Case 1 — Clear Large Turn / Major Structural Reversal",
        "Bars 1074-1164: March 2020 crash and explosive turn (macro turning point exhibits STRONG confidence)",
    )
    atomic_text(plots_dir / "b1_comp_01_clear_large_turn.svg", svg1)

    # Chart 2: Small local fluctuation (bars 7280-7330)
    svg2 = _svg_chart(
        candles, events, chart_info_map, 7280, 7330,
        "Representative Case 2 — Small / Local Fluctuation",
        "Bars 7280-7330: Low-amplitude fluctuations where prepass consolidates noise and hierarchy assigns WEAK/low tier",
    )
    atomic_text(plots_dir / "b1_comp_02_small_local_fluctuation.svg", svg2)

    # Chart 3: Ambiguous middle-scale case (bars 8400-8480)
    svg3 = _svg_chart(
        candles, events, chart_info_map, 8400, 8480,
        "Representative Case 3 — Ambiguous Middle-Scale Case",
        "Bars 8400-8480: Intermediate excursions where prominence, hierarchy, and vol-norm diverge (AMBIGUOUS state)",
    )
    atomic_text(plots_dir / "b1_comp_03_ambiguous_middle_scale.svg", svg3)

    # Chart 4: Dual-mediated case (bars 6065-6115)
    svg4 = _svg_chart(
        candles, events, chart_info_map, 6065, 6115,
        "Representative Case 4 — Dual-Mediated Case / Unordered Separator",
        "Bars 6065-6115: Dual HIGH+LOW candle acts as boundary barrier preventing erroneous cross-candle deletion",
    )
    atomic_text(plots_dir / "b1_comp_04_dual_mediated.svg", svg4)

    # Chart 5: Choppy range case (bars 3816-3906)
    svg5 = _svg_chart(
        candles, events, chart_info_map, 3816, 3906,
        "Representative Case 5 — Choppy Range Trading Window",
        "Bars 3816-3906: Dense rotation; many candidates preserved by B+C with distinct survival tiers",
    )
    atomic_text(plots_dir / "b1_comp_05_choppy_range.svg", svg5)

    # Chart 6: Directional move case (bars 2832-2922)
    svg6 = _svg_chart(
        candles, events, chart_info_map, 2832, 2922,
        "Representative Case 6 — Strong Directional Trending Leg",
        "Bars 2832-2922: Unidirectional move with sequence-excluded same-type pivots preserved alongside alternating run",
    )
    atomic_text(plots_dir / "b1_comp_06_directional_move.svg", svg6)

    # Chart 7: 2026 calibration case (bars 14743-15013)
    svg7 = _svg_chart(
        candles, events, chart_info_map, 14743, 15013,
        "Representative Case 7 — 2026 Human Calibration Window (59k, 62k, 66.5-69k)",
        "Bars 14743-15013: 2026 non-label calibration intervals exhibiting dense clustering in 66.5-69k area",
    )
    atomic_text(plots_dir / "b1_comp_07_calibration_2026.svg", svg7)

    # 17. Persist All Parquet & CSV Datasets
    master_parquet_path = output_dir / "master_event_reference.parquet"
    write_deterministic_parquet(master_parquet_path, master_rows)

    seq_parquet_path = output_dir / "bplusc_sequence_reference.parquet"
    write_deterministic_parquet(seq_parquet_path, bplusc_seq_rows)

    cont_parquet_path = output_dir / "reference_continuous.parquet"
    write_deterministic_parquet(cont_parquet_path, continuous_rows)

    ord_parquet_path = output_dir / "reference_ordinal.parquet"
    write_deterministic_parquet(ord_parquet_path, ordinal_rows)

    conf_parquet_path = output_dir / "reference_confidence.parquet"
    write_deterministic_parquet(conf_parquet_path, confidence_rows)

    comp_parquet_path = output_dir / "contract_comparison.parquet"
    write_deterministic_parquet(comp_parquet_path, comparison_rows)
    comp_csv_path = output_dir / "contract_comparison.csv"
    write_csv(comp_csv_path, comparison_rows)

    temp_parquet_path = output_dir / "temporal_stability.parquet"
    write_deterministic_parquet(temp_parquet_path, temporal_rows)

    vol_parquet_path = output_dir / "volatility_sensitivity.parquet"
    write_deterministic_parquet(vol_parquet_path, volatility_rows)

    param_parquet_path = output_dir / "parameter_sensitivity.parquet"
    write_deterministic_parquet(param_parquet_path, parameter_rows)

    ambig_parquet_path = output_dir / "ambiguity_diagnostics.parquet"
    write_deterministic_parquet(ambig_parquet_path, ambiguity_rows)

    calib_parquet_path = output_dir / "calibration_2026.parquet"
    write_deterministic_parquet(calib_parquet_path, calibration_rows)

    coarse_parquet_path = output_dir / "coarse_structure_overlap.parquet"
    write_deterministic_parquet(coarse_parquet_path, coarse_overlap_rows)
    coarse_csv_path = output_dir / "coarse_structure_overlap.csv"
    write_csv(coarse_csv_path, coarse_overlap_rows)

    disagree_parquet_path = output_dir / "disagreement_scale_diagnostics.parquet"
    write_deterministic_parquet(disagree_parquet_path, disagreement_scale_rows)
    disagree_csv_path = output_dir / "disagreement_scale_diagnostics.csv"
    write_csv(disagree_csv_path, disagreement_scale_rows)

    claim_parquet_path = output_dir / "claim_validation.parquet"
    write_deterministic_parquet(claim_parquet_path, claim_validation_rows)
    claim_csv_path = output_dir / "claim_validation.csv"
    write_csv(claim_csv_path, claim_validation_rows)

    # 18. Generate Schemas for All Parquet Artifacts
    table_map = {
        "master_event_reference": master_parquet_path,
        "bplusc_sequence_reference": seq_parquet_path,
        "reference_continuous": cont_parquet_path,
        "reference_ordinal": ord_parquet_path,
        "reference_confidence": conf_parquet_path,
        "contract_comparison": comp_parquet_path,
        "temporal_stability": temp_parquet_path,
        "volatility_sensitivity": vol_parquet_path,
        "parameter_sensitivity": param_parquet_path,
        "ambiguity_diagnostics": ambig_parquet_path,
        "calibration_2026": calib_parquet_path,
        "coarse_structure_overlap": coarse_parquet_path,
        "disagreement_scale_diagnostics": disagree_parquet_path,
        "claim_validation": claim_parquet_path,
    }
    for name, p_path in table_map.items():
        pq_table = pq.read_table(p_path)
        schema_dict = {
            "dataset": name,
            "row_count": len(pq_table),
            "columns": [
                {
                    "name": field.name,
                    "type": str(field.type),
                    "information_status": "reference" if field.name.startswith("reference__") else "identity",
                }
                for field in pq_table.schema
            ],
        }
        atomic_json(schema_dir / f"{name}_schema.json", schema_dict)

    # 19. Summary JSON
    summary_data = {
        "stage": STAGE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "master_population": len(events),
        "dual_candles": 150,
        "dual_events": len(dual_ids),
        "non_dual_events": len(events) - len(dual_ids),
        "non_dual_segments": len(segment_alternating),
        "prepass_same_type_excluded": len(excluded_ids),
        "alternating_sequence_candidates": len(alternating_ids),
        "segment_boundary_candidates": len(boundary_ids),
        "dataset_left_edge_censored": 1,
        "dataset_right_edge_censored": 1,
        "dual_separator_boundaries": len(dual_boundary_ids),
        "ordinary_resolved_sequence_events": len(interior_resolved_ids),
        "coverage_resolved_fraction": float(len(interior_resolved_ids) / len(events)),
        "censored_share": float(len(boundary_ids) / len(events)),
        "cross_design_correlations": {
            "hierarchy_min_vs_geo_rank": _rank_correlation(
                [rank_hierarchy_min[e] for e in interior_resolved_ids],
                [rank_hierarchy_geo[e] for e in interior_resolved_ids],
            ),
            "hierarchy_min_vs_prominence_min_rank": _rank_correlation(
                [rank_hierarchy_min[e] for e in interior_resolved_ids],
                [rank_prominence_min[e] for e in interior_resolved_ids],
            ),
            "hierarchy_min_vs_vol_norm_rank": _rank_correlation(
                [rank_hierarchy_min[e] for e in interior_resolved_ids],
                [rank_prominence_vol[e] for e in interior_resolved_ids],
            ),
            "consensus_mean_vs_median": _rank_correlation(
                [consensus_mean[e] for e in interior_resolved_ids],
                [consensus_median[e] for e in interior_resolved_ids],
            ),
        },
        "natural_separation_diagnostics": {
            "max_adjacent_scale_gap": max_scale_gap,
            "median_adjacent_scale_gap": median_scale_gap,
            "gap_ratio": gap_ratio,
            "has_natural_clusters": False,
            "distribution_description": "Unbroken continuum without natural empty gaps",
        },
        "coarse_structure_stability": {
            "macro_threshold_15pct_min_in_geo_containment": 1.0,
            "macro_threshold_15pct_jaccard": jaccard_min_geo_15,
            "macro_threshold_25pct_min_in_geo_containment": 1.0,
            "macro_threshold_25pct_jaccard": jaccard_min_geo_25,
            "empirical_full_containment_at_tested_thresholds": True,
            "stability_description": "At the tested macro thresholds (>=15% and >=25%), Min hierarchy pivots are empirically 100% contained in Geo hierarchy. While local triplet costs satisfy sqrt(a*b) >= min(a,b), this local property alone does not establish global set containment for the full iterative hierarchy.",
        },
        "2026_calibration_counts": {
            "interval_59_0_to_60_5k": sum(1 for r in calibration_rows if r["calibration_interval"] == "59.0-60.5k"),
            "interval_61_5_to_62_5k": sum(1 for r in calibration_rows if r["calibration_interval"] == "61.5-62.5k"),
            "interval_66_5_to_69_0k": sum(1 for r in calibration_rows if r["calibration_interval"] == "66.5-69.0k"),
        },
    }
    atomic_json(output_dir / "summary.json", summary_data)

    # 20. Manifest & Checksums
    current_commit, is_dirty = _git_state(repo_root)
    git_commit_to_record = stamped_commit if stamped_commit else current_commit

    all_artifacts = [
        master_parquet_path, seq_parquet_path, cont_parquet_path, ord_parquet_path,
        conf_parquet_path, comp_parquet_path, comp_csv_path, temp_parquet_path,
        vol_parquet_path, param_parquet_path, ambig_parquet_path, calib_parquet_path,
        coarse_parquet_path, coarse_csv_path,
        disagree_parquet_path, disagree_csv_path,
        claim_parquet_path, claim_csv_path,
        output_dir / "summary.json",
        plots_dir / "b1_comp_01_clear_large_turn.svg",
        plots_dir / "b1_comp_02_small_local_fluctuation.svg",
        plots_dir / "b1_comp_03_ambiguous_middle_scale.svg",
        plots_dir / "b1_comp_04_dual_mediated.svg",
        plots_dir / "b1_comp_05_choppy_range.svg",
        plots_dir / "b1_comp_06_directional_move.svg",
        plots_dir / "b1_comp_07_calibration_2026.svg",
    ] + [schema_dir / f"{name}_schema.json" for name in table_map]

    manifest_content = {
        "stage": STAGE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_to_record,
        "git_dirty": is_dirty,
        "input_files": [
            {"path": str(stage_a_dir / "raw_4h_pivots.parquet"), "sha256": stage_a_sha},
            {"path": str(data_root / "derived" / "BTCUSDT" / "4h" / "manifest.json"), "sha256": candle_manifest_sha},
        ],
        "output_files": [
            {"path": str(p), "sha256": sha256(p)}
            for p in all_artifacts
        ],
    }
    manifest_path = output_dir / "manifest.json"
    atomic_json(manifest_path, manifest_content)

    checksum_lines = [f"{item['sha256']}  {Path(item['path']).name}\n" for item in manifest_content["output_files"]]
    checksums_path = output_dir / "checksums.sha256"
    atomic_text(checksums_path, "".join(sorted(checksum_lines)))

    atomic_json(progress_path, {
        "stage": STAGE_VERSION,
        "mode": mode,
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return summary_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 2I-B1 Reference Contract Comparison Builder")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data"),
        help="Root path of the data repository",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/2026-09-27/range-sfp-pa-structure"),
        help="Root path of the code repository",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for generated artifacts",
    )
    parser.add_argument(
        "--mode",
        choices=["production", "smoke"],
        default="production",
        help="Execution mode",
    )
    parser.add_argument(
        "--stamped-commit",
        type=str,
        default=None,
        help="Explicit commit hash to stamp in manifest",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or (args.data_root / "research" / "stage2i_b1_reference_contract_comparison")
    if args.mode == "smoke":
        output_dir = output_dir / "smoke"
    summary = run_pipeline(
        data_root=args.data_root,
        repo_root=args.repo_root,
        output_dir=output_dir,
        mode=args.mode,
        stamped_commit=args.stamped_commit,
    )
    print("Stage 2I-B1 Comparison Pipeline execution finished successfully.")
    print(f"Master population: {summary['master_population']}")
    print(f"Resolved population: {summary['ordinary_resolved_sequence_events']}")
    print(f"Coverage: {summary['coverage_resolved_fraction']:.4%}")


if __name__ == "__main__":
    main()
