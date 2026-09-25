# Time and Cross-Timeframe Contract

## Purpose

Define canonical UTC grids, rolling semantics, refined aggTrade-resolved macro boundaries, unresolved-time fallback, and cross-timeframe composition.

## Canonical time

All canonical candle boundaries use UTC half-open `[start_time,end_time)` intervals.

Fixed grid:
- 1D: UTC day
- 12H: 00/12
- 4H: 00/04/08/12/16/20
- 1H: hour
- 15m: :00/:15/:30/:45
- 5m: minute divisible by 5.

Rolling duration `W` ending at `t` is `[t-W,t)` and is never snapped to fixed grid. Approved rolling durations: `30m,1h,4h,12h,24h,3d`.

The primary first-pass macro-signature research resolutions are `1D`, `12H`, and `4H`. These are parallel representations of the same approved historical macro segments; no one of them is assumed to be the true structural timeframe in advance.

`1W` is not part of the primary fixed-grid research set in the first pass. It may be added later as an optional coarse-context/robustness resolution for sufficiently long macro segments if there are enough weekly observations to support meaningful analysis.

## Source timestamps vs canonical timestamps

Canonical 1m starts are exact minute-grid timestamps. A continuous 60-second series with stable source offset is distinct from a true gap and may be canonicalized only under a proven source-specific rule with original timestamps preserved. The known +20.799s December-2017 spot series is the required regression case.

## Macro time layers

Each macro anchor keeps separate fields for:
1. source coordinate/original bucket uncertainty;
2. reviewed candidate localization windows;
3. refined realized pivot price;
4. resolved aggTrade event time/sequence when deterministic;
5. unresolved-time bounds/fallback evidence when not deterministic.

These layers SHALL NOT overwrite the same columns.

## Candidate-window semantics

Every reviewed localization candidate is scanned as half-open `[candidate_start,candidate_start+5m)`, including known off-grid source-localization candidates. Historical `.999` end representations are provenance only.

## Refined aggTrade pivot

A macro pivot becomes temporally resolved when approved aggTrade refinement yields one authoritative ordering key under either approved method:
- `unique_exact_touch`: exactly one exact source-anchor-price aggTrade touch exists with complete approved coverage;
- `directional_extreme`: no exact touch exists; high pivot selects maximum realized price, low pivot selects minimum realized price, and the selected extremum occurs exactly once.

If two or more exact source-anchor-price touches exist, refined realized price is known but authoritative time/sequence remain null under status `repeated_exact_trade_touch`. Preserve the ordered evidence plus first touch, last touch, touch count and touch span. Do not silently select first, midpoint/average or last touch as the authoritative pivot.

If the selected directional extremum occurs multiple times, refined realized price is known but authoritative time/sequence remain null until a separate tie-break rule is explicitly approved.

A unique 5m localization window alone is not an exact event coordinate.

## LEFT/RIGHT boundary semantics

For authoritative pivot key `K` inside canonical `[B0,B1)`:
- LEFT contains ordered approved aggTrade source records `<=K`;
- RIGHT contains ordered records `>K`;
- RIGHT starts from refined pivot price as initial price state;
- pivot record volume/count is counted once, in LEFT.

Canonical fixed candle grid is unchanged.

Repeated exact-touch and repeated selected-extremum cases have no authoritative key `K`, so no exact LEFT/RIGHT boundary split is created for them.

## Higher-resolution partial boundaries

At `15m/1H/4H/12H/1D`, partial boundary interval composes from the trade-resolved partial 5m fragment plus complete canonical 5m intervals between the 5m edge and enclosing higher-TF edge. Exact composition fails across canonical 5m gap/source incompatibility.

## Refined macro time

For a leg whose two endpoint times are resolved:
- `start_time = resolved start pivot time`
- `end_time = resolved end pivot time`
- `duration_seconds = end_time-start_time`.

Original source times/duration remain separately `source_*`.

## Unresolved-time fallback

If pivot time is unresolved, preserve all possible boundary occurrence evidence.

For possible start interval `[S0,S1)` and end interval `[E0,E1)`, fallback unambiguous interval is `[S1,E0)`.

For a repeated exact-touch episode, first and last exact source touches provide descriptive bounds on the possible event interval when no broader source uncertainty applies. They are not an authoritative pivot selection.

A fixed calculation candle contributes only if its whole interval lies inside fallback interval. Expected constituent count is the number of fixed-grid slots wholly contained there, not `duration/resolution`.

If `S1 >= E0` or otherwise no fixed-grid slot is wholly contained, expected/observed counts are zero and boundary-dependent fallback metrics are null with explicit `no_unambiguous_interior` status.

## Repeated extrema / repeated exact touches

At candle calculation resolution preserve first/last/count as candle-resolution observations. At aggTrade refinement preserve all exact touches and all occurrences of a selected directional extremum with native ordering identity. Do not conflate the two.

Research-only boundary sensitivity analysis may compare results under first-touch and last-touch bounds, but neither bound becomes the canonical timestamp without a separate approved rule.

## Retrospective availability

Macro refined/fallback boundaries remain retrospective (`available_at=null`). Historical timing does not make completed macro structure causal/live-known.
