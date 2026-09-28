from dataclasses import asdict
from typing import Dict, List, Optional

from .models import BacktestResult, Trade


def max_drawdown(equity_curve: List[tuple]) -> float:
    peak: Optional[float] = None
    worst = 0.0
    for _, equity in equity_curve:
        if peak is None or equity > peak:
            peak = equity
        if peak is not None and peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return worst


def summarize(result: BacktestResult, initial_cash: float) -> Dict[str, object]:
    trades = result.trades
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl < 0]
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = -sum(t.net_pnl for t in losses)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    realized_net = sum(t.net_pnl for t in trades)
    total_net = result.final_equity - initial_cash
    closed_fees = sum(t.fees for t in trades)
    closed_funding = sum(t.funding for t in trades)
    liquidation_fees = sum(t.liquidation_fee for t in trades)
    liquidation_trades = [t for t in trades if t.exit_reason == "liquidation"]
    liquidation_events = len({t.exit_time for t in liquidation_trades})
    return {
        "trades": len(trades),
        "net_pnl": total_net,
        "realized_net_pnl": realized_net,
        "unrealized_pnl": result.open_position_unrealized_pnl,
        "return_pct": (total_net / initial_cash * 100.0) if initial_cash else None,
        "win_rate_pct": (len(wins) / len(trades) * 100.0) if trades else None,
        "profit_factor": profit_factor,
        "close_to_close_max_drawdown_pct": max_drawdown(result.equity_curve) * 100.0,
        "intrabar_worst_max_drawdown_pct": (
            max_drawdown(result.intrabar_equity_curve) * 100.0
        ),
        "fees": closed_fees + result.open_position_entry_fee,
        "funding": closed_funding + result.open_position_funding,
        "liquidation_fees": liquidation_fees,
        "expectancy_closed_trade": (realized_net / len(trades)) if trades else None,
        "final_cash": result.final_cash,
        "final_equity": result.final_equity,
        "open_position": bool(result.open_positions),
        "open_long": "long" in result.open_positions,
        "open_short": "short" in result.open_positions,
        "open_legs": len(result.open_positions),
        "liquidation_events": liquidation_events,
        "liquidated_legs": len(liquidation_trades),
        "rejected_orders": len(result.rejected_orders),
        "intrabar_ambiguities": len(result.intrabar_ambiguities),
        "qa_status": result.qa_status,
        "qa_issues": list(result.qa_issues),
    }


def trades_as_dicts(trades: List[Trade]) -> List[dict]:
    return [asdict(trade) for trade in trades]
