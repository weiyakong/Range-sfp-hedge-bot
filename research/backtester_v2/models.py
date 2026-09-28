from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

Side = Literal["long", "short"]
OrderType = Literal["market", "limit"]
TimeInForce = Literal["GTC", "IOC"]
IntrabarPolicy = Literal["worst_case"]
LimitFillPolicy = Literal["touch", "strict_through"]
EndOfDataPolicy = Literal["mark_to_market", "force_close"]
FundingPriceSource = Literal["provided", "bar_open"]
MarginMode = Literal["cross"]
FillTimeResolution = Literal["exact", "bar"]
LiquidationExecutionModel = Literal["mark_trigger_approximation"]
SourceType = Literal["external_replication", "external_adaptation", "internal"]


@dataclass(frozen=True)
class Bar:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    mark_open: Optional[float] = None
    mark_high: Optional[float] = None
    mark_low: Optional[float] = None
    mark_close: Optional[float] = None


@dataclass(frozen=True)
class MaintenanceTier:
    notional_cap: Optional[float]
    maintenance_margin_rate: float
    maintenance_amount: float = 0.0


@dataclass(frozen=True)
class OrderIntent:
    action: Literal["enter", "exit", "cancel"]
    side: Optional[Side] = None
    order_type: OrderType = "market"
    qty: float = 0.0
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_hold_bars: Optional[int] = None
    time_in_force: Optional[TimeInForce] = None

    @classmethod
    def market(cls, side: Side, qty: float,
               stop_loss: Optional[float] = None,
               take_profit: Optional[float] = None,
               max_hold_bars: Optional[int] = None) -> "OrderIntent":
        return cls("enter", side=side, order_type="market", qty=qty,
                   stop_loss=stop_loss, take_profit=take_profit,
                   max_hold_bars=max_hold_bars)

    @classmethod
    def limit(cls, side: Side, qty: float, limit_price: float,
              time_in_force: TimeInForce,
              stop_loss: Optional[float] = None,
              take_profit: Optional[float] = None,
              max_hold_bars: Optional[int] = None) -> "OrderIntent":
        return cls("enter", side=side, order_type="limit", qty=qty,
                   limit_price=limit_price, stop_loss=stop_loss,
                   take_profit=take_profit, max_hold_bars=max_hold_bars,
                   time_in_force=time_in_force)

    @classmethod
    def exit_market(cls, side: Side) -> "OrderIntent":
        return cls("exit", side=side, order_type="market")

    @classmethod
    def cancel_pending(cls, side: Side) -> "OrderIntent":
        return cls("cancel", side=side)


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000.0
    maker_fee_rate: float = 0.0
    taker_fee_rate: float = 0.0
    slippage_rate: float = 0.0
    intrabar_policy: IntrabarPolicy = "worst_case"
    limit_fill_policy: LimitFillPolicy = "strict_through"
    end_of_data_policy: EndOfDataPolicy = "mark_to_market"
    funding_price_source: FundingPriceSource = "provided"
    funding_rate_by_time: Dict[int, float] = field(default_factory=dict)
    funding_price_by_time: Dict[int, float] = field(default_factory=dict)
    margin_mode: MarginMode = "cross"
    leverage: float = 1.0
    liquidation_enabled: bool = False
    liquidation_fee_rate: float = 0.0
    maintenance_tiers: Tuple[MaintenanceTier, ...] = field(default_factory=tuple)
    liquidation_execution_model: LiquidationExecutionModel = "mark_trigger_approximation"
    mark_price_data_verified: bool = False
    funding_data_verified: bool = False
    maintenance_tiers_verified: bool = False
    liquidation_execution_verified: bool = False


@dataclass
class Position:
    side: Side
    qty: float
    entry_bar_time: int
    entry_time_exact: Optional[int]
    fill_time_resolution: FillTimeResolution
    entry_price: float
    entry_bar_index: int
    stop_loss: Optional[float]
    take_profit: Optional[float]
    max_hold_bars: Optional[int]
    entry_fee: float
    funding_paid: float = 0.0

    @property
    def entry_time(self) -> Optional[int]:
        return self.entry_time_exact

@dataclass(frozen=True)
class PositionSnapshot:
    side: Side
    qty: float
    entry_bar_time: int
    entry_time_exact: Optional[int]
    fill_time_resolution: FillTimeResolution
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    max_hold_bars: Optional[int]

    @property
    def entry_time(self) -> Optional[int]:
        return self.entry_time_exact


@dataclass(frozen=True)
class PendingOrder:
    intent: OrderIntent
    submitted_bar_time: int
    submission_time_exact: Optional[int] = None
    time_resolution: FillTimeResolution = "bar"


@dataclass(frozen=True)
class RejectedOrder:
    bar_time: int
    side: Side
    reason: str
    order_type: OrderType
    qty: float
    limit_price: Optional[float]
    attempted_fill_price: Optional[float]
    event_type: str = "ORDER_REJECTED"


@dataclass(frozen=True)
class IntrabarAmbiguity:
    bar_time: int
    open_legs_before: Tuple[Side, ...]
    competing_paths: str
    chosen_path: str
    resulting_trade_indices: Tuple[int, ...]
    resulting_legs: Tuple[Side, ...]
    competing_events: str = ""
    reason: str = "AMBIGUOUS_INTRABAR"


@dataclass(frozen=True)
class StrategyState:
    cash: float
    equity: float
    long_position: Optional[PositionSnapshot]
    short_position: Optional[PositionSnapshot]
    pending_long: bool
    pending_short: bool

    @property
    def position(self) -> Optional[PositionSnapshot]:
        open_legs = [p for p in (self.long_position, self.short_position) if p is not None]
        return open_legs[0] if len(open_legs) == 1 else None

    @property
    def has_pending_order(self) -> bool:
        return self.pending_long or self.pending_short


@dataclass(frozen=True)
class Trade:
    side: Side
    qty: float
    entry_bar_time: int
    entry_time_exact: Optional[int]
    fill_time_resolution: FillTimeResolution
    exit_time: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    fees: float
    funding: float
    liquidation_fee: float
    net_pnl: float
    exit_reason: str
    liquidation_trigger_price: Optional[float] = None
    liquidation_execution_price: Optional[float] = None

    @property
    def entry_time(self) -> Optional[int]:
        return self.entry_time_exact

@dataclass
class EngineState:
    cash: float
    positions: Dict[Side, Position] = field(default_factory=dict)
    pending_orders: Dict[Side, PendingOrder] = field(default_factory=dict)

    @property
    def position(self) -> Optional[Position]:
        open_legs = list(self.positions.values())
        return open_legs[0] if len(open_legs) == 1 else None


@dataclass(frozen=True)
class BacktestResult:
    final_cash: float
    final_equity: float
    trades: List[Trade]
    equity_curve: List[Tuple[int, float]]
    intrabar_equity_curve: List[Tuple[int, float]]
    open_positions: Dict[Side, Position]
    pending_orders: Dict[Side, PendingOrder]
    rejected_orders: List[RejectedOrder]
    intrabar_ambiguities: List[IntrabarAmbiguity]
    open_position_unrealized_pnl: float
    open_position_entry_fee: float
    open_position_funding: float
    qa_status: str
    qa_issues: Tuple[str, ...]

    @property
    def open_position(self) -> Optional[Position]:
        open_legs = list(self.open_positions.values())
        return open_legs[0] if len(open_legs) == 1 else None

    @property
    def open_long_position(self) -> Optional[Position]:
        return self.open_positions.get("long")

    @property
    def open_short_position(self) -> Optional[Position]:
        return self.open_positions.get("short")
