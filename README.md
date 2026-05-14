# Range SFP Hedge Bot

Version: **0.2**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.2 provides a Pine Script v5 indicator for visually studying possible Swing Failure Pattern (SFP) reactions around important BTC levels.

## What this project does

- Adds a TradingView indicator for visual BTC chart analysis.
- Marks previous daily, weekly, and monthly high/low levels as clean horizontal segments.
- Marks simple swing highs and swing lows using pivot detection.
- Shows short SFP labels such as `Bear SFP`, `Bull SFP`, `Retest`, `Re-sweep`, `Conflict`, `Expansion`, and `Chop`.
- Draws short trigger-level lines so users can see exactly which level caused a label.
- Filters confusing same-candle conflicts, large expansion candles, stale swing levels, and repeated same-zone SFPs.

## What this project does not do

This version is intentionally visual-only.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** add webhook automation.
- It does **not** provide financial advice.

## Possible future direction

After the indicator is tested visually, future versions may add:

- More refined TradingView alerts.
- Webhook message design for paper trading only.
- Paper trading tools.
- Exchange testnet experiments only after validation.

Real exchange execution is not part of version 0.2.

## Risk warning

Trading crypto is risky. SFP setups can fail, levels can break, and fast markets can move against a position quickly. Never risk more than you can afford to lose. Any future trading system should use strict risk management, and risk per trade should remain small.
