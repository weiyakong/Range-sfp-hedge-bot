# Range SFP Hedge Bot

Version: **0.3**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.3 provides a Pine Script v5 indicator for visually qualifying possible Swing Failure Pattern (SFP) setups around important BTC levels.

## What this project does

Version 0.3 is no longer meant to act like a noisy SFP label generator. It is a setup qualification tool:

1. Context first.
2. Decision zone second.
3. SFP/rejection third.
4. TP0 / reward-to-risk check fourth.

The indicator helps visualize:

- Previous daily, weekly, and monthly high/low levels as clean horizontal segments.
- Fresh swing highs and swing lows using pivot detection.
- Market Mode: `Trend`, `Range`, `Chop`, or `Expansion`.
- EMA bias, volatility state, setup status, active zone, and TP0 status in a dashboard.
- Strict `Chop / No Trade` filtering so SFPs inside compressed chop are suppressed.
- `Ambiguous / No Trade` handling when both sides sweep and context is unclear.
- `Countertrend / No Trade` handling in strong trends unless rejection and structure weakness/strength are present.
- Entry, SL, and TP0 lines when a valid visual setup qualifies.

## TP0 terminology

`TP0` is the protection point at **2R** from the planned entry. At TP0, the future concept is to close 50% and protect the remaining position.

TP1, TP2, TP3, and Runner logic are **not included yet**. They are planned future modules.

## SFP reclaim logic

Version 0.3 does **not** require mandatory candle-close confirmation by default. The default logic is based on an intrabar sweep and reclaim/current price returning back beyond the level. In Pine Script, the realtime bar's `close` value represents the current price.

A conservative candle-close confirmation option exists in the indicator settings, but it is not the default.

## What this project does not do

This version is intentionally visual-only.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** add webhook automation.
- It does **not** add server code.
- It does **not** provide financial advice.

## Planned future modules

Future versions may explore additional analysis modules after visual testing:

- TP1, TP2, TP3, and Runner handling.
- FVG.
- Volume Profile, POC, VAH, and VAL.
- CVD.
- Anchored VWAP.
- Fibonacci.
- Multiple-top/bottom RSI divergence.
- Paper trading tools after validation.
- Exchange testnet experiments only after validation.

Real exchange execution is not part of version 0.3.

## Risk warning

Trading crypto is risky. SFP setups can fail, levels can break, and fast markets can move against a position quickly. Never risk more than you can afford to lose. Any future trading system should use strict risk management, and risk per trade should remain small.
