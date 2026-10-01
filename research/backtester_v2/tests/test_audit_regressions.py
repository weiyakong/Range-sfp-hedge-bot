import json
import tempfile
import unittest
from math import inf, nan
from pathlib import Path
from unittest.mock import patch

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.metrics import summarize
from research.backtester_v2.models import (
    BacktestConfig,
    Bar,
    MaintenanceTier,
    OrderIntent,
)
from research.backtester_v2.output import build_run_metadata, write_results


MINUTE = 60_000


def marked_bar(index, open_price, high, low, close):
    timestamp = index * MINUTE
    return Bar(
        timestamp, open_price, high, low, close, 1.0,
        open_price, high, low, close,
    )


class ScriptedStrategy:
    def __init__(self, steps):
        self.steps = list(steps)
        self.index = 0

    def on_bar(self, bar, state):
        intents = self.steps[self.index] if self.index < len(self.steps) else []
        self.index += 1
        return intents


def liquidation_config(**overrides):
    values = {
        "initial_cash": 1_000.0,
        "leverage": 10.0,
        "liquidation_enabled": True,
        "maintenance_tiers": (MaintenanceTier(None, 0.005, 0.0),),
    }
    values.update(overrides)
    return BacktestConfig(**values)


def audit_metadata():
    return build_run_metadata(
        repo_root=Path(__file__).resolve().parents[3],
        strategy_name="audit_fixture",
        strategy_version="1",
        source_type="internal",
        run_purpose="TEST",
        run_stage="DEVELOPMENT",
        strategy_parameters={"x": 1},
        source_reference=None,
        manifest_path=None,
        symbol="BTCUSDT",
        market="USDT-M perpetual futures",
        timeframe="1m",
        tested_start=0,
        tested_end=0,
        row_count=1,
    )


class DynamicHedgeLiquidationRegressionTests(unittest.TestCase):
    def test_simultaneous_same_price_hedge_exits_are_both_processed(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,110,100,110,1),
        ]
        result = BacktestEngine(BacktestConfig()).run(
            bars,
            ScriptedStrategy([[
                OrderIntent.market("long", 1, take_profit=110),
                OrderIntent.market("short", 1, stop_loss=110),
            ]]),
        )
        self.assertEqual(
            {(trade.side, trade.exit_reason) for trade in result.trades},
            {("long", "take_profit"), ("short", "stop_loss")},
        )
        self.assertFalse(result.open_positions)
        self.assertEqual(len(result.intrabar_ambiguities), 1)

    def test_long_tp_then_short_liquidation(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 125, 100, 125),
        ]
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 50, take_profit=105),
            OrderIntent.market("short", 50),
        ]])
        result = BacktestEngine(liquidation_config()).run(bars, strategy)
        self.assertEqual(
            [(trade.side, trade.exit_reason) for trade in result.trades],
            [("long", "take_profit"), ("short", "liquidation")],
        )
        self.assertFalse(result.open_positions)
        self.assertEqual(result.intrabar_ambiguities, [])

    def test_short_tp_then_long_liquidation(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 100, 75, 75),
        ]
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 50),
            OrderIntent.market("short", 50, take_profit=95),
        ]])
        result = BacktestEngine(liquidation_config()).run(bars, strategy)
        self.assertEqual(
            [(trade.side, trade.exit_reason) for trade in result.trades],
            [("short", "take_profit"), ("long", "liquidation")],
        )
        self.assertFalse(result.open_positions)
        self.assertEqual(result.intrabar_ambiguities, [])

    def test_stop_then_opposite_liquidation(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 125, 95, 125),
        ]
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 50, stop_loss=95),
            OrderIntent.market("short", 50),
        ]])
        result = BacktestEngine(liquidation_config()).run(bars, strategy)
        reasons = {(trade.side, trade.exit_reason) for trade in result.trades}
        self.assertIn(("long", "stop_loss"), reasons)
        self.assertIn(("short", "liquidation"), reasons)
        self.assertFalse(result.open_positions)

    def test_open_exit_then_intrabar_liquidation(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 125, 100, 125),
        ]
        strategy = ScriptedStrategy([
            [OrderIntent.market("long", 50), OrderIntent.market("short", 50)],
            [OrderIntent.exit_market("long")],
        ])
        result = BacktestEngine(liquidation_config()).run(bars, strategy)
        self.assertEqual(
            [(trade.side, trade.exit_reason) for trade in result.trades],
            [("long", "signal_exit"), ("short", "liquidation")],
        )

    def test_ambiguous_path_uses_worst_result_and_records_flag(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 125, 95, 100),
        ]
        strategy = ScriptedStrategy([[
            OrderIntent.market("long", 50, stop_loss=95),
            OrderIntent.market("short", 50),
        ]])
        result = BacktestEngine(liquidation_config()).run(bars, strategy)
        self.assertTrue(any(t.exit_reason == "liquidation" for t in result.trades))
        self.assertEqual(len(result.intrabar_ambiguities), 1)
        ambiguity = result.intrabar_ambiguities[0]
        self.assertEqual(ambiguity.bar_time, 2 * MINUTE)
        self.assertEqual(ambiguity.reason, "AMBIGUOUS_INTRABAR")


class FillMarginAndLimitRegressionTests(unittest.TestCase):
    def test_passive_fill_margin_uses_actual_fill(self):
        bars = [
            Bar(0, 100, 100, 100, 100, 1),
            Bar(MINUTE, 100, 150, 100, 150, 1),
        ]
        strategy = ScriptedStrategy([[
            OrderIntent.limit("short", 80, 150, "GTC")
        ]])
        result = BacktestEngine(
            BacktestConfig(initial_cash=1_000, leverage=10, limit_fill_policy="touch")
        ).run(bars, strategy)
        self.assertIsNone(result.open_short_position)
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(result.rejected_orders[0].reason, "INSUFFICIENT_CROSS_MARGIN")

    def test_slippage_induced_insufficient_margin_is_rejected(self):
        bars = [
            Bar(0, 100, 100, 100, 100, 1),
            Bar(MINUTE, 100, 100, 100, 100, 1),
        ]
        result = BacktestEngine(
            BacktestConfig(initial_cash=1_000, leverage=10, slippage_rate=0.05)
        ).run(bars, ScriptedStrategy([[OrderIntent.market("long", 100)]]))
        self.assertIsNone(result.open_long_position)
        self.assertEqual(result.rejected_orders[0].reason, "INSUFFICIENT_CROSS_MARGIN")
        self.assertEqual(result.rejected_orders[0].event_type, "ORDER_REJECTED")

    def test_margin_rejection_does_not_abort_later_strategy_actions(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,100,100,100,1),
        ]
        result = BacktestEngine(
            BacktestConfig(initial_cash=1_000, leverage=10)
        ).run(
            bars,
            ScriptedStrategy([
                [OrderIntent.market("long", 101)],
                [OrderIntent.market("long", 1)],
            ]),
        )
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(result.rejected_orders[0].event_type, "ORDER_REJECTED")
        self.assertIsNotNone(result.open_long_position)
        self.assertEqual(result.open_long_position.qty, 1)

    def test_marketable_buy_limit_applies_slippage(self):
        bars = [Bar(0,100,100,100,100,1), Bar(MINUTE,100,105,95,100,1)]
        order = OrderIntent.limit("long", 1, 110, "GTC")
        result = BacktestEngine(BacktestConfig(slippage_rate=0.01)).run(
            bars, ScriptedStrategy([[order]])
        )
        self.assertAlmostEqual(result.open_long_position.entry_price, 101.0)

    def test_marketable_short_limit_applies_slippage(self):
        bars = [Bar(0,100,100,100,100,1), Bar(MINUTE,100,105,95,100,1)]
        order = OrderIntent.limit("short", 1, 90, "GTC")
        result = BacktestEngine(BacktestConfig(slippage_rate=0.01)).run(
            bars, ScriptedStrategy([[order]])
        )
        self.assertAlmostEqual(result.open_short_position.entry_price, 99.0)

    def test_marketable_limit_slippage_beyond_cap_does_not_fill(self):
        bars = [Bar(0,100,100,100,100,1), Bar(MINUTE,100,105,95,100,1)]
        orders = [
            OrderIntent.limit("long", 1, 100.5, "IOC"),
            OrderIntent.limit("short", 1, 99.5, "IOC"),
        ]
        result = BacktestEngine(BacktestConfig(slippage_rate=0.01)).run(
            bars, ScriptedStrategy([orders])
        )
        self.assertFalse(result.open_positions)

    def test_slippage_bookkeeping_does_not_change_execution_or_pnl(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,110,110,110,110,1),
        ]
        result = BacktestEngine(BacktestConfig(slippage_rate=0.01)).run(
            bars,
            ScriptedStrategy([
                [OrderIntent.market("long", 1)],
                [OrderIntent.exit_market("long")],
            ]),
        )
        trade = result.trades[0]
        self.assertAlmostEqual(trade.entry_reference_price, 100.0)
        self.assertAlmostEqual(trade.entry_price, 101.0)
        self.assertAlmostEqual(trade.exit_reference_price, 110.0)
        self.assertAlmostEqual(trade.exit_price, 108.9)
        self.assertAlmostEqual(trade.entry_slippage_cost, 1.0)
        self.assertAlmostEqual(trade.exit_slippage_cost, 1.1)
        self.assertAlmostEqual(trade.slippage_cost, 2.1)
        self.assertAlmostEqual(trade.gross_pnl, 7.9)
        self.assertAlmostEqual(trade.net_pnl, 7.9)

    def test_passive_fill_has_zero_slippage_cost(self):
        bars = [Bar(0,105,105,105,105,1), Bar(MINUTE,105,106,99,101,1)]
        result = BacktestEngine(
            BacktestConfig(slippage_rate=0.01, limit_fill_policy="touch")
        ).run(
            bars,
            ScriptedStrategy([[
                OrderIntent.limit("long", 1, 100, "GTC")
            ]]),
        )
        self.assertAlmostEqual(result.open_long_position.entry_reference_price, 100.0)
        self.assertAlmostEqual(result.open_long_position.entry_price, 100.0)
        self.assertAlmostEqual(result.open_long_position.entry_slippage_cost, 0.0)
        self.assertEqual(
            result.open_long_position.entry_fill_classification,
            "PASSIVE_LIMIT_MAKER",
        )


class ValidationAndRiskMetricRegressionTests(unittest.TestCase):
    def test_invalid_enum_values_are_rejected(self):
        for field, value in (
            ("intrabar_policy", "unknown"),
            ("limit_fill_policy", "unknown"),
            ("end_of_data_policy", "unknown"),
            ("funding_price_source", "unknown"),
            ("margin_mode", "unknown"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    BacktestEngine(BacktestConfig(**{field: value}))

    def test_non_finite_funding_and_tiers_are_rejected(self):
        invalid_configs = [
            BacktestConfig(funding_rate_by_time={0: nan}),
            BacktestConfig(funding_price_by_time={0: inf}),
            BacktestConfig(
                liquidation_enabled=True,
                maintenance_tiers=(MaintenanceTier(None, nan, 0),),
            ),
            BacktestConfig(
                liquidation_enabled=True,
                maintenance_tiers=(MaintenanceTier(None, 0.005, inf),),
            ),
        ]
        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    BacktestEngine(config)

    def test_uncapped_tier_must_be_last(self):
        config = BacktestConfig(
            liquidation_enabled=True,
            maintenance_tiers=(
                MaintenanceTier(None, 0.005, 0),
                MaintenanceTier(100_000, 0.01, 500),
            ),
        )
        with self.assertRaises(ValueError):
            BacktestEngine(config)

    def test_close_and_intrabar_drawdown_are_separate(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,100,50,100,1),
        ]
        result = BacktestEngine(BacktestConfig(initial_cash=1_000, leverage=10)).run(
            bars, ScriptedStrategy([[OrderIntent.market("long", 10)]])
        )
        metrics = summarize(result, 1_000)
        self.assertEqual(metrics["close_to_close_max_drawdown_pct"], 0.0)
        self.assertAlmostEqual(metrics["intrabar_worst_max_drawdown_pct"], 50.0)

    def test_equal_hedge_intrabar_drawdown_keeps_costs_only(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,150,50,100,1),
        ]
        config = BacktestConfig(initial_cash=1_000, taker_fee_rate=0.001)
        result = BacktestEngine(config).run(
            bars,
            ScriptedStrategy([[
                OrderIntent.market("long", 1),
                OrderIntent.market("short", 1),
            ]]),
        )
        metrics = summarize(result, 1_000)
        self.assertAlmostEqual(metrics["intrabar_worst_max_drawdown_pct"], 0.02)

    def test_unequal_hedge_uses_one_admissible_price_path(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,150,50,100,1),
        ]
        result = BacktestEngine(BacktestConfig(initial_cash=1_000, leverage=10)).run(
            bars,
            ScriptedStrategy([[
                OrderIntent.market("long", 10),
                OrderIntent.market("short", 5),
            ]]),
        )
        metrics = summarize(result, 1_000)
        self.assertAlmostEqual(metrics["intrabar_worst_max_drawdown_pct"], 25.0)

    def test_intrabar_exit_path_contributes_to_worst_drawdown(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,110,50,100,1),
        ]
        result = BacktestEngine(BacktestConfig(initial_cash=1_000)).run(
            bars,
            ScriptedStrategy([[
                OrderIntent.market("long", 10, take_profit=110),
            ]]),
        )
        metrics = summarize(result, 1_000)
        self.assertAlmostEqual(metrics["intrabar_worst_max_drawdown_pct"], 50.0)
        self.assertEqual(len(result.intrabar_ambiguities), 1)

    def test_near_liquidation_intrabar_drawdown_uses_mark_extreme(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 100, 100, 91, 100),
        ]
        result = BacktestEngine(liquidation_config()).run(
            bars, ScriptedStrategy([[OrderIntent.market("long", 100)]])
        )
        self.assertFalse(any(t.exit_reason == "liquidation" for t in result.trades))
        metrics = summarize(result, 1_000)
        self.assertAlmostEqual(metrics["intrabar_worst_max_drawdown_pct"], 90.0)

    def test_liquidation_model_is_explicit_and_not_verified_by_default(self):
        bars = [
            marked_bar(0, 100, 100, 100, 100),
            marked_bar(1, 100, 100, 100, 100),
            marked_bar(2, 90, 92, 85, 88),
        ]
        result = BacktestEngine(liquidation_config()).run(
            bars, ScriptedStrategy([[OrderIntent.market("long", 100)]])
        )
        trade = result.trades[0]
        self.assertEqual(trade.liquidation_trigger_price, 90)
        self.assertEqual(trade.liquidation_execution_price, 90)
        self.assertEqual(result.qa_status, "NOT VERIFIED")
        self.assertIn(
            "NOT_VERIFIED_LIQUIDATION_EXECUTION_MODEL", result.qa_issues
        )

    def test_leverage_without_liquidation_model_is_not_verified(self):
        result = BacktestEngine(BacktestConfig(leverage=2)).run(
            [Bar(0,100,100,100,100,1)], ScriptedStrategy([])
        )
        self.assertEqual(result.qa_status, "NOT VERIFIED")
        self.assertIn(
            "LEVERAGED_RUN_WITHOUT_LIQUIDATION_MODEL", result.qa_issues
        )

    def test_bar_participation_exposure_has_explicit_definition(self):
        bars = [
            Bar(0,100,100,100,100,1),
            Bar(MINUTE,100,100,100,100,1),
            Bar(2*MINUTE,100,100,100,100,1),
        ]
        result = BacktestEngine(BacktestConfig()).run(
            bars,
            ScriptedStrategy([
                [OrderIntent.market("long", 1)],
                [OrderIntent.exit_market("long")],
            ]),
        )
        metrics = summarize(result, 10_000)
        self.assertEqual(
            result.bar_exposure_curve,
            [(0, False), (MINUTE, True), (2 * MINUTE, True)],
        )
        self.assertAlmostEqual(metrics["time_exposure_pct"], 200 / 3)
        self.assertEqual(
            metrics["time_exposure_definition"],
            "ANY_POSITION_ACTIVE_DURING_BAR_FRACTION",
        )


class StateAndOutputRegressionTests(unittest.TestCase):
    def test_pending_state_preserves_submission_and_fill_resolution(self):
        bars = [Bar(0,100,100,100,100,1), Bar(MINUTE,100,101,99,100,1)]
        result = BacktestEngine(BacktestConfig()).run(
            bars,
            ScriptedStrategy([[OrderIntent.limit("long", 1, 90, "GTC")]]),
        )
        pending = result.pending_orders["long"]
        self.assertEqual(pending.submitted_bar_time, 0)
        self.assertEqual(pending.intent.limit_price, 90)

        filled = BacktestEngine(BacktestConfig(limit_fill_policy="touch")).run(
            [Bar(0,100,100,100,100,1), Bar(MINUTE,100,101,89,95,1)],
            ScriptedStrategy([[OrderIntent.limit("long", 1, 90, "GTC")]]),
        )
        self.assertIsNone(filled.open_long_position.entry_time_exact)
        self.assertEqual(filled.open_long_position.entry_bar_time, MINUTE)
        self.assertEqual(filled.open_long_position.fill_time_resolution, "bar")

    def test_output_contains_provenance_logs_and_is_atomic(self):
        bars = [Bar(0,100,100,100,100,1)]
        config = BacktestConfig(initial_cash=1_000)
        result = BacktestEngine(config).run(bars, ScriptedStrategy([]))
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            output_dir = parent / "run"
            metadata = audit_metadata()
            write_results(output_dir, result, config, metadata)
            expected = {
                "trades.csv", "equity.csv", "intrabar_equity.csv",
                "metrics.json", "config.json", "exposure.json",
                "bar_exposure.csv",
                "intrabar_ambiguities.csv", "rejected_orders.csv",
                "run_metadata.json", "manifest.json",
            }
            self.assertEqual({p.name for p in output_dir.iterdir()}, expected)
            with (output_dir / "run_metadata.json").open() as handle:
                saved = json.load(handle)
            self.assertEqual(saved["strategy"]["name"], "audit_fixture")
            self.assertIn("git_commit", saved["code"])
            self.assertIn("qa_status", saved)
            with (output_dir / "manifest.json").open() as handle:
                manifest = json.load(handle)
            self.assertEqual(set(manifest["checksums"]), expected - {"manifest.json"})

    def test_atomic_output_failure_leaves_no_completed_run(self):
        bars = [Bar(0,100,100,100,100,1)]
        config = BacktestConfig(initial_cash=1_000)
        result = BacktestEngine(config).run(bars, ScriptedStrategy([]))
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            output_dir = parent / "failed-run"
            with patch(
                "research.backtester_v2.output._write_json",
                side_effect=RuntimeError("injected write failure"),
            ):
                with self.assertRaises(RuntimeError):
                    write_results(output_dir, result, config, audit_metadata())
            self.assertFalse(output_dir.exists())
            self.assertFalse(any(".incomplete-" in path.name for path in parent.iterdir()))

    def test_completed_run_is_not_overwritten(self):
        bars = [Bar(0,100,100,100,100,1)]
        config = BacktestConfig(initial_cash=1_000)
        result = BacktestEngine(config).run(bars, ScriptedStrategy([]))
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "run"
            write_results(output_dir, result, config, audit_metadata())
            manifest_before = (output_dir / "manifest.json").read_bytes()
            with self.assertRaises(FileExistsError):
                write_results(output_dir, result, config, audit_metadata())
            self.assertEqual(
                (output_dir / "manifest.json").read_bytes(), manifest_before
            )


if __name__ == "__main__":
    unittest.main()
