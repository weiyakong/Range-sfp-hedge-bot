# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure that one approved research run leaves enough atomic market data and whole-leg measurements across the full locally available BTC history to investigate market movement behavior later without rerunning source-data collection or inventing missing semantics.

## ADDED Requirements

### Requirement: Production coverage uses the full locally available history

The first production research dataset SHALL target the full approved BTC history made available for the project from the earliest approved source timestamp through the latest approved source timestamp, subject to source coverage and integrity.

The pipeline SHALL NOT impose `2023-01-01` or `2024-01-01` as collection or dataset-coverage cutoffs.

The periods `2023-01-01` onward and especially `2024-01-01` onward MAY receive higher priority during later analytical comparison, smoke review, and criteria research, but this analytical prioritization SHALL remain separate from source inventory and production dataset coverage.

### Requirement: Canonical 1m source layer is retained without requiring full 1m feature materialization

The approved canonical `1m` OHLCV source history SHALL remain queryable as the finest candle layer used to construct and validate research timeframes.

The retained canonical `1m` layer SHALL preserve at minimum candle identity, market type, source/source-segment identity, UTC interval, OHLC, source-native volume, provenance, completeness, and gap status.

The first production pass SHALL NOT be required to materialize the full heavy feature family on every 1m candle. `1m` is primarily the reproducible source/drill-down layer; full-market feature production MAY begin at `5m` unless a feature explicitly requires finer calculation.

### Requirement: Atomic target-candle records are retained

For target resolutions `5m`, `15m`, `1H`, `4H`, and `1D`, the research store SHALL retain a queryable candle-level table sufficient to recompute later derived features without rerunning market-data download.

Each candle record SHALL contain at minimum:

- stable candle identifier;
- instrument/symbol identity;
- venue/market-source identity;
- market type;
- `source_segment_id`;
- timeframe/resolution;
- canonical UTC `start_time` and exclusive `end_time`;
- `open`, `high`, `low`, `close`;
- source-native/additively derived volume where valid;
- source/provenance identifier;
- whether the candle is source-native or derived;
- source calculation resolution when derived;
- expected constituent count;
- observed constituent count;
- coverage ratio;
- completeness/gap status.

The final research dataset SHALL NOT replace this atomic layer with derived feature tables only.

### Requirement: Target candles are deterministically derived from canonical finer candles when configured

For a target interval built from complete same-source canonical finer candles ordered by time:

- `open = first constituent open`
- `high = max(constituent high)`
- `low = min(constituent low)`
- `close = last constituent close`
- additive source-native volume fields SHALL be summed according to the volume/provenance contract.

A derived target candle SHALL contain only constituent candles from one `source_segment_id` and SHALL NOT cross the spot/futures boundary or another source-segment boundary.

Expected constituent counts on a complete 1m basis are:

- `5m`: 5
- `15m`: 15
- `1H`: 60
- `4H`: 240
- `1D`: 1440.

If any required constituent candle is missing, the target interval MAY be retained for diagnostics with its observed OHLC aggregation and explicit incomplete coverage, but it SHALL NOT be marked complete and SHALL NOT silently substitute/interpolate the missing candle. Any observed-only derived values SHALL be explicitly distinguishable from complete target-candle values.

### Requirement: Source construction method is explicit before the full run

The implementation SHALL record for each target resolution whether candles are read directly from a native approved local source or deterministically aggregated from the canonical finer source.

The source map SHALL identify source artifact/path or stable source identifier, source timeframe, target timeframe, venue/instrument identity, market type, source-segment identity, construction method, first timestamp, last timestamp, and known coverage limitations.

The pipeline SHALL NOT silently choose between native and aggregated candles when both or neither are available. When derived candles are the canonical research representation, native higher-timeframe sources MAY be used as QA references without replacing provenance.

### Requirement: Canonical candle timestamps have explicit semantics

For every source used, the implementation SHALL establish whether a source timestamp denotes candle open/start, source-reported close timestamp, or another convention and SHALL convert it deterministically to canonical UTC `[start_time, end_time)` intervals without shifting the market interval.

Source-native timestamp fields MAY be retained separately for provenance, but canonical `end_time` SHALL always be the exclusive interval boundary used for containment and rolling logic.

### Requirement: Approved macro-leg source is explicit

The first-pass whole-leg research SHALL use the approved `macro_legs_log20.csv` dataset as the macro-leg anchor source unless the user explicitly approves a replacement.

The macro-leg source SHALL be supplied by exact configured path or immutable source identifier; the pipeline SHALL NOT discover or substitute another similarly named macro/swing/parent file automatically.

For the currently approved reference copy, the expected content includes 128 macro-leg rows and columns for `leg_id`, `direction`, start/end event ids, start/end times, start/end prices, ordinary/log movement, and duration. A source fingerprint/checksum SHALL be recorded in run provenance before processing. The known reference SHA-256 of the reviewed uploaded copy is `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`; a different configured source SHALL require explicit provenance review rather than silent acceptance as the same input.

### Requirement: Whole macro-leg measurements are first-class retrospective research outputs

For every approved existing macro leg overlapping available approved candle coverage, the system SHALL calculate a whole-leg measurement record in addition to fixed-calendar and rolling observations.

The whole-leg record SHALL preserve at minimum anchors, duration, ordinary/log movement and speed, multi-resolution path and efficiencies, directional path components, alternation, overlap summaries, candle activity, volume/volatility summaries, and explicit coverage status.

All measurements that depend on the known macro-leg endpoint or the direction of the completed whole leg SHALL be marked `retrospective`. They SHALL NOT be exposed to live-strategy research as though they were known before the macro leg completed.

No whole-leg record SHALL assign a new semantic `impulse` or `correction` class.

### Requirement: Macro-leg close-path uses source anchors explicitly

For a macro leg with source anchors `(T0, P0)` and `(T1, P1)` and an approved finer candle resolution, the system SHALL distinguish internal finer-close path from anchor-inclusive path.

`internal_close_path` SHALL sum absolute changes between chronologically consecutive eligible finer closes inside one continuous source segment whose close/end timestamps lie after `T0` and at or before `T1`.

`anchor_inclusive_close_path` SHALL additionally include the transition from `P0` to the first eligible finer close and from the last eligible finer close to `P1` when those anchor transitions are valid within the same source semantics and are not already represented by the same observed price point.

A macro leg that intersects a source boundary SHALL NOT bridge that boundary as one complete path. Per-segment partial measurements MAY be retained with explicit coverage, while complete whole-leg path metrics SHALL be null unless a later approved contract defines a justified cross-source treatment.

### Requirement: Gaps cannot masquerade as valid path

A missing expected finer candle SHALL NOT be bridged silently as though surrounding closes were consecutive observations of a complete path.

For every path-dependent observation, the system SHALL preserve expected finer-bar count, observed finer-bar count, coverage ratio, and gap status.

Complete-path metrics and efficiency SHALL be null when required constituent coverage is incomplete, unless a separately named `observed_only_*` diagnostic is produced and marked incomplete.

### Requirement: Whole-leg overlap summaries remain reconstructable from atomic pairs

For each supported calculation resolution, pairwise candle-overlap records SHALL remain atomic and timestamped so that a macro leg or arbitrary later interval can be reaggregated without rerunning market-data collection.

Where complete pair coverage exists inside a macro leg, the whole-leg output SHALL include separately named summaries of `overlap_share_prev`, `overlap_share_curr`, `overlap_jaccard`, `any_overlap_share`, and approved mirrored/observation-relative penetration and extension fields.

The contributing pair count and coverage status SHALL be retained.

### Requirement: Modern contrast cases are directly extractable without limiting historical storage

The extraction layer SHALL support selecting complete whole-leg records and their underlying atomic candles/pairs by `macro_leg_id`, including multiple macro legs in one request.

This SHALL make it possible to prioritize modern cases with similar absolute log movement but materially different duration/path behavior while retaining full historical data for robustness and comparison.
