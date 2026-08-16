# Research Table Schema Contract

## Purpose

Define the canonical logical tables, row grain, stable identifiers, join keys, availability classes, and physical partitioning for Structure Research v5 so implementation does not invent its own data model.

## ADDED Requirements

### Requirement: Stable identifiers use one deterministic UUIDv5 namespace

Stable entity identifiers SHALL use UUIDv5 with project namespace:

`87411ce4-8483-55b7-a348-700b7ad4b9ab`

Canonical identity strings SHALL use UTF-8, literal field separators `|`, UTC timestamps in ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`, and the exact normalized enum values recorded by the schema. Row order, local file path, download run, and mutable provenance SHALL NOT participate in identity unless explicitly stated.

Required identities:

- `source_segment_id = uuid5(namespace, "segment|{venue}|{instrument}|{market_type}|{segment_start_time}")`
- `gap_id = uuid5(namespace, "gap|{venue}|{instrument}|{market_type}|{gap_start_time}|{gap_end_time}")`
- `candle_id = uuid5(namespace, "candle|{venue}|{instrument}|{market_type}|{timeframe}|{start_time}")`
- fixed `observation_id = uuid5(namespace, "observation|fixed|{candle_id}")`
- rolling `observation_id = uuid5(namespace, "observation|rolling|{venue}|{instrument}|{market_type}|{rolling_duration}|{end_time}")`
- macro-leg `observation_id = uuid5(namespace, "observation|macro_leg|{macro_source_checksum}|{macro_leg_id}")`
- `pair_id = uuid5(namespace, "pair|{prev_candle_id}|{curr_candle_id}")`.

A provenance-only change SHALL NOT change candle identity. Repairing a historical gap MAY change source-segment membership and completeness but SHALL NOT create a new identity for an already existing candle timestamp.

### Requirement: Canonical enums are explicit

At minimum the first-pass schema SHALL use these normalized values:

- `venue`: `binance`
- `instrument`: `BTCUSDT`
- `market_type`: `spot`, `usdt_m_futures`
- `timeframe`: `1m`, `5m`, `15m`, `1H`, `4H`, `1D`
- `observation_kind`: `fixed`, `rolling`, `macro_leg`
- `availability_class`: `causal`, `retrospective`
- `direction`: `up`, `down`, `flat`
- `completeness_status`: `complete`, `incomplete_gap`, `incomplete_boundary`, `invalid`
- `provenance_kind`: source-accurate values including at minimum `native_kline`, `reconstructed_from_trades`, `reconstructed_from_aggtrades`, `derived_from_1m` where applicable.

Unknown or future enum values SHALL be explicit strings; they SHALL NOT be silently coerced into an existing value.

### Requirement: Logical table `source_segments` has one row per continuous market segment

Primary key: `source_segment_id`.

Required columns:

- `source_segment_id`
- `venue`
- `instrument`
- `market_type`
- `segment_start_time`
- `segment_end_time`
- `first_candle_id`
- `last_candle_id`
- `row_count`
- `segment_status`
- `start_reason`
- `end_reason`
- `source_contract_version`.

A new archive file or reconstructed same-market candle SHALL NOT by itself create a new segment. Real unresolved gaps and market-type changes SHALL.

### Requirement: Logical table `source_gaps` has one row per unresolved real gap

Primary key: `gap_id`.

Required columns:

- `gap_id`
- `venue`
- `instrument`
- `market_type`
- `gap_start_time`
- `gap_end_time`
- `missing_1m_count`
- `gap_reason`
- `recovery_attempted`
- `recovery_source`
- `recovered_1m_count`
- `recovery_status`
- `evidence_artifact`
- `left_source_segment_id`
- `right_source_segment_id`.

Irrecoverable Binance source gaps SHALL remain rows in this table rather than being represented by synthetic candles.

### Requirement: Logical table `candles_1m` is the narrow canonical source layer

Row grain: one canonical 1m interval for one market stream.

Primary key: `candle_id`.

Natural uniqueness SHALL be enforced on `(venue, instrument, market_type, timeframe, start_time)`.

Required columns:

- `candle_id`
- `venue`
- `instrument`
- `market_type`
- `source_segment_id`
- `timeframe` = `1m`
- `start_time`
- `end_time`
- `open`
- `high`
- `low`
- `close`
- `volume`
- optional source-native additive fields under source-accurate names such as `quote_volume`, `trade_count`, `taker_buy_base_volume`, `taker_buy_quote_volume`
- `source_id`
- `raw_artifact_id`
- `provenance_kind`
- `is_reconstructed`
- `validation_status`
- `completeness_status`
- `schema_version`
- `run_id`.

The 1m table SHALL NOT carry the complete heavy feature family.

### Requirement: Logical table `candles_fixed` contains all canonical 5m-and-higher fixed candles

Row grain: one fixed UTC candle at one target timeframe.

Primary key: `candle_id`.

Natural uniqueness SHALL be enforced on `(venue, instrument, market_type, timeframe, start_time)`.

Required columns:

- all identity/time/market columns needed to join the candle;
- `source_segment_id` when the complete candle belongs to one continuous segment;
- `timeframe` in `5m`, `15m`, `1H`, `4H`, `1D`;
- canonical `start_time`, `end_time`;
- complete `open`, `high`, `low`, `close`, `volume` or null when the target interval is incomplete;
- approved additive native-volume fields where valid;
- `construction_method` = `derived_from_1m` for the canonical first-pass representation;
- `source_calculation_resolution` = `1m`;
- `expected_constituent_count`;
- `observed_constituent_count`;
- `coverage_ratio`;
- `completeness_status`;
- optional explicitly named `observed_only_*` diagnostic OHLCV fields;
- `schema_version`;
- `run_id`.

Native higher-timeframe QA candles SHALL NOT be mixed into this canonical table as alternative rows for the same natural key.

### Requirement: 1m constituent membership is deterministic and need not be exploded into a mapping table

For a canonical fixed candle, its required 1m constituents SHALL be reconstructable by selecting canonical 1m candles with the same venue/instrument/market type/source continuity whose intervals lie within the target `[start_time,end_time)`.

Because this relationship is exact and potentially tens of millions of rows when exploded across every parent timeframe, the canonical store SHALL NOT be required to persist one explicit 1m-to-parent mapping row per constituent.

Target-candle expected/observed counts and coverage SHALL remain stored on `candles_fixed` and SHALL provide QA evidence that deterministic membership was evaluated.

### Requirement: Logical table `cross_timeframe_map` stores useful target-to-target containment

Row grain: one child fixed candle mapped to one containing larger target timeframe.

Primary key: `(child_candle_id, parent_timeframe)`.

Required columns:

- `child_candle_id`
- `child_timeframe`
- `parent_candle_id`
- `parent_timeframe`
- `venue`
- `instrument`
- `market_type`
- `source_segment_id`
- `child_start_time`
- `child_end_time`
- `child_ordinal_in_parent`
- `expected_child_count_in_parent`
- `observed_child_count_in_parent`
- `parent_coverage_ratio`
- `mapping_status`.

Persist mappings among target timeframes where the child is smaller than the parent: `5m -> 15m/1H/4H/1D`, `15m -> 1H/4H/1D`, `1H -> 4H/1D`, and `4H -> 1D`.

### Requirement: Logical table `observation_index` unifies fixed, rolling, and macro-leg observations

Row grain: one research observation interval.

Primary key: `observation_id`.

Required columns:

- `observation_id`
- `observation_kind`
- `venue`
- `instrument`
- `market_type` nullable only for a macro leg spanning more than one market type
- `source_segment_id` when fully contained in one segment, otherwise null
- `start_time`
- `end_time`
- `observation_end_year`
- `duration_seconds`
- `start_price`
- `end_price`
- `local_price_direction`
- `fixed_timeframe` nullable
- `rolling_duration` nullable
- `anchor_candle_id` nullable
- `macro_leg_id` nullable
- `macro_source_checksum` nullable
- `availability_class`
- `available_at`
- `expected_base_count`
- `observed_base_count`
- `coverage_ratio`
- `completeness_status`
- `schema_version`
- `run_id`.

Fixed observations SHALL correspond one-to-one with canonical target candles and SHALL be `causal` at candle `end_time` when complete.

Rolling observations SHALL be created on the canonical 5m evaluation grid for each approved duration `30m`, `1h`, `4h`, `12h`, `24h`, `3d`. Coarser calculation resolutions MAY contribute feature rows only at endpoints aligned to those resolutions; they SHALL reuse the same observation id for the same market interval rather than creating duplicate observations.

Macro-leg observations SHALL preserve the approved source anchors and SHALL be `retrospective`, with `available_at = macro_leg.end_time` for research bookkeeping. This SHALL NOT imply that the leg identity was known live at its end.

### Requirement: Rolling calculation-resolution matrix is explicit

The complete first-pass rolling feature matrix SHALL use every target calculation resolution that divides the rolling duration exactly and contributes at least two complete candles:

- `30m`: `5m`, `15m`
- `1h`: `5m`, `15m`
- `4h`: `5m`, `15m`, `1H`
- `12h`: `5m`, `15m`, `1H`, `4H`
- `24h`: `5m`, `15m`, `1H`, `4H`
- `3d`: `5m`, `15m`, `1H`, `4H`, `1D`.

This matrix SHALL apply to calculation-resolution-dependent path/activity, overlap, volume, and realized-volatility families where the metric is meaningful. A calculation resolution SHALL NOT be omitted from this approved matrix merely for convenience or performance without explicit approval.

Rolling observation identity remains based on market interval, not calculation resolution. Multiple calculation-resolution rows SHALL join to the same `observation_id`.

### Requirement: Large feature tables denormalize only pruning dimensions

To make direct Parquet filtering efficient without a mandatory join to `observation_index`, every large observation feature table SHALL repeat these non-authoritative pruning columns:

- `observation_kind`
- `market_type` nullable only for cross-market retrospective macro observations
- `observation_end_year`.

These repeated columns SHALL equal the corresponding `observation_index` values and SHALL be validated as such. They are physical/query conveniences and SHALL NOT redefine observation identity or semantics.

### Requirement: Logical table `observation_price_speed` stores one non-resolution-specific geometry/speed row per observation

Row grain: one `observation_id`.

Primary key: `observation_id`.

Required columns:

- `observation_id`
- pruning columns `observation_kind`, `market_type`, `observation_end_year`
- `signed_price_change`
- `absolute_price_change`
- `signed_return_pct`
- `absolute_return_pct`
- `signed_log_move`
- `absolute_log_move`
- `raw_signed_speed_pct_per_hour`
- `signed_log_speed_per_hour`
- `absolute_log_speed_per_hour`
- `local_direction_normalized_speed_pct_per_hour` where defined
- `local_direction_normalized_log_speed_per_hour` where defined
- for rolling observations, previous-adjacent-window `speed_change_pct_per_hour` and `acceleration_pct_per_hour2` plus explicitly log-named companions where defined
- `metric_status`
- `schema_version`
- `run_id`.

Because each rolling row already has exactly one `rolling_duration` in `observation_index`, speed-change column names SHALL NOT encode the duration redundantly; the observation join supplies that duration.

Macro-direction-aligned versions for causal fixed/rolling observations SHALL NOT be stored in this causal/local table; they belong to retrospective macro-context data.

### Requirement: Logical table `observation_path_activity` is keyed by observation and calculation resolution

Row grain: one `(observation_id, calculation_resolution)`.

Primary key: `(observation_id, calculation_resolution)`.

Required columns SHALL include:

- `observation_id`
- pruning columns `observation_kind`, `market_type`, `observation_end_year`
- `calculation_resolution`
- `expected_constituent_count`
- `observed_constituent_count`
- `coverage_ratio`
- `close_path`
- `log_close_path`
- `path_efficiency`
- `log_path_efficiency`
- `upward_close_path`
- `downward_close_path`
- approved log upward/downward path companions
- `path_with_local_direction`
- `path_against_local_direction`
- `counter_local_path_share`
- approved log local-direction path companions
- `nonzero_step_count`
- `zero_step_count`
- `zero_step_share`
- `sign_change_count`
- `alternation_rate`
- `sum_full_range`
- `sum_body_size`
- `sum_upper_wick`
- `sum_lower_wick`
- `sum_true_range`
- approved log/normalized activity sums
- `observation_high`
- `observation_low`
- `high_first_time`
- `high_last_time`
- `high_occurrence_count`
- `low_first_time`
- `low_last_time`
- `low_occurrence_count`
- `upward_excursion_abs`
- `downward_excursion_abs`
- `upward_excursion_pct`
- `downward_excursion_pct`
- approved log excursion fields
- `metric_status`
- `schema_version`
- `run_id`.

Complete path/activity metrics SHALL be null when required constituent coverage is incomplete. Any observed-only diagnostics SHALL use explicit names and SHALL NOT replace complete metrics.

### Requirement: Logical table `atomic_candle_pairs` preserves pair geometry independently of later observation direction

Row grain: one chronological neighbor candidate at one calculation resolution.

Primary key: `pair_id`.

Required columns:

- `pair_id`
- `prev_candle_id`
- `curr_candle_id`
- `calculation_resolution`
- `venue`
- `instrument`
- `market_type`
- `observation_end_year` defined as `curr_start_time.year` for physical partitioning
- `prev_source_segment_id`
- `curr_source_segment_id`
- `prev_start_time`
- `prev_end_time`
- `curr_start_time`
- `curr_end_time`
- `pair_eligible`
- `ineligibility_reason` nullable
- all approved range-overlap absolute/prev/current/Jaccard fields
- approved overlap-position fields
- all approved body-overlap fields
- upper/lower extension absolute/share fields
- neutral mirrored extreme/body/close/wick-only penetration-from-top and penetration-from-bottom fields and shares
- `schema_version`
- `run_id`.

If a chronological neighbor candidate crosses a real gap or source boundary, the row MAY be retained for boundary QA with `pair_eligible=false`; sequential geometry metrics that would imply continuity SHALL be null. Eligible feature aggregation SHALL use only `pair_eligible=true` rows.

### Requirement: Logical table `observation_overlap_summary` stores full-path overlap evolution

Row grain: one `(observation_id, calculation_resolution)` where pair aggregation is defined.

Primary key: `(observation_id, calculation_resolution)`.

Required columns SHALL include:

- `observation_id`
- pruning columns `observation_kind`, `market_type`, `observation_end_year`
- `calculation_resolution`
- `eligible_pair_count`
- `expected_pair_count`
- `pair_coverage_ratio`
- `any_overlap_share`
- mean and median `overlap_share_prev`
- mean and median `overlap_share_curr`
- mean and median `overlap_jaccard`
- mean and median approved body-overlap normalizations
- mean and median approved neutral penetration/extension shares
- observation-direction-relative `against_move` penetration/extension summaries where the observation direction is valid
- `metric_status`
- `schema_version`
- `run_id`.

Only pairs fully internal to the observation interval SHALL contribute to its ordinary overlap summary. A pair crossing the observation start boundary SHALL not be silently included as an internal pair.

### Requirement: Logical table `observation_volume_volatility` is keyed by observation and calculation resolution

Row grain: one `(observation_id, calculation_resolution)`.

Primary key: `(observation_id, calculation_resolution)`.

Required columns SHALL include:

- `observation_id`
- pruning columns `observation_kind`, `market_type`, `observation_end_year`
- `calculation_resolution`
- expected/observed constituent counts and `coverage_ratio`
- `volume_sum`
- `volume_mean`
- `volume_median`
- previous-equal-window `volume_delta`
- previous-equal-window `volume_ratio`
- `volume_body_up`, `volume_body_down`, `volume_body_flat`
- `volume_body_up_share`, `volume_body_down_share`, `volume_body_flat_share`
- `volume_close_step_up`, `volume_close_step_down`, `volume_close_step_flat`
- `volume_close_step_up_share`, `volume_close_step_down_share`, `volume_close_step_flat_share`
- approved effort-versus-result numeric fields
- `true_range_sum`, `true_range_mean` where meaningful for the observation
- `atr14_sma_at_end`
- `atr14_wilder_at_end`
- `realized_variance`
- `realized_volatility`
- `realized_volatility_per_sqrt_day`
- `rolling_high_low_width`
- `mean_candle_range`
- `median_candle_range`
- current-versus-previous equal-window range/TR/ATR numeric delta/ratio fields required by the compression/expansion contract
- `metric_status`
- `schema_version`
- `run_id`.

The table SHALL contain numeric measurements only and SHALL NOT contain semantic accumulation/distribution/absorption/exhaustion/compression/expansion labels.

### Requirement: Logical table `observation_macro_context` isolates retrospective macro information from causal feature tables

Row grain: one `(observation_id, macro_leg_id)` relationship where a fixed/rolling observation intersects or is evaluated relative to an approved macro leg.

Primary key: `(observation_id, macro_leg_id)`.

Required columns:

- `observation_id`
- pruning columns `observation_kind`, `market_type`, `observation_end_year`
- `macro_leg_id`
- `macro_observation_id`
- `intersection_start_time`
- `intersection_end_time`
- `intersection_duration_seconds`
- `observation_time_fraction_inside_leg`
- `endpoint_inside_leg`
- `macro_source_direction`
- `macro_price_derived_direction`
- `elapsed_time_from_leg_start`
- `remaining_time_to_leg_end`
- `leg_time_progress`
- approved macro-direction-aligned speed/path/penetration fields when calculated
- `availability_class` = `retrospective`
- `schema_version`
- `run_id`.

This table SHALL NOT be silently joined into a causal-only strategy research extract.

### Requirement: Macro-leg source identity remains queryable directly

The canonical analytical store SHALL retain a small `macro_legs` table with one row per approved source leg.

Primary key: `macro_leg_id`.

Required columns SHALL preserve the approved `macro_legs_log20.csv` fields without semantic relabeling, plus:

- `macro_source_checksum`
- `macro_observation_id`
- price-derived direction QA fields
- `start_anchor_market_type`
- `end_anchor_market_type`
- `cross_source_boundary`
- coverage status by canonical research source where needed
- `schema_version`
- `run_id`.

The original source columns SHALL remain distinguishable from recomputed research fields. For a macro leg spanning spot and futures, its `observation_index.market_type` and `source_segment_id` SHALL be null while start/end anchor market types remain explicit here.

### Requirement: Feature dictionary is a canonical table with a human CSV copy

The canonical `feature_dictionary` SHALL contain one row per exported feature column with at minimum:

- `logical_table`
- `feature_name`
- `human_meaning`
- `formula_or_derivation`
- `units`
- `observation_kind_applicability`
- `source_resolution`
- `calculation_resolution_semantics`
- `fixed_or_rolling_semantics`
- `availability_class`
- `available_at_rule`
- `null_meaning`
- `provenance`
- `schema_version`.

The canonical copy SHALL be Parquet; a CSV review copy SHALL also be emitted because this table is small and intended for human inspection.

### Requirement: Causal-only extraction is structurally enforceable

An extraction request for `availability_class=causal` SHALL:

- exclude `macro_leg` observations from `observation_index`;
- exclude `observation_macro_context`;
- exclude feature columns whose feature-dictionary availability is retrospective;
- include only rows whose `available_at <= requested_as_of_time` when an as-of time is supplied.

A field becoming known at the close of a fixed/rolling observation MAY be causal from that close onward; it SHALL NOT be exposed at timestamps before its `available_at`.

### Requirement: Canonical partitioning avoids both monoliths and tiny-file explosion

Canonical Parquet SHALL use Zstandard compression.

Physical partitioning SHALL be:

- `candles_1m`: `market_type / year / month` derived from `start_time`;
- `candles_fixed`: `timeframe / market_type / year` derived from `start_time`;
- `cross_timeframe_map`: `child_timeframe / market_type / year` derived from child start time;
- `observation_index`: `observation_kind / market_type / observation_end_year`, with cross-market macro observations stored under explicit physical partition value `cross_market` while logical `market_type` remains null;
- `observation_price_speed`: `observation_kind / market_type / observation_end_year`;
- `observation_path_activity`: `calculation_resolution / market_type / observation_end_year`;
- `atomic_candle_pairs`: `calculation_resolution / market_type / observation_end_year`;
- `observation_overlap_summary`: `calculation_resolution / market_type / observation_end_year`;
- `observation_volume_volatility`: `calculation_resolution / market_type / observation_end_year`;
- `observation_macro_context`: `market_type / observation_end_year`.

Small dimension tables such as `source_segments`, `source_gaps`, `macro_legs`, and `feature_dictionary` SHALL remain unpartitioned unless size later justifies partitioning.

`source_segment_id` SHALL remain a predicate/filter column but SHALL NOT be a physical partition key in this first pass, because real historical gaps could otherwise create excessive small partitions.

Within a partition, writers SHALL target reasonably large Parquet parts rather than one file per observation/day. Implementations SHOULD target approximately 128-512 MB compressed files where table size permits and SHOULD compact materially smaller fragments after successful stage completion.

### Requirement: Run provenance does not become entity identity

Every canonical table SHALL carry `schema_version` and `run_id` or equivalent table/run provenance.

Stable entity ids SHALL remain independent of `run_id`. Re-running the same approved inputs/configuration SHALL reproduce the same entity ids and natural keys while allowing QA to distinguish which run produced a physical artifact.

### Requirement: Canonical table manifests make the schema auditable

Each logical table SHALL have manifest metadata recording at minimum:

- logical table name;
- schema version;
- physical partition columns;
- part paths;
- row counts;
- min/max time coverage;
- market types;
- timeframes/calculation resolutions where applicable;
- source-segment coverage;
- checksum or equivalent integrity evidence where feasible;
- producing run id;
- validation status.

The extraction utility SHALL discover canonical parts through these manifests or an equivalent deterministic catalog rather than relying on directory guessing.
