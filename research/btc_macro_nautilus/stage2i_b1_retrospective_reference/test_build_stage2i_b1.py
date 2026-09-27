from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_stage2i_b1.py")
SPEC = importlib.util.spec_from_file_location("stage2i_b1", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def pivot(
    index: int,
    kind: str,
    price: float,
    *,
    dual: bool = False,
    suffix: str = "",
) -> object:
    return MODULE.PivotEvent(
        event_id=f"P{index:03d}_{kind}{suffix}",
        bar_index=index,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index),
        pivot_type=kind,
        price=price,
        is_dual=dual,
    )


class Stage2IB1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            pivot(0, "LOW", 100.0),
            pivot(2, "HIGH", 110.0),
            pivot(4, "HIGH", 112.0),
            pivot(6, "LOW", 106.0),
            pivot(8, "HIGH", 120.0),
            pivot(10, "LOW", 108.0),
        ]

    def test_same_type_neighbors_keep_more_extreme_event(self) -> None:
        prepared = MODULE.prepare_sequence(self.events, dual_mode="deferred")
        self.assertEqual([item.event_id for item in prepared.sequence], [
            "P000_LOW", "P004_HIGH", "P006_LOW", "P008_HIGH", "P010_LOW"
        ])
        self.assertEqual(prepared.prepass_removed["P002_HIGH"], "same_type_less_extreme")

    def test_duals_are_deferred_without_fabricated_temporal_order(self) -> None:
        duals = [
            pivot(0, "LOW", 100.0),
            pivot(2, "HIGH", 113.0, dual=True),
            pivot(2, "LOW", 95.0, dual=True, suffix="B"),
            pivot(4, "HIGH", 120.0),
        ]
        prepared = MODULE.prepare_sequence(duals, dual_mode="deferred")
        self.assertNotIn("P002_HIGH", {item.event_id for item in prepared.sequence})
        self.assertNotIn("P002_LOWB", {item.event_id for item in prepared.sequence})
        self.assertEqual(set(prepared.deferred_duals), {"P002_HIGH", "P002_LOWB"})
        self.assertTrue(all(
            left.bar_index < right.bar_index
            for left, right in zip(prepared.sequence, prepared.sequence[1:])
        ))

    def test_hierarchy_is_deterministic_monotone_and_marks_edges(self) -> None:
        prepared = MODULE.prepare_sequence(self.events, dual_mode="deferred")
        first = MODULE.hierarchical_simplification(prepared, cost_mode="minimum_log_excursion")
        second = MODULE.hierarchical_simplification(prepared, cost_mode="minimum_log_excursion")
        self.assertEqual(first, second)
        finite = [
            row.reference__removal_log_scale
            for row in first.values()
            if row.reference__removal_log_scale is not None
        ]
        self.assertEqual(finite, sorted(finite))
        edge_records = [record for record in first.values() if record.reference__edge_censored]
        self.assertGreaterEqual(len(edge_records), 1)
        self.assertTrue(all(record.reference__removal_log_scale is None for record in edge_records))
        left, right = MODULE.chronological_boundary_flags(prepared, prepared.sequence[-1].event_id)
        self.assertFalse(left)
        self.assertTrue(right)

    def test_parameter_sweep_reproduces_exactly(self) -> None:
        prepared = MODULE.prepare_sequence(self.events, dual_mode="deferred")
        scales = (0.01, 0.03, 0.05)
        first = MODULE.threshold_sweep(prepared, scales, family="log_price", local_scale_by_id={})
        second = MODULE.threshold_sweep(prepared, scales, family="log_price", local_scale_by_id={})
        self.assertEqual(first, second)
        self.assertEqual(
            [(row.parameter, row.event_id, row.retained) for row in first],
            sorted((row.parameter, row.event_id, row.retained) for row in first),
        )
        for scale in scales:
            direct = {
                event.event_id
                for event in MODULE._retained_at_threshold(
                    prepared.sequence, scale, "log_price", {}
                )
            }
            optimized = {
                row.event_id
                for row in first
                if row.parameter == scale and row.retained
            }
            self.assertEqual(optimized, direct)

    def test_retracement_ratio_is_outgoing_over_incoming(self) -> None:
        left = pivot(0, "LOW", 100.0)
        center = pivot(2, "HIGH", 110.0)
        right = pivot(4, "LOW", 80.0)
        actual = MODULE._support(left, center, right, "retracement_ratio", {})
        expected = abs(MODULE.math.log(80.0 / 110.0)) / abs(MODULE.math.log(110.0 / 100.0))
        self.assertAlmostEqual(actual, expected)
        self.assertGreater(actual, 1.0)

    def test_reference_namespace_rejects_unmarked_future_fields(self) -> None:
        MODULE.assert_reference_namespace([
            "event_id", "pivot_timestamp", "reference__score", "postevent__right_support"
        ])
        with self.assertRaises(ValueError):
            MODULE.assert_reference_namespace(["event_id", "future_support"])

    def test_source_identity_validation_detects_change(self) -> None:
        ids = [event.event_id for event in self.events]
        MODULE.validate_source_identity(ids, ids)
        with self.assertRaises(ValueError):
            MODULE.validate_source_identity(ids, ids[:-1])

    def test_parquet_serialization_is_byte_identical(self) -> None:
        scratch = Path(__file__).with_name(".test-tmp")
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir()
        try:
            rows = [
                {"event_id": "a", "reference__score": 0.1},
                {"event_id": "b", "reference__score": 0.2},
            ]
            first = scratch / "first.parquet"
            second = scratch / "second.parquet"
            MODULE.write_deterministic_parquet(first, rows)
            MODULE.write_deterministic_parquet(second, rows)
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_source_contains_no_legacy_structural_level_dependency(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        forbidden = "structural" + "_levels.csv"
        self.assertNotIn(forbidden, source)

    def test_price_scale_diagnostics_excludes_boundary_nulls(self) -> None:
        rows = [
            {
                "pivot_price": 100.0,
                "reference__primary_sequence_eligible": True,
                "reference__design_a_min_prominence_rank": None,
                "reference__design_b_primary_survival_rank": 1.0,
                "reference__design_c_log_survival_fraction": 1.0,
                "reference__design_c_local_vol_survival_fraction": 1.0,
            },
            {
                "pivot_price": 110.0,
                "reference__primary_sequence_eligible": True,
                "reference__design_a_min_prominence_rank": 0.2,
                "reference__design_b_primary_survival_rank": 0.3,
                "reference__design_c_log_survival_fraction": 0.4,
                "reference__design_c_local_vol_survival_fraction": 0.5,
            },
            {
                "pivot_price": 120.0,
                "reference__primary_sequence_eligible": True,
                "reference__design_a_min_prominence_rank": 0.8,
                "reference__design_b_primary_survival_rank": 0.7,
                "reference__design_c_log_survival_fraction": 0.6,
                "reference__design_c_local_vol_survival_fraction": 0.5,
            },
        ]
        result = MODULE.price_scale_diagnostics(rows)
        self.assertEqual(set(result), {
            "corr_log_price_design_a_rank", "corr_log_price_design_b_rank",
            "corr_log_price_design_c_log_survival", "corr_log_price_design_c_local_vol_survival",
        })


if __name__ == "__main__":
    unittest.main()
