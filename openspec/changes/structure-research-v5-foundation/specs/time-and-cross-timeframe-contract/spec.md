# Time and Cross-Timeframe Contract

## Purpose

Define canonical UTC grids, rolling semantics, exact trade-resolved macro boundaries, fallback ambiguity, and cross-timeframe composition.

## Canonical time

All canonical candle boundaries use UTC half-open `[start_time,end_time)` intervals.

Fixed grid:
- 1D: UTC day
- 4H: 00/04/08/12/16/20
- 1H: hour
- 15m: :00/:15/:30/:45
- 5m: minute divisible by 5.

Rolling duration `W` ending at `t` is `[t-W,t)` and is never snapped to fixed grid.

Approved rolling durations: `30m,1h,4h,12h,24h,3d`.

## Source timestamps vs canonical timestamps

Canonical 1m starts are exact minute-grid timestamps.

A source row with a non-minute timestamp is an anomaly, but not automatically a missing minute. A continuous 60-second sequence with stable source offset is classified separately from a true gap and may be canonicalized only under a proven source-specific rule with original timestamps preserved.

The known `+20.799s` December-2017 spot series is the required regression case.

## Macro time layers

Each macro anchor keeps separate fields for:

1. source coordinate / original bucket uncertainty;
2. 5m candidate localization;
3. exact trade time/sequence when uniquely resolved;
4. fallback refined uncertainty when exact resolution is unavailable.

These layers SHALL NOT overwrite the same time columns.

## Exact trade pivot

A macro pivot becomes temporally exact only with status `exact_unique_trade_touch`, preserving both event time and native sequence id.

A unique 5m candle alone is not exact.

For multiple exact touches, exact pivot time remains null.

## LEFT/RIGHT boundary semantics

For exact pivot key `K` inside `[B0,B1)`:

- LEFT contains ordered source records `<=K`;
- RIGHT contains ordered source records `>K`;
- RIGHT starts from pivot price as initial price state;
- pivot record volume/count is counted once, in LEFT.

Canonical fixed candle grid is unchanged.

## Higher-resolution partial boundaries

At `15m/1H/4H/1D`, the partial boundary interval is composed from:
- the trade-resolved partial 5m fragment;
- plus complete canonical 5m intervals between the 5m edge and enclosing higher-TF edge.

Exact composition fails across a canonical 5m gap/source incompatibility.

## Exact macro time

For a leg whose two endpoints are uniquely trade-resolved:

- `start_time = exact start pivot time`
- `end_time = exact end pivot time`
- `duration_seconds = end_time-start_time`.

Original source times/duration remain separately `source_*`.

## Ambiguous fallback

If exact pivot time is unavailable, preserve all possible touch/candidate evidence.

For possible start interval `[S0,S1)` and end interval `[E0,E1)`, fallback unambiguous interval is `[S1,E0)`.

A fixed calculation candle contributes only if its whole interval lies inside the fallback interval.

Expected constituent count is the number of fixed-grid slots wholly contained in the fallback interval. Off-grid boundaries SHALL NOT use naive `duration/resolution`.

## Repeated extrema

At candle calculation resolution preserve first/last/count as candle-resolution observations.

At trade refinement preserve every exact anchor-price touch with native ordering identity. Do not conflate the two.

## Retrospective availability

Macro exact/fallback boundaries remain retrospective (`available_at=null`). Exact historical timing does not make completed macro structure causal/live-known.
