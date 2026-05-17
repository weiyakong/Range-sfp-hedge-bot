"""
Freqtrade port of `tradingview/sfp_candidate_debug.pine` with split timeframes:

- 15m finds and persists SFP candidate levels (Entry High / Entry Low).
- 1m checks sweep -> reclaim / rejection and triggers the entry immediately.
- Hedge mode is allowed: one long and one short may coexist on the same pair, but duplicate
  same-side trades are blocked by `confirm_trade_entry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, BooleanParameter, IntParameter, DecimalParameter
from pandas import DataFrame


@dataclass
class TradePlan:
    side: str
    entry: float
    stop: float
    tp0: float
    tp1: float
    tp2: float
    tp3: float
    tp4: float
    risk: float
    protected_stop: float


class SFPCandidateDebugStrategy(IStrategy):
    """
    15m level finder + 1m SFP trigger strategy.

    Candidate architecture:
    - The strategy timeframe is 1m so entries can react as soon as a 1m candle sweeps and reclaims.
    - The only level-source timeframe is 15m. Confirmed 15m pivots become raw swings, then active
      candidate levels after the Pine-style `min_move_usd` move away from the swing.
    - Active 15m Candidate High / Candidate Low levels persist until clean break or trade trigger.

    Entry rules:
    - Short: active 15m Entry High exists, 1m high sweeps it by at least `sweep_usd`, then the same
      1m candle closes back below the level. Entry price is the level, SL is sweep wick high + buffer.
    - Long: active 15m Entry Low exists, 1m low sweeps it by at least `sweep_usd`, then the same
      1m candle closes back above the level. Entry price is the level, SL is sweep wick low - buffer.

    Hedge rules:
    - `can_short = True`, futures/isolated must be configured in config, and `max_open_trades` can be 2.
    - `confirm_trade_entry` blocks duplicate same-side trades per pair: max one long and max one short.
      A long and a short on the same pair may coexist if the exchange/account hedge mode allows it.
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    informative_timeframe = "15m"
    can_short = True
    startup_candle_count = 1500
    process_only_new_candles = True
    use_custom_stoploss = True
    position_adjustment_enable = True

    minimal_roi = {"0": 1000}
    stoploss = -0.99

    # 15m candidate engine parameters mirroring sfp_candidate_debug.pine defaults where possible.
    pivot_len_15m = IntParameter(2, 40, default=5, space="buy", optimize=False)
    min_move_usd = DecimalParameter(0.0, 3000.0, default=700.0, decimals=1, space="buy", optimize=False)
    merge_usd = DecimalParameter(0.0, 500.0, default=120.0, decimals=1, space="buy", optimize=False)
    clean_break_usd = DecimalParameter(0.0, 500.0, default=120.0, decimals=1, space="buy", optimize=False)
    max_raw_swings = IntParameter(20, 400, default=160, space="buy", optimize=False)
    max_candidates = IntParameter(20, 300, default=120, space="buy", optimize=False)

    use_impulse_filter = BooleanParameter(default=True, space="buy", optimize=False)
    impulse_atr_len = IntParameter(1, 100, default=14, space="buy", optimize=False)
    impulse_body_atr = DecimalParameter(0.1, 5.0, default=1.2, decimals=1, space="buy", optimize=False)
    impulse_close_portion = DecimalParameter(0.05, 0.45, default=0.25, decimals=2, space="buy", optimize=False)
    impulse_bars_hold = IntParameter(1, 50, default=6, space="buy", optimize=False)
    exhaustion_wick_portion = DecimalParameter(0.1, 0.8, default=0.45, decimals=2, space="buy", optimize=False)

    # 1m trigger and trade-management rules.
    sweep_usd = DecimalParameter(0.0, 300.0, default=50.0, decimals=1, space="buy", optimize=False)
    stop_buffer_usd = DecimalParameter(0.0, 300.0, default=50.0, decimals=1, space="sell", optimize=False)
    tp0_r = DecimalParameter(0.5, 5.0, default=2.0, decimals=1, space="sell", optimize=False)
    tp1_r = DecimalParameter(1.0, 6.0, default=2.5, decimals=1, space="sell", optimize=False)
    tp2_r = DecimalParameter(1.0, 8.0, default=3.0, decimals=1, space="sell", optimize=False)
    tp3_r = DecimalParameter(1.0, 10.0, default=3.5, decimals=1, space="sell", optimize=False)
    tp4_r = DecimalParameter(1.0, 12.0, default=4.0, decimals=1, space="sell", optimize=False)
    protected_stop_offset_usd = DecimalParameter(0.0, 500.0, default=150.0, decimals=1, space="sell", optimize=False)

    trade_budget_usd = DecimalParameter(10.0, 100000.0, default=1000.0, decimals=1, space="buy", optimize=False)
    max_capital_risk = DecimalParameter(0.001, 0.10, default=0.01, decimals=3, space="buy", optimize=False)

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "force_entry": "limit",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._trade_plans: dict[int, TradePlan] = {}

    def informative_pairs(self) -> list[tuple[str, str]]:
        return [(pair, self.informative_timeframe) for pair in self.dp.current_whitelist()]

    @staticmethod
    def _pivot_high(high: pd.Series, left_right: int) -> pd.Series:
        """Confirmed pivot high equivalent to Pine ta.pivothigh on the 15m source series."""
        window = left_right * 2 + 1
        roll_max = high.rolling(window=window, center=True).max()
        return high.where(high == roll_max).shift(left_right)

    @staticmethod
    def _pivot_low(low: pd.Series, left_right: int) -> pd.Series:
        """Confirmed pivot low equivalent to Pine ta.pivotlow on the 15m source series."""
        window = left_right * 2 + 1
        roll_min = low.rolling(window=window, center=True).min()
        return low.where(low == roll_min).shift(left_right)

    @staticmethod
    def _trim_old(items: list[dict[str, Any]], max_items: int) -> None:
        while len(items) > max_items:
            items.pop(0)

    @staticmethod
    def _atr(dataframe: DataFrame, length: int) -> pd.Series:
        prev_close = dataframe["close"].shift(1)
        true_range = pd.concat(
            [
                dataframe["high"] - dataframe["low"],
                (dataframe["high"] - prev_close).abs(),
                (dataframe["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.rolling(length).mean()

    def _build_15m_source(self, df: DataFrame) -> DataFrame:
        """Build the sole candidate timeframe: 15m OHLC plus confirmed 15m raw pivots."""
        pivot = int(self.pivot_len_15m.value)
        source_15m = (
            df.set_index("date")
            .resample("15min", label="right", closed="left")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )
        source_15m["raw_high_15m"] = self._pivot_high(source_15m["high"], pivot)
        source_15m["raw_low_15m"] = self._pivot_low(source_15m["low"], pivot)

        atr = self._atr(source_15m, int(self.impulse_atr_len.value))
        bar_range = source_15m["high"] - source_15m["low"]
        body = (source_15m["close"] - source_15m["open"]).abs()
        lower_wick = source_15m[["open", "close"]].min(axis=1) - source_15m["low"]
        upper_wick = source_15m["high"] - source_15m[["open", "close"]].max(axis=1)
        close_portion = float(self.impulse_close_portion.value)
        body_atr = float(self.impulse_body_atr.value)
        wick_portion = float(self.exhaustion_wick_portion.value)

        source_15m["bear_impulse_15m"] = (
            bool(self.use_impulse_filter.value)
            & (source_15m["close"] < source_15m["open"])
            & (body >= atr * body_atr)
            & (bar_range > 0)
            & ((source_15m["close"] - source_15m["low"]) <= bar_range * close_portion)
        )
        source_15m["bull_impulse_15m"] = (
            bool(self.use_impulse_filter.value)
            & (source_15m["close"] > source_15m["open"])
            & (body >= atr * body_atr)
            & (bar_range > 0)
            & ((source_15m["high"] - source_15m["close"]) <= bar_range * close_portion)
        )
        source_15m["bear_exhaustion_15m"] = (
            (bar_range > 0)
            & (lower_wick >= bar_range * wick_portion)
            & (source_15m["close"] > source_15m["low"] + bar_range * 0.45)
        )
        source_15m["bull_exhaustion_15m"] = (
            (bar_range > 0)
            & (upper_wick >= bar_range * wick_portion)
            & (source_15m["close"] < source_15m["high"] - bar_range * 0.45)
        )
        return source_15m.reset_index()

    @staticmethod
    def _merge_15m_levels(df: DataFrame, source_15m: DataFrame) -> DataFrame:
        """Expose newly confirmed 15m levels to the 1m execution stream at their 15m timestamp."""
        columns = [
            "date",
            "raw_high_15m",
            "raw_low_15m",
            "bear_impulse_15m",
            "bull_impulse_15m",
            "bear_exhaustion_15m",
            "bull_exhaustion_15m",
        ]
        return df.merge(source_15m[columns], on="date", how="left")

    def _simulate_candidate_engine(self, dataframe: DataFrame) -> DataFrame:
        """15m candidate engine + 1m sweep/reclaim trigger loop."""
        df = dataframe.copy()
        source_15m = self._build_15m_source(df)
        df = self._merge_15m_levels(df, source_15m)

        min_move = float(self.min_move_usd.value)
        merge = float(self.merge_usd.value)
        clean_break = float(self.clean_break_usd.value)
        sweep = float(self.sweep_usd.value)
        stop_buffer = float(self.stop_buffer_usd.value)
        tp0_r = float(self.tp0_r.value)
        tp1_r = float(self.tp1_r.value)
        tp2_r = float(self.tp2_r.value)
        tp3_r = float(self.tp3_r.value)
        tp4_r = float(self.tp4_r.value)
        protected_offset = float(self.protected_stop_offset_usd.value)
        max_raw = int(self.max_raw_swings.value)
        max_candidates = int(self.max_candidates.value)

        raw_levels: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        impulse_mode = 0
        impulse_started_pos: Optional[int] = None

        columns = [
            "entry_high_15m", "entry_low_15m", "entry_price", "entry_stop", "entry_risk",
            "tp0_price", "tp1_price", "tp2_price", "tp3_price", "tp4_price", "protected_stop",
            "sfp_short", "sfp_long", "active_entry_high_count", "active_entry_low_count", "last_entry_level",
        ]
        for col in columns:
            df[col] = float("nan")
        df["sfp_short"] = 0
        df["sfp_long"] = 0
        df["active_entry_high_count"] = 0
        df["active_entry_low_count"] = 0

        for pos, row in enumerate(df.itertuples()):
            high_1m = float(row.high)
            low_1m = float(row.low)
            close_1m = float(row.close)

            if not pd.isna(getattr(row, "bear_impulse_15m")) and bool(getattr(row, "bear_impulse_15m")):
                impulse_mode = -1
                impulse_started_pos = pos
            elif not pd.isna(getattr(row, "bull_impulse_15m")) and bool(getattr(row, "bull_impulse_15m")):
                impulse_mode = 1
                impulse_started_pos = pos
            elif (
                impulse_mode == -1
                and impulse_started_pos is not None
                and pos - impulse_started_pos >= int(self.impulse_bars_hold.value) * 15
                and not pd.isna(getattr(row, "bear_exhaustion_15m"))
                and bool(getattr(row, "bear_exhaustion_15m"))
            ):
                impulse_mode = 0
                impulse_started_pos = None
            elif (
                impulse_mode == 1
                and impulse_started_pos is not None
                and pos - impulse_started_pos >= int(self.impulse_bars_hold.value) * 15
                and not pd.isna(getattr(row, "bull_exhaustion_15m"))
                and bool(getattr(row, "bull_exhaustion_15m"))
            ):
                impulse_mode = 0
                impulse_started_pos = None

            def counter_trend_blocked(is_high: bool) -> bool:
                # Same rule as SFP Candidate Debug: bearish impulse blocks lows; bullish impulse blocks highs.
                return (impulse_mode == -1 and not is_high) or (impulse_mode == 1 and is_high)

            raw_high_15m = getattr(row, "raw_high_15m")
            raw_low_15m = getattr(row, "raw_low_15m")
            if not pd.isna(raw_high_15m) and not counter_trend_blocked(True):
                raw_levels.append({"price": float(raw_high_15m), "is_high": True, "active": True})
                self._trim_old(raw_levels, max_raw)
            if not pd.isna(raw_low_15m) and not counter_trend_blocked(False):
                raw_levels.append({"price": float(raw_low_15m), "is_high": False, "active": True})
                self._trim_old(raw_levels, max_raw)

            # Promote 15m raw swings into persistent Entry levels only after the required move away.
            for raw in raw_levels:
                if not raw["active"]:
                    continue
                price = float(raw["price"])
                is_high = bool(raw["is_high"])
                move_size = price - low_1m if is_high else high_1m - price
                if move_size < min_move or counter_trend_blocked(is_high):
                    continue

                duplicate = any(
                    c["active"] and c["is_high"] == is_high and abs(float(c["price"]) - price) <= merge
                    for c in candidates
                )
                raw["active"] = False
                if duplicate:
                    continue
                candidates.append({"price": price, "is_high": is_high, "active": True})
                self._trim_old(candidates, max_candidates)

            active_highs = [c for c in candidates if c["active"] and c["is_high"]]
            active_lows = [c for c in candidates if c["active"] and not c["is_high"]]
            df.iat[pos, df.columns.get_loc("active_entry_high_count")] = len(active_highs)
            df.iat[pos, df.columns.get_loc("active_entry_low_count")] = len(active_lows)

            # 1m execution layer: sweep a stored 15m level, reclaim in the same 1m candle, enter at level.
            short_matches = [
                c for c in active_highs
                if high_1m >= float(c["price"]) + sweep and close_1m < float(c["price"])
            ]
            long_matches = [
                c for c in active_lows
                if low_1m <= float(c["price"]) - sweep and close_1m > float(c["price"])
            ]

            if short_matches:
                level = min(short_matches, key=lambda c: high_1m - float(c["price"]))
                entry = float(level["price"])
                stop = high_1m + stop_buffer
                risk = stop - entry
                if risk > 0:
                    self._write_signal_row(df, pos, True, entry, stop, risk, tp0_r, tp1_r, tp2_r, tp3_r, tp4_r, protected_offset)
                    level["active"] = False

            if long_matches:
                level = min(long_matches, key=lambda c: float(c["price"]) - low_1m)
                entry = float(level["price"])
                stop = low_1m - stop_buffer
                risk = entry - stop
                if risk > 0:
                    self._write_signal_row(df, pos, False, entry, stop, risk, tp0_r, tp1_r, tp2_r, tp3_r, tp4_r, protected_offset)
                    level["active"] = False

            for candidate in candidates:
                if not candidate["active"]:
                    continue
                price = float(candidate["price"])
                is_high = bool(candidate["is_high"])
                if (is_high and close_1m > price + clean_break) or (not is_high and close_1m < price - clean_break):
                    candidate["active"] = False

        return df

    @staticmethod
    def _write_signal_row(
        df: DataFrame,
        pos: int,
        is_short: bool,
        entry: float,
        stop: float,
        risk: float,
        tp0_r: float,
        tp1_r: float,
        tp2_r: float,
        tp3_r: float,
        tp4_r: float,
        protected_offset: float,
    ) -> None:
        direction = -1.0 if is_short else 1.0
        tp0 = entry + direction * risk * tp0_r
        tp1 = entry + direction * risk * tp1_r
        tp2 = entry + direction * risk * tp2_r
        tp3 = entry + direction * risk * tp3_r
        tp4 = entry + direction * risk * tp4_r
        protected_stop = tp0 + direction * protected_offset

        df.iat[pos, df.columns.get_loc("sfp_short" if is_short else "sfp_long")] = 1
        df.iat[pos, df.columns.get_loc("entry_high_15m" if is_short else "entry_low_15m")] = entry
        df.iat[pos, df.columns.get_loc("entry_price")] = entry
        df.iat[pos, df.columns.get_loc("entry_stop")] = stop
        df.iat[pos, df.columns.get_loc("entry_risk")] = risk
        df.iat[pos, df.columns.get_loc("tp0_price")] = tp0
        df.iat[pos, df.columns.get_loc("tp1_price")] = tp1
        df.iat[pos, df.columns.get_loc("tp2_price")] = tp2
        df.iat[pos, df.columns.get_loc("tp3_price")] = tp3
        df.iat[pos, df.columns.get_loc("tp4_price")] = tp4
        df.iat[pos, df.columns.get_loc("protected_stop")] = protected_stop
        df.iat[pos, df.columns.get_loc("last_entry_level")] = entry

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        return self._simulate_candidate_engine(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = None

        dataframe.loc[dataframe["sfp_long"] == 1, ["enter_long", "enter_tag"]] = (1, "sfp_1m_reclaim_15m_entry_low")
        dataframe.loc[dataframe["sfp_short"] == 1, ["enter_short", "enter_tag"]] = (1, "sfp_1m_reclaim_15m_entry_high")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def _plan_from_signal_row(self, row: pd.Series, side: str) -> Optional[TradePlan]:
        values = {
            "entry": row.get("entry_price"),
            "stop": row.get("entry_stop"),
            "tp0": row.get("tp0_price"),
            "tp1": row.get("tp1_price"),
            "tp2": row.get("tp2_price"),
            "tp3": row.get("tp3_price"),
            "tp4": row.get("tp4_price"),
            "risk": row.get("entry_risk"),
            "protected": row.get("protected_stop"),
        }
        if any(pd.isna(x) for x in values.values()):
            return None
        return TradePlan(
            side=side,
            entry=float(values["entry"]),
            stop=float(values["stop"]),
            tp0=float(values["tp0"]),
            tp1=float(values["tp1"]),
            tp2=float(values["tp2"]),
            tp3=float(values["tp3"]),
            tp4=float(values["tp4"]),
            risk=float(values["risk"]),
            protected_stop=float(values["protected"]),
        )

    def _latest_signal_plan(self, pair: str, side: str) -> Optional[TradePlan]:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        if dataframe.empty:
            return None
        signal_col = "sfp_short" if side == "short" else "sfp_long"
        signals = dataframe[dataframe[signal_col] == 1]
        if signals.empty:
            return None
        return self._plan_from_signal_row(signals.iloc[-1], side)

    def _trade_plan(self, trade: Trade) -> Optional[TradePlan]:
        trade_id = int(trade.id or 0)
        if trade_id in self._trade_plans:
            return self._trade_plans[trade_id]

        side = "short" if trade.is_short else "long"
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=trade.pair, timeframe=self.timeframe)
        if dataframe.empty:
            return None

        signal_col = "sfp_short" if trade.is_short else "sfp_long"
        signals = dataframe[(dataframe[signal_col] == 1) & (dataframe["date"] <= trade.open_date_utc)]
        if signals.empty:
            signals = dataframe[dataframe[signal_col] == 1]
        if signals.empty:
            return None

        plan = self._plan_from_signal_row(signals.iloc[-1], side)
        if plan is not None and trade_id:
            self._trade_plans[trade_id] = plan
        return plan

    @staticmethod
    def _has_open_trade_on_side(pair: str, side: str) -> bool:
        """Block duplicate same-side trades while allowing opposite-side hedge trades."""
        side_is_short = side == "short"
        for open_trade in Trade.get_open_trades():
            if open_trade.pair == pair and bool(open_trade.is_short) == side_is_short:
                return True
        return False

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs: Any,
    ) -> bool:
        return not self._has_open_trade_on_side(pair, side)

    def custom_entry_price(
        self,
        pair: str,
        trade: Optional[Trade],
        current_time: datetime,
        proposed_rate: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs: Any,
    ) -> float:
        plan = self._latest_signal_plan(pair, side)
        return plan.entry if plan is not None else proposed_rate

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs: Any,
    ) -> float:
        plan = self._latest_signal_plan(pair, side)
        if plan is None or plan.risk <= 0:
            return min(max(float(proposed_stake), float(min_stake or 0.0)), float(max_stake))

        budget = float(self.trade_budget_usd.value)
        risk_cash = budget * float(self.max_capital_risk.value)
        units = risk_cash / plan.risk
        stake = units * plan.entry / max(float(leverage), 1.0)
        stake = min(stake, budget, float(max_stake))
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        return stake

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs: Any,
    ) -> float:
        return min(1.0, max_leverage)

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> Optional[float]:
        plan = self._trade_plan(trade)
        if plan is None or trade.nr_of_successful_exits > 0:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=trade.pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1] if not dataframe.empty else None
        if candle is not None:
            tp0_hit = bool(candle["low"] <= plan.tp0) if trade.is_short else bool(candle["high"] >= plan.tp0)
        else:
            tp0_hit = current_rate <= plan.tp0 if trade.is_short else current_rate >= plan.tp0

        if tp0_hit:
            return -(trade.stake_amount * 0.5)
        return None

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> Optional[str]:
        plan = self._trade_plan(trade)
        if plan is None:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1] if not dataframe.empty else None
        high = float(candle["high"]) if candle is not None else current_rate
        low = float(candle["low"]) if candle is not None else current_rate

        tp0_done = trade.nr_of_successful_exits > 0
        if trade.is_short:
            if low <= plan.tp4:
                return "tp4_full_exit"
            if tp0_done and high >= plan.protected_stop:
                return "safe_exit"
            if not tp0_done and high >= plan.stop:
                return "sl_exit"
        else:
            if high >= plan.tp4:
                return "tp4_full_exit"
            if tp0_done and low <= plan.protected_stop:
                return "safe_exit"
            if not tp0_done and low <= plan.stop:
                return "sl_exit"
        return None

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool = False,
        **kwargs: Any,
    ) -> float:
        """Emergency exchange-style stop; custom_exit provides the semantic exit tags."""
        plan = self._trade_plan(trade)
        if plan is None:
            return self.stoploss

        stop_price = plan.protected_stop if trade.nr_of_successful_exits > 0 else plan.stop
        if trade.is_short:
            distance = (stop_price - current_rate) / current_rate
        else:
            distance = (current_rate - stop_price) / current_rate
        return max(0.001, min(abs(distance), 0.99))
