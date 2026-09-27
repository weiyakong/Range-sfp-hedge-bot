"""Validation Script for Stage 2I-B1 Reference Contract Comparison.

Performs comprehensive validation of generated artifacts, population invariants,
B+C contract semantics, schema compliance, and checksum verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Set

import pyarrow.parquet as pq

EXPECTED_MASTER_COUNT = 4450
EXPECTED_DUAL_COUNT = 300
EXPECTED_EXCLUDED_SAME_TYPE = 865
EXPECTED_RESOLVED_COUNT = 2867
EXPECTED_LEFT_EDGE_COUNT = 1
EXPECTED_RIGHT_EDGE_COUNT = 1
EXPECTED_DUAL_BOUNDARY_COUNT = 416
EXPECTED_ALTERNATING_CANDIDATES = 3285
EXPECTED_SEGMENTS = 145


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_artifacts(artifact_dir: Path) -> None:
    print(f"=== Validating Stage 2I-B1 Comparison Artifacts at: {artifact_dir} ===")

    # 1. Manifest and Checksums
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest.json at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    checksums_path = artifact_dir / "checksums.sha256"
    if not checksums_path.exists():
        raise FileNotFoundError(f"Missing checksums.sha256 at {checksums_path}")

    print("Checking SHA-256 checksums of all output artifacts...")
    for item in manifest["output_files"]:
        target = Path(item["path"])
        if not target.exists():
            raise FileNotFoundError(f"Manifest output file missing: {target}")
        actual_sha = sha256(target)
        if actual_sha != item["sha256"]:
            raise ValueError(f"Checksum mismatch for {target}: expected {item['sha256']}, got {actual_sha}")
    print("✓ All artifact checksums match manifest.")

    # 2. Master Event Reference Invariants
    master_path = artifact_dir / "master_event_reference.parquet"
    master_table = pq.read_table(master_path)
    if master_table.num_rows != EXPECTED_MASTER_COUNT:
        raise ValueError(f"Master population mismatch: expected {EXPECTED_MASTER_COUNT}, got {master_table.num_rows}")

    rows = master_table.to_pylist()
    eids = [r["event_id"] for r in rows]
    if len(eids) != len(set(eids)):
        raise ValueError("Duplicate event IDs detected in master event reference!")

    # Check special state counts
    state_counts: Dict[str, int] = {}
    for r in rows:
        st = r["special_state"]
        state_counts[st] = state_counts.get(st, 0) + 1

    print("Master event population special state breakdown:")
    for st, count in sorted(state_counts.items()):
        print(f"  - {st}: {count}")

    if state_counts.get("dual_unordered") != EXPECTED_DUAL_COUNT:
        raise ValueError(f"Dual unordered count mismatch: expected {EXPECTED_DUAL_COUNT}, got {state_counts.get('dual_unordered')}")
    if state_counts.get("technical_same_type_exclusion") != EXPECTED_EXCLUDED_SAME_TYPE:
        raise ValueError(f"Excluded same type count mismatch: expected {EXPECTED_EXCLUDED_SAME_TYPE}, got {state_counts.get('technical_same_type_exclusion')}")
    if state_counts.get("ordinary_resolved_sequence_event") != EXPECTED_RESOLVED_COUNT:
        raise ValueError(f"Ordinary resolved sequence count mismatch: expected {EXPECTED_RESOLVED_COUNT}, got {state_counts.get('ordinary_resolved_sequence_event')}")
    if state_counts.get("dataset_left_edge_censored") != EXPECTED_LEFT_EDGE_COUNT:
        raise ValueError(f"Dataset left edge count mismatch: expected {EXPECTED_LEFT_EDGE_COUNT}, got {state_counts.get('dataset_left_edge_censored')}")
    if state_counts.get("dataset_right_edge_censored") != EXPECTED_RIGHT_EDGE_COUNT:
        raise ValueError(f"Dataset right edge count mismatch: expected {EXPECTED_RIGHT_EDGE_COUNT}, got {state_counts.get('dataset_right_edge_censored')}")
    if state_counts.get("dual_separator_boundary") != EXPECTED_DUAL_BOUNDARY_COUNT:
        raise ValueError(f"Dual separator boundary count mismatch: expected {EXPECTED_DUAL_BOUNDARY_COUNT}, got {state_counts.get('dual_separator_boundary')}")

    print("✓ Master population counts, special states, and uniqueness verified.")

    # 3. Verify B+C Preservation: No forced scale 0 for excluded pivots
    cont_path = artifact_dir / "reference_continuous.parquet"
    cont_table = pq.read_table(cont_path)
    cont_rows = cont_table.to_pylist()
    for r in cont_rows:
        st = r["special_state"]
        scale = r["reference__hierarchy_min_scale"]
        if st != "ordinary_resolved_sequence_event":
            if scale is not None:
                raise ValueError(f"Unresolved event {r['event_id']} ({st}) has forced scale: {scale}")
        else:
            if scale is None or not math.isfinite(scale):
                raise ValueError(f"Resolved event {r['event_id']} has missing/non-finite scale")
    print("✓ B+C semantics verified: Unresolved candidates have scale None (no forced values or semantic scale 0).")

    # 4. Sequence Reference Validation
    seq_path = artifact_dir / "bplusc_sequence_reference.parquet"
    seq_table = pq.read_table(seq_path)
    if seq_table.num_rows != EXPECTED_ALTERNATING_CANDIDATES:
        raise ValueError(f"Alternating sequence count mismatch: expected {EXPECTED_ALTERNATING_CANDIDATES}, got {seq_table.num_rows}")
    seq_rows = seq_table.to_pylist()
    seg_ids = {r["segment_id"] for r in seq_rows}
    if len(seg_ids) != EXPECTED_SEGMENTS:
        raise ValueError(f"Segment count mismatch: expected {EXPECTED_SEGMENTS}, got {len(seg_ids)}")
    print("✓ B+C segment sequence verified: 3,285 alternating candidates across 145 segments.")

    # 5. Comparison Table Consistency
    comp_path = artifact_dir / "contract_comparison.parquet"
    comp_table = pq.read_table(comp_path)
    for row in comp_table.to_pylist():
        if row["master_N"] != EXPECTED_MASTER_COUNT:
            raise ValueError(f"Comparison row {row['variant']} has master_N != {EXPECTED_MASTER_COUNT}")
        if row["resolved_N"] != EXPECTED_RESOLVED_COUNT:
            raise ValueError(f"Comparison row {row['variant']} has resolved_N != {EXPECTED_RESOLVED_COUNT}")
    print("✓ Comparison table verified: all head-to-head variants share identical denominators (N=2,867).")

    # 6. SVG Charts Existence
    plots_dir = artifact_dir / "plots"
    required_charts = [
        "b1_comp_01_clear_large_turn.svg",
        "b1_comp_02_small_local_fluctuation.svg",
        "b1_comp_03_ambiguous_middle_scale.svg",
        "b1_comp_04_dual_mediated.svg",
        "b1_comp_05_choppy_range.svg",
        "b1_comp_06_directional_move.svg",
        "b1_comp_07_calibration_2026.svg",
    ]
    for ch in required_charts:
        ch_path = plots_dir / ch
        if not ch_path.exists() or ch_path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty chart: {ch_path}")
    print("✓ All 7 representative SVG charts verified.")

    # 7. Summary Verification
    summary_path = artifact_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["master_population"] != EXPECTED_MASTER_COUNT:
        raise ValueError("Summary master population mismatch")
    if summary["ordinary_resolved_sequence_events"] != EXPECTED_RESOLVED_COUNT:
        raise ValueError("Summary resolved population mismatch")
    print("✓ summary.json verified.")
    print("\n>>> ALL VALIDATION CHECKS PASSED SUCCESSFULLY. <<<")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2I-B1 Artifact Validator")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_reference_contract_comparison"),
        help="Path to artifacts to validate",
    )
    args = parser.parse_args()
    validate_artifacts(args.artifact_dir)


if __name__ == "__main__":
    main()
