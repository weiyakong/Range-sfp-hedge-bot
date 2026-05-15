# Next Steps

Version: **0.3.8**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Test only structure and levels

Add the Pine Script indicator to a BTC chart in TradingView. Use BTC 15m first because the v0.3.8 defaults are tuned for that visual review.

Do **not** evaluate entries, stops, TP0, TP1, TP2, TP3, runners, add-ons, reversals, or countertrend scalp logic in this version. They are intentionally absent.

## 2. Validate the v0.3.8 visual layers

Review these layers manually:

1. Fresh Swing High / Swing Low levels.
2. Validated/frozen Structure High / Structure Low levels.
3. Daily / Weekly / Monthly body-aligned levels.
4. Optional ordinary D/W/M wick high/low context levels.
5. Lower High / Higher Low / Retest / Structure reaction / Possible continuation labels.
6. Bear SFP candidate / Bull SFP candidate labels.
7. Compact dashboard status.

## 3. Structure checklist

Ask these questions while reviewing historical and live candles:

- Did the indicator avoid marking every tiny candle as a swing?
- Did fresh swing levels extend right until touched?
- Were consumed levels hidden by default?
- If `showConsumedLevels` is enabled, were consumed levels very muted?
- Did local structure require at least two touches/reactions, repeated body levels, a consolidation boundary, or a confirmed swing?
- Did the script avoid creating a new Structure High / Structure Low on every candle?
- Once a structure level appeared, did it freeze and extend right instead of moving every candle?
- Was a Bear/Bull SFP shown only as a candidate label, never as a trade plan?
- Did the SFP candidate level already exist before the sweep/reclaim candle?
- Did the dashboard remain compact and avoid covering the chart?

## 4. Defaults to verify

These settings should be off by default to reduce clutter:

- `showEntryDiagnostics = false`
- `historicalVisualTestMode = false`
- `showStructureCandidates = false`
- `showConsumedLevels = false`
- `showOrdinaryDwmHighLowLevels = false`

The default dashboard mode should be `Compact`.

## 5. Settings to tune

After basic visual validation, experiment with:

- `swingLength`
- `minSwingProminenceAtr`
- `minStructureBars`
- `minStructureTouches`
- `structureToleranceUsd`
- `structureLookback`
- `consolidationLookback`
- `consolidationMaxAtrRange`
- `levelCooldownBars`
- `showConsumedLevels`
- `showStructureCandidates`
- `dashboardMode`

The first goal is alignment with human-marked levels, not signal generation.

## 6. Keep automation out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, or strategy orders should be added in v0.3.8.

## 7. Future work

Only after the structure visualizer is trusted should future versions revisit trade qualification, TP0, TP1/TP2/TP3, runners, add-ons, reversals, countertrend scalp mode, FVG, Volume Profile, CVD, AVWAP, Fibonacci, Moon cycle, or any paper-trading/testnet work.
