import unittest
from dataclasses import FrozenInstanceError

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.metrics import summarize
from research.backtester_v2.models import (
    Bar,
    BacktestConfig,
    MaintenanceTier,
    OrderIntent,
)


class SignalOnFirstBar:
    def __init__(self, intent: OrderIntent):
        self.intent = intent
        self.called = False

    def on_bar(self, bar, state):
        if not self.called:
            self.called = True
            return [self.intent]
        return []


class NoopStrategy:
    def on_bar(self, bar, state):
        return []
class ExecutionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = BacktestConfig(initial_cash=10_000.0, limit_fill_policy="touch")

    def test_market_signal_executes_next_bar_open(self):
        bars = [Bar(0,100,101,99,100,1), Bar(60_000,110,112,109,111,1)]
        result = BacktestEngine(self.cfg).run(
            bars, SignalOnFirstBar(OrderIntent.market("long", 1.0))
        )
        self.assertEqual(result.open_position.entry_time, 60_000)
        self.assertEqual(result.open_position.entry_price, 110.0)

    def test_passive_limit_cannot_claim_same_bar_target(self):
        bars = [Bar(0,105,105,105,105,1), Bar(60_000,105,110,99,101,1)]
        order = OrderIntent.limit(
            "long", 1.0, 100.0, "GTC", take_profit=108.0
        )
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        self.assertEqual(len(result.trades), 0)
        self.assertIsNotNone(result.open_position)
        self.assertEqual(result.open_position.entry_price, 100.0)

    def test_passive_short_limit_cannot_claim_same_bar_target(self):
        bars = [Bar(0,95,95,95,95,1), Bar(60_000,95,101,90,99,1)]
        order = OrderIntent.limit(
            "short", 1.0, 100.0, "GTC", take_profit=92.0
        )
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        self.assertEqual(len(result.trades), 0)
        self.assertIsNotNone(result.open_position)
    def test_gap_stop_uses_first_available_open(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,99,100,1),
            Bar(120_000,90,92,85,88,1),
        ]
        order = OrderIntent.market("long", 1.0, stop_loss=95.0)
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "stop_loss_gap")
        self.assertEqual(trade.exit_price, 90.0)
        self.assertEqual(trade.net_pnl, -10.0)

    def test_marketable_buy_limit_fills_at_open_as_taker(self):
        cfg = BacktestConfig(initial_cash=1000.0, taker_fee_rate=0.001)
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,105,95,101,1)]
        order = OrderIntent.limit("long", 1.0, 110.0, "GTC")
        result = BacktestEngine(cfg).run(bars, SignalOnFirstBar(order))
        self.assertEqual(result.open_position.entry_price, 100.0)
        self.assertAlmostEqual(result.open_position.entry_fee, 0.1)

    def test_gtc_limit_persists_until_fill(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,95,100,1),
            Bar(120_000,95,96,89,92,1),
        ]
        order = OrderIntent.limit("long", 1.0, 90.0, "GTC")
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        self.assertIsNotNone(result.open_position)
        self.assertIsNone(result.open_position.entry_time_exact)
        self.assertEqual(result.open_position.entry_bar_time, 120_000)
        self.assertEqual(result.open_position.fill_time_resolution, "bar")
        self.assertEqual(result.open_position.entry_price, 90.0)
    def test_ioc_limit_expires_after_first_attempt(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,95,100,1),
            Bar(120_000,95,96,89,92,1),
        ]
        order = OrderIntent.limit("long", 1.0, 90.0, "IOC")
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        self.assertIsNone(result.open_position)
        self.assertEqual(result.trades, [])

    def test_non_monotonic_timestamps_rejected(self):
        bars = [Bar(120_000,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        with self.assertRaises(ValueError):
            BacktestEngine(self.cfg).run(bars, NoopStrategy())

    def test_duplicate_timestamp_rejected(self):
        bars = [Bar(60_000,100,100,100,100,1), Bar(60_000,100,100,100,100,1)]
        with self.assertRaises(ValueError):
            BacktestEngine(self.cfg).run(bars, NoopStrategy())

    def test_same_bar_passive_limit_keeps_adverse_stop(self):
        bars = [Bar(0,105,105,105,105,1), Bar(60_000,105,110,94,100,1)]
        order = OrderIntent.limit(
            "long", 1.0, 100.0, "GTC", stop_loss=95.0, take_profit=108.0
        )
        result = BacktestEngine(self.cfg).run(bars, SignalOnFirstBar(order))
        self.assertEqual(result.trades[0].exit_reason, "stop_loss_same_bar_after_limit")
        self.assertEqual(result.trades[0].exit_price, 95.0)
class StateAndAccountingTests(unittest.TestCase):
    def test_strategy_state_is_immutable(self):
        class MutatingStrategy:
            def on_bar(self, bar, state):
                state.cash += 1_000_000
                return []
        with self.assertRaises(FrozenInstanceError):
            BacktestEngine(BacktestConfig()).run(
                [Bar(0,100,100,100,100,1)], MutatingStrategy()
            )

    def test_long_and_short_intents_same_bar_are_allowed(self):
        class HedgeStrategy:
            def __init__(self):
                self.sent = False
            def on_bar(self, bar, state):
                if self.sent:
                    return []
                self.sent = True
                return [OrderIntent.market("long", 1), OrderIntent.market("short", 1)]
        result = BacktestEngine(BacktestConfig()).run(
            [Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)],
            HedgeStrategy(),
        )
        self.assertIsNotNone(result.open_long_position)
        self.assertIsNotNone(result.open_short_position)

    def test_duplicate_same_side_intents_are_rejected(self):
        class BadStrategy:
            def on_bar(self, bar, state):
                return [OrderIntent.market("long", 1), OrderIntent.market("long", 1)]
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig()).run(
                [Bar(0,100,100,100,100,1)], BadStrategy()
            )

    def test_eod_metrics_include_open_loss_and_entry_fee(self):
        cfg = BacktestConfig(initial_cash=1000.0, taker_fee_rate=0.001)
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,100,50,50,1)]
        result = BacktestEngine(cfg).run(
            bars, SignalOnFirstBar(OrderIntent.market("long", 1.0))
        )
        metrics = summarize(result, cfg.initial_cash)
        self.assertAlmostEqual(result.final_cash, 999.9)
        self.assertAlmostEqual(result.final_equity, 949.9)
        self.assertAlmostEqual(metrics["net_pnl"], -50.1)
        self.assertAlmostEqual(metrics["fees"], 0.1)
        self.assertTrue(metrics["open_position"])
