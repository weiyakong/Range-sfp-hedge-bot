# Range SFP Hedge Bot

Version: **0.3.8**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.3.8 intentionally stops trying to generate trade entries and focuses only on validating whether the indicator sees the same structure, swing, and higher-timeframe body levels that a human chart reader sees.

## What this project does in v0.3.8

Version 0.3.8 is a clean **structure-and-level visualizer**:

- Draws meaningful fresh Swing High / Swing Low levels and extends them right until touched.
- Hides consumed levels by default, with optional muted consumed-level display through `showConsumedLevels`.
- Validates and freezes local Structure High / Structure Low levels instead of treating every rolling high/low as structure.
- Requires structure validation through repeated touches/reactions, repeated body levels, consolidation tops/bottoms, or confirmed swings.
- Keeps Daily / Weekly / Monthly body-aligned levels because they are important context:
  - Daily body levels: lime / light green.
  - Weekly body levels: orange.
  - Monthly body levels: white by default and configurable.
- Keeps ordinary D/W/M wick high/low levels optional and context-only, disabled by default with `showOrdinaryDwmHighLowLevels = false`.
- Shows context labels only, such as `Lower High`, `Higher Low`, `Retest`, `Structure reaction`, and `Possible continuation`.
- Shows `Bear SFP candidate` and `Bull SFP candidate` labels only when an already-existing fresh level is swept and reclaimed.
- Uses a compact dashboard by default with Version, Market Mode, EMA Bias, Active scenario, Nearest fresh level, and Last structure event.

## What v0.3.8 deliberately does not do

Version 0.3.8 does **not** generate trade plans.

- It does **not** draw Entry.
- It does **not** draw SL.
- It does **not** draw TP0.
- It does **not** classify setups as `Valid Setup`.
- It does **not** show `Missed / Too Late`.
- It does **not** use `Countertrend / No Trade` as a trade decision.
- It does **not** create trade plans from SFP candidates.

The goal is level validation first. Trade decisioning and execution logic should not be added until the visual structure model is trusted.

## Structure model

A local structure level must be validated before it is drawn as a frozen level. Rolling highs/lows are only candidates and are hidden by default unless `showStructureCandidates` is enabled for debugging.

Default BTC 15m testing settings:

- `minStructureBars = 12`
- `minStructureTouches = 2`
- `structureToleranceUsd = 75`
- `structureLookback = 24`

Once a Structure High / Structure Low is frozen, it extends right until touched or consumed. A new SFP candidate cannot be created from a structure level on the same candle that created the structure level.

## Visual-only scope

This version is intentionally visual-only.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** add webhook automation.
- It does **not** add server code.
- It does **not** provide financial advice.

## Not included in this version

Do not add these modules to v0.3.8:

- Runner logic.
- Add-ons.
- Re-entry logic.
- Reversal engine.
- Countertrend scalp mode.
- TP1 / TP2 / TP3.
- FVG.
- Volume Profile.
- CVD.
- AVWAP.
- Fibonacci.
- Moon cycle.
- Live trading, webhooks, API keys, server code, or real bot execution.

## Risk warning

Trading crypto is risky. This project is only a visual charting aid. Levels can fail, markets can move quickly, and no label should be treated as financial advice.
