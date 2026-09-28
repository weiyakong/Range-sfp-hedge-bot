import unittest

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import Bar, BacktestConfig, OrderIntent


class SequenceStrategy:
    def __init__(self, intents):
        self.intents = list(intents)
        self.index = 0

    def on_bar(self, bar, state):
        if self.index >= len(self.intents):
            return []
        intent = self.intents[self.index]
        self.index += 1
        return [] if intent is None else [intent]


class FundingTests(unittest.TestCase):
    def test_positive_funding_long_pays_short_receives(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,100,100,100,100,1),
        ]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: 0.001},
            funding_price_by_time={120_000: 100.0},
        )
        long_result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("long", 1.0)])
        )
        short_result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("short", 1.0)])
        )
        self.assertAlmostEqual(long_result.final_cash, 999.9)
        self.assertAlmostEqual(short_result.final_cash, 1000.1)

    def test_negative_funding_reverses_signs(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,100,100,100,100,1),
        ]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: -0.001},
            funding_price_by_time={120_000: 100.0},
        )
        long_result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("long", 1.0)])
        )
        short_result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("short", 1.0)])
        )
        self.assertAlmostEqual(long_result.final_cash, 1000.1)
        self.assertAlmostEqual(short_result.final_cash, 999.9)
    def test_missing_provided_funding_price_is_error(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,100,100,100,100,1),
        ]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: 0.001},
        )
        with self.assertRaises(ValueError):
            BacktestEngine(cfg).run(
                bars, SequenceStrategy([OrderIntent.market("long", 1.0)])
            )

    def test_entry_on_funding_timestamp_does_not_pay_same_timestamp(self):
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={60_000: 0.001},
            funding_price_by_time={60_000: 100.0},
        )
        result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("long", 1.0)])
        )
        self.assertAlmostEqual(result.final_cash, 1000.0)
        self.assertAlmostEqual(result.open_position_funding, 0.0)
    def test_exit_on_funding_timestamp_pays_before_exit(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,100,100,100,100,1),
        ]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: 0.001},
            funding_price_by_time={120_000: 100.0},
        )
        strategy = SequenceStrategy([
            OrderIntent.market("long", 1.0),
            OrderIntent.exit_market("long"),
        ])
        result = BacktestEngine(cfg).run(bars, strategy)
        self.assertEqual(result.trades[0].exit_time, 120_000)
        self.assertAlmostEqual(result.trades[0].funding, 0.1)
        self.assertAlmostEqual(result.final_cash, 999.9)

    def test_bar_open_funding_price_requires_explicit_mode(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,110,110,110,110,1),
        ]
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_price_source="bar_open",
            funding_rate_by_time={120_000: 0.001},
        )
        result = BacktestEngine(cfg).run(
            bars, SequenceStrategy([OrderIntent.market("long", 1.0)])
        )
        self.assertAlmostEqual(result.open_position_funding, 0.11)


if __name__ == "__main__":
    unittest.main()
