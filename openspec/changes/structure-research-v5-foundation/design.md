# Design: Structure Research v5 Foundation

## 1. Design intent

Structure Research v5 is a staged descriptive research-data pipeline, not a trading-decision engine.

Priorities: source fidelity, deterministic time construction, explicit causality, stable identities, bounded memory, resumability, independent semantic validation, honest macro-anchor uncertainty, and efficient later extraction.

## 2. Canonical source architecture

The strict canonical 1m spine is:

- spot before `2019-09-08T17:57:00Z`;
- USDT-M futures from `2019-09-08T17:57:00Z` onward;
- documented canonical gaps preserved, including futures `2019-09-08T19:00`;
- post-boundary spot rows excluded from combined canonical chronology;
- synthetic 19:00 repair retained only as diagnostic evidence.

Canonical target intervals `5m/15m/1H/4H/1D` derive from this strict 1m spine.

## 3. Macro source architecture

The approved `macro_legs_log20.csv` remains a retrospective source segmentation with historical provenance distinct from current canonical market scope.

Late-2019 macro source may be `mixed` while the canonical wall-clock market is futures. These are separate columns/concepts.

Coarse macro anchor timestamps identify buckets containing extrema, not exact event times.

Before any macro-specific canonical path/activity/overlap/volume calculation, the pipeline attempts deterministic anchor refinement against compatible complete canonical 1m data.

For each anchor preserve:

- source price/time/precision;
- initial possible-time interval;
- refinement status;
- candidate count/first/last candidate minute;
- refined possible-time interval;
- historical provenance and canonical compatibility.

A unique 1m match narrows the anchor to one minute but that entire minute remains a boundary uncertainty zone because intra-minute event order is unknown.

Shared pivots are represented once in `macro_anchors` and referenced by both adjacent legs.

For start uncertainty `[S0,S1)` and end uncertainty `[E0,E1)`, safe canonical interior is `[S1,E0)`.

Boundary-overlapping candles remain stored/queryable but are not arbitrarily assigned to either leg safe interior.

## 4. Causal and retrospective separation

Fixed/rolling features are causal from documented close/availability.

Macro observations, macro anchors/refinement, completed-leg context and endpoint-dependent relationships are retrospective with `available_at=null` in this pass.

Causal extraction excludes them regardless of source timestamps.

## 5. Pipeline stage graph

Implementation SHALL respect dependencies in this order:

1. `S00_contract_and_config`
2. `S01_source_inventory`
3. `S02_canonical_1m`
4. `S03_source_segments_and_gaps`
5. `S04_fixed_candles`
6. `S05_candle_geometry`
7. `S06_cross_timeframe_map`
8. `S07_macro_source_and_anchor_refinement`
9. `S08_observation_index`
10. `S09_price_speed`
11. `S10_atomic_pairs`
12. `S11_path_activity`
13. `S12_overlap_summary`
14. `S13_volume_volatility`
15. `S14_macro_context`
16. `S15_retracement_measurements`
17. `S16_feature_dictionary_and_manifests`
18. `S17_independent_qa`
19. `S18_extraction_smoke`.

A stage is complete only after persisted outputs pass required validation.

## 6. Stage details

### S00 — Contract/config freeze

Freeze schema/source-contract versions, exact approved sources/checksums, canonical boundary, macro checksum/path, calculation matrices, output/checkpoint roots, code commit, and semantic `config_hash`.

### S01 — Source inventory

Inventory approved local sources: provenance, market/timeframe, coverage, duplicates, timestamp alignment, OHLC validity, gaps, and checksums. Distinguish canonical source data from diagnostic synthetic/legacy references.

### S02 — Canonical 1m

Normalize only observed approved rows into strict minute-aligned `candles_1m`. Exclude post-boundary spot and synthetic futures 19:00. Never silently round misaligned source rows.

### S03 — Source segments/gaps

Derive continuity from strict canonical 1m. Real spot gaps, futures 19:00 and market transition split sequential continuity. Archive/provenance changes alone do not.

### S04 — Fixed target grid

Build complete UTC target interval grid directly from canonical 1m. Boundary-crossing rows are `cross_market/incomplete_boundary`; gap rows are incomplete; complete OHLCV null on incomplete intervals.

### S05 — Candle geometry

Materialize atomic geometry for every complete target candle; incomplete rows do not produce valid geometry.

### S06 — Cross-timeframe map

Persist deterministic target-to-target containment and zero-based ordinals.

### S07 — Macro source and anchor refinement

Load exact approved macro source/checksum.

Create shared `macro_anchors` records from source pivot/event ids.

For every non-exact compatible anchor:

1. derive initial bucket uncertainty interval from source precision;
2. require complete canonical 1m coverage for uniqueness claims;
3. search exact source high/low price in compatible canonical market;
4. classify unique/multiple/no-match/incomplete/source-incompatible;
5. preserve candidates and refined possible interval;
6. compute each leg's safe interior from shared start/end uncertainty intervals;
7. derive canonical macro `market_type` independently of historical provenance.

No macro path/activity stage may run before this stage is validated.

### S08 — Observation index

Create fixed/rolling/macro identities. Macro rows preserve source-coordinate start/end times/prices, canonical market scope, retrospective availability and null `available_at`; safe-interior times live in macro leg/feature fields.

### S09 — Price/speed

Calculate complete fixed/rolling movement/speed under canonical names. Macro source displacement/speed remain retrospective source-coordinate measurements, not newly exact canonical event timing.

### S10 — Atomic pairs

Build neutral same-segment exact-adjacent target candle pairs and pair geometry.

### S11 — Path/activity/extrema

Fixed/rolling use exact approved matrices and formulas.

Macro rows use only complete calculation candles fully inside the refined safe interior. Persist `safe_*` path/activity/coverage names.

Complete `anchor_inclusive_*` whole-leg path remains null unless full ordered boundary path is genuinely established; coarse or unique-minute timing alone is insufficient.

### S12 — Overlap summaries

Aggregate eligible pairs fully internal to each valid fixed/rolling interval or macro safe interior.

### S13 — Volume/volatility

Compute canonical volume/TR/ATR and fixed/rolling RV. Macro volume/activity may use safe interior; macro RV is deferred.

### S14 — Macro context

Build retrospective observation-to-macro relationships using source-coordinate and safe-interior concepts explicitly. Do not invent parent hierarchy or live availability.

### S15 — Retracement measurements

Materialize only explicitly configured A-B-C relationships. No arbitrary tuple generation.

### S16 — Dictionary/manifests

Generate dictionary/manifests for every logical table including `macro_anchors`, geometry and retracement tables. Dictionary must distinguish source-coordinate, safe-interior and anchor-inclusive macro metrics.

### S17 — Independent QA

Run G01-G40 and persisted-artifact invariants independently of builder success flags. Critical macro QA includes anchor refinement, candidate ambiguity, incomplete search coverage, boundary-minute exclusion, canonical-vs-historical market separation, retrospective availability and safe-interior membership.

### S18 — Extraction smoke

Exercise real extraction for market/time/resolution, geometry, macro leg/anchor uncertainty, boundary candles, safe-interior features, retracements, causal exclusion and CSV export with no hidden recomputation.

## 7. Materialization strategy

Materialize once:

- canonical 1m;
- source segments/gaps;
- fixed target grid;
- candle geometry;
- cross-TF map;
- macro anchors/refinement;
- observation index;
- price/speed;
- atomic pairs;
- path/activity;
- overlap;
- volume/volatility;
- macro legs/context;
- approved retracement relationships;
- dictionary/manifests.

Boundary-ambiguous candles are not deleted; they remain canonical data and can be extracted with the relevant anchor.

## 8. Physical storage and resume

Use schema partition plan with Zstandard, bounded writes, validate-before-promotion, then manifest update.

Checkpoint validated work often enough that no more than 20 minutes of validated work is at risk. Resume validates source/config/schema/stage/artifacts and skips only proven completed units.

## 9. Execution gate

Implementation may proceed through golden tests and bounded smoke only. Full-history production requires a separate explicit authorization after smoke review.
