# Range SFP Hedge Bot

Version: **0.4.2**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.4.2 keeps the project visual-only and fixes Relevant Reaction Level lifecycle/directionality.

## Main purpose of v0.4.2

Version 0.4.2 ensures a Relevant Reaction Level stops acting active after it is cleanly broken.

Core rules:

- A **Relevant Reaction Low** is active support only while price is above it and it has not been broken downward.
- A **Relevant Reaction High** is active resistance only while price is below it and it has not been broken upward.
- Broken relevant levels are removed from active reaction/SFP logic.
- Broken levels can optionally remain visible as muted history with `showPastRelevantLevels = true`.
- A broken support retest is not a long reaction.
- A broken resistance retest is not a short reaction.

## Relevant level lifecycle

Active Relevant Reaction Low:

- Can produce `Reaction at Relevant Level` from above.
- Can produce `SFP at Relevant Low` only while still active.
- Becomes `Broken Relevant Low` after a clean break below.

Active Relevant Reaction High:

- Can produce `Reaction at Relevant Level` from below.
- Can produce `SFP at Relevant High` only while still active.
- Becomes `Broken Relevant High` after a clean break above.

Broken/past relevant levels:

- Are muted or hidden depending on `showPastRelevantLevels`.
- Do not extend as active levels.
- Do not create SFP candidates.
- Do not create same-direction active reaction labels.
- May show only compact `Broken support retest` or `Broken resistance retest` labels when past relevant levels are visible.

## Clean break defaults

A clean break uses close-based logic by default:

- `cleanBreakCloseRequired = true`
- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`
- `keepRelevantLevelAfterCleanBreak = false`

A strong displacement candle through relevant levels also breaks them. Multiple crossed relevant lows/highs can be muted in the same displacement pass.

## Noise and grouping defaults

Defaults are intentionally quiet:

- `showRelevantReactionLevels = true`
- `showPastRelevantLevels = false`
- `showPastSwingLevels = true`
- `showMinorReactionLabels = false`
- `showMicroSwingLabels = false`
- `showDebugLabels = false`
- `showStructureCandidates = false`
- `showOrdinaryDwmHighLowLevels = false`
- `relevantEventCooldownBars = 12`
- `relevantZoneMergeUsd = 100`
- `dashboardMode = Compact`

Close relevant highs/lows are grouped into a zone label instead of producing many overlapping relevant lines.

## Dashboard

Compact dashboard shows:

- Version: v0.4.2
- Market Mode
- EMA Bias
- HTF Context
- Nearest Relevant Level
- Last Relevant Event

Nearest Relevant Level only considers active levels on the correct side of price: active lows below price and active highs above price.

## What v0.4.2 deliberately does not do

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
- It does **not** add Fibonacci, FVG, Volume Profile, CVD, AVWAP, or Moon cycle modules.

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
