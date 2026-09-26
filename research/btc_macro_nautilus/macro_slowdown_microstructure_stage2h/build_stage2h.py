#!/usr/bin/env python3
"""Stage 2H: causal lower-timeframe microstructure inside frozen Stage 2F slowdowns."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence, cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


SEED = 20260926
BOOTSTRAP_REPETITIONS = 1000
TIMEFRAME_MINUTES = {"15m": 15, "5m": 5, "3m": 3, "1m": 1}
TIMEFRAMES = tuple(TIMEFRAME_MINUTES)
STAGE2F_AUC = 0.7223262032085561
STAGE2F_BALANCED_ACCURACY = 0.6776069518716578
H0_FEATURES = [
    "persistence", "alternation", "volatility", "volume", "trade_count", "overlap", "speed", "geometry",
    "delta_persistence", "delta_alternation", "delta_volatility", "delta_volume", "delta_trade_count",
    "delta_overlap_body_overlap_mean", "delta_speed_movement_rate_mean", "delta_candle_geometry_mean",
]
FAMILIES = {
    "directional": ["persistence", "alternation", "alignment_fraction", "directional_sign_changes_per_step",
                    "maximum_same_direction_run", "mean_same_direction_run_length"],
    "path_geometry": ["overlap_body_overlap_mean", "total_travelled_path", "path_efficiency",
                      "counter_move_share", "maximum_favourable_excursion", "maximum_adverse_excursion",
                      "end_retention"],
    "volatility": ["log_range_mean", "log_range_median", "log_range_std", "log_range_iqr",
                   "log_range_min", "log_range_max", "log_range_slope"],
    "participation": ["volume_mean", "volume_median", "volume_std", "volume_iqr", "volume_min", "volume_max",
                      "volume_slope", "trade_count_mean", "trade_count_median", "trade_count_std",
                      "trade_count_iqr", "trade_count_min", "trade_count_max", "trade_count_slope"],
    "movement_rate": ["directional_step_mean", "directional_step_median", "directional_step_std",
                      "directional_step_iqr", "directional_step_min", "directional_step_max",
                      "directional_step_slope", "movement_rate_mean", "movement_rate_slope",
                      "directional_rate_mean", "directional_rate_slope", "progress_per_volume",
                      "progress_per_trade_count", "progress_relative_to_volatility", "path_per_volume",
                      "path_per_trade_count"],
}
MICRO_FEATURES = [feature for family in FAMILIES.values() for feature in family]
ARTIFACT_ONLY_ALGEBRAIC = ["abs_net_progress", "forward_move_share", "retracement_from_internal_extreme"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def write_parquet(path: Path, rows: Sequence[dict[str, object]]) -> None:
    temporary = path.with_name(path.name + ".partial")
    pq.write_table(pa.Table.from_pylist(list(rows)), temporary, compression="zstd")
    os.replace(temporary, path)


def write_checksums(root: Path) -> bool:
    targets = sorted(path for path in root.iterdir() if path.name != "checksums.sha256")
    index = root / "checksums.sha256"
    index.write_text("".join(f"{sha256_file(path)}  {path.name}\n" for path in targets), encoding="utf-8")
    lines = index.read_text(encoding="utf-8").splitlines()
    return len(lines) == len(targets) and all(
        line.split(maxsplit=1)[0] == sha256_file(path) and line.split(maxsplit=1)[1].strip() == path.name
        for path, line in zip(targets, lines)
    )


def as_utc(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value)}")
    if value.tzinfo is None:
        raise ValueError("Naive timestamp is forbidden")
    return value.astimezone(timezone.utc)


def select_half_open(rows: Sequence[dict[str, object]], start: object, end: object) -> list[dict[str, object]]:
    start_dt, end_dt = as_utc(start), as_utc(end)
    return [row for row in rows if as_utc(row["start_time"]) >= start_dt and as_utc(row["end_time"]) <= end_dt]


def summary(values: np.ndarray, prefix: str) -> dict[str, float]:
    if values.size == 0:
        raise ValueError(f"No values for {prefix}")
    return {
        f"{prefix}_mean": float(np.mean(values)), f"{prefix}_median": float(np.median(values)),
        f"{prefix}_std": float(np.std(values)),
        f"{prefix}_iqr": float(np.quantile(values, .75) - np.quantile(values, .25)),
        f"{prefix}_min": float(np.min(values)), f"{prefix}_max": float(np.max(values)),
    }


def robust_slope(values: np.ndarray) -> float:
    """Huber M-estimator slope against normalized elapsed time [0,1]."""
    y = np.asarray(values, dtype=float)
    if y.size < 2 or np.all(y == y[0]):
        return 0.0
    x = np.linspace(0.0, 1.0, y.size)
    design = np.column_stack([np.ones(y.size), x])
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    for _ in range(30):
        residual = y - design @ beta
        scale = 1.4826 * np.median(np.abs(residual - np.median(residual)))
        if scale <= np.finfo(float).eps:
            break
        standardized = np.abs(residual) / (1.345 * scale)
        weights = np.ones_like(standardized)
        mask = standardized > 1
        weights[mask] = 1 / standardized[mask]
        weighted = design * np.sqrt(weights)[:, None]
        updated = np.linalg.lstsq(weighted, y * np.sqrt(weights), rcond=None)[0]
        if np.max(np.abs(updated - beta)) < 1e-12:
            beta = updated
            break
        beta = updated
    return float(beta[1])


def _float(row: dict[str, object], field: str) -> float:
    value = row[field]
    if value is None:
        raise ValueError(f"Null {field}")
    return float(cast(float, value))


def microstructure_features(rows: Sequence[dict[str, object]], direction: int, timeframe: str) -> dict[str, object]:
    if direction not in (-1, 1) or timeframe not in TIMEFRAME_MINUTES:
        raise ValueError("Invalid direction/timeframe")
    if len(rows) < 2:
        raise ValueError("At least two complete bars are required")
    closes = np.asarray([_float(row, "close") for row in rows])
    opens = np.asarray([_float(row, "open") for row in rows])
    highs = np.asarray([_float(row, "high") for row in rows])
    lows = np.asarray([_float(row, "low") for row in rows])
    volumes = np.asarray([_float(row, "volume") for row in rows])
    trades = np.asarray([_float(row, "trade_count") for row in rows])
    if np.any(closes <= 0) or np.any(opens <= 0) or np.any(lows <= 0):
        raise ValueError("Non-positive price")
    steps = np.diff(np.log(closes))
    directional_steps = steps * direction
    signs = np.sign(steps).astype(int)
    directional_signs = signs * direction
    nonzero = signs[signs != 0]
    changes = int(np.sum(nonzero[1:] != nonzero[:-1])) if nonzero.size > 1 else 0
    runs: list[int] = []
    if nonzero.size:
        length = 1
        for previous, current in zip(nonzero[:-1], nonzero[1:]):
            if current == previous:
                length += 1
            else:
                runs.append(length)
                length = 1
        runs.append(length)
    total_path = float(np.sum(np.abs(steps)))
    directional_net = float(np.sum(directional_steps))
    forward = float(np.sum(directional_steps[directional_steps > 0]))
    counter = float(-np.sum(directional_steps[directional_steps < 0]))
    if total_path <= np.finfo(float).eps:
        path_efficiency = forward_share = counter_share = 0.0
    else:
        path_efficiency = abs(directional_net) / total_path
        forward_share, counter_share = forward / total_path, counter / total_path
    overlap = []
    for previous, current in zip(rows[:-1], rows[1:]):
        previous_low, previous_high = sorted((_float(previous, "open"), _float(previous, "close")))
        current_low, current_high = sorted((_float(current, "open"), _float(current, "close")))
        overlap.append(max(0.0, min(previous_high, current_high) - max(previous_low, current_low)))
    log_ranges = np.log(highs / lows)
    minutes = TIMEFRAME_MINUTES[timeframe]
    step_hours = minutes / 60.0
    rates = np.abs(steps) / step_hours
    directional_rates = directional_steps / step_hours
    start_price = opens[0]
    favourable = np.maximum(direction * np.log(highs / start_price), direction * np.log(lows / start_price))
    adverse = np.minimum(direction * np.log(highs / start_price), direction * np.log(lows / start_price))
    mfe = max(0.0, float(np.max(favourable)))
    mae = max(0.0, float(-np.min(adverse)))
    final_progress = float(direction * math.log(closes[-1] / start_price))
    total_volume, total_trades = float(np.sum(volumes)), float(np.sum(trades))
    total_volatility = float(np.sum(log_ranges))
    result: dict[str, object] = {
        "timeframe": timeframe, "bar_count": len(rows), "step_count": len(steps),
        "persistence": float(np.mean(directional_signs)),
        "alternation": float(changes / (nonzero.size - 1)) if nonzero.size > 1 else 0.0,
        "alignment_fraction": float(np.mean(directional_signs > 0)),
        "directional_sign_changes": changes,
        "directional_sign_changes_per_step": float(changes / max(1, nonzero.size - 1)),
        "maximum_same_direction_run": max(runs) if runs else 0,
        "mean_same_direction_run_length": float(np.mean(runs)) if runs else 0.0,
        "overlap_body_overlap_mean": float(np.mean(overlap)),
        "total_travelled_path": total_path, "directional_net_progress": directional_net,
        "abs_net_progress": abs(directional_net), "window_directional_progress": final_progress,
        "path_efficiency": path_efficiency, "forward_move_share": forward_share,
        "counter_move_share": counter_share, "maximum_favourable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "end_retention": final_progress / mfe if mfe > np.finfo(float).eps else 0.0,
        "retracement_from_internal_extreme": mfe - final_progress,
        "movement_rate_mean": float(np.mean(rates)), "movement_rate_slope": robust_slope(rates),
        "directional_rate_mean": float(np.mean(directional_rates)),
        "directional_rate_slope": robust_slope(directional_rates),
        "progress_per_volume": final_progress / total_volume if total_volume > 0 else 0.0,
        "progress_per_trade_count": final_progress / total_trades if total_trades > 0 else 0.0,
        "progress_relative_to_volatility": final_progress / total_volatility if total_volatility > 0 else 0.0,
        "path_per_volume": total_path / total_volume if total_volume > 0 else 0.0,
        "path_per_trade_count": total_path / total_trades if total_trades > 0 else 0.0,
        "total_volume": total_volume, "total_trade_count": total_trades,
        "first_bar_start": as_utc(rows[0]["start_time"]), "last_bar_end": as_utc(rows[-1]["end_time"]),
    }
    result.update(summary(log_ranges, "log_range"))
    result.update(summary(volumes, "volume"))
    result.update(summary(trades, "trade_count"))
    result.update(summary(directional_steps, "directional_step"))
    result["log_range_slope"] = robust_slope(log_ranges)
    result["volume_slope"] = robust_slope(volumes)
    result["trade_count_slope"] = robust_slope(trades)
    result["directional_step_slope"] = robust_slope(directional_steps)
    return result


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(values, -30, 30)))


def fit_ridge(features: np.ndarray, outcome: np.ndarray, penalty: float = .1) -> np.ndarray:
    weights = np.zeros(features.shape[1] + 1)
    for _ in range(500):
        probability = sigmoid(weights[0] + features @ weights[1:])
        gradient_intercept = np.mean(probability - outcome)
        gradient = features.T @ (probability - outcome) / len(outcome) + penalty * weights[1:]
        weights -= .05 * np.r_[gradient_intercept, gradient]
    return weights


def auc(outcome: np.ndarray, probability: np.ndarray) -> float | None:
    positive, negative = probability[outcome == 1], probability[outcome == 0]
    if not len(positive) or not len(negative):
        return None
    return float((np.sum(positive[:, None] > negative) + .5 * np.sum(positive[:, None] == negative)) /
                 (len(positive) * len(negative)))


def model_metrics(outcome: np.ndarray, probability: np.ndarray) -> dict[str, float | None]:
    score = auc(outcome, probability)
    balanced = float(((probability[outcome == 1] >= .5).mean() + (probability[outcome == 0] < .5).mean()) / 2)
    clipped = np.clip(probability, 1e-12, 1 - 1e-12)
    return {"auc": score, "balanced_accuracy": balanced,
            "brier_score": float(np.mean((probability - outcome) ** 2)),
            "log_loss": float(-np.mean(outcome * np.log(clipped) + (1 - outcome) * np.log(1 - clipped)))}


@dataclass(frozen=True)
class ModelResult:
    predictions: np.ndarray
    metrics: dict[str, float | None]
    folds: list[dict[str, object]]
    coefficients: list[dict[str, object]]
    group_disjoint: bool


def grouped_model(rows: Sequence[dict[str, object]], feature_names: Sequence[str]) -> ModelResult:
    matrix = np.asarray([[float(cast(float, row[name])) for name in feature_names] for row in rows], dtype=float)
    outcome = np.asarray([int(cast(int, row["outcome_binary"])) for row in rows])
    groups = np.asarray([str(row["parent_macro_leg_id"]) for row in rows])
    if not np.isfinite(matrix).all():
        raise ValueError("Non-finite model matrix")
    predictions = np.full(len(rows), np.nan)
    folds: list[dict[str, object]] = []
    disjoint = True
    for group in sorted(set(groups)):
        test = groups == group
        train = ~test
        disjoint = disjoint and not np.any(groups[train] == group) and np.all(groups[test] == group)
        if len(set(outcome[train])) < 2:
            continue
        mean, scale = matrix[train].mean(0), matrix[train].std(0)
        scale[scale == 0] = 1
        weights = fit_ridge((matrix[train] - mean) / scale, outcome[train])
        predictions[test] = sigmoid(weights[0] + ((matrix[test] - mean) / scale) @ weights[1:])
        folds.append({"held_out_macro_leg_id": group, "test_rows": int(test.sum()),
                      "train_rows": int(train.sum()), "train_only_preprocessing": True})
    if not np.isfinite(predictions).all():
        raise RuntimeError("Incomplete grouped predictions")
    mean, scale = matrix.mean(0), matrix.std(0)
    scale[scale == 0] = 1
    weights = fit_ridge((matrix - mean) / scale, outcome)
    coefficients = [{"feature": name, "coefficient_for_reversal": float(value)}
                    for name, value in zip(feature_names, weights[1:])]
    return ModelResult(predictions, model_metrics(outcome, predictions), folds, coefficients, disjoint)


def grouped_bootstrap_delta(outcome: np.ndarray, groups: np.ndarray, baseline: np.ndarray,
                            candidate: np.ndarray, repetitions: int = BOOTSTRAP_REPETITIONS,
                            seed: int = SEED) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    unique = np.asarray(sorted(set(groups)))
    distributions: dict[str, list[float]] = defaultdict(list)
    for _ in range(repetitions):
        sampled = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([np.flatnonzero(groups == group) for group in sampled])
        base_metrics, candidate_metrics = model_metrics(outcome[indices], baseline[indices]), model_metrics(outcome[indices], candidate[indices])
        if base_metrics["auc"] is None or candidate_metrics["auc"] is None:
            continue
        for metric in ("auc", "balanced_accuracy", "brier_score", "log_loss"):
            distributions[metric].append(float(cast(float, candidate_metrics[metric])) - float(cast(float, base_metrics[metric])))
    result: dict[str, float | int] = {"repetitions": repetitions, "valid_repetitions": len(distributions["auc"])}
    for metric, values in distributions.items():
        result[f"delta_{metric}_ci_low"] = float(np.quantile(values, .025))
        result[f"delta_{metric}_ci_high"] = float(np.quantile(values, .975))
    return result


def cliffs_delta(left: Sequence[float], right: Sequence[float]) -> float:
    return float(np.mean(np.sign(np.asarray(left)[:, None] - np.asarray(right)[None, :])))


def grouped_median_bootstrap(rows: Sequence[dict[str, object]], feature: str, seed: int) -> tuple[float, float]:
    by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_group[str(row["parent_macro_leg_id"])].append(row)
    groups = sorted(by_group)
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        sample = [row for group in rng.choice(groups, len(groups), replace=True) for row in by_group[str(group)]]
        continuation = [float(cast(float, row[feature])) for row in sample if row["outcome"] == "CONTINUATION"]
        reversal = [float(cast(float, row[feature])) for row in sample if row["outcome"] == "REVERSAL"]
        if continuation and reversal:
            differences.append(float(np.median(continuation) - np.median(reversal)))
    return float(np.quantile(differences, .025)), float(np.quantile(differences, .975))


def direction_sign(row: dict[str, object]) -> int:
    macro = 1 if row["parent_direction"] == "up" else -1
    relative = 1 if row["current_direction_relative"] == "forward" else -1
    return macro * relative


@dataclass(frozen=True)
class Window:
    slowdown_id: str
    start: datetime
    end: datetime


def merge_windows(windows: Sequence[Window]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for window in sorted(windows, key=lambda value: value.start):
        if not merged or window.start > merged[-1][1]:
            merged.append([window.start, window.end])
        else:
            merged[-1][1] = max(merged[-1][1], window.end)
    return [(item[0], item[1]) for item in merged]


def assign_rows_to_windows(rows: Iterable[dict[str, object]], windows: Sequence[Window]) -> dict[str, list[dict[str, object]]]:
    ordered = sorted(windows, key=lambda value: value.start)
    result = {window.slowdown_id: [] for window in ordered}
    active: list[Window] = []
    index = 0
    for row in rows:
        timestamp = as_utc(row["start_time"])
        while index < len(ordered) and ordered[index].start <= timestamp:
            active.append(ordered[index])
            index += 1
        active = [window for window in active if window.end > timestamp]
        for window in active:
            if timestamp >= window.start and as_utc(row["end_time"]) <= window.end:
                result[window.slowdown_id].append(row)
    return result


def iter_derived_windows(root: Path, timeframe: str, windows: Sequence[Window]) -> Iterator[dict[str, object]]:
    years = {year for window in windows for year in range(window.start.year, window.end.year + 1)}
    columns = ["start_time", "end_time", "open", "high", "low", "close", "volume", "quote_volume",
               "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume", "complete", "incomplete_reason"]
    merged = merge_windows(windows)
    for path in sorted((root / f"derived/BTCUSDT/{timeframe}").glob("part-*.parquet")):
        if int(path.stem.split("-")[1]) not in years:
            continue
        for batch in pq.ParquetFile(path).iter_batches(batch_size=100_000, columns=columns):
            for row in batch.to_pylist():
                start = as_utc(row["start_time"])
                if any(begin <= start < end for begin, end in merged):
                    yield cast(dict[str, object], row)


def load_canonical_module(repo_root: Path) -> object:
    path = repo_root / "research/btc_macro_nautilus/canonical_candles/build_canonical_futures_candles.py"
    spec = importlib.util.spec_from_file_location("canonical_stage2h_reader", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def iter_1m_windows(data_root: Path, repo_root: Path, windows: Sequence[Window]) -> Iterator[dict[str, object]]:
    module = load_canonical_module(repo_root)
    manifest_path = data_root / "manifests/strict_futures_1m_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ranges = [(int(begin.timestamp() * 1000), int(end.timestamp() * 1000) - 60_000)
              for begin, end in merge_windows(windows)]
    iterator = getattr(module, "iter_source_rows")(manifest, ranges)
    for raw in iterator:
        start = datetime.fromtimestamp(int(raw[0]) / 1000, timezone.utc)
        yield {"start_time": start, "end_time": start + timedelta(minutes=1), "open": float(raw[1]),
               "high": float(raw[2]), "low": float(raw[3]), "close": float(raw[4]), "volume": float(raw[5]),
               "quote_volume": float(raw[6]), "trade_count": int(raw[7]),
               "taker_buy_base_volume": float(raw[8]), "taker_buy_quote_volume": float(raw[9]),
               "complete": True, "incomplete_reason": None}


def load_population(data_root: Path) -> tuple[list[dict[str, object]], list[Window]]:
    stage2f = data_root / "research/macro_slowdown_outcome_stage2f"
    population = cast(list[dict[str, object]], pq.read_table(stage2f / "slowdown_population.parquet").to_pylist())
    candidates = cast(list[dict[str, object]], pq.read_table(
        data_root / "research/macro_within_leg_stage2a/candidate_subsegments.parquet").to_pylist())
    candidate_by_id = {str(row["subsegment_id"]): row for row in candidates}
    windows = []
    for row in population:
        source = candidate_by_id[str(row["slowdown_id"])]
        row["slowdown_start"] = as_utc(source["start_timestamp"])
        row["slowdown_end"] = as_utc(source["end_timestamp"])
        windows.append(Window(str(row["slowdown_id"]), as_utc(source["start_timestamp"]), as_utc(source["end_timestamp"])))
    return population, windows


def effective_features(rows: Sequence[dict[str, object]], declared: Sequence[str], prefix: str) -> tuple[list[str], list[dict[str, object]]]:
    kept, audit = [], []
    matrix = np.asarray([[float(cast(float, row[prefix + name])) for name in declared] for row in rows])
    prior: list[int] = []
    for index, name in enumerate(declared):
        column = matrix[:, index]
        reason = None
        if np.std(column) <= np.finfo(float).eps:
            reason = "zero_variance"
        else:
            for previous in prior:
                if np.array_equal(column, matrix[:, previous]):
                    reason = f"exact_duplicate_of:{declared[previous]}"
                    break
        if reason is None:
            kept.append(prefix + name)
            prior.append(index)
        audit.append({"feature": prefix + name, "status": "included" if reason is None else "excluded", "reason": reason})
    return kept, audit


def compatible_checkpoint(output: Path, source_sha256: str) -> tuple[Path, dict[str, object]] | None:
    candidates = sorted(output.parent.glob(f".{output.name}.build-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        lease_path = candidate / "active_lease.json"
        if lease_path.is_file():
            lease = cast(dict[str, object], json.loads(lease_path.read_text(encoding="utf-8")))
            try:
                os.kill(int(cast(int, lease["pid"])), 0)
                continue
            except (OSError, KeyError, TypeError, ValueError):
                pass
        checkpoint_path = candidate / "progress_checkpoint.json"
        if not checkpoint_path.is_file():
            continue
        checkpoint = cast(dict[str, object], json.loads(checkpoint_path.read_text(encoding="utf-8")))
        completed = cast(list[str], checkpoint.get("completed_timeframes", []))
        if (checkpoint.get("source_population_sha256") == source_sha256 and
                all((candidate / f"microstructure_{timeframe}.parquet").is_file() for timeframe in completed)):
            return candidate, checkpoint
    return None


def build(data_root: Path, repo_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    output = data_root / "research/macro_slowdown_microstructure_stage2h"
    if output.exists():
        raise FileExistsError(output)
    source_population_path = data_root / "research/macro_slowdown_outcome_stage2f/slowdown_population.parquet"
    source_population_sha = sha256_file(source_population_path)
    checkpoint_match = compatible_checkpoint(output, source_population_sha)
    if checkpoint_match:
        temporary, checkpoint = checkpoint_match
        run_id = str(checkpoint["run_id"])
        completed_timeframes = cast(list[str], checkpoint["completed_timeframes"])
    else:
        temporary = output.parent / f".{output.name}.build-{uuid.uuid4().hex}"
        temporary.mkdir(parents=True)
        run_id = uuid.uuid4().hex
        completed_timeframes = []
    atomic_json(temporary / "active_lease.json", {"pid": os.getpid(), "run_id": run_id,
                                                   "started_at_utc": datetime.now(timezone.utc)})
    try:
        population, windows = load_population(data_root)
        window_by_id = {window.slowdown_id: window for window in windows}
        population_ids = [str(row["slowdown_id"]) for row in population]
        if len(population_ids) != 210 or len(set(population_ids)) != 210:
            raise RuntimeError("Stage 2F population contract mismatch")
        feature_rows: dict[str, list[dict[str, object]]] = {}
        enriched = [{**row} for row in population]
        enriched_by_id = {str(row["slowdown_id"]): row for row in enriched}
        for timeframe in TIMEFRAMES:
            if timeframe in completed_timeframes:
                rows_for_tf = cast(list[dict[str, object]], pq.read_table(
                    temporary / f"microstructure_{timeframe}.parquet").to_pylist())
            else:
                source_rows = (iter_1m_windows(data_root, repo_root, windows) if timeframe == "1m"
                               else iter_derived_windows(data_root, timeframe, windows))
                by_window = assign_rows_to_windows(source_rows, windows)
                rows_for_tf = []
                minutes = TIMEFRAME_MINUTES[timeframe]
                for base in population:
                    slowdown_id = str(base["slowdown_id"])
                    window = window_by_id[slowdown_id]
                    bars = by_window[slowdown_id]
                    expected = int((window.end - window.start).total_seconds() / (60 * minutes))
                    aligned = (int(window.start.timestamp() // 60) % minutes == 0 and
                               int(window.end.timestamp() // 60) % minutes == 0)
                    complete = aligned and len(bars) == expected and all(bool(row["complete"]) for row in bars)
                    reason = None
                    if not aligned:
                        reason = "window_not_timeframe_aligned"
                    elif len(bars) != expected:
                        reason = f"constituent_count:{len(bars)}/{expected}"
                    elif not all(bool(row["complete"]) for row in bars):
                        reason = "incomplete_source_bar"
                    record: dict[str, object] = {
                        "slowdown_id": slowdown_id, "parent_macro_leg_id": base["parent_macro_leg_id"],
                        "outcome": base["outcome"], "outcome_binary": base["outcome_binary"],
                        "boundary_population": base["boundary_population"], "timeframe": timeframe,
                        "slowdown_start": window.start, "slowdown_end": window.end,
                        "expected_bar_count": expected, "actual_bar_count": len(bars),
                        "eligible": complete, "exclusion_reason": reason,
                    }
                    if complete:
                        record.update(microstructure_features(bars, direction_sign(base), timeframe))
                    rows_for_tf.append(record)
                write_parquet(temporary / f"microstructure_{timeframe}.parquet", rows_for_tf)
                completed_timeframes.append(timeframe)
            feature_rows[timeframe] = rows_for_tf
            for record in rows_for_tf:
                slowdown_id = str(record["slowdown_id"])
                enriched_by_id[slowdown_id][f"eligible_{timeframe}"] = record["eligible"]
                enriched_by_id[slowdown_id][f"exclusion_reason_{timeframe}"] = record["exclusion_reason"]
            atomic_json(temporary / "progress_checkpoint.json", {
                "run_id": run_id, "completed_timeframes": completed_timeframes,
                "stage": "feature_extraction", "source_population_sha256": sha256_file(
                    data_root / "research/macro_slowdown_outcome_stage2f/slowdown_population.parquet"),
            })

        common_ids = {slowdown_id for slowdown_id in population_ids if all(
            bool(enriched_by_id[slowdown_id][f"eligible_{timeframe}"]) for timeframe in TIMEFRAMES)}
        common = [row for row in enriched if str(row["slowdown_id"]) in common_ids]
        write_parquet(temporary / "slowdown_ltf_population.parquet", enriched)
        write_parquet(temporary / "common_tf_population.parquet", common)
        tf_by_id = {timeframe: {str(row["slowdown_id"]): row for row in rows}
                    for timeframe, rows in feature_rows.items()}
        modeling_rows: list[dict[str, object]] = []
        for base in common:
            row = {**base}
            for timeframe in TIMEFRAMES:
                row.update({f"{timeframe}_{name}": tf_by_id[timeframe][str(base["slowdown_id"])][name]
                            for name in MICRO_FEATURES + ARTIFACT_ONLY_ALGEBRAIC})
            modeling_rows.append(row)
        strong_full = [row for row in population if row["boundary_population"] == "strong"]
        strong = [row for row in modeling_rows if row["boundary_population"] == "strong"]
        weak = [row for row in modeling_rows if row["boundary_population"] == "weak"]
        baseline_full = grouped_model(strong_full, H0_FEATURES)
        baseline_reproduced = (abs(float(cast(float, baseline_full.metrics["auc"])) - STAGE2F_AUC) < 1e-12 and
                               abs(float(cast(float, baseline_full.metrics["balanced_accuracy"])) - STAGE2F_BALANCED_ACCURACY) < 1e-12)
        if not baseline_reproduced:
            raise RuntimeError(f"Stage 2F baseline mismatch: {baseline_full.metrics}")
        effective: dict[str, list[str]] = {}
        redundancy_rows: list[dict[str, object]] = []
        for timeframe in TIMEFRAMES:
            effective[timeframe], audit = effective_features(strong, MICRO_FEATURES, timeframe + "_")
            redundancy_rows.extend({**item, "timeframe": timeframe} for item in audit)
            matrix = np.asarray([[float(cast(float, row[name])) for name in effective[timeframe]] for row in strong])
            rank = int(np.linalg.matrix_rank(matrix - matrix.mean(0)))
            correlation = np.corrcoef(matrix, rowvar=False)
            high = int(np.sum(np.triu(np.abs(correlation) >= .95, 1)))
            redundancy_rows.append({"timeframe": timeframe, "feature": "__matrix__", "status": "diagnostic",
                                    "declared_columns": len(MICRO_FEATURES), "effective_columns": len(effective[timeframe]),
                                    "effective_rank": rank, "high_correlation_pairs_abs_ge_0_95": high,
                                    "algebraic_artifact_exclusions": ";".join(ARTIFACT_ONLY_ALGEBRAIC)})
        h0 = grouped_model(strong, H0_FEATURES)
        model_results = {"H0": h0}
        comparison: list[dict[str, object]] = [{"model": "H0", **h0.metrics, "delta_auc_vs_H0": 0.0,
                                                "rows": len(strong), "features": len(H0_FEATURES)}]
        bootstrap_rows: list[dict[str, object]] = []
        groups = np.asarray([str(row["parent_macro_leg_id"]) for row in strong])
        outcome = np.asarray([int(cast(int, row["outcome_binary"])) for row in strong])
        for timeframe in TIMEFRAMES:
            name = "H" + timeframe.removesuffix("m")
            result = grouped_model(strong, H0_FEATURES + effective[timeframe])
            model_results[name] = result
            comparison.append({"model": name, "timeframe": timeframe, **result.metrics,
                               "delta_auc_vs_H0": float(cast(float, result.metrics["auc"])) - float(cast(float, h0.metrics["auc"])),
                               "delta_balanced_accuracy_vs_H0": float(cast(float, result.metrics["balanced_accuracy"])) - float(cast(float, h0.metrics["balanced_accuracy"])),
                               "delta_brier_vs_H0": float(cast(float, result.metrics["brier_score"])) - float(cast(float, h0.metrics["brier_score"])),
                               "delta_log_loss_vs_H0": float(cast(float, result.metrics["log_loss"])) - float(cast(float, h0.metrics["log_loss"])),
                               "rows": len(strong), "features": len(H0_FEATURES) + len(effective[timeframe])})
            bootstrap_rows.append({"model": name, "timeframe": timeframe,
                                   **grouped_bootstrap_delta(outcome, groups, h0.predictions, result.predictions,
                                                             BOOTSTRAP_REPETITIONS, SEED + len(bootstrap_rows))})
        micro_only = []
        for timeframe in TIMEFRAMES:
            result = grouped_model(strong, effective[timeframe])
            micro_only.append({"timeframe": timeframe, **result.metrics, "rows": len(strong),
                               "features": len(effective[timeframe])})

        univariate: list[dict[str, object]] = []
        for timeframe in TIMEFRAMES:
            for offset, feature in enumerate(MICRO_FEATURES):
                name = timeframe + "_" + feature
                continuation = [float(cast(float, row[name])) for row in strong if row["outcome"] == "CONTINUATION"]
                reversal = [float(cast(float, row[name])) for row in strong if row["outcome"] == "REVERSAL"]
                effect = cliffs_delta(continuation, reversal)
                low, high = grouped_median_bootstrap(strong, name, SEED + offset + 100 * list(TIMEFRAMES).index(timeframe))
                signs = []
                for leg in sorted({str(row["parent_macro_leg_id"]) for row in strong}):
                    leg_rows = [row for row in strong if row["parent_macro_leg_id"] == leg]
                    left = [float(cast(float, row[name])) for row in leg_rows if row["outcome"] == "CONTINUATION"]
                    right = [float(cast(float, row[name])) for row in leg_rows if row["outcome"] == "REVERSAL"]
                    if left and right:
                        signs.append(np.sign(np.median(left) - np.median(right)) == np.sign(effect))
                univariate.append({"timeframe": timeframe, "feature": feature,
                                   "continuation_median": float(np.median(continuation)),
                                   "reversal_median": float(np.median(reversal)),
                                   "median_difference_cont_minus_rev": float(np.median(continuation) - np.median(reversal)),
                                   "group_bootstrap_ci_low": low, "group_bootstrap_ci_high": high,
                                   "cliffs_delta_cont_minus_rev": effect,
                                   "macro_leg_direction_consistency": float(np.mean(signs)) if signs else None,
                                   "macro_legs_with_both_outcomes": len(signs)})
        strongest = {timeframe: sorted([row for row in univariate if row["timeframe"] == timeframe],
                                       key=lambda row: -abs(float(cast(float, row["cliffs_delta_cont_minus_rev"]))))[:5]
                     for timeframe in TIMEFRAMES}
        family_ablation = []
        positive_timeframes = [timeframe for timeframe, row in zip(TIMEFRAMES, comparison[1:])
                               if float(cast(float, row["delta_auc_vs_H0"])) > 0]
        for timeframe in positive_timeframes:
            for family, names in FAMILIES.items():
                selected = [timeframe + "_" + name for name in names if timeframe + "_" + name in effective[timeframe]]
                result = grouped_model(strong, H0_FEATURES + selected)
                family_ablation.append({"timeframe": timeframe, "family": family, **result.metrics,
                                        "delta_auc_vs_H0": float(cast(float, result.metrics["auc"])) - float(cast(float, h0.metrics["auc"])),
                                        "feature_count": len(selected)})
        direction_results = []
        for context in ("forward", "counter"):
            context_rows = [row for row in strong if row["current_direction_relative"] == context]
            base = grouped_model(context_rows, H0_FEATURES)
            for timeframe in TIMEFRAMES:
                candidate = grouped_model(context_rows, H0_FEATURES + effective[timeframe])
                direction_results.append({"context": context, "timeframe": timeframe,
                                          "rows": len(context_rows),
                                          "continuation": sum(row["outcome"] == "CONTINUATION" for row in context_rows),
                                          "reversal": sum(row["outcome"] == "REVERSAL" for row in context_rows),
                                          "h0_auc": base.metrics["auc"], "micro_auc": candidate.metrics["auc"],
                                          "delta_auc": float(cast(float, candidate.metrics["auc"])) - float(cast(float, base.metrics["auc"]))})
        bull_bear, era_rows = [], []
        for timeframe in TIMEFRAMES:
            for item in strongest[timeframe]:
                name = timeframe + "_" + str(item["feature"])
                for direction in ("up", "down"):
                    subset = [row for row in strong if row["parent_direction"] == direction]
                    left = [float(cast(float, row[name])) for row in subset if row["outcome"] == "CONTINUATION"]
                    right = [float(cast(float, row[name])) for row in subset if row["outcome"] == "REVERSAL"]
                    bull_bear.append({"timeframe": timeframe, "feature": item["feature"], "parent_direction": direction,
                                      "rows": len(subset), "continuation": len(left), "reversal": len(right),
                                      "cliffs_delta": cliffs_delta(left, right) if left and right else None})
                for era in sorted({str(row["calendar_era"]) for row in strong}):
                    subset = [row for row in strong if str(row["calendar_era"]) == era]
                    left = [float(cast(float, row[name])) for row in subset if row["outcome"] == "CONTINUATION"]
                    right = [float(cast(float, row[name])) for row in subset if row["outcome"] == "REVERSAL"]
                    era_rows.append({"timeframe": timeframe, "feature": item["feature"], "calendar_era": era,
                                     "rows": len(subset), "continuation": len(left), "reversal": len(right),
                                     "cliffs_delta": cliffs_delta(left, right) if left and right else None})
        weak_sensitivity = []
        if weak:
            weak_h0 = grouped_model(weak, H0_FEATURES)
            for timeframe in TIMEFRAMES:
                candidate = grouped_model(weak, H0_FEATURES + effective[timeframe])
                weak_sensitivity.append({"timeframe": timeframe, "rows": len(weak), "h0_auc": weak_h0.metrics["auc"],
                                         "micro_auc": candidate.metrics["auc"],
                                         "delta_auc": float(cast(float, candidate.metrics["auc"])) - float(cast(float, weak_h0.metrics["auc"]))})

        combined_rows: list[dict[str, object]] = []
        robust = [row["timeframe"] for row in bootstrap_rows if float(cast(float, row["delta_auc_ci_low"])) > 0]
        if len(robust) >= 2:
            combined_features = [name for timeframe in robust for name in effective[str(timeframe)]]
            matrix = np.asarray([[float(cast(float, row[name])) for name in combined_features] for row in strong])
            rank = int(np.linalg.matrix_rank(matrix - matrix.mean(0)))
            if rank <= len(strong) // 3:
                result = grouped_model(strong, H0_FEATURES + combined_features)
                combined_rows.append({"timeframes": ";".join(map(str, robust)), "effective_rank": rank,
                                      "rows": len(strong), **result.metrics,
                                      "delta_auc_vs_H0": float(cast(float, result.metrics["auc"])) - float(cast(float, h0.metrics["auc"]))})

        representative = []
        for slowdown_id in (population_ids[0], population_ids[len(population_ids) // 2], population_ids[-1]):
            rows = [tf_by_id[timeframe][slowdown_id] for timeframe in TIMEFRAMES]
            volumes = [float(cast(float, row["total_volume"])) for row in rows]
            trades = [float(cast(float, row["total_trade_count"])) for row in rows]
            progress = [float(cast(float, row["window_directional_progress"])) for row in rows]
            representative.append({"slowdown_id": slowdown_id,
                                   "same_window": len({(row["slowdown_start"], row["slowdown_end"]) for row in rows}) == 1,
                                   "volume_consistent": bool(np.allclose(volumes, volumes[0], rtol=1e-12, atol=1e-6)),
                                   "trades_consistent": bool(np.allclose(trades, trades[0], rtol=0, atol=0)),
                                   "net_progress_consistent": bool(np.allclose(progress, progress[0], rtol=1e-12, atol=1e-12)),
                                   "no_future_bar": all(as_utc(row["last_bar_end"]) == window_by_id[slowdown_id].end for row in rows)})
        path_checks = all(
            float(cast(float, row["total_travelled_path"])) + 1e-12 >= float(cast(float, row["abs_net_progress"])) and
            0 <= float(cast(float, row["path_efficiency"])) <= 1 + 1e-12 and
            0 <= float(cast(float, row["forward_move_share"])) <= 1 + 1e-12 and
            0 <= float(cast(float, row["counter_move_share"])) <= 1 + 1e-12 and
            abs(float(cast(float, row["forward_move_share"])) + float(cast(float, row["counter_move_share"])) -
                (1.0 if float(cast(float, row["total_travelled_path"])) > np.finfo(float).eps else 0.0)) < 1e-10
            for timeframe in TIMEFRAMES for row in feature_rows[timeframe] if bool(row["eligible"])
        )
        common_ids_identical = all({str(row["slowdown_id"]) for row in feature_rows[timeframe] if bool(row["eligible"])} == common_ids
                                   for timeframe in TIMEFRAMES)
        same_folds = all([fold["held_out_macro_leg_id"] for fold in result.folds] ==
                         [fold["held_out_macro_leg_id"] for fold in h0.folds]
                         for name, result in model_results.items() if name != "H0")
        qa = {
            "status": "PASS", "run_id": run_id, "stage2f_population_rows": len(population),
            "slowdown_ids_match_stage2f": set(population_ids) == {str(row["slowdown_id"]) for row in enriched},
            "outcomes_unchanged": all(enriched_by_id[str(row["slowdown_id"])]["outcome"] == row["outcome"] for row in population),
            "boundary_status_unchanged": all(enriched_by_id[str(row["slowdown_id"])]["boundary_population"] == row["boundary_population"] for row in population),
            "duplicate_slowdown_ids": len(set(population_ids)) != len(population_ids),
            "window_alignment": all(int(window.start.timestamp()) % (4 * 3600) == 0 and int(window.end.timestamp()) % (4 * 3600) == 0 for window in windows),
            "representative_cross_tf": representative, "path_identities": path_checks,
            "stage2f_baseline_reproduced": baseline_reproduced,
            "baseline_auc": baseline_full.metrics["auc"], "baseline_balanced_accuracy": baseline_full.metrics["balanced_accuracy"],
            "common_sample_ids_identical": common_ids_identical, "common_fold_ids_identical": same_folds,
            "grouped_split_disjoint": all(result.group_disjoint for result in model_results.values()),
            "train_only_preprocessing": all(all(bool(fold["train_only_preprocessing"]) for fold in result.folds) for result in model_results.values()),
            "future_predictors_used": False, "next_subsegment_fields_in_predictors": False,
            "side_experiment_consumed": False, "finite_model_predictors": all(np.isfinite(result.predictions).all() for result in model_results.values()),
        }
        required = [qa["slowdown_ids_match_stage2f"], qa["outcomes_unchanged"], qa["boundary_status_unchanged"],
                    not qa["duplicate_slowdown_ids"], qa["window_alignment"],
                    all(all(bool(item[key]) for key in ("same_window", "volume_consistent", "trades_consistent", "net_progress_consistent", "no_future_bar")) for item in representative),
                    qa["path_identities"], qa["stage2f_baseline_reproduced"], qa["common_sample_ids_identical"],
                    qa["common_fold_ids_identical"], qa["grouped_split_disjoint"], qa["train_only_preprocessing"],
                    not qa["future_predictors_used"], not qa["side_experiment_consumed"], qa["finite_model_predictors"]]
        if not all(required):
            qa["status"] = "FAIL"
            raise RuntimeError(qa)

        contract = {
            "schema_version": "macro-slowdown-microstructure-stage2h-v1",
            "window": "[slowdown_start, slowdown_end), only complete canonical bars",
            "direction_normalization": "slowdown direction positive; outcome is never used",
            "persistence": "mean(sign(close_t/close_t-1) * slowdown_direction) using internal close steps only",
            "alternation": "fraction of changes between consecutive nonzero internal close-step signs",
            "overlap_body_overlap_mean": "mean(max(0,min(previous body high,current body high)-max(previous body low,current body low)))",
            "total_travelled_path": "sum(abs(log(close_t/close_t-1))) over internal close steps",
            "directional_net_progress": "slowdown-direction * log(final close/first close)",
            "window_directional_progress": "slowdown-direction * log(final close/first bar open); used for cross-TF and effort/result",
            "path_efficiency": "abs(directional_net_progress)/total_travelled_path; zero for zero path",
            "robust_slope": "Huber M-estimator slope (c=1.345) versus normalized elapsed index [0,1]",
            "families": FAMILIES, "primary_model_micro_features": MICRO_FEATURES,
            "artifact_only_algebraic_exclusions": ARTIFACT_ONLY_ALGEBRAIC,
        }
        write_csv(temporary / "univariate_microstructure_comparison.csv", univariate)
        write_csv(temporary / "tf_incremental_model_comparison.csv", comparison)
        write_csv(temporary / "tf_incremental_bootstrap.csv", bootstrap_rows)
        write_csv(temporary / "micro_only_model_comparison.csv", micro_only)
        write_csv(temporary / "feature_family_ablation.csv", family_ablation)
        write_csv(temporary / "direction_conditioned_results.csv", direction_results)
        write_csv(temporary / "bull_bear_sensitivity.csv", bull_bear)
        write_csv(temporary / "era_sensitivity.csv", era_rows)
        write_csv(temporary / "feature_redundancy_report.csv", redundancy_rows)
        write_csv(temporary / "strong_vs_weak_sensitivity.csv", weak_sensitivity)
        if combined_rows:
            write_csv(temporary / "combined_multitf_diagnostic.csv", combined_rows)
        atomic_json(temporary / "microstructure_feature_contract.json", contract)
        atomic_json(temporary / "qa.json", qa)
        confounder = (
            "# Stage 2H confounder report\n\n"
            f"All TF comparisons use the same {len(strong)} strong observations and identical leave-one-macro-leg-out folds. "
            "Duration and lower-TF bar count are not predictors; fixed windows make them deterministic multiples across TF. "
            "Calendar-era, parent bull/bear, forward/counter, and weak-boundary diagnostics are saved separately. "
            f"Excluded for incomplete lower-TF data: {len(population) - len(common)}. "
            "No pre-window, next-subsegment, external-level, or side-experiment data are used.\n"
        )
        (temporary / "confounder_report.md").write_text(confounder, encoding="utf-8")
        (temporary / "progress_checkpoint.json").unlink(missing_ok=True)
        (temporary / "active_lease.json").unlink(missing_ok=True)
        files = [{"path": str(output / path.name), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                 for path in sorted(temporary.iterdir())]
        manifest = {
            "schema_version": "macro-slowdown-microstructure-stage2h-v1", "run_id": run_id,
            "source_stage2f_population": str(data_root / "research/macro_slowdown_outcome_stage2f/slowdown_population.parquet"),
            "source_stage2f_population_sha256": sha256_file(data_root / "research/macro_slowdown_outcome_stage2f/slowdown_population.parquet"),
            "source_lower_tf_manifests": {timeframe: {
                "path": str(data_root / f"derived/BTCUSDT/{timeframe}/manifest.json"),
                "sha256": sha256_file(data_root / f"derived/BTCUSDT/{timeframe}/manifest.json")}
                for timeframe in ("15m", "5m", "3m")},
            "source_1m_manifest": str(data_root / "manifests/strict_futures_1m_manifest.json"),
            "source_1m_manifest_sha256": sha256_file(data_root / "manifests/strict_futures_1m_manifest.json"),
            "population": {"stage2f": len(population), "common": len(common), "strong_common": len(strong), "weak_common": len(weak)},
            "baseline": baseline_full.metrics, "qa": qa, "output_files": files,
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "execution": "union-window bounded reads; sequential TF extraction; atomic final promotion",
            "code_version": {"git_commit_at_build": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
                             "pipeline_sha256": sha256_file(Path(__file__)),
                             "working_tree_dirty_at_build": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True).strip())},
        }
        atomic_json(temporary / "manifest.json", manifest)
        if not write_checksums(temporary):
            raise RuntimeError("Checksum verification failed")
        os.replace(temporary, output)
        return {"status": "PASS", "output": str(output), "population": len(population), "common": len(common),
                "strong_common": len(strong), "runtime_seconds": manifest["runtime_seconds"], "checksums": "PASS"}
    except Exception:
        if temporary.is_dir():
            (temporary / "active_lease.json").unlink(missing_ok=True)
            atomic_json(temporary / "failure.json", {"run_id": run_id, "failed_at_utc": datetime.now(timezone.utc),
                                                      "checkpoint_preserved": True})
        raise


def stamp_git_commit(data_root: Path, commit: str) -> dict[str, object]:
    output = data_root / "research/macro_slowdown_microstructure_stage2h"
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["code_version"]["git_commit"] = commit
    atomic_json(manifest_path, manifest)
    if not write_checksums(output):
        raise RuntimeError("Checksum verification failed after stamp")
    return {"status": "PASS", "git_commit": commit, "checksums": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp-git-commit")
    arguments = parser.parse_args()
    result = (stamp_git_commit(arguments.data_root, arguments.stamp_git_commit) if arguments.stamp_git_commit
              else build(arguments.data_root, arguments.repo_root))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
