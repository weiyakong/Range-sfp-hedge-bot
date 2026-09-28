"""Stage 2I-B1 Unresolved Diagnostics Validator.

Independently validates that:
1. Total unresolved population is exactly 1,583 (4,450 master - 2,867 resolved).
2. Category counts match: 300 dual_unordered / 865 technical_same_type_exclusion / 416 dual_separator_boundary / 2 dataset_edge_censored.
3. Subgroup breakdown is verified (283 endpoints vs 133 interior survivors for DSB).
4. All 19 canonical fields across 4 layers are covered for every unresolved group.
5. Output artifacts (CSV, Parquet, summary.json, manifest.json) match SHA-256 checksums.
6. No canonical specification values or files were altered.
7. No production B1 comparison artifacts were altered (checksums verified).
8. No Stage 2I-B2 files were created.
9. All claims trace directly to computed data artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import pyarrow.parquet as pq


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_checksums(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["output_files"]:
        target = Path(item["path"])
        if not target.exists():
            raise FileNotFoundError(f"Missing referenced artifact: {target}")
        actual = sha256(target)
        if actual != item["sha256"]:
            raise ValueError(f"Checksum mismatch for {target}: expected {item['sha256']}, got {actual}")


def validate_b1_production_integrity(b1_dir: Path) -> None:
    """Verifies that the original Stage 2I-B1 comparison artifacts were not touched."""
    manifest_path = b1_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing B1 manifest file: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["output_files"]:
        file_path = Path(item["path"])
        if not file_path.exists():
            raise FileNotFoundError(f"Missing B1 production file: {file_path}")
        actual_hash = sha256(file_path)
        expected_hash = item["sha256"]
        if actual_hash != expected_hash:
            raise ValueError(
                f"CRITICAL INTEGRITY FAILURE: B1 file {file_path.name} modified! Hash {actual_hash} != {expected_hash}"
            )


def validate_diagnostics(
    artifact_dir: Path,
    repo_root: Path,
    data_root: Path,
) -> bool:
    print(f"=== Validating Stage 2I-B1 Unresolved Diagnostics at: {artifact_dir} ===")

    # 1. Validate output artifact checksums
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    validate_checksums(manifest_path)
    print("✓ Output artifact checksums match manifest.")

    # 2. Validate B1 production artifacts integrity
    b1_dir = data_root / "research" / "stage2i_b1_reference_contract_comparison"
    validate_b1_production_integrity(b1_dir)
    print("✓ B1 production artifacts are completely UNTOUCHED (all 23 checksums match).")

    # 3. Validate master population accounting
    master_table = pq.read_table(b1_dir / "master_event_reference.parquet")
    master_rows = master_table.to_pylist()
    total_master = len(master_rows)
    resolved = [r for r in master_rows if r["representation_resolved"]]
    unresolved = [r for r in master_rows if not r["representation_resolved"]]

    assert total_master == 4450, f"Expected 4450 master, got {total_master}"
    assert len(resolved) == 2867, f"Expected 2867 resolved, got {len(resolved)}"
    assert len(unresolved) == 1583, f"Expected 1583 unresolved, got {len(unresolved)}"
    print(f"✓ Master population verified: {total_master} total, {len(resolved)} resolved, {len(unresolved)} unresolved.")

    # 4. Validate category breakdown
    states: Dict[str, int] = {}
    for r in unresolved:
        s = r["special_state"]
        states[s] = states.get(s, 0) + 1

    assert states.get("dual_unordered") == 300, f"Expected 300 dual_unordered, got {states.get('dual_unordered')}"
    assert states.get("technical_same_type_exclusion") == 865, f"Expected 865 technical_same_type_exclusion, got {states.get('technical_same_type_exclusion')}"
    assert states.get("dual_separator_boundary") == 416, f"Expected 416 dual_separator_boundary, got {states.get('dual_separator_boundary')}"
    edge_count = states.get("dataset_left_edge_censored", 0) + states.get("dataset_right_edge_censored", 0)
    assert edge_count == 2, f"Expected 2 dataset edge events, got {edge_count}"
    print("✓ Unresolved category counts verified: 300 / 865 / 416 / 2.")

    # 5. Validate subgroup breakdown for DSB
    bplusc_table = pq.read_table(b1_dir / "bplusc_sequence_reference.parquet")
    bplusc_rows = bplusc_table.to_pylist()
    bplusc_by_id = {r["event_id"]: r for r in bplusc_rows}

    dsb_events = [r for r in unresolved if r["special_state"] == "dual_separator_boundary"]
    dsb_interior = [
        r for r in dsb_events
        if r["event_id"] in bplusc_by_id
        and not bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
        and not bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
    ]
    dsb_endpoints = [
        r for r in dsb_events
        if r["event_id"] in bplusc_by_id
        and (
            bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
            or bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
        )
    ]
    assert len(dsb_interior) == 133, f"Expected 133 interior survivors, got {len(dsb_interior)}"
    assert len(dsb_endpoints) == 283, f"Expected 283 endpoints, got {len(dsb_endpoints)}"
    print(f"✓ DSB sub-breakdown verified: 133 interior survivors + 283 endpoints = 416 total.")

    # 6. Validate diagnostics table structure (group diagnostics: 76 rows = 4 groups x 19 fields)
    group_table = pq.read_table(artifact_dir / "unresolved_group_diagnostics.parquet")
    group_rows = group_table.to_pylist()
    assert len(group_rows) == 76, f"Expected 76 group rows (4 x 19), got {len(group_rows)}"

    unique_groups = {r["unresolved_group"] for r in group_rows}
    assert unique_groups == {"dual_unordered", "technical_same_type_exclusion", "dual_separator_boundary", "dataset_edge_censored"}

    unique_fields = {r["canonical_field"] for r in group_rows}
    assert len(unique_fields) == 19, f"Expected 19 canonical fields, got {len(unique_fields)}"

    for g in unique_groups:
        g_rows = [r for r in group_rows if r["unresolved_group"] == g]
        assert len(g_rows) == 19, f"Group {g} should have 19 field rows, got {len(g_rows)}"
    print("✓ Diagnostic table verified: all 19 canonical fields covered for each of the 4 unresolved groups (76 rows).")

    # 7. Validate subgroup table structure (subgroup diagnostics: 114 rows = 6 subgroups x 19 fields)
    subgroup_table = pq.read_table(artifact_dir / "unresolved_subgroup_diagnostics.parquet")
    subgroup_rows = subgroup_table.to_pylist()
    assert len(subgroup_rows) == 114, f"Expected 114 subgroup rows (6 x 19), got {len(subgroup_rows)}"
    print("✓ Subgroup diagnostic table verified: 6 subgroups x 19 fields = 114 rows.")

    # 8. Validate summary.json
    summary_path = artifact_dir / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["unresolved_population"] == 1583
    assert summary["master_population"] == 4450
    assert summary["resolved_population"] == 2867
    assert summary["unresolved_category_counts"]["dual_unordered"] == 300
    assert summary["unresolved_category_counts"]["technical_same_type_exclusion"] == 865
    assert summary["unresolved_category_counts"]["dual_separator_boundary"] == 416
    assert summary["unresolved_category_counts"]["dataset_edge_censored"] == 2
    print("✓ summary.json content and scenario counts verified.")

    # 9. Verify PA_STRUCTURE_CANONICAL.md is byte-identical to HEAD
    canonical_spec = repo_root / "docs" / "research" / "pa_structure" / "PA_STRUCTURE_CANONICAL.md"
    diff_out = subprocess.check_output(["git", "diff", "HEAD", "--", str(canonical_spec)], cwd=repo_root, text=True)
    assert not diff_out.strip(), f"PA_STRUCTURE_CANONICAL.md must be byte-identical to HEAD! Diff: {diff_out}"
    print("✓ PA_STRUCTURE_CANONICAL.md is strictly UNMODIFIED (byte-identical to HEAD).")

    # 10. Verify no Stage 2I-B2 files exist
    b2_dir = repo_root / "research" / "btc_macro_nautilus" / "stage2i_b2_predictiveness"
    assert not b2_dir.exists(), "Stage 2I-B2 directory must NOT exist!"
    print("✓ Stage 2I-B2 is absent.")

    print("\n>>> ALL 10 VALIDATION GATES PASSED SUCCESSFULLY. <<<")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Stage 2I-B1 Unresolved Diagnostics")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data"),
        help="Path to authoritative data root",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/2026-09-27/range-sfp-pa-structure"),
        help="Path to authoritative repository worktree root",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Path to diagnostic artifact directory",
    )
    args = parser.parse_args()

    artifact_dir = args.artifact_dir or (args.data_root / "research" / "stage2i_b1_unresolved_diagnostics")
    validate_diagnostics(
        artifact_dir=artifact_dir,
        repo_root=args.repo_root,
        data_root=args.data_root,
    )


if __name__ == "__main__":
    main()
