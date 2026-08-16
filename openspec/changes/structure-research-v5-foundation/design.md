# Design: Structure Research v5 Foundation

## 1. Design intent

Structure Research v5 is a staged descriptive research-data pipeline, not a trading-decision engine.

The implementation prioritizes source fidelity, deterministic time construction, explicit causality, stable analytical identities, decomposed feature families, bounded memory use, resumability, independent semantic validation, and later extraction without full-history recomputation.

Business semantics and formulas are defined by the specs. This design defines how those contracts are assembled safely.

## 2. Canonical source architecture

### 2.1 Strict canonical 1m spine

The canonical market spine is observed Binance BTCUSDT 1m data under the finalized source contract:

- spot before `2019-09-08T17:57:00Z`;
- USDT-M futures from `2019-09-08T17:57:00Z` onward.

Raw spot rows after the cutoff may remain in source inventory but do not enter the canonical combined chronology.

The exact first futures trade `2019-09-08T17:57:50.575000Z` is provenance evidence; the candle-grid source boundary is the first futures 1m bucket start `2019-09-08T17:57:00Z`.

### 2.2 Synthetic no-trade buckets are diagnostic only

The audited `2019-09-08T19:00:00Z` futures minute has no native kline and no official trades. The previously inserted flat `10000` zero-volume row is a deterministic synthetic no-trade bucket.

It must not be promoted into strict canonical `candles_1m`. The canonical pipeline records a real source gap `[19:00,19:01)` and splits source continuity around it. The synthetic row may remain only as recovery/audit evidence.

### 2.3 Canonical spot gaps are derived from the minute grid

The raw spot inventory has 6235 missing minutes; the cutoff audit reports 5972 canonical-relevant minutes across 16 intervals and excludes 263 post-boundary minutes.

Production must recompute canonical gaps from validated minute-grid rows because several audit boundary strings are not minute aligned. Non-minute timestamps are source-alignment evidence, not canonical gap boundaries to copy blindly.

### 2.4 Source continuity is separate from provenance

`source_segment_id` means one continuous canonical 1m market sequence for the same venue/instrument/market type. Archive files, local paths, download runs, or source-provenance changes alone do not split a segment.

Real unresolved gaps and the spot/futures transition do split continuity.

## 3. Macro-source architecture

The approved `macro_legs_log20.csv` is a retrospective observation source with historical provenance distinct from the current canonical market chronology.

The old parent daily merged source remained spot through `2019-12-30` and switched to futures on `2019-12-31`, while the macro builder also used futures 4H refinement from September 2019. Therefore audited late-2019 macro anchors may be `mixed` (`spot daily + futures 4H refinement`).

The pipeline must preserve:

- original macro source values;
- parent daily source regime;
- refinement source/timeframe where known;
- effective historical source class `spot/futures/mixed/unknown`;
- anchor-time precision;
- compatibility with current canonical data.

A 4H-refined macro timestamp is a 4H bucket start, not proof that the high/low occurred exactly at that timestamp. Internal canonical path may still be measured, but source-anchor-inclusive path is allowed only when source market compatibility and anchor-time precision are sufficient.

## 4. Causal and retrospective separation

Fixed and rolling features are causal only after their complete observation close and only when complete canonical inputs exist.

Macro-leg identity, completed-leg direction, endpoint-relative progress, mixed historical provenance, and whole-leg relationships are retrospective.

Retrospective joins are materialized separately and excluded from causal-only extraction.

## 5. Pipeline stage graph

Recommended stages:

1. `S00_contract_and_config`
2. `S01_source_inventory`
3. `S02_canonical_1m`
4. `S03_source_segments_and_gaps`
5. `S04_fixed_candles`
6. `S05_candle_geometry`
7. `S06_cross_timeframe_map`
8. `S07_observation_index`
9. `S08_price_speed`
10. `S09_atomic_pairs`
11. `S10_path_activity`
12. `S11_overlap_summary`
13. `S12_volume_volatility`
14. `S13_macro_source_and_context`
15. `S14_retracement_measurements`
16. `S15_feature_dictionary_and_manifests`
17. `S16_independent_qa`
18. `S17_extraction_smoke`

A stage is complete only after its persisted outputs pass stage validation.

## 6. Stage details

### S00 — Contract/config freeze

Freeze schema version, source-contract version, approved local source artifacts, source boundary, approved macro checksum/path, rolling/fixed/macro calculation matrices, output/checkpoint roots, code commit id, and normalized semantic `config_hash`.

Feature/test code does not maintain an independent market-boundary constant.

### S01 — Source inventory

Inventory approved local sources without deriving research features. Validate provenance, market type, timeframe, first/last timestamp, row count, duplicates, minute alignment, OHLC validity, numeric validity, and detected gaps.

Explicitly distinguish:

- raw spot gap evidence;
- canonical pre-cutoff spot gap candidates;
- native early-futures rows;
- the diagnostic synthetic 19:00 row;
- public futures archive parts;
- legacy higher-TF diagnostic references.

No unapproved downloads are permitted by implementation.

### S02 — Canonical 1m

Normalize only observed approved source candles into `candles_1m` with strict UTC minute alignment and stable ids.

Do not insert the synthetic 19:00 bucket. Do not retain post-boundary spot rows in canonical combined chronology.

Rows with non-minute-aligned source timestamps require explicit validation; do not silently round and accept them.

### S03 — Source segments and gaps

Derive `source_segments` and `source_gaps` from strict canonical 1m plus source contract.

Expected discontinuities include validated historical spot gaps, the spot/futures transition, and the native/source gap at futures 19:00.

Archive/provenance changes do not split continuity. Final canonical spot gap totals are compared to 5972/16 audit evidence but must be derived from the actual valid grid.

### S04 — Canonical fixed candles

Build the complete UTC interval grid for `5m`, `15m`, `1H`, `4H`, `1D` directly from canonical 1m.

A complete target candle requires the full expected 1m set from one source segment.

Boundary-crossing intervals exist as `market_type=cross_market`, `completeness_status=incomplete_boundary`, `source_segment_id=null`, and complete OHLCV null.

Gap-containing intervals are `incomplete_gap` with complete OHLCV null. Optional observed-only diagnostics remain explicitly named.

### S05 — Candle geometry

For each complete 5m-and-higher target candle materialize atomic geometry: full range, body, body bounds, wicks, shares, log geometry, and mechanical body direction.

Incomplete/boundary rows do not produce valid complete geometry.

### S06 — Cross-timeframe map

Persist deterministic target-to-target containment and zero-based ordinals. Do not persist a full exploded 1m-to-all-parent mapping.

### S07 — Observation index

Create fixed, rolling, and macro observation identities.

Fixed observations map one-to-one to target interval rows, including incomplete placeholders.

Rolling observations are indexed on the 5m endpoint grid for durations `30m`, `1h`, `4h`, `12h`, `24h`, `3d`; one observation id represents the interval regardless of calculation resolution.

Macro observations retain approved source anchors as retrospective data.

`expected_base_resolution` is explicit: 1m for fixed completeness, 5m for rolling observation completeness, null for macro unless specifically defined.

Incomplete fixed/rolling observations do not expose ordinary start/end movement or speed as complete features.

### S08 — Price/speed

Calculate canonical movement/speed names from complete observation endpoints only:

- ordinary/log displacement;
- `raw_signed_speed_pct_per_hour`;
- `signed_log_speed_per_hour`;
- `local_direction_speed_pct_per_hour`;
- `local_direction_log_speed_per_hour`;
- rolling adjacent-window speed change/acceleration.

No threshold labels.

### S09 — Atomic pairs

Build target-resolution chronological neighbor candidates. Pair eligibility requires same source segment, same resolution, and exact adjacency.

Calculate neutral range/body overlap, overlap position, upper/lower extension, and mirrored penetration. Do not attach observation direction at pair-construction time.

### S10 — Path/activity/extrema

Use exact approved calculation matrices.

Fixed:

- 15m via 5m;
- 1H via 5m/15m;
- 4H via 5m/15m/1H;
- 1D via 5m/15m/1H/4H.

Rolling:

- 30m via 5m/15m;
- 1h via 5m/15m;
- 4h via 5m/15m/1H;
- 12h via 5m/15m/1H/4H;
- 24h via 5m/15m/1H/4H;
- 3d via 5m/15m/1H/4H/1D.

Macro internal path/activity may be attempted at 5m/15m/1H/4H/1D when at least two complete eligible constituents exist.

Calculate close/log path, efficiency, directional components, alternation, activity sums, extrema first/last/count, and excursions.

Macro internal path is separate from source-anchor-inclusive path. Anchor-inclusive metrics require compatible market provenance and sufficient anchor-time precision; otherwise they are null with explicit status.

### S11 — Overlap summaries

Aggregate only eligible atomic pairs fully internal to observations, using the same supported calculation matrices. Direction-relative summaries are derived only after valid observation direction is known.

### S12 — Volume/volatility

Use canonical field names including `volume_sum_change_vs_prev`, `volume_sum_ratio_vs_prev`, `observation_high_low_width`, `mean_full_range`, and related explicit log/TR fields.

Compute dual mechanical volume groupings, TR/ATR, fixed/rolling realized variance/volatility, and numeric contraction/expansion components.

Macro realized variance/volatility is not required in this pass. Macro volume summaries may be materialized under complete-coverage rules.

All sequential states reset at real canonical gaps/boundaries.

### S13 — Macro source/context

Load the exact approved macro source/checksum and enrich it with forensic source provenance. Do not overwrite historical mixed source classification using the current canonical boundary.

Build retrospective observation-to-macro temporal intersections and approved macro-aligned numeric context. No parent hierarchy is inferred.

### S14 — Retracement measurements

The formula engine supports direct approved A-B-C retracement measurement, but production materialization occurs only for explicitly configured/approved relationship tuples.

Do not generate arbitrary combinations of approved anchors. If no production relationship list is configured, the canonical `retracement_measurements` table may validly contain zero rows while the golden formula test still passes.

### S15 — Dictionary/manifests

Generate feature dictionary from declared schema/formulas and deterministic manifests for every logical table. Dictionary availability/null semantics must agree with actual extraction behavior.

### S16 — Independent QA

QA reads persisted artifacts independently of builder success flags and executes G01-G34 plus production invariants.

Critical QA includes source-grid alignment, synthetic 19:00 exclusion, source segmentation, cross-market fixed placeholders, historical macro mixed provenance, anchor-precision gating, candle geometry, calculation matrices, field-name regression, causal leakage, resume equivalence, referential integrity, and manifest reconstruction.

Legacy inconsistent higher-TF caches are diagnostic references, not critical truth in inconsistent regions.

### S17 — Extraction smoke

Exercise real Parquet extraction with partition/column pruning, causal-only exclusion, macro extraction, retracement-table selection when populated, geometry extraction, CSV export, and no hidden canonical feature recomputation.

## 7. Materialization strategy

Materialize once:

- strict canonical 1m;
- source segments/gaps;
- target fixed interval grid;
- atomic target candle geometry;
- cross-TF map;
- observation index;
- price/speed;
- atomic pair geometry;
- path/activity;
- overlap summaries;
- volume/volatility;
- macro legs/context;
- explicitly approved retracement relationships;
- dictionary/manifests.

Extraction may join/filter/format existing canonical data but must not silently invent missing canonical features.

## 8. Physical storage

Use the partition plan from `research-table-schema` with Zstandard compression. Avoid one-file-per-observation/day patterns. Use bounded writes, validate before atomic promotion, then update manifests.

Checkpoint/cache artifacts remain distinct from validated canonical output.

## 9. Resume/idempotency

Checkpoint validated work units often enough that no more than 20 minutes of completed validated work is at risk.

Resume validates source/config/schema/stage/checkpoint/artifact identity and skips only proven completed units. Stable ids/natural keys prevent duplicate canonical entities. Incompatible/corrupt checkpoints fail explicitly.

## 10. Causality

Every feature definition declares availability class and available-at rule. Causal fixed/rolling features use only data available by observation close. Retrospective macro joins happen after causal/local materialization. Future-data invariance is a critical regression test.

## 11. Execution gate

Implementation may proceed through golden tests and a bounded real-data smoke only.

Full-history production is a separate deferred execution gate requiring explicit authorization after smoke review. Implementation completion does not authorize a full production run.
