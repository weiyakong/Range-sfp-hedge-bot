from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("review_stage2i_a.py")
SPEC = importlib.util.spec_from_file_location("review_stage2i_a", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def bars(values: list[tuple[float, float, float]]) -> list[object]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = []
    for index, (high, low, close) in enumerate(values):
        result.append(MODULE.Candle(
            index=index,
            timestamp=start + timedelta(hours=4 * index),
            end_time=start + timedelta(hours=4 * (index + 1)),
            open=close,
            high=high,
            low=low,
            close=close,
            volume=100.0 + index,
            trade_count=1000 + index,
        ))
    return result


class Stage2IAPivotStructureReviewTests(unittest.TestCase):
    def test_distribution_summary_uses_linear_quantiles(self) -> None:
        summary = MODULE.describe([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["p25"], 1.75)
        self.assertEqual(summary["median"], 2.5)
        self.assertEqual(summary["p90"], 3.7)

    def test_gap_buckets_are_explicit_about_intervening_bars(self) -> None:
        self.assertEqual(MODULE.gap_bucket(0), "same_candle")
        self.assertEqual(MODULE.gap_bucket(1), "adjacent_candles")
        self.assertEqual(MODULE.gap_bucket(2), "one_intervening_bar")
        self.assertEqual(MODULE.gap_bucket(3), "two_intervening_bars")
        self.assertEqual(MODULE.gap_bucket(6), "three_to_five_intervening_bars")
        self.assertEqual(MODULE.gap_bucket(13), "six_to_twelve_intervening_bars")
        self.assertEqual(MODULE.gap_bucket(14), "more_than_twelve_intervening_bars")

    def test_bars_to_breach_is_strict_and_future_only(self) -> None:
        candles = bars([(11, 9, 10), (12, 8, 10), (12, 8, 10), (12.1, 7.9, 10)])
        self.assertEqual(MODULE.bars_to_breach(candles, 0, "HIGH", 12.0), 3)
        self.assertEqual(MODULE.bars_to_breach(candles, 0, "LOW", 8.0), 3)
        self.assertIsNone(MODULE.bars_to_breach(candles, 3, "HIGH", 12.1))

    def test_pair_geometry_uses_close_path(self) -> None:
        candles = bars([(11, 9, 10), (13, 10, 12), (12, 9, 11)])
        metrics = MODULE.pair_geometry(candles, 0, 2, 9.0, 12.0)
        self.assertEqual(metrics["absolute_pivot_move"], 3.0)
        self.assertEqual(metrics["close_path"], 3.0)
        self.assertAlmostEqual(metrics["close_path_efficiency"], 1 / 3)
        self.assertEqual(metrics["price_excursion"], 4.0)
        self.assertEqual(metrics["directional_persistence"], 0.0)
        self.assertEqual(metrics["alternation"], 1.0)

    def test_dual_geometry_compares_center_with_four_neighbors(self) -> None:
        candles = bars([(10, 5, 7), (11, 4, 8), (15, 1, 9), (12, 3, 8), (10, 5, 7)])
        metrics = MODULE.dual_geometry(candles, 2)
        self.assertEqual(metrics["center_range"], 14.0)
        self.assertEqual(metrics["high_extension"], 3.0)
        self.assertEqual(metrics["low_extension"], 2.0)
        self.assertAlmostEqual(metrics["center_to_neighbor_mean_range_ratio"], 14 / 6.5)

    def test_svg_output_is_deterministic(self) -> None:
        candles = bars([(11, 9, 10), (12, 8, 11), (13, 10, 12)])
        first = MODULE.candlestick_svg(candles, [], "fixture").encode()
        second = MODULE.candlestick_svg(candles, [], "fixture").encode()
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())

    def test_review_dictionary_separates_causal_and_postevent_fields(self) -> None:
        fields = MODULE._data_dictionary()["tables"]["pivot_diagnostics.csv"]["column_information_status"]
        self.assertEqual(fields["incoming_path_efficiency"], "causal")
        self.assertEqual(fields["same_type_extension_pct"], "causal")
        self.assertEqual(fields["outgoing_path_efficiency"], "postevent")
        self.assertEqual(fields["bars_to_strict_pivot_price_breach"], "postevent")


if __name__ == "__main__":
    unittest.main()
