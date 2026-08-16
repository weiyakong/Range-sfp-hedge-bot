# Time and Cross-Timeframe Contract

## Purpose

Define canonical UTC grids, rolling semantics, refined aggTrade-resolved macro boundaries, unresolved-time fallback, and cross-timeframe composition.

## Canonical time

All canonical candle boundaries use UTC half-open `[start_time,end_time)` intervals.

Fixed grid:
- 1D: UTC day
- 4H: 00/04/08/12/16/20
- 1H: hour
- 15m: :00/:15/:30/:45
- 5m: minute divisible by 5.

Rolling duration `W` ending at `t` is `[t-W,t)` and is never snapped to fixed grid. Approved rolling durations: `30m,1h,4h,12h,24h,3d`.

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
- `earliest_exact_touch`: one or more exact source-anchor-price touches exist; choose earliest `(event_time,agg_trade_id)` while preserving all touches;
- `directional_extreme`: no exact touch exists; high pivot selects maximum realized price, low pivot selects minimum realized price, and the selected extremum occurs exactly once.

If the selected directional extremum occurs multiple times, refined realized price is known but authoritative time/sequence remain null until a separate tie-break rule is explicitly approved.

A unique 5m localization window alone is not an exact event coordinate.

## LEFT/RIGHT boundary semantics

For authoritative pivot key `K` inside canonical `[B0,B1)`:
- LEFT contains ordered approved aggTrade source records `<=K`;
- RIGHT contains ordered records `>K`;
- RIGHT starts from refined pivot price as initial price state;
- pivot record volume/count is counted once, in LEFT.

Canonical fixed candle grid is unchanged.

## Higher-resolution partial boundaries

At `15m/1H/4H/1D`, partial boundary interval composes from the trade-resolved partial 5m fragment plus complete canonical 5m intervals between the 5m edge and enclosing higher-TF edge. Exact composition fails across canonical 5m gap/source incompatibility.

## Refined macro time

For a leg whose two endpoint times are resolved:
- `start_time = resolved start pivot time`
- `end_time = resolved end pivot time`
- `duration_seconds = end_time-start_time`.

Original source times/duration remain separately `source_*`.

## Unresolved-time fallback

If pivot time is unresolved, preserve all possible boundary occurrence evidence.

For possible start interval `[S0,S1)` and end interval `[E0,E1)`, fallback unambiguous interval is `[S1,E0)`.

A fixed calculation candle contributes only if its whole interval lies inside fallback interval. Expected constituent count is the number of fixed-grid slots wholly contained there, not `duration/resolution`.

If `S1 >= E0` or otherwise no fixed-grid slot is wholly contained, expected/observed counts are zero and boundary-dependent fallback metrics are null with explicit `no_unambiguous_interior` status.

## Repeated extrema

At candle calculation resolution preserve first/last/count as candle-resolution observations. At aggTrade refinement preserve all exact touches and all occurrences of a selected directional extremum with native ordering identity. Do not conflate the two.

## Retrospective availability

Macro refined/fallback boundaries remain retrospective (`available_at=null`). Historical timing does not make completed macro structure causal/live-known.
