#!/usr/bin/env python3
"""Unit and Contract Tests for Stage 2I-B1 Reference Contract Comparison.

Implements all 13 required test suites from Section 19 of the specification using standard unittest.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

import pyarrow.parquet as pq

MODULE_PATH = Path(__file__).with_name("build_stage2i_b1_comparison.py")
SPEC = importlib.util.spec_from_file_location("b1_comparison", MODULE_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

EXPECTED_MASTER_COUNT = 4450
EXPECTED_DUAL_COUNT = 300
EXPECTED_EXCLUDED_SAME_TYPE = 865
EXPECTED_RESOLVED_COUNT = 2867
EXPECTED_LEFT_EDGE_COUNT = 1
EXPECTED_RIGHT_EDGE_COUNT = 1
EXPECTED_DUAL_BOUNDARY_COUNT = 416
EXPECTED_ALTERNATING_CANDIDATES = 3285
EXPECTED_SEGMENTS = 145

DATA_ROOT = Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data")
STAGE_A_DIR = DATA_ROOT / "research" / "stage2i_a_raw_4h_pivots"
ARTIFACT_DIR = DATA_ROOT / "research" / "stage2i_b1_reference_contract_comparison"


class TestStage2IB1Comparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candles, cls.c_sha = MODULE._load_candles(DATA_ROOT)
        cls.events, cls.raw_rows, cls.a_sha = MODULE._load_pivots(STAGE_A_DIR)
        cls.scales = MODULE.local_volatility_scales(cls.candles, cls.events)

    # Test 1: source population invariance
    def test_01_source_population_invariance(self):
        self.assertEqual(len(self.events), EXPECTED_MASTER_COUNT, "Master population must have exactly 4,450 events")
        eids = [e.event_id for e in self.events]
        self.assertEqual(len(eids), len(set(eids)), "No duplicate IDs allowed in source population")

    # Test 2: event-ID invariance
    def test_02_event_id_invariance(self):
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        master_ids = master_table["event_id"].to_pylist()
        source_ids = [e.event_id for e in self.events]
        self.assertEqual(master_ids, source_ids, "Master event IDs must match Stage 2I-A source IDs exactly in order and identity")

    # Test 3: B+C dual-barrier behavior
    def test_03_bc_dual_barrier_behavior(self):
        ordered = sorted(self.events, key=lambda e: (e.bar_index, e.timestamp, e.event_id))
        dual_bars = {e.bar_index for e in self.events if e.is_dual}
        self.assertEqual(len(dual_bars), 150, "Expected exactly 150 dual candles")
        self.assertEqual(sum(e.is_dual for e in self.events), EXPECTED_DUAL_COUNT, "Expected exactly 300 dual events")

        # Verify timeline is separated by dual bars
        timeline = []
        for e in ordered:
            if e.is_dual:
                if not timeline or timeline[-1] != ("DUAL", e.bar_index, None):
                    timeline.append(("DUAL", e.bar_index, None))
            else:
                timeline.append(("PIVOT", e.bar_index, e))

        segments = []
        cur = []
        for item_type, _, e_obj in timeline:
            if item_type == "DUAL":
                if cur:
                    segments.append(cur)
                    cur = []
            else:
                cur.append(e_obj)
        if cur:
            segments.append(cur)
        self.assertEqual(len(segments), EXPECTED_SEGMENTS, f"Expected {EXPECTED_SEGMENTS} non-dual segments separated by dual barriers")

    # Test 4: no hierarchy edge across dual separator
    def test_04_no_hierarchy_edge_across_dual_separator(self):
        seq_table = pq.read_table(ARTIFACT_DIR / "bplusc_sequence_reference.parquet")
        seq_rows = seq_table.to_pylist()
        for r in seq_rows:
            if r["is_segment_left_boundary"]:
                self.assertIsNone(r["left_neighbor_event_id"], f"Segment left boundary {r['event_id']} must have no left neighbor across dual")
            if r["is_segment_right_boundary"]:
                self.assertIsNone(r["right_neighbor_event_id"], f"Segment right boundary {r['event_id']} must have no right neighbor across dual")

    # Test 5: same-type preservation semantics
    def test_05_same_type_preservation_semantics(self):
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        rows = master_table.to_pylist()
        excluded = [r for r in rows if r["excluded_from_alternating_sequence"]]
        self.assertEqual(len(excluded), EXPECTED_EXCLUDED_SAME_TYPE, f"Expected exactly {EXPECTED_EXCLUDED_SAME_TYPE} excluded same-type pivots")
        for r in excluded:
            self.assertEqual(r["special_state"], "technical_same_type_exclusion")
            self.assertEqual(r["exclusion_reason"], "same_type_prepass")
            self.assertFalse(r["representation_resolved"])

        # Verify no scale 0 forced value in continuous dataset
        cont_table = pq.read_table(ARTIFACT_DIR / "reference_continuous.parquet")
        cont_by_id = {r["event_id"]: r for r in cont_table.to_pylist()}
        for r in excluded:
            c_row = cont_by_id[r["event_id"]]
            self.assertIsNone(c_row["reference__hierarchy_min_scale"], "Technical same-type exclusion must NOT have scale 0 or forced value")

    # Test 6: unresolved-state preservation
    def test_06_unresolved_state_preservation(self):
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        rows = master_table.to_pylist()
        unresolved = [r for r in rows if not r["representation_resolved"]]
        self.assertEqual(len(unresolved), EXPECTED_MASTER_COUNT - EXPECTED_RESOLVED_COUNT)
        for r in unresolved:
            self.assertIn(
                r["special_state"],
                (
                    "dual_unordered",
                    "technical_same_type_exclusion",
                    "dataset_left_edge_censored",
                    "dataset_right_edge_censored",
                    "dual_separator_boundary",
                ),
            )

    # Test 7: continuous deterministic output
    def test_07_continuous_deterministic_output(self):
        cont_table = pq.read_table(ARTIFACT_DIR / "reference_continuous.parquet")
        resolved_scales = [
            r["reference__hierarchy_min_scale"]
            for r in cont_table.to_pylist()
            if r["representation_resolved"]
        ]
        self.assertEqual(len(resolved_scales), EXPECTED_RESOLVED_COUNT)
        self.assertTrue(all(s is not None and math.isfinite(s) and s >= 0 for s in resolved_scales))
        resolved_ranks = [
            r["reference__rank_hierarchy_min"]
            for r in cont_table.to_pylist()
            if r["representation_resolved"]
        ]
        self.assertGreater(min(resolved_ranks), 0.0)
        self.assertEqual(max(resolved_ranks), 1.0)

    # Test 8: ordinal deterministic mapping
    def test_08_ordinal_deterministic_mapping(self):
        ord_table = pq.read_table(ARTIFACT_DIR / "reference_ordinal.parquet")
        rows = ord_table.to_pylist()
        resolved_ord = [r for r in rows if r["representation_resolved"]]
        self.assertEqual(len(resolved_ord), EXPECTED_RESOLVED_COUNT)
        for r in resolved_ord:
            self.assertTrue(0 <= r["reference__ord_survival_scale"] <= 10)
            self.assertIn(r["reference__ord_q3_band"], ("Q1_lower", "Q2_middle", "Q3_upper"))
            self.assertIn(r["reference__ord_q4_band"], ("Q1", "Q2", "Q3", "Q4"))
            self.assertIn(r["reference__ord_q5_band"], ("Q1", "Q2", "Q3", "Q4", "Q5"))

    # Test 9: confidence deterministic mapping
    def test_09_confidence_deterministic_mapping(self):
        conf_table = pq.read_table(ARTIFACT_DIR / "reference_confidence.parquet")
        rows = conf_table.to_pylist()
        for r in rows:
            if r["representation_resolved"]:
                for col in (
                    "reference__conf_unanimous_t10",
                    "reference__conf_majority_t10",
                    "reference__conf_unanimous_t20",
                    "reference__conf_majority_t20",
                    "reference__conf_unanimous_t25",
                    "reference__conf_majority_t25",
                    "reference__conf_unanimous_t30",
                    "reference__conf_majority_t30",
                ):
                    self.assertIn(r[col], ("STRONG", "WEAK", "AMBIGUOUS"))
            else:
                for col in (
                    "reference__conf_unanimous_t10",
                    "reference__conf_majority_t10",
                    "reference__conf_unanimous_t20",
                    "reference__conf_majority_t20",
                    "reference__conf_unanimous_t25",
                    "reference__conf_majority_t25",
                    "reference__conf_unanimous_t30",
                    "reference__conf_majority_t30",
                ):
                    self.assertEqual(r[col], "UNRESOLVED")

    # Test 10: censored handling
    def test_10_censored_handling(self):
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        rows = master_table.to_pylist()
        left_edges = [r for r in rows if r["dataset_left_edge_censored"]]
        right_edges = [r for r in rows if r["dataset_right_edge_censored"]]
        dual_bounds = [r for r in rows if r["special_state"] == "dual_separator_boundary"]
        self.assertEqual(len(left_edges), 1)
        self.assertEqual(len(right_edges), 1)
        self.assertEqual(len(dual_bounds), EXPECTED_DUAL_BOUNDARY_COUNT)
        self.assertEqual(left_edges[0]["event_id"], "P4H_000006_HIGH")
        self.assertEqual(right_edges[0]["event_id"], "P4H_015442_LOW")

    # Test 11: no forced values for unresolved candidates
    def test_11_no_forced_values_for_unresolved(self):
        cont_table = pq.read_table(ARTIFACT_DIR / "reference_continuous.parquet")
        ord_table = pq.read_table(ARTIFACT_DIR / "reference_ordinal.parquet")
        for r in cont_table.to_pylist():
            if not r["representation_resolved"]:
                self.assertIsNone(r["reference__hierarchy_min_scale"])
                self.assertIsNone(r["reference__hierarchy_geo_scale"])
                self.assertIsNone(r["reference__hierarchy_vol_scale"])
                self.assertIsNone(r["reference__prominence_min_log"])
                self.assertIsNone(r["reference__rank_hierarchy_min"])
        for r in ord_table.to_pylist():
            if not r["representation_resolved"]:
                self.assertIsNone(r["reference__ord_survival_scale"])
                self.assertIsNone(r["reference__ord_q3_band"])

    # Test 12: comparison denominator consistency
    def test_12_comparison_denominator_consistency(self):
        comp_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        rows = comp_table.to_pylist()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertEqual(r["master_N"], EXPECTED_MASTER_COUNT, "master_N must be 4,450 for all comparisons")
            self.assertEqual(r["resolved_N"], EXPECTED_RESOLVED_COUNT, "resolved_N must be 2,867 for all comparisons")
            self.assertAlmostEqual(r["coverage"], EXPECTED_RESOLVED_COUNT / EXPECTED_MASTER_COUNT, places=5)

    # Test 13: parameter sweep reproducibility
    def test_13_parameter_sweep_reproducibility(self):
        param_table = pq.read_table(ARTIFACT_DIR / "parameter_sensitivity.parquet")
        rows = param_table.to_pylist()
        self.assertGreaterEqual(len(rows), 7)
        h_row = next(r for r in rows if r["comparison_dimension"] == "Hierarchy Cost Formulation")
        self.assertGreater(h_row["rank_correlation"], 0.95, "Hierarchy min and geo must have r > 0.95")
        self.assertEqual(h_row["macro_overlap_ge15pct"], 1.0, "Coarse macro structure must be invariant")


if __name__ == "__main__":
    unittest.main()
