# Research Table Schema Contract

## Purpose

Define canonical logical tables, row grain, stable identifiers, joins, availability classes, macro-anchor uncertainty, and physical partitioning for Structure Research v5 so implementation does not invent its own data model.

## ADDED Requirements

### Requirement: Stable identifiers use one deterministic UUIDv5 namespace

Namespace:

`87411ce4-8483-55b7-a348-700b7ad4b9ab`.

Canonical identity strings use UTF-8, `|` separators, normalized enum values, and UTC timestamps in `YYYY-MM-DDTHH:MM:SSZ`.

Required identities:

- `source_segment_id = uuid5(namespace, "segment|{venue}|{instrument}|{market_type}|{segment_start_time}")`
- `gap_id = uuid5(namespace, "gap|{venue}|{instrument}|{market_type}|{gap_start_time}|{gap_end_time}")`
- `candle_id = uuid5(namespace, "candle|{venue}|{instrument}|{market_type}|{timeframe}|{start_time}")`
- fixed `observation_id = uuid5(namespace, "observation|fixed|{candle_id}")`
- rolling `observation_id = uuid5(namespace, "observation|rolling|{venue}|{instrument}|{market_type}|{rolling_duration}|{end_time}")`
- macro `observation_id = uuid5(namespace, "observation|macro_leg|{macro_source_checksum}|{macro_leg_id}")`
- `pair_id = uuid5(namespace, "pair|{prev_candle_id}|{curr_candle_id}")`
- `retracement_id = uuid5(namespace, "retracement|{anchor_a_id}|{anchor_b_id}|{anchor_c_id}|{relationship_source_id}")`
- `macro_anchor_id = uuid5(namespace, "macro_anchor|{macro_source_checksum}|{source_event_id}")` where a stable source event id exists.

A boundary-crossing fixed interval uses logical `market_type=cross_market` in its candle identity.

Run id, local path, archive filename, and mutable provenance do not redefine stable entity identity.

### Requirement: Canonical enums are explicit

At minimum:

- `venue`: `binance`
- `instrument`: `BTCUSDT`
- canonical 1m market type: `spot`, `usdt_m_futures`
- derived canonical market scope: `spot`, `usdt_m_futures`, `cross_market`
- `timeframe`: `1m`, `5m`, `15m`, `1H`, `4H`, `1D`
- `observation_kind`: `fixed`, `rolling`, `macro_leg`
- `availability_class`: `causal`, `retrospective`
- `direction`: `up`, `down`, `flat`
- `completeness_status`: `complete`, `incomplete_gap`, `incomplete_boundary`, `invalid`
- macro historical provenance: `spot`, `futures`, `mixed`, `unknown`
- anchor-time precision: `exact`, `1m_bucket`, `5m_bucket`, `15m_bucket`, `1H_bucket`, `4H_bucket`, `1D_bucket`, `unknown`
- anchor refinement status: `exact_source`, `unique_1m_match`, `multiple_1m_matches`, `no_1m_match`, `incomplete_search_coverage`, `source_incompatible`, `not_attempted`.

Unknown future enum values remain explicit and are never silently coerced.

### Requirement: `source_segments` has one row per continuous canonical 1m segment

Primary key: `source_segment_id`.

Required columns:

- `source_segment_id`
- `venue`, `instrument`, canonical `market_type`
- `segment_start_time`, `segment_end_time`
- `first_candle_id`, `last_candle_id`
- `row_count`
- `start_reason`, `end_reason`
- `segment_status`
- `source_contract_version`, `schema_version`, `run_id`.

Archive/provenance changes do not create segments. Real gaps and market-type transitions do.

### Requirement: `source_gaps` has one row per unresolved canonical 1m gap

Primary key: `gap_id`.

Required columns:

- `gap_id`
- `venue`, `instrument`, `market_type`
- `gap_start_time`, `gap_end_time`
- `missing_1m_count`
- `gap_reason`
- `recovery_attempted`, `recovery_source`, `recovery_status`
- `diagnostic_synthetic_row_exists`
- `evidence_artifact`
- `left_source_segment_id`, `right_source_segment_id`
- `schema_version`, `run_id`.

Synthetic/no-trade diagnostic buckets do not remove a gap unless approved observed OHLC becomes available and the source contract changes.

### Requirement: `candles_1m` is the strict observed canonical source spine

Row grain: one observed canonical 1m candle.

Primary key: `candle_id`.
Natural uniqueness: `(venue,instrument,market_type,timeframe,start_time)`.

Required columns include identity/market fields, `source_segment_id`, `timeframe=1m`, exact minute-grid `start_time/end_time`, OHLCV, validated source-native additive fields where available, `source_id`, `raw_artifact_id`, `provenance_kind`, `is_reconstructed`, validation/completeness status, schema version and run id.

An unobserved synthetic no-trade bucket is not a canonical 1m row.

### Requirement: `candles_fixed` contains the complete UTC target interval grid

Row grain: one fixed UTC interval at `5m`, `15m`, `1H`, `4H`, or `1D`.

Primary key: `candle_id`.

Required columns:

- identity/market fields;
- canonical `market_type` including `cross_market` when an interval spans a market boundary;
- `source_segment_id` only when the complete interval belongs to one segment;
- timeframe/times;
- complete OHLCV when valid, else null;
- approved additive native fields when valid;
- `construction_method=derived_from_1m`;
- `source_calculation_resolution=1m`;
- expected/observed constituent count, coverage ratio;
- completeness status;
- optional explicitly named `observed_only_*` diagnostics;
- schema/run provenance.

### Requirement: `candle_geometry` materializes atomic target-candle geometry

Row grain: one complete target candle `5m` and higher.
Primary key: `candle_id`.

Required: candle identity/time/source fields, `full_range`, `body_size`, `body_high`, `body_low`, upper/lower wick, shares, log geometry, body direction, metric status, schema/run provenance.

Incomplete/boundary target intervals do not produce valid complete geometry.

### Requirement: `cross_timeframe_map` stores target-to-target containment

Primary key: `(child_candle_id,parent_timeframe)`.

Persist:

- `5m -> 15m/1H/4H/1D`
- `15m -> 1H/4H/1D`
- `1H -> 4H/1D`
- `4H -> 1D`.

Required fields include child/parent ids/timeframes, canonical market/source scope, child times, zero-based ordinal, expected/observed counts, coverage, mapping status and provenance.

### Requirement: `macro_anchors` stores one shared anchor/refinement record per source pivot

Row grain: one approved source macro pivot/event.
Primary key: `macro_anchor_id`.

Required columns:

- `macro_anchor_id`, `macro_source_checksum`, `source_event_id`;
- `source_anchor_time`, `source_anchor_price`, `anchor_extreme_type` (`high`/`low`);
- `source_parent_market`, `source_refinement_market`, `source_refinement_timeframe`;
- `historical_source_classification`;
- `source_time_precision`;
- initial `possible_time_start`, `possible_time_end`;
- `refinement_status`;
- `refinement_market_type`;
- `search_coverage_complete`;
- `candidate_1m_count`;
- `first_candidate_1m_start`, `last_candidate_1m_start`;
- refined `possible_time_start`, `possible_time_end` after the deterministic 1m audit;
- `boundary_uncertainty_seconds`;
- evidence/provenance fields;
- `availability_class=retrospective`, `available_at=null`;
- schema/run provenance.

When a pivot is shared between adjacent macro legs, both legs reference the same `macro_anchor_id`.

### Requirement: canonical `market_type` and historical macro provenance are different columns

Canonical `market_type` answers: which market population does this wall-clock interval belong to under the current Structure Research v5 source chronology?

Historical macro provenance answers: from which old source mixture was the macro anchor/leg originally constructed?

They SHALL NOT substitute for each other.

For macro observations:

- if the macro source-time interval lies wholly before the canonical spot/futures boundary, `market_type=spot`;
- if wholly at/after the boundary, `market_type=usdt_m_futures`;
- if it spans the boundary, `market_type=cross_market`.

Historical `leg_source_classification=mixed` does NOT make canonical `market_type` null.

A canonical gap inside an otherwise futures/spot macro interval does not change market type; it makes `source_segment_id=null` and affects coverage/status.

### Requirement: `observation_index` unifies fixed, rolling, and macro observations

Primary key: `observation_id`.

Required columns:

- `observation_id`, `observation_kind`;
- venue/instrument;
- non-null canonical `market_type` for fixed/rolling/macro (`spot`, `usdt_m_futures`, or `cross_market`);
- `source_segment_id` only when fully contained in exactly one canonical segment;
- `start_time`, `end_time`, `observation_end_year`, `duration_seconds`;
- start/end price only when semantically valid for that observation kind;
- local mechanical direction where defined;
- nullable fixed timeframe / rolling duration / macro ids;
- `availability_class`, `available_at`;
- expected-base fields and coverage;
- completeness status;
- schema/run provenance.

For macro rows specifically:

- `start_time/end_time` are the preserved source-coordinate anchor timestamps and SHALL be documented as source-coordinate times, not exact event times when bucket-limited;
- `start_price/end_price` are approved source macro anchor prices;
- `availability_class=retrospective`;
- `available_at=null`;
- `source_segment_id` is non-null only if the entire relevant canonical safe interior lies in one segment and no stronger ambiguity applies.

Expected base resolution:

- fixed = `1m`;
- rolling = `5m`;
- macro = null unless an explicit safe-interior base count is materialized elsewhere.

Incomplete fixed/rolling ordinary endpoints/net features do not masquerade as complete metrics.

### Requirement: rolling calculation-resolution matrix is exact

- `30m`: `5m`, `15m`
- `1h`: `5m`, `15m`
- `4h`: `5m`, `15m`, `1H`
- `12h`: `5m`, `15m`, `1H`, `4H`
- `24h`: `5m`, `15m`, `1H`, `4H`
- `3d`: `5m`, `15m`, `1H`, `4H`, `1D`.

### Requirement: fixed calculation-resolution matrix is exact

For path/activity/overlap/volume/volatility families:

- fixed `15m`: via `5m`
- fixed `1H`: via `5m`, `15m`
- fixed `4H`: via `5m`, `15m`, `1H`
- fixed `1D`: via `5m`, `15m`, `1H`, `4H`.

Fixed 5m has atomic geometry but no lower target calculation resolution in this pass.

### Requirement: macro safe-interior calculation-resolution matrix is exact

For a macro observation, safe-interior path/activity/overlap/volume summaries SHALL be attempted at `5m`, `15m`, `1H`, `4H`, and `1D` when at least two complete eligible constituents fit wholly inside the safe interior and required continuity exists.

Macro RV is not required. Complete anchor-inclusive path is separately gated and is not implied by safe-interior availability.

### Requirement: `observation_price_speed` uses canonical speed names

Primary key: `observation_id`.

Required fields include ordinary/log displacement, `raw_signed_speed_pct_per_hour`, `signed_log_speed_per_hour`, `absolute_log_speed_per_hour`, `local_direction_speed_pct_per_hour`, `local_direction_log_speed_per_hour`, rolling speed-change/acceleration fields, metric status and pruning/provenance columns.

Macro source-coordinate speed may be retained as retrospective source measurement, clearly named/documented as source-coordinate rather than exact canonical timing.

### Requirement: `observation_path_activity` separates fixed/rolling complete path from macro safe interior

Primary key: `(observation_id,calculation_resolution)`.

For fixed/rolling required fields include coverage, `close_path`, `log_close_path`, efficiencies, upward/downward and local-direction components, alternation, candle activity, extrema/excursions, status/provenance.

For macro rows, use explicit safe-interior names:

- `safe_interior_start_time`, `safe_interior_end_time`;
- `safe_expected_constituent_count`, `safe_observed_constituent_count`, `safe_coverage_ratio`;
- `safe_internal_close_path`, `safe_internal_log_close_path`;
- `safe_internal_displacement`, `safe_internal_log_displacement`;
- `safe_internal_path_efficiency`, `safe_internal_log_path_efficiency`;
- safe directional/alternation/activity/extrema fields as declared in feature dictionary;
- `safe_internal_status`;
- separately nullable `anchor_inclusive_close_path`, `anchor_inclusive_log_close_path`, corresponding efficiency fields and `anchor_inclusive_status`.

The old ambiguous interpretation of generic macro `internal_close_path` as whole-leg internal path is prohibited. Macro metrics with uncertain boundaries SHALL use the `safe_*` namespace.

### Requirement: `atomic_candle_pairs` preserves neutral pair geometry

Primary key: `pair_id`. Required fields include pair/candle ids, resolution, market type, source segments/times, eligibility/reason, approved range/body overlap, position, extension and mirrored penetration fields plus provenance.

### Requirement: `observation_overlap_summary` stores pair evolution

Primary key: `(observation_id,calculation_resolution)`.

Only eligible pairs fully inside the observation's valid constituent interval contribute. Macro rows use the safe interior only when boundaries are uncertain.

### Requirement: `observation_volume_volatility` uses canonical names

Primary key: `(observation_id,calculation_resolution)`.

Required fields include coverage, volume sum/mean/median, rolling `volume_sum_change_vs_prev` and ratio where defined, body/close-step directional volume groups, TR/ATR, fixed/rolling RV, high-low width, range/log-range summaries, explicitly declared rolling comparison fields and status/provenance.

Macro rows may contain safe-interior volume/TR/activity summaries under the safe coverage contract but SHALL NOT materialize macro RV in this pass.

### Requirement: `retracement_measurements` stores only explicitly configured approved A-B-C relationships

Primary key: `retracement_id`.

Required fields include relationship source, A/B/C anchor ids/times/prices, anchor provenance/precision, direct retracement formula fields, availability, status and run/schema provenance.

Arbitrary combinations are prohibited. Zero rows is valid when no production tuple list is configured.

### Requirement: `macro_legs` preserves source leg plus refined boundary semantics

Primary key: `macro_leg_id`.

Preserve all approved source columns plus:

- `macro_source_checksum`, `macro_observation_id`;
- `start_macro_anchor_id`, `end_macro_anchor_id`;
- source-vs-derived direction QA;
- `leg_source_classification` (`spot`, `futures`, `mixed`, `unknown`);
- canonical `market_type` (`spot`, `usdt_m_futures`, `cross_market`);
- canonical source compatibility/coverage status;
- `cross_canonical_boundary`;
- `safe_interior_start_time`, `safe_interior_end_time`;
- `safe_interior_duration_seconds` when non-empty;
- `boundary_uncertainty_status`;
- source/canonical coverage status;
- schema/run provenance.

Historical source provenance SHALL NOT overwrite canonical market assignment.

### Requirement: `observation_macro_context` isolates retrospective macro relationships

Primary key: `(observation_id,macro_leg_id)`.

Required columns include temporal intersection, source-coordinate time fraction where explicitly named, endpoint/source direction, approved macro-aligned numeric fields, `availability_class=retrospective`, `available_at=null`, pruning/status/provenance fields.

Source-coordinate progress is not exact event-time progress when anchor timing is bucket-limited.

### Requirement: feature dictionary is canonical and complete

One row per materialized metric feature with logical table, feature name, meaning, formula, units, applicability, calculation-resolution semantics, observation-kind semantics, availability, null meaning, provenance and schema version.

Canonical copy is Parquet; emit a small CSV review copy.

### Requirement: causal-only extraction is structurally enforceable

Causal extraction excludes macro observations/context, macro anchor refinement records, retrospective retracement rows, and every retrospective feature. `available_at=null` on retrospective entities SHALL NOT make them causal.

### Requirement: canonical Parquet partitioning is explicit

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
- `retracement_measurements`: unpartitioned unless size later requires otherwise
- `macro_anchors`, `macro_legs`, source/dictionary dimension tables: unpartitioned unless size later justifies otherwise.

No null `market_type` partition is permitted merely because macro provenance is mixed.

### Requirement: manifests and run provenance are auditable

Every logical table carries schema/run provenance. Every logical-table manifest records schema version, partition columns, part paths, row counts, time coverage, market types/resolutions, source-segment coverage where applicable, integrity evidence, producing run id and validation status.

Extraction discovers canonical parts through manifests/catalog, never path guessing.
