# Next Steps

Version: **0.4.1**

This project should be tested slowly and visually before any automation or trade-plan logic is considered.

## 1. Validate Relevant Reaction Levels first

Open BTC on a 15m chart and check whether the indicator preserves old horizontal levels that caused strong reactions.

Look for:

- Relevant Reaction High after price moves down strongly from an old high/body/range level.
- Relevant Reaction Low after price moves up strongly from an old low/body/range level.
- Few labels, not a stream of minor ignored reactions.
- Old important levels extending right for later retests.

## 2. Verify the reaction strength filter

Defaults are:

- `reactionLookaheadBars = 24`
- `reactionMinUsd = 700`
- `reactionMinAtr = 3.0`
- `reactionMinPercent = 0.7`

A level should become relevant only if the reaction away from it is meaningful. Levels where price moved only 100–300 USD should usually stay silent.

## 3. Verify future interactions

When price later returns to a Relevant Reaction High / Low, the indicator may show only compact labels:

- `Reaction at Relevant Level`
- `SFP candidate at Relevant Level`

It should not draw Entry, SL, TP0, or any trade plan.

If price cleanly breaks through a relevant level and `keepRelevantLevelAfterCleanBreak = false`, the level should become inactive/muted.

## 4. Verify old swing vs relevant level distinction

Past Swing High / Past Swing Low:

- muted;
- historical context only;
- not extended as a fresh reaction level.

Relevant Reaction High / Relevant Reaction Low:

- proved itself through a strong reaction;
- remains extended right;
- can be watched for future reaction/SFP candidates.

## 5. Confirm noise defaults

These settings should keep the chart quiet by default:

- `showRelevantReactionLevels = true`
- `showPastSwingLevels = true`
- `showMinorReactionLabels = false`
- `showMicroSwingLabels = false`
- `showDebugLabels = false`
- `showStructureCandidates = false`
- `showOrdinaryDwmHighLowLevels = false`
- `dashboardMode = Compact`

The chart should not show `Minor reaction / ignore` labels unless explicitly enabled.

## 6. Validate MTF context without clutter

The existing HTF context can remain, but it should not be the noisy part of the indicator. Use Full dashboard only for debugging nearest 4H/8H/12H/1D levels and impulse/chop context.

Compact dashboard should show:

- Version
- Market Mode
- EMA Bias
- HTF Context
- Nearest Relevant Level
- Last Relevant Event

If there is no important event, Last Relevant Event should remain `None`.

## 7. Keep automation out

No live trading, exchange connection, API keys, webhook automation, server code, real bot execution, strategy orders, Entry / SL / TP0, TP1 / TP2 / TP3, runner logic, add-ons, re-entry, reversal engine, countertrend scalp mode, FVG, Volume Profile, CVD, AVWAP, Fibonacci, or Moon cycle module should be added in v0.4.1.

## 8. Future work

Only after relevant reaction levels are visually trusted should future versions revisit trade qualification, paper trading, testnet work, or advanced context modules.
