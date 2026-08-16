# Research Table Schema Contract

## Purpose

Define canonical logical tables, row grain, stable identifiers, joins, availability classes, refined/fallback macro-boundary semantics, and physical partitioning for Structure Research v5.

## Stable identifiers

UUIDv5 namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`.

Canonical identities include source segment, gap, candle, fixed/rolling/macro observation, canonical pair, macro anchor and retracement as previously frozen.

Add:
`macro_boundary_fragment_id = uuid5(namespace, "macro_boundary_fragment|{macro_anchor_id}|{side}|{calculation_resolution}")`.

Associated macro leg membership is a foreign-key relationship and SHALL NOT redefine fragment identity. Run id, local path, archive filename and mutable provenance do not redefine stable identity.

## Canonical refinement enums

At minimum:
- `trade_source_granularity=agg_trade`
- refinement status: `exact_trade_touch_resolved`, `extreme_trade_price_resolved`, `repeated_extreme_trade_price`, `incomplete_trade_coverage`, `source_unavailable`, `not_attempted`
- resolution method: `earliest_exact_touch`, `directional_extreme`, `none`
- aggregate boundary precision: `single_underlying_trade`, `aggregate_boundary_indivisible`, `not_applicable`.

## Core source/candle tables

`source_segments`, `source_gaps`, `candles_1m`, `candles_fixed`, `candle_geometry`, and `cross_timeframe_map` retain the canonical contracts: strict observed 1m, explicit gaps/boundaries, derived fixed candles, exact geometry and deterministic cross-TF mapping.

## `macro_anchors`

One shared row per approved source pivot/event. Primary key `macro_anchor_id`.

Required fields:
- identity: `macro_anchor_id`, `macro_source_checksum`, `source_event_id`
- source coordinate: `source_anchor_time`, `source_anchor_price`, `source_anchor_price_units`, `anchor_extreme_type`
- anchor provenance: `source_time_precision`, source/refinement markets/timeframe, historical source classification
- source uncertainty: `source_possible_time_start/end`
- localization: status, candidate count, candidate starts/ends/kinds, localization checksum
- refinement: `trade_refinement_status`, `resolution_method`, `trade_source_granularity=agg_trade`
- exact source-price evidence: `exact_touch_count`, first/last exact-touch time
- selected realized coordinate: `resolved_pivot_price`, `resolved_pivot_price_units`, `resolved_pivot_time`, `resolved_pivot_sequence_id`
- selected-extremum evidence where applicable: `selected_extreme_occurrence_count`, first/last selected-extreme time
- canonical containment only when resolved time is non-null: `canonical_pivot_5m_start_time/end_time`
- selected pivot aggregate metadata: first/last underlying trade ids/count, aggregate precision
- unresolved-time bounds/uncertainty when applicable
- evidence/checksums
- retrospective availability and run/schema provenance.

Rules:
- exact source-anchor price touch(es) => earliest exact touch resolves pivot; preserve all exact touches;
- no exact touch => high selects maximum realized price, low selects minimum realized price;
- repeated selected extremum => realized price known but time/id null until separately approved tie-break;
- source anchor coordinate is never overwritten.

Every localization candidate is half-open `[candidate_start,candidate_start+5m)`.

## `macro_trade_touches`

One row per approved aggTrade evidence row relevant to refinement, with deterministic natural key including anchor, candidate window, event time and `agg_trade_id`.

Preserve exact price/price_units, market, aggTrade id, first/last underlying ids, event time, quantities where exact, `buyer_is_maker`, artifact/checksum and evidence role (`exact_source_price_touch`, `selected_directional_extreme`, other audited candidate as required).

Do not store reconstructed individual raw-trade rows.

## `macro_boundary_fragments`

One row per authoritative LEFT/RIGHT fragment and calculation resolution when one authoritative pivot aggTrade key exists.

Primary key `macro_boundary_fragment_id`; natural uniqueness `(macro_anchor_id,side,calculation_resolution)`.

Required: anchor id, associated leg id(s) as foreign-key context, side, resolution, market, enclosing canonical interval, resolved pivot time/id/price, fragment bounds/duration, composition method, aggregate precision, coverage/status and objective fragment OHLCV/geometry/activity where applicable.

Pivot aggTrade belongs LEFT once; RIGHT begins from pivot price state and excludes pivot row. Canonical fixed candles remain unchanged.

## Observation index / speed / path

Fixed and rolling retain canonical definitions and approved matrices.

For macro, exact start/end/duration and refined whole-leg speed exist only when both endpoint times are deterministically resolved by approved refinement. Source-coordinate movement/duration/speed remains under `source_*` fields.

Resolved macro close-path at R:
`resolved start price -> chronological complete R closes with start < candle.end <= end -> resolved end price if needed`.

AggTrade boundary path is never added to TF close path.

Fallback uses only whole fixed-grid intervals guaranteed inside unresolved boundary possibilities. If none exist: expected=observed=0, boundary-dependent fallback metrics null, explicit `no_unambiguous_interior` status.

## Atomic pairs / overlap

`atomic_candle_pairs` contains canonical same-resolution adjacent complete fixed-candle pairs only.

Resolved macro boundary-fragment relationships are separately typed. Macro overlap sequence is non-overlapping `start RIGHT fragment -> complete interior intervals -> end LEFT fragment`, with exact formulas and aggregation defined in `price-path-speed-and-overlap/spec.md`. Never include full boundary candle plus its fragment.

## Volume/volatility

`observation_volume_volatility` materializes both:
- `atr14_sma`
- `atr14_wilder`.

TR requires valid adjacent previous close inside the same resolution/source segment. Continuity breaks reset both ATRs; 14 new consecutive valid TRs are required. In fallback, previous close outside guaranteed interval is forbidden.

Macro RV remains deferred.

## Retracement

`retracement_measurements` contains exactly the approved adjacent opposite-direction shared-pivot relationships A->B->C. A/B/C are macro anchor foreign keys. Expected production count 118; 9 discontinuous adjacent transitions excluded. No Fibonacci labels.

## Feature dictionary / extraction safety

Every materialized feature has one definition including formula, units, applicability, calculation resolution, availability, null meaning and provenance. Causal extraction excludes all retrospective macro entities/features. Raw individual trades remain outside approved lineage unless separately authorized.

## Physical partitioning

Use Parquet/Zstandard and the previously approved pruning dimensions by market/timeframe/year/resolution. Macro anchors/touches/fragments/retracements may remain unpartitioned unless size later justifies otherwise.

Every manifest records schema/version, partitions/parts, row counts, time coverage, market/resolution coverage, source coverage, integrity evidence, producing run id and validation status. Extraction discovers parts through manifests/catalog, never path guessing.
