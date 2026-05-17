# Freqtrade port of SFP Smart Money Strategy v1 (SHORT ONLY)

Python/Freqtrade port of
[`tradingview/sfp_smart_money_strategy_v1_short_only.pine`](../tradingview/sfp_smart_money_strategy_v1_short_only.pine).

## Layout

```
freqtrade/
├── README.md
└── user_data/
    ├── config.json                      # SFP strategy config (BTC/USDT:USDT futures, 15m)
    ├── config_nfi.json                  # Optional: NFI X7 config (see "Optional: NFI X7" below)
    └── strategies/
        ├── SFPSmartMoneyShort.py        # The port (faithful to Pine)
        └── verify.py                    # Indicator audit harness
```

Everything under `user_data/data/`, `user_data/backtest_results/`, and
`user_data/logs/` is generated at runtime and is gitignored.

## Strategy port — what it does

A faithful port of the Pine v6 strategy:

- Base timeframe **15m**, informative **4h** + **1d** (with weekly/monthly
  re-aggregation from 1d).
- 15m and 4H pivots via custom `pivot_high`/`pivot_low` matching Pine's
  `ta.pivothigh(left, right)` confirmation lag semantics (`lookahead_off`).
- Equal-high detection (EQH), 15m BOS-down + bearish order-block tracking.
- Multi-timeframe confluence scoring across `h15`, `eqh`, `pdh/pwh/pmh`,
  bearish OB hi/lo, and 4h `h4`.
- SFP entry trigger: `high >= level AND close < level` on a high-confluence
  level, with a downside-room (`target_dn ≤ tp0`) gate.
- Entry math, anchored to the **signal-bar close** to match Pine exactly:
  - `sl = signal_high + sl_buffer`
  - `r  = sl − signal_close + fee(signal_close)`
  - `tp0 = signal_close − 2·r`
  - `tp1..tp5 = tp0 − N·tp_step`
- 50% partial at TP0 + 5× 10% runners at TP1..TP5 via
  `adjust_trade_position`.
- Mode A / B / C SL trailing via `custom_stoploss` (BE after TP0 in C,
  aggressive ladder lock-in in B, loose in A).

## Quick start (Docker)

Prereq: Docker / OrbStack running.

```bash
docker pull freqtradeorg/freqtrade:stable

# 2 years of BTC/USDT:USDT 15m + 4h + 1d (futures)
docker run --rm -v "$PWD/freqtrade/user_data:/freqtrade/user_data" \
  freqtradeorg/freqtrade:stable download-data \
  --exchange binance --pairs BTC/USDT:USDT \
  --timeframes 15m 4h 1d \
  --timerange 20240517-20260517 \
  --trading-mode futures --data-format-ohlcv feather

# Backtest
docker run --rm -v "$PWD/freqtrade/user_data:/freqtrade/user_data" \
  freqtradeorg/freqtrade:stable backtesting \
  --config user_data/config.json \
  --strategy SFPSmartMoneyShort \
  --timeframe 15m \
  --timerange 20240517-20260517 \
  --data-format-ohlcv feather --cache none
```

### Switch trade-management mode

Edit `mode: str = "A"` in `SFPSmartMoneyShort.py` to `"B"` (aggressive
ladder lock-in) or `"C"` (BE after TP0).

### Tune the SL buffer

In `SFPSmartMoneyShort.py`:

- `sl_buffer = 100.0` — buffer beyond the wick (USD), **not the total
  risk**. R is `sl − close + fee`, so total risk varies with the wick
  size of the signal candle.
- For BTC on 15m, a single wick is often $200–500, so values of
  `20–100` may be too tight; consider 200+ or an ATR-scaled version.

## Verifying the port

```bash
docker run --rm -v "$PWD/freqtrade/user_data:/freqtrade/user_data" \
  --entrypoint python freqtradeorg/freqtrade:stable \
  /freqtrade/user_data/strategies/verify.py
```

Prints pivot timing checks, EQH/OB counts, SFP-hits-per-level breakdown,
and signal-bar confluence distribution.

## 2y backtest baseline (Mode A, BTC/USDT:USDT, 2024-05-21 → 2026-05-17)

| metric | value |
|---|---|
| trades | 542 (all short) |
| total profit | −2.06% |
| win rate | 24.2% |
| profit factor | 0.89 |
| max drawdown | 4.18% |
| market change (BTC) | +9.81% |

Result is approximately flat with a small negative drift; details and
exit-reason breakdown are in the PR description.

## Optional: NFI X7 comparison run

[`NostalgiaForInfinityX7`](https://github.com/iterativv/NostalgiaForInfinity)
is gitignored. To reproduce the comparison run:

```bash
git clone --depth 1 https://github.com/iterativv/NostalgiaForInfinity.git /tmp/nfi
cp /tmp/nfi/NostalgiaForInfinityX7.py freqtrade/user_data/strategies/
# Enable futures mode (line ~179):
sed -i '' 's/  is_futures_mode = False/  is_futures_mode = True/' \
  freqtrade/user_data/strategies/NostalgiaForInfinityX7.py

# Backtest on 10 majors (config provided)
docker run --rm -v "$PWD/freqtrade/user_data:/freqtrade/user_data" \
  freqtradeorg/freqtrade:stable backtesting \
  --config user_data/config_nfi.json \
  --strategy NostalgiaForInfinityX7 \
  --timeframe 5m \
  --timerange 20250517-20260517 \
  --data-format-ohlcv feather --cache none
```

Note: NFI is designed for 40-80 alt-coin pairs; BTC alone produces
zero entries because its filters are tuned for alt-coin volatility.

## Known port limitations vs the Pine original

| | Pine | Port |
|---|---|---|
| Entry fill | signal-bar close | next-bar limit @ bid |
| TP fill mechanic | each TP a limit @ exact `tpN` | `adjust_trade_position` → market-style fill at current bar rate |
| SL fill | stop attached, fills @ `sl` | freqtrade SL handler, fills @ next-bar open |
| Order persistence intra-bar | yes | per-closed-candle only |

Net effect: the port's results are realistically more conservative than
an idealised Pine backtest would show.
