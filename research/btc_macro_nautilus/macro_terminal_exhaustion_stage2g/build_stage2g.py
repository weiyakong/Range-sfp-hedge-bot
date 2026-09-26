#!/usr/bin/env python3
"""Paired previous-push versus terminal-push analysis on frozen Stage 2 outputs."""
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
BASE_FEATURES = [
    "speed", "net_move", "duration_hours", "candle_count", "persistence",
    "alternation", "overlap", "geometry", "volatility", "volume", "trade_count",
]
EFFORT_FEATURES = [
    "progress_per_hour", "total_volume", "total_trade_count", "total_volatility",
    "progress_per_volume", "progress_per_trade_count", "progress_per_volatility",
]
PAIR_FEATURES = BASE_FEATURES + EFFORT_FEATURES
MODEL_FEATURES = [
    "speed", "net_move", "persistence", "alternation", "overlap", "geometry",
    "volatility", "volume", "trade_count", "progress_per_hour",
    "progress_per_volume", "progress_per_trade_count", "progress_per_volatility",
]


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


def sign_name(value: float) -> str:
    return "up" if value > 0 else "down" if value < 0 else "flat"


def paired_rank_biserial(changes: np.ndarray) -> float | None:
    nonzero = np.asarray(changes, dtype=float)
    nonzero = nonzero[nonzero != 0]
    if len(nonzero) == 0:
        return None
    order = np.argsort(np.abs(nonzero), kind="stable")
    ranks = np.empty(len(nonzero), dtype=float)
    sorted_abs = np.abs(nonzero)[order]
    start = 0
    while start < len(nonzero):
        end = start + 1
        while end < len(nonzero) and sorted_abs[end] == sorted_abs[start]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2
        start = end
    total = ranks.sum()
    return float((ranks[nonzero > 0].sum() - ranks[nonzero < 0].sum()) / total)


def cluster_bootstrap_median(changes: np.ndarray, legs: np.ndarray, seed: int, repetitions: int = 1000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique = np.asarray(sorted(set(legs)))
    values = []
    for _ in range(repetitions):
        sampled = rng.choice(unique, len(unique), replace=True)
        draw = np.concatenate([changes[legs == leg] for leg in sampled])
        values.append(float(np.median(draw)))
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


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


def push_metrics(feature: dict) -> dict[str, float]:
    progress = abs(float(feature["net_move"]))
    candles = float(feature["candle_count"])
    duration = float(feature["duration_hours"])
    total_volume = float(feature["volume"]) * candles
    total_trades = float(feature["trade_count"]) * candles
    total_volatility = float(feature["volatility"]) * candles
    return {
        **{name: float(feature[name]) for name in BASE_FEATURES},
        "net_move": progress,
        "progress_per_hour": progress / duration,
        "total_volume": total_volume,
        "total_trade_count": total_trades,
        "total_volatility": total_volatility,
        "progress_per_volume": progress / total_volume,
        "progress_per_trade_count": progress / total_trades,
        "progress_per_volatility": progress / total_volatility,
    }


def extreme_metrics(previous_rows: list[dict], terminal_rows: list[dict], direction: str, terminal_volatility: float) -> dict:
    previous_extreme = max(row["high"] for row in previous_rows) if direction == "up" else min(row["low"] for row in previous_rows)
    terminal_extreme = max(row["high"] for row in terminal_rows) if direction == "up" else min(row["low"] for row in terminal_rows)
    terminal_high = max(row["high"] for row in terminal_rows)
    terminal_low = min(row["low"] for row in terminal_rows)
    terminal_close = terminal_rows[-1]["close"]
    if direction == "up":
        extension = math.log(terminal_extreme / previous_extreme) if terminal_extreme > previous_extreme else 0.0
        close_beyond = math.log(terminal_close / previous_extreme)
        rejection = math.log(terminal_extreme / terminal_close)
        close_location = (terminal_close - terminal_low) / (terminal_high - terminal_low)
    else:
        extension = math.log(previous_extreme / terminal_extreme) if terminal_extreme < previous_extreme else 0.0
        close_beyond = math.log(previous_extreme / terminal_close)
        rejection = math.log(terminal_close / terminal_extreme)
        close_location = (terminal_high - terminal_close) / (terminal_high - terminal_low)
    new_extreme = extension > 0
    retained = max(0.0, close_beyond) if new_extreme else 0.0
    return {
        "previous_same_direction_extreme": float(previous_extreme),
        "terminal_extreme": float(terminal_extreme),
        "terminal_close": float(terminal_close),
        "new_extreme": new_extreme,
        "extension_log": extension,
        "extension_per_total_volatility": extension / terminal_volatility,
        "close_progress_beyond_previous_extreme_log": close_beyond,
        "retained_extension_log": retained,
        "retained_extension_fraction": min(1.0, retained / extension) if new_extreme else None,
        "rejection_from_terminal_extreme_log": rejection,
        "terminal_close_location_oriented": close_location,
    }


def load_atomic(data_root: Path) -> tuple[list[dict], Path, str]:
    root = data_root / "features/BTCUSDT/4h_atomic"
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["qa"]["status"] != "PASS":
        raise ValueError("atomic source QA is not PASS")
    files = []
    for item in manifest["output_files"]:
        path = Path(item["path"])
        if not path.is_absolute():
            path = root / path
        if sha256(path) != item["sha256"]:
            raise ValueError(f"atomic checksum mismatch: {path}")
        files.append(path)
    columns = ["timestamp", "end_time", "open", "high", "low", "close", "signed_log_move"]
    return pq.read_table(files, columns=columns).to_pylist(), manifest_path, sha256(manifest_path)


def build(data_root: Path, repo_root: Path) -> dict:
    started = time.perf_counter()
    stage2a = data_root / "research/macro_within_leg_stage2a"
    stage2e = data_root / "research/macro_within_leg_stage2e_feature_separation"
    output = data_root / "research/macro_terminal_exhaustion_stage2g"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    temporary = output.parent / f".{output.name}.build-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True)
    try:
        a_manifest = json.loads((stage2a / "manifest.json").read_text())
        e_manifest = json.loads((stage2e / "feature_separation_manifest.json").read_text())
        if a_manifest["qa"]["status"] != "PASS" or e_manifest["qa"]["status"] != "PASS":
            raise ValueError("upstream QA is not PASS")
        atomic, atomic_manifest_path, atomic_manifest_sha = load_atomic(data_root)
        original = pq.read_table(stage2a / "candidate_subsegments.parquet").to_pylist()
        features = pq.read_table(stage2e / "separated_subsegment_features.parquet").to_pylist()
        transitions = pq.read_table(stage2e / "refined_adjacent_transitions.parquet").to_pylist()
        original_map = {row["subsegment_id"]: row for row in original}
        feature_map = {row["subsegment_id"]: row for row in features}
        transition_map = {(row["from_subsegment_id"], row["to_subsegment_id"]): row for row in transitions}
        atomic_sorted = sorted(atomic, key=lambda row: row["timestamp"])
        atomic_cache: dict[str, list[dict]] = {}

        def candles(subsegment_id: str) -> list[dict]:
            if subsegment_id not in atomic_cache:
                source = original_map[subsegment_id]
                rows = [row for row in atomic_sorted if row["timestamp"] >= source["start_timestamp"] and row["end_time"] <= source["end_timestamp"]]
                if len(rows) != source["candle_count"]:
                    raise ValueError(f"atomic membership mismatch: {subsegment_id}")
                atomic_cache[subsegment_id] = rows
            return atomic_cache[subsegment_id]

        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in features:
            grouped[row["parent_macro_leg_id"]].append(row)
        population, pairs, progress_rows, extreme_rows, divergence_rows = [], [], [], [], []
        excluded_without_previous = 0
        for enclosing_macro_leg_id, rows in sorted(grouped.items()):
            rows.sort(key=lambda row: original_map[row["subsegment_id"]]["subsegment_order"])
            for index, terminal in enumerate(rows[:-1]):
                next_subsegment = rows[index + 1]
                if terminal["net_direction_relative"] != "forward" or next_subsegment["net_direction_relative"] != "counter":
                    continue
                boundary = transition_map[(terminal["subsegment_id"], next_subsegment["subsegment_id"])]["boundary_class"]
                previous = next((row for row in reversed(rows[:index]) if row["net_direction_relative"] == "forward"), None)
                population.append({
                    "terminal_subsegment_id": terminal["subsegment_id"],
                    "enclosing_macro_leg_id": enclosing_macro_leg_id,
                    "enclosing_macro_leg_direction": terminal["macro_direction"],
                    "next_subsegment_id": next_subsegment["subsegment_id"],
                    "next_direction_relative": next_subsegment["net_direction_relative"],
                    "reversal_boundary_strength": boundary,
                    "previous_same_direction_subsegment_id": None if previous is None else previous["subsegment_id"],
                    "paired_comparison_eligible": previous is not None,
                })
                if previous is None:
                    excluded_without_previous += 1
                    continue
                previous_metrics, terminal_metrics = push_metrics(previous), push_metrics(terminal)
                pair_id = f"{previous['subsegment_id']}__{terminal['subsegment_id']}"
                base = {
                    "pair_id": pair_id,
                    "enclosing_macro_leg_id": enclosing_macro_leg_id,
                    "enclosing_macro_leg_direction": terminal["macro_direction"],
                    "calendar_era": str(original_map[terminal["subsegment_id"]]["start_timestamp"].year),
                    "previous_subsegment_id": previous["subsegment_id"],
                    "terminal_subsegment_id": terminal["subsegment_id"],
                    "next_subsegment_id": next_subsegment["subsegment_id"],
                    "reversal_boundary_strength": boundary,
                }
                pair = dict(base)
                for name in PAIR_FEATURES:
                    pair[f"previous_{name}"] = previous_metrics[name]
                    pair[f"terminal_{name}"] = terminal_metrics[name]
                    pair[f"delta_{name}"] = terminal_metrics[name] - previous_metrics[name]
                pairs.append(pair)
                progress_rows.append({**base, **{f"previous_{name}": previous_metrics[name] for name in EFFORT_FEATURES + ["net_move"]}, **{f"terminal_{name}": terminal_metrics[name] for name in EFFORT_FEATURES + ["net_move"]}, **{f"delta_{name}": terminal_metrics[name] - previous_metrics[name] for name in EFFORT_FEATURES + ["net_move"]}})
                direction = terminal["macro_direction"]
                terminal_total_volatility = terminal_metrics["total_volatility"]
                extreme = extreme_metrics(candles(previous["subsegment_id"]), candles(terminal["subsegment_id"]), direction, terminal_total_volatility)
                extreme_rows.append({**base, **extreme})
                delta = {name: terminal_metrics[name] - previous_metrics[name] for name in PAIR_FEATURES}
                divergence_rows.append({
                    **base,
                    "new_extreme": extreme["new_extreme"],
                    "progress_weaker": delta["net_move"] < 0,
                    "speed_lower": delta["speed"] < 0,
                    "persistence_lower": delta["persistence"] < 0,
                    "alternation_higher": delta["alternation"] > 0,
                    "overlap_higher": delta["overlap"] > 0,
                    "volatility_higher": delta["volatility"] > 0,
                    "volume_higher": delta["volume"] > 0,
                    "volume_lower": delta["volume"] < 0,
                    "trade_count_higher": delta["trade_count"] > 0,
                    "trade_count_lower": delta["trade_count"] < 0,
                    "progress_per_hour_lower": delta["progress_per_hour"] < 0,
                    "progress_per_volume_lower": delta["progress_per_volume"] < 0,
                    "progress_per_trade_count_lower": delta["progress_per_trade_count"] < 0,
                    "progress_per_volatility_lower": delta["progress_per_volatility"] < 0,
                    "duration_higher_with_progress_lower": delta["duration_hours"] > 0 and delta["net_move"] < 0,
                    "candle_count_higher_with_progress_lower": delta["candle_count"] > 0 and delta["net_move"] < 0,
                    "extension_log": extreme["extension_log"],
                    "retained_extension_fraction": extreme["retained_extension_fraction"],
                    "terminal_close_location_oriented": extreme["terminal_close_location_oriented"],
                })

        strong_pairs = [row for row in pairs if row["reversal_boundary_strength"] == "strong"]
        weak_pairs = [row for row in pairs if row["reversal_boundary_strength"] == "weak"]
        comparison, sensitivity = [], []
        for feature_index, name in enumerate(PAIR_FEATURES):
            changes = np.asarray([row[f"delta_{name}"] for row in strong_pairs], dtype=float)
            legs = np.asarray([row["enclosing_macro_leg_id"] for row in strong_pairs])
            low, high = cluster_bootstrap_median(changes, legs, SEED + feature_index)
            overall_sign = np.sign(np.median(changes))
            leg_medians = [np.median(changes[legs == leg]) for leg in sorted(set(legs))]
            supported = sum(np.sign(value) == overall_sign for value in leg_medians if value != 0)
            eligible_legs = sum(value != 0 for value in leg_medians)
            comparison.append({
                "feature": name,
                "previous_median": float(np.median([row[f"previous_{name}"] for row in strong_pairs])),
                "terminal_median": float(np.median([row[f"terminal_{name}"] for row in strong_pairs])),
                "paired_change_median": float(np.median(changes)),
                "paired_change_p25": float(np.quantile(changes, 0.25)),
                "paired_change_p75": float(np.quantile(changes, 0.75)),
                "paired_rank_biserial": paired_rank_biserial(changes),
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "bootstrap_excludes_zero": low > 0 or high < 0,
                "proportion_terminal_lower": float(np.mean(changes < 0)),
                "proportion_terminal_higher": float(np.mean(changes > 0)),
                "cross_leg_direction_support": supported / eligible_legs if eligible_legs else None,
                "macro_legs": len(set(legs)),
            })
            for boundary, rows in (("strong", strong_pairs), ("weak", weak_pairs)):
                values = np.asarray([row[f"delta_{name}"] for row in rows], dtype=float)
                sensitivity.append({"feature": name, "boundary_population": boundary, "pairs": len(rows), "median_paired_change": float(np.median(values)), "paired_rank_biserial": paired_rank_biserial(values), "proportion_terminal_lower": float(np.mean(values < 0)), "proportion_terminal_higher": float(np.mean(values > 0))})

        form_rows = []
        strong_divergence = [row for row in divergence_rows if row["reversal_boundary_strength"] == "strong"]
        component_names = [
            "new_extreme", "progress_weaker", "speed_lower", "persistence_lower", "alternation_higher",
            "overlap_higher", "volatility_higher", "volume_higher", "trade_count_higher",
            "progress_per_hour_lower", "progress_per_volume_lower", "progress_per_trade_count_lower",
            "progress_per_volatility_lower", "duration_higher_with_progress_lower",
        ]
        for name in component_names:
            matches = [row for row in strong_divergence if row[name]]
            form_rows.append({"record_type": "component_support", "pattern": name, "pairs": len(matches), "pair_fraction": len(matches) / len(strong_divergence), "macro_legs": len({row["enclosing_macro_leg_id"] for row in matches}), "calendar_eras": len({row["calendar_era"] for row in matches}), "up_pairs": sum(row["enclosing_macro_leg_direction"] == "up" for row in matches), "down_pairs": sum(row["enclosing_macro_leg_direction"] == "down" for row in matches)})
        conjunctions = {
            "new_extreme_and_progress_weaker": lambda row: row["new_extreme"] and row["progress_weaker"],
            "new_extreme_progress_weaker_speed_lower": lambda row: row["new_extreme"] and row["progress_weaker"] and row["speed_lower"],
            "new_extreme_progress_weaker_volume_efficiency_lower": lambda row: row["new_extreme"] and row["progress_weaker"] and row["progress_per_volume_lower"],
            "new_extreme_volatility_volume_trades_higher": lambda row: row["new_extreme"] and row["volatility_higher"] and row["volume_higher"] and row["trade_count_higher"],
            "new_extreme_activity_higher_joint_efficiency_lower": lambda row: row["new_extreme"] and row["volatility_higher"] and row["volume_higher"] and row["trade_count_higher"] and row["progress_per_volume_lower"] and row["progress_per_trade_count_lower"],
        }
        for name, rule in conjunctions.items():
            matches = [row for row in strong_divergence if rule(row)]
            form_rows.append({"record_type": "combination_support", "pattern": name, "pairs": len(matches), "pair_fraction": len(matches) / len(strong_divergence), "macro_legs": len({row["enclosing_macro_leg_id"] for row in matches}), "calendar_eras": len({row["calendar_era"] for row in matches}), "up_pairs": sum(row["enclosing_macro_leg_direction"] == "up" for row in matches), "down_pairs": sum(row["enclosing_macro_leg_direction"] == "down" for row in matches)})
        signature_groups: dict[str, list[dict]] = defaultdict(list)
        for row in strong_divergence:
            signature = "|".join([
                f"progress_{'weaker' if row['progress_weaker'] else 'not_weaker'}",
                f"speed_{'lower' if row['speed_lower'] else 'not_lower'}",
                f"volatility_{'higher' if row['volatility_higher'] else 'not_higher'}",
                f"volume_{'higher' if row['volume_higher'] else 'not_higher'}",
                f"trades_{'higher' if row['trade_count_higher'] else 'not_higher'}",
                f"efficiency_{'lower' if row['progress_per_volume_lower'] and row['progress_per_trade_count_lower'] else 'not_jointly_lower'}",
            ])
            signature_groups[signature].append(row)
        for signature, rows in sorted(signature_groups.items(), key=lambda item: (-len(item[1]), item[0])):
            form_rows.append({"record_type": "observed_signature", "pattern": signature, "pairs": len(rows), "pair_fraction": len(rows) / len(strong_divergence), "macro_legs": len({row["enclosing_macro_leg_id"] for row in rows}), "calendar_eras": len({row["calendar_era"] for row in rows}), "up_pairs": sum(row["enclosing_macro_leg_direction"] == "up" for row in rows), "down_pairs": sum(row["enclosing_macro_leg_direction"] == "down" for row in rows)})

        # One bounded diagnostic: distinguish P from T using only end-of-push features.
        model_x, model_y, model_legs = [], [], []
        for row in strong_pairs:
            for prefix, label in (("previous", 0), ("terminal", 1)):
                model_x.append([row[f"{prefix}_{name}"] for name in MODEL_FEATURES])
                model_y.append(label)
                model_legs.append(row["enclosing_macro_leg_id"])
        x = np.asarray(model_x, dtype=float)
        y = np.asarray(model_y, dtype=int)
        model_legs_array = np.asarray(model_legs)
        predictions = np.full(len(y), np.nan)
        grouped_results, disjoint = [], True
        for leg in sorted(set(model_legs_array)):
            test = model_legs_array == leg
            train = ~test
            disjoint = disjoint and not np.any(model_legs_array[train] == leg) and np.all(model_legs_array[test] == leg)
            mean, scale = x[train].mean(axis=0), x[train].std(axis=0)
            scale[scale == 0] = 1
            weights = fit_ridge((x[train] - mean) / scale, y[train])
            predictions[test] = sigmoid(weights[0] + ((x[test] - mean) / scale) @ weights[1:])
            grouped_results.append({"held_out_enclosing_macro_leg_id": leg, "rows": int(test.sum()), "terminal_rows": int(y[test].sum()), "mean_terminal_probability": float(np.mean(predictions[test]))})
        valid = np.isfinite(predictions)
        full_mean, full_scale = x.mean(axis=0), x.std(axis=0)
        full_scale[full_scale == 0] = 1
        full_weights = fit_ridge((x - full_mean) / full_scale, y)
        diagnostic = {
            "method": "fixed ridge logistic regression; lambda=0.1; leave-one-enclosing-macro-leg-out",
            "target": "terminal push T versus previous same-direction push P",
            "rows": len(y),
            "pairs": len(strong_pairs),
            "enclosing_macro_legs": len(set(model_legs_array)),
            "predictors": MODEL_FEATURES,
            "pooled_grouped_auc": auc(y[valid], predictions[valid]),
            "pooled_grouped_balanced_accuracy": float(((predictions[valid][y[valid] == 1] >= 0.5).mean() + (predictions[valid][y[valid] == 0] < 0.5).mean()) / 2),
            "full_fit_standardized_coefficients": sorted(({"feature": name, "coefficient_for_terminal": float(value)} for name, value in zip(MODEL_FEATURES, full_weights[1:])), key=lambda row: -abs(row["coefficient_for_terminal"])),
            "future_features_used": False,
        }

        confounder_rows = []
        for group_type, values in (("enclosing_macro_leg_direction", sorted({row["enclosing_macro_leg_direction"] for row in strong_pairs})), ("calendar_era", sorted({row["calendar_era"] for row in strong_pairs}))):
            for value in values:
                rows = [row for row in strong_pairs if row[group_type] == value]
                for name in PAIR_FEATURES:
                    changes = np.asarray([row[f"delta_{name}"] for row in rows], dtype=float)
                    confounder_rows.append({"group_type": group_type, "group_value": value, "feature": name, "pairs": len(rows), "enclosing_macro_legs": len({row["enclosing_macro_leg_id"] for row in rows}), "median_paired_change": float(np.median(changes)), "paired_rank_biserial": paired_rank_biserial(changes), "proportion_terminal_lower": float(np.mean(changes < 0)), "proportion_terminal_higher": float(np.mean(changes > 0))})
        direction_counts = Counter((row["enclosing_macro_leg_direction"], row["reversal_boundary_strength"]) for row in pairs)
        era_counts = Counter((row["calendar_era"], row["reversal_boundary_strength"]) for row in pairs)
        confounder = "# Confounder report\n\nAll comparisons are paired within one enclosing macro leg. The grouped diagnostic holds out complete enclosing macro legs. Duration and candle count are reported as explicit paired metadata rather than hidden in totals. Volatility is retained as a continuous validated component; no post-outcome regime label is created.\n\n"
        confounder += f"Pairs by enclosing macro-leg direction and boundary: {dict(direction_counts)}.\n\nPairs by calendar era and boundary: {dict(era_counts)}.\n\n"
        confounder += "Feature-wise direction and era sensitivity is stored in `confounder_sensitivity.csv`. Terminal close retention uses the exact terminal-subsegment high/low/final close. No arbitrary late-window deterioration, adverse-wick aggregation, or return-inside rule was introduced because no canonical validated aggregation exists for those concepts. Counter-movement share and travelled-path efficiency were not assessed because the validated Stage 2E fields are unavailable/all-null.\n"

        representative_progress = []
        representative_extreme = []
        for row in pairs[:3]:
            terminal = feature_map[row["terminal_subsegment_id"]]
            prior = feature_map[row["previous_subsegment_id"]]
            terminal_atomic_progress = sum((1 if terminal["macro_direction"] == "up" else -1) * candle["signed_log_move"] for candle in candles(terminal["subsegment_id"]))
            prior_atomic_progress = sum((1 if prior["macro_direction"] == "up" else -1) * candle["signed_log_move"] for candle in candles(prior["subsegment_id"]))
            representative_progress.append({"pair_id": row["pair_id"], "passed": bool(np.isclose(terminal_atomic_progress, row["terminal_net_move"]) and np.isclose(prior_atomic_progress, row["previous_net_move"]))})
            saved = next(item for item in extreme_rows if item["pair_id"] == row["pair_id"])
            recalculated = extreme_metrics(candles(prior["subsegment_id"]), candles(terminal["subsegment_id"]), terminal["macro_direction"], row["terminal_total_volatility"])
            representative_extreme.append({"pair_id": row["pair_id"], "passed": bool(np.isclose(saved["extension_log"], recalculated["extension_log"]) and saved["new_extreme"] == recalculated["new_extreme"])})

        nearest_previous_ok = True
        for row in pairs:
            ordered = sorted(grouped[row["enclosing_macro_leg_id"]], key=lambda item: original_map[item["subsegment_id"]]["subsegment_order"])
            terminal_index = next(index for index, item in enumerate(ordered) if item["subsegment_id"] == row["terminal_subsegment_id"])
            expected = next(item for item in reversed(ordered[:terminal_index]) if item["net_direction_relative"] == "forward")
            nearest_previous_ok = nearest_previous_ok and expected["subsegment_id"] == row["previous_subsegment_id"]
        required_matrix = np.asarray([[row[f"{prefix}_{name}"] for prefix in ("previous", "terminal") for name in PAIR_FEATURES] for row in pairs], dtype=float)
        qa = {
            "status": "PASS",
            "terminal_candidates": len(population),
            "valid_pairs": len(pairs),
            "strong_pairs": len(strong_pairs),
            "weak_pairs": len(weak_pairs),
            "excluded_without_previous_same_direction_push": excluded_without_previous,
            "terminal_forward_relative_to_enclosing_macro_leg": all(feature_map[row["terminal_subsegment_id"]]["net_direction_relative"] == "forward" for row in pairs),
            "next_changes_direction": all(feature_map[row["next_subsegment_id"]]["net_direction_relative"] == "counter" for row in pairs),
            "nearest_previous_same_direction_push": nearest_previous_ok,
            "same_enclosing_macro_leg": all(feature_map[row["previous_subsegment_id"]]["parent_macro_leg_id"] == row["enclosing_macro_leg_id"] == feature_map[row["terminal_subsegment_id"]]["parent_macro_leg_id"] for row in pairs),
            "chronological_order": all(original_map[row["previous_subsegment_id"]]["end_timestamp"] <= original_map[row["terminal_subsegment_id"]]["start_timestamp"] for row in pairs),
            "future_predictors_used": False,
            "duplicate_pair_ids": len({row["pair_id"] for row in pairs}) != len(pairs),
            "strong_weak_separate": len(strong_pairs) + len(weak_pairs) == len(pairs),
            "finite_required_values": bool(np.isfinite(required_matrix).all()),
            "grouped_validation_disjoint": bool(disjoint),
            "representative_progress_recompute": representative_progress,
            "representative_extreme_recompute": representative_extreme,
            "noncanonical_late_window_rule_created": False,
        }
        required_checks = [
            qa["terminal_forward_relative_to_enclosing_macro_leg"], qa["next_changes_direction"],
            qa["nearest_previous_same_direction_push"], qa["same_enclosing_macro_leg"], qa["chronological_order"],
            not qa["future_predictors_used"], not qa["duplicate_pair_ids"], qa["strong_weak_separate"],
            qa["finite_required_values"], qa["grouped_validation_disjoint"],
            all(row["passed"] for row in representative_progress), all(row["passed"] for row in representative_extreme),
        ]
        if not all(required_checks):
            raise RuntimeError(qa)

        write_parquet(temporary / "terminal_push_population.parquet", population)
        write_parquet(temporary / "previous_vs_terminal_pairs.parquet", pairs)
        write_csv(temporary / "paired_feature_comparison.csv", comparison)
        write_csv(temporary / "progress_effort_metrics.csv", progress_rows)
        write_csv(temporary / "new_extreme_diagnostics.csv", extreme_rows)
        write_csv(temporary / "price_effort_divergence.csv", divergence_rows)
        write_csv(temporary / "terminal_form_diagnostics.csv", form_rows)
        write_csv(temporary / "strong_vs_weak_sensitivity.csv", sensitivity)
        write_csv(temporary / "confounder_sensitivity.csv", confounder_rows)
        write_json(temporary / "multivariate_diagnostic.json", diagnostic)
        write_csv(temporary / "grouped_validation_results.csv", grouped_results)
        (temporary / "confounder_report.md").write_text(confounder)
        write_json(temporary / "qa.json", qa)
        files = [{"path": str(output / path.name), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(temporary.iterdir())]
        manifest = {
            "schema_version": "macro-terminal-exhaustion-stage2g-v1",
            "terminology": "enclosing_macro_leg",
            "terminal_candidate_rule": "T is forward relative to enclosing macro leg and next subsegment is counter; next contributes direction only",
            "previous_push_rule": "nearest earlier forward subsegment in same enclosing macro leg",
            "source_stage2a_manifest": str(stage2a / "manifest.json"),
            "source_stage2a_manifest_sha256": sha256(stage2a / "manifest.json"),
            "source_stage2e_manifest": str(stage2e / "feature_separation_manifest.json"),
            "source_stage2e_manifest_sha256": sha256(stage2e / "feature_separation_manifest.json"),
            "source_atomic_manifest": str(atomic_manifest_path),
            "source_atomic_manifest_sha256": atomic_manifest_sha,
            "paired_features": PAIR_FEATURES,
            "model_features": MODEL_FEATURES,
            "qa": qa,
            "output_files": files,
            "checksum_index": "checksums.sha256",
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "code_version": {"git_commit_at_build": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(), "pipeline_sha256": sha256(Path(__file__))},
        }
        write_json(temporary / "manifest.json", manifest)
        if not write_checksums(temporary):
            raise RuntimeError("checksum verification failed")
        os.replace(temporary, output)
        return {"status": "PASS", "path": str(output), "terminal_candidates": len(population), "valid_pairs": len(pairs), "strong_pairs": len(strong_pairs), "weak_pairs": len(weak_pairs), "checksums_verified": True, "runtime_seconds": manifest["runtime_seconds"]}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def stamp(data_root: Path, commit: str) -> dict:
    output = data_root / "research/macro_terminal_exhaustion_stage2g"
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
