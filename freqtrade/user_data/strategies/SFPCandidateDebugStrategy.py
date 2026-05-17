"""
Freqtrade port of `tradingview/sfp_candidate_debug.pine` for realtime 1m SFP entries.

Core idea:
- Build persistent Entry High / Entry Low levels from confirmed swing candidates.
- A trade is triggered on 1m when price sweeps an already stored level by `sweep_usd`,
  then reclaims the level inside the same 1m candle.
- Entry is priced at the stored level, with initial SL behind the sweep extreme +/− `stop_buffer_usd`.
- Position size is risk-based: default budget is 1000 USDT and max risk is 1% of that budget.

This strategy intentionally keeps the level engine in a deterministic candle-by-candle loop because
Pine arrays in the source script are stateful and persistent.
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
    tp4: float
    risk: float
    protected_stop: float


class SFPCandidateDebugStrategy(IStrategy):
    """
    SFP Candidate Debug strategy port.

    Entry rules on 1m:
    - Short: an active Entry High already exists; current 1m high sweeps it by at least $50;
      current 1m close returns below the level; limit entry price is the Entry High.
    - Long: an active Entry Low already exists; current 1m low sweeps it by at least $50;
      current 1m close returns above the level; limit entry price is the Entry Low.

    Exit plan:
    - TP0 at 2R closes 50% via `adjust_trade_position`.
    - After TP0 is touched, protected stop becomes TP0 +/- $150 and a later hit is tagged SAFE EXIT.
    - Initial stop before TP0 is tagged SL / EXIT.
    - TP4 at 4R closes the rest.
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    can_short = True
    startup_candle_count = 500
    process_only_new_candles = True
    use_custom_stoploss = True
    position_adjustment_enable = True

    minimal_roi = {"0": 1000}
    stoploss = -0.99

    # Candidate engine parameters mirroring sfp_candidate_debug.pine defaults where possible.
    use_1m_swings = BooleanParameter(default=False, space="buy", optimize=False)
    use_5m_swings = BooleanParameter(default=True, space="buy", optimize=False)
    use_15m_swings = BooleanParameter(default=True, space="buy", optimize=False)
    use_1h_swings = BooleanParameter(default=True, space="buy", optimize=False)
    use_4h_swings = BooleanParameter(default=True, space="buy", optimize=False)
    pivot_len = IntParameter(2, 40, default=5, space="buy", optimize=False)
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

    # Trade rules requested by the user.
    sweep_usd = DecimalParameter(0.0, 300.0, default=50.0, decimals=1, space="buy", optimize=False)
    stop_buffer_usd = DecimalParameter(0.0, 300.0, default=50.0, decimals=1, space="sell", optimize=False)
    tp0_r = DecimalParameter(0.5, 5.0, default=2.0, decimals=1, space="sell", optimize=False)
    tp4_r = DecimalParameter(1.0, 10.0, default=4.0, decimals=1, space="sell", optimize=False)
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

    @staticmethod
    def _pivot_high(high: pd.Series, left_right: int) -> pd.Series:
        """Confirmed pivot high using past and future bars, equivalent to Pine ta.pivothigh."""
        window = left_right * 2 + 1
        roll_max = high.rolling(window=window, center=True).max()
        return high.where(high == roll_max).shift(left_right)

    @staticmethod
    def _pivot_low(low: pd.Series, left_right: int) -> pd.Series:
        """Confirmed pivot low using past and future bars, equivalent to Pine ta.pivotlow."""
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

    def _add_confirmed_pivots(self, df: DataFrame, rule: str, prefix: str, pivot_len: int) -> DataFrame:
        htf = (
            df.set_index("date")
            .resample(rule, label="right", closed="left")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )
        htf[f"raw_high_{prefix}"] = self._pivot_high(htf["high"], pivot_len)
        htf[f"raw_low_{prefix}"] = self._pivot_low(htf["low"], pivot_len)
        return df.merge(
            htf[[f"raw_high_{prefix}", f"raw_low_{prefix}"]].reset_index(),
            on="date",
            how="left",
        )

    def _simulate_candidate_engine(self, dataframe: DataFrame) -> DataFrame:
        """Stateful 1m candidate engine based on sfp_candidate_debug.pine."""
        df = dataframe.copy()
        pivot = int(self.pivot_len.value)
        min_move = float(self.min_move_usd.value)
        merge = float(self.merge_usd.value)
        clean_break = float(self.clean_break_usd.value)
        sweep = float(self.sweep_usd.value)
        stop_buffer = float(self.stop_buffer_usd.value)
        tp0_r = float(self.tp0_r.value)
        tp4_r = float(self.tp4_r.value)
        protected_offset = float(self.protected_stop_offset_usd.value)
        max_raw = int(self.max_raw_swings.value)
        max_candidates = int(self.max_candidates.value)

        if bool(self.use_1m_swings.value):
            df["raw_high_1m"] = self._pivot_high(df["high"], pivot)
            df["raw_low_1m"] = self._pivot_low(df["low"], pivot)
        else:
            df["raw_high_1m"] = float("nan")
            df["raw_low_1m"] = float("nan")
        if bool(self.use_5m_swings.value):
            df = self._add_confirmed_pivots(df, "5min", "5m", pivot)
        else:
            df["raw_high_5m"] = float("nan")
            df["raw_low_5m"] = float("nan")
        if bool(self.use_15m_swings.value):
            df = self._add_confirmed_pivots(df, "15min", "15m", pivot)
        else:
            df["raw_high_15m"] = float("nan")
            df["raw_low_15m"] = float("nan")
        if bool(self.use_1h_swings.value):
            df = self._add_confirmed_pivots(df, "1h", "1h", pivot)
        else:
            df["raw_high_1h"] = float("nan")
            df["raw_low_1h"] = float("nan")
        if bool(self.use_4h_swings.value):
            df = self._add_confirmed_pivots(df, "4h", "4h", pivot)
        else:
            df["raw_high_4h"] = float("nan")
            df["raw_low_4h"] = float("nan")

        atr = self._atr(df, int(self.impulse_atr_len.value))
        bar_range = df["high"] - df["low"]
        body = (df["close"] - df["open"]).abs()
        lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
        upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
        close_portion = float(self.impulse_close_portion.value)
        body_atr = float(self.impulse_body_atr.value)
        wick_portion = float(self.exhaustion_wick_portion.value)
        df["bear_impulse_bar"] = (
            bool(self.use_impulse_filter.value)
            & (df["close"] < df["open"])
            & (body >= atr * body_atr)
            & (bar_range > 0)
            & ((df["close"] - df["low"]) <= bar_range * close_portion)
        )
        df["bull_impulse_bar"] = (
            bool(self.use_impulse_filter.value)
            & (df["close"] > df["open"])
            & (body >= atr * body_atr)
            & (bar_range > 0)
            & ((df["high"] - df["close"]) <= bar_range * close_portion)
        )
        df["bear_exhaustion"] = (bar_range > 0) & (lower_wick >= bar_range * wick_portion) & (df["close"] > df["low"] + bar_range * 0.45)
        df["bull_exhaustion"] = (bar_range > 0) & (upper_wick >= bar_range * wick_portion) & (df["close"] < df["high"] - bar_range * 0.45)

        raw_levels: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        impulse_mode = 0
        impulse_started_pos: Optional[int] = None

        columns = [
            "entry_high", "entry_low", "entry_price", "entry_stop", "entry_risk",
            "tp0_price", "tp4_price", "protected_stop", "sfp_short", "sfp_long",
            "active_entry_high_count", "active_entry_low_count", "last_entry_level",
        ]
        for col in columns:
            df[col] = float("nan")
        df["sfp_short"] = 0
        df["sfp_long"] = 0
        df["active_entry_high_count"] = 0
        df["active_entry_low_count"] = 0

        for pos, row in enumerate(df.itertuples()):
            high = float(row.high)
            low = float(row.low)
            close = float(row.close)
            if bool(getattr(row, "bear_impulse_bar")):
                impulse_mode = -1
                impulse_started_pos = pos
            elif bool(getattr(row, "bull_impulse_bar")):
                impulse_mode = 1
                impulse_started_pos = pos
            elif (
                impulse_mode == -1
                and impulse_started_pos is not None
                and pos - impulse_started_pos >= int(self.impulse_bars_hold.value)
                and bool(getattr(row, "bear_exhaustion"))
            ):
                impulse_mode = 0
                impulse_started_pos = None
            elif (
                impulse_mode == 1
                and impulse_started_pos is not None
                and pos - impulse_started_pos >= int(self.impulse_bars_hold.value)
                and bool(getattr(row, "bull_exhaustion"))
            ):
                impulse_mode = 0
                impulse_started_pos = None

            def counter_trend_blocked(is_high: bool) -> bool:
                return (impulse_mode == -1 and not is_high) or (impulse_mode == 1 and is_high)

            for source in ["1m", "5m", "15m", "1h", "4h"]:
                pivot_high = getattr(row, f"raw_high_{source}")
                pivot_low = getattr(row, f"raw_low_{source}")
                if not pd.isna(pivot_high) and not counter_trend_blocked(True):
                    raw_levels.append({"price": float(pivot_high), "is_high": True, "active": True, "source": source})
                    self._trim_old(raw_levels, max_raw)
                if not pd.isna(pivot_low) and not counter_trend_blocked(False):
                    raw_levels.append({"price": float(pivot_low), "is_high": False, "active": True, "source": source})
                    self._trim_old(raw_levels, max_raw)

            for raw in raw_levels:
                if not raw["active"]:
                    continue
                price = float(raw["price"])
                is_high = bool(raw["is_high"])
                move_size = price - low if is_high else high - price
                if move_size < min_move or counter_trend_blocked(is_high):
                    continue

                duplicate = any(
                    c["active"] and c["is_high"] == is_high and abs(float(c["price"]) - price) <= merge
                    for c in candidates
                )
                raw["active"] = False
                if duplicate:
                    continue
                candidates.append({"price": price, "is_high": is_high, "active": True, "source": raw.get("source", "")})
                self._trim_old(candidates, max_candidates)

            active_highs = [c for c in candidates if c["active"] and c["is_high"]]
            active_lows = [c for c in candidates if c["active"] and not c["is_high"]]
            df.iat[pos, df.columns.get_loc("active_entry_high_count")] = len(active_highs)
            df.iat[pos, df.columns.get_loc("active_entry_low_count")] = len(active_lows)

            # Short SFP: level already active before this 1m candle, sweep + reclaim inside candle.
            short_matches = [
                c for c in active_highs
                if high >= float(c["price"]) + sweep and close < float(c["price"])
            ]
            # Long SFP: level already active before this 1m candle, sweep + reclaim inside candle.
            long_matches = [
                c for c in active_lows
                if low <= float(c["price"]) - sweep and close > float(c["price"])
            ]

            if short_matches:
                level = min(short_matches, key=lambda c: high - float(c["price"]))
                entry = float(level["price"])
                stop = high + stop_buffer
                risk = stop - entry
                if risk > 0:
                    tp0 = entry - risk * tp0_r
                    tp4 = entry - risk * tp4_r
                    protected_stop = tp0 - protected_offset
                    df.iat[pos, df.columns.get_loc("sfp_short")] = 1
                    df.iat[pos, df.columns.get_loc("entry_high")] = entry
                    df.iat[pos, df.columns.get_loc("entry_price")] = entry
                    df.iat[pos, df.columns.get_loc("entry_stop")] = stop
                    df.iat[pos, df.columns.get_loc("entry_risk")] = risk
                    df.iat[pos, df.columns.get_loc("tp0_price")] = tp0
                    df.iat[pos, df.columns.get_loc("tp4_price")] = tp4
                    df.iat[pos, df.columns.get_loc("protected_stop")] = protected_stop
                    df.iat[pos, df.columns.get_loc("last_entry_level")] = entry
                    level["active"] = False

            if long_matches:
                level = min(long_matches, key=lambda c: float(c["price"]) - low)
                entry = float(level["price"])
                stop = low - stop_buffer
                risk = entry - stop
                if risk > 0:
                    tp0 = entry + risk * tp0_r
                    tp4 = entry + risk * tp4_r
                    protected_stop = tp0 + protected_offset
                    df.iat[pos, df.columns.get_loc("sfp_long")] = 1
                    df.iat[pos, df.columns.get_loc("entry_low")] = entry
                    df.iat[pos, df.columns.get_loc("entry_price")] = entry
                    df.iat[pos, df.columns.get_loc("entry_stop")] = stop
                    df.iat[pos, df.columns.get_loc("entry_risk")] = risk
                    df.iat[pos, df.columns.get_loc("tp0_price")] = tp0
                    df.iat[pos, df.columns.get_loc("tp4_price")] = tp4
                    df.iat[pos, df.columns.get_loc("protected_stop")] = protected_stop
                    df.iat[pos, df.columns.get_loc("last_entry_level")] = entry
                    level["active"] = False

            # Clean breaks retire candidates that were not reclaimed.
            for candidate in candidates:
                if not candidate["active"]:
                    continue
                price = float(candidate["price"])
                is_high = bool(candidate["is_high"])
                if (is_high and close > price + clean_break) or (not is_high and close < price - clean_break):
                    candidate["active"] = False

        return df

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        return self._simulate_candidate_engine(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = None

        long_condition = dataframe["sfp_long"] == 1
        short_condition = dataframe["sfp_short"] == 1

        dataframe.loc[long_condition, ["enter_long", "enter_tag"]] = (1, "sfp_long_entry_low")
        dataframe.loc[short_condition, ["enter_short", "enter_tag"]] = (1, "sfp_short_entry_high")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def _plan_from_signal_row(self, row: pd.Series, side: str) -> Optional[TradePlan]:
        entry = row.get("entry_price")
        stop = row.get("entry_stop")
        tp0 = row.get("tp0_price")
        tp4 = row.get("tp4_price")
        risk = row.get("entry_risk")
        protected = row.get("protected_stop")
        if any(pd.isna(x) for x in [entry, stop, tp0, tp4, risk, protected]):
            return None
        return TradePlan(side, float(entry), float(stop), float(tp0), float(tp4), float(risk), float(protected))

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
        tp0_hit = False
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
