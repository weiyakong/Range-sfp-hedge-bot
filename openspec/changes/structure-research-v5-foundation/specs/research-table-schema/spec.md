# Research Table Schema Contract

## Purpose

Define canonical logical tables, row grain, stable identifiers, joins, availability classes, exact/fallback macro-boundary semantics, and physical partitioning for Structure Research v5.

## Stable identifiers

UUIDv5 namespace:

`87411ce4-8483-55b7-a348-700b7ad4b9ab`

Canonical identities:

- `source_segment_id = uuid5(namespace, "segment|{venue}|{instrument}|{market_type}|{segment_start_time}")`
- `gap_id = uuid5(namespace, "gap|{venue}|{instrument}|{market_type}|{gap_start_time}|{gap_end_time}")`
- `candle_id = uuid5(namespace, "candle|{venue}|{instrument}|{market_type}|{timeframe}|{start_time}")`
- fixed `observation_id = uuid5(namespace, "observation|fixed|{candle_id}")`
- rolling `observation_id = uuid5(namespace, "observation|rolling|{venue}|{instrument}|{market_type}|{rolling_duration}|{end_time}")`
- macro `observation_id = uuid5(namespace, "observation|macro_leg|{macro_source_checksum}|{macro_leg_id}")`
- `pair_id = uuid5(namespace, "pair|{prev_candle_id}|{curr_candle_id}")`
- `macro_anchor_id = uuid5(namespace, "macro_anchor|{macro_source_checksum}|{source_event_id}")`
- `retracement_id = uuid5(namespace, "retracement|{anchor_a_id}|{anchor_b_id}|{anchor_c_id}|{relationship_source_id}")`

Run id, local path, archive filename and mutable provenance do not redefine stable identity.

## Canonical enums

At minimum:

- `venue=binance`
- `instrument=BTCUSDT`
- market type: `spot`, `usdt_m_futures`, `cross_market`
- timeframe: `1m`, `5m`, `15m`, `1H`, `4H`, `1D`
- observation kind: `fixed`, `rolling`, `macro_leg`
- availability: `causal`, `retrospective`
- direction: `up`, `down`, `flat`
- completeness: `complete`, `incomplete_gap`, `incomplete_boundary`, `invalid`
- historical macro provenance: `spot`, `futures`, `mixed`, `unknown`
- source anchor precision: `exact`, `1m_bucket`, `5m_bucket`, `15m_bucket`, `1H_bucket`, `4H_bucket`, `1D_bucket`, `unknown`
- 5m localization status: `unique_5m_match`, `multiple_5m_matches`, `no_5m_match`, `incomplete_5m_search_coverage`, `unresolved`
- trade refinement status: `exact_unique_trade_touch`, `multiple_exact_trade_touches`, `no_exact_trade_touch`, `incomplete_trade_coverage`, `source_unavailable`, `not_attempted`.

Unknown future values remain explicit and are never silently coerced.

## Core source/candle tables

### `source_segments`
One row per continuous canonical 1m same-market segment. Primary key `source_segment_id`. Preserve market/time bounds, first/last candle, row count, start/end reason, status and provenance. Archive changes alone do not split a segment.

### `source_gaps`
One row per unresolved canonical gap. Primary key `gap_id`. Preserve market/time bounds, missing count, reason, recovery evidence/status, synthetic diagnostic evidence, adjacent segments and provenance.

### `candles_1m`
Strict observed canonical 1m spine. Primary key `candle_id`; natural uniqueness `(venue,instrument,market_type,timeframe,start_time)`. Preserve exact canonical minute grid, OHLCV/native validated additive fields, source identity, raw artifact, source-native timestamp evidence, canonicalization method/status and provenance. Synthetic no-trade buckets are excluded.

### `candles_fixed`
Complete UTC grid for `5m/15m/1H/4H/1D`. Preserve market scope, times, OHLCV only when complete, construction `derived_from_1m`, expected/observed constituent counts, coverage and completeness. Boundary/gap rows remain explicit with complete metrics null.

### `candle_geometry`
One row per complete target candle with range/body/wicks/shares/log geometry/body direction and provenance.

### `cross_timeframe_map`
Persist `5m->15m/1H/4H/1D`, `15m->1H/4H/1D`, `1H->4H/1D`, `4H->1D`, including ordinal/coverage/status.

## Macro anchor tables

### `macro_anchors`

One shared row per approved source pivot/event. Primary key `macro_anchor_id`.

Required fields separate every precision layer instead of overwriting one pair of columns:

- identity: `macro_anchor_id`, `macro_source_checksum`, `source_event_id`
- source facts: `source_anchor_time`, `source_anchor_price`, `source_anchor_price_units`, `anchor_extreme_type`
- anchor-level provenance from approved localization artifact: `source_time_precision`, `source_market`, `source_parent_market`, `source_refinement_market`, `source_refinement_timeframe`, `historical_source_classification`
- original source uncertainty: `source_possible_time_start`, `source_possible_time_end`
- approved 5m localization: `localization_5m_status`, `candidate_5m_count`, `candidate_5m_start_times`, nullable `localized_5m_start_time`, `localized_5m_end_time`, localization artifact checksum
- trade refinement: `trade_refinement_status`, `trade_source_granularity`, `trade_touch_count`, `first_trade_touch_time`, `last_trade_touch_time`
- exact boundary only when unique: `exact_pivot_time`, `exact_pivot_sequence_id`
- fallback uncertainty after all available evidence: `refined_possible_time_start`, `refined_possible_time_end`, `boundary_uncertainty_seconds`
- evidence/provenance/checksums
- `availability_class=retrospective`, `available_at=null`
- schema/run provenance.

The approved 5m localization artifact, not per-leg `duration_precision`, supplies anchor-level source precision/provenance. The original per-leg `duration_precision` remains a source-leg field only.

A shared pivot is referenced by both adjacent legs through the same `macro_anchor_id`.

### `macro_trade_touches`
One row per exact matching source trade/aggTrade touch considered for an anchor. Primary key may be `(macro_anchor_id,candidate_5m_start_time,event_time,native_sequence_id)`. Preserve price/price_units, source market, granularity, native ids, first/last underlying trade ids where present, artifact/checksum and eligibility.

### `macro_boundary_fragments`
One row per authoritative exact LEFT/RIGHT boundary fragment and calculation resolution when a unique trade pivot exists.

Required identity/context:

- macro anchor/leg id
- fragment side `LEFT|RIGHT`
- calculation resolution `5m|15m|1H|4H|1D`
- market type
- enclosing canonical interval id/times
- exact pivot time/sequence id/price
- fragment start/end and duration
- composition method (`trade_only_5m` or `trade_5m_plus_complete_5m`)
- coverage/status.

Persist fragment OHLCV/geometry/activity as mathematically applicable. Trade-sequence measurements use explicit `trade_*` names. The pivot source record volume/count belongs to LEFT once; RIGHT begins from pivot price state but excludes the pivot record from its trade volume/count.

Canonical fixed candles remain unchanged.

## Observation tables

### `observation_index`
Primary key `observation_id`. Preserve observation kind, market scope, times, duration, endpoints/direction where valid, source segment, fixed/rolling/macro ids, availability, completeness and provenance.

For macro:
- if both pivots are `exact_unique_trade_touch`, `start_time/end_time` are exact pivot times and `duration_seconds` is exact;
- otherwise exact macro start/end/duration are null and source-coordinate start/end/duration remain in explicitly `source_*` fields;
- `availability_class=retrospective`, `available_at=null`.

### Rolling calculation matrix
- `30m`: `5m`, `15m`
- `1h`: `5m`, `15m`
- `4h`: `5m`, `15m`, `1H`
- `12h`: `5m`, `15m`, `1H`, `4H`
- `24h`: `5m`, `15m`, `1H`, `4H`
- `3d`: `5m`, `15m`, `1H`, `4H`, `1D`.

### Fixed calculation matrix
- `15m`: via `5m`
- `1H`: via `5m`, `15m`
- `4H`: via `5m`, `15m`, `1H`
- `1D`: via `5m`, `15m`, `1H`, `4H`.

### Macro calculation matrix
Attempt macro path/activity/overlap/volume at `5m/15m/1H/4H/1D`.

For exact trade-resolved legs use exact pivots plus exact boundary-fragment composition.

For unresolved/ambiguous pivots use fallback unambiguous interior only. At resolution `R`:

`fallback_expected_constituent_count` = number of canonical fixed-grid `R` intervals whose whole `[start,end)` lies inside the fallback unambiguous interval, regardless of data presence.

`fallback_observed_constituent_count` = expected slots having valid complete compatible canonical candles.

Coverage = observed/expected. Never use `duration/R` when boundaries are off-grid.

Macro RV remains deferred.

### `observation_price_speed`
Primary key `observation_id`.

Fixed/rolling use canonical ordinary/log speed names.

Macro separates:
- original `source_*` displacement/duration/speed from `macro_legs_log20`;
- exact `macro_*` displacement/duration/speed only when both trade pivots are exact.

Generic exact macro speed SHALL NOT be populated from bucket-limited source timestamps.

There is one exact whole-leg macro speed. Timeframe-specific tables describe internal evolution; they do not redefine the whole-leg speed.

### `observation_path_activity`
Primary key `(observation_id,calculation_resolution)`.

Fixed/rolling: close path/log path/efficiency/directional components/alternation/activity/extrema/coverage.

Exact macro close-path sequence at resolution `R`:
- `Q0 = exact start pivot price`;
- chronological closes of complete canonical `R` candles satisfying `start_pivot_time < candle.end_time <= end_pivot_time`;
- append exact end pivot price if not already the final price state.

The same sequence defines macro displacement, close path, log path, efficiency, directional components and alternation. Trade-level boundary path is never added to this close path.

For ambiguous fallback macro rows, use explicit `fallback_*` names. If fallback constituents `B1...Bn` are used, the measured sequence starts with `Q0=open(B1)` and `Qi=close(Bi)`, so the first eligible candle's open->close movement is not lost. Also persist `fallback_measured_start_time=B1.start_time` and `fallback_measured_end_time=Bn.end_time`.

### `atomic_candle_pairs`
Canonical same-resolution adjacent complete fixed-candle pairs only. Boundary-fragment pairs are a separate relationship type/table or explicitly typed rows and never masquerade as canonical pairs.

### `observation_overlap_summary`
Fixed/rolling aggregate eligible canonical pairs. Exact macro may additionally aggregate explicitly typed boundary-fragment relationships plus complete interior pairs without double counting. Ambiguous macro fallback uses only pairs wholly inside fallback interval.

### `observation_volume_volatility`
Fixed/rolling preserve volume summaries, directional volume, TR/ATR, RV, width/range summaries and rolling comparisons.

Exact macro volume/activity uses the non-overlapping union of start RIGHT fragment + full interior canonical intervals + end LEFT fragment at the stated resolution. Never include a full boundary candle together with its fragment. Ambiguous fallback uses only the fallback constituent set. Macro RV remains null/deferred.

## Retracement

### `retracement_measurements`

First-pass production relationship is specifically consecutive opposite-direction macro legs sharing the same pivot:

`A -> B` followed immediately by `B -> C`.

A/B/C are therefore `macro_anchor_id` foreign keys; no polymorphic candle/rolling anchor ids are allowed in this pass.

Relationship source id is deterministic, e.g. `macro_adjacent_opposite|{previous_macro_leg_id}|{next_macro_leg_id}`.

The approved 128-leg source has 127 adjacent leg transitions; 118 share the same boundary pivot and are opposite-direction (59 up->down, 59 down->up). Those 118 relationships are the production retracement set. The 9 non-shared transitions do not receive a retracement row.

Required: previous/next leg ids, A/B/C macro anchor ids/times/prices, direct reference/candidate deltas, `candidate_vs_reference_pct`, `opposing_retracement_abs`, `retracement_pct`, boundary precision/refinement status, retrospective availability and provenance.

No Fibonacci label/conversion.

## `macro_legs`

Preserve all approved source columns plus:
- macro source checksum/observation id
- start/end macro anchor ids
- source direction QA
- historical source classification
- canonical market type
- exact-boundary status
- exact start/end pivot times when resolved
- exact duration when resolved
- fallback uncertainty interval only when needed
- canonical coverage/status
- schema/run provenance.

Historical provenance never overwrites canonical market scope.

## `observation_macro_context`
Retrospective observation-to-macro relationships. Exact temporal fractions may be exposed only when exact pivot boundaries exist; otherwise source-coordinate/fallback concepts are explicitly named. `availability_class=retrospective`, `available_at=null`.

## Feature dictionary / extraction safety

Every materialized feature has exactly one dictionary definition including table, name, formula, units, applicability, calculation resolution, availability, null meaning and provenance.

Causal extraction excludes macro observations/anchors/touches/fragments/context/retracement and every retrospective feature.

## Physical partitioning

Use Zstandard.

- `candles_1m`: `market_type/year/month`
- `candles_fixed`: `timeframe/market_type/year`
- `candle_geometry`: `timeframe/market_type/year`
- `cross_timeframe_map`: `child_timeframe/market_type/year`
- `observation_index`: `observation_kind/market_type/observation_end_year`
- `observation_price_speed`: same pruning dimensions
- `observation_path_activity`: `calculation_resolution/market_type/observation_end_year`
- `atomic_candle_pairs`: `calculation_resolution/market_type/year`
- `observation_overlap_summary`: `calculation_resolution/market_type/observation_end_year`
- `observation_volume_volatility`: `calculation_resolution/market_type/observation_end_year`
- `observation_macro_context`: `market_type/observation_end_year`
- `macro_trade_touches`, `macro_boundary_fragments`, `retracement_measurements`, `macro_anchors`, `macro_legs`, source/dictionary dimensions: unpartitioned unless size later justifies otherwise.

No null market partition merely because historical macro provenance is mixed.

Every manifest records schema/version, partitions/parts, row counts, time coverage, market/resolution coverage, source coverage, integrity evidence, producing run id and validation status. Extraction discovers parts through manifests/catalog, never path guessing.
