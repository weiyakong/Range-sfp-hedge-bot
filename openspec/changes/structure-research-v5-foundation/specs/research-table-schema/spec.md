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
- localization status: `unique_5m_match`, `multiple_5m_matches`, `no_5m_match`, `incomplete_5m_search_coverage`, `unresolved`
- localization window kind: `canonical_5m`, `off_grid_source_5m`
- approved refinement source granularity: `agg_trade`
- refinement status: `exact_unique_trade_touch`, `multiple_exact_trade_touches`, `no_exact_trade_touch`, `incomplete_trade_coverage`, `source_unavailable`, `not_attempted`
- aggregate boundary precision: `single_underlying_trade`, `aggregate_boundary_indivisible`, `not_applicable`.

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
- anchor-level provenance from reviewed localization artifact: `source_time_precision`, `source_market`, `source_parent_market`, `source_refinement_market`, `source_refinement_timeframe`, `historical_source_classification`
- original source uncertainty: `source_possible_time_start`, `source_possible_time_end`
- reviewed localization: `localization_status`, `candidate_window_count`, `candidate_window_start_times`, `candidate_window_end_times`, `candidate_window_kinds`, localization artifact checksum
- known anomaly flag for windows inherited from off-grid source timestamps
- approved aggTrade refinement: `trade_refinement_status`, `trade_source_granularity=agg_trade`, `trade_touch_count`, `first_trade_touch_time`, `last_trade_touch_time`
- canonical exact containment after approved aggTrade resolution: `canonical_pivot_5m_start_time`, `canonical_pivot_5m_end_time`
- resolved boundary only when one unique matching aggTrade exists: `exact_pivot_time`, `exact_pivot_sequence_id=agg_trade_id`
- pivot aggregate metadata: `pivot_first_trade_id`, `pivot_last_trade_id`, `pivot_underlying_trade_count`, `aggregate_boundary_precision`
- fallback uncertainty after all approved evidence: `refined_possible_time_start`, `refined_possible_time_end`, `boundary_uncertainty_seconds`
- evidence/provenance/checksums
- `availability_class=retrospective`, `available_at=null`
- schema/run provenance.

The reviewed localization artifact, not per-leg `duration_precision`, supplies anchor-level source precision/provenance. The original per-leg `duration_precision` remains a source-leg field only.

The current localization artifact contains 145 distinct candidate windows. 142 are canonical-grid 5m windows. Three (`E00059`, `E00065`, `E00070`) are 5-minute off-grid source-localization windows with `+20.799s`; they SHALL NOT populate canonical 5m fields until approved aggTrade evidence locates the resolved pivot and therefore its actual canonical 5m candle.

Raw individual trade files are outside the approved schema path for this stage. Their existence on disk does not permit populating these fields from raw trades unless the user later explicitly approves a source change.

A shared pivot is referenced by both adjacent legs through the same `macro_anchor_id`.

### `macro_trade_touches`
One row per exact matching approved `aggTrades` row considered for an anchor. Primary key `(macro_anchor_id,candidate_window_start,event_time,agg_trade_id)`. Preserve:

- exact price/price_units
- source market
- `source_granularity=agg_trade`
- `agg_trade_id`
- first/last underlying trade ids
- underlying trade count where derivable exactly
- event time
- quantity/quote quantity where source provides exact values
- maker-side source field where present
- artifact/checksum
- eligibility/status.

Do not store reconstructed individual raw-trade rows here.

### `macro_boundary_fragments`
One row per authoritative LEFT/RIGHT boundary fragment and calculation resolution when one unique approved aggTrade pivot exists.

Required identity/context:

- macro anchor/leg id
- fragment side `LEFT|RIGHT`
- calculation resolution `5m|15m|1H|4H|1D`
- market type
- enclosing canonical interval id/times
- resolved pivot event time/agg_trade_id/price
- fragment start/end and duration
- composition method (`agg_trade_only_5m` or `agg_trade_5m_plus_complete_5m`)
- `aggregate_boundary_precision`
- coverage/status.

Persist fragment OHLCV/geometry/activity as mathematically applicable at approved aggTrade-source granularity. Aggregate-sequence measurements use explicit aggregate/trade-level names and SHALL NOT be described as reconstructed raw-trade measurements.

The pivot aggTrade row belongs to LEFT once as an indivisible source record. RIGHT begins from pivot price state but excludes that aggregate row. If the pivot aggregate contains multiple underlying trades, its quantity/count SHALL NOT be split internally between LEFT and RIGHT.

Canonical fixed candles remain unchanged.

## Observation tables

### `observation_index`
Primary key `observation_id`. Preserve observation kind, market scope, times, duration, endpoints/direction where valid, source segment, fixed/rolling/macro ids, availability, completeness and provenance.

For macro:
- if both pivots are `exact_unique_trade_touch` under approved aggTrade-source resolution, `start_time/end_time` are the resolved aggTrade event times and `duration_seconds` follows them;
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

For uniquely aggTrade-resolved legs use resolved pivots plus boundary-fragment composition.

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
- resolved `macro_*` displacement/duration/speed only when both pivots have one unique approved aggTrade touch.

Generic macro speed SHALL NOT be populated from bucket-limited source timestamps.

There is one whole-leg macro speed. Timeframe-specific tables describe internal evolution; they do not redefine the whole-leg speed.

### `observation_path_activity`
Primary key `(observation_id,calculation_resolution)`.

Fixed/rolling: close path/log path/efficiency/directional components/alternation/activity/extrema/coverage.

Resolved macro close-path sequence at resolution `R`:
- `Q0 = resolved start pivot price`;
- chronological closes of complete canonical `R` candles satisfying `start_pivot_time < candle.end_time <= end_pivot_time`;
- append resolved end pivot price if not already the final price state.

The same sequence defines macro displacement, close path, log path, efficiency, directional components and alternation. AggTrade-level boundary path is never added to this close path.

For ambiguous fallback macro rows, use explicit `fallback_*` names. If fallback constituents `B1...Bn` are used, the measured sequence starts with `Q0=open(B1)` and `Qi=close(Bi)`, so the first eligible candle's open->close movement is not lost. Also persist `fallback_measured_start_time=B1.start_time` and `fallback_measured_end_time=Bn.end_time`.

### `atomic_candle_pairs`
Canonical same-resolution adjacent complete fixed-candle pairs only. Boundary-fragment pairs are a separate relationship type/table or explicitly typed rows and never masquerade as canonical pairs.

### `observation_overlap_summary`
Fixed/rolling aggregate eligible canonical pairs. Resolved macro may additionally aggregate explicitly typed boundary-fragment relationships plus complete interior pairs without double counting. Ambiguous macro fallback uses only pairs wholly inside fallback interval.

### `observation_volume_volatility`
Fixed/rolling preserve volume summaries, directional volume, TR/ATR, RV, width/range summaries and rolling comparisons.

Resolved macro volume/activity uses the non-overlapping union of start RIGHT fragment + full interior canonical intervals + end LEFT fragment at the stated resolution. Never include a full boundary candle together with its fragment. A multi-underlying pivot aggTrade remains indivisible and carries aggregate-boundary precision. Ambiguous fallback uses only the fallback constituent set. Macro RV remains null/deferred.

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
- approved aggTrade-boundary status
- resolved start/end pivot times when available
- resolved duration when both endpoints are unique under approved aggTrade-source resolution
- fallback uncertainty interval only when needed
- canonical coverage/status
- schema/run provenance.

Historical provenance never overwrites canonical market scope.

## `observation_macro_context`
Retrospective observation-to-macro relationships. Exact temporal fractions may be exposed only when both boundary coordinates are resolved under the approved aggTrade source; otherwise source-coordinate/fallback concepts are explicitly named. `availability_class=retrospective`, `available_at=null`.

## Feature dictionary / extraction safety

Every materialized feature has exactly one dictionary definition including table, name, formula, units, applicability, calculation resolution, availability, null meaning and provenance.

Causal extraction excludes macro observations/anchors/aggTrade touches/fragments/context/retracement and every retrospective feature.

Raw individual trade artifacts are excluded from the approved feature lineage unless a later explicit user decision changes the source contract.

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
