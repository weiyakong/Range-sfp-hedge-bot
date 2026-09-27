#!/usr/bin/env python3
"""Unit tests for Stage 2I-B1 Same-Type Prepass Sensitivity Audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).with_name("build_stage2i_b1_prepass_audit.py")
SPEC = importlib.util.spec_from_file_location("prepass_audit", MODULE_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_pivot(
    index: int,
    kind: str,
    price: float,
    *,
    dual: bool = False,
    suffix: str = "",
) -> object:
    return MODULE.PivotEvent(
        event_id=f"P{index:04d}_{kind}{suffix}",
        bar_index=index,
        timestamp=f"2024-01-01T{index:02d}:00:00Z",
        pivot_type=kind,
        price=price,
        is_dual=dual,
    )


class PrepassAuditTests(unittest.TestCase):
    def test_current_prepass_high_keeps_higher(self) -> None:
        events = [
            make_pivot(10, "HIGH", 50000.0),
            make_pivot(14, "HIGH", 51000.0),
            make_pivot(20, "LOW", 48000.0),
        ]
        seq, removed, runs = MODULE.run_prepass_variant_a(events)
        self.assertEqual([e.event_id for e in seq], ["P0014_HIGH", "P0020_LOW"])
        self.assertIn("P0010_HIGH", removed)
        self.assertEqual(removed["P0010_HIGH"].event_id, "P0014_HIGH")

    def test_current_prepass_low_keeps_lower(self) -> None:
        events = [
            make_pivot(10, "LOW", 49000.0),
            make_pivot(14, "LOW", 48000.0),
            make_pivot(20, "HIGH", 52000.0),
        ]
        seq, removed, runs = MODULE.run_prepass_variant_a(events)
        self.assertEqual([e.event_id for e in seq], ["P0014_LOW", "P0020_HIGH"])
        self.assertIn("P0010_LOW", removed)
        self.assertEqual(removed["P0010_LOW"].event_id, "P0014_LOW")

    def test_dual_aware_separator_prevents_same_type_collapse(self) -> None:
        events = [
            make_pivot(10, "HIGH", 50000.0),
            make_pivot(15, "HIGH", 52000.0, dual=True),
            make_pivot(15, "LOW", 47000.0, dual=True, suffix="_LOW"),
            make_pivot(20, "HIGH", 51000.0),
        ]
        # In Variant A, duals are ignored in candidate stream -> HIGH 10 and HIGH 20 collapse
        seq_a, rem_a, _ = MODULE.run_prepass_variant_a(events)
        self.assertEqual(len(seq_a), 1)
        self.assertEqual(seq_a[0].event_id, "P0020_HIGH")
        self.assertIn("P0010_HIGH", rem_a)

        # In Variant B, dual at bar 15 acts as a barrier -> HIGH 10 and HIGH 20 do NOT collapse
        cand_b, rem_b, rem_b_ids = MODULE.run_prepass_variant_b(events)
        self.assertEqual(len(cand_b), 2)
        self.assertEqual([e.event_id for e in cand_b], ["P0010_HIGH", "P0020_HIGH"])
        self.assertNotIn("P0010_HIGH", rem_b_ids)

    def test_hierarchy_is_deterministic(self) -> None:
        events = [
            make_pivot(0, "LOW", 100.0),
            make_pivot(2, "HIGH", 110.0),
            make_pivot(4, "LOW", 105.0),
            make_pivot(6, "HIGH", 120.0),
            make_pivot(8, "LOW", 108.0),
        ]
        res1 = MODULE.hierarchical_simplification(events, [])
        res2 = MODULE.hierarchical_simplification(events, [])
        self.assertEqual(res1, res2)

    def test_namespace_enforcement(self) -> None:
        valid_cols = ["event_id", "pivot_bar_index", "reference__metric_a", "postevent__test"]
        MODULE.assert_reference_namespace(valid_cols)

        invalid_cols = ["event_id", "unprefixed_metric"]
        with self.assertRaises(ValueError):
            MODULE.assert_reference_namespace(invalid_cols)


if __name__ == "__main__":
    unittest.main()
