import unittest

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import Bar, BacktestConfig, OrderIntent


class FirstSignal:
    def __init__(self, intent):
        self.intent = intent
        self.sent = False

    def on_bar(self, bar, state):
        if not self.sent:
            self.sent = True
            return [self.intent]
        return []


class ContractTests(unittest.TestCase):
    def test_short_gap_stop_and_slippage_are_adverse(self):
        cfg = BacktestConfig(initial_cash=1000.0, slippage_rate=0.01)
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,99,100,1),
            Bar(120_000,110,115,109,112,1),
        ]
        order = OrderIntent.market("short", 1.0, stop_loss=105.0)
        result = BacktestEngine(cfg).run(bars, FirstSignal(order))
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "stop_loss_gap")
        self.assertAlmostEqual(trade.entry_price, 99.0)
        self.assertAlmostEqual(trade.exit_price, 111.1)
    def test_repeated_entry_while_open_is_rejected(self):
        class RepeatEntry:
            def __init__(self):
                self.calls = 0
            def on_bar(self, bar, state):
                self.calls += 1
                if self.calls <= 2:
                    return [OrderIntent.market("long", 1.0)]
                return []
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,100,101,99,100,1)]
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig()).run(bars, RepeatEntry())

    def test_opposite_entry_while_open_creates_hedge_leg(self):
        class HedgeEntry:
            def __init__(self):
                self.calls = 0
            def on_bar(self, bar, state):
                self.calls += 1
                if self.calls == 1:
                    return [OrderIntent.market("long", 1.0)]
                if self.calls == 2:
                    return [OrderIntent.market("short", 1.0)]
                return []
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(60_000,100,101,99,100,1),
            Bar(120_000,100,101,99,100,1),
        ]
        result = BacktestEngine(BacktestConfig()).run(bars, HedgeEntry())
        self.assertIsNotNone(result.open_long_position)
        self.assertIsNotNone(result.open_short_position)
    def test_time_exit_counts_1_2_10_bars(self):
        for hold in (1, 2, 10):
            bars = [Bar(i*60_000,100+i,100+i,100+i,100+i,1) for i in range(hold + 3)]
            order = OrderIntent.market("long", 1.0, max_hold_bars=hold)
            result = BacktestEngine(BacktestConfig()).run(bars, FirstSignal(order))
            self.assertEqual(result.trades[0].exit_time, (hold + 1) * 60_000)
            self.assertEqual(result.trades[0].exit_reason, "time_exit")

    def test_maker_and_taker_fees_are_separate(self):
        cfg = BacktestConfig(
            initial_cash=1000.0,
            maker_fee_rate=0.001,
            taker_fee_rate=0.002,
            limit_fill_policy="touch",
        )
        bars = [
            Bar(0,105,105,105,105,1),
            Bar(60_000,105,106,99,101,1),
            Bar(120_000,101,110,100,109,1),
        ]
        order = OrderIntent.limit("long", 1.0, 100.0, "GTC", take_profit=108.0)
        result = BacktestEngine(cfg).run(bars, FirstSignal(order))
        trade = result.trades[0]
        self.assertAlmostEqual(trade.fees, 0.208)
        self.assertAlmostEqual(trade.net_pnl, 7.792)
    def test_invalid_config_rejected(self):
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig(slippage_rate=-0.01))
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig(leverage=0.5))
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig(liquidation_enabled=True))

    def test_invalid_ohlc_rejected(self):
        bad = Bar(0,100,99,98,100,1)
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig()).run([bad], FirstSignal(OrderIntent.market("long", 1)))

    def test_invalid_protective_level_at_fill_rejected(self):
        bars = [Bar(0,100,100,100,100,1), Bar(60_000,90,91,89,90,1)]
        order = OrderIntent.market("long", 1.0, stop_loss=95.0)
        with self.assertRaises(ValueError):
            BacktestEngine(BacktestConfig()).run(bars, FirstSignal(order))


if __name__ == "__main__":
    unittest.main()
