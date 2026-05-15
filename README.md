# Range SFP Hedge Bot

Version: **0.4.5**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.4.5 is a diagnostic release that keeps Relevant High / Low SFP logic strict while showing which source created each SFP level.

## Main purpose of v0.4.5

Version 0.4.5 helps identify which Relevant/SFP sources are useful and which ones are noise:

- SFP labels include their source, such as `SFP High · 4H`, `SFP Low · W Body`, `SFP High · LTF`, or `SFP Low · Range`.
- Dashboard `Nearest Active Relevant` shows side, price, and source, such as `Low 78695 · W Body`.
- Dashboard `Last Relevant Event` uses source-aware text for SFPs, such as `SFP Low · W Body` or `SFP High · 4H`.
- HTF and D/W/M body sources are enabled by default for SFP signals.
- LTF, Range, and Body Cluster sources are still created for diagnostics but are disabled by default for active SFP signals.

## Tracked Relevant/SFP sources

Relevant levels store the source that produced them:

- `1H Swing High / Low`
- `4H Swing High / Low`
- `8H Swing High / Low`
- `12H Swing High / Low`
- `1D Swing High / Low`
- `Daily Body High / Low`
- `Weekly Body High / Low`
- `Monthly Body High / Low`
- `LTF Swing High / Low`
- `Range High / Low`
- `Body High Cluster / Body Low Cluster`

Short labels use compact source names: `1H`, `4H`, `8H`, `12H`, `1D`, `D Body`, `W Body`, `M Body`, `LTF`, `Range`, and `Body Cluster`.

## Source filter defaults

Defaults are intentionally clean:

- `allowHtfSfpLevels = true`
- `allowDwmBodySfpLevels = true`
- `allowLtfSfpLevels = false`
- `allowRangeSfpLevels = false`
- `allowBodyClusterSfpLevels = false`
- `showDisabledSfpSources = false`

When disabled, LTF / Range / Body Cluster SFP candidates do **not** print active SFP labels and do **not** update `Last Relevant Event`. If `showDisabledSfpSources = true`, muted diagnostic labels can appear, such as `Disabled SFP High · LTF` or `Disabled SFP Low · Range`.

## Relevant SFP lifecycle

Active Relevant Reaction Low:

- Valid Bull SFP: current low sweeps below the level and current close reclaims above it.
- Clean break: if no reclaim occurs and price closes below the buffered level, it becomes `Broken Relevant Low`.
- No touch or sweep means no relevant-level event.

Active Relevant Reaction High:

- Valid Bear SFP: current high sweeps above the level and current close reclaims below it.
- Clean break: if no reclaim occurs and price closes above the buffered level, it becomes `Broken Relevant High`.
- No touch or sweep means no relevant-level event.

Broken/past relevant levels do not create active SFP labels.

## Clean break defaults

Clean breaks use close-based buffered logic by default:

- `cleanBreakCloseRequired = true`
- `cleanBreakAtrBuffer = 0.3`
- `cleanBreakUsdBuffer = 100`

Wick-through-and-reclaim candles are treated as SFPs first and do not break the relevant level on the same candle.

## Dashboard

Compact dashboard shows:

- Version: v0.4.5
- Market Mode
- EMA Bias
- HTF Context
- Nearest Active Relevant
- Last Relevant Event

`Nearest Active Relevant` includes side, price, and source. `Last Relevant Event` includes the SFP side and source for allowed SFP sources.

## What v0.4.5 deliberately does not do

This version does **not** try to trade.

- It does **not** draw Entry.
- It does **not** draw SL.
- It does **not** draw TP or TP0.
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
