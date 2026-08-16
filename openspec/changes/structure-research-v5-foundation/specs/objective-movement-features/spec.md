# Objective Movement Features Specification

## Purpose

Define objective measurement families for Structure Research v5 without classifying impulse/correction/range/chop/Elliott/Fibonacci states.

## Macro source as retrospective container

Approved `macro_legs_log20` boundaries/direction/prices remain source research containers, not validated hierarchy.

Historical macro provenance remains separate from current canonical market assignment.

## Macro boundary refinement

The approved 5m localization artifact covers all 138 macro pivots (131 unique 5m, 7 multiple 5m). Before exact macro metrics are assigned, all candidate 5m intervals are refined with same-market official trade evidence.

A 5m match is not treated as an exact pivot. Exact pivot requires one exact anchor-price touch with deterministic native sequence identity.

Multiple touches remain explicit ambiguity.

## Exact vs fallback macro measurement

For a trade-resolved leg:
- exact endpoints/timing/duration/speed use trade pivots;
- macro TF close-path uses exact pivot price plus canonical close sequence at each calculation resolution;
- LEFT/RIGHT boundary fragment microstructure is stored separately;
- exact macro volume/activity uses boundary fragments plus complete interior intervals without double counting.

For ambiguous leg boundaries:
- exact duration/speed/boundary-inclusive metrics remain null;
- only fallback unambiguous constituents are aggregated.

## Speed

Collect signed/log/local-direction speed and rolling speed-change/acceleration numerically.

Whole-leg macro speed is one endpoint-to-endpoint value when exact. TF-specific measurements describe internal evolution.

## Path/activity

Preserve:
- net displacement
- close/log path
- efficiency
- directional path components
- alternation
- extrema
- candle activity.

Trade-level boundary path is separate `trade_*` microstructure and never added to TF close-path.

## Candle and pair geometry

Materialize complete candle range/body/wicks/log geometry and neutral pair overlap/penetration/extension. Boundary fragment pair relationships remain explicitly typed.

## Retracement

First-pass retracement means the following opposite-direction macro leg relative to the immediately preceding macro leg when they share one pivot.

The approved source yields 118 such adjacent relationships.

Store direct percentage retracement only; no Fibonacci conversion.

## Volume/volatility

Preserve source-accurate volume, directional volume systems, TR/ATR, fixed/rolling RV and numeric range/compression components.

Exact macro volume/activity may include boundary fragments; macro RV remains deferred.

## Scope guard

Do not construct a new internal swing hierarchy, parent impulse, impulse/correction labels, range/breakout/chop labels, Fib/FibTime, or Elliott labels in this pass.

Later internal-leg/correction candidates may use the same trade-boundary refinement method after the first macro analysis identifies which boundaries merit tick/trade refinement.
