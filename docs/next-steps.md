# Next Steps

Version: **0.4.5**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Validate source-aware SFP labels

Open BTC on a 15m chart and find active Relevant Reaction High / Low lines.

Expected behavior:

- Allowed active HTF SFP labels show short source text, such as `SFP High · 4H`, `SFP Low · 8H`, or `SFP High · 1D`.
- Allowed active D/W/M body SFP labels show body source text, such as `SFP Low · W Body` or `SFP High · D Body`.
- Labels stay short and do not use the old generic `SFP at Relevant High / Low` label text.

## 2. Validate source filter defaults

Defaults are:

- `allowHtfSfpLevels = true`
- `allowDwmBodySfpLevels = true`
- `allowLtfSfpLevels = false`
- `allowRangeSfpLevels = false`
- `allowBodyClusterSfpLevels = false`
- `showDisabledSfpSources = false`

With defaults, LTF / Range / Body Cluster SFP candidates may still exist as diagnostic relevant levels, but they should not print active SFP labels and should not update `Last Relevant Event`.

## 3. Validate disabled source diagnostics

Turn on `showDisabledSfpSources = true` only for debugging.

Expected muted labels:

- `Disabled SFP High · LTF`
- `Disabled SFP Low · Range`
- `Disabled SFP High · Body Cluster`

These muted labels are diagnostic only and should not update `Last Relevant Event`.

## 4. Validate SFP-before-break priority

Find candles that wick through a Relevant Reaction High / Low and then reclaim the level before close.

Expected behavior:

- A wick below an active Relevant Reaction Low with a close back above it shows an allowed source-aware low SFP label and does not mark that low broken on the same candle.
- A wick above an active Relevant Reaction High with a close back below it shows an allowed source-aware high SFP label and does not mark that high broken on the same candle.
- Only a clean close beyond the buffered level, without reclaim, marks the level broken.

## 5. Validate dashboard source fields

Compact dashboard should show:

- Version v0.4.5
- Market Mode
- EMA Bias
- HTF Context
- Nearest Active Relevant
- Last Relevant Event

`Nearest Active Relevant` should include side, price, and source, for example `Low 78695 · W Body` or `High 81930 · 4H`. `Last Relevant Event` should include source-aware SFP text, for example `SFP Low · W Body`, `SFP High · 4H`, or `SFP High · LTF` only when that source is allowed.

## 6. Validate broken relevant levels

After a Relevant Reaction Low breaks downward:

- Later candles do not show allowed `SFP Low · source` labels from that broken low.

After a Relevant Reaction High breaks upward:

- Later candles do not show allowed `SFP High · source` labels from that broken high.

## 7. Keep automation and extra modules out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP / TP0, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, front-run reaction, reaction-near-level logic, Fibonacci, FVG, Volume Profile, CVD, AVWAP, or Moon cycle module should be added in v0.4.5.

## 8. Future work

Only after source diagnostics show which level families produce useful SFPs should future versions revisit source defaults, trade qualification, paper trading, testnet work, or advanced context modules.
