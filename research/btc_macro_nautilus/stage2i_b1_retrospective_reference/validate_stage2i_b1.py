#!/usr/bin/env python3
"""Independent artifact-level validation for Stage 2I-B1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import pyarrow.parquet as pq


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_checksums(output_dir: Path) -> int:
    lines = (output_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        if sha256(output_dir / relative) != expected:
            raise ValueError(f"Checksum mismatch: {relative}")
    return len(lines)


def validate(data_root: Path, output_dir: Path) -> Mapping[str, object]:
    checksum_count = validate_checksums(output_dir)
    source_path = data_root / "research" / "stage2i_a_raw_4h_pivots" / "raw_4h_pivots.parquet"
    source = pq.read_table(source_path, columns=["event_id", "pivot_bar_index", "causal__dual_high_low_same_candle"]).to_pylist()
    diagnostics_path = output_dir / "b1_pivot_reference_diagnostics.parquet"
    diagnostics_table = pq.read_table(diagnostics_path)
    diagnostics = diagnostics_table.to_pylist()
    source_ids = [str(row["event_id"]) for row in source]
    output_ids = [str(row["event_id"]) for row in diagnostics]
    if source_ids != output_ids or len(output_ids) != len(set(output_ids)):
        raise ValueError("Output does not preserve the exact Stage 2I-A pivot identity/order")
    if len(diagnostics) != 4450:
        raise ValueError(f"Expected 4,450 diagnostics, found {len(diagnostics)}")
    for column in diagnostics_table.column_names:
        if column.startswith("causal__"):
            raise ValueError(f"Retrospective output exposes causal namespace: {column}")
        if any(token in column.lower() for token in ("micro_label", "independent_label", "b2_feature")):
            raise ValueError(f"Forbidden final/B2 field: {column}")
    primary_columns = (
        "reference__design_a_min_log_prominence",
        "reference__design_b_primary_removal_log_scale",
        "reference__design_c_ratio_survival_fraction",
        "reference__design_c_log_survival_fraction",
        "reference__design_c_local_vol_survival_fraction",
    )
    dual_rows = [row for row in diagnostics if row["dual_flag"]]
    if len(dual_rows) != 300:
        raise ValueError("Dual population mismatch")
    if any(row[column] is not None for row in dual_rows for column in primary_columns):
        raise ValueError("A dual event leaked into the primary alternating sequence")
    if any(not row["reference__dual_unordered_event_preserved"] for row in dual_rows):
        raise ValueError("An unordered dual event was not preserved")
    if sum(bool(row["reference__right_boundary_unresolved"]) for row in diagnostics) != 1:
        raise ValueError("Right-boundary unresolved status is not explicit and unique")
    if sum(bool(row["reference__left_boundary_censored"]) for row in diagnostics) != 1:
        raise ValueError("Left-boundary censored status is not explicit and unique")

    bars = {str(row["event_id"]): int(row["pivot_bar_index"]) for row in source}
    long_table = pq.read_table(output_dir / "b1_segmentations_long.parquet")
    long_rows = long_table.to_pylist()
    for row in long_rows:
        pivot_id = str(row["pivot_id"])
        previous = row["reference__previous_structural_pivot_id"]
        following = row["reference__next_structural_pivot_id"]
        if previous is not None and bars[str(previous)] >= bars[pivot_id]:
            raise ValueError("Previous structural neighbor is not strictly earlier")
        if following is not None and bars[str(following)] <= bars[pivot_id]:
            raise ValueError("Next structural neighbor is not strictly later")
    grouped: Dict[Tuple[str, str, str], List[Tuple[float, bool]]] = {}
    for row in long_rows:
        if row["reference__retained"] is None or row["reference__parameter"] is None:
            continue
        key = (str(row["reference__method"]), str(row["reference__method_variant"]), str(row["pivot_id"]))
        grouped.setdefault(key, []).append((float(row["reference__parameter"]), bool(row["reference__retained"])))
    for key, values in grouped.items():
        ordered = [retained for _, retained in sorted(values)]
        if any((not left) and right for left, right in zip(ordered, ordered[1:])):
            raise ValueError(f"Non-monotone survival sweep: {key}")

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest["qa_status"] != "PASS" or manifest["stage"] != "stage2i-b1-v1":
        raise ValueError("Manifest status/version mismatch")
    chart_paths = sorted((output_dir / "plots").glob("*.svg"))
    if len(chart_paths) != 6:
        raise ValueError(f"Expected six representative charts, found {len(chart_paths)}")
    for path in chart_paths:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("<svg") or "Canonical BTCUSDT futures 4H" not in text:
            raise ValueError(f"Invalid chart: {path}")
    summary = json.loads((output_dir / "b1_summary.json").read_text(encoding="utf-8"))
    if summary["dual_sensitivity"]["fabricated_same_bar_transitions"] != 0:
        raise ValueError("Dual temporal ordering was fabricated")
    return {
        "status": "PASS",
        "source_rows": len(source),
        "diagnostic_rows": len(diagnostics),
        "long_rows": len(long_rows),
        "dual_rows": len(dual_rows),
        "checksums_verified": checksum_count,
        "charts_verified": len(chart_paths),
        "causal_namespace_columns": 0,
        "final_binary_label_columns": 0,
        "fabricated_dual_transitions": 0,
        "left_boundary_censored_rows": 1,
        "right_boundary_unresolved_rows": 1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(validate(args.data_root, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
