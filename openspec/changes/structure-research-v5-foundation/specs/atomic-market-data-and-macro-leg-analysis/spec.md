# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure that one approved research run leaves enough atomic market data and whole-leg measurements across the full approved BTC history to investigate movement behavior later without rerunning market-data download or inventing missing semantics.

## ADDED Requirements

### Requirement: Production coverage uses the full approved history

The first production research dataset SHALL target the full approved BTC history from the earliest approved source timestamp through the latest approved source timestamp, subject to actual coverage and integrity.

The pipeline SHALL NOT impose `2023-01-01` or `2024-01-01` as collection cutoffs. Those periods MAY receive higher analytical priority later without reducing stored historical coverage.

### Requirement: Source segment means continuous market continuity, not file provenance

Every canonical candle SHALL carry both row-level provenance and a `source_segment_id`.

`source_segment_id` SHALL identify one temporally continuous sequence of the same venue, instrument, market type, and canonical timeframe/source stream. It SHALL NOT change merely because:

- a new monthly/daily archive file begins;
- a different local path stores the next raw part;
- a candle was downloaded in a different run;
- an otherwise valid missing candle was deterministically reconstructed from approved lower-level official data of the same venue/instrument/market type.

Row-level `source_id`, raw artifact/file identity, download/reconstruction provenance, and validation status SHALL remain separately preserved.

A new source segment SHALL begin when continuity is genuinely broken, including at minimum:

- spot -> futures or futures -> spot market-type transition;
- venue or instrument change;
- unresolved real candle gap;
- another explicitly documented discontinuity that makes sequential calculations invalid.

If a previously unresolved gap is later completely repaired and validated from approved same-market lower-level official data, the repaired continuous sequence MAY be represented as one source segment while retaining reconstruction provenance on the repaired rows.

### Requirement: Canonical 1m source layer is retained without heavy 1m feature materialization

The approved canonical `1m` OHLCV history SHALL remain queryable as the finest candle source/drill-down layer.

Each retained 1m candle SHALL preserve at minimum stable candle identity, symbol/instrument, venue, market type, `source_segment_id`, canonical UTC `[start_time,end_time)`, OHLC, source-native volume, row-level provenance, validation status, and completeness/gap status.

The first production pass SHALL NOT be required to materialize the complete heavy feature family on every 1m candle. Full-market feature production SHALL begin at `5m` unless a separately approved feature requires 1m calculation.

### Requirement: Canonical target candles are deterministically derived from canonical 1m

For this first-pass research dataset, canonical `5m`, `15m`, `1H`, `4H`, and `1D` candles SHALL be deterministically aggregated from the approved canonical `1m` layer.

Existing native/local higher-timeframe candle datasets SHALL be treated as QA/reference sources and SHALL NOT silently replace the canonical 1m-derived representation.

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

Each target row SHALL preserve expected count, observed count, coverage ratio, source segment, and completeness state.

### Requirement: Incomplete target intervals cannot masquerade as complete candles

If any required 1m constituent is missing, misaligned, or belongs to another source segment, the complete canonical target candle SHALL be marked incomplete.

Complete OHLC/volume fields used by the research feature pipeline SHALL be null for that interval rather than presenting a partial aggregation as a valid complete candle.

For diagnostics, the system MAY separately retain explicitly named `observed_only_open`, `observed_only_high`, `observed_only_low`, `observed_only_close`, `observed_only_volume`, and related counts/coverage calculated only from the observed constituents.

Observed-only values SHALL never be consumed interchangeably with complete canonical candle fields.

No interpolation or synthetic constituent candle is permitted.

### Requirement: Atomic target-candle records remain queryable

For canonical target resolutions `5m`, `15m`, `1H`, `4H`, and `1D`, the analytical store SHALL retain queryable candle-level rows sufficient to recompute later features without rerunning market-data download.

Each row SHALL contain at minimum:

- stable candle identifier;
- instrument/symbol;
- venue;
- market type;
- `source_segment_id`;
- timeframe;
- canonical `start_time` and exclusive `end_time`;
- complete OHLC/volume when valid;
- construction/provenance identifier;
- source calculation resolution (`1m`);
- expected/observed constituent counts;
- coverage ratio;
- completeness/gap status.

### Requirement: Source construction map is explicit

Before full production, run provenance SHALL record the exact canonical 1m source artifacts/manifest and the deterministic 1m->target construction contract, including venue, instrument, market type, source segments, first/last timestamps, known gaps, and schema/version.

Native higher-timeframe QA sources MAY also be listed separately, clearly marked `qa_reference`, and SHALL NOT be confused with canonical target-candle provenance.

### Requirement: Canonical timestamp semantics are explicit

Source-native timestamp fields MAY be retained as provenance, but canonical candles SHALL use UTC half-open `[start_time,end_time)` intervals according to the approved time-grid contract.

Canonical interval boundaries SHALL be deterministic and independent of source representations such as inclusive `close_time = ...59.999`.

### Requirement: Approved macro-leg source is explicit

Whole-leg research SHALL use the approved `macro_legs_log20.csv` anchor dataset unless the user explicitly approves a replacement.

It SHALL be supplied by exact configured path or immutable identifier; the pipeline SHALL NOT search for or substitute similarly named macro/swing/parent files.

The reviewed reference has 128 rows with `leg_id`, direction, start/end event ids, start/end times/prices, ordinary/log movement, and duration fields. Run provenance SHALL record a source checksum. The reviewed reference SHA-256 is:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

A different checksum/source requires explicit provenance review before it may be treated as the same approved anchor input.

### Requirement: Macro-leg anchor market source follows the same approved spot-to-futures regime

The approved `macro_legs_log20.csv` anchors SHALL be interpreted under the same market-source regime as the canonical research history:

- anchors before `2019-12-31T00:00:00Z` belong to the approved Binance BTCUSDT spot source regime;
- anchors at or after `2019-12-31T00:00:00Z` belong to the approved Binance BTCUSDT USDT-M futures source regime.

Within a macro leg whose start/end anchors and required candle path lie entirely inside one valid continuous market/source segment, the source anchor prices are approved for anchor-inclusive path and efficiency calculations under this contract; no separate source-compatibility discovery step is required.

A macro leg that crosses the spot-to-futures boundary SHALL preserve its original source anchor movement/duration as a retrospective macro-structure measurement, but complete sequential whole-leg path, ATR/RV-style sequential summaries, overlap sequence, and path efficiency SHALL NOT bridge the spot/futures transition as though it were one continuous traded instrument. Per-segment diagnostics MAY be retained separately.

### Requirement: Whole macro-leg measurements are first-class retrospective outputs

For every approved macro leg overlapping approved candle coverage, the system SHALL calculate a whole-leg record in addition to fixed/rolling observations.

It SHALL preserve anchors, duration, ordinary/log movement and speed, multi-resolution path/efficiency, directional path components, alternation, overlap/penetration summaries, candle activity, volume/volatility summaries, and coverage status where calculable.

Measurements that depend on the known macro-leg endpoint or whole-leg direction SHALL be explicitly `retrospective` and SHALL NOT be exposed as live-available features.

No new semantic `impulse` or `correction` class is permitted.

### Requirement: Macro-leg path uses explicit anchors and does not bridge discontinuities

For macro leg `(T0,P0)->(T1,P1)` and an approved finer resolution, preserve internal finer-close path separately from anchor-inclusive path.

Internal path SHALL use chronologically consecutive eligible finer closes inside each continuous source segment.

Anchor-inclusive path SHALL add `P0 -> first eligible finer close` and `last eligible finer close -> P1` only when those transitions are valid under the same market/source semantics and are not already represented by the same observed point.

A macro leg intersecting a source-segment boundary or unresolved gap SHALL NOT bridge it as one complete path. Per-segment partial/observed-only diagnostics MAY be retained, while complete whole-leg path/efficiency for that resolution SHALL be null.

Equivalent log path SHALL use absolute log ratios for strictly positive prices.

### Requirement: Gaps cannot masquerade as valid path

Every path-dependent observation SHALL preserve expected finer count, observed finer count, coverage ratio, and gap status.

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
