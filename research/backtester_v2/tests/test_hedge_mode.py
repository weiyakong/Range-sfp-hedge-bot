import unittest

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import (
    BacktestConfig, Bar, MaintenanceTier, OrderIntent,
)


def mark_bar(t, o, h, l, c):
    return Bar(t, o, h, l, c, 1, o, h, l, c)


class ScriptedStrategy:
    def __init__(self, steps):
        self.steps = list(steps)
        self.index = 0

    def on_bar(self, bar, state):
        if self.index >= len(self.steps):
            return []
        intents = self.steps[self.index]
        self.index += 1
        return intents


class HedgeModeTests(unittest.TestCase):
    def test_simultaneous_long_short_open(self):
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 1.0),
            OrderIntent.market("short", 1.0),
        ]])
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,99,100,1),
        ]
        result = BacktestEngine(BacktestConfig()).run(bars, strategy)
        self.assertIsNotNone(result.open_long_position)
        self.assertIsNotNone(result.open_short_position)
        self.assertIsNone(result.open_position)

    def test_long_and_short_close_independently(self):
        strategy = ScriptedStrategy([
            [OrderIntent.market("long", 1.0), OrderIntent.market("short", 1.0)],
            [OrderIntent.exit_market("long")],
            [],
        ])
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,99,100,1),
            Bar(120_000,105,106,104,105,1),
        ]
        result = BacktestEngine(BacktestConfig()).run(bars, strategy)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].side, "long")
        self.assertIsNone(result.open_long_position)
        self.assertIsNotNone(result.open_short_position)
    def test_equal_hedge_funding_offsets(self):
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: 0.001},
            funding_price_by_time={120_000: 100.0},
        )
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 2.0),
            OrderIntent.market("short", 2.0),
        ]])
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,100,100,100,1),
            Bar(120_000,100,100,100,100,1),
        ]
        result = BacktestEngine(cfg).run(bars, strategy)
        self.assertAlmostEqual(result.final_cash, 1000.0)
        self.assertAlmostEqual(result.open_long_position.funding_paid, 0.2)
        self.assertAlmostEqual(result.open_short_position.funding_paid, -0.2)

    def test_cross_margin_capacity_sums_both_legs(self):
        cfg = BacktestConfig(initial_cash=1000.0, leverage=10.0)
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 60.0),
            OrderIntent.market("short", 50.0),
        ]])
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        result = BacktestEngine(cfg).run(bars, strategy)
        self.assertIsNotNone(result.open_long_position)
        self.assertIsNone(result.open_short_position)
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(
            result.rejected_orders[0].reason, "INSUFFICIENT_CROSS_MARGIN"
        )
    def test_account_liquidation_closes_both_legs(self):
        cfg = BacktestConfig(
            initial_cash=2000.0,
            leverage=10.0,
            liquidation_enabled=True,
            maintenance_tiers=(MaintenanceTier(None, 0.005, 0.0),),
        )
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 100.0),
            OrderIntent.market("short", 50.0),
        ]])
        bars = [
            mark_bar(0,100,100,100,100),
            mark_bar(60_000,100,100,100,100),
            mark_bar(120_000,100,100,50,60),
        ]
        result = BacktestEngine(cfg).run(bars, strategy)
        liquidations = [t for t in result.trades if t.exit_reason == "liquidation"]
        self.assertEqual(len(liquidations), 2)
        self.assertEqual({t.side for t in liquidations}, {"long", "short"})
        self.assertAlmostEqual(liquidations[0].exit_price, liquidations[1].exit_price)
        self.assertFalse(result.open_positions)

    def test_same_side_pyramiding_still_rejected(self):
        strategy = ScriptedStrategy([
            [OrderIntent.market("long", 1.0)],
            [OrderIntent.market("long", 1.0)],
        ])
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig()).run(bars, strategy)


if __name__ == "__main__":
    unittest.main()
