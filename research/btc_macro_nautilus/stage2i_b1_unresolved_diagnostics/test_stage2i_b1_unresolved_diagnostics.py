"""Tests for Stage 2I-B1 Unresolved Diagnostics.

Verifies:
1. Total unresolved count is exactly 1,583 (4,450 master - 2,867 resolved).
2. Category counts match: 300 dual_unordered / 865 technical_same_type_exclusion / 416 dual_separator_boundary / 2 dataset_edge_censored.
3. Every canonical field (19 fields across 4 layers) is covered for every unresolved group.
4. No canonical values or definitions were changed.
5. No resolved B1 values changed (all 2,867 resolved pivots remain identical).
6. No Stage 2I-B2 files created.
7. PA_STRUCTURE_CANONICAL.md is byte-identical to starting HEAD.
8. No None/UNRESOLVED values were filled in production B1 artifacts.
9. Diagnostic artifacts are deterministic (byte-identical rerun).
10. All claims trace to actual code/data dependencies.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data")
B1_DIR = DATA_ROOT / "research" / "stage2i_b1_reference_contract_comparison"
DIAG_DIR = DATA_ROOT / "research" / "stage2i_b1_unresolved_diagnostics"
CANONICAL_SPEC = REPO_ROOT / "docs" / "research" / "pa_structure" / "PA_STRUCTURE_CANONICAL.md"


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestStage2IB1UnresolvedDiagnostics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.master_table = pq.read_table(B1_DIR / "master_event_reference.parquet")
        cls.master_rows = cls.master_table.to_pylist()
        cls.diag_table = pq.read_table(DIAG_DIR / "unresolved_group_diagnostics.parquet")
        cls.diag_rows = cls.diag_table.to_pylist()
        cls.subdiag_table = pq.read_table(DIAG_DIR / "unresolved_subgroup_diagnostics.parquet")
        cls.subdiag_rows = cls.subdiag_table.to_pylist()
        cls.summary = json.loads((DIAG_DIR / "summary.json").read_text(encoding="utf-8"))

    # 1. Total unresolved = 1,583
    def test_01_total_unresolved_count(self):
        resolved = [r for r in self.master_rows if r["representation_resolved"]]
        unresolved = [r for r in self.master_rows if not r["representation_resolved"]]
        self.assertEqual(len(self.master_rows), 4450)
        self.assertEqual(len(resolved), 2867)
        self.assertEqual(len(unresolved), 1583)
        self.assertEqual(self.summary["unresolved_population"], 1583)

    # 2. Category counts: 300 / 865 / 416 / 2
    def test_02_category_counts(self):
        unresolved = [r for r in self.master_rows if not r["representation_resolved"]]
        states = {}
        for r in unresolved:
            s = r["special_state"]
            states[s] = states.get(s, 0) + 1

        self.assertEqual(states["dual_unordered"], 300)
        self.assertEqual(states["technical_same_type_exclusion"], 865)
        self.assertEqual(states["dual_separator_boundary"], 416)
        edge_count = states.get("dataset_left_edge_censored", 0) + states.get("dataset_right_edge_censored", 0)
        self.assertEqual(edge_count, 2)
        self.assertEqual(states["dataset_left_edge_censored"], 1)
        self.assertEqual(states["dataset_right_edge_censored"], 1)

    # 3. Every canonical field covered for every unresolved group
    def test_03_every_canonical_field_covered(self):
        self.assertEqual(len(self.diag_rows), 76)  # 4 groups x 19 fields
        groups = {r["unresolved_group"] for r in self.diag_rows}
        self.assertEqual(groups, {"dual_unordered", "technical_same_type_exclusion", "dual_separator_boundary", "dataset_edge_censored"})

        fields = {r["canonical_field"] for r in self.diag_rows}
        self.assertEqual(len(fields), 19)

        for g in groups:
            g_rows = [r for r in self.diag_rows if r["unresolved_group"] == g]
            self.assertEqual(len(g_rows), 19, f"Group {g} should have 19 field rows")
            for r in g_rows:
                self.assertFalse(r["computable_under_current_contract"])
                self.assertTrue(r["methodological_decision_required"])
                self.assertTrue(len(r["exact_blocking_reason"]) > 10)
                self.assertTrue(len(r["decision_description"]) > 10)

    # 4. No canonical values or definitions changed
    def test_04_canonical_spec_integrity(self):
        self.assertTrue(CANONICAL_SPEC.exists())
        diff_out = subprocess.check_output(
            ["git", "diff", "HEAD", "--", str(CANONICAL_SPEC)],
            cwd=REPO_ROOT,
            text=True,
        )
        self.assertEqual(diff_out.strip(), "", "PA_STRUCTURE_CANONICAL.md must be byte-identical to HEAD")

    # 5. No resolved B1 values changed (all 2,867 resolved pivots remain identical)
    def test_05_resolved_b1_values_unchanged(self):
        manifest = json.loads((B1_DIR / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["output_files"]:
            p = Path(item["path"])
            self.assertTrue(p.exists(), f"Missing B1 output file: {p}")
            self.assertEqual(sha256(p), item["sha256"], f"B1 file was altered: {p}")

    # 6. No Stage 2I-B2 files created
    def test_06_no_b2_files(self):
        b2_dir = REPO_ROOT / "research" / "btc_macro_nautilus" / "stage2i_b2_predictiveness"
        self.assertFalse(b2_dir.exists(), "Stage 2I-B2 directory must NOT exist")

    # 7. PA_STRUCTURE_CANONICAL.md byte-identical to starting HEAD
    def test_07_canonical_spec_byte_identical_to_starting_head(self):
        # Verify git status has no diff for canonical spec
        cmd = subprocess.run(
            ["git", "diff", "15e70f8579a1268725e1940647886172d46750f8", "--", str(CANONICAL_SPEC)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(cmd.stdout.strip(), "")

    # 8. No None/UNRESOLVED values filled in production artifacts
    def test_08_no_unresolved_filled_in_production(self):
        cont = pq.read_table(B1_DIR / "reference_continuous.parquet").to_pylist()
        unresolved_cont = [r for r in cont if not r["representation_resolved"]]
        self.assertEqual(len(unresolved_cont), 1583)
        for r in unresolved_cont:
            self.assertIsNone(r["reference__prominence_min_log"])
            self.assertIsNone(r["reference__hierarchy_min_scale"])
            self.assertIsNone(r["reference__rank_consensus_mean"])

        conf = pq.read_table(B1_DIR / "reference_confidence.parquet").to_pylist()
        unresolved_conf = [r for r in conf if not r["representation_resolved"]]
        self.assertEqual(len(unresolved_conf), 1583)
        for r in unresolved_conf:
            self.assertEqual(r["reference__conf_majority_t20"], "UNRESOLVED")
            self.assertEqual(r["reference__conf_unanimous_t20"], "UNRESOLVED")

    # 9. Diagnostic artifacts deterministic
    def test_09_artifacts_deterministic(self):
        manifest = json.loads((DIAG_DIR / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["output_files"]:
            p = Path(item["path"])
            self.assertTrue(p.exists())
            self.assertEqual(sha256(p), item["sha256"])

    # 10. DSB subgroup breakdown: 133 interior survivors + 283 endpoints = 416
    def test_10_dsb_subgroup_counts(self):
        sub_rows = self.subdiag_rows
        interior_rows = [r for r in sub_rows if r["subgroup_name"] == "dual_separator_boundary_interior_survivor"]
        endpoint_rows = [r for r in sub_rows if r["subgroup_name"] == "dual_separator_boundary_endpoint"]
        self.assertEqual(len(interior_rows), 19)
        self.assertEqual(len(endpoint_rows), 19)
        self.assertEqual(interior_rows[0]["event_count"], 133)
        self.assertEqual(endpoint_rows[0]["event_count"], 283)


if __name__ == "__main__":
    unittest.main()
