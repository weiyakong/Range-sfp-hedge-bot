# Range SFP Hedge Bot

Version: **0.4.4**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.4.4 narrows Relevant Reaction Level output so only true SFPs at active Relevant High / Low levels are actionable relevant-level events.

## Main purpose of v0.4.4

Version 0.4.4 makes the relevant-level lifecycle strict:

- A **Relevant Reaction Low** can print `SFP at Relevant Low` only while it is active, unbroken, and swept/reclaimed by the current candle.
- A **Relevant Reaction High** can print `SFP at Relevant High` only while it is active, unbroken, and swept/reclaimed by the current candle.
- Generic relevant-level reaction labels are disabled from working logic.
- Broken or past relevant levels cannot create SFP labels.
- Clean breaks are checked only after SFP is checked first, so one level cannot print SFP and Broken on the same candle.

## Relevant SFP lifecycle

Active Relevant Reaction Low:

- Valid Bull SFP: current low sweeps below the level and current close reclaims above it.
- Clean break: if no reclaim occurs and price closes below the buffered level, it becomes `Broken Relevant Low`.
- No touch or sweep means no relevant-level event.

Active Relevant Reaction High:

- Valid Bear SFP: current high sweeps above the level and current close reclaims below it.
- Clean break: if no reclaim occurs and price closes above the buffered level, it becomes `Broken Relevant High`.
- No touch or sweep means no relevant-level event.

Broken/past relevant levels:

- Are muted or hidden depending on `showPastRelevantLevels`.
- Do not extend as active levels.
- Do not create SFP labels.
- Do not create actionable relevant-level events.

## Clean break defaults

Clean breaks use close-based buffered logic by default:

- `cleanBreakCloseRequired = true`
- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`

Wick-through-and-reclaim candles are treated as SFPs first and do not break the relevant level on the same candle.

## Quiet visual defaults

Defaults are intentionally quiet:

- `showRelevantReactionLevels = true`
- `showRelevantSfpLabels = true`
- `showDebugReactionLabels = false`
- `showPastRelevantLevels = false`
- `showPastSwingLevels = true`
- `showMinorReactionLabels = false`
- `showMicroSwingLabels = false`
- `showDebugLabels = false`
- `showStructureCandidates = false`
- `showOrdinaryDwmHighLowLevels = false`
- `relevantEventCooldownBars = 12`
- `dashboardMode = Compact`

## Dashboard

Compact dashboard shows:

- Version: v0.4.4
- Market Mode
- EMA Bias
- HTF Context
- Nearest active Relevant Level
- Last Relevant Event

`Last Relevant Event` is limited to `SFP at Relevant Low`, `SFP at Relevant High`, `Broken Relevant Low`, `Broken Relevant High`, or `None`.

## What v0.4.4 deliberately does not do

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
- It does **not** add front-run reaction logic.
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
