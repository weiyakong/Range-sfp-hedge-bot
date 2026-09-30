from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

from .models import (
    BacktestConfig,
    BacktestResult,
    Bar,
    EngineState,
    IntrabarAmbiguity,
    MaintenanceTier,
    OrderIntent,
    PendingOrder,
    Position,
    PositionSnapshot,
    RejectedOrder,
    Side,
    StrategyState,
    Trade,
)


class Strategy(Protocol):
    def on_bar(self, bar: Bar, state: StrategyState) -> List[OrderIntent]:
        ...


@dataclass
class _PathCandidate:
    name: str
    state: EngineState
    trades: List[Trade]
    rejected_orders: List[RejectedOrder]
    worst_equity: float
    ambiguity_events: Tuple[str, ...]


class BacktestEngine:
    """Causal 1m OHLC backtester with cross-margin hedge-mode support."""

    SIDES: Tuple[Side, Side] = ("long", "short")

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._validate_config()

    def run(self, bars: Iterable[Bar], strategy: Strategy) -> BacktestResult:
        state = EngineState(cash=self.config.initial_cash)
        trades: List[Trade] = []
        equity_curve: List[Tuple[int, float]] = []
        intrabar_equity_curve: List[Tuple[int, float]] = []
        bar_exposure_curve: List[Tuple[int, bool]] = []
        rejected_orders: List[RejectedOrder] = []
        ambiguities: List[IntrabarAmbiguity] = []
        last_time: Optional[int] = None
        last_bar: Optional[Bar] = None

        for index, bar in enumerate(bars):
            self._validate_bar(bar, last_time)
            last_time = bar.open_time
            last_bar = bar
            positions_before_bar = bool(state.positions)
            trades_before_bar = len(trades)

            self._apply_funding(state, bar)
            liquidated = self._check_liquidation_at_open(state, trades, bar)
            if not liquidated:
                self._process_scheduled_open_exits(state, trades, bar, index)
                self._process_gap_exits(state, trades, bar)
                self._process_open_entries(state, bar, index, rejected_orders)
                liquidated = self._check_liquidation_at_open(state, trades, bar)
                if not liquidated:
                    intrabar_worst = self._process_intrabar_paths(
                        state, trades, rejected_orders, ambiguities, bar, index,
                    )
                else:
                    intrabar_worst = state.cash
            else:
                intrabar_worst = state.cash

            equity = self._equity_at_close(state, bar)
            equity_curve.append((bar.open_time, equity))
            intrabar_equity_curve.append((bar.open_time, min(equity, intrabar_worst)))
            bar_exposure_curve.append((
                bar.open_time,
                positions_before_bar or bool(state.positions) or len(trades) > trades_before_bar,
            ))
            intents = strategy.on_bar(bar, self._strategy_state(state, equity))
            self._accept_strategy_intents(state, intents, bar.open_time)

        return self._finalize(
            state, trades, equity_curve, intrabar_equity_curve,
            bar_exposure_curve, rejected_orders, ambiguities, last_bar,
        )
    def _finalize(
        self, state: EngineState, trades: List[Trade],
        equity_curve: List[Tuple[int, float]],
        intrabar_equity_curve: List[Tuple[int, float]],
        bar_exposure_curve: List[Tuple[int, bool]],
        rejected_orders: List[RejectedOrder],
        ambiguities: List[IntrabarAmbiguity],
        last_bar: Optional[Bar],
    ) -> BacktestResult:
        if last_bar is None:
            return BacktestResult(
                final_cash=state.cash, final_equity=state.cash, trades=trades,
                equity_curve=[], intrabar_equity_curve=[], open_positions={},
                bar_exposure_curve=[],
                pending_orders=dict(state.pending_orders),
                rejected_orders=rejected_orders,
                intrabar_ambiguities=ambiguities,
                open_position_unrealized_pnl=0.0,
                open_position_entry_fee=0.0,
                open_position_funding=0.0,
                qa_status=self._qa_status()[0], qa_issues=self._qa_status()[1],
            )

        if state.positions and self.config.end_of_data_policy == "force_close":
            for side in list(self.SIDES):
                if side in state.positions:
                    self._close_position(
                        state, trades, side, last_bar.open_time, last_bar.close,
                        "eod_force_close", taker=True,
                    )
            equity_curve[-1] = (last_bar.open_time, state.cash)
            intrabar_equity_curve[-1] = (
                last_bar.open_time,
                min(intrabar_equity_curve[-1][1], state.cash),
            )

        mark = self._mark_close(last_bar)
        unrealized = sum(self._gross_pnl(p, mark) for p in state.positions.values())
        entry_fees = sum(p.entry_fee for p in state.positions.values())
        funding = sum(p.funding_paid for p in state.positions.values())
        final_equity = equity_curve[-1][1]
        return BacktestResult(
            final_cash=state.cash, final_equity=final_equity, trades=trades,
            equity_curve=equity_curve,
            intrabar_equity_curve=intrabar_equity_curve,
            bar_exposure_curve=bar_exposure_curve,
            open_positions=dict(state.positions),
            pending_orders=dict(state.pending_orders),
            rejected_orders=rejected_orders,
            intrabar_ambiguities=ambiguities,
            open_position_unrealized_pnl=unrealized,
            open_position_entry_fee=entry_fees,
            open_position_funding=funding,
            qa_status=self._qa_status()[0], qa_issues=self._qa_status()[1],
        )
    def _process_scheduled_open_exits(
        self, state: EngineState, trades: List[Trade], bar: Bar, bar_index: int,
    ) -> None:
        for side in list(self.SIDES):
            position = state.positions.get(side)
            if position is None:
                continue
            pending = state.pending_orders.get(side)
            if pending is not None and pending.intent.action == "exit":
                del state.pending_orders[side]
                self._close_position(
                    state, trades, side, bar.open_time, bar.open,
                    "signal_exit", taker=True,
                )
                continue
            if self._time_exit_due(position, bar_index):
                self._close_position(
                    state, trades, side, bar.open_time, bar.open,
                    "time_exit", taker=True,
                )

    def _process_gap_exits(
        self, state: EngineState, trades: List[Trade], bar: Bar,
    ) -> None:
        for side in list(self.SIDES):
            position = state.positions.get(side)
            if position is None:
                continue
            if side == "long":
                stop_gap = position.stop_loss is not None and bar.open <= position.stop_loss
                target_gap = position.take_profit is not None and bar.open >= position.take_profit
            else:
                stop_gap = position.stop_loss is not None and bar.open >= position.stop_loss
                target_gap = position.take_profit is not None and bar.open <= position.take_profit
            if stop_gap:
                self._close_position(state, trades, side, bar.open_time, bar.open,
                                     "stop_loss_gap", taker=True)
            elif target_gap:
                self._close_position(state, trades, side, bar.open_time,
                                     position.take_profit, "take_profit_gap", taker=False)
    def _process_open_entries(
        self, state: EngineState, bar: Bar, bar_index: int,
        rejected_orders: List[RejectedOrder],
    ) -> None:
        """Fill orders executable at the bar open; leave passive limits pending."""
        for side in self.SIDES:
            pending = state.pending_orders.get(side)
            if pending is None or pending.intent.action != "enter" or side in state.positions:
                continue
            order = pending.intent
            self._validate_order(order)
            fill: Optional[float] = None
            reference_price: Optional[float] = None
            fill_classification: Optional[str] = None
            if order.order_type == "market":
                reference_price = bar.open
                fill = self._apply_slippage(bar.open, side, True)
                fill_classification = "MARKET_TAKER"
            else:
                assert order.limit_price is not None
                marketable = (
                    bar.open <= order.limit_price if side == "long"
                    else bar.open >= order.limit_price
                )
                if marketable:
                    candidate = self._apply_slippage(bar.open, side, True)
                    within_cap = (
                        candidate <= order.limit_price if side == "long"
                        else candidate >= order.limit_price
                    )
                    if within_cap:
                        reference_price = bar.open
                        fill = candidate
                        fill_classification = "MARKETABLE_LIMIT_TAKER"
                    elif order.time_in_force == "IOC":
                        del state.pending_orders[side]
                elif order.time_in_force == "IOC":
                    # IOC remains eligible for a passive attempt during this bar.
                    pass
            if fill is None:
                continue
            mark_price = self._mark_open_or_trade_open(bar)
            if not self._has_entry_capacity(state, order, fill, mark_price, taker=True):
                self._reject_order(
                    state, rejected_orders, side, order, bar.open_time, fill,
                    "INSUFFICIENT_CROSS_MARGIN",
                )
                continue
            del state.pending_orders[side]
            self._open_position(
                state, order, fill, bar.open_time, bar_index,
                taker=True, passive=False,
                reference_price=reference_price if reference_price is not None else fill,
                fill_classification=fill_classification or "MARKET_TAKER",
            )

    def _has_entry_capacity(
        self, state: EngineState, order: OrderIntent, fill_price: float,
        mark_price: float, taker: bool,
    ) -> bool:
        fee_rate = self.config.taker_fee_rate if taker else self.config.maker_fee_rate
        entry_fee = abs(fill_price * order.qty) * fee_rate
        post_fill_equity = self._account_equity(state, mark_price) - entry_fee
        if order.side == "long":
            post_fill_equity += (mark_price - fill_price) * order.qty
        else:
            post_fill_equity += (fill_price - mark_price) * order.qty
        required = sum(
            abs(position.qty * mark_price) / self.config.leverage
            for position in state.positions.values()
        )
        required += abs(order.qty * fill_price) / self.config.leverage
        return required <= post_fill_equity + 1e-12

    @staticmethod
    def _reject_order(
        state: EngineState, rejected_orders: List[RejectedOrder], side: Side,
        order: OrderIntent, bar_time: int, attempted_fill_price: Optional[float],
        reason: str,
    ) -> None:
        state.pending_orders.pop(side, None)
        rejected_orders.append(RejectedOrder(
            bar_time=bar_time, side=side, reason=reason,
            order_type=order.order_type, qty=order.qty,
            limit_price=order.limit_price,
            attempted_fill_price=attempted_fill_price,
        ))

    def _open_position(
        self, state: EngineState, order: OrderIntent, fill_price: float,
        fill_time: int, bar_index: int, taker: bool, passive: bool,
        reference_price: float, fill_classification: str,
    ) -> None:
        side = order.side
        if side is None:
            raise ValueError("entry order requires side")
        if side in state.positions:
            raise ValueError(f"{side} position already open")
        self._validate_protective_levels(order, fill_price)
        fee_rate = self.config.taker_fee_rate if taker else self.config.maker_fee_rate
        entry_fee = abs(fill_price * order.qty) * fee_rate
        state.cash -= entry_fee
        state.positions[side] = Position(
            side=side, qty=order.qty, entry_bar_time=fill_time,
            entry_time_exact=None if passive else fill_time,
            fill_time_resolution="bar" if passive else "exact",
            entry_price=fill_price, entry_bar_index=bar_index,
            entry_reference_price=reference_price,
            entry_fill_classification=fill_classification,
            entry_slippage_cost=self._slippage_cost(
                side, order.qty, reference_price, fill_price, is_entry=True,
            ),
            stop_loss=order.stop_loss, take_profit=order.take_profit,
            max_hold_bars=order.max_hold_bars, entry_fee=entry_fee,
        )
    def _process_intrabar_paths(
        self, state: EngineState, trades: List[Trade],
        rejected_orders: List[RejectedOrder],
        ambiguities: List[IntrabarAmbiguity], bar: Bar, bar_index: int,
    ) -> float:
        """Simulate both admissible OHLC paths and retain the worst result."""
        base_trade_count = len(trades)
        open_before = tuple(side for side in self.SIDES if side in state.positions)
        candidates = [
            self._simulate_path(
                "high_then_low", state, trades, rejected_orders, bar, bar_index,
                (bar.open, bar.high, bar.low, bar.close),
                self._mark_path(bar, high_first=True),
            ),
            self._simulate_path(
                "low_then_high", state, trades, rejected_orders, bar, bar_index,
                (bar.open, bar.low, bar.high, bar.close),
                self._mark_path(bar, high_first=False),
            ),
        ]
        signatures = [self._path_signature(item, base_trade_count) for item in candidates]
        chosen = min(
            candidates,
            key=lambda item: (
                self._account_equity(item.state, self._mark_close(bar)),
                item.worst_equity,
                item.state.cash,
                item.name,
            ),
        )
        state.cash = chosen.state.cash
        state.positions = chosen.state.positions
        state.pending_orders = chosen.state.pending_orders
        trades[:] = chosen.trades
        rejected_orders[:] = chosen.rejected_orders
        internal_ambiguities = tuple(
            event
            for candidate in candidates
            for event in candidate.ambiguity_events
        )
        if signatures[0] != signatures[1] or internal_ambiguities:
            ambiguities.append(IntrabarAmbiguity(
                bar_time=bar.open_time,
                open_legs_before=open_before,
                competing_paths="high_then_low|low_then_high",
                chosen_path=chosen.name,
                resulting_trade_indices=tuple(range(base_trade_count, len(trades))),
                resulting_legs=tuple(
                    side for side in self.SIDES if side in state.positions
                ),
                competing_events=(
                    f"{signatures[0]} | {signatures[1]}"
                    + (f" | simultaneous={internal_ambiguities}"
                       if internal_ambiguities else "")
                ),
            ))
        return chosen.worst_equity

    def _mark_path(self, bar: Bar, high_first: bool) -> Tuple[float, float, float, float]:
        if self.config.liquidation_enabled:
            values = (
                self._require_mark(bar.mark_open, "mark_open"),
                self._require_mark(bar.mark_high, "mark_high"),
                self._require_mark(bar.mark_low, "mark_low"),
                self._require_mark(bar.mark_close, "mark_close"),
            )
        else:
            values = (bar.open, bar.high, bar.low, bar.close)
        return values if high_first else (values[0], values[2], values[1], values[3])

    def _simulate_path(
        self, name: str, source_state: EngineState, source_trades: List[Trade],
        source_rejections: List[RejectedOrder], bar: Bar, bar_index: int,
        trade_path: Tuple[float, float, float, float],
        mark_path: Tuple[float, float, float, float],
    ) -> _PathCandidate:
        state = deepcopy(source_state)
        trades = deepcopy(source_trades)
        rejections = deepcopy(source_rejections)
        ambiguity_events: List[str] = []
        worst = self._account_equity(state, mark_path[0])
        for index in range(3):
            worst = min(
                worst,
                self._simulate_segment(
                    state, trades, rejections, bar, bar_index,
                    trade_path[index], trade_path[index + 1],
                    mark_path[index], mark_path[index + 1],
                    ambiguity_events,
                ),
            )
        for side in self.SIDES:
            pending = state.pending_orders.get(side)
            if (
                pending is not None
                and pending.intent.action == "enter"
                and pending.intent.time_in_force == "IOC"
            ):
                del state.pending_orders[side]
        return _PathCandidate(
            name, state, trades, rejections, worst, tuple(ambiguity_events)
        )

    def _simulate_segment(
        self, state: EngineState, trades: List[Trade],
        rejected_orders: List[RejectedOrder], bar: Bar, bar_index: int,
        trade_start: float, trade_end: float, mark_start: float, mark_end: float,
        ambiguity_events: List[str],
    ) -> float:
        current_trade = trade_start
        current_mark = mark_start
        worst = self._account_equity(state, current_mark)
        for _ in range(32):
            events: List[Tuple[float, int, str, Optional[Side], float]] = []
            liquidation_progress = self._liquidation_progress(
                state, current_mark, mark_end,
            )
            if liquidation_progress is not None:
                trigger = current_mark + (mark_end - current_mark) * liquidation_progress
                events.append((liquidation_progress, 0, "liquidation", None, trigger))
            for side in self.SIDES:
                position = state.positions.get(side)
                if position is not None:
                    events.extend(
                        self._protective_events(position, current_trade, trade_end)
                    )
                pending = state.pending_orders.get(side)
                if (
                    pending is not None
                    and pending.intent.action == "enter"
                    and pending.intent.order_type == "limit"
                    and side not in state.positions
                ):
                    progress = self._passive_fill_progress(
                        pending.intent, current_trade, trade_end,
                    )
                    if progress is not None:
                        assert pending.intent.limit_price is not None
                        events.append((progress, 1, "passive_fill", side,
                                       pending.intent.limit_price))
            if not events:
                current_trade = trade_end
                current_mark = mark_end
                worst = min(worst, self._account_equity(state, current_mark))
                break
            events.sort()
            progress = events[0][0]
            simultaneous = [
                item for item in events if abs(item[0] - progress) <= 1e-12
            ]
            if len(simultaneous) > 1:
                ambiguity_events.append(str(tuple(
                    (item[2], item[3], item[4]) for item in simultaneous
                )))
            current_trade += (trade_end - current_trade) * progress
            current_mark += (mark_end - current_mark) * progress
            worst = min(worst, self._account_equity(state, current_mark))
            for _, _, event, side, price in simultaneous:
                if event == "liquidation":
                    self._close_liquidation_all(
                        state, trades, bar.open_time,
                        trigger_price=price, execution_price=price,
                    )
                elif event == "passive_fill":
                    assert side is not None
                    pending = state.pending_orders.get(side)
                    if pending is None or side in state.positions:
                        continue
                    order = pending.intent
                    if not self._has_entry_capacity(
                        state, order, price, current_mark, taker=False,
                    ):
                        self._reject_order(
                            state, rejected_orders, side, order, bar.open_time,
                            price, "INSUFFICIENT_CROSS_MARGIN",
                        )
                    else:
                        del state.pending_orders[side]
                        self._open_position(
                            state, order, price, bar.open_time, bar_index,
                            taker=False, passive=True, reference_price=price,
                            fill_classification="PASSIVE_LIMIT_MAKER",
                        )
                else:
                    assert side is not None
                    position = state.positions.get(side)
                    if position is None:
                        continue
                    reason = event
                    if (
                        reason == "stop_loss"
                        and position.fill_time_resolution == "bar"
                        and position.entry_bar_time == bar.open_time
                    ):
                        reason = "stop_loss_same_bar_after_limit"
                    self._close_position(
                        state, trades, side, bar.open_time, price, reason,
                        taker=event == "stop_loss",
                    )
                worst = min(worst, self._account_equity(state, current_mark))
                if (
                    event != "liquidation"
                    and self.config.liquidation_enabled
                    and self._is_liquidatable(state, current_mark)
                ):
                    self._close_liquidation_all(
                        state, trades, bar.open_time,
                        trigger_price=current_mark,
                        execution_price=current_mark,
                    )
                    worst = min(worst, state.cash)
                    break
            if not state.positions and not state.pending_orders:
                break
        else:
            raise RuntimeError("intrabar event loop did not converge")
        return worst

    def _liquidation_progress(
        self, state: EngineState, mark_start: float, mark_end: float,
    ) -> Optional[float]:
        if not self.config.liquidation_enabled or not state.positions:
            return None
        if self._is_liquidatable(state, mark_start):
            return 0.0
        if not self._is_liquidatable(state, mark_end):
            return None
        trigger = self._find_liquidation_trigger(state, mark_start, mark_end)
        if mark_end == mark_start:
            return 0.0
        return max(0.0, min(1.0, (trigger - mark_start) / (mark_end - mark_start)))

    def _protective_events(
        self, position: Position, start: float, end: float,
    ) -> List[Tuple[float, int, str, Optional[Side], float]]:
        events: List[Tuple[float, int, str, Optional[Side], float]] = []
        for reason, level, priority in (
            ("stop_loss", position.stop_loss, 0),
            ("take_profit", position.take_profit, 2),
        ):
            if level is None:
                continue
            progress = self._crossing_progress(start, end, level)
            if progress is not None:
                events.append((progress, priority, reason, position.side, level))
        return events

    def _passive_fill_progress(
        self, order: OrderIntent, start: float, end: float,
    ) -> Optional[float]:
        assert order.side is not None and order.limit_price is not None
        level = order.limit_price
        if order.side == "long":
            eligible = end <= level if self.config.limit_fill_policy == "touch" else end < level
            direction_ok = end < start
        else:
            eligible = end >= level if self.config.limit_fill_policy == "touch" else end > level
            direction_ok = end > start
        if not eligible or not direction_ok:
            return None
        return self._crossing_progress(start, end, level)

    @staticmethod
    def _crossing_progress(start: float, end: float, level: float) -> Optional[float]:
        if start == end:
            return None
        progress = (level - start) / (end - start)
        return progress if 0.0 < progress <= 1.0 else None

    @staticmethod
    def _path_signature(
        candidate: _PathCandidate, base_trade_count: int,
    ) -> Tuple[object, ...]:
        return (
            tuple(
                (trade.side, trade.exit_reason, round(trade.exit_price, 12))
                for trade in candidate.trades[base_trade_count:]
            ),
            tuple(
                (side, round(position.entry_price, 12))
                for side, position in sorted(candidate.state.positions.items())
            ),
            tuple(
                (side, pending.intent.action, pending.intent.order_type)
                for side, pending in sorted(candidate.state.pending_orders.items())
            ),
            tuple(
                (item.side, item.reason, item.order_type)
                for item in candidate.rejected_orders
            ),
            round(candidate.worst_equity, 12),
        )

    def _close_position(
        self, state: EngineState, trades: List[Trade], side: Side,
        exit_time: int, raw_price: float, reason: str, taker: bool,
    ) -> None:
        position = state.positions.get(side)
        if position is None:
            return
        exit_price = (
            self._apply_slippage(raw_price, side, False) if taker else raw_price
        )
        gross = self._gross_pnl(position, exit_price)
        exit_slippage_cost = self._slippage_cost(
            side, position.qty, raw_price, exit_price, is_entry=False,
        )
        fee_rate = self.config.taker_fee_rate if taker else self.config.maker_fee_rate
        exit_fee = abs(exit_price * position.qty) * fee_rate
        total_fees = position.entry_fee + exit_fee
        net = gross - total_fees - position.funding_paid
        state.cash += gross - exit_fee
        trades.append(Trade(
            side=side, qty=position.qty,
            entry_bar_time=position.entry_bar_time,
            entry_time_exact=position.entry_time_exact,
            fill_time_resolution=position.fill_time_resolution,
            exit_time=exit_time,
            entry_price=position.entry_price, exit_price=exit_price,
            entry_reference_price=position.entry_reference_price,
            exit_reference_price=raw_price,
            entry_fill_classification=position.entry_fill_classification,
            exit_fill_classification=(
                "STOP_MARKET_TAKER" if reason.startswith("stop_loss")
                else "MARKET_EXIT_TAKER" if taker
                else "PROTECTIVE_LIMIT_MAKER"
            ),
            entry_slippage_cost=position.entry_slippage_cost,
            exit_slippage_cost=exit_slippage_cost,
            slippage_cost=position.entry_slippage_cost + exit_slippage_cost,
            gross_pnl=gross, fees=total_fees,
            funding=position.funding_paid, liquidation_fee=0.0,
            net_pnl=net, exit_reason=reason,
        ))
        del state.positions[side]
        pending = state.pending_orders.get(side)
        if pending is not None and pending.intent.action == "exit":
            del state.pending_orders[side]

    def _close_liquidation_all(
        self, state: EngineState, trades: List[Trade],
        exit_time: int, trigger_price: float, execution_price: float,
    ) -> None:
        for side in list(self.SIDES):
            position = state.positions.get(side)
            if position is None:
                continue
            gross = self._gross_pnl(position, execution_price)
            liq_fee = (
                abs(execution_price * position.qty)
                * self.config.liquidation_fee_rate
            )
            net = gross - position.entry_fee - position.funding_paid - liq_fee
            state.cash += gross - liq_fee
            trades.append(Trade(
                side=side, qty=position.qty,
                entry_bar_time=position.entry_bar_time,
                entry_time_exact=position.entry_time_exact,
                fill_time_resolution=position.fill_time_resolution,
                exit_time=exit_time,
                entry_price=position.entry_price, exit_price=execution_price,
                entry_reference_price=position.entry_reference_price,
                exit_reference_price=execution_price,
                entry_fill_classification=position.entry_fill_classification,
                exit_fill_classification="LIQUIDATION_MODEL",
                entry_slippage_cost=position.entry_slippage_cost,
                exit_slippage_cost=0.0,
                slippage_cost=position.entry_slippage_cost,
                gross_pnl=gross, fees=position.entry_fee,
                funding=position.funding_paid, liquidation_fee=liq_fee,
                net_pnl=net, exit_reason="liquidation",
                liquidation_trigger_price=trigger_price,
                liquidation_execution_price=execution_price,
            ))
        state.positions.clear()
        state.pending_orders.clear()
    def _check_liquidation_at_open(
        self, state: EngineState, trades: List[Trade], bar: Bar,
    ) -> bool:
        if not self.config.liquidation_enabled or not state.positions:
            return False
        mark_open = self._require_mark(bar.mark_open, "mark_open")
        if self._is_liquidatable(state, mark_open):
            self._close_liquidation_all(
                state, trades, bar.open_time,
                trigger_price=mark_open, execution_price=mark_open,
            )
            return True
        return False

    def _is_liquidatable(self, state: EngineState, mark_price: float) -> bool:
        if not state.positions:
            return False
        return self._account_equity(state, mark_price) <= self._maintenance_margin_total(
            state, mark_price
        )

    def _account_equity(self, state: EngineState, mark_price: float) -> float:
        return state.cash + sum(
            self._gross_pnl(position, mark_price)
            for position in state.positions.values()
        )

    def _maintenance_margin_total(
        self, state: EngineState, mark_price: float,
    ) -> float:
        return sum(
            self._maintenance_margin(position, mark_price)
            for position in state.positions.values()
        )

    def _maintenance_margin(self, position: Position, mark_price: float) -> float:
        notional = abs(position.qty * mark_price)
        tier = self._maintenance_tier(notional)
        return max(
            0.0,
            notional * tier.maintenance_margin_rate - tier.maintenance_amount,
        )

    def _maintenance_tier(self, notional: float) -> MaintenanceTier:
        for tier in self.config.maintenance_tiers:
            if tier.notional_cap is None or notional <= tier.notional_cap:
                return tier
        raise ValueError("no maintenance tier covers position notional")
    def _find_liquidation_trigger(
        self, state: EngineState, mark_open: float, endpoint: float,
    ) -> float:
        if self._is_liquidatable(state, mark_open):
            return mark_open
        if not self._is_liquidatable(state, endpoint):
            raise ValueError("liquidation endpoint must be unsafe")

        safe = mark_open
        unsafe = endpoint
        for _ in range(64):
            mid = (safe + unsafe) / 2.0
            if self._is_liquidatable(state, mid):
                unsafe = mid
            else:
                safe = mid
        return (safe + unsafe) / 2.0

    def _apply_funding(self, state: EngineState, bar: Bar) -> None:
        rate = self.config.funding_rate_by_time.get(bar.open_time)
        if rate is None or not state.positions:
            return
        if self.config.funding_price_source == "provided":
            if bar.open_time not in self.config.funding_price_by_time:
                raise ValueError(f"missing funding price at {bar.open_time}")
            funding_price = self.config.funding_price_by_time[bar.open_time]
        else:
            funding_price = bar.open
        if not isfinite(funding_price) or funding_price <= 0:
            raise ValueError("funding price must be finite and positive")

        for position in state.positions.values():
            signed_cost = position.qty * funding_price * rate
            if position.side == "short":
                signed_cost = -signed_cost
            state.cash -= signed_cost
            position.funding_paid += signed_cost
    def _strategy_state(self, state: EngineState, equity: float) -> StrategyState:
        def snap(side: Side) -> Optional[PositionSnapshot]:
            p = state.positions.get(side)
            if p is None:
                return None
            return PositionSnapshot(
                side=p.side, qty=p.qty,
                entry_bar_time=p.entry_bar_time,
                entry_time_exact=p.entry_time_exact,
                fill_time_resolution=p.fill_time_resolution,
                entry_price=p.entry_price, stop_loss=p.stop_loss,
                entry_reference_price=p.entry_reference_price,
                entry_fill_classification=p.entry_fill_classification,
                entry_slippage_cost=p.entry_slippage_cost,
                take_profit=p.take_profit, max_hold_bars=p.max_hold_bars,
            )

        return StrategyState(
            cash=state.cash, equity=equity,
            long_position=snap("long"), short_position=snap("short"),
            pending_long="long" in state.pending_orders,
            pending_short="short" in state.pending_orders,
        )

    def _accept_strategy_intents(
        self, state: EngineState, intents: List[OrderIntent], bar_time: int,
    ) -> None:
        if len(intents) > 2:
            raise ValueError("hedge-mode contract permits at most one intent per side per bar")
        sides = [intent.side for intent in intents]
        if any(side not in self.SIDES for side in sides):
            raise ValueError("every hedge-mode intent requires explicit long/short side")
        if len(set(sides)) != len(sides):
            raise ValueError("at most one intent per side per bar")

        for intent in intents:
            side = intent.side
            assert side in self.SIDES
            if intent.action == "cancel":
                pending = state.pending_orders.get(side)
                if pending is None or pending.intent.action != "enter":
                    raise ValueError(f"cancel requires pending {side} entry")
                del state.pending_orders[side]
                continue

            if intent.action == "enter":
                self._validate_order(intent)
                if side in state.positions:
                    raise ValueError(f"{side} entry while same-side position is open")
                if side in state.pending_orders:
                    raise ValueError(f"{side} entry while same-side order is pending")
                state.pending_orders[side] = PendingOrder(
                    intent=intent, submitted_bar_time=bar_time,
                )
                continue

            if intent.action == "exit":
                if side not in state.positions:
                    raise ValueError(f"{side} exit while that side is flat")
                if side in state.pending_orders:
                    raise ValueError(f"{side} exit conflicts with pending same-side order")
                state.pending_orders[side] = PendingOrder(
                    intent=intent, submitted_bar_time=bar_time,
                )
                continue
            raise ValueError(f"unsupported intent action: {intent.action}")
    def _equity_at_close(self, state: EngineState, bar: Bar) -> float:
        return self._account_equity(state, self._mark_close(bar))

    def _mark_close(self, bar: Bar) -> float:
        if self.config.liquidation_enabled:
            return self._require_mark(bar.mark_close, "mark_close")
        return bar.mark_close if bar.mark_close is not None else bar.close

    def _mark_open_or_trade_open(self, bar: Bar) -> float:
        return bar.mark_open if bar.mark_open is not None else bar.open

    @staticmethod
    def _require_mark(value: Optional[float], field_name: str) -> float:
        if value is None or not isfinite(value) or value <= 0:
            raise ValueError(f"{field_name} is required, finite, and positive")
        return value

    def _apply_slippage(self, price: float, side: Side, is_entry: bool) -> float:
        rate = self.config.slippage_rate
        if side == "long":
            return price * (1 + rate) if is_entry else price * (1 - rate)
        return price * (1 - rate) if is_entry else price * (1 + rate)

    @staticmethod
    def _slippage_cost(
        side: Side, qty: float, reference_price: float, actual_price: float,
        is_entry: bool,
    ) -> float:
        if side == "long":
            adverse_delta = actual_price - reference_price if is_entry else reference_price - actual_price
        else:
            adverse_delta = reference_price - actual_price if is_entry else actual_price - reference_price
        return adverse_delta * qty

    @staticmethod
    def _gross_pnl(position: Position, exit_price: Optional[float]) -> float:
        if exit_price is None:
            raise ValueError("exit price is required for PnL")
        if position.side == "long":
            return (exit_price - position.entry_price) * position.qty
        return (position.entry_price - exit_price) * position.qty

    @staticmethod
    def _time_exit_due(position: Position, bar_index: int) -> bool:
        if position.max_hold_bars is None:
            return False
        return (bar_index - position.entry_bar_index) >= position.max_hold_bars
    def _validate_config(self) -> None:
        c = self.config
        allowed_values = (
            ("intrabar_policy", c.intrabar_policy,
             {"worst_case"}),
            ("limit_fill_policy", c.limit_fill_policy,
             {"touch", "strict_through"}),
            ("end_of_data_policy", c.end_of_data_policy,
             {"mark_to_market", "force_close"}),
            ("funding_price_source", c.funding_price_source,
             {"provided", "bar_open"}),
            ("margin_mode", c.margin_mode, {"cross"}),
            ("liquidation_execution_model", c.liquidation_execution_model,
             {"mark_trigger_approximation"}),
        )
        for name, value, allowed in allowed_values:
            if value not in allowed:
                raise ValueError(f"unsupported {name}: {value}")
        if not isfinite(c.initial_cash) or c.initial_cash <= 0:
            raise ValueError("initial_cash must be finite and positive")
        for name, value in (
            ("maker_fee_rate", c.maker_fee_rate),
            ("taker_fee_rate", c.taker_fee_rate),
            ("slippage_rate", c.slippage_rate),
            ("liquidation_fee_rate", c.liquidation_fee_rate),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not isfinite(c.leverage) or c.leverage < 1:
            raise ValueError("leverage must be finite and >= 1")
        for name, mapping in (
            ("funding_rate_by_time", c.funding_rate_by_time),
            ("funding_price_by_time", c.funding_price_by_time),
        ):
            for timestamp, value in mapping.items():
                if not isinstance(timestamp, int) or not isfinite(value):
                    raise ValueError(f"{name} requires integer timestamps and finite values")
                if name == "funding_price_by_time" and value <= 0:
                    raise ValueError("funding prices must be positive")
        if c.liquidation_enabled and not c.maintenance_tiers:
            raise ValueError("liquidation requires maintenance tiers")
        previous_cap = 0.0
        for index, tier in enumerate(c.maintenance_tiers):
            if (
                not isfinite(tier.maintenance_margin_rate)
                or not isfinite(tier.maintenance_amount)
                or tier.maintenance_margin_rate < 0
                or tier.maintenance_amount < 0
            ):
                raise ValueError("maintenance tier values must be finite and non-negative")
            if tier.notional_cap is None and index != len(c.maintenance_tiers) - 1:
                raise ValueError("uncapped maintenance tier must be last")
            if tier.notional_cap is not None:
                if not isfinite(tier.notional_cap) or tier.notional_cap <= previous_cap:
                    raise ValueError("maintenance tier caps must increase")
                previous_cap = tier.notional_cap
        if (
            c.liquidation_enabled
            and c.maintenance_tiers
            and c.maintenance_tiers[-1].notional_cap is not None
        ):
            raise ValueError("liquidation tiers require a final uncapped tier")

    def _qa_status(self) -> Tuple[str, Tuple[str, ...]]:
        issues: List[str] = []
        if self.config.leverage > 1 and not self.config.liquidation_enabled:
            issues.append("LEVERAGED_RUN_WITHOUT_LIQUIDATION_MODEL")
        if self.config.liquidation_enabled:
            if not self.config.mark_price_data_verified:
                issues.append("MISSING_VERIFIED_HISTORICAL_MARK_PRICE")
            if not self.config.maintenance_tiers_verified:
                issues.append("MISSING_VERIFIED_HISTORICAL_MAINTENANCE_TIERS")
            if not self.config.liquidation_execution_verified:
                issues.append("NOT_VERIFIED_LIQUIDATION_EXECUTION_MODEL")
        if self.config.funding_rate_by_time and not self.config.funding_data_verified:
            issues.append("MISSING_VERIFIED_HISTORICAL_FUNDING_DATA")
        return ("VERIFIED" if not issues else "NOT VERIFIED", tuple(issues))
    @staticmethod
    def _validate_bar(bar: Bar, last_time: Optional[int]) -> None:
        if last_time is not None and bar.open_time <= last_time:
            raise ValueError("bar timestamps must be strictly increasing")
        values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
        if not all(isfinite(v) for v in values):
            raise ValueError("bar contains non-finite values")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if bar.volume < 0:
            raise ValueError("volume must be non-negative")
        if bar.high < max(bar.open, bar.close, bar.low):
            raise ValueError("invalid high")
        if bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError("invalid low")

        marks = (bar.mark_open, bar.mark_high, bar.mark_low, bar.mark_close)
        present = [m is not None for m in marks]
        if any(present) and not all(present):
            raise ValueError("mark OHLC must be supplied as a complete set")
        if all(present):
            mark_open, mark_high, mark_low, mark_close = marks
            assert mark_open is not None and mark_high is not None
            assert mark_low is not None and mark_close is not None
            if not all(isfinite(v) and v > 0 for v in marks if v is not None):
                raise ValueError("mark OHLC must be finite and positive")
            if mark_high < max(mark_open, mark_close, mark_low):
                raise ValueError("invalid mark high")
            if mark_low > min(mark_open, mark_close, mark_high):
                raise ValueError("invalid mark low")
    @staticmethod
    def _validate_order(order: OrderIntent) -> None:
        if order.action != "enter":
            return
        if order.side not in ("long", "short"):
            raise ValueError("entry side must be long or short")
        if not isfinite(order.qty) or order.qty <= 0:
            raise ValueError("qty must be finite and positive")
        if order.order_type == "limit":
            if order.limit_price is None or not isfinite(order.limit_price) or order.limit_price <= 0:
                raise ValueError("limit order requires positive finite limit_price")
            if order.time_in_force not in ("GTC", "IOC"):
                raise ValueError("limit order requires GTC or IOC time_in_force")
        elif order.order_type == "market":
            if order.time_in_force is not None:
                raise ValueError("market order must not specify time_in_force")
        else:
            raise ValueError("unsupported order type")
        for name, value in (("stop_loss", order.stop_loss), ("take_profit", order.take_profit)):
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        if order.max_hold_bars is not None and order.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive")

    @staticmethod
    def _validate_protective_levels(order: OrderIntent, fill_price: float) -> None:
        if order.side == "long":
            if order.stop_loss is not None and order.stop_loss >= fill_price:
                raise ValueError("long stop_loss must be below actual fill price")
            if order.take_profit is not None and order.take_profit <= fill_price:
                raise ValueError("long take_profit must be above actual fill price")
        else:
            if order.stop_loss is not None and order.stop_loss <= fill_price:
                raise ValueError("short stop_loss must be above actual fill price")
            if order.take_profit is not None and order.take_profit >= fill_price:
                raise ValueError("short take_profit must be below actual fill price")
