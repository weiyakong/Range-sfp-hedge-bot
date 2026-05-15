# Range SFP Hedge Bot

Version: **0.3.7**

Range SFP Hedge Bot is a **TradingView visual analysis project**. Version 0.3.7 stabilizes the Pine Script v5 indicator logic for visually qualifying possible Swing Failure Pattern (SFP) setups around important BTC levels before any automation is considered.

## What this project does

Version 0.3.7 is a setup qualification and level-lifecycle visualization tool. Its decision pipeline is intentionally explicit:

1. Detect active fresh levels.
2. Validate and freeze real structure levels.
3. Detect current-bar sweep/reclaim only against levels that already existed before the current candle.
4. Classify setup direction.
5. Apply market mode, trend, active scenario, and countertrend filters.
6. Apply TP0 and late-entry filters.
7. Set the final status.
8. Draw Entry / SL / TP0 only when final status is `Valid Setup`.
9. Otherwise draw only a compact diagnostic label when diagnostics are enabled.

The indicator helps visualize:

- Previous daily, weekly, and monthly wick high/low levels as clean horizontal segments.
- Previous daily, weekly, and monthly **body-aligned** high/low levels as dotted context levels, with Daily body levels in lime/light green, Weekly body levels in orange, and Monthly body levels configurable with white as the default.
- Level lifecycle states: `Fresh`, `Touched`, and `Consumed`.
- Fresh levels extending to the right until their first touch.
- Consumed levels hidden by default, with an optional capped historical visual test mode.
- Validated/frozen Structure High / Structure Low levels only after repeated touches, consolidation boundaries, or confirmed swings.
- Candidate rolling structure levels only in debug mode; candidates are not trade triggers until validated/frozen.
- Fresh swing highs and swing lows using pivot detection.
- Market Mode: `Trend`, `Range`, `Chop`, or `Expansion`.
- Compact dashboard mode by default, plus an optional full debug dashboard.
- Strict `Chop / No Trade`, `Countertrend / No Trade`, `Pullback / No new entry`, `Noise / No structure`, `Retest / No new entry`, `Late Entry / No Trade`, and `TP0 blocked` classification.
- Active scenario classification: a valid Bear SFP locks a Short scenario, and a valid Bull SFP locks a Long scenario until invalidation.
- Entry, SL, and TP0 lines only when the final status is exactly `Valid Setup`.
- Event-based SFP detection: a new setup requires the current bar itself to sweep and reclaim an already-existing fresh trigger level.
- D/W/M levels remain context-only by default with `useDwmAsPrimaryTriggers = false`.
- Weakening-push / exhaustion clues shown as quality context only, without requiring them as a signal condition.

## Level and structure model

Version 0.3.7 does **not** treat every rolling high or low as structure. A Structure High / Structure Low must be frozen before it can be used as an SFP trigger. A structure candidate becomes valid only when it has sufficient quality, such as repeated high/body-high or low/body-low touches, a consolidation top/bottom, or a confirmed swing. The level must already exist before the sweep/reclaim candle.

By default, consumed levels are hidden to reduce chart noise. Enable **Historical visual test mode** only when reviewing older chart sections; historical plans are capped by `maxHistoricalPlans` and still respect the final status gate.

## TP0 terminology

`TP0` is the protection point. In this visual version, TP0 is shown at **2R** from the planned entry so setups can be reviewed consistently.

In a future execution bot, TP0 should be calculated as the protection price where closing 50% of the position covers full trading fees, the potential stop loss on the remaining position, and an optional slippage buffer. TP0 is not meant to be a normal profit target; it is the position protection point.

TP1, TP2, TP3, Runner logic, add-ons, reversals, re-entries, and countertrend scalp mode are **not included**.

## SFP reclaim logic

Version 0.3.7 does **not** require mandatory candle-close confirmation by default. The default logic is based on an intrabar sweep and reclaim/current price returning back beyond an already-existing fresh level. In Pine Script, the realtime bar's `close` value represents the current price.

A conservative candle-close confirmation option exists in the indicator settings, but it is not the default. Old sweeps and later retests do not create new Entry / SL / TP0 plans.

## What this project does not do

This version is intentionally visual-only.

- It does **not** place trades.
- It does **not** connect to any crypto exchange.
- It does **not** use API keys.
- It does **not** run a live trading bot.
- It does **not** add webhook automation.
- It does **not** add server code.
- It does **not** provide financial advice.

## Planned future modules

Future versions may explore additional analysis modules after visual testing:

- TP1, TP2, TP3, and Runner handling.
- Add-on logic.
- Reversal logic.
- Countertrend scalp mode.
- FVG.
- Volume Profile, POC, VAH, and VAL.
- CVD.
- Anchored VWAP.
- Fibonacci.
- Multiple-top/bottom RSI divergence.
- Moon cycle and Fibonacci time studies.
- Paper trading tools after validation.
- Exchange testnet experiments only after validation.

Real exchange execution is not part of version 0.3.7.

## Risk warning

Trading crypto is risky. SFP setups can fail, levels can break, and fast markets can move against a position quickly. Never risk more than you can afford to lose. Any future trading system should use strict risk management, and risk per trade should remain small.
