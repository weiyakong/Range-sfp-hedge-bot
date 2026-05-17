"""
Verification harness: re-runs the indicator pipeline of SFPSmartMoneyShort on
the downloaded data, then prints diagnostics so we can spot-check whether the
Python port matches the Pine spec.

Run inside the Docker container:
  docker run --rm -v "$PWD/freqtrade/user_data:/freqtrade/user_data" \
    --entrypoint python freqtradeorg/freqtrade:stable \
    /freqtrade/user_data/strategies/verify.py
"""
import sys, os, math
import numpy as np
import pandas as pd

sys.path.insert(0, "/freqtrade/user_data/strategies")
from SFPSmartMoneyShort import pivot_high, pivot_low, valuewhen  # noqa: E402

DATA_DIR = "/freqtrade/user_data/data/binance/futures"


def load(timeframe: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"BTC_USDT_USDT-{timeframe}-futures.feather")
    df = pd.read_feather(path)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main() -> None:
    d15 = load("15m")
    d4h = load("4h")
    d1d = load("1d")
    print(f"15m bars: {len(d15)}  range: {d15.date.iloc[0]} -> {d15.date.iloc[-1]}")
    print(f"4h  bars: {len(d4h)}")
    print(f"1d  bars: {len(d1d)}")

    SW = 20

    # ---------------- 15m pivots ----------------
    ph = pivot_high(d15["high"], SW, SW)
    pl = pivot_low(d15["low"], SW, SW)
    print(f"\n15m pivot highs confirmed: {ph.notna().sum()}  (avg every "
          f"{len(d15)/max(ph.notna().sum(),1):.0f} bars)")
    print(f"15m pivot lows  confirmed: {pl.notna().sum()}")

    # First few pivots: verify pivot value equals high `right` bars before confirm bar
    print("\nFirst 5 pivot highs — confirmed at bar i; value should equal high[i-20]")
    found = 0
    for i in range(len(d15)):
        if not np.isnan(ph.iloc[i]):
            pivot_bar = i - SW
            expect = d15["high"].iloc[pivot_bar]
            ok = "OK" if math.isclose(expect, ph.iloc[i]) else "MISMATCH"
            print(f"  confirm_i={i} pivot_bar={pivot_bar} value={ph.iloc[i]:.2f} "
                  f"high[i-20]={expect:.2f} [{ok}]")
            found += 1
            if found >= 5:
                break

    # Strict pivot property check (sample)
    print("\nPivot strictness check on 50 random confirmed pivots…")
    rng = np.random.default_rng(0)
    confirmed_idx = np.where(ph.notna().values)[0]
    sample = rng.choice(confirmed_idx, size=min(50, len(confirmed_idx)), replace=False)
    bad = 0
    for i in sample:
        center = i - SW
        win = d15["high"].iloc[center-SW:center+SW+1].values
        c = win[SW]
        if c != win.max():
            bad += 1
        if (win == c).sum() != 1:
            bad += 1
    print(f"  pivots failing strict (unique max in window): {bad}")

    # ---------------- valuewhen sanity ----------------
    h15 = valuewhen(ph.notna(), ph, 0)
    h15p = valuewhen(ph.notna(), ph, 1)
    # On bar of confirm, h15 should == that pivot; h15p == previous pivot
    idx = confirmed_idx[5]  # 6th confirmed pivot
    prev_idx = confirmed_idx[4]
    print(f"\nvaluewhen check at bar {idx}: h15={h15.iloc[idx]:.2f} "
          f"expected={ph.iloc[idx]:.2f}  | h15p={h15p.iloc[idx]:.2f} "
          f"expected={ph.iloc[prev_idx]:.2f}")

    # ---------------- EQH count ----------------
    eq_usd = 100.0
    eqh = np.where(
        h15.notna() & h15p.notna() & ((h15 - h15p).abs() <= eq_usd),
        (h15 + h15p) / 2.0,
        np.nan,
    )
    eqh_distinct_periods = pd.Series(eqh).notna().diff().fillna(False).sum()
    print(f"\nEQH active bars: {pd.Series(eqh).notna().sum()}  "
          f"(non-na count). Roughly {pd.Series(eqh).notna().mean()*100:.1f}% of time.")

    # ---------------- BOS-down + Bear OB ----------------
    last_pl = valuewhen(pl.notna(), pl, 0)
    bos = (d15["close"] < last_pl) & (d15["close"].shift(1) >= last_pl.shift(1))
    print(f"\n15m BOS-down events: {bos.sum()}")

    bull = d15["close"] > d15["open"]
    last_bull_hi = valuewhen(bull, d15["high"], 0)
    last_bull_lo = valuewhen(bull, d15["low"], 0)
    ob_hi = np.full(len(d15), np.nan)
    cur_hi = np.nan
    cur_lo = np.nan
    bvals = bos.values
    bhi = last_bull_hi.values
    blo = last_bull_lo.values
    highs = d15["high"].values
    n_set = 0
    n_invalidated = 0
    for i in range(len(d15)):
        if bvals[i]:
            cur_hi = bhi[i]
            cur_lo = blo[i]
            n_set += 1
        if not np.isnan(cur_hi) and highs[i] > cur_hi:
            cur_hi = np.nan
            cur_lo = np.nan
            n_invalidated += 1
        ob_hi[i] = cur_hi
    active_bars = pd.Series(ob_hi).notna().sum()
    print(f"  OB set events: {n_set}, invalidations: {n_invalidated}, "
          f"active bars: {active_bars} ({active_bars/len(d15)*100:.1f}% of time)")

    # ---------------- SFP triggers per level ----------------
    # Build a minimal df
    df = d15.copy()
    df["h15"] = h15
    df["h15p"] = h15p
    df["eqh"] = eqh
    df["l15"] = valuewhen(pl.notna(), pl, 0)
    df["l15p"] = valuewhen(pl.notna(), pl, 1)

    # PDH from 1d
    inf1d = d1d.sort_values("date").reset_index(drop=True).copy()
    inf1d["pdh"] = inf1d["high"].shift(1)
    inf1d["pdl"] = inf1d["low"].shift(1)
    inf1d["_week"] = inf1d["date"].dt.strftime("%G-%V")
    w = inf1d.groupby("_week").agg(wh=("high","max"), wl=("low","min")).reset_index()
    w["pwh"] = w["wh"].shift(1); w["pwl"] = w["wl"].shift(1)
    inf1d = inf1d.merge(w[["_week","pwh","pwl"]], on="_week", how="left")
    inf1d["_month"] = inf1d["date"].dt.strftime("%Y-%m")
    m = inf1d.groupby("_month").agg(mh=("high","max"), ml=("low","min")).reset_index()
    m["pmh"] = m["mh"].shift(1); m["pml"] = m["ml"].shift(1)
    inf1d = inf1d.merge(m[["_month","pmh","pml"]], on="_month", how="left")
    df = pd.merge_asof(df.sort_values("date"),
                       inf1d[["date","pdh","pdl","pwh","pwl","pmh","pml"]].rename(columns={"date":"d1"}),
                       left_on="date", right_on="d1", direction="backward")

    # 4H pivots
    inf4 = d4h.sort_values("date").reset_index(drop=True).copy()
    ph4 = pivot_high(inf4["high"], SW, SW)
    pl4 = pivot_low(inf4["low"], SW, SW)
    inf4["h4"] = valuewhen(ph4.notna(), ph4, 0)
    inf4["l4"] = valuewhen(pl4.notna(), pl4, 0)
    df = pd.merge_asof(df.sort_values("date"),
                       inf4[["date","h4","l4"]].rename(columns={"date":"d4"}),
                       left_on="date", right_on="d4", direction="backward")
    df["bear_ob_hi"] = ob_hi
    df["bear_ob_lo"] = np.nan  # not needed for trigger counts here

    def hit(col):
        lvl = df[col]
        return lvl.notna() & (df["high"] >= lvl) & (df["close"] < lvl)

    for col in ["h15","eqh","pdh","pwh","pmh","bear_ob_hi","h4"]:
        n = hit(col).sum()
        print(f"  SFP hits at {col:<14s}: {n}")

    # ---------------- Combined short_lvl + confluence ----------------
    short_lvl = np.select(
        [hit("h15"), hit("eqh"), hit("pdh"), hit("pwh"), hit("pmh"), hit("bear_ob_hi")],
        [df["h15"], df["eqh"], df["pdh"], df["pwh"], df["pmh"], df["bear_ob_hi"]],
        default=np.nan,
    )
    n_signals = pd.Series(short_lvl).notna().sum()
    print(f"\nshort_lvl signal bars: {n_signals}")

    # confluence
    near_usd = 150.0
    def near(a, b):
        return ~np.isnan(a) & ~np.isnan(b) & (np.abs(a - b) <= near_usd)
    cols = ["h15","eqh","pdh","pwh","pmh","bear_ob_hi","h4"]
    sc = np.zeros(len(df), dtype=int)
    for c in cols:
        sc += near(short_lvl, df[c].values).astype(int)
    print(f"signal-bar confluence distribution:")
    sc_series = pd.Series(sc[pd.Series(short_lvl).notna()])
    print(sc_series.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
