# Next Steps

Version: **0.4.0**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Test the multi-timeframe level model

Open BTC on a 15m chart, but evaluate whether the indicator is pulling the important levels from higher timeframes:

- 4H Swing High / 4H Swing Low
- 8H Swing High / 8H Swing Low
- 12H Swing High / 12H Swing Low
- 1D Swing High / 1D Swing Low
- Optional 1H Swing High / 1H Swing Low as medium structure

15m should be treated as the reaction layer, not the primary source of important levels.

## 2. Validate active vs past behavior

Review whether active levels:

- extend right while untouched;
- stop extending after price touches, sweeps, trades through, or displaces through them;
- become muted Past Swing High / Past Swing Low visual context;
- stop acting as fresh reaction levels after consumption.

Strong displacement candles or sequences should consume crossed levels quickly, especially old 15m/LTF minor swings.

## 3. Validate swing scale classification

Check whether swings are classified sensibly:

- HTF 4H / 8H / 12H / 1D levels should usually be more important than 15m levels.
- 1H levels should behave as medium intraday structure.
- 15m swings inside overlap/chop should usually be Minor Swing or Micro Swing.
- Micro swings should be hidden by default with `showMicroSwings = false`.

## 4. Validate 15m reactions around HTF levels

A 15m reaction should be meaningful only near:

- an HTF swing level;
- a D/W/M body-aligned level;
- a major structure level.

Expected reaction labels include:

- `Rejection at HTF level`
- `SFP candidate at HTF level`
- `Retest`
- `Reclaim at HTF level`
- `Minor reaction / ignore`
- `Micro Chop`

A 15m SFP-like move in the middle of nowhere should be ignored or classified as minor context, not promoted to an active scenario.

## 5. Validate MTF context

Use the compact dashboard to check:

- Version
- Market Mode
- EMA Bias
- HTF Context
- Active Scenario
- Nearest HTF Level
- Last Structure Event

Use Full dashboard mode only when debugging nearest 4H/8H/12H/1D levels, current 15m reaction, swing scale, and impulse/chop context.

## 6. Keep visual clarity

Default clutter controls should remain:

- `showHTFLevels = true`
- `showLTFSwings = true`
- `showMicroSwings = false`
- `showPastSwingLevels = true`
- `showReactionLabels = true`
- `showDebugLabels = false`
- `showOrdinaryDwmHighLowLevels = false`
- `dashboardMode = Compact`

Important labels should be few and readable. The indicator should not cover the chart.

## 7. Keep automation out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP0, TP1 / TP2 / TP3, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, FVG, Volume Profile, CVD, AVWAP, Fibonacci, or Moon cycle module should be added in v0.4.0.

## 8. Future work

Only after the MTF visual context is trusted should future versions revisit trade qualification, paper trading, testnet work, or advanced context modules.
