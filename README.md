# Range SFP Hedge Bot

Version: **0.4.0**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.4.0 keeps the project visual-only and shifts important level discovery away from 15m swings toward multi-timeframe structure.

## Main purpose of v0.4.0

Version 0.4.0 is for validating whether the indicator sees meaningful higher-timeframe levels and classifies 15m reactions around those levels.

Core idea:

- **HTF levels** are the important reaction levels.
- **15m/LTF price action** is the reaction, rejection, reclaim, retest, and context layer.
- 15m micro swings are not primary important levels by default.

## What the indicator shows

- Higher-timeframe swing levels from 4H, 8H, 12H, and 1D.
- Optional 1H medium timeframe structure.
- Active vs Past swing state:
  - Active levels extend right until touched, swept, traded through, or displaced through.
  - Past levels stop extending and are muted.
- Swing scale labels/classes: `Major Swing`, `Medium Swing`, `Minor Swing`, and `Micro Swing`.
- LTF swings as separate `LTF Swing High`, `LTF Swing Low`, or muted `Micro Swing` context.
- Daily / Weekly / Monthly body-aligned context levels:
  - Daily: lime / light green.
  - Weekly: orange.
  - Monthly: white by default and configurable.
- Optional ordinary D/W/M high/low context levels, disabled by default.
- 15m reaction labels only when meaningful:
  - `Rejection at HTF level`
  - `SFP candidate at HTF level`
  - `Retest`
  - `Reclaim at HTF level`
  - `Minor reaction / ignore`
  - `Micro Chop`
- Multi-timeframe context labels/dashboard values:
  - `15m impulse only / local move`
  - `1H impulse / relevant intraday move`
  - `4H displacement / major move`
  - `Inside HTF range`
  - `Near HTF swing level`
  - `Mid-range / no important level nearby`
- Basic impulse/chop context such as `Bullish impulse`, `Bearish impulse`, `Post-impulse micro chop`, and `Post-impulse correction watch`.

## What v0.4.0 deliberately does not do

This version does **not** try to trade.

- It does **not** draw Entry.
- It does **not** draw SL.
- It does **not** draw TP0.
- It does **not** add TP1 / TP2 / TP3.
- It does **not** add runner logic.
- It does **not** add add-ons.
- It does **not** add re-entry logic.
- It does **not** add reversal logic.
- It does **not** add countertrend scalp mode.
- It does **not** add FVG, Volume Profile, CVD, AVWAP, Fibonacci, or Moon cycle modules.

## Default clutter controls

Defaults are intentionally conservative:

- `dashboardMode = Compact`
- `showHTFLevels = true`
- `showLTFSwings = true`
- `showMicroSwings = false`
- `showPastSwingLevels = true`
- `showReactionLabels = true`
- `showDebugLabels = false`
- `showOrdinaryDwmHighLowLevels = false`

## Visual-only scope

This version is intentionally visual-only.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** add webhook automation.
- It does **not** add server code.
- It does **not** provide financial advice.

## Risk warning

Trading crypto is risky. This project is only a visual charting aid. Levels can fail, markets can move quickly, and no label should be treated as financial advice.
