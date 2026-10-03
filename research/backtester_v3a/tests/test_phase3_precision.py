from __future__ import annotations

import unittest

from research.backtester_v2.models import OrderIntent
from research.backtester_v3a.contracts import parse_instrument_metadata
from research.backtester_v3a.precision import (
    IntentNormalizationError,
    classify_marketable_limit,
    normalize_order_intent,
)
from research.backtester_v3a.tests.test_phase2_contracts import metadata_payload


def metadata(**updates: object):
    payload = metadata_payload()
    payload.update(updates)
    return parse_instrument_metadata(payload)


class PrecisionNormalizationTests(unittest.TestCase):
    def test_tick_rounding_uses_nearest_grid_point(self) -> None:
        intent = OrderIntent.limit("long", 1.2349, 100.06, "GTC")
        normalized = normalize_order_intent(intent, metadata(), reference_price=100.0)
        self.assertEqual(normalized.qty, 1.234)
        self.assertEqual(normalized.limit_price, 100.1)

    def test_protective_prices_are_rounded(self) -> None:
        intent = OrderIntent.market(
            "long", 1.0, stop_loss=99.94, take_profit=101.06,
        )
        normalized = normalize_order_intent(intent, metadata(), reference_price=100.0)
        self.assertEqual(normalized.stop_loss, 99.9)
        self.assertEqual(normalized.take_profit, 101.1)

    def test_grid_valid_intent_is_unchanged(self) -> None:
        intent = OrderIntent.limit(
            "long", 1.25, 100.1, "GTC", stop_loss=99.0, take_profit=102.0,
        )
        self.assertEqual(
            normalize_order_intent(intent, metadata(), reference_price=100.0),
            intent,
        )
    def test_quantity_rounding_to_zero_fails(self) -> None:
        with self.assertRaisesRegex(IntentNormalizationError, "zero"):
            normalize_order_intent(
                OrderIntent.market("long", 0.0009),
                metadata(),
                reference_price=100.0,
            )

    def test_minimum_quantity_fails(self) -> None:
        with self.assertRaisesRegex(IntentNormalizationError, "min_qty"):
            normalize_order_intent(
                OrderIntent.market("long", 0.004),
                metadata(step_size="0.001", min_qty="0.005"),
                reference_price=10_000.0,
            )

    def test_minimum_notional_fails(self) -> None:
        with self.assertRaisesRegex(IntentNormalizationError, "min_notional"):
            normalize_order_intent(
                OrderIntent.market("long", 0.01),
                metadata(min_notional="5"),
                reference_price=100.0,
            )

    def test_invalid_rounded_stop_fails(self) -> None:
        with self.assertRaisesRegex(IntentNormalizationError, "stop_loss"):
            normalize_order_intent(
                OrderIntent.market("long", 1.0, stop_loss=99.96),
                metadata(),
                reference_price=100.0,
            )

    def test_invalid_rounded_take_profit_fails(self) -> None:
        with self.assertRaisesRegex(IntentNormalizationError, "take_profit"):
            normalize_order_intent(
                OrderIntent.market("short", 1.0, take_profit=99.96),
                metadata(),
                reference_price=100.0,
            )

    def test_marketable_limit_is_classified_after_normalization(self) -> None:
        raw = OrderIntent.limit("long", 1.0, 99.96, "GTC")
        normalized = normalize_order_intent(raw, metadata(), reference_price=100.0)
        self.assertEqual(normalized.limit_price, 100.0)
        self.assertTrue(classify_marketable_limit(normalized, bar_open=100.0))

    def test_exit_intent_passes_without_entry_checks(self) -> None:
        intent = OrderIntent.exit_market("long")
        self.assertEqual(
            normalize_order_intent(intent, metadata(), reference_price=100.0),
            intent,
        )
