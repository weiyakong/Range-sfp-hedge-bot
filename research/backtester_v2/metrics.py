import math
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
    total_bars = len(result.bar_exposure_curve)
    total_return = total_net / initial_cash if initial_cash else None
    close_dd = max_drawdown(result.equity_curve)
    intrabar_dd = max_drawdown(result.intrabar_equity_curve)
    returns = []
    for (_, previous), (_, current) in zip(result.equity_curve, result.equity_curve[1:]):
        if previous:
            returns.append(current / previous - 1.0)
    mean_return = sum(returns) / len(returns) if returns else None
    variance = (
        sum((value - mean_return) ** 2 for value in returns) / len(returns)
        if returns and mean_return is not None else None
    )
    downside = [min(value, 0.0) for value in returns]
    downside_variance = (
        sum(value * value for value in downside) / len(downside)
        if downside else None
    )
    sharpe = (
        mean_return / math.sqrt(variance)
        if mean_return is not None and variance is not None and variance > 0 else None
    )
    sortino = (
        mean_return / math.sqrt(downside_variance)
        if mean_return is not None and downside_variance is not None and downside_variance > 0 else None
    )
    duration_ms = (
        result.equity_curve[-1][0] - result.equity_curve[0][0]
        if len(result.equity_curve) > 1 else 0
    )
    years = duration_ms / (365.25 * 24 * 60 * 60 * 1000)
    annualized_log_growth = (
        math.log(result.final_equity / initial_cash) / years
        if years > 0 and initial_cash > 0 and result.final_equity > 0 else None
    )
    yearly_return = (
        math.exp(annualized_log_growth) - 1.0
        if annualized_log_growth is not None and abs(annualized_log_growth) < 700
        else None
    )
    peak = None
    underwater = 0
    for _, equity in result.equity_curve:
        if peak is None or equity >= peak:
            peak = equity
        else:
            underwater += 1
    turnover = (
        sum(abs(t.entry_price * t.qty) + abs(t.exit_price * t.qty) for t in trades)
        / initial_cash if initial_cash else None
    )
    average_holding = (
        sum(t.exit_time - t.entry_bar_time for t in trades) / len(trades)
        if trades else None
    )
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
        "slippage_cost": (
            sum(t.slippage_cost for t in trades)
            + sum(p.entry_slippage_cost for p in result.open_positions.values())
        ),
        "time_exposure_pct": (
            sum(exposed for _, exposed in result.bar_exposure_curve)
            / total_bars * 100.0
            if total_bars else None
        ),
        "time_exposure_definition": "ANY_POSITION_ACTIVE_DURING_BAR_FRACTION",
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
        "metric_contract_version": "BACKTESTER_V2_METRICS_2",
        "total_return": total_return,
        "expectancy_per_trade": (total_net / len(trades)) if trades else None,
        "win_rate": (len(wins) / len(trades)) if trades else None,
        "close_to_close_max_drawdown": close_dd,
        "intrabar_worst_max_drawdown": intrabar_dd,
        "return_to_intrabar_drawdown": (
            total_return / intrabar_dd
            if total_return is not None and intrabar_dd > 0 else None
        ),
        "time_exposure": (
            sum(exposed for _, exposed in result.bar_exposure_curve) / total_bars
            if total_bars else None
        ),
        "turnover": turnover,
        "average_holding_time": average_holding,
        "ambiguity_rate": (
            len(result.intrabar_ambiguities) / total_bars if total_bars else None
        ),
        "yearly_return": yearly_return,
        "sharpe": sharpe,
        "sortino": sortino,
        "recovery_factor": (
            total_return / close_dd
            if total_return is not None and close_dd > 0 else None
        ),
        "time_underwater": underwater / total_bars if total_bars else None,
    }


def trades_as_dicts(trades: List[Trade]) -> List[dict]:
    return [asdict(trade) for trade in trades]
