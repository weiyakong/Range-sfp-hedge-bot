# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure that one approved research run leaves enough atomic market data and whole-leg measurements across the full locally available BTC history to investigate market movement behavior later without rerunning source-data collection or inventing missing semantics.

## ADDED Requirements

### Requirement: Production coverage uses the full locally available history

The first production research dataset SHALL target the full approved local BTC history from the earliest locally available timestamp through the latest locally available timestamp for each approved source/timeframe, subject to actual source coverage and integrity.

The pipeline SHALL NOT impose `2023-01-01` or `2024-01-01` as collection or dataset-coverage cutoffs.

The periods `2023-01-01` onward and especially `2024-01-01` onward MAY receive higher priority during later analytical comparison, smoke review, and criteria research, but this analytical prioritization SHALL remain separate from source inventory and production dataset coverage.

No additional market data SHALL be downloaded without explicit approval.

### Requirement: Atomic target-candle records are retained

For every available target resolution (`1D`, `4H`, `1H`, `15m`, `5m`), the research store SHALL retain a queryable candle-level table sufficient to recompute later derived features without rerunning the source-data engine.

Each candle record SHALL contain at minimum:

- stable candle identifier;
- instrument/symbol identity;
- venue/market-source identity;
- market type where relevant (for example spot or futures);
- timeframe/resolution;
- canonical UTC `start_time` and `end_time`;
- `open`, `high`, `low`, `close`;
- source-native volume when available;
- source/provenance identifier;
- whether the candle is source-native or derived from another approved resolution;
- coverage/completeness status where applicable.

Optional source-native fields such as quote volume, trade count, or taker-side volume SHALL retain source-accurate names if preserved.

The final research dataset SHALL NOT replace this atomic layer with derived feature tables only.

### Requirement: Source construction method is explicit before the full run

After source inventory and before the full production run, the implementation SHALL record for each target resolution whether candles are read directly from a native local source or deterministically aggregated from an approved finer local source.

The source map SHALL identify at minimum source artifact/path or stable source identifier, source timeframe, target timeframe, venue/instrument identity, construction method, first timestamp, last timestamp, and known coverage limitations.

The pipeline SHALL NOT silently choose between native and aggregated candles when both or neither are available.

### Requirement: Canonical candle timestamps have explicit semantics

For every source used, the implementation SHALL establish whether the source timestamp denotes candle open/start, candle close/end, or another source convention and SHALL convert it deterministically to canonical UTC `start_time` and `end_time` without shifting the market interval.

Timestamp semantics SHALL be recorded in provenance and tested on representative source rows.

### Requirement: Whole macro-leg measurements are first-class research outputs

For every approved existing macro leg overlapping available approved candle coverage, the system SHALL calculate a whole-leg measurement record in addition to fixed-calendar and rolling observations.

The whole-leg record SHALL preserve at minimum:

- macro-leg source identifier;
- start/end anchors and source prices;
- duration;
- signed and absolute ordinary return;
- signed and absolute log move;
- ordinary and log speed;
- available internal path and log-path measurements at each approved finer resolution;
- ordinary and log path efficiency at each approved finer resolution;
- directional/counter-direction path components;
- alternation measurements;
- whole-leg overlap summaries where the required candle coverage exists;
- whole-leg candle-activity summaries;
- whole-leg volume and volatility summaries where supported by source coverage;
- explicit coverage status for every resolution-dependent family.

No whole-leg record SHALL assign a new semantic `impulse` or `correction` class.

### Requirement: Macro-leg close-path uses source anchors explicitly

For a macro leg with source anchors `(T0, P0)` and `(T1, P1)` and an approved finer candle resolution, the system SHALL distinguish internal finer-close path from anchor-inclusive path.

`internal_close_path` SHALL sum absolute changes between chronologically consecutive eligible finer closes whose close/end timestamps lie after `T0` and at or before `T1`.

`anchor_inclusive_close_path` SHALL additionally include the transition from `P0` to the first eligible finer close and from the last eligible finer close to `P1` when those anchor transitions are not already represented by the same observed price point.

Equivalent log versions SHALL use absolute log price ratios for strictly positive prices.

Whole-leg path efficiency SHALL use the anchor-inclusive path so that its numerator and denominator refer to the same source start/end anchors.

The output SHALL identify the finer calculation resolution and whether anchor transitions were added.

### Requirement: Gaps cannot masquerade as valid path

A missing expected finer candle SHALL NOT be bridged silently as though the two surrounding closes were consecutive observations of a complete path.

For every path-dependent observation, the system SHALL preserve expected finer-bar count, observed finer-bar count, coverage ratio, and gap status.

A complete-path metric and its efficiency SHALL be null when required constituent coverage is incomplete, unless a separately named `observed_only_*` diagnostic is explicitly produced.

Any `observed_only_*` path SHALL be marked incomplete and SHALL NOT be used interchangeably with the complete-path metric.

### Requirement: Whole-leg overlap summaries remain reconstructable from atomic pairs

For each supported calculation resolution, pairwise candle-overlap records SHALL remain atomic and timestamped so that a macro-leg or arbitrary later interval can be reaggregated from them without rerunning market-data collection.

Where complete pair coverage exists inside a macro leg, the whole-leg output SHALL include at minimum mean and median canonical normalized range overlap, `any_overlap_share`, and summaries of the approved direction-aware penetration/extension fields.

The contributing pair count and coverage status SHALL be retained.

### Requirement: Modern contrast cases are directly extractable without limiting historical storage

The extraction layer SHALL support selecting complete whole-leg records and their underlying atomic candles/pairs by `macro_leg_id`, including multiple macro legs in one request.

This SHALL make it possible to prioritize modern cases with similar absolute log movement but materially different duration/path behavior while retaining the full historical dataset for robustness and comparison.
