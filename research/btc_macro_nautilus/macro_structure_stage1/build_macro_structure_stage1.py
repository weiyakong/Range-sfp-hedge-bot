#!/usr/bin/env python3
"""Unsupervised Stage 1 diagnostics for validated futures macro-segment aggregates.

This module deliberately produces no semantic class labels.  It only prepares
feature-family matrices and reproducible structural/stability diagnostics.
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
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


SEED = 20260926
RESOLUTIONS = ("1d", "12h", "4h")
FAMILIES = (
    "overlap_body_overlap",
    "path_efficiency_counter_direction",
    "alternation_directional_persistence",
    "speed_movement_rate",
    "candle_geometry",
    "volatility_volume_activity",
)
SCHEMA_VERSION = "macro-structure-stage1-v1"
CONFIG = {
    "seed": SEED,
    "minimum_feature_coverage": 0.80,
    "near_duplicate_abs_correlation": 0.999999,
    "high_redundancy_abs_correlation": 0.98,
    "minimum_samples": 20,
    "minimum_features": 2,
    "clusterability_hopkins_supported": 0.65,
    "clusterability_silhouette_supported": 0.25,
    "clusterability_hopkins_weak": 0.55,
    "clusterability_silhouette_weak": 0.10,
    "candidate_k": [2, 3, 4, 5],
    "stability_repetitions": 20,
    "stability_subsample_fraction": 0.80,
    "stability_feature_fraction": 0.80,
    "stability_minimum_ari": 0.60,
}
IDENTITY_COLUMNS = {
    "segment_id", "start_point_id", "end_point_id", "segment_start", "segment_end", "direction",
    "known_macro_class", "known_macro_class_status", "resolution", "source_duration_precision",
    "aggregation_start_bound", "aggregation_end_bound", "start_boundary_mode", "end_boundary_mode",
    "membership_semantics", "segment_status", "measurement_first_timestamp", "measurement_last_end_time",
}
RELIABILITY_COLUMNS = {"atomic_row_count", "complete_candle_count", "incomplete_candle_count", "eligible_pair_count", "source_duration_hours"}
CONFOUNDER_COLUMNS = {"source_move_pct", "source_log_move", "source_duration_hours", "atomic_row_count", "complete_candle_count", "eligible_pair_count", "segment_start"}
NON_PREDICTOR_ATOMIC = {
    "source_constituent_count", "source_expected_constituent_count", "open", "high", "low", "close",
    "body_high", "body_low", "duration_hours",
}
SIGNED_ATOMIC = {
    "signed_price_change", "signed_close_return", "signed_return_pct", "signed_log_move",
    "raw_signed_speed_pct_per_hour", "signed_log_speed_per_hour",
}
STATISTICS = {"count", "mean", "median", "std", "min", "max", "p25", "p75", "eligible_count", "true_count", "true_share", "positive_count", "positive_share", "negative_count", "negative_share", "zero_count", "zero_share", "positive_share"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_seed(*parts: str, offset: int = 0) -> int:
    payload = "|".join(parts).encode("utf-8")
    return SEED + offset + int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % 1_000_000


def atomic_json(path: Path, value: Any) -> None:
    partial = path.with_name(path.name + ".partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    partial = path.with_name(path.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def family_for_atomic(name: str) -> str | None:
    if any(token in name for token in ("overlap", "penetration", "extension")):
        return "overlap_body_overlap"
    if name.startswith(("volume_body", "volume_close_step")):
        return "alternation_directional_persistence"
    if name in {"full_range", "true_range", "atr14_sma", "atr14_wilder", "log_full_range"} or name.startswith(("volume", "quote_volume", "trade_count", "taker_buy", "complete_volume", "complete_quote", "complete_trade", "complete_taker")):
        return "volatility_volume_activity"
    if name in {"body_size", "upper_wick", "lower_wick", "body_share", "upper_wick_share", "lower_wick_share", "log_body_size", "log_upper_wick", "log_lower_wick"}:
        return "candle_geometry"
    if name in SIGNED_ATOMIC or name.startswith(("absolute_price_change", "absolute_close_return", "absolute_return_pct", "absolute_log_move")):
        return "speed_movement_rate"
    return None


def parse_aggregate_column(name: str, atomic_features: set[str]) -> tuple[str | None, str | None]:
    if "__" not in name:
        return None, None
    source, statistic = name.rsplit("__", 1)
    return (source, statistic) if source in atomic_features and statistic in STATISTICS else (None, None)


def registry_for_columns(columns: list[str], atomic_features: list[str]) -> list[dict[str, Any]]:
    atomic = set(atomic_features)
    registry = []
    for column in columns:
        source, statistic = parse_aggregate_column(column, atomic)
        family = family_for_atomic(source) if source else None
        predictor = family is not None and source not in NON_PREDICTOR_ATOMIC and statistic not in {"count", "eligible_count", "true_count", "positive_count", "negative_count", "zero_count"}
        reason = None
        if column in IDENTITY_COLUMNS:
            reason = "identity_or_technical_metadata"
        elif column in CONFOUNDER_COLUMNS:
            reason = "confounder_metadata"
        elif source in NON_PREDICTOR_ATOMIC:
            reason = "raw_price_level_or_reliability_field"
        elif source is None and column.startswith("interior_"):
            family = "path_efficiency_counter_direction" if any(token in column for token in ("path", "counter", "net", "move", "speed")) else None
            predictor = family is not None and column not in {"interior_path_contiguous"}
        elif source is None and column.startswith(("alternation_indicator", "local_direction", "close_step_sign")):
            family = "alternation_directional_persistence"
            predictor = column.endswith(("true_share", "positive_share", "negative_share", "zero_share"))
        elif source is None and column not in IDENTITY_COLUMNS:
            reason = "non_atomic_or_segment_metadata"
        if predictor and reason is None:
            reason = "candidate_predictor"
        registry.append({
            "aggregate_column": column,
            "atomic_source_feature": source,
            "aggregation_statistic": statistic,
            "feature_family": family or "metadata_or_deferred",
            "predictor_candidate": predictor,
            "selection_reason": reason,
        })
    return registry


def load_source(data_root: Path) -> tuple[list[dict[str, Any]], dict, str]:
    root = data_root / "research/macro_segment_aggregates"
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [Path(item["path"]) for item in manifest["output_files"]]
    for item, path in zip(manifest["output_files"], files):
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Input checksum mismatch: {path}")
    return pq.read_table(files).to_pylist(), manifest, sha256_file(manifest_path)


def normalized_column(row: dict[str, Any], column: str) -> tuple[str, Any, str]:
    """Orient only transforms whose leg-relative semantics are algebraically exact."""
    direction = 1.0 if row["direction"] == "up" else -1.0
    if column.startswith("interior_net_signed_move"):
        return "leg_relative_" + column, _multiply(row[column], direction), "multiply_by_leg_direction"
    if column.startswith("interior_signed_log_move") or column.startswith("interior_speed_signed"):
        return "leg_relative_" + column, _multiply(row[column], direction), "multiply_by_leg_direction"
    if "__" in column:
        source, stat = column.rsplit("__", 1)
        if source in SIGNED_ATOMIC:
            if direction > 0 or stat in {"count", "std"}:
                return "leg_relative_" + column, row[column], "signed_stat_leg_orientation"
            swap = {"min": "max", "max": "min", "p25": "p75", "p75": "p25"}.get(stat, stat)
            original = f"{source}__{swap}"
            return "leg_relative_" + column, _multiply(row.get(original), -1.0), "signed_stat_leg_orientation"
    return column, row[column], "not_required"


def _multiply(value: Any, factor: float) -> Any:
    return None if value is None else float(value) * factor


def add_directional_relative_features(row: dict[str, Any]) -> dict[str, Any]:
    direction_up = row["direction"] == "up"
    out: dict[str, Any] = {}
    for prefix in ("local_direction", "close_step_sign"):
        pos, neg, zero = (f"{prefix}__positive_share", f"{prefix}__negative_share", f"{prefix}__zero_share")
        out[f"leg_relative_{prefix}__forward_share"] = row.get(pos) if direction_up else row.get(neg)
        out[f"leg_relative_{prefix}__counter_share"] = row.get(neg) if direction_up else row.get(pos)
        out[f"leg_relative_{prefix}__zero_share"] = row.get(zero)
    for base in ("volume_body", "volume_close_step"):
        for stat in ("mean", "median", "std", "min", "max", "p25", "p75"):
            up, down = row.get(f"{base}_up__{stat}"), row.get(f"{base}_down__{stat}")
            out[f"leg_relative_{base}_forward__{stat}"] = up if direction_up else down
            out[f"leg_relative_{base}_counter__{stat}"] = down if direction_up else up
    return out


def feature_frame(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], family: str) -> tuple[list[str], dict[str, np.ndarray], list[dict[str, Any]]]:
    candidate_columns = [row["aggregate_column"] for row in candidates if row["predictor_candidate"] and row["feature_family"] == family]
    values: dict[str, np.ndarray] = {}
    normalization_rows = []
    for column in candidate_columns:
        transformed = []
        output_name = None
        mapping = None
        for row in rows:
            name, value, transform = normalized_column(row, column)
            output_name = name
            mapping = transform
            transformed.append(np.nan if value is None else float(value))
        values[output_name] = np.asarray(transformed, dtype=float)
        normalization_rows.append({"original_feature": column, "discovery_feature": output_name, "transform": mapping, "status": "included_candidate"})
    # Add explicit leg-relative directional persistence variables rather than raw up/down shares.
    if family == "alternation_directional_persistence":
        extras = [add_directional_relative_features(row) for row in rows]
        for name in sorted(extras[0]):
            values[name] = np.asarray([np.nan if item[name] is None else float(item[name]) for item in extras], dtype=float)
            normalization_rows.append({"original_feature": "directional_pair_or_volume_components", "discovery_feature": name, "transform": "swap_up_down_by_leg_direction", "status": "included_candidate"})
    return list(values), values, normalization_rows


def clean_compact_matrix(values: dict[str, np.ndarray]) -> tuple[list[str], np.ndarray, np.ndarray, list[dict[str, Any]]]:
    audit = []
    retained: list[str] = []
    for name in sorted(values):
        array = values[name]
        finite = np.isfinite(array)
        coverage = float(finite.mean())
        reason = "retained_pre_redundancy"
        if coverage < CONFIG["minimum_feature_coverage"]:
            reason = "near_empty_coverage"
        elif finite.any() and np.nanstd(array) == 0:
            reason = "constant"
        elif not finite.any():
            reason = "no_finite_values"
        else:
            retained.append(name)
        audit.append({"feature": name, "coverage": coverage, "status": reason})
    if not retained:
        return [], np.empty((0, 0)), np.array([], dtype=bool), audit
    complete_mask = np.all(np.column_stack([np.isfinite(values[name]) for name in retained]), axis=1)
    matrix = np.column_stack([values[name][complete_mask] for name in retained])
    if matrix.shape[0] < CONFIG["minimum_samples"]:
        for entry in audit:
            if entry["feature"] in retained:
                entry["status"] = "excluded_insufficient_complete_cases"
        return [], np.empty((0, 0)), complete_mask, audit
    priority = {"mean": 0, "median": 1, "std": 2, "p75": 3, "p25": 4, "max": 5, "min": 6, "true_share": 7, "forward_share": 8, "counter_share": 9, "zero_share": 10}
    def order(name: str) -> tuple[int, str]:
        suffix = name.rsplit("__", 1)[-1]
        return priority.get(suffix, 99), name
    keep_indices: list[int] = []
    for index in sorted(range(len(retained)), key=lambda i: order(retained[i])):
        candidate = matrix[:, index]
        if not keep_indices:
            keep_indices.append(index)
            continue
        correlations = [abs(np.corrcoef(candidate, matrix[:, existing])[0, 1]) for existing in keep_indices]
        strongest = max(correlations)
        if np.isfinite(strongest) and strongest >= CONFIG["near_duplicate_abs_correlation"]:
            status = "excluded_near_duplicate"
        elif np.isfinite(strongest) and strongest >= CONFIG["high_redundancy_abs_correlation"]:
            status = "excluded_high_correlation"
        else:
            keep_indices.append(index)
            continue
        for entry in audit:
            if entry["feature"] == retained[index]:
                entry["status"] = status
    names = [retained[index] for index in keep_indices]
    matrix = matrix[:, keep_indices]
    return names, matrix, complete_mask, audit


def standardize(matrix: np.ndarray) -> np.ndarray:
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0, ddof=0)
    if np.any(std == 0):
        raise ValueError("constant feature reached standardization")
    return (matrix - mean) / std


def svd_pca(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    standardized = standardize(matrix)
    _, singular, vt = np.linalg.svd(standardized, full_matrices=False)
    variance = singular ** 2 / max(standardized.shape[0] - 1, 1)
    share = variance / variance.sum()
    scores = standardized @ vt.T
    return standardized, scores, vt, share


def pca_summary(matrix: np.ndarray, names: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray]:
    _, scores, vt, share = svd_pca(matrix)
    components = min(5, len(share))
    summary = {f"pc{index + 1}_explained_variance": float(share[index]) for index in range(components)}
    summary["pc1_pc2_explained_variance"] = float(share[: min(2, len(share))].sum())
    loadings = []
    for component in range(components):
        for feature_index, feature in enumerate(names):
            loadings.append({"component": component + 1, "feature": feature, "loading": float(vt[component, feature_index])})
    return summary, loadings, scores[:, :components]


def distance_matrix(matrix: np.ndarray) -> np.ndarray:
    square = np.sum(matrix * matrix, axis=1, keepdims=True)
    return np.sqrt(np.maximum(square + square.T - 2 * matrix @ matrix.T, 0.0))


def hopkins(matrix: np.ndarray, seed: int) -> float:
    rng = np.random.default_rng(seed)
    n = len(matrix)
    m = min(20, n // 2)
    if m < 2:
        return float("nan")
    chosen = rng.choice(n, m, replace=False)
    observed = matrix[chosen]
    lower, upper = matrix.min(axis=0), matrix.max(axis=0)
    uniform = rng.uniform(lower, upper, size=(m, matrix.shape[1]))
    dist = distance_matrix(matrix)
    observed_nn = np.array([np.min(np.delete(dist[index], index)) for index in chosen])
    uniform_nn = np.array([np.min(np.sqrt(np.sum((matrix - point) ** 2, axis=1))) for point in uniform])
    return float(uniform_nn.sum() / (uniform_nn.sum() + observed_nn.sum()))


def kmeans(matrix: np.ndarray, k: int, seed: int, iterations: int = 100) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(matrix)
    centers = matrix[rng.choice(n, k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(iterations):
        distances = np.sum((matrix[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        next_labels = np.argmin(distances, axis=1)
        next_centers = centers.copy()
        for cluster in range(k):
            members = matrix[next_labels == cluster]
            next_centers[cluster] = members.mean(axis=0) if len(members) else matrix[rng.integers(n)]
        if np.array_equal(labels, next_labels):
            break
        labels, centers = next_labels, next_centers
    return labels, centers


def silhouette(matrix: np.ndarray, labels: np.ndarray) -> float:
    distances = distance_matrix(matrix)
    scores = []
    for index, label in enumerate(labels):
        own = np.where(labels == label)[0]
        if len(own) <= 1:
            scores.append(0.0)
            continue
        a = distances[index, own[own != index]].mean()
        b = min(distances[index, labels == other].mean() for other in set(labels) if other != label)
        scores.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return float(np.mean(scores))


def adjusted_rand_index(left: np.ndarray, right: np.ndarray) -> float:
    n = len(left)
    if n < 2:
        return 1.0
    contingency: dict[tuple[int, int], int] = {}
    for a, b in zip(left, right):
        contingency[(int(a), int(b))] = contingency.get((int(a), int(b)), 0) + 1
    choose2 = lambda x: x * (x - 1) / 2
    sum_comb = sum(choose2(value) for value in contingency.values())
    a_counts = [sum(value for (a, _), value in contingency.items() if a == group) for group in set(left)]
    b_counts = [sum(value for (_, b), value in contingency.items() if b == group) for group in set(right)]
    a_comb, b_comb, total = sum(map(choose2, a_counts)), sum(map(choose2, b_counts)), choose2(n)
    expected = a_comb * b_comb / total if total else 0.0
    maximum = (a_comb + b_comb) / 2
    return 1.0 if maximum == expected else float((sum_comb - expected) / (maximum - expected))


def stability(matrix: np.ndarray, labels: np.ndarray, k: int, seed: int) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n, p = matrix.shape
    repeats = CONFIG["stability_repetitions"]
    co_same = np.zeros((n, n), dtype=float)
    co_seen = np.zeros((n, n), dtype=float)
    observation_scores: list[list[float]] = [[] for _ in range(n)]
    aris = []
    completed = 0
    attempts = 0
    # A globally usable feature can be constant in one subsample. Draw the
    # feature subset after observing sampled rows, avoiding zero-variance fits.
    while completed < repeats:
        attempts += 1
        if attempts > repeats * 10:
            raise RuntimeError("Could not draw enough non-constant stability subsamples")
        sample_size = max(k + 1, int(math.floor(n * CONFIG["stability_subsample_fraction"])))
        requested_feature_size = max(2, int(math.floor(p * CONFIG["stability_feature_fraction"])))
        sample = np.sort(rng.choice(n, sample_size, replace=False))
        available = np.flatnonzero(np.std(matrix[sample], axis=0, ddof=0) > 0)
        if len(available) < 2:
            continue
        features = np.sort(rng.choice(available, min(requested_feature_size, len(available)), replace=False))
        subset = standardize(matrix[sample][:, features])
        trial, _ = kmeans(subset, k, seed + completed + 1)
        base = labels[sample]
        aris.append(adjusted_rand_index(base, trial))
        base_same = base[:, None] == base[None, :]
        trial_same = trial[:, None] == trial[None, :]
        indices = np.ix_(sample, sample)
        co_seen[indices] += 1
        co_same[indices] += trial_same
        for local, global_index in enumerate(sample):
            peers = np.arange(sample_size) != local
            observation_scores[global_index].append(float((base_same[local, peers] == trial_same[local, peers]).mean()))
        completed += 1
    coassignment = np.divide(co_same, co_seen, out=np.full_like(co_same, np.nan), where=co_seen > 0)
    per_leg = np.array([np.mean(values) if values else np.nan for values in observation_scores])
    return {
        "stability_mean_ari": float(np.mean(aris)),
        "stability_min_ari": float(np.min(aris)),
        "stability_max_ari": float(np.max(aris)),
        "repetitions": completed,
        "sampling_attempts": attempts,
    }, coassignment, per_leg


def clusterability(matrix: np.ndarray, seed: int) -> tuple[dict[str, Any], dict[int, tuple[np.ndarray, float]]]:
    standardized = standardize(matrix)
    diagnostics = {"hopkins": hopkins(standardized, seed)}
    distance = distance_matrix(standardized)
    nearest = np.array([np.min(np.delete(row, index)) for index, row in enumerate(distance)])
    diagnostics.update({"distance_median": float(np.median(distance[np.triu_indices(len(distance), 1)])), "nearest_neighbor_median": float(np.median(nearest))})
    candidates = {}
    for k in CONFIG["candidate_k"]:
        if k >= len(matrix):
            continue
        labels, _ = kmeans(standardized, k, seed + k)
        score = silhouette(standardized, labels)
        candidates[k] = (labels, score)
        diagnostics[f"silhouette_k{k}"] = score
    best = max((score for _, score in candidates.values()), default=float("nan"))
    diagnostics["best_provisional_silhouette"] = best
    h = diagnostics["hopkins"]
    if h >= CONFIG["clusterability_hopkins_supported"] and best >= CONFIG["clusterability_silhouette_supported"]:
        status = "supported"
    elif h >= CONFIG["clusterability_hopkins_weak"] or best >= CONFIG["clusterability_silhouette_weak"]:
        status = "weak"
    else:
        status = "unsupported"
    diagnostics["status"] = status
    return diagnostics, candidates


@dataclass
class FamilyResult:
    resolution: str
    family: str
    segment_ids: list[str]
    feature_names: list[str]
    complete_mask: np.ndarray
    diagnostics: dict[str, Any]
    pca_summary: dict[str, Any]
    pca_loadings: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    coassignments: list[tuple[str, np.ndarray, list[str]]]
    cleaned_audit: list[dict[str, Any]]


def analyze_family(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], resolution: str, family: str) -> FamilyResult:
    names, values, normalization = feature_frame(rows, candidates, family)
    clean_names, matrix, complete_mask, audit = clean_compact_matrix(values)
    for entry in audit:
        entry.update({"resolution": resolution, "family": family})
    if not clean_names:
        diagnostics = {"status": "unsupported", "reason": "insufficient_usable_features_or_complete_cases", "samples": 0, "features": 0}
        return FamilyResult(resolution, family, [], [], complete_mask, diagnostics, {}, [], [], [], audit)
    pca, loadings, _ = pca_summary(matrix, clean_names)
    diagnostics, provisional = clusterability(matrix, stable_seed(resolution, family))
    diagnostics.update({"samples": int(matrix.shape[0]), "features": int(matrix.shape[1])})
    segment_ids = [rows[index]["segment_id"] for index in np.where(complete_mask)[0]]
    candidate_rows, coassignments = [], []
    if diagnostics["status"] == "supported":
        for k, (labels, score) in provisional.items():
            metrics, coassignment, per_leg = stability(matrix, labels, k, stable_seed(resolution, family, str(k), offset=1000 * k))
            justified = score >= CONFIG["clusterability_silhouette_supported"] and metrics["stability_mean_ari"] >= CONFIG["stability_minimum_ari"]
            for segment_id, label, stability_score in zip(segment_ids, labels, per_leg):
                candidate_rows.append({"resolution": resolution, "family": family, "k": k, "segment_id": segment_id, "cluster": int(label), "silhouette": score, "membership_stability": None if math.isnan(stability_score) else float(stability_score), "justified": justified})
            if justified:
                coassignments.append((f"coassignment_{resolution}_{family}_k{k}", coassignment, segment_ids))
            metrics.update({"resolution": resolution, "family": family, "k": k, "silhouette": score, "justified": justified})
            diagnostics.setdefault("stability", []).append(metrics)
    return FamilyResult(resolution, family, segment_ids, clean_names, complete_mask, diagnostics, pca, loadings, candidate_rows, coassignments, audit)


def result_signature(result: FamilyResult) -> str:
    payload = {
        "feature_names": result.feature_names,
        "diagnostics": result.diagnostics,
        "candidates": result.candidates,
    }
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def rank_array(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks


def correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    mask = np.isfinite(left) & np.isfinite(right)
    if mask.sum() < 3 or np.std(left[mask]) == 0 or np.std(right[mask]) == 0:
        return None
    return float(np.corrcoef(rank_array(left[mask]), rank_array(right[mask]))[0, 1])


def confounder_report(rows: list[dict[str, Any]], family_results: list[FamilyResult], resolution: str) -> list[dict[str, Any]]:
    usable = [result for result in family_results if result.resolution == resolution and result.feature_names]
    if not usable:
        return []
    # A compact global PCA for audit only; family predictors remain separate for discovery.
    common = np.ones(len(rows), dtype=bool)
    for result in usable:
        common &= result.complete_mask
    selected = np.where(common)[0]
    if len(selected) < CONFIG["minimum_samples"]:
        return [{"resolution": resolution, "status": "insufficient_common_complete_cases", "samples": int(len(selected))}]
    # Derive PCA from the retained feature values kept in diagnostics-independent matrices.
    # Rebuild family value maps using the recorded names to avoid any metadata columns.
    matrix_parts = []
    for result in usable:
        all_names, values, _ = feature_frame(rows, _CANDIDATES_BY_RESOLUTION[resolution], result.family)
        matrix_parts.append(np.column_stack([values[name][selected] for name in result.feature_names]))
    matrix = np.column_stack(matrix_parts)
    _, _, scores = pca_summary(matrix, [f"f{index}" for index in range(matrix.shape[1])])
    confounders = {
        "direction": np.asarray([1.0 if rows[index]["direction"] == "up" else -1.0 for index in selected]),
        "duration_hours": np.asarray([float(rows[index]["source_duration_hours"]) for index in selected]),
        "absolute_log_move": np.asarray([abs(float(rows[index]["source_log_move"])) for index in selected]),
        "candle_count": np.asarray([float(rows[index]["complete_candle_count"]) for index in selected]),
        "eligible_pair_count": np.asarray([float(rows[index]["eligible_pair_count"]) for index in selected]),
        "historical_period": np.asarray([rows[index]["segment_start"].timestamp() for index in selected]),
        "atr14_wilder_proxy": np.asarray([np.nan if rows[index].get("atr14_wilder__mean") is None else float(rows[index]["atr14_wilder__mean"]) for index in selected]),
    }
    report = []
    for axis in range(min(3, scores.shape[1])):
        for name, values in confounders.items():
            report.append({"resolution": resolution, "axis": f"PC{axis + 1}", "confounder": name, "spearman_correlation": correlation(scores[:, axis], values), "samples": len(selected)})
    return report


def reliability_report(assignments: list[dict[str, Any]], reliability: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit whether solution instability tracks duration or observation counts."""
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in assignments:
        if row["justified"] and row["membership_stability"] is not None:
            grouped.setdefault((row["segment_id"], row["resolution"]), []).append(float(row["membership_stability"]))
    per_leg = []
    for row in reliability:
        values = grouped.get((row["segment_id"], row["resolution"]), [])
        if values:
            mean_stability = float(np.mean(values))
            per_leg.append({**row, "mean_membership_stability": mean_stability, "instability": float(1 - mean_stability), "supporting_solutions": len(values)})
    report = []
    for resolution in RESOLUTIONS:
        subset = [row for row in per_leg if row["resolution"] == resolution]
        instability = np.asarray([row["instability"] for row in subset], dtype=float)
        for field in ("source_duration_hours", "candle_count", "eligible_pair_count"):
            report.append({"resolution": resolution, "metric": "instability", "against": field, "spearman_correlation": correlation(instability, np.asarray([row[field] for row in subset], dtype=float)), "samples": len(subset), "status": "assessed" if len(subset) >= 3 else "no_justified_stable_solution"})
    return report, per_leg


_CANDIDATES_BY_RESOLUTION: dict[str, list[dict[str, Any]]] = {}


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd", compression_level=9)


def build(data_root: Path, repo_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    rows, source_manifest, source_sha = load_source(data_root)
    columns = list(rows[0])
    registry = registry_for_columns(columns, source_manifest["numeric_atomic_features_aggregated"])
    by_resolution = {resolution: [row for row in rows if row["resolution"] == resolution] for resolution in RESOLUTIONS}
    if any(len(by_resolution[resolution]) != 79 for resolution in RESOLUTIONS):
        raise ValueError("Expected exactly 79 segments per resolution")
    global _CANDIDATES_BY_RESOLUTION
    _CANDIDATES_BY_RESOLUTION = {resolution: registry for resolution in RESOLUTIONS}
    output_root = data_root / "research/macro_structure_stage1"
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing stage output: {output_root}")
    temp_root = output_root.parent / f".{output_root.name}.build-{uuid.uuid4().hex}"
    temp_root.mkdir(parents=True)
    try:
        build_started = time.perf_counter()
        normalization_rows = []
        cleaned_rows = []
        pca_rows = []
        diagnostics_rows = []
        assignments = []
        stability_rows = []
        reliability = []
        all_results: list[FamilyResult] = []
        coassignment_items: list[tuple[str, np.ndarray, list[str]]] = []
        for resolution in RESOLUTIONS:
            tf_rows = by_resolution[resolution]
            for row in tf_rows:
                reliability.append({"segment_id": row["segment_id"], "resolution": resolution, "source_duration_hours": row["source_duration_hours"], "candle_count": row["complete_candle_count"], "eligible_pair_count": row["eligible_pair_count"], "atomic_row_count": row["atomic_row_count"]})
            for family in FAMILIES:
                _, _, mapping = feature_frame(tf_rows, registry, family)
                normalization_rows.extend([{**entry, "resolution": resolution, "family": family} for entry in mapping])
                result = analyze_family(tf_rows, registry, resolution, family)
                all_results.append(result)
                cleaned_rows.extend(result.cleaned_audit)
                diagnostics_rows.append({"resolution": resolution, "family": family, **result.diagnostics, **result.pca_summary})
                pca_rows.extend([{"resolution": resolution, "family": family, **entry} for entry in result.pca_loadings])
                assignments.extend(result.candidates)
                stability_rows.extend(result.diagnostics.get("stability", []))
                coassignment_items.extend(result.coassignments)
        for entry in registry:
            if not entry["predictor_candidate"]:
                normalization_rows.append({
                    "resolution": "all",
                    "family": entry["feature_family"],
                    "original_feature": entry["aggregate_column"],
                    "discovery_feature": None,
                    "transform": "excluded_from_discovery",
                    "status": entry["selection_reason"],
                })
        # Fixed-seed rerun of the computational core validates reproducibility without rereading inputs.
        deterministic_rerun = True
        for result in all_results:
            rerun = analyze_family(by_resolution[result.resolution], registry, result.resolution, result.family)
            if result_signature(result) != result_signature(rerun):
                deterministic_rerun = False
                break
        confounders = []
        for resolution in RESOLUTIONS:
            confounders.extend(confounder_report(by_resolution[resolution], all_results, resolution))
        build_seconds = time.perf_counter() - build_started

        atomic_csv(temp_root / "feature_registry.csv", registry)
        atomic_csv(temp_root / "direction_normalization_map.csv", normalization_rows)
        atomic_csv(temp_root / "cleaned_feature_lists.csv", cleaned_rows)
        atomic_csv(temp_root / "pca_loadings.csv", pca_rows)
        atomic_csv(temp_root / "clusterability_diagnostics.csv", diagnostics_rows)
        atomic_csv(temp_root / "stability_metrics.csv", stability_rows)
        atomic_csv(temp_root / "confounder_report.csv", confounders)
        write_parquet(temp_root / "reliability_metadata.parquet", reliability)
        write_parquet(temp_root / "candidate_cluster_assignments.parquet", assignments)
        reliability_rows, per_leg_reliability = reliability_report(assignments, reliability)
        atomic_csv(temp_root / "reliability_instability_report.csv", reliability_rows)
        write_parquet(temp_root / "reliability_by_segment.parquet", per_leg_reliability)

        consensus_ids = sorted({row["segment_id"] for row in rows})
        consensus_sum = np.zeros((len(consensus_ids), len(consensus_ids)), dtype=float)
        consensus_count = np.zeros_like(consensus_sum)
        matrix_manifest = []
        for name, matrix, ids in coassignment_items:
            full = np.full_like(consensus_sum, np.nan)
            index = {segment_id: position for position, segment_id in enumerate(consensus_ids)}
            positions = [index[segment_id] for segment_id in ids]
            full[np.ix_(positions, positions)] = matrix
            pair_rows = [{"segment_id_a": consensus_ids[i], "segment_id_b": consensus_ids[j], "coassignment": None if math.isnan(full[i, j]) else float(full[i, j])} for i in range(len(consensus_ids)) for j in range(len(consensus_ids))]
            path = temp_root / f"{name}.parquet"
            write_parquet(path, pair_rows)
            matrix_manifest.append({"name": path.name, "rows": len(pair_rows)})
            valid = np.isfinite(full)
            consensus_sum[valid] += full[valid]
            consensus_count[valid] += 1
        consensus = np.divide(consensus_sum, consensus_count, out=np.full_like(consensus_sum, np.nan), where=consensus_count > 0)
        consensus_rows = [{"segment_id_a": consensus_ids[i], "segment_id_b": consensus_ids[j], "consensus_coassignment": None if math.isnan(consensus[i, j]) else float(consensus[i, j]), "supporting_solutions": int(consensus_count[i, j])} for i in range(len(consensus_ids)) for j in range(len(consensus_ids))]
        write_parquet(temp_root / "cross_tf_consensus.parquet", consensus_rows)
        upper = np.triu_indices(len(consensus_ids), 1)
        upper_values = consensus[upper]
        supported = consensus_count[upper] > 0
        stable_pairs = supported & np.isfinite(upper_values) & ((upper_values >= 0.8) | (upper_values <= 0.2))
        unstable_rows = [row for row in per_leg_reliability if row["mean_membership_stability"] < CONFIG["stability_minimum_ari"]]
        write_parquet(temp_root / "unstable_segment_membership.parquet", unstable_rows)
        atomic_json(temp_root / "cross_tf_consensus_summary.json", {
            "status": "assessed" if coassignment_items else "no_justified_stable_solution",
            "segment_count": len(consensus_ids),
            "stable_pairwise_relations": int(stable_pairs.sum()),
            "pairs_with_solution_support": int(supported.sum()),
            "unstable_segment_resolution_rows": len(unstable_rows),
            "stability_threshold": CONFIG["stability_minimum_ari"],
            "stable_relation_thresholds": {"same_at_least": 0.8, "different_at_most": 0.2},
        })

        qa_started = time.perf_counter()
        predictor_names = {entry["aggregate_column"] for entry in registry if entry["predictor_candidate"]}
        prohibited = IDENTITY_COLUMNS | CONFOUNDER_COLUMNS | {"known_macro_class", "known_macro_class_status"}
        leakage = sorted(predictor_names & prohibited)
        assignment_ids = {(row["segment_id"], row["resolution"], row["family"], row["k"]) for row in assignments}
        qa = {
            "status": "PASS" if not leakage else "FAIL",
            "segments_per_resolution": {resolution: len(by_resolution[resolution]) for resolution in RESOLUTIONS},
            "identity_or_label_predictor_leakage": leakage,
            "candidate_assignment_duplicate_keys": len(assignment_ids) != len(assignments),
            "deterministic_rerun": deterministic_rerun,
            "input_source_sha256": source_sha,
            "fixed_seed": SEED,
        }
        if qa["candidate_assignment_duplicate_keys"]:
            qa["status"] = "FAIL"
        if not qa["deterministic_rerun"]:
            qa["status"] = "FAIL"
        if qa["status"] != "PASS":
            raise RuntimeError(f"Stage 1 QA failed: {qa}")
        qa_seconds = time.perf_counter() - qa_started

        files = []
        for path in sorted(temp_root.iterdir()):
            if path.is_file():
                files.append({"path": str(output_root / path.name), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "build_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_macro_segment_manifest": str(data_root / "research/macro_segment_aggregates/manifest.json"),
            "source_macro_segment_manifest_sha256": source_sha,
            "aggregation_version": source_manifest["aggregation_version"],
            "stage_config": CONFIG,
            "feature_families": list(FAMILIES),
            "labels_used": False,
            "class_like_fields_excluded": ["known_macro_class", "known_macro_class_status"],
            "rows": len(rows),
            "segments": len(consensus_ids),
            "registry_rows": len(registry),
            "qa": qa,
            "deferred": {
                "semantic_cluster_interpretation": "explicitly outside unsupervised Stage 1",
                "semantic_impulse_correction_labels": "no authoritative mapping exists and labels are prohibited in predictors",
                "progress_buckets": "no approved neutral segment-division rule",
            },
            "output_files": files,
            "coassignment_matrices": matrix_manifest,
            "code_version": {"git_commit_at_build": git_commit(repo_root), "pipeline_sha256": sha256_file(Path(__file__))},
        }
        atomic_json(temp_root / "manifest.json", manifest)
        os.replace(temp_root, output_root)
        report = {
            "status": "PASS", "path": str(output_root), "rows": len(rows), "segments": len(consensus_ids),
            "usable_by_tf_family": [{"resolution": result.resolution, "family": result.family, "features": len(result.feature_names), "samples": result.diagnostics.get("samples", 0), "status": result.diagnostics.get("status")} for result in all_results],
            "candidate_assignments": len(assignments), "coassignment_matrices": len(coassignment_items),
            "runtime_seconds": {"build": round(build_seconds, 3), "validation": round(qa_seconds, 3), "total": round(time.perf_counter() - started, 3)},
        }
        atomic_json(data_root / "manifests/macro_structure_stage1_build_report.json", report)
        return report
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def stamp_git_commit(data_root: Path, commit: str) -> None:
    path = data_root / "research/macro_structure_stage1/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["code_version"]["git_commit"] = commit
    atomic_json(path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp-git-commit")
    args = parser.parse_args()
    if args.stamp_git_commit:
        stamp_git_commit(args.data_root, args.stamp_git_commit)
        print(json.dumps({"stamped_git_commit": args.stamp_git_commit}, indent=2))
        return
    print(json.dumps(build(args.data_root, args.repo_root), indent=2))


if __name__ == "__main__":
    main()
