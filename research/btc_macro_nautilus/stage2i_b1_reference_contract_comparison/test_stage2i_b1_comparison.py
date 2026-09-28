#!/usr/bin/env python3
"""Unit and Contract Tests for Stage 2I-B1 Reference Contract Comparison.

Implements all 13 required test suites from Section 19 of the specification using standard unittest.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import subprocess
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
        self.assertAlmostEqual(h_row["macro_overlap_ge15pct"], 61.0 / 104.0, places=4, msg="macro_overlap_ge15pct must be dynamically computed Jaccard (61/104)")

    # Test 14: computed macro overlap values from sets
    def test_14_computed_macro_overlap_from_sets(self):
        coarse_table = pq.read_table(ARTIFACT_DIR / "coarse_structure_overlap.parquet")
        rows = coarse_table.to_pylist()
        self.assertEqual(len(rows), 2)
        r15 = next(r for r in rows if r["threshold_pct"] == 15)
        r25 = next(r for r in rows if r["threshold_pct"] == 25)
        self.assertEqual(r15["min_hierarchy_count"], 61)
        self.assertEqual(r15["geo_hierarchy_count"], 104)
        self.assertEqual(r15["intersection_count"], 61)
        self.assertAlmostEqual(r15["jaccard_similarity"], 61.0 / 104.0, places=4)
        self.assertEqual(r15["containment_min_in_geo"], 1.0)
        self.assertEqual(r25["min_hierarchy_count"], 22)
        self.assertEqual(r25["geo_hierarchy_count"], 35)
        self.assertEqual(r25["intersection_count"], 22)
        self.assertAlmostEqual(r25["jaccard_similarity"], 22.0 / 35.0, places=4)
        self.assertEqual(r25["containment_min_in_geo"], 1.0)

    # Test 15: valid denominators in all comparisons
    def test_15_valid_denominators(self):
        comp_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        for r in comp_table.to_pylist():
            self.assertEqual(r["master_N"], 4450)
            self.assertEqual(r["resolved_N"], 2867)
            self.assertAlmostEqual(r["coverage"], 2867 / 4450, places=4)
            self.assertAlmostEqual(r["censored_share"], 418 / 4450, places=4)

    # Test 16: reproducible >=15% and >=25% comparisons
    def test_16_reproducible_coarse_comparisons(self):
        cont_table = pq.read_table(ARTIFACT_DIR / "reference_continuous.parquet")
        resolved = [r for r in cont_table.to_pylist() if r["representation_resolved"]]
        s_min_15 = {r["event_id"] for r in resolved if r["reference__hierarchy_min_scale"] >= 0.15}
        s_geo_15 = {r["event_id"] for r in resolved if r["reference__hierarchy_geo_scale"] >= 0.15}
        s_min_25 = {r["event_id"] for r in resolved if r["reference__hierarchy_min_scale"] >= 0.25}
        s_geo_25 = {r["event_id"] for r in resolved if r["reference__hierarchy_geo_scale"] >= 0.25}
        self.assertEqual(len(s_min_15), 61)
        self.assertEqual(len(s_geo_15), 104)
        self.assertTrue(s_min_15.issubset(s_geo_15))
        self.assertEqual(len(s_min_25), 22)
        self.assertEqual(len(s_geo_25), 35)
        self.assertTrue(s_min_25.issubset(s_geo_25))

    # Test 17: disagreement range matches empirical data
    def test_17_disagreement_range_matches_data(self):
        diag_table = pq.read_table(ARTIFACT_DIR / "disagreement_scale_diagnostics.parquet")
        rows = diag_table.to_pylist()
        maj_20 = next(r for r in rows if r["tail_size_pct"] == 20 and r["confidence_rule"] == "majority")
        self.assertEqual(maj_20["ambiguous_count"], 1767)
        self.assertEqual(maj_20["count_1_5_to_5pct"], 1593)
        self.assertEqual(maj_20["count_5_to_10pct"], 165)
        self.assertEqual(maj_20["count_ge_10pct"], 9)
        self.assertFalse(maj_20["strictly_confined_1_5_to_5pct"])

    # Test 18: no zero false tail claims
    def test_18_no_zero_false_tail_claims(self):
        comp_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        for r in comp_table.to_pylist():
            self.assertNotIn("zero false tail", r["information_retention_descriptors"].lower())
            self.assertNotIn("zero false tail", r["notes"].lower())
        claim_table = pq.read_table(ARTIFACT_DIR / "claim_validation.parquet")
        clm1 = next(r for r in claim_table.to_pylist() if r["claim_id"] == "CLM-01-ZERO-FALSE-TAIL")
        self.assertEqual(clm1["audited_verdict"], "REJECTED_METHODOLOGICALLY")

    # Test 19: no micro scale promotions
    def test_19_no_micro_scale_promotions(self):
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        for r in master_table.to_pylist():
            self.assertNotEqual(r.get("special_state"), "micro")
            self.assertNotEqual(r.get("exclusion_reason"), "micro")

    # Test 20: no independent families phrasing
    def test_20_no_independent_families_phrasing(self):
        comp_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        for r in comp_table.to_pylist():
            self.assertNotIn("independent families", r["cross_design_agreement"].lower())
            self.assertNotIn("independent evidence", r["cross_design_agreement"].lower())

    # Test 21: no preferred winner or canonical contract chosen
    def test_21_no_preferred_contract_chosen(self):
        comp_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        for r in comp_table.to_pylist():
            self.assertNotIn("preferred", r["notes"].lower())
            self.assertNotIn("recommended canonical", r["notes"].lower())

    # Test 22: no censored double count
    def test_22_no_censored_double_count(self):
        summary_table = pq.read_table(ARTIFACT_DIR / "contract_comparison.parquet")
        for r in summary_table.to_pylist():
            self.assertEqual(r["censored_share"], 418.0 / 4450.0)
            self.assertNotEqual(r["censored_share"], 420.0 / 4450.0)

    # Test 23: PA_STRUCTURE_CANONICAL.md is untouched
    def test_23_canonical_untouched(self):
        canonical_path = MODULE_PATH.parents[2] / "PA_STRUCTURE_CANONICAL.md"
        if canonical_path.exists():
            content = canonical_path.read_text(encoding="utf-8")
            self.assertNotIn("Stage 2I-B1", content)
            self.assertNotIn("Stage 2I-B2", content)

    # Test 24: Stage 2I-B2 is absent
    def test_24_stage_b2_absent(self):
        b2_dir = MODULE_PATH.parent.parent / "stage2i_b2_predictiveness"
        self.assertFalse(b2_dir.exists(), "Stage 2I-B2 directory must NOT exist")

    # Test 25: all audit diagnostic artifacts exist
    def test_25_audit_artifacts_exist(self):
        for name in ("coarse_structure_overlap", "disagreement_scale_diagnostics", "claim_validation"):
            p_file = ARTIFACT_DIR / f"{name}.parquet"
            c_file = ARTIFACT_DIR / f"{name}.csv"
            self.assertTrue(p_file.exists(), f"Missing {p_file}")
            self.assertTrue(c_file.exists(), f"Missing {c_file}")
            self.assertGreater(p_file.stat().st_size, 0)
            self.assertGreater(c_file.stat().st_size, 0)

    # Test 26: methodology wording discipline
    def test_26_methodology_wording_discipline(self):
        repo_root = Path(__file__).resolve().parents[3]
        doc_path = repo_root / "docs" / "research" / "stage2i_b1_reference_contract_comparison.md"
        self.assertTrue(doc_path.exists(), f"Missing {doc_path}")
        content = doc_path.read_text(encoding="utf-8")

        # 1. Report does NOT state B1 is selected in B2
        self.assertNotIn("deferred to Stage 2I-B2", content)
        self.assertNotIn("chosen before Stage 2I-B2", content)

        # 2. Report explicitly states B1 contract is selected/refined BEFORE B2 is launched
        self.assertIn("must be selected/refined before Stage 2I-B2 is launched", content)

        # 3. No global theorem "Min ⊆ Geo for every θ"
        self.assertNotIn("proves that the coarse macro structure of the Min hierarchy is a mathematical subset", content)
        self.assertNotIn("strictly contained within the Geometric-cost macro structure for any given scale threshold", content)

        # 4. Exact empirical containment verified
        self.assertIn("61/61 at $\\ge 15\\%$", content)
        self.assertIn("22/22 at $\\ge 25\\%$", content)
        overlap_table = pq.read_table(ARTIFACT_DIR / "coarse_structure_overlap.parquet")
        rows = {r["threshold_pct"]: r for r in overlap_table.to_pylist()}
        self.assertEqual(rows[15]["min_hierarchy_count"], 61)
        self.assertEqual(rows[15]["geo_hierarchy_count"], 104)
        self.assertEqual(rows[15]["intersection_count"], 61)
        self.assertEqual(rows[25]["min_hierarchy_count"], 22)
        self.assertEqual(rows[25]["geo_hierarchy_count"], 35)
        self.assertEqual(rows[25]["intersection_count"], 22)

        # 5. Volatility-normalized metric is NOT called invariant
        self.assertNotIn("remains remarkably invariant across regimes: 2.10x, 2.00x, 1.87x", content)
        self.assertIn("substantially reduces volatility-regime drift", content)

        # 6. Ordinal boundaries: "not detected / not supported", not universally refuted
        self.assertIn("NOT DETECTED / NOT SUPPORTED IN TESTED DIAGNOSTICS", content)
        self.assertNotIn("UNIVERSALLY REFUTED", content)

        # 7. Single representation: "no tested representation dominated", not universally refuted
        self.assertIn("NO TESTED SINGLE REPRESENTATION DOMINATED", content)
        self.assertNotIn("single representation is universally impossible", content.lower())

        # 8. Layered representation is now the canonical B1 contract (user decision recorded)
        self.assertIn("COMPATIBLE CANDIDATE ARCHITECTURE", content)
        self.assertIn("USER-SELECTED AS CANONICAL B1 CONTRACT", content)
        self.assertNotIn("layered representation is the canonical architecture", content.lower())

        # 9. PA_STRUCTURE_CANONICAL.md exists and records the layered contract decision
        canonical_path = repo_root / "docs" / "research" / "pa_structure" / "PA_STRUCTURE_CANONICAL.md"
        self.assertTrue(canonical_path.exists())
        canonical_content = canonical_path.read_text(encoding="utf-8")
        self.assertIn("FIXED (LAYERED)", canonical_content)
        self.assertIn("7.8", canonical_content)

        # 10. Stage B2 directory is absent
        b2_dir = Path(__file__).resolve().parents[1] / "stage2i_b2_predictiveness"
        self.assertFalse(b2_dir.exists(), "Stage 2I-B2 directory must NOT exist")

    # Test 27: B1 layered contract is fixed with correct 4-layer structure
    def test_27_b1_layered_contract_fixed(self):
        repo_root = Path(__file__).resolve().parents[3]
        canonical_path = repo_root / "docs" / "research" / "pa_structure" / "PA_STRUCTURE_CANONICAL.md"
        self.assertTrue(canonical_path.exists(), f"Missing {canonical_path}")
        content = canonical_path.read_text(encoding="utf-8")

        # 1. Canonical B1 contract is LAYERED
        self.assertIn("FIXED (LAYERED)", content)
        self.assertIn("7.8", content)

        # 2. Canonical enumerates exactly 4 logical layers by heading
        self.assertIn("Layer 1 — Structural Components", content)
        self.assertIn("Layer 2 — Continuous Ordering", content)
        self.assertIn("Layer 3 — Structural Survival Scale", content)
        self.assertIn("Layer 4 — Cross-View Agreement States", content)

        # 3. Continuous layer includes CONT-RANK, CONT-CONSENSUS-MEAN, CONT-CONSENSUS-MEDIAN
        self.assertIn("reference__rank_consensus_mean", content)
        self.assertIn("reference__rank_consensus_median", content)
        self.assertIn("reference__rank_prominence_min", content)

        # 4. Survival layer = ORD-SURVIVAL (canonical field name)
        self.assertIn("reference__ord_survival_scale", content)
        # ORD-Q3/Q4/Q5 not in canonical contract
        self.assertNotIn("ORD-Q3/Q4/Q5 are part of the canonical", content.lower())

        # 5. Agreement layer includes all 8 variants: 10/20/25/30 × unanimous/majority
        for tail in ("t10", "t20", "t25", "t30"):
            self.assertIn(f"reference__conf_unanimous_{tail}", content)
            self.assertIn(f"reference__conf_majority_{tail}", content)

        # 6. No preferred tail
        self.assertNotIn("preferred tail", content.lower())
        self.assertNotIn("preferred tail size", content.lower())

        # 7. Q3/Q4/Q5 are diagnostic only, not canonical contract
        self.assertIn("ORD-Q3, ORD-Q4, ORD-Q5", content)
        self.assertIn("NOT part of the canonical layered B1 contract", content)

        # 8. Unresolved states preserved (None, not 0/False)
        self.assertIn("UNRESOLVED", content)
        self.assertIn("None", content)

        # 9. B1 retrospective / B2 causal separation preserved
        self.assertIn("must never be used as B2 predictor inputs or live inference features", content)

        # 10. Stage B2 directory is absent
        b2_dir = Path(__file__).resolve().parents[1] / "stage2i_b2_predictiveness"
        self.assertFalse(b2_dir.exists(), "Stage 2I-B2 directory must NOT exist")

        # Verify artifact join structure: all 4 layer artifacts exist
        for artifact_name in (
            "reference_continuous.parquet",
            "reference_ordinal.parquet",
            "reference_confidence.parquet",
            "master_event_reference.parquet",
        ):
            self.assertTrue((ARTIFACT_DIR / artifact_name).exists(), f"Missing {artifact_name}")

        # Verify Layer 1 fields exist in reference_continuous.parquet
        cont_table = pq.read_table(ARTIFACT_DIR / "reference_continuous.parquet")
        cont_schema_names = set(cont_table.schema.names)
        for field in (
            "reference__prominence_min_log",
            "reference__prominence_geo_log",
            "reference__prominence_balance",
            "reference__prominence_vol_norm",
            "reference__hierarchy_min_scale",
            "reference__hierarchy_geo_scale",
        ):
            self.assertIn(field, cont_schema_names, f"Missing Layer 1 field: {field}")

        # Verify Layer 2 fields exist
        for field in (
            "reference__rank_prominence_min",
            "reference__rank_hierarchy_min",
            "reference__rank_consensus_mean",
            "reference__rank_consensus_median",
        ):
            self.assertIn(field, cont_schema_names, f"Missing Layer 2 field: {field}")

        # Verify Layer 3 field exists in reference_ordinal.parquet
        ord_table = pq.read_table(ARTIFACT_DIR / "reference_ordinal.parquet")
        self.assertIn("reference__ord_survival_scale", set(ord_table.schema.names))

        # Verify Layer 4 fields exist in reference_confidence.parquet
        conf_table = pq.read_table(ARTIFACT_DIR / "reference_confidence.parquet")
        conf_schema_names = set(conf_table.schema.names)
        for tail in ("t10", "t20", "t25", "t30"):
            for rule in ("unanimous", "majority"):
                field = f"reference__conf_{rule}_{tail}"
                self.assertIn(field, conf_schema_names, f"Missing Layer 4 field: {field}")

        # Verify unresolved events carry UNRESOLVED state (spot-check Layer 4 on non-resolved rows)
        conf_rows = conf_table.to_pylist()
        unresolved_rows = [r for r in conf_rows if not r["representation_resolved"]]
        self.assertGreater(len(unresolved_rows), 0, "Expected unresolved rows in confidence artifact")
        sample = unresolved_rows[0]
        for tail in ("t10", "t20", "t25", "t30"):
            for rule in ("unanimous", "majority"):
                field = f"reference__conf_{rule}_{tail}"
                self.assertEqual(sample[field], "UNRESOLVED", f"Unresolved row should have UNRESOLVED in {field}")

        # Verify master population size
        master_table = pq.read_table(ARTIFACT_DIR / "master_event_reference.parquet")
        self.assertEqual(master_table.num_rows, 4450)

        # Verify all 4 artifacts share same number of rows
        self.assertEqual(cont_table.num_rows, 4450)
        self.assertEqual(ord_table.num_rows, 4450)
        self.assertEqual(conf_table.num_rows, 4450)


if __name__ == "__main__":
    unittest.main()


