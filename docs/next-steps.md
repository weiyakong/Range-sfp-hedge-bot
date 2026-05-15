# Next Steps

Version: **0.4.3**

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

- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`

With close-based lifecycle logic, a Relevant Reaction Low should break when price closes below the level by the USD/ATR buffer. A Relevant Reaction High should break when price closes above the level by the USD/ATR buffer.

## 3. Validate future retests of broken levels

After a Relevant Reaction Low breaks downward:

- Later retests from below should not show `Reaction at Relevant Level` for a long reaction.
- Later retests from below should not show `SFP at Relevant Low`.
- If past relevant labels are enabled, only `Broken support retest` may appear.

After a Relevant Reaction High breaks upward:

- Later retests from above should not show `Reaction at Relevant Level` for a short reaction.
- Later retests from above should not show `SFP at Relevant High`.
- If past relevant labels are enabled, only `Broken resistance retest` may appear.

## 4. Validate SFP-before-break priority

Find candles that wick through a Relevant Reaction High / Low and then reclaim the level before close.

Expected behavior:

- A wick below an active Relevant Reaction Low with a close back above it shows `SFP at Relevant Low` and does not mark that low broken on the same candle.
- A wick above an active Relevant Reaction High with a close back below it shows `SFP at Relevant High` and does not mark that high broken on the same candle.
- Only a clean close beyond the buffered level, without reclaim, marks the level broken.

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

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP0, TP1 / TP2 / TP3, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, Fibonacci, FVG, Volume Profile, CVD, AVWAP, or Moon cycle module should be added in v0.4.3.

## 8. Future work

Only after relevant level lifecycle and broken-level behavior are visually trusted should future versions revisit trade qualification, paper trading, testnet work, or advanced context modules.
