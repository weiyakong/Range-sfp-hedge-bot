#!/usr/bin/env python3
"""Build futures macro-segment aggregates from validated atomic feature tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq


AGGREGATION_VERSION = "macro-segment-atomic-interior-v1"
SCHEMA_VERSION = "macro-segment-aggregates-v1"
RESOLUTIONS = ("4h", "12h", "1d")
ISO_PATTERN = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?\+00:00")
NUMERIC_EXCLUSIONS = {"close_step_sign"}
BOOLEAN_FEATURES = ("alternation_indicator",)
DIRECTIONAL_FIELDS = ("local_direction", "close_step_sign")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    partial = path.with_name(path.name + ".partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_windows(value: Any) -> list[datetime]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    return [parse_time(match.group(0)) for match in ISO_PATTERN.finditer(str(value))]


def optional_time(value: Any) -> datetime | None:
    if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
        return None
    return parse_time(str(value))


def boundary_bounds(anchor: dict[str, Any], side: str) -> tuple[datetime | None, str]:
    """Return the conservative whole-candle bound required by the contract."""
    exact = optional_time(anchor.get("exact_pivot_time"))
    if exact is not None:
        return exact, "exact_pivot_time"
    windows = parse_windows(anchor.get("matching_5m_start_times"))
    if not windows:
        return None, "missing_candidate_window"
    if side == "start":
        return max(windows) + timedelta(minutes=5), "guaranteed_after_all_candidate_windows"
    if side == "end":
        return min(windows), "guaranteed_before_all_candidate_windows"
    raise ValueError(side)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: list[float], prefix: str) -> dict[str, Any]:
    result = {f"{prefix}__count": len(values)}
    for suffix in ("mean", "median", "std", "min", "max", "p25", "p75"):
        result[f"{prefix}__{suffix}"] = None
    if not values:
        return result
    result.update(
        {
            f"{prefix}__mean": statistics.fmean(values),
            f"{prefix}__median": statistics.median(values),
            f"{prefix}__std": statistics.stdev(values) if len(values) > 1 else 0.0,
            f"{prefix}__min": min(values),
            f"{prefix}__max": max(values),
            f"{prefix}__p25": percentile(values, 0.25),
            f"{prefix}__p75": percentile(values, 0.75),
        }
    )
    return result


def direction_summary(values: list[Any], prefix: str) -> dict[str, Any]:
    valid = [value for value in values if value is not None]
    count = len(valid)
    result = {f"{prefix}__eligible_count": count}
    for label in ("positive", "negative", "zero"):
        result[f"{prefix}__{label}_count"] = 0
        result[f"{prefix}__{label}_share"] = None
    if not valid:
        return result
    if prefix == "local_direction":
        counts = {"positive": valid.count("up"), "negative": valid.count("down"), "zero": valid.count("flat")}
    else:
        counts = {"positive": sum(value > 0 for value in valid), "negative": sum(value < 0 for value in valid), "zero": sum(value == 0 for value in valid)}
    for label, value in counts.items():
        result[f"{prefix}__{label}_count"] = value
        result[f"{prefix}__{label}_share"] = value / count
    return result


def bool_summary(values: list[Any], prefix: str) -> dict[str, Any]:
    valid = [value for value in values if value is not None]
    count = len(valid)
    true_count = sum(bool(value) for value in valid)
    return {
        f"{prefix}__eligible_count": count,
        f"{prefix}__true_count": true_count,
        f"{prefix}__true_share": true_count / count if count else None,
    }


def path_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [row for row in rows if row["source_complete"]]
    defaults = {
        "interior_net_signed_move": None,
        "interior_absolute_move": None,
        "interior_signed_log_move": None,
        "interior_absolute_log_move": None,
        "interior_close_path": None,
        "interior_log_close_path": None,
        "interior_path_efficiency": None,
        "interior_counter_direction_path_share": None,
        "interior_path_contiguous": False,
        "interior_speed_signed_return_pct_per_hour": None,
        "interior_speed_signed_log_per_hour": None,
        "interior_speed_absolute_log_per_hour": None,
    }
    if not complete:
        return defaults
    contiguous = all(row["pair_eligible"] for row in complete[1:])
    if not contiguous:
        return defaults
    sequence = [float(complete[0]["open"])] + [float(row["close"]) for row in complete]
    if any(price <= 0 for price in sequence):
        return defaults
    steps = [sequence[index] - sequence[index - 1] for index in range(1, len(sequence))]
    log_steps = [math.log(sequence[index] / sequence[index - 1]) for index in range(1, len(sequence))]
    net = sequence[-1] - sequence[0]
    log_move = math.log(sequence[-1] / sequence[0])
    close_path = sum(abs(step) for step in steps)
    log_path = sum(abs(step) for step in log_steps)
    duration_hours = (complete[-1]["end_time"] - complete[0]["timestamp"]).total_seconds() / 3600
    counter_path = None
    if net > 0 and close_path > 0:
        counter_path = sum(abs(step) for step in steps if step < 0) / close_path
    elif net < 0 and close_path > 0:
        counter_path = sum(abs(step) for step in steps if step > 0) / close_path
    return {
        "interior_net_signed_move": net,
        "interior_absolute_move": abs(net),
        "interior_signed_log_move": log_move,
        "interior_absolute_log_move": abs(log_move),
        "interior_close_path": close_path,
        "interior_log_close_path": log_path,
        "interior_path_efficiency": abs(net) / close_path if close_path > 0 else None,
        "interior_counter_direction_path_share": counter_path,
        "interior_path_contiguous": True,
        "interior_speed_signed_return_pct_per_hour": 100 * (sequence[-1] / sequence[0] - 1) / duration_hours if duration_hours > 0 else None,
        "interior_speed_signed_log_per_hour": log_move / duration_hours if duration_hours > 0 else None,
        "interior_speed_absolute_log_per_hour": abs(log_move) / duration_hours if duration_hours > 0 else None,
    }


def read_atomic(data_root: Path, resolution: str) -> tuple[list[dict[str, Any]], dict, str]:
    directory = data_root / f"features/BTCUSDT/{resolution}_atomic"
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [Path(item["path"]) for item in manifest["output_files"]]
    for item, path in zip(manifest["output_files"], files):
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Atomic feature checksum mismatch: {path}")
    rows = pq.read_table(files).to_pylist()
    return rows, manifest, sha256_file(manifest_path)


def load_segments(repo_root: Path) -> tuple[list[dict[str, Any]], Path, Path]:
    legs_path = repo_root / "research/btc_macro_nautilus/macro_structure/v8/macro_legs_log20.csv"
    anchors_path = repo_root / "research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_refinement_anchors.csv"
    import csv

    with legs_path.open(encoding="utf-8", newline="") as handle:
        legs = list(csv.DictReader(handle))
    with anchors_path.open(encoding="utf-8", newline="") as handle:
        anchors = {row["event_id"]: row for row in csv.DictReader(handle)}
    segments = []
    for leg in legs:
        start_anchor = anchors.get(leg["start_event_id"])
        end_anchor = anchors.get(leg["end_event_id"])
        if not start_anchor or not end_anchor:
            raise ValueError(f"Missing anchor for {leg['leg_id']}")
        if start_anchor["source_market"] != "futures" or end_anchor["source_market"] != "futures":
            continue
        start_bound, start_mode = boundary_bounds(start_anchor, "start")
        end_bound, end_mode = boundary_bounds(end_anchor, "end")
        segments.append(
            {
                "segment_id": leg["leg_id"],
                "start_point_id": leg["start_event_id"],
                "end_point_id": leg["end_event_id"],
                "segment_start": parse_time(leg["start_time"]),
                "segment_end": parse_time(leg["end_time"]),
                "direction": leg["direction"],
                "known_macro_class": None,
                "known_macro_class_status": "not_present_in_approved_macro_legs_log20",
                "source_move_pct": float(leg["move_pct"]),
                "source_log_move": float(leg["log_move"]),
                "source_duration_hours": float(leg["duration_hours"]),
                "source_duration_precision": leg["duration_precision"],
                "aggregation_start_bound": start_bound,
                "aggregation_end_bound": end_bound,
                "start_boundary_mode": start_mode,
                "end_boundary_mode": end_mode,
            }
        )
    return segments, legs_path, anchors_path


def numeric_feature_names(sample: dict[str, Any]) -> list[str]:
    ignored = {"timestamp", "end_time", "previous_timestamp", "resolution", "market", "instrument", "pair_ineligibility_reason", "local_direction"}
    names = []
    for name, value in sample.items():
        if name in ignored or name in NUMERIC_EXCLUSIONS or name in BOOLEAN_FEATURES or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) or value is None:
            names.append(name)
    return names


def aggregate_segment(segment: dict[str, Any], rows: list[dict[str, Any]], resolution: str, numeric_features: list[str]) -> dict[str, Any]:
    start_bound = segment["aggregation_start_bound"]
    end_bound = segment["aggregation_end_bound"]
    status = "eligible"
    selected: list[dict[str, Any]] = []
    if start_bound is None or end_bound is None:
        status = "missing_boundary_candidate"
    elif start_bound >= end_bound:
        status = "no_guaranteed_interior"
    else:
        selected = [row for row in rows if row["timestamp"] >= start_bound and row["end_time"] <= end_bound]
    complete = [row for row in selected if row["source_complete"]]
    pairs = [row for row in selected if row["pair_eligible"]]
    output = {
        **segment,
        "resolution": resolution,
        "membership_semantics": "whole_candle_guaranteed_interior",
        "segment_status": status,
        "atomic_row_count": len(selected),
        "complete_candle_count": len(complete),
        "incomplete_candle_count": len(selected) - len(complete),
        "eligible_pair_count": len(pairs),
        "measurement_first_timestamp": selected[0]["timestamp"] if selected else None,
        "measurement_last_end_time": selected[-1]["end_time"] if selected else None,
    }
    for feature in numeric_features:
        relevant = pairs if feature.startswith(("signed_", "absolute_", "duration_hours", "raw_signed_speed", "true_range", "atr14_", "range_", "overlap_", "body_overlap", "upper_extension", "lower_extension", "extreme_penetration", "body_penetration", "close_penetration", "wick_only_penetration", "volume_close_step")) else complete
        values = [float(row[feature]) for row in relevant if row[feature] is not None]
        output.update(numeric_summary(values, feature))
        if "overlap" in feature:
            output[f"{feature}__positive_count"] = sum(value > 0 for value in values)
            output[f"{feature}__positive_share"] = sum(value > 0 for value in values) / len(values) if values else None
    output.update(bool_summary([row["alternation_indicator"] for row in pairs], "alternation_indicator"))
    output.update(direction_summary([row["local_direction"] for row in pairs], "local_direction"))
    output.update(direction_summary([row["close_step_sign"] for row in pairs], "close_step_sign"))
    output.update(path_metrics(selected))
    return output


def write_dataset(rows: list[dict[str, Any]], temp_dir: Path) -> tuple[list[dict[str, Any]], pa.Schema]:
    table = pa.Table.from_pylist(rows)
    files = []
    for year in sorted({row["segment_start"].year for row in rows}):
        subset = [row for row in rows if row["segment_start"].year == year]
        path = temp_dir / f"part-{year}.parquet"
        pq.write_table(pa.Table.from_pylist(subset, schema=table.schema), path, compression="zstd", compression_level=9, write_statistics=True)
        files.append({"path": path.name, "year": year, "rows": len(subset), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return files, table.schema


def _same(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, float) or isinstance(right, float):
        return float(left) == float(right)
    return left == right


def qa(rows: list[dict[str, Any]], segments: list[dict[str, Any]], source_by_tf: dict[str, list[dict[str, Any]]], numeric_features: list[str]) -> dict:
    errors = []
    expected = {(segment["segment_id"], resolution) for segment in segments for resolution in RESOLUTIONS}
    observed = {(row["segment_id"], row["resolution"]) for row in rows}
    if observed != expected:
        errors.append("segment_tf_coverage")
    if len(observed) != len(rows):
        errors.append("duplicate_segment_tf")
    for row in rows:
        if row["direction"] not in ("up", "down"):
            errors.append(f"direction:{row['segment_id']}")
        if row["known_macro_class"] is not None or row["known_macro_class_status"] != "not_present_in_approved_macro_legs_log20":
            errors.append(f"class_provenance:{row['segment_id']}")
        for key, value in row.items():
            if isinstance(value, float) and not math.isfinite(value):
                errors.append(f"non_finite:{row['segment_id']}:{key}")
    # Deterministic direct recomputation: first, middle, and final segment × each TF.
    representative = [segments[0], segments[len(segments) // 2], segments[-1]]
    spot_checks = []
    by_key = {(row["segment_id"], row["resolution"]): row for row in rows}
    for segment in representative:
        for resolution in RESOLUTIONS:
            fresh = aggregate_segment(segment, source_by_tf[resolution], resolution, numeric_features)
            stored = by_key[(segment["segment_id"], resolution)]
            keys = (
                "atomic_row_count", "complete_candle_count", "eligible_pair_count", "measurement_first_timestamp",
                "measurement_last_end_time", "full_range__mean", "range_overlap_abs__mean", "interior_close_path",
                "interior_path_efficiency", "alternation_indicator__true_count",
            )
            passed = all(_same(stored.get(key), fresh.get(key)) for key in keys)
            spot_checks.append({"segment_id": segment["segment_id"], "resolution": resolution, "passed": passed})
            if not passed:
                errors.append(f"spot_check:{segment['segment_id']}:{resolution}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "spot_checks": spot_checks, "rows": len(rows)}


def build(data_root: Path, repo_root: Path) -> dict:
    started = time.perf_counter()
    segments, legs_path, anchors_path = load_segments(repo_root)
    source_by_tf = {}
    manifests = {}
    for resolution in RESOLUTIONS:
        rows, manifest, manifest_sha = read_atomic(data_root, resolution)
        source_by_tf[resolution] = rows
        manifests[resolution] = {"path": str(data_root / f"features/BTCUSDT/{resolution}_atomic/manifest.json"), "sha256": manifest_sha, "rows": manifest["rows"]}
    numeric_features = numeric_feature_names(source_by_tf["4h"][0])
    build_started = time.perf_counter()
    output_rows = [aggregate_segment(segment, source_by_tf[resolution], resolution, numeric_features) for segment in segments for resolution in RESOLUTIONS]
    output_root = data_root / "research/macro_segment_aggregates"
    if output_root.exists():
        raise FileExistsError(f"Output already exists; refusing unvalidated overwrite: {output_root}")
    temp_dir = output_root.parent / f".{output_root.name}.build-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True)
    try:
        files, schema = write_dataset(output_rows, temp_dir)
        build_seconds = time.perf_counter() - build_started
        qa_started = time.perf_counter()
        reloaded = pq.read_table(sorted(temp_dir.glob("part-*.parquet"))).to_pylist()
        qa_result = qa(reloaded, segments, source_by_tf, numeric_features)
        qa_seconds = time.perf_counter() - qa_started
        if qa_result["status"] != "PASS":
            raise RuntimeError("macro segment aggregate QA failed")
        final_files = [{**item, "path": str(output_root / item["path"])} for item in files]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "aggregation_version": AGGREGATION_VERSION,
            "build_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "market": "binance_usdt_futures",
            "instrument": "BTCUSDT",
            "resolutions": list(RESOLUTIONS),
            "macro_source": {"path": str(legs_path), "sha256": sha256_file(legs_path), "segments_total": len(segments)},
            "macro_anchor_source": {"path": str(anchors_path), "sha256": sha256_file(anchors_path)},
            "source_atomic_manifests": manifests,
            "membership_semantics": "whole_candle_guaranteed_interior",
            "known_macro_class": "null; not present in approved macro_legs_log20 source",
            "output_rows": len(output_rows),
            "aggregate_columns": len(schema.names),
            "numeric_atomic_features_aggregated": numeric_features,
            "numeric_summary_statistics": ["count", "mean", "median", "std", "min", "max", "p25", "p75"],
            "deferred": {
                "early_middle_late_progress_buckets": "no approved neutral segment-division rule exists in the current contracts",
                "extremum_update_rate_and_count": "no exact approved atomic-to-segment formula exists in the current contracts",
                "macro_boundary_fragments": "atomic inputs contain whole candles only; fragment-inclusive macro metrics require separately materialized approved fragments",
            },
            "qa": qa_result,
            "output_files": final_files,
            "code_version": {"git_commit_at_build": git_commit(repo_root), "pipeline_sha256": sha256_file(Path(__file__))},
        }
        atomic_json(temp_dir / "manifest.json", manifest)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_dir, output_root)
        report = {
            "status": "PASS",
            "path": str(output_root),
            "rows": len(output_rows),
            "aggregate_columns": len(schema.names),
            "bytes": sum(item["bytes"] for item in files),
            "segments": len(segments),
            "qa": qa_result,
            "runtime_seconds": {"build": round(build_seconds, 3), "validation": round(qa_seconds, 3), "total": round(time.perf_counter() - started, 3)},
        }
        atomic_json(data_root / "manifests/macro_segment_aggregates_build_report.json", report)
        return report
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def stamp_git_commit(data_root: Path, commit: str) -> None:
    path = data_root / "research/macro_segment_aggregates/manifest.json"
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
