"""Exact V2-to-V3-A BTC differential harness for grid-valid inputs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Mapping, Sequence, Tuple

from research.backtester_v2.models import BacktestResult, OrderIntent

from .contracts import canonical_json_bytes


class DifferentialError(AssertionError):
    """Raised for any unexplained V2/V3-A semantic or numeric difference."""


def _maximum_drawdown(equity_curve: Sequence[Tuple[int, float]]) -> float:
    peak: float = float("-inf")
    maximum = 0.0
    for _, equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def differential_snapshot(
    result: BacktestResult,
    intents: Sequence[OrderIntent],
) -> Mapping[str, object]:
    """Expose every required differential dimension as deterministic data."""
    trades = [asdict(item) for item in result.trades]
    return {
        "signals_and_intents": [asdict(item) for item in intents],
        "submissions": [asdict(item) for item in intents],
        "fills": [
            {
                "side": item.side,
                "qty": item.qty,
                "entry_bar_time": item.entry_bar_time,
                "entry_time_exact": item.entry_time_exact,
                "exit_time": item.exit_time,
                "entry_price": item.entry_price,
                "exit_price": item.exit_price,
                "entry_fill_classification": item.entry_fill_classification,
                "exit_fill_classification": item.exit_fill_classification,
            }
            for item in result.trades
        ],
        "trade_log": trades,
        "fees": [item.fees for item in result.trades],
        "slippage": [item.slippage_cost for item in result.trades],
        "funding": [item.funding for item in result.trades],
        "realized_pnl": [item.net_pnl for item in result.trades],
        "unrealized_pnl": result.open_position_unrealized_pnl,
        "liquidation": [
            {
                "reason": item.exit_reason,
                "trigger": item.liquidation_trigger_price,
                "execution": item.liquidation_execution_price,
                "fee": item.liquidation_fee,
            }
            for item in result.trades
        ],
        "open_positions": {
            key: asdict(value) for key, value in result.open_positions.items()
        },
        "pending_orders": {
            key: asdict(value) for key, value in result.pending_orders.items()
        },
        "rejected_orders": [asdict(item) for item in result.rejected_orders],
        "final_cash": result.final_cash,
        "final_equity": result.final_equity,
        "equity_curve": result.equity_curve,
        "intrabar_equity_curve": result.intrabar_equity_curve,
        "drawdown": _maximum_drawdown(result.equity_curve),
        "ambiguity_labels": [asdict(item) for item in result.intrabar_ambiguities],
        "qa_status": result.qa_status,
        "qa_issues": result.qa_issues,
    }


def assert_v2_v3a_equivalent(
    v2_result: BacktestResult,
    v3a_result: BacktestResult,
    v2_intents: Sequence[OrderIntent],
    v3a_intents: Sequence[OrderIntent],
) -> None:
    left = differential_snapshot(v2_result, v2_intents)
    right = differential_snapshot(v3a_result, v3a_intents)
    mismatches = [
        field
        for field in left
        if canonical_json_bytes(left[field]) != canonical_json_bytes(right[field])
    ]
    if mismatches:
        raise DifferentialError(
            "unexplained V2/V3-A differential in: " + ", ".join(mismatches),
        )


__all__ = [
    "DifferentialError",
    "assert_v2_v3a_equivalent",
    "differential_snapshot",
]
