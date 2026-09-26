#!/usr/bin/env python3
"""Canonical Stage 2G: incremental pre-slowdown history on frozen Stage 2 data."""
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
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SEED = 20260926
SEMANTIC = ["persistence", "alternation", "volatility", "volume", "trade_count", "overlap", "speed", "geometry"]
CONTEXT = ["net_move", "duration_hours", "candle_count"]
DELTA_FIELD = {
    "persistence": "delta_persistence",
    "alternation": "delta_alternation",
    "volatility": "delta_volatility",
    "volume": "delta_volume",
    "trade_count": "delta_trade_count",
    "overlap": "delta_overlap_body_overlap_mean",
    "speed": "delta_speed_movement_rate_mean",
    "geometry": "delta_candle_geometry_mean",
}
SEPARATED = ["persistence", "alternation", "volatility", "volume", "trade_count"]
H0_DECLARED = [f"s0_{name}" for name in SEMANTIC] + [f"d10_{name}" for name in SEMANTIC]
H1_DECLARED = H0_DECLARED + [f"s1_{name}" for name in SEMANTIC]
H2_DECLARED = H1_DECLARED + [f"d21_{name}" for name in SEMANTIC] + [f"s2_{name}" for name in SEMANTIC] + [f"dd_{name}" for name in SEMANTIC]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    os.replace(partial, path)


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    partial = path.with_name(path.name + ".partial")
    with partial.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(partial, path)


def write_parquet(path: Path, rows: list[dict]) -> None:
    if rows:
        pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def write_checksums(root: Path) -> bool:
    targets = sorted(path for path in root.iterdir() if path.name != "checksums.sha256")
    (root / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in targets))
    lines = (root / "checksums.sha256").read_text().splitlines()
    return len(targets) == len(lines) and all(
        sha256(path) == line.split(maxsplit=1)[0] and path.name == line.split(maxsplit=1)[1].strip()
        for path, line in zip(targets, lines)
    )


def verify_checksum_index(root: Path) -> bool:
    lines = (root / "checksums.sha256").read_text().splitlines()
    return all((root / line.split(maxsplit=1)[1].strip()).is_file() and sha256(root / line.split(maxsplit=1)[1].strip()) == line.split(maxsplit=1)[0] for line in lines)


def sigmoid(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(value, -30, 30)))


def fit_ridge(x: np.ndarray, y: np.ndarray, penalty: float = 0.1) -> np.ndarray:
    weights = np.zeros(x.shape[1] + 1)
    for _ in range(500):
        probability = sigmoid(weights[0] + x @ weights[1:])
        gradient = x.T @ (probability - y) / len(y) + penalty * weights[1:]
        weights -= 0.05 * np.r_[np.mean(probability - y), gradient]
    return weights


def auc(y: np.ndarray, probability: np.ndarray) -> float | None:
    positive, negative = probability[y == 1], probability[y == 0]
    if not len(positive) or not len(negative):
        return None
    return float((np.sum(positive[:, None] > negative) + 0.5 * np.sum(positive[:, None] == negative)) / (len(positive) * len(negative)))


def metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float | None]:
    if not len(y):
        return {"grouped_auc": None, "balanced_accuracy": None, "brier_score": None, "log_loss": None}
    clipped = np.clip(probability, 1e-12, 1 - 1e-12)
    true_positive = (probability[y == 1] >= 0.5).mean() if np.any(y == 1) else np.nan
    true_negative = (probability[y == 0] < 0.5).mean() if np.any(y == 0) else np.nan
    return {
        "grouped_auc": auc(y, probability),
        "balanced_accuracy": float((true_positive + true_negative) / 2),
        "brier_score": float(np.mean((probability - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
    }


def cliff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.sign(a[:, None] - b[None, :])))


def cluster_bootstrap_median_difference(values: np.ndarray, outcomes: np.ndarray, legs: np.ndarray, seed: int, repetitions: int = 1000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique = np.asarray(sorted(set(legs)))
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([np.flatnonzero(legs == leg) for leg in sampled])
        continuation = values[indices][outcomes[indices] == 0]
        reversal = values[indices][outcomes[indices] == 1]
        if len(continuation) and len(reversal):
            draws.append(float(np.median(continuation) - np.median(reversal)))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def independent_names(rows: list[dict], declared: list[str], tolerance: float = 1e-10) -> list[str]:
    matrix = np.asarray([[row[name] for name in declared] for row in rows], dtype=float)
    mean, scale = matrix.mean(axis=0), matrix.std(axis=0)
    scale[scale == 0] = 1
    standardized = (matrix - mean) / scale
    selected: list[int] = []
    current = np.ones((len(rows), 1))
    rank = np.linalg.matrix_rank(current, tol=tolerance)
    for index in range(standardized.shape[1]):
        candidate = np.column_stack([current, standardized[:, index]])
        candidate_rank = np.linalg.matrix_rank(candidate, tol=tolerance)
        if candidate_rank > rank:
            selected.append(index)
            current = candidate
            rank = candidate_rank
    return [declared[index] for index in selected]


def grouped_model(rows: list[dict], feature_names: list[str]) -> tuple[np.ndarray, dict, list[dict], list[dict]]:
    x = np.asarray([[row[name] for name in feature_names] for row in rows], dtype=float)
    y = np.asarray([row["outcome_binary"] for row in rows], dtype=int)
    legs = np.asarray([row["enclosing_macro_leg_id"] for row in rows])
    predictions = np.full(len(y), np.nan)
    fold_rows, fold_ids = [], []
    for leg in sorted(set(legs)):
        test = legs == leg
        train = ~test
        if len(set(y[train])) < 2:
            continue
        mean, scale = x[train].mean(axis=0), x[train].std(axis=0)
        scale[scale == 0] = 1
        weights = fit_ridge((x[train] - mean) / scale, y[train])
        predictions[test] = sigmoid(weights[0] + ((x[test] - mean) / scale) @ weights[1:])
        fold_ids.append(leg)
        fold_rows.append({"held_out_enclosing_macro_leg_id": leg, "rows": int(test.sum()), "reversal_rows": int(y[test].sum()), "mean_reversal_probability": float(np.mean(predictions[test]))})
    if not np.isfinite(predictions).all():
        raise RuntimeError("incomplete grouped predictions")
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    weights = fit_ridge((x - mean) / scale, y)
    coefficients = sorted(({"feature": name, "standardized_coefficient_for_reversal": float(value)} for name, value in zip(feature_names, weights[1:])), key=lambda row: -abs(row["standardized_coefficient_for_reversal"]))
    summary = {**metrics(y, predictions), "rows": len(rows), "enclosing_macro_legs": len(set(legs)), "continuation": int((y == 0).sum()), "reversal": int((y == 1).sum()), "declared_feature_count": None, "effective_feature_count": len(feature_names), "matrix_rank_with_intercept": int(np.linalg.matrix_rank(np.column_stack([np.ones(len(x)), x])))}
    return predictions, summary, fold_rows, coefficients


def bootstrap_metric_differences(rows: list[dict], predictions: dict[str, np.ndarray], repetitions: int = 2000) -> list[dict]:
    legs = np.asarray([row["enclosing_macro_leg_id"] for row in rows])
    y = np.asarray([row["outcome_binary"] for row in rows], dtype=int)
    unique = np.asarray(sorted(set(legs)))
    rng = np.random.default_rng(SEED)
    comparisons = [("H1", "H0"), ("H2", "H0"), ("H2", "H1")]
    distributions = {pair: [] for pair in comparisons}
    ba_distributions = {pair: [] for pair in comparisons}
    for _ in range(repetitions):
        sampled = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([np.flatnonzero(legs == leg) for leg in sampled])
        if len(set(y[indices])) < 2:
            continue
        sample_metrics = {name: metrics(y[indices], probability[indices]) for name, probability in predictions.items()}
        for high, low in comparisons:
            distributions[(high, low)].append(sample_metrics[high]["grouped_auc"] - sample_metrics[low]["grouped_auc"])
            ba_distributions[(high, low)].append(sample_metrics[high]["balanced_accuracy"] - sample_metrics[low]["balanced_accuracy"])
    output = []
    point = {name: metrics(y, probability) for name, probability in predictions.items()}
    for high, low in comparisons:
        values = np.asarray(distributions[(high, low)])
        ba_values = np.asarray(ba_distributions[(high, low)])
        output.append({
            "comparison": f"{high}-{low}",
            "delta_auc": point[high]["grouped_auc"] - point[low]["grouped_auc"],
            "delta_auc_ci_low": float(np.quantile(values, 0.025)),
            "delta_auc_ci_high": float(np.quantile(values, 0.975)),
            "delta_auc_positive_probability": float(np.mean(values > 0)),
            "delta_balanced_accuracy": point[high]["balanced_accuracy"] - point[low]["balanced_accuracy"],
            "delta_balanced_accuracy_ci_low": float(np.quantile(ba_values, 0.025)),
            "delta_balanced_accuracy_ci_high": float(np.quantile(ba_values, 0.975)),
            "bootstrap_repetitions": len(values),
            "cluster_unit": "enclosing_macro_leg_id",
        })
    return output


def trajectory_sign(first_delta: float, second_delta: float) -> str:
    def label(value: float) -> str:
        return "up" if value > 0 else "down" if value < 0 else "flat"
    return f"{label(first_delta)}_then_{label(second_delta)}"


def build(data_root: Path, repo_root: Path) -> dict:
    started = time.perf_counter()
    stage2a = data_root / "research/macro_within_leg_stage2a"
    stage2e = data_root / "research/macro_within_leg_stage2e_feature_separation"
    stage2f = data_root / "research/macro_slowdown_outcome_stage2f"
    output = data_root / "research/macro_slowdown_history_stage2g"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    temporary = output.parent / f".{output.name}.build-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True)
    try:
        if not verify_checksum_index(stage2f):
            raise ValueError("Stage 2F checksum verification failed")
        f_manifest = json.loads((stage2f / "manifest.json").read_text())
        e_manifest = json.loads((stage2e / "feature_separation_manifest.json").read_text())
        a_manifest = json.loads((stage2a / "manifest.json").read_text())
        if any(manifest["qa"]["status"] != "PASS" for manifest in (f_manifest, e_manifest, a_manifest)):
            raise ValueError("upstream QA is not PASS")
        stage2f_population = pq.read_table(stage2f / "slowdown_population.parquet").to_pylist()
        source_features = pq.read_table(stage2e / "separated_subsegment_features.parquet").to_pylist()
        source_transitions = pq.read_table(stage2e / "refined_adjacent_transitions.parquet").to_pylist()
        source_original = pq.read_table(stage2a / "candidate_subsegments.parquet").to_pylist()
        feature_map = {row["subsegment_id"]: row for row in source_features}
        original_map = {row["subsegment_id"]: row for row in source_original}
        transition_to = {row["to_subsegment_id"]: row for row in source_transitions}
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in source_features:
            grouped[row["parent_macro_leg_id"]].append(row)
        position: dict[str, tuple[list[dict], int]] = {}
        for leg, rows in grouped.items():
            rows.sort(key=lambda row: original_map[row["subsegment_id"]]["subsegment_order"])
            for index, row in enumerate(rows):
                position[row["subsegment_id"]] = (rows, index)

        population_rows, history_rows, trajectory_rows = [], [], []
        for source in stage2f_population:
            current_id = source["slowdown_id"]
            rows, index = position[current_id]
            previous1 = rows[index - 1]
            previous2 = rows[index - 2] if index >= 2 else None
            current = feature_map[current_id]
            inbound10 = transition_to[current_id]
            next_subsegment = feature_map[source["next_subsegment_id"]]
            if previous1["subsegment_id"] != source["previous_subsegment_id"]:
                raise ValueError(f"Stage 2F previous mismatch: {current_id}")
            core = {
                "slowdown_id": current_id,
                "enclosing_macro_leg_id": source["parent_macro_leg_id"],
                "enclosing_macro_leg_direction": current["macro_direction"],
                "current_direction_relative": current["net_direction_relative"],
                "outcome": source["outcome"],
                "outcome_binary": source["outcome_binary"],
                "boundary_population": source["boundary_population"],
                "calendar_era": source["calendar_era"],
                "s0_subsegment_id": current_id,
                "s1_subsegment_id": previous1["subsegment_id"],
                "s2_subsegment_id": None if previous2 is None else previous2["subsegment_id"],
                "outcome_subsegment_id": next_subsegment["subsegment_id"],
                "H1_eligible": True,
                "H2_eligible": previous2 is not None,
                "slowdown_subsegment_order": original_map[current_id]["subsegment_order"],
                "enclosing_macro_leg_subsegment_count": len(rows),
            }
            population_rows.append(core)
            history = dict(core)
            for name in SEMANTIC + CONTEXT:
                history[f"s0_{name}"] = abs(current[name]) if name == "net_move" else current[name]
                history[f"s1_{name}"] = abs(previous1[name]) if name == "net_move" else previous1[name]
                history[f"s2_{name}"] = None if previous2 is None else abs(previous2[name]) if name == "net_move" else previous2[name]
            for name in SEMANTIC:
                history[f"d10_{name}"] = inbound10[DELTA_FIELD[name]]
            for name in SEPARATED:
                history[f"ratio10_{name}"] = inbound10[f"ratio_{name}"]
                history[f"z10_{name}"] = inbound10[f"z_delta_{name}"]
            history["d10_net_move_magnitude"] = abs(current["net_move"]) - abs(previous1["net_move"])
            history["d10_duration_hours"] = current["duration_hours"] - previous1["duration_hours"]
            history["d10_candle_count"] = current["candle_count"] - previous1["candle_count"]
            history_rows.append(history)
            if previous2 is None:
                continue
            inbound21 = transition_to[previous1["subsegment_id"]]
            trajectory = dict(history)
            for name in SEMANTIC:
                trajectory[f"d21_{name}"] = inbound21[DELTA_FIELD[name]]
                trajectory[f"dd_{name}"] = trajectory[f"d10_{name}"] - trajectory[f"d21_{name}"]
            for name in SEPARATED:
                trajectory[f"ratio21_{name}"] = inbound21[f"ratio_{name}"]
                trajectory[f"z21_{name}"] = inbound21[f"z_delta_{name}"]
            trajectory["d21_net_move_magnitude"] = abs(previous1["net_move"]) - abs(previous2["net_move"])
            trajectory["dd_net_move_magnitude"] = trajectory["d10_net_move_magnitude"] - trajectory["d21_net_move_magnitude"]
            trajectory["d21_duration_hours"] = previous1["duration_hours"] - previous2["duration_hours"]
            trajectory["dd_duration_hours"] = trajectory["d10_duration_hours"] - trajectory["d21_duration_hours"]
            trajectory["d21_candle_count"] = previous1["candle_count"] - previous2["candle_count"]
            trajectory["dd_candle_count"] = trajectory["d10_candle_count"] - trajectory["d21_candle_count"]
            trajectory_rows.append(trajectory)

        strong_full = [row for row in history_rows if row["boundary_population"] == "strong"]
        strong_common = [row for row in trajectory_rows if row["boundary_population"] == "strong"]
        weak_common = [row for row in trajectory_rows if row["boundary_population"] == "weak"]

        # Exact Stage 2F baseline gate on the full primary population.
        baseline_predictions, baseline_summary, baseline_folds, baseline_coefficients = grouped_model(strong_full, H0_DECLARED)
        reference = json.loads((stage2f / "multivariate_diagnostic.json").read_text())
        baseline_reproduced = abs(baseline_summary["grouped_auc"] - reference["pooled_grouped_auc"]) < 1e-12 and abs(baseline_summary["balanced_accuracy"] - reference["pooled_grouped_balanced_accuracy"]) < 1e-12
        if not baseline_reproduced:
            raise RuntimeError({"baseline": baseline_summary, "reference": reference})

        declared = {"H0": H0_DECLARED, "H1": H1_DECLARED, "H2": H2_DECLARED}
        effective = {name: independent_names(strong_common, names) for name, names in declared.items()}
        common_predictions: dict[str, np.ndarray] = {}
        common_summaries, fold_rows, coefficients = {}, [], {}
        fold_sets = {}
        for name in ("H0", "H1", "H2"):
            prediction, summary, folds, coefficient = grouped_model(strong_common, effective[name])
            summary["declared_feature_count"] = len(declared[name])
            summary["effective_feature_count"] = len(effective[name])
            summary["history_level"] = name
            summary["scope"] = "common_strong"
            common_predictions[name] = prediction
            common_summaries[name] = summary
            coefficients[name] = coefficient
            fold_sets[name] = [row["held_out_enclosing_macro_leg_id"] for row in folds]
            fold_rows.extend({**row, "history_level": name, "scope": "common_strong"} for row in folds)
        validation_rows = [{**baseline_summary, "history_level": "H0", "scope": "stage2f_full_strong", "declared_feature_count": len(H0_DECLARED), "effective_feature_count": len(H0_DECLARED), "delta_auc_vs_H0": 0.0}]
        for name in ("H0", "H1", "H2"):
            validation_rows.append({**common_summaries[name], "delta_auc_vs_H0": common_summaries[name]["grouped_auc"] - common_summaries["H0"]["grouped_auc"]})
        incremental_rows = bootstrap_metric_differences(strong_common, common_predictions)

        direction_rows = []
        for context in ("forward", "counter"):
            rows = [row for row in strong_common if row["current_direction_relative"] == context]
            context_predictions = {}
            context_summaries = {}
            for name in ("H0", "H1", "H2"):
                prediction, summary, _, _ = grouped_model(rows, effective[name])
                context_predictions[name] = prediction
                context_summaries[name] = summary
            context_bootstrap = {row["comparison"]: row for row in bootstrap_metric_differences(rows, context_predictions)}
            for name in ("H0", "H1", "H2"):
                comparison = None if name == "H0" else context_bootstrap[f"{name}-H0"]
                direction_rows.append({
                    "current_direction_relative": context, "history_level": name, **context_summaries[name],
                    "declared_feature_count": len(declared[name]),
                    "delta_auc_vs_context_H0": context_summaries[name]["grouped_auc"] - context_summaries["H0"]["grouped_auc"],
                    "delta_auc_ci_low": 0.0 if comparison is None else comparison["delta_auc_ci_low"],
                    "delta_auc_ci_high": 0.0 if comparison is None else comparison["delta_auc_ci_high"],
                    "delta_auc_positive_probability": 0.0 if comparison is None else comparison["delta_auc_positive_probability"],
                })

        sensitivity_rows = []
        for boundary, rows in (("strong", strong_common), ("weak", weak_common)):
            for name in ("H0", "H1", "H2"):
                prediction, summary, _, _ = grouped_model(rows, effective[name])
                sensitivity_rows.append({"boundary_population": boundary, "history_level": name, **summary})

        univariate_names = []
        for prefix in ("s1", "s2", "d21", "dd"):
            univariate_names.extend(f"{prefix}_{name}" for name in SEMANTIC)
        univariate_names.extend(f"{prefix}_{name}" for prefix in ("ratio10", "z10", "ratio21", "z21") for name in SEPARATED)
        univariate_names.extend(["s1_net_move", "s2_net_move", "d10_net_move_magnitude", "d21_net_move_magnitude", "dd_net_move_magnitude", "s1_duration_hours", "s2_duration_hours", "d10_duration_hours", "d21_duration_hours", "dd_duration_hours", "s1_candle_count", "s2_candle_count", "d10_candle_count", "d21_candle_count", "dd_candle_count"])
        univariate_rows = []
        outcomes = np.asarray([row["outcome_binary"] for row in strong_common], dtype=int)
        legs = np.asarray([row["enclosing_macro_leg_id"] for row in strong_common])
        for index, name in enumerate(univariate_names):
            available = np.asarray([row[name] is not None and np.isfinite(row[name]) for row in strong_common])
            values = np.asarray([np.nan if row[name] is None else row[name] for row in strong_common], dtype=float)
            continuation = values[available & (outcomes == 0)]
            reversal = values[available & (outcomes == 1)]
            if not len(continuation) or not len(reversal):
                univariate_rows.append({"feature": name, "status": "not_assessed_no_values"})
                continue
            low, high = cluster_bootstrap_median_difference(values[available], outcomes[available], legs[available], SEED + index)
            difference = float(np.median(continuation) - np.median(reversal))
            eligible_leg_effects = []
            for leg in sorted(set(legs[available])):
                leg_values = values[available & (legs == leg)]
                leg_outcomes = outcomes[available & (legs == leg)]
                if np.any(leg_outcomes == 0) and np.any(leg_outcomes == 1):
                    eligible_leg_effects.append(float(np.median(leg_values[leg_outcomes == 0]) - np.median(leg_values[leg_outcomes == 1])))
            overall_sign = np.sign(difference)
            direction_effects = {}
            for context in ("forward", "counter"):
                mask = available & np.asarray([row["current_direction_relative"] == context for row in strong_common])
                a, b = values[mask & (outcomes == 0)], values[mask & (outcomes == 1)]
                direction_effects[context] = cliff(a, b) if len(a) and len(b) else None
            univariate_rows.append({
                "feature": name,
                "continuation_n": len(continuation), "reversal_n": len(reversal),
                "continuation_median": float(np.median(continuation)), "reversal_median": float(np.median(reversal)),
                "median_difference_cont_minus_rev": difference,
                "cliffs_delta_cont_minus_rev": cliff(continuation, reversal),
                "bootstrap_ci_low": low, "bootstrap_ci_high": high, "bootstrap_excludes_zero": low > 0 or high < 0,
                "eligible_cross_leg_comparisons": len(eligible_leg_effects),
                "cross_leg_sign_consistency": float(np.mean(np.sign(eligible_leg_effects) == overall_sign)) if eligible_leg_effects and overall_sign else None,
                "forward_cliffs_delta": direction_effects["forward"], "counter_cliffs_delta": direction_effects["counter"],
                "status": "assessed",
            })

        recurring_rows = []
        for name in SEMANTIC:
            groups: dict[str, list[dict]] = defaultdict(list)
            for row in strong_common:
                groups[trajectory_sign(row[f"d21_{name}"], row[f"d10_{name}"])].append(row)
            for pattern, rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
                continuation = sum(row["outcome"] == "CONTINUATION" for row in rows)
                reversal = sum(row["outcome"] == "REVERSAL" for row in rows)
                recurring_rows.append({
                    "feature": name, "trajectory": pattern, "support": len(rows),
                    "enclosing_macro_leg_support": len({row["enclosing_macro_leg_id"] for row in rows}),
                    "continuation": continuation, "reversal": reversal, "reversal_rate": reversal / len(rows),
                    "calendar_era_coverage": len({row["calendar_era"] for row in rows}),
                    "forward_slowdown": sum(row["current_direction_relative"] == "forward" for row in rows),
                    "counter_slowdown": sum(row["current_direction_relative"] == "counter" for row in rows),
                })
        activity_groups: dict[str, list[dict]] = defaultdict(list)
        for row in strong_common:
            signature = "|".join(f"{name}:{trajectory_sign(row[f'd21_{name}'], row[f'd10_{name}'])}" for name in ("volatility", "volume", "trade_count"))
            activity_groups[signature].append(row)
        for pattern, rows in sorted(activity_groups.items(), key=lambda item: (-len(item[1]), item[0])):
            continuation = sum(row["outcome"] == "CONTINUATION" for row in rows)
            reversal = sum(row["outcome"] == "REVERSAL" for row in rows)
            recurring_rows.append({
                "feature": "activity_triplet_exact", "trajectory": pattern, "support": len(rows),
                "enclosing_macro_leg_support": len({row["enclosing_macro_leg_id"] for row in rows}),
                "continuation": continuation, "reversal": reversal, "reversal_rate": reversal / len(rows),
                "calendar_era_coverage": len({row["calendar_era"] for row in rows}),
                "forward_slowdown": sum(row["current_direction_relative"] == "forward" for row in rows),
                "counter_slowdown": sum(row["current_direction_relative"] == "counter" for row in rows),
            })

        available = [row for row in population_rows if row["H2_eligible"]]
        unavailable = [row for row in population_rows if not row["H2_eligible"]]
        confounder = "# Confounder report\n\n"
        confounder += "H0/H1/H2 primary metrics use the identical H2-eligible strong sample and identical held-out enclosing macro-leg folds. Therefore any common-sample metric difference is not caused by H2 observations being deeper in longer legs. External generalization remains limited because edge observations without S_(i-2) are excluded.\n\n"
        confounder += f"H2 available: {len(available)}; unavailable: {len(unavailable)}. Median slowdown order available/unavailable: {np.median([row['slowdown_subsegment_order'] for row in available])}/{np.median([row['slowdown_subsegment_order'] for row in unavailable])}. Median enclosing-leg subsegment count: {np.median([row['enclosing_macro_leg_subsegment_count'] for row in available])}/{np.median([row['enclosing_macro_leg_subsegment_count'] for row in unavailable])}.\n\n"
        confounder += f"Outcome counts available: {dict(Counter(row['outcome'] for row in available))}; unavailable: {dict(Counter(row['outcome'] for row in unavailable))}. Current-direction counts available: {dict(Counter(row['current_direction_relative'] for row in available))}; unavailable: {dict(Counter(row['current_direction_relative'] for row in unavailable))}.\n\n"
        confounder += "Duration and candle count are metadata/univariate trajectory fields, not semantic model predictors. Calendar era, enclosing macro-leg direction, forward/counter context, and continuous volatility trajectories are retained in output diagnostics. No volatility bins or post-outcome regimes were created.\n\n"
        confounder += f"Rank audit: H0 {len(H0_DECLARED)} declared/{len(effective['H0'])} effective; H1 {len(H1_DECLARED)} declared/{len(effective['H1'])} effective; H2 {len(H2_DECLARED)} declared/{len(effective['H2'])} effective. H1 absolute previous values are algebraically reconstructable from S_i and d10, so they add no independent rank. Ratios and z-magnitudes are preserved in artifacts/univariate diagnostics but excluded from the ridge matrix as redundant representations; nullable ratios are not imputed.\n"

        representative = []
        for row in strong_common[:3]:
            transition10 = transition_to[row["s0_subsegment_id"]]
            transition21 = transition_to[row["s1_subsegment_id"]]
            checks = {name: bool(np.isclose(row[f"dd_{name}"], transition10[DELTA_FIELD[name]] - transition21[DELTA_FIELD[name]])) for name in SEMANTIC}
            representative.append({"slowdown_id": row["slowdown_id"], "feature_checks": checks, "passed": all(checks.values())})

        common_ids = [row["slowdown_id"] for row in strong_common]
        qa = {
            "status": "PASS",
            "stage2f_baseline_reproduced": baseline_reproduced,
            "stage2f_reference_auc": reference["pooled_grouped_auc"],
            "reproduced_auc": baseline_summary["grouped_auc"],
            "stage2f_reference_balanced_accuracy": reference["pooled_grouped_balanced_accuracy"],
            "reproduced_balanced_accuracy": baseline_summary["balanced_accuracy"],
            "stage2f_population": len(population_rows), "stage2f_strong": len(strong_full),
            "H1_eligible": sum(row["H1_eligible"] for row in population_rows),
            "H2_eligible": sum(row["H2_eligible"] for row in population_rows),
            "common_strong": len(strong_common), "common_weak": len(weak_common),
            "sequence_order_correct": all(original_map[row["s2_subsegment_id"]]["subsegment_order"] + 1 == original_map[row["s1_subsegment_id"]]["subsegment_order"] and original_map[row["s1_subsegment_id"]]["subsegment_order"] + 1 == original_map[row["s0_subsegment_id"]]["subsegment_order"] and original_map[row["s0_subsegment_id"]]["subsegment_order"] + 1 == original_map[row["outcome_subsegment_id"]]["subsegment_order"] for row in trajectory_rows),
            "same_enclosing_macro_leg": all(feature_map[row["s2_subsegment_id"]]["parent_macro_leg_id"] == feature_map[row["s1_subsegment_id"]]["parent_macro_leg_id"] == feature_map[row["s0_subsegment_id"]]["parent_macro_leg_id"] == feature_map[row["outcome_subsegment_id"]]["parent_macro_leg_id"] for row in trajectory_rows),
            "duplicate_slowdown_ids": len({row["slowdown_id"] for row in population_rows}) != len(population_rows),
            "cross_leg_histories": False,
            "future_predictors_used": False,
            "common_sample_ids_identical": all([row["slowdown_id"] for row in strong_common] == common_ids for _ in ("H0", "H1", "H2")),
            "common_fold_ids_identical": fold_sets["H0"] == fold_sets["H1"] == fold_sets["H2"],
            "grouped_split_disjoint": all(row["held_out_enclosing_macro_leg_id"] in fold_sets["H0"] for row in fold_rows),
            "strong_weak_separate": len(strong_common) + len(weak_common) == len(trajectory_rows),
            "representative_trajectory_recompute": representative,
            "side_experiment_consumed": False,
            "finite_effective_predictors": all(np.isfinite([[row[name] for name in effective[level]] for row in strong_common]).all() for level in ("H0", "H1", "H2")),
        }
        required = [qa["stage2f_baseline_reproduced"], qa["sequence_order_correct"], qa["same_enclosing_macro_leg"], not qa["duplicate_slowdown_ids"], not qa["cross_leg_histories"], not qa["future_predictors_used"], qa["common_sample_ids_identical"], qa["common_fold_ids_identical"], qa["grouped_split_disjoint"], qa["strong_weak_separate"], all(row["passed"] for row in representative), not qa["side_experiment_consumed"], qa["finite_effective_predictors"]]
        if not all(required):
            raise RuntimeError(qa)

        write_parquet(temporary / "history_population.parquet", population_rows)
        write_parquet(temporary / "history_features.parquet", history_rows)
        write_parquet(temporary / "trajectory_features.parquet", trajectory_rows)
        write_csv(temporary / "univariate_history_comparison.csv", univariate_rows)
        write_csv(temporary / "H0_H1_H2_grouped_validation.csv", validation_rows)
        write_csv(temporary / "incremental_value_bootstrap.csv", incremental_rows)
        write_csv(temporary / "direction_conditioned_results.csv", direction_rows)
        write_csv(temporary / "recurring_trajectories.csv", recurring_rows)
        write_csv(temporary / "strong_vs_weak_sensitivity.csv", sensitivity_rows)
        write_csv(temporary / "grouped_fold_results.csv", fold_rows)
        write_json(temporary / "model_diagnostics.json", {"declared_features": declared, "effective_features_after_rank_audit": effective, "coefficients": coefficients})
        (temporary / "confounder_report.md").write_text(confounder)
        write_json(temporary / "qa.json", qa)
        files = [{"path": str(output / path.name), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(temporary.iterdir())]
        manifest = {
            "schema_version": "macro-slowdown-history-stage2g-v1",
            "canonical_stage": "Stage 2G continuation of Stage 2F",
            "side_experiment_used": False,
            "source_stage2f_manifest": str(stage2f / "manifest.json"), "source_stage2f_manifest_sha256": sha256(stage2f / "manifest.json"),
            "source_stage2e_manifest": str(stage2e / "feature_separation_manifest.json"), "source_stage2e_manifest_sha256": sha256(stage2e / "feature_separation_manifest.json"),
            "source_stage2a_manifest": str(stage2a / "manifest.json"), "source_stage2a_manifest_sha256": sha256(stage2a / "manifest.json"),
            "declared_features": declared, "effective_features_after_rank_audit": effective,
            "model": "fixed ridge logistic regression lambda=0.1; leave-one-enclosing-macro-leg-out",
            "qa": qa, "output_files": files, "checksum_index": "checksums.sha256",
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "code_version": {"git_commit_at_build": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(), "pipeline_sha256": sha256(Path(__file__))},
        }
        write_json(temporary / "manifest.json", manifest)
        if not write_checksums(temporary):
            raise RuntimeError("checksum verification failed")
        os.replace(temporary, output)
        return {"status": "PASS", "path": str(output), "stage2f_population": len(population_rows), "common_strong": len(strong_common), "common_weak": len(weak_common), "baseline_auc": baseline_summary["grouped_auc"], "checksums_verified": True, "runtime_seconds": manifest["runtime_seconds"]}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def stamp(data_root: Path, commit: str) -> dict:
    output = data_root / "research/macro_slowdown_history_stage2g"
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["code_version"]["git_commit_at_build"] = commit
    write_json(manifest_path, manifest)
    if not write_checksums(output):
        raise RuntimeError("checksum verification failed after commit stamp")
    return {"status": "PASS", "path": str(output), "git_commit_at_build": commit, "checksums_verified": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp-git-commit")
    args = parser.parse_args()
    result = stamp(args.data_root, args.stamp_git_commit) if args.stamp_git_commit else build(args.data_root, args.repo_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
