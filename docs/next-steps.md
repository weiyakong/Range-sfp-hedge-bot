# Next Steps

Version: **0.3.7**

This project should be tested slowly and visually before any automation is considered.

## 1. Test visually on BTC

Add the Pine Script indicator to a BTC chart in TradingView. Review multiple timeframes and different market conditions, especially BTC 15m because the v0.3.7 structure defaults are tuned for visual testing there.

## 2. Use the v0.3.7 qualification order

Review setups in this order:

1. Context first: Market Mode, EMA bias, impulse direction, volatility, and nearby wick/body D/W/M context.
2. Decision zone second: fresh D/W/M wick/body level, frozen validated structure level, fresh swing level, or consolidation reaction zone.
3. Structure validation third: confirm the trigger level existed before the sweep candle and was validated by repeated touches, body clustering, consolidation, or a confirmed swing.
4. SFP/rejection fourth: current-bar sweep/reclaim against that already-existing fresh level.
5. Classification fifth: check trend, countertrend block, active scenario lock, retest/consumed level handling, and noise/no-structure handling.
6. Entry diagnostics sixth: diagnostics should be compact and off by default.
7. TP0/RR check seventh: make sure TP0 at 2R is not blocked by the next meaningful reaction area.
8. Final status gate last: Entry / SL / TP0 should appear only when final status is `Valid Setup`.

## 3. Compare labels with manual analysis

Do not trust labels automatically. Compare each label and dashboard status with manual chart reading.

Ask:

- Is the compact dashboard small enough and limited to Version, Market Mode, EMA Bias, Setup, Status, Trigger source, and TP0 status?
- Does Full dashboard mode show debug-only fields such as Trigger level type, Level state, Entry diag, D/W/M body, History mode, and Active scenario?
- Is the setup suppressed during `Chop / No Trade`?
- Are all countertrend SFPs in Trend mode blocked as `Countertrend / No Trade`?
- After a valid Bear SFP, are opposite Bull SFPs classified as `Pullback / No new long` until the Short scenario is invalidated?
- After a valid Bull SFP, are opposite Bear SFPs classified as `Pullback / No new short` until the Long scenario is invalidated?
- Are Entry / SL / TP0 lines absent for every No Trade, TP0 blocked, Retest, Expansion, Late, Pullback, and Noise status?
- Are rolling high/low candidates hidden unless `showStructureCandidates` is enabled?
- When candidates are shown, are they muted and debug-only?
- Are frozen Structure High / Structure Low lines created only from validated structure, not every candle?
- Did the trigger level exist before the sweep/reclaim candle?
- Are weak tiny Bull SFPs inside a bearish Trend classified as countertrend or pullback instead of valid long setups?
- Are weak tiny Bear SFPs inside a bullish Trend classified as countertrend or pullback instead of valid short setups?
- Are Daily/Weekly/Monthly body-aligned dotted levels useful as context without overwhelming the chart?
- Do consumed levels stop extending and remain hidden by default?
- In historical visual test mode, are historical plans capped and drawn only for `Valid Setup`?
- Was the candle correctly marked `Valid Setup`, `Retest / No new entry`, `Pullback / No new entry`, `Countertrend / No Trade`, `Noise / No structure`, `Expansion / Wait`, `Late Entry / No Trade`, or `TP0 blocked`?

## 4. Remember the SFP reclaim rule

Version 0.3.7 does **not** require mandatory candle-close confirmation by default. The default logic allows an intrabar sweep and reclaim/current price returning back beyond an already-existing fresh level. Pine Script uses the realtime bar's `close` value as current price.

Only enable conservative close confirmation if you intentionally want a slower confirmation mode. If the current bar is not the sweep/reclaim event, v0.3.7 should avoid drawing Entry / SL / TP0. Later behavior should be treated as retest/no-new-entry context, not a new plan.

## 5. Adjust settings

Experiment with the indicator settings:

- Dashboard mode: `Off`, `Compact`, or `Full`.
- EMA and ADX market-mode settings.
- ATR volatility and expansion settings.
- Chop compression and repeated-touch settings.
- Swing freshness and consumed-level settings.
- Same-zone clustering settings.
- Consolidation zone settings.
- TP0/SL buffer and reaction-zone distance settings.
- Maximum entry distance from trigger in R.
- Maximum entry delay bars, which should not create delayed entries.
- Maximum entry distance from trigger in USD.
- Structure lookback, minimum structure bars, minimum touches, and structure tolerance USD.
- Frozen structure level visibility.
- Structure candidate debug visibility.
- D/W/M body-aligned level visibility and Monthly body color.
- Hide-consumed-level behavior.
- Historical visual test mode and max historical plans.
- Entry diagnostic visibility, which should remain off unless actively debugging.
- `useDwmAsPrimaryTriggers` and untapped D/W/M wick/body level behavior after the first tap/sweep.
- Latest-only setup plan and max visible setup label settings.

The first values are only starting points.

## 6. Historical visual test workflow

When validating older chart sections:

1. Enable **Historical visual test mode**.
2. Confirm fresh levels extend until the exact first-touch bar.
3. Confirm consumed levels become muted instead of continuing as fresh signals.
4. Confirm only `Valid Setup` bars draw Entry / SL / TP0.
5. Confirm the number of historical plans is capped by `maxHistoricalPlans`.
6. Turn historical visual test mode back off for normal chart use to keep the display clean.

## 7. Future modules

TP0 is only a visual 2R protection reference in v0.3.7. Future execution logic should calculate TP0 as the protection price that covers fees, remaining-position stop risk, and optional slippage buffer. TP1, TP2, TP3, Runner logic, add-ons, re-entries, reversals, FVG, Volume Profile, POC, VAH, VAL, CVD, Anchored VWAP, Fibonacci, multiple-top/bottom RSI divergence, Moon cycle, and Fibonacci time studies are future modules, not part of version 0.3.7.

## 8. Keep automation out for now

No live trading, exchange connection, API keys, webhook automation, server code, or real bot execution should be added in this version. Paper trading and exchange testnets should only be considered after visual validation.
