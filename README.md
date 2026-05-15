# Range SFP Hedge Bot

Version: **0.4.1**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.4.1 keeps the project visual-only and adds a quieter **Relevant Reaction Levels** module.

## Main purpose of v0.4.1

Version 0.4.1 stops labeling minor ignored reactions and focuses on old horizontal levels that already proved importance.

Core idea:

- A swing, body cluster, range boundary, or D/W/M body level is only promoted to a **Relevant Reaction High** or **Relevant Reaction Low** after price moves away strongly from it.
- Strong reaction is measured by USD distance, ATR distance, percent move, or a local structure break.
- Relevant Reaction Levels remain useful for future retests/rejections/SFP candidates.
- Ordinary past swings remain muted historical context and are not the same as relevant reaction levels.

## What the indicator shows

- Relevant Reaction High / Relevant Reaction Low levels, extended right and visually emphasized.
- Reaction at Relevant Level and SFP candidate at Relevant Level labels when price later returns to a relevant level.
- Higher-timeframe swing context from 4H, 8H, 12H, and 1D, with optional 1H medium structure.
- Active vs Past swing state for HTF/LTF context levels.
- D/W/M body-aligned context levels:
  - Daily: lime / light green.
  - Weekly: orange.
  - Monthly: white by default and configurable.
- Optional ordinary D/W/M high/low context levels, disabled by default.
- Compact dashboard with Version, Market Mode, EMA Bias, HTF Context, Nearest Relevant Level, and Last Relevant Event.

## Relevant Reaction Level requirements

A candidate level becomes relevant only after a strong reaction within `reactionLookaheadBars`.

Defaults:

- `reactionLookaheadBars = 24`
- `reactionMinUsd = 700`
- `reactionMinAtr = 3.0`
- `reactionMinPercent = 0.7`

A Relevant Reaction High is created only after price moves down strongly from a candidate high. A Relevant Reaction Low is created only after price moves up strongly from a candidate low. Small 100–300 USD reactions should generally not create relevant levels.

## Noise reduction defaults

Defaults are intentionally quiet:

- `showRelevantReactionLevels = true`
- `showPastSwingLevels = true`
- `showMinorReactionLabels = false`
- `showMicroSwingLabels = false`
- `showDebugLabels = false`
- `showStructureCandidates = false`
- `showOrdinaryDwmHighLowLevels = false`
- `dashboardMode = Compact`

If something is ignored, the indicator should usually stay silent.

## What v0.4.1 deliberately does not do

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
