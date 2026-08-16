# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure that one approved research run leaves enough atomic market data and whole-leg measurements across the full approved BTC history to investigate movement behavior later without rerunning market-data download or inventing missing semantics.

## ADDED Requirements

### Requirement: Production coverage uses the full approved history

The first production research dataset SHALL target the full approved BTC history from the earliest approved source timestamp through the latest approved source timestamp, subject to actual coverage and integrity.

The pipeline SHALL NOT impose `2023-01-01` or `2024-01-01` as collection cutoffs. Those periods MAY receive higher analytical priority later without reducing stored historical coverage.

### Requirement: Source segment means canonical 1m market continuity, not file provenance or target timeframe

Every canonical 1m candle SHALL carry row-level provenance and a `source_segment_id`.

`source_segment_id` SHALL identify one temporally continuous sequence of canonical 1m candles for the same venue, instrument, and market type. It is defined on the canonical 1m market spine and inherited by complete target candles/observations that lie wholly within one such segment.

It SHALL NOT change merely because:

- a new monthly/daily archive file begins;
- a different local path stores the next raw part;
- a candle was downloaded in a different run;
- row-level provenance changes while canonical market continuity remains valid.

A new source segment SHALL begin when continuity is genuinely broken, including at minimum:

- spot -> futures or futures -> spot market-type transition;
- venue or instrument change;
- unresolved real canonical 1m gap;
- another explicitly documented discontinuity that makes sequential calculations invalid.

A synthetic diagnostic bucket whose OHLC is not observed from approved source data SHALL NOT repair canonical continuity merely because it fills a timestamp.

### Requirement: Canonical 1m source layer is retained without heavy 1m feature materialization

The approved canonical `1m` OHLCV history SHALL remain queryable as the finest candle source/drill-down layer.

Each retained 1m candle SHALL preserve at minimum stable candle identity, symbol/instrument, venue, market type, `source_segment_id`, canonical UTC `[start_time,end_time)`, OHLC, source-native volume, row-level provenance, validation status, and completeness/gap status.

Every canonical 1m start SHALL be exactly minute-grid aligned. Non-minute-aligned source rows SHALL be explicitly validated/classified rather than silently rounded into canonical candles.

The first production pass SHALL NOT be required to materialize the complete heavy feature family on every 1m candle. Full-market feature production SHALL begin at `5m` unless a separately approved feature requires 1m calculation.

### Requirement: Canonical target candles are deterministically derived from canonical 1m

For this first-pass research dataset, canonical `5m`, `15m`, `1H`, `4H`, and `1D` candle intervals SHALL be deterministically evaluated from the strict canonical `1m` spine.

Existing native/local higher-timeframe candle datasets SHALL be treated as QA/reference sources only and SHALL NOT silently replace the canonical 1m-derived representation.

A different canonical construction source requires explicit user approval and a source-contract update.

### Requirement: Complete target-candle aggregation has exact formulas

For a target interval whose complete expected 1m constituents are present, temporally aligned, and all belong to one source segment:

- `open = first constituent open`
- `high = max(constituent high)`
- `low = min(constituent low)`
- `close = last constituent close`
- additive volume/native additive fields SHALL follow the volume contract.

Expected 1m constituent counts are:

- `5m`: 5
- `15m`: 15
- `1H`: 60
- `4H`: 240
- `1D`: 1440.

Each target row SHALL preserve expected count, observed valid canonical count, coverage ratio, source scope, and completeness state.

### Requirement: Boundary-crossing and gap-containing target intervals remain explicit rows but cannot masquerade as candles from one market

The fixed UTC grid SHALL remain complete as an interval index even where a target interval intersects:

- the spot-to-futures market boundary;
- an unresolved canonical source gap;
- more than one source segment.

Such a row SHALL be retained with `completeness_status` such as `incomplete_boundary` or `incomplete_gap`, logical `market_type = cross_market` where more than one market type contributes to the interval, and `source_segment_id = null`.

Complete canonical OHLC/volume fields used by the research feature pipeline SHALL be null for any incomplete interval.

For diagnostics, explicitly named `observed_only_*` values MAY be retained from actual observed constituents, but SHALL never be consumed interchangeably with complete canonical candle fields.

No interpolation or synthetic constituent candle is permitted.

### Requirement: Atomic target-candle records remain queryable

For canonical target resolutions `5m`, `15m`, `1H`, `4H`, and `1D`, the analytical store SHALL retain queryable candle-level rows sufficient to inspect/recompute later features without rerunning market-data download.

Each row SHALL contain at minimum:

- stable candle identifier;
- instrument/symbol;
- venue;
- market type/source scope;
- `source_segment_id` when single-segment complete;
- timeframe;
- canonical `start_time` and exclusive `end_time`;
- complete OHLC/volume when valid;
- construction/provenance identifier;
- source calculation resolution (`1m`);
- expected/observed constituent counts;
- coverage ratio;
- completeness/gap/boundary status.

### Requirement: Source construction map is explicit

Before full production, run provenance SHALL record the exact canonical 1m source artifacts/manifest and the deterministic 1m->target construction contract, including venue, instrument, market type, source segments, first/last timestamps, known gaps, and schema/version.

Native higher-timeframe QA sources MAY be listed separately, clearly marked as diagnostic or validated QA references, and SHALL NOT be confused with canonical target-candle provenance.

### Requirement: Canonical timestamp semantics are explicit

Source-native timestamp fields MAY be retained as provenance, but canonical candles SHALL use UTC half-open `[start_time,end_time)` intervals according to the approved time-grid contract.

Canonical interval boundaries SHALL be deterministic and independent of source representations such as inclusive `close_time = ...59.999`.

### Requirement: Approved macro-leg source is explicit

Whole-leg research SHALL use the approved `macro_legs_log20.csv` anchor dataset unless the user explicitly approves a replacement.

It SHALL be supplied by exact configured path or immutable identifier; the pipeline SHALL NOT search for or substitute similarly named macro/swing/parent files.

The reviewed reference has 128 rows with `leg_id`, direction, start/end event ids, start/end times/prices, ordinary/log movement, and duration fields. Run provenance SHALL record a source checksum. The reviewed reference SHA-256 is:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

A different checksum/source requires explicit provenance review before it may be treated as the same approved anchor input.

### Requirement: Macro source provenance is historical source provenance, not reassignment by the new canonical boundary

The approved `macro_legs_log20.csv` was built from an older mixed research source and SHALL preserve that provenance as originally constructed.

The forensic audit establishes:

- old merged daily source remained spot through `2019-12-30T00:00:00Z`;
- old merged daily source switched to futures at `2019-12-31T00:00:00Z`;
- the macro build also used futures 4H refinement beginning in September 2019;
- audited Oct-Nov 2019 refined anchor timestamps/prices match futures 4H rows while their parent daily rows remain from the old spot daily regime.

Therefore disputed Sep-Dec 2019 macro source provenance SHALL be represented as `mixed` where applicable, including explicit parent-daily regime and refinement-source fields. Those anchors SHALL NOT be relabeled as pure spot or pure futures solely from the Structure Research v5 canonical boundary.

Canonical market type covering the same wall-clock time is a separate research attribute.

### Requirement: Macro anchor time precision is explicit

A refined macro anchor whose timestamp equals a 4H candle start while its anchor price is that candle's high/low SHALL be described as a `4H_bucket` or equivalent resolution-limited anchor time, not an exact tick-time extreme.

For each macro anchor preserve at minimum where known:

- source parent regime;
- refinement source market/timeframe;
- anchor timestamp;
- anchor price;
- anchor-time precision/class;
- compatibility with the current canonical market source.

A 4H bucket-start timestamp SHALL NOT be interpreted as proof that the high/low occurred at the start of the 4H candle.

### Requirement: Whole macro-leg measurements are first-class retrospective outputs

For every approved macro leg overlapping approved candle coverage, the system SHALL preserve the source anchors, duration, ordinary/log movement and speed, and shall calculate retrospective whole-leg descriptive measurements where their required canonical coverage and anchor semantics are valid.

Supported whole-leg families include internal multi-resolution path/efficiency, directional path components, alternation, overlap/penetration summaries, candle activity, and volume/volatility summaries where explicitly defined by the relevant formula/matrix contracts.

Measurements that depend on the known macro-leg endpoint or whole-leg direction SHALL be explicitly `retrospective` and SHALL NOT be exposed as live-available features.

No new semantic `impulse` or `correction` class is permitted.

### Requirement: Macro internal canonical path is separate from source-anchor movement

For a macro leg `(T0,P0)->(T1,P1)` and an approved finer calculation resolution, preserve:

1. source macro movement between the approved source anchor prices;
2. canonical internal close path constructed only from chronologically eligible complete canonical candles whose intervals lie within the macro observation;
3. anchor-inclusive canonical path only when both anchor market/source compatibility and temporal precision make the ordering valid.

Internal canonical path SHALL never bridge a source-segment boundary or unresolved gap. If the required whole-leg sequence crosses one, complete whole-leg path/efficiency at that resolution SHALL be null; per-segment diagnostics MAY be retained separately.

### Requirement: Anchor-inclusive macro path requires proven ordering, not merely matching market name

Anchor-inclusive path SHALL add `P0 -> first eligible canonical close` and `last eligible canonical close -> P1` only when BOTH endpoint anchors satisfy all of the following:

- the anchor price source is compatible with the canonical market source used for that endpoint/path;
- the anchor time is exact enough to establish ordering relative to the canonical constituent sequence;
- the anchor transition is not already represented by the same observed point;
- no source gap/boundary is crossed by that transition.

A macro anchor known only as a high/low somewhere inside a 4H bucket, while timestamped at the bucket start, does NOT satisfy exact ordering for finer anchor-inclusive path. In that case:

- source macro displacement remains valid as source measurement;
- internal canonical path may remain valid where coverage permits;
- anchor-inclusive canonical path/efficiency SHALL be null with explicit status such as `anchor_time_precision_insufficient`.

A mixed historical source anchor likewise SHALL NOT be forced into anchor-inclusive canonical path unless compatibility is explicitly established.

Equivalent log path SHALL use absolute log ratios for strictly positive prices.

### Requirement: Macro volatility applicability is explicit

Macro observations MAY receive volume/activity/overlap summaries from complete canonical constituents according to the approved feature matrix.

Realized variance/volatility for macro observations is NOT a required first-pass canonical feature unless a separate approved formula defines its exact boundary-price sequence independently of the source macro anchors. The fixed/rolling RV formula SHALL NOT be silently reused for macro legs with resolution-limited/mixed source anchors.

### Requirement: Gaps cannot masquerade as valid path

Every path-dependent observation SHALL preserve expected finer count, observed finer count, coverage ratio, and gap/boundary status.

Complete path/efficiency SHALL be null with incomplete required coverage. Any `observed_only_*` path SHALL be explicitly marked incomplete and SHALL NOT be used interchangeably with complete path.

### Requirement: Whole-leg overlap summaries remain reconstructable from atomic pairs

For each supported calculation resolution, eligible atomic pair records SHALL remain timestamped and keyed so arbitrary later intervals/macro legs can be reaggregated without market-data recollection.

Where complete pair coverage exists, whole-leg output SHALL separately summarize at minimum:

- `overlap_share_prev`;
- `overlap_share_curr`;
- `overlap_jaccard`;
- body-overlap normalizations;
- `any_overlap_share`;
- approved penetration/extension shares.

Contributing eligible pair count and coverage status SHALL be retained.

### Requirement: Modern contrast cases are directly extractable without limiting historical storage

The extraction layer SHALL support selection of whole-leg records and underlying atomic candles/pairs by `macro_leg_id`, including multiple leg ids in one request.

This SHALL support direct comparison of modern movements with similar log distance but materially different duration/path behavior while retaining the full approved historical dataset.
