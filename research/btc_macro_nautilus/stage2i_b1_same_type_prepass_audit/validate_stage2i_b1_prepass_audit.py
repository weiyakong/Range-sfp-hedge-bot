#!/usr/bin/env python3
"""Independent validation for Stage 2I-B1 Same-Type Prepass Sensitivity Audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping

import pyarrow.parquet as pq


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_checksums(output_dir: Path) -> int:
    checksum_file = output_dir / "checksums.sha256"
    if not checksum_file.exists():
        raise FileNotFoundError(f"Missing checksums file: {checksum_file}")
    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = output_dir / relative
        if sha256(target) != expected:
            raise ValueError(f"Checksum mismatch for {relative}")
    return len(lines)


def validate_audit(data_root: Path, output_dir: Path) -> Mapping[str, object]:
    # 1. Checksums
    checksum_count = validate_checksums(output_dir)

    # 2. Source identity check
    stage_a_path = data_root / "research" / "stage2i_a_raw_4h_pivots" / "raw_4h_pivots.parquet"
    source = pq.read_table(stage_a_path, columns=["event_id", "pivot_bar_index", "causal__dual_high_low_same_candle"]).to_pylist()
    if len(source) != 4450:
        raise ValueError(f"Expected 4,450 Stage A pivots, found {len(source)}")

    # 3. Check diagnostics artifact
    diag_path = output_dir / "prepass_removed_event_diagnostics.parquet"
    diag_table = pq.read_table(diag_path)
    diag_rows = diag_table.to_pylist()

    if len(diag_rows) != 924:
        raise ValueError(f"Expected 924 removed events, found {len(diag_rows)}")

    # Namespace and forbidden tokens check
    for col in diag_table.column_names:
        if col.startswith("causal__"):
            raise ValueError(f"Retrospective audit exposes causal namespace: {col}")
        for token in ("micro_label", "independent_label", "b2_feature", "zone_boundary", "trading_signal"):
            if token in col.lower():
                raise ValueError(f"Forbidden semantic token in column: {col}")

    # Geometry integrity checks
    for r in diag_rows:
        if float(r["reference__departure_adverse_pct"]) < 0.0:
            raise ValueError(f"Negative adverse excursion in row: {r['event_id']}")
        if int(r["reference__departure_adverse_bars"]) < 0:
            raise ValueError(f"Negative departure duration in row: {r['event_id']}")
        if not (0.0 <= float(r["reference__path_efficiency_to_retained"]) <= 1.0001):
            raise ValueError(f"Invalid path efficiency in row: {r['event_id']}")

    # Rescued count in diagnostics
    rescued_in_diag = sum(bool(r["reference__rescued_in_variant_b"]) for r in diag_rows)
    if rescued_in_diag != 59:
        raise ValueError(f"Expected 59 rescued events, found {rescued_in_diag}")

    # 4. Check dual mediated cases
    dual_table = pq.read_table(output_dir / "dual_mediated_cases.parquet")
    dual_rows = dual_table.to_pylist()
    if len(dual_rows) < 59:
        raise ValueError(f"Expected at least 59 dual mediated cases, found {len(dual_rows)}")

    # 5. Check hierarchy sensitivity artifact
    hier_table = pq.read_table(output_dir / "hierarchy_sensitivity.parquet")
    hier_rows = hier_table.to_pylist()
    scales = sorted({float(r["reference__scale_parameter"]) for r in hier_rows})
    if len(scales) < 10:
        raise ValueError(f"Expected at least 10 scale sweeps, found {len(scales)}")

    for variant in ("variant_a_current", "variant_b_dual_aware"):
        v_rows = [r for r in hier_rows if r["reference__variant"] == variant]
        v_rows = sorted(v_rows, key=lambda x: float(x["reference__scale_parameter"]))
        counts = [int(r["reference__retained_count"]) for r in v_rows]
        if any(left < right for left, right in zip(counts, counts[1:])):
            raise ValueError(f"Non-monotone hierarchy retained count for {variant}: {counts}")

    # 6. Check manifest
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("qa_status") != "PASS":
        raise ValueError("Manifest QA status is not PASS")

    # 7. Check plots
    plots_dir = output_dir / "plots"
    svg_files = sorted(plots_dir.glob("*.svg"))
    if len(svg_files) != 6:
        raise ValueError(f"Expected 6 SVG plots, found {len(svg_files)}")
    for svg_file in svg_files:
        content = svg_file.read_text(encoding="utf-8")
        if not content.startswith("<svg"):
            raise ValueError(f"File {svg_file.name} is not a valid SVG")

    return {
        "qa_status": "PASS",
        "checksums_verified": checksum_count,
        "removed_events_verified": len(diag_rows),
        "rescued_events_verified": rescued_in_diag,
        "plots_verified": len(svg_files),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--mode", choices=["prod", "smoke"], default="prod")
    args = parser.parse_args()

    target_dir = args.output_dir or (
        args.data_root / "research" / "stage2i_b1_same_type_prepass_audit"
        if args.mode == "prod"
        else args.data_root / "research" / "stage2i_b1_same_type_prepass_audit" / "smoke"
    )

    result = validate_audit(args.data_root, target_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
