import unittest

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import (
    Bar,
    BacktestConfig,
    MaintenanceTier,
    OrderIntent,
)


class SignalOnFirstBar:
    def __init__(self, intent):
        self.intent = intent
        self.called = False

    def on_bar(self, bar, state):
        if not self.called:
            self.called = True
            return [self.intent]
        return []


def mark_bar(t, o, h, l, c):
    return Bar(t, o, h, l, c, 1, o, h, l, c)


class CrossMarginLiquidationTests(unittest.TestCase):
    def setUp(self):
        self.tier = MaintenanceTier(None, 0.005, 0.0)
    def cfg(self, **overrides):
        base = dict(
            initial_cash=1000.0,
            leverage=10.0,
            liquidation_enabled=True,
            maintenance_tiers=(self.tier,),
        )
        base.update(overrides)
        return BacktestConfig(**base)

    def test_long_liquidates_on_mark_price(self):
        bars = [
            mark_bar(0,100,100,100,100),
            mark_bar(60_000,100,100,100,100),
            mark_bar(120_000,100,100,90,95),
        ]
        order = OrderIntent.market("long", 100.0)
        result = BacktestEngine(self.cfg()).run(bars, SignalOnFirstBar(order))
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "liquidation")
        self.assertAlmostEqual(trade.exit_price, 9000 / 99.5, places=6)

    def test_short_liquidates_on_mark_price(self):
        bars = [
            mark_bar(0,100,100,100,100),
            mark_bar(60_000,100,100,100,100),
            mark_bar(120_000,100,110,100,105),
        ]
        order = OrderIntent.market("short", 100.0)
        result = BacktestEngine(self.cfg()).run(bars, SignalOnFirstBar(order))
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "liquidation")
        self.assertAlmostEqual(trade.exit_price, 11000 / 100.5, places=6)
    def test_gap_liquidation_uses_mark_open(self):
        bars = [
            mark_bar(0,100,100,100,100),
            mark_bar(60_000,100,100,100,100),
            mark_bar(120_000,90,92,85,88),
        ]
        result = BacktestEngine(self.cfg()).run(
            bars, SignalOnFirstBar(OrderIntent.market("long", 100.0))
        )
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "liquidation")
        self.assertEqual(trade.exit_price, 90.0)

    def test_liquidation_fee_is_separate_cost(self):
        bars = [
            mark_bar(0,100,100,100,100),
            mark_bar(60_000,100,100,100,100),
            mark_bar(120_000,90,92,85,88),
        ]
        result = BacktestEngine(self.cfg(liquidation_fee_rate=0.01)).run(
            bars, SignalOnFirstBar(OrderIntent.market("long", 100.0))
        )
        trade = result.trades[0]
        self.assertAlmostEqual(trade.liquidation_fee, 90.0)
        self.assertAlmostEqual(trade.net_pnl, -1090.0)

    def test_missing_mark_data_rejected_for_liquidation_run(self):
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        with self.assertRaises(ValueError):
            BacktestEngine(self.cfg()).run(
                bars, SignalOnFirstBar(OrderIntent.market("long", 1.0))
            )
    def test_insufficient_cross_margin_rejected(self):
        bars = [mark_bar(0,100,100,100,100), mark_bar(60_000,100,100,100,100)]
        result = BacktestEngine(self.cfg()).run(
            bars, SignalOnFirstBar(OrderIntent.market("long", 101.0))
        )
        self.assertIsNone(result.open_position)
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(
            result.rejected_orders[0].reason, "INSUFFICIENT_CROSS_MARGIN"
        )

    def test_maintenance_amount_is_used(self):
        tier = MaintenanceTier(None, 0.01, 50.0)
        cfg = self.cfg(maintenance_tiers=(tier,))
        engine = BacktestEngine(cfg)
        bars = [mark_bar(0,100,100,100,100), mark_bar(60_000,100,100,100,100)]
        result = engine.run(bars, SignalOnFirstBar(OrderIntent.market("long", 100.0)))
        self.assertIsNotNone(result.open_position)


if __name__ == "__main__":
    unittest.main()
