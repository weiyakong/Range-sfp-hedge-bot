# Objective Movement Features Specification

## Purpose

Define objective measurement families for Structure Research v5 without classifying impulse/correction/range/chop/Elliott/Fibonacci states.

## Macro source as retrospective container

Approved `macro_legs_log20` boundaries/direction/prices remain source research containers, not validated hierarchy. Historical macro provenance remains separate from current canonical market assignment.

## Macro boundary refinement

The approved 5m localization artifact covers all 138 macro pivots across 145 candidate windows. Before refined macro metrics are assigned, all candidate intervals are processed with same-market official Binance `aggTrades` only.

A 5m localization match is not an exact event coordinate.

Refinement rule:
- preserve all exact source-anchor-price aggTrade touches;
- if exact touches exist, select the earliest by `(event_time,agg_trade_id)`;
- if no exact touch exists, high pivot selects the maximum realized aggTrade price and low pivot selects the minimum realized aggTrade price;
- preserve every occurrence of the selected extremum;
- a unique selected extremum resolves price/time/id;
- repeated selected extremum preserves price but leaves authoritative time/id unresolved until a separately approved tie-break rule exists.

## Refined vs fallback macro measurement

For a leg whose two endpoint times are deterministically resolved:
- refined endpoints/timing/duration/speed use refined realized pivots;
- macro TF close-path uses refined pivot prices plus canonical close sequence at each calculation resolution;
- LEFT/RIGHT boundary fragment microstructure is stored separately;
- refined macro volume/activity uses boundary fragments plus complete interior intervals without double counting.

For unresolved-time boundaries:
- exact duration/speed/boundary-inclusive metrics remain null;
- only guaranteed fallback constituents are aggregated;
- if no guaranteed interior constituent exists, boundary-dependent fallback metrics are null with explicit status.

## Speed

Collect signed/log/local-direction speed and rolling speed-change/acceleration numerically. Whole-leg macro speed is one endpoint-to-endpoint value when both endpoint times resolve. TF-specific measurements describe internal evolution.

## Path/activity

Preserve net displacement, close/log path, efficiency, directional path components, alternation, extrema and candle activity. Trade-level boundary path is separate `trade_*` microstructure and never added to TF close-path.

## Candle and pair geometry

Materialize complete candle range/body/wicks/log geometry and neutral pair overlap/penetration/extension using the explicit formulas in `price-path-speed-and-overlap/spec.md`. Boundary-fragment pair relationships remain explicitly typed.

## Volume/volatility

Preserve source-accurate volume, directional volume systems, both `atr14_sma` and `atr14_wilder`, fixed/rolling RV and numeric range/compression components. Exact macro volume/activity may include boundary fragments; macro RV remains deferred.

## Bounded source access

Candidate refinement and fragment construction must use bounded aggTrade access. Per-anchor/per-fragment code may not repeatedly parse whole day/month archives. Fragment construction reads only the required canonical 5m bucket through robust streaming/range-filtered access; parser failure is explicit and never triggers raw-trade fallback.

## Retracement

First-pass retracement means the following opposite-direction macro leg relative to the immediately preceding macro leg when they share one pivot. Approved source yields 118 relationships. Store direct percentage retracement only; no Fibonacci conversion.

## Scope guard

Do not construct a new internal swing hierarchy, parent impulse, impulse/correction labels, range/breakout/chop labels, Fib/FibTime, or Elliott labels in this pass.
