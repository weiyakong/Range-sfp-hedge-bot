# Next Steps

Version: **0.3.4**

This project should be tested slowly and visually before any automation is considered.

## 1. Test visually on BTC

Add the Pine Script indicator to a BTC chart in TradingView. Review multiple timeframes and different market conditions.

## 2. Use the v0.3.4 qualification order

Review setups in this order:

1. Context first: Market Mode, EMA bias, impulse direction, and volatility.
2. Decision zone second: D/W/M level, fresh swing level, or consolidation reaction zone.
3. SFP/rejection third: sweep/reclaim or failed reclaim at the decision zone.
4. TP0/RR check fourth: make sure TP0 at 2R is not blocked by the next meaningful reaction area.

## 3. Compare labels with manual analysis

Do not trust labels automatically. Compare each label and dashboard status with manual chart reading.

Ask:

- Is the dashboard showing `Trend`, `Range`, `Chop`, or `Expansion` correctly?
- Is the setup suppressed during `Chop / No Trade`?
- Is the signal with trend or countertrend?
- If countertrend, is there strong rejection and structure weakness/strength?
- Did the trigger-level line match the level you expected?
- Is TP0 at 2R realistic before the next meaningful reaction area?
- Is the planned entry still close to the actual swept/reclaimed trigger level?
- Did the indicator use only untapped D/W/M levels and avoid repeating consumed D High / D Low labels?
- Did it choose Swing High / Swing Low or Local High / Local Low when that was the real SFP trigger instead of a nearby D/W/M level?
- Did any `Weak push` clue appear only as extra quality context rather than as a required signal?
- Was the candle marked `Ambiguous / No Trade`, `Countertrend / No Trade`, `Expansion / Wait`, `Late Entry / No Trade`, `Missed / Too Late`, or `No Trade / TP0 blocked`?

## 4. Remember the SFP reclaim rule

Version 0.3.4 does **not** require mandatory candle-close confirmation by default. The default logic allows an intrabar sweep and reclaim/current price returning back beyond the level. Pine Script uses the realtime bar's `close` value as current price.

Only enable conservative close confirmation if you intentionally want a slower confirmation mode. If the current bar is not the sweep/reclaim event, v0.3.4 should avoid drawing Entry / SL / TP0. Later behavior should be treated as retest/no-new-entry context, not a new plan.

## 5. Adjust settings

Experiment with the indicator settings:

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
- Local liquidity lookback and local-trigger near-zone settings.
- Untapped D/W/M level behavior after the first tap/sweep.
- Latest-only setup plan and max visible setup label settings.

The first values are only starting points.

## 6. Future modules

TP0 is only a visual 2R protection reference in v0.3.4. Future execution logic should calculate TP0 as the protection price that covers fees, remaining-position stop risk, and optional slippage buffer. TP1, TP2, TP3, and Runner logic are future modules. FVG, Volume Profile, POC, VAH, VAL, CVD, Anchored VWAP, Fibonacci, and multiple-top/bottom RSI divergence, Moon cycle, and Fibonacci time studies are also planned future modules, not part of version 0.3.4.

## 7. Keep automation out for now

No live trading, exchange connection, API keys, webhook automation, server code, or real bot execution should be added in this version. Paper trading and exchange testnets should only be considered after visual validation.
