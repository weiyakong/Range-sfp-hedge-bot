# Research Table Schema Contract

## Purpose

Define the canonical logical tables, row grain, stable identifiers, joins, availability classes, and physical partitioning for Structure Research v5 so implementation does not invent its own data model.

## ADDED Requirements

### Requirement: Stable identifiers use one deterministic UUIDv5 namespace

Stable entity identifiers SHALL use UUIDv5 namespace:

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
- `retracement_id = uuid5(namespace, "retracement|{anchor_a_id}|{anchor_b_id}|{anchor_c_id}|{relationship_source_id}")`.

For a boundary-crossing fixed interval, use logical `market_type=cross_market` in the candle identity. Such a row is an interval placeholder/diagnostic and never a complete tradable candle.

Run id, local path, archive filename, and mutable provenance SHALL NOT redefine stable entity identity.

### Requirement: Canonical enums are explicit

At minimum:

- `venue`: `binance`
- `instrument`: `BTCUSDT`
- 1m market type: `spot`, `usdt_m_futures`
- derived interval market type/source scope: `spot`, `usdt_m_futures`, `cross_market`
- `timeframe`: `1m`, `5m`, `15m`, `1H`, `4H`, `1D`
- `observation_kind`: `fixed`, `rolling`, `macro_leg`
- `availability_class`: `causal`, `retrospective`
- `direction`: `up`, `down`, `flat`
- `completeness_status`: `complete`, `incomplete_gap`, `incomplete_boundary`, `invalid`
- macro provenance class: `spot`, `futures`, `mixed`, `unknown`
- anchor-time precision: `exact`, `1m_bucket`, `5m_bucket`, `15m_bucket`, `1H_bucket`, `4H_bucket`, `1D_bucket`, `unknown`.

Unknown future enum values remain explicit and SHALL NOT be coerced silently.

### Requirement: `source_segments` has one row per continuous canonical 1m segment

Primary key: `source_segment_id`.

Required columns:

- `source_segment_id`
- `venue`, `instrument`, `market_type`
- `segment_start_time`, `segment_end_time`
- `first_candle_id`, `last_candle_id`
- `row_count`
- `start_reason`, `end_reason`
- `segment_status`
- `source_contract_version`, `schema_version`, `run_id`.

Archive/provenance changes do not create segments. Real canonical gaps and market-type transitions do.

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

Synthetic/no-trade diagnostic buckets SHALL NOT remove a row from this table unless approved observed OHLC becomes available and the source contract changes.

### Requirement: `candles_1m` is the strict canonical source spine

Row grain: one observed canonical 1m candle.

Primary key: `candle_id`.
Natural uniqueness: `(venue,instrument,market_type,timeframe,start_time)`.

Required columns:

- identity/market fields;
- `source_segment_id`;
- `timeframe=1m`;
- `start_time`, `end_time` exactly minute-grid aligned;
- `open`, `high`, `low`, `close`, `volume`;
- source-native additive fields where truly available;
- `source_id`, `raw_artifact_id`, `provenance_kind`;
- `is_reconstructed`;
- `validation_status`, `completeness_status`;
- `schema_version`, `run_id`.

An unobserved synthetic no-trade bucket is not a canonical `candles_1m` row.

### Requirement: `candles_fixed` contains the complete UTC target interval grid

Row grain: one fixed UTC target interval at `5m`, `15m`, `1H`, `4H`, or `1D`.

Primary key: `candle_id`.

Required columns:

- `candle_id`, `venue`, `instrument`;
- `market_type` including `cross_market` for an interval spanning the spot/futures boundary;
- `source_segment_id` only when the complete interval belongs to exactly one segment;
- `timeframe`, `start_time`, `end_time`;
- complete `open`, `high`, `low`, `close`, `volume` when valid, else null;
- approved additive native fields when valid;
- `construction_method=derived_from_1m`;
- `source_calculation_resolution=1m`;
- `expected_constituent_count`, `observed_constituent_count`, `coverage_ratio`;
- `completeness_status`;
- optional `observed_only_*` diagnostics;
- `schema_version`, `run_id`.

A fixed interval that crosses the source boundary SHALL exist as `market_type=cross_market`, `source_segment_id=null`, `completeness_status=incomplete_boundary`, and complete OHLCV null.

### Requirement: `candle_geometry` materializes atomic target-candle geometry

Row grain: one complete target candle (`5m` and higher).
Primary key: `candle_id`.

Required columns:

- `candle_id`, `timeframe`, `market_type`, `source_segment_id`, `start_time`;
- `full_range`, `body_size`, `body_high`, `body_low`, `upper_wick`, `lower_wick`;
- `body_share`, `upper_wick_share`, `lower_wick_share`;
- `log_full_range`, `log_body_size`, `log_upper_wick`, `log_lower_wick`;
- `body_direction`;
- `metric_status`, `schema_version`, `run_id`.

Incomplete/boundary target intervals SHALL NOT produce a valid complete geometry row.

### Requirement: direct 1m constituent membership is deterministic and not exploded

A fixed target's 1m constituents are recovered from its `[start_time,end_time)`, market/source continuity, and canonical 1m grid. No full persisted 1m-to-all-parent mapping is required.

### Requirement: `cross_timeframe_map` stores target-to-target containment

Row grain: one child target candle mapped to one larger target timeframe.
Primary key: `(child_candle_id,parent_timeframe)`.

Required columns:

- child/parent ids and timeframes;
- market/source scope;
- child times;
- `child_ordinal_in_parent` zero-based;
- expected/observed child counts;
- parent coverage ratio;
- `mapping_status`, `schema_version`, `run_id`.

Persist: `5m -> 15m/1H/4H/1D`, `15m -> 1H/4H/1D`, `1H -> 4H/1D`, `4H -> 1D`.

### Requirement: `observation_index` unifies fixed, rolling, and macro observations

Row grain: one research observation interval.
Primary key: `observation_id`.

Required columns:

- `observation_id`, `observation_kind`;
- `venue`, `instrument`;
- `market_type` (`cross_market` allowed for boundary-spanning fixed/rolling; nullable for historically mixed macro source where appropriate);
- `source_segment_id` when fully contained in one canonical segment;
- `start_time`, `end_time`, `observation_end_year`, `duration_seconds`;
- `start_price`, `end_price` only when the observation has valid complete canonical boundary prices or approved source macro anchors;
- `local_price_direction` where defined;
- `fixed_timeframe` nullable;
- `rolling_duration` nullable;
- `anchor_candle_id` nullable;
- `macro_leg_id`, `macro_source_checksum` nullable;
- `availability_class`, `available_at`;
- `expected_base_resolution`;
- `expected_base_count`, `observed_base_count`, `coverage_ratio`;
- `completeness_status`;
- `schema_version`, `run_id`.

`expected_base_resolution` is explicit:

- fixed observations: `1m` for canonical completeness;
- rolling observations: `5m` for observation interval completeness/indexing;
- macro observations: null unless an explicitly defined base-coverage count is materialized.

Incomplete fixed/rolling observations MAY retain explicitly named diagnostic observed-only endpoints, but ordinary `start_price/end_price`, net move, direction, and speed SHALL not masquerade as complete metrics.

### Requirement: rolling calculation-resolution matrix is exact

- `30m`: `5m`, `15m`
- `1h`: `5m`, `15m`
- `4h`: `5m`, `15m`, `1H`
- `12h`: `5m`, `15m`, `1H`, `4H`
- `24h`: `5m`, `15m`, `1H`, `4H`
- `3d`: `5m`, `15m`, `1H`, `4H`, `1D`.

Rolling feature rows reuse the same observation id across calculation resolutions.

### Requirement: fixed calculation-resolution matrix is exact

For calculation-resolution-dependent path/activity/overlap/volume/volatility families:

- fixed `15m`: via `5m`
- fixed `1H`: via `5m`, `15m`
- fixed `4H`: via `5m`, `15m`, `1H`
- fixed `1D`: via `5m`, `15m`, `1H`, `4H`.

A fixed `5m` candle has atomic candle geometry but no lower target calculation resolution in this pass.

### Requirement: macro calculation-resolution matrix is exact

For a macro observation, where canonical coverage exists:

- internal path/activity and overlap summaries SHALL be attempted at `5m`, `15m`, `1H`, `4H`, and `1D` when at least two complete eligible constituents exist;
- volume summaries MAY be produced at the same resolutions under complete-coverage rules;
- macro realized variance/volatility is not required in this pass;
- anchor-inclusive path is separately gated by anchor compatibility/time precision and is not implied by internal-path availability.

### Requirement: `observation_price_speed` uses canonical speed names

Row grain: one `observation_id`.
Primary key: `observation_id`.

Required metric columns:

- `signed_price_change`, `absolute_price_change`;
- `signed_return_pct`, `absolute_return_pct`;
- `signed_log_move`, `absolute_log_move`;
- `raw_signed_speed_pct_per_hour`;
- `signed_log_speed_per_hour`, `absolute_log_speed_per_hour`;
- `local_direction_speed_pct_per_hour`;
- `local_direction_log_speed_per_hour`;
- rolling `speed_change_pct_per_hour`, `acceleration_pct_per_hour2` and explicitly log-named companions where defined;
- `metric_status`;
- pruning columns `observation_kind`, `market_type`, `observation_end_year`;
- `schema_version`, `run_id`.

Macro-direction-aligned fields belong to retrospective macro context, not this local causal table.

### Requirement: `observation_path_activity` is keyed by observation and calculation resolution

Primary key: `(observation_id,calculation_resolution)`.

Required columns include:

- pruning/coverage fields;
- `close_path`, `log_close_path`;
- `path_efficiency`, `log_path_efficiency`;
- `upward_close_path`, `downward_close_path` and log companions;
- `path_with_local_direction`, `path_against_local_direction`, `counter_local_path_share` and log companions;
- zero/nonzero/sign-change/alternation fields;
- sums of range/body/wicks/TR/log activity;
- observation high/low with first/last/count;
- upward/downward excursions abs/pct/log;
- for macro observations: `internal_close_path`/`internal_log_close_path` may alias the ordinary canonical internal path under dictionary rules, while `anchor_inclusive_close_path`, `anchor_inclusive_log_close_path`, corresponding efficiency fields, and `anchor_inclusive_status` are separate nullable fields;
- `metric_status`, `schema_version`, `run_id`.

### Requirement: `atomic_candle_pairs` preserves neutral pair geometry

Row grain: one chronological neighbor candidate at one calculation resolution.
Primary key: `pair_id`.

Required columns:

- pair/candle ids, resolution, venue/instrument/market type;
- prev/curr source segment ids and times;
- `pair_eligible`, `ineligibility_reason`;
- all approved range overlap, overlap position, body overlap, neutral extension, and mirrored penetration fields;
- `schema_version`, `run_id`.

A boundary/gap candidate may be retained for QA with geometry requiring continuity null.

### Requirement: `observation_overlap_summary` stores pair evolution

Primary key: `(observation_id,calculation_resolution)`.

Required columns include coverage counts, `any_overlap_share`, mean/median overlap normalizations, body overlap, neutral penetration/extensions, and observation-direction-relative summaries where valid, plus pruning/status/provenance columns.

Only pairs fully internal to the observation contribute.

### Requirement: `observation_volume_volatility` uses canonical names

Primary key: `(observation_id,calculation_resolution)`.

Required columns include:

- coverage fields;
- `volume_sum`, `volume_mean`, `volume_median`;
- `volume_sum_change_vs_prev`, `volume_sum_ratio_vs_prev` for rolling where defined;
- `volume_body_up/down/flat` and shares;
- `volume_close_step_up/down/flat` and shares;
- approved effort-versus-result fields;
- `true_range_sum`, `true_range_mean`, `true_range_median`;
- `normalized_true_range_mean`;
- `atr14_sma_at_end`, `atr14_wilder_at_end`;
- `realized_variance`, `realized_volatility`, `realized_volatility_per_sqrt_day` only for fixed/rolling where defined;
- `observation_high_low_width`, `observation_high_low_width_pct_start`, `observation_log_high_low_width`;
- `mean_full_range`, `median_full_range`, `mean_log_full_range`, `median_log_full_range`;
- explicitly named current-vs-previous rolling deltas/ratios only for dictionary-declared components;
- pruning/status/provenance columns.

No semantic compression/expansion/accumulation/exhaustion labels are allowed.

### Requirement: `retracement_measurements` stores only explicitly configured approved A-B-C relationships

Row grain: one explicitly approved reference/candidate tuple `(A,B,C)`.
Primary key: `retracement_id`.

Required columns:

- `retracement_id`;
- `relationship_source_id`, `relationship_source_type`;
- `anchor_a_id`, `anchor_b_id`, `anchor_c_id`;
- A/B/C times and prices;
- anchor provenance and time-precision fields;
- `reference_delta`, `candidate_delta`;
- `candidate_vs_reference_pct`;
- `opposing_retracement_abs`;
- `retracement_pct`;
- `availability_class`, `available_at`;
- `metric_status`, `schema_version`, `run_id`.

The pipeline SHALL NOT generate arbitrary combinations of otherwise approved anchors. A tuple must itself be explicitly configured/approved as a relationship. If no production tuple list is configured, the canonical table may validly contain zero rows while G14 still tests the formula engine.

### Requirement: `macro_legs` preserves historical source provenance separately from canonical compatibility

Primary key: `macro_leg_id`.

Preserve all approved source columns plus:

- `macro_source_checksum`, `macro_observation_id`;
- source-vs-derived direction QA;
- for each start/end anchor: parent daily regime, refinement source timeframe/market, effective source class, anchor-time precision;
- `leg_source_classification` (`spot`, `futures`, `mixed`, `unknown`);
- canonical market type at each anchor wall-clock time;
- canonical source compatibility status;
- cross-canonical-boundary flag;
- source/canonical coverage status;
- `schema_version`, `run_id`.

Historical source provenance SHALL NOT be overwritten by current canonical market assignment.

### Requirement: `observation_macro_context` isolates retrospective macro relationships

Primary key: `(observation_id,macro_leg_id)`.

Required columns include temporal intersection, time fraction, endpoint-inside-leg, source/derived macro direction, elapsed/remaining/progress, approved macro-aligned speed/path/penetration fields, `availability_class=retrospective`, pruning/status/provenance fields.

It SHALL NOT be silently joined into causal-only extracts.

### Requirement: feature dictionary is canonical and complete

One row per materialized metric feature with logical table, feature name, meaning, formula, units, applicability, source/calculation-resolution semantics, fixed/rolling/macro semantics, availability/available-at, null meaning, provenance, schema version.

Canonical copy is Parquet; emit a small CSV review copy.

### Requirement: causal-only extraction is structurally enforceable

Causal extraction excludes macro observations/context and every retrospective feature; optional as-of filtering requires `available_at <= as_of`.

### Requirement: large feature tables repeat only pruning dimensions

Large observation feature tables repeat non-authoritative:

- `observation_kind`
- `market_type`
- `observation_end_year`.

They must equal `observation_index` values.

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
- `retracement_measurements`: unpartitioned unless material size later requires otherwise.

Small dimension tables remain unpartitioned.

Do not partition by `source_segment_id` in this pass.

Writers SHOULD target roughly 128-512 MB compressed parts where size permits and compact materially smaller fragments after successful stage validation.

### Requirement: manifests and run provenance are auditable

Every logical table carries `schema_version` and `run_id` or equivalent run provenance. Stable entity ids remain independent of run id.

Every logical table manifest records schema version, partition columns, part paths, row counts, time coverage, market types/resolutions, source-segment coverage where applicable, integrity evidence, producing run id, and validation status.

Extraction discovers canonical parts through manifests/catalog, never path guessing.
