"""
SFP Smart Money Strategy v1 (SHORT ONLY) — Python/Freqtrade port of
tradingview/sfp_smart_money_strategy_v1_short_only.pine

Faithful port: pivots, EQH, bearish order block, multi-timeframe confluence,
SFP entry on close-back-below, 2R TP0 + 5 stepped runners, and three SL
management modes (A/B/C).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter
from freqtrade.strategy import stoploss_from_absolute


# ----------------------------- helpers ---------------------------------------
def pivot_high(series: pd.Series, left: int, right: int) -> pd.Series:
    """Pine-style ta.pivothigh: bar i is a pivot if high[i] is the max of
    [i-left, i+right]. Returned aligned so the pivot value appears at i+right
    (i.e. the bar where the pivot is *confirmed*), like Pine's behaviour.
    Returns NaN where no pivot is confirmed."""
    n = len(series)
    out = np.full(n, np.nan)
    vals = series.values
    win = left + right + 1
    for i in range(win - 1, n):
        center = i - right
        if center - left < 0:
            continue
        window = vals[center - left:center + right + 1]
        c = vals[center]
        if c == window.max() and (window == c).sum() == 1:
            out[i] = c  # confirmed at bar i (= center + right)
    return pd.Series(out, index=series.index)


def pivot_low(series: pd.Series, left: int, right: int) -> pd.Series:
    n = len(series)
    out = np.full(n, np.nan)
    vals = series.values
    win = left + right + 1
    for i in range(win - 1, n):
        center = i - right
        if center - left < 0:
            continue
        window = vals[center - left:center + right + 1]
        c = vals[center]
        if c == window.min() and (window == c).sum() == 1:
            out[i] = c
    return pd.Series(out, index=series.index)


def valuewhen(cond: pd.Series, src: pd.Series, occurrence: int = 0) -> pd.Series:
    """Pine ta.valuewhen: value of src at the Nth most recent True of cond.
    occurrence=0 -> most recent, 1 -> one before that, etc."""
    out = np.full(len(src), np.nan)
    hits: list[float] = []
    s = src.values
    c = cond.values
    for i in range(len(src)):
        if c[i] and not (isinstance(s[i], float) and np.isnan(s[i])):
            hits.append(s[i])
        if len(hits) > occurrence:
            out[i] = hits[-1 - occurrence]
    return pd.Series(out, index=src.index)


# ----------------------------- strategy --------------------------------------
class SFPSmartMoneyShort(IStrategy):
    INTERFACE_VERSION = 3

    can_short: bool = True
    timeframe = "15m"

    # We manage exits entirely via custom_stoploss + adjust_trade_position.
    minimal_roi = {"0": 100}
    stoploss = -0.99  # superseded by custom_stoploss
    use_custom_stoploss = True
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count: int = 400

    position_adjustment_enable = True
    max_entry_position_adjustment = 0

    # ---- Pine inputs (as attrs so easy to tune) ----
    mode: str = "A"          # A / B / C
    swing15: int = 20
    swing4h: int = 20
    eq_usd: float = 100.0
    near_usd: float = 150.0
    min_conf: int = 1
    sl_buffer: float = 100.0
    tp_step: float = 300.0
    sl_lock: float = 150.0
    fee_taker: float = 0.10
    fee_maker: float = 0.036
    use_taker_taker: bool = True
    require_tp0_space: bool = True
    min_tp0_usd: float = 100.0

    @property
    def fee_pct(self) -> float:
        return (self.fee_taker * 2) if self.use_taker_taker else (self.fee_taker + self.fee_maker)

    # ---- informative pairs ----
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        info: list[tuple[str, str]] = []
        for p in pairs:
            info.append((p, "4h"))
            info.append((p, "1d"))
        return info

    # ---- indicators ----
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        # ---- 15m pivots ----
        ph = pivot_high(df["high"], self.swing15, self.swing15)
        pl = pivot_low(df["low"], self.swing15, self.swing15)
        df["ph15"] = ph
        df["pl15"] = pl
        df["h15"] = valuewhen(ph.notna(), ph, 0)
        df["h15p"] = valuewhen(ph.notna(), ph, 1)
        df["l15"] = valuewhen(pl.notna(), pl, 0)
        df["l15p"] = valuewhen(pl.notna(), pl, 1)

        # EQH: avg of last two 15m pivot highs if within eq_usd
        df["eqh"] = np.where(
            df["h15"].notna() & df["h15p"].notna() & ((df["h15"] - df["h15p"]).abs() <= self.eq_usd),
            (df["h15"] + df["h15p"]) / 2.0,
            np.nan,
        )

        # ---- BOS-down on 15m: close crosses under last 15m pivot low ----
        last_pl = df["l15"]  # most recent confirmed pivot low value
        df["bos_dn15"] = (df["close"] < last_pl) & (df["close"].shift(1) >= last_pl.shift(1))

        # last bullish 15m candle (close > open) high/low (Pine valuewhen)
        bull = df["close"] > df["open"]
        df["last_bull_hi"] = valuewhen(bull, df["high"], 0)
        df["last_bull_lo"] = valuewhen(bull, df["low"], 0)

        # ---- Bearish OB tracking (stateful loop) ----
        ob_hi = np.full(len(df), np.nan)
        ob_lo = np.full(len(df), np.nan)
        cur_hi = np.nan
        cur_lo = np.nan
        bos = df["bos_dn15"].values
        bhi = df["last_bull_hi"].values
        blo = df["last_bull_lo"].values
        highs = df["high"].values
        for i in range(len(df)):
            if bos[i]:
                cur_hi = bhi[i]
                cur_lo = blo[i]
            if not np.isnan(cur_hi) and highs[i] > cur_hi:
                cur_hi = np.nan
                cur_lo = np.nan
            ob_hi[i] = cur_hi
            ob_lo[i] = cur_lo
        df["bear_ob_hi"] = ob_hi
        df["bear_ob_lo"] = ob_lo

        # ---- 4H pivots via informative ----
        pair = metadata["pair"]
        inf4 = self.dp.get_pair_dataframe(pair, "4h").copy()
        inf4["ph4h"] = pivot_high(inf4["high"], self.swing4h, self.swing4h)
        inf4["pl4h"] = pivot_low(inf4["low"], self.swing4h, self.swing4h)
        inf4["h4"] = valuewhen(inf4["ph4h"].notna(), inf4["ph4h"], 0)
        inf4["l4"] = valuewhen(inf4["pl4h"].notna(), inf4["pl4h"], 0)
        # merge h4/l4 onto 15m using as-of (Pine lookahead_off semantics)
        inf4_small = inf4[["date", "h4", "l4"]].rename(columns={"date": "date_4h"})
        df = pd.merge_asof(
            df.sort_values("date"),
            inf4_small.sort_values("date_4h"),
            left_on="date",
            right_on="date_4h",
            direction="backward",
        )
        df.drop(columns=["date_4h"], inplace=True)

        # ---- 1D informative for pdh/pdl + derive pwh/pwl, pmh/pml ----
        inf1d = self.dp.get_pair_dataframe(pair, "1d").copy()
        inf1d = inf1d.sort_values("date").reset_index(drop=True)
        inf1d["pdh"] = inf1d["high"].shift(1)
        inf1d["pdl"] = inf1d["low"].shift(1)

        # Weekly: group by ISO week-year, prior week
        inf1d["_week"] = inf1d["date"].dt.strftime("%G-%V")
        weekly = inf1d.groupby("_week").agg(wh=("high", "max"), wl=("low", "min")).reset_index()
        weekly["pwh"] = weekly["wh"].shift(1)
        weekly["pwl"] = weekly["wl"].shift(1)
        inf1d = inf1d.merge(weekly[["_week", "pwh", "pwl"]], on="_week", how="left")

        # Monthly
        inf1d["_month"] = inf1d["date"].dt.strftime("%Y-%m")
        monthly = inf1d.groupby("_month").agg(mh=("high", "max"), ml=("low", "min")).reset_index()
        monthly["pmh"] = monthly["mh"].shift(1)
        monthly["pml"] = monthly["ml"].shift(1)
        inf1d = inf1d.merge(monthly[["_month", "pmh", "pml"]], on="_month", how="left")

        inf1d_small = inf1d[["date", "pdh", "pdl", "pwh", "pwl", "pmh", "pml"]].rename(
            columns={"date": "date_1d"}
        )
        df = pd.merge_asof(
            df.sort_values("date"),
            inf1d_small.sort_values("date_1d"),
            left_on="date",
            right_on="date_1d",
            direction="backward",
        )
        df.drop(columns=["date_1d"], inplace=True)

        # ---- SFP triggers per level: high >= lvl AND close < lvl ----
        def hit(lvl_col: str) -> pd.Series:
            lvl = df[lvl_col]
            return lvl.notna() & (df["high"] >= lvl) & (df["close"] < lvl)

        df["hit_h15"] = hit("h15")
        df["hit_eqh"] = hit("eqh")
        df["hit_pdh"] = hit("pdh")
        df["hit_pwh"] = hit("pwh")
        df["hit_pmh"] = hit("pmh")
        df["hit_ob_hi"] = hit("bear_ob_hi")
        df["hit_ob_lo"] = hit("bear_ob_lo")
        df["hit_h4"] = hit("h4")

        # short_lvl in Pine priority order
        df["short_lvl"] = np.select(
            [df["hit_h15"], df["hit_eqh"], df["hit_pdh"], df["hit_pwh"], df["hit_pmh"],
             df["hit_ob_hi"], df["hit_ob_lo"]],
            [df["h15"], df["eqh"], df["pdh"], df["pwh"], df["pmh"],
             df["bear_ob_hi"], df["bear_ob_lo"]],
            default=np.nan,
        )

        # confluence count for the candidate level
        def near(a: pd.Series, b: pd.Series) -> pd.Series:
            return a.notna() & b.notna() & ((a - b).abs() <= self.near_usd)

        lvl = df["short_lvl"]
        c = pd.Series(0, index=df.index)
        for col in ["h15", "eqh", "pdh", "pwh", "pmh", "bear_ob_hi", "bear_ob_lo", "h4"]:
            c = c + near(lvl, df[col]).astype(int)
        df["sc"] = c

        # target_dn: max among support levels below current close
        supports = df[["l15", "l15p", "pdl", "pwl", "pml", "l4"]]
        # Build mask of levels strictly below close
        below = supports.lt(df["close"], axis=0) & supports.notna()
        masked = supports.where(below)
        df["target_dn"] = masked.max(axis=1)

        # short setup — Pine semantics:
        #   sl  = high + slBuffer            (signal bar wick + buffer)
        #   r   = sl - close + fee(close)    (entry-to-SL distance + commission)
        #   tp0 = close - 2 * r              (anchored to SIGNAL close, not fill)
        sl_price = df["high"] + self.sl_buffer
        r = sl_price - df["close"] + df["close"] * self.fee_pct / 100.0
        tp0 = df["close"] - 2.0 * r
        space_ok = (~self.require_tp0_space) | (
            df["target_dn"].notna() & (df["target_dn"] <= tp0) & ((df["close"] - tp0) >= self.min_tp0_usd)
        )
        df["short_ok"] = (
            df["short_lvl"].notna()
            & (df["sc"] >= self.min_conf)
            & (r > 0)
            & space_ok
        )
        df["sfp_r"] = r
        df["sfp_sl"] = sl_price
        df["sfp_tp0"] = tp0
        # Snapshot of signal-bar close — used as Pine's `ep` so the TP ladder
        # is anchored exactly as Pine computes it, regardless of where the
        # freqtrade limit order eventually fills.
        df["sfp_ep_signal"] = df["close"]
        return df

    # ---- entry ----
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["short_ok"], ["enter_short", "enter_tag"]] = (1, "sfp_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # All exits are managed by custom_stoploss + adjust_trade_position
        return dataframe

    # ---- on entry, snapshot ep/sl/r/tps onto the trade ----
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return True
        # `last` is the SIGNAL candle (the bar that triggered enter_short=1).
        # In freqtrade backtest, the actual fill happens at next bar's open
        # at price `rate`. Pine, however, anchors ep := signal-bar close and
        # derives the TP/SL ladder from that. We reproduce Pine here:
        #   sl  = signal_high + slBuffer
        #   r   = sl - signal_close + fee(signal_close)
        #   tp0 = signal_close - 2 * r          (NOT fill_rate - 2*r)
        last = df.iloc[-1]
        signal_close = float(last["sfp_ep_signal"]) if not np.isnan(last["sfp_ep_signal"]) else float(rate)
        sl = float(last["sfp_sl"]) if not np.isnan(last["sfp_sl"]) else signal_close + self.sl_buffer
        r = float(last["sfp_r"]) if not np.isnan(last["sfp_r"]) else (sl - signal_close)
        tp0 = signal_close - 2 * r
        tps = [tp0 - i * self.tp_step for i in range(0, 6)]  # tp0..tp5

        key = f"{pair}|{current_time.isoformat()}"
        self._trade_state[key] = {
            "ep": signal_close,              # Pine's reference entry price
            "fill_rate": float(rate),        # freqtrade's actual fill (for diag)
            "sl": sl,
            "r": r,
            "tp": tps,                       # list len 6
            "got": [False] * 6,
            "filled_frac": 0.0,
        }
        self._trade_state[pair] = key
        return True

    _trade_state: dict = {}

    def _state_for(self, trade: Trade) -> Optional[dict]:
        key = self._trade_state.get(trade.pair)
        if key is None:
            return None
        return self._trade_state.get(key)

    # ---- TP ladder via partial exits ----
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        st = self._state_for(trade)
        if st is None:
            return None
        df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if df is None or len(df) < 1:
            return None
        last = df.iloc[-1]
        low = float(last["low"])

        # Determine which TPs are newly hit this candle (short: low <= tpN).
        # Percent ladder: TP0=50%, TP1..TP5=10% each.
        pct = [0.50, 0.10, 0.10, 0.10, 0.10, 0.10]
        new_frac = 0.0
        for i, tp in enumerate(st["tp"]):
            if not st["got"][i] and not np.isnan(tp) and low <= tp:
                st["got"][i] = True
                new_frac += pct[i]
        if new_frac <= 0.0:
            return None

        # Compute stake amount to remove. trade.stake_amount is current remaining stake.
        # We want to remove `new_frac` of the INITIAL stake.
        # Track initial stake on first call.
        if "initial_stake" not in st:
            # current filled_frac is 0 here; trade.stake_amount equals initial
            st["initial_stake"] = trade.stake_amount / (1.0 - st["filled_frac"]) if st["filled_frac"] < 1 else trade.stake_amount
        st["filled_frac"] = min(1.0, st["filled_frac"] + new_frac)
        remove_stake = st["initial_stake"] * new_frac
        # cap so we don't remove more than remaining
        remove_stake = min(remove_stake, trade.stake_amount * 0.999)
        return -remove_stake

    # ---- SL trailing per mode ----
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        st = self._state_for(trade)
        if st is None:
            # fallback wide
            return None
        ep = st["ep"]
        sl = st["sl"]
        got = st["got"]
        tp = st["tp"]

        # Recompute SL based on TP hits and mode (short: lower SL = tighter)
        new_sl = sl
        if self.mode == "C" and got[0] and not got[1]:
            new_sl = min(new_sl, ep)                 # BE
        if got[1]:
            new_sl = min(new_sl, tp[0] - self.sl_lock)
        if self.mode == "B" and got[2]:
            new_sl = min(new_sl, tp[1] - self.sl_lock)
        if self.mode == "B" and got[3]:
            new_sl = min(new_sl, tp[2] - self.sl_lock)
        if self.mode == "B" and got[4]:
            new_sl = min(new_sl, tp[3] - self.sl_lock)
        if self.mode == "B" and got[5]:
            new_sl = min(new_sl, tp[4] - self.sl_lock)
        st["sl"] = new_sl

        # Convert absolute SL price -> ratio expected by freqtrade
        return stoploss_from_absolute(
            stop_rate=new_sl,
            current_rate=current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage or 1.0,
        )

    # ---- leverage ----
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 entry_tag: Optional[str], **kwargs) -> float:
        return 1.0
