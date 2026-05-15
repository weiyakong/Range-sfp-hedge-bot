# Next Steps

Version: **0.4.4**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Validate active relevant-level SFP only

Open BTC on a 15m chart and find active Relevant Reaction High / Low lines.

Expected behavior:

- An active Relevant Reaction Low prints `SFP at Relevant Low` only when the current candle sweeps below it and closes back above it.
- An active Relevant Reaction High prints `SFP at Relevant High` only when the current candle sweeps above it and closes back below it.
- Levels that are not touched or swept produce no relevant-level label.
- Broken or past relevant levels do not create SFP labels.

## 2. Validate clean break settings

Defaults are:

- `cleanBreakCloseRequired = true`
- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`

With close-based lifecycle logic, a Relevant Reaction Low should break when price closes below the level by the USD/ATR buffer and does not reclaim. A Relevant Reaction High should break when price closes above the level by the USD/ATR buffer and does not reclaim.

## 3. Validate SFP-before-break priority

Find candles that wick through a Relevant Reaction High / Low and then reclaim the level before close.

Expected behavior:

- A wick below an active Relevant Reaction Low with a close back above it shows `SFP at Relevant Low` and does not mark that low broken on the same candle.
- A wick above an active Relevant Reaction High with a close back below it shows `SFP at Relevant High` and does not mark that high broken on the same candle.
- Only a clean close beyond the buffered level, without reclaim, marks the level broken.

## 4. Validate broken relevant levels

After a Relevant Reaction Low breaks downward:

- Later candles do not show `SFP at Relevant Low` from that broken low.
- The broken low does not create an actionable relevant-level event.

After a Relevant Reaction High breaks upward:

- Later candles do not show `SFP at Relevant High` from that broken high.
- The broken high does not create an actionable relevant-level event.

## 5. Validate nearest relevant dashboard field

Compact dashboard should show:

- Version v0.4.4
- Market Mode
- EMA Bias
- HTF Context
- Nearest active Relevant Level
- Last Relevant Event

Nearest active Relevant Level should ignore broken/past levels. It should only consider active Relevant Reaction Lows below price and active Relevant Reaction Highs above price. If none exist, it should show `None`.

## 6. Validate quiet label cleanup

The chart should show only the relevant-level labels needed for this pass:

- `SFP at Relevant Low`
- `SFP at Relevant High`

`Last Relevant Event` should be only `SFP at Relevant Low`, `SFP at Relevant High`, `Broken Relevant Low`, `Broken Relevant High`, or `None`.

## 7. Keep automation and extra modules out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP0, TP1 / TP2 / TP3, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, front-run reaction, reaction-near-level logic, Fibonacci, FVG, Volume Profile, CVD, AVWAP, or Moon cycle module should be added in v0.4.4.

## 8. Future work

Only after active Relevant High / Low SFP behavior is visually trusted should future versions revisit trade qualification, paper trading, testnet work, or advanced context modules.
