# Next Steps

Version: **0.4.2**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Validate broken relevant level lifecycle

Open BTC on a 15m chart and find Relevant Reaction High / Low levels that are later broken.

Expected behavior:

- A Relevant Reaction Low stops acting active after price cleanly breaks below it.
- A Relevant Reaction High stops acting active after price cleanly breaks above it.
- Broken levels stop extending as active levels.
- Broken levels are hidden by default unless `showPastRelevantLevels = true`.
- Broken lows do not create Bull SFP candidates.
- Broken highs do not create Bear SFP candidates.

## 2. Validate clean break settings

Defaults are:

- `cleanBreakCloseRequired = true`
- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`
- `keepRelevantLevelAfterCleanBreak = false`

With the default close requirement, a Relevant Reaction Low should break when price closes below the level by the USD/ATR buffer or displaces strongly through it. A Relevant Reaction High should break when price closes above the level by the USD/ATR buffer or displaces strongly through it.

## 3. Validate future retests of broken levels

After a Relevant Reaction Low breaks downward:

- Later retests from below should not show `Reaction at Relevant Level` for a long reaction.
- Later retests from below should not show `SFP at Relevant Low`.
- If past relevant labels are enabled, only `Broken support retest` may appear.

After a Relevant Reaction High breaks upward:

- Later retests from above should not show `Reaction at Relevant Level` for a short reaction.
- Later retests from above should not show `SFP at Relevant High`.
- If past relevant labels are enabled, only `Broken resistance retest` may appear.

## 4. Validate displacement through multiple levels

Find strong impulse candles or sequences that cross several relevant levels.

Expected behavior:

- Bearish displacement through multiple Relevant Reaction Lows marks all crossed lows broken/past.
- Bullish displacement through multiple Relevant Reaction Highs marks all crossed highs broken/past.
- Crossed broken levels are not used later for same-direction reaction/SFP labels.

## 5. Validate nearest relevant dashboard field

Compact dashboard should show:

- Version
- Market Mode
- EMA Bias
- HTF Context
- Nearest Relevant Level
- Last Relevant Event

Nearest Relevant Level should ignore broken/past levels. It should only consider active Relevant Reaction Lows below price and active Relevant Reaction Highs above price. If none exist, it should show `None`.

## 6. Validate label cleanup

The chart should use short labels:

- `Relevant High`
- `Relevant Low`
- `SFP at Relevant Low`
- `SFP at Relevant High`
- `Broken support retest`
- `Broken resistance retest`

`relevantEventCooldownBars = 12` should prevent repeated labels for the same level/zone.

## 7. Keep automation out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP0, TP1 / TP2 / TP3, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, Fibonacci, FVG, Volume Profile, CVD, AVWAP, or Moon cycle module should be added in v0.4.2.

## 8. Future work

Only after relevant level lifecycle and broken-level behavior are visually trusted should future versions revisit trade qualification, paper trading, testnet work, or advanced context modules.
