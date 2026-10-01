from __future__ import annotations

import subprocess
import sys
import types
import unittest
from dataclasses import fields
from pathlib import Path

from research.backtester_v2 import engine as current_engine
from research.backtester_v2 import models as current_models


REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCE = "2b096ebf52928248ad2e608be685bef37a7d6887"
MINUTE = 60_000


def load_reference():
    package_name = "_reference_backtester_v2"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    loaded = {}
    for name in ("models", "engine"):
        module_name = f"{package_name}.{name}"
        module = types.ModuleType(module_name)
        module.__package__ = package_name
        sys.modules[module_name] = module
        source = subprocess.check_output(
            ["git", "show", f"{REFERENCE}:research/backtester_v2/{name}.py"],
            cwd=REPO_ROOT, text=True,
        )
        exec(compile(source, f"{REFERENCE}/{name}.py", "exec"), module.__dict__)
        loaded[name] = module
    return loaded["models"], loaded["engine"]


class Scripted:
    def __init__(self, steps):
        self.steps = steps
        self.index = 0

    def on_bar(self, bar, state):
        result = self.steps[self.index] if self.index < len(self.steps) else []
        self.index += 1
        return result


def bar(m, index, o, h=None, l=None, c=None, marked=False):
    h = o if h is None else h
    l = o if l is None else l
    c = o if c is None else c
    marks = (o, h, l, c) if marked else (None, None, None, None)
    return m.Bar(index * MINUTE, o, h, l, c, 1.0, *marks)


def project(result):
    trade_keys = (
        "side", "qty", "entry_bar_time", "entry_time_exact", "fill_time_resolution",
        "exit_time", "entry_price", "exit_price", "gross_pnl", "fees", "funding",
        "liquidation_fee", "net_pnl", "exit_reason", "liquidation_trigger_price",
        "liquidation_execution_price",
    )
    position_keys = (
        "side", "qty", "entry_bar_time", "entry_time_exact", "fill_time_resolution",
        "entry_price", "stop_loss", "take_profit", "max_hold_bars", "entry_fee",
        "funding_paid",
    )
    return {
        "final_cash": result.final_cash,
        "final_equity": result.final_equity,
        "trades": [tuple(getattr(item, key) for key in trade_keys) for item in result.trades],
        "equity_curve": result.equity_curve,
        "intrabar_equity_curve": result.intrabar_equity_curve,
        "open_positions": {
            side: tuple(getattr(item, key) for key in position_keys)
            for side, item in result.open_positions.items()
        },
        "pending": sorted(result.pending_orders),
        "rejected": [(item.side, item.reason, item.order_type) for item in result.rejected_orders],
        "ambiguities": len(result.intrabar_ambiguities),
        "open_unrealized": result.open_position_unrealized_pnl,
        "open_entry_fee": result.open_position_entry_fee,
        "open_funding": result.open_position_funding,
        "qa_status": result.qa_status,
        "qa_issues": result.qa_issues,
    }


def scenarios(m):
    O = m.OrderIntent
    base = [bar(m, 0, 100), bar(m, 1, 100), bar(m, 2, 110)]
    return {
        "no_trade": (m.BacktestConfig(), base, [[], [], []]),
        "market_long": (m.BacktestConfig(), base, [[O.market("long", 1)], [O.exit_market("long")]]),
        "market_short": (m.BacktestConfig(), base, [[O.market("short", 1)], [O.exit_market("short")]]),
        "marketable_limit_long": (m.BacktestConfig(slippage_rate=0.001), base, [[O.limit("long", 1, 105, "GTC")], [O.exit_market("long")]]),
        "marketable_limit_short": (m.BacktestConfig(slippage_rate=0.001), base, [[O.limit("short", 1, 95, "GTC")], [O.exit_market("short")]]),
        "passive_limit_long": (m.BacktestConfig(limit_fill_policy="touch"), [bar(m, 0, 105), bar(m, 1, 105, 106, 99, 101)], [[O.limit("long", 1, 100, "GTC")]]),
        "passive_limit_short": (m.BacktestConfig(limit_fill_policy="touch"), [bar(m, 0, 95), bar(m, 1, 95, 101, 94, 99)], [[O.limit("short", 1, 100, "GTC")]]),
        "gap_stop": (m.BacktestConfig(), [bar(m, 0, 100), bar(m, 1, 100), bar(m, 2, 80)], [[O.market("long", 1, stop_loss=90)]]),
        "gap_target": (m.BacktestConfig(), [bar(m, 0, 100), bar(m, 1, 100), bar(m, 2, 120)], [[O.market("long", 1, take_profit=110)]]),
        "signal_exit": (m.BacktestConfig(), base, [[O.market("long", 1)], [O.exit_market("long")]]),
        "hedge": (m.BacktestConfig(), base, [[O.market("long", 1), O.market("short", 1)], [O.exit_market("long"), O.exit_market("short")]]),
        "funding": (m.BacktestConfig(funding_rate_by_time={MINUTE: 0.001}, funding_price_by_time={MINUTE: 100}), [bar(m, 0, 100), bar(m, 1, 100)], [[O.market("long", 1)]]),
        "eod_force_close": (m.BacktestConfig(end_of_data_policy="force_close"), [bar(m, 0, 100), bar(m, 1, 105)], [[O.market("long", 1)]]),
        "liquidation": (m.BacktestConfig(initial_cash=1000, leverage=10, liquidation_enabled=True, maintenance_tiers=(m.MaintenanceTier(None, 0.005, 0),)), [bar(m, 0, 100, marked=True), bar(m, 1, 100, marked=True), bar(m, 2, 100, 100, 70, 70, marked=True)], [[O.market("long", 90)]]),
        "ioc_no_fill": (m.BacktestConfig(), [bar(m, 0, 100), bar(m, 1, 100, 101, 99, 100)], [[O.limit("long", 1, 90, "IOC")]]),
    }


class DifferentialExecutionReferenceTests(unittest.TestCase):
    def test_15_execution_classes_match_pre_enforcement_reference(self) -> None:
        reference_models, reference_engine = load_reference()
        current = scenarios(current_models)
        reference = scenarios(reference_models)
        self.assertEqual(set(current), set(reference))
        self.assertEqual(len(current), 15)
        for name in sorted(current):
            current_config, current_bars, current_steps = current[name]
            reference_config, reference_bars, reference_steps = reference[name]
            with self.subTest(scenario=name):
                current_result = current_engine.BacktestEngine(current_config).run(
                    current_bars, Scripted(current_steps),
                )
                reference_result = reference_engine.BacktestEngine(reference_config).run(
                    reference_bars, Scripted(reference_steps),
                )
                self.assertEqual(project(current_result), project(reference_result))


if __name__ == "__main__":
    unittest.main()
