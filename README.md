# Range SFP Hedge Bot

Version: **0.2**

Range SFP Hedge Bot starts as a **TradingView visual analysis project**. Version 0.2 provides a Pine Script v5 indicator that helps traders visually study possible Swing Failure Pattern (SFP) reactions around important BTC levels.

## Version history

- **v0.1:** Initial visual TradingView indicator and documentation. No trading, no exchange connection, and no API keys.
- **v0.2:** Keeps the v0.1 visual-only scope while improving chart readability with shorter labels, trigger-level lines, conflict handling, expansion filtering, swing freshness checks, and same-zone SFP clustering.

## What this project does

- Adds a TradingView indicator for visual BTC chart analysis.
- Marks daily, weekly, and monthly high/low levels.
- Marks simple swing highs and swing lows.
- Shows short possible bullish and bearish SFP labels when price sweeps a level and reclaims it.
- Draws short trigger-level lines so users can see which level caused a label.
- Filters confusing same-candle conflicts and large expansion candles.
- Includes a simple chop warning to remind the user when the market may be too compressed or noisy.

## What this project does not do

This version is intentionally limited.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** provide financial advice.

## Possible future direction

After the indicator is tested visually, future versions may add:

- TradingView alerts.
- Webhook messages.
- Paper trading only.
- Exchange testnet experiments only after validation.

Real exchange execution is not part of version 0.2.

## Risk warning

Trading crypto is risky. SFP setups can fail, levels can break, and fast markets can move against a position quickly. Never risk more than you can afford to lose. Any future trading system should use strict risk management, and risk per trade should remain small.
