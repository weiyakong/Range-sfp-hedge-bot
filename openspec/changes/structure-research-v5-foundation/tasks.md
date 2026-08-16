# Tasks: Structure Research v5 Foundation

## Execution policy

Implement in the order below. Do not launch full-history production as part of implementation completion. A task that writes files but fails semantic validation is incomplete.

## Phase 0 — Contract freeze and scaffolding

### T00. Freeze final source contract
Record canonical boundary, raw/canonical spot-gap evidence, futures 19:00 gap/synthetic exclusion, approved source artifacts/checksums, and macro forensic provenance.

Acceptance: one source/config truth; no conflicting hardcoded boundary; synthetic rows cannot satisfy completeness.

### T01. Define typed runtime schemas
Implement typed contracts for all logical tables including `macro_anchors`, `candle_geometry`, `retracement_measurements`, canonical `market_type`, historical macro provenance, anchor precision/refinement status and safe-interior fields.

### T02. Implement deterministic ids
Implement UUIDv5 identities including macro anchor and retracement ids.

## Phase 1 — Canonical source spine

### T10. Inventory approved sources
Validate provenance, market, timeframe, coverage, duplicates, alignment, gaps, OHLC/numeric integrity, checksums. Report non-minute anomalies rather than rounding.

### T11. Build strict canonical 1m
Observed approved OHLCV only; exclude post-boundary spot and synthetic futures19:00; minute-aligned ids; partitioned Parquet.

### T12. Build source gaps and segments
Real gaps/market transition split continuity; archive changes do not. Recompute minute-grid spot gaps and compare to 5972/16 audit evidence.

### T13. Build fixed UTC target grid
5m/15m/1H/4H/1D directly from canonical1m; boundary-crossing rows `cross_market/incomplete_boundary`; gap rows incomplete.

### T14. Build atomic target candle geometry
One geometry row per complete target candle; G31.

### T15. Build cross-timeframe containment
Target-to-target mappings, zero-based ordinals; G06.

## Phase 2 — Macro source and anchor refinement MUST precede macro feature calculation

### T20. Load/validate approved macro source
Verify exact `macro_legs_log20.csv` checksum and source event ids. Preserve source leg fields unchanged.

### T21. Build shared `macro_anchors`
Create one anchor record per source pivot/event so the end of one leg and start of the next reference the same boundary object.

Preserve source anchor time/price/extreme type, parent/refinement provenance, source time precision and initial possible-time interval.

### T22. Refine coarse anchors against compatible canonical 1m
For every non-exact compatible anchor:

- derive search bucket from source precision;
- require complete canonical 1m coverage before uniqueness claim;
- match low anchor to exact canonical 1m low or high anchor to exact canonical 1m high after deterministic decimal normalization;
- classify `unique_1m_match`, `multiple_1m_matches`, `no_1m_match`, `incomplete_search_coverage`, or `source_incompatible`;
- preserve candidate count/first/last candidate minute;
- never pick first/last/nearest arbitrarily.

Acceptance: G35/G36/G37.

### T23. Derive macro uncertainty boundaries and safe interiors
For each refined anchor possible interval `[U0,U1)`, preserve it as shared ambiguous boundary.

For leg start `[S0,S1)` and end `[E0,E1)`, derive safe interior `[S1,E0)`.

Unique 1m pivot minute remains ambiguous and is excluded wholesale from both adjacent safe interiors.

Acceptance: G35/G40.

### T24. Derive canonical macro market scope separately from historical provenance
Canonical `market_type` = spot/futures/cross_market by current source chronology. Historical `leg_source_classification` remains separate and may be mixed.

Acceptance: October2019 can be canonical futures + historical mixed simultaneously; G38.

## Phase 3 — Observation identity and movement

### T30. Build observation index
Fixed/rolling/macro rows. Macro uses canonical non-null market type, source-coordinate anchor times/prices, `availability_class=retrospective`, `available_at=null`.

Acceptance: G05/G16/G38/G39.

### T31. Build price/speed
Canonical names only. Fixed/rolling complete causal metrics; macro source-coordinate displacement/speed explicitly retrospective/source-derived.

## Phase 4 — Pair/path/activity

### T40. Build atomic pair geometry
Same segment/resolution/exact adjacency required; G11.

### T41. Build fixed/rolling path/activity/extrema
Use exact fixed/rolling matrices; G08/G09/G10/G16/G32.

### T42. Build macro safe-interior path/activity
At 5m/15m/1H/4H/1D where at least two complete eligible candles lie wholly in safe interior.

Persist only `safe_*` macro path/activity names when boundaries remain uncertain.

No candle overlapping anchor uncertainty contributes to safe metrics.

Acceptance: G33/G35/G36/G37/G40.

### T43. Build complete anchor-inclusive macro path only when fully justified
Complete whole-leg path requires full ordered boundary path, source compatibility and no gap/uncertainty. Coarse or unique1m bucket alone is insufficient.

Acceptance: G15 formula fixture and G29 production gate.

## Phase 5 — Overlap

### T50. Build observation overlap summaries
Fixed/rolling use valid intervals; macro uses safe interior only. Boundary-overlapping pairs excluded from safe macro summaries.

## Phase 6 — Volume/volatility

### T60. Build dual volume-direction groupings
G12; no ambiguous generic up/down names.

### T61. Build TR/ATR
Reset at real gaps/boundaries; G13.

### T62. Build fixed/rolling RV and numeric range/TR/ATR components
Use canonical field names; macro RV not materialized in first pass; G08/G33/G34.

### T63. Build rolling volume comparisons
Use `volume_sum_change_vs_prev` / ratio; G34.

### T64. Build macro safe-interior volume/activity summaries
Use same safe constituent membership as macro path. Do not assign ambiguous boundary candles wholesale to a leg.

## Phase 7 — Macro context and retracement

### T70. Build retrospective observation-macro context
Use source-coordinate and safe-interior concepts explicitly; no parent hierarchy; no live leakage.

### T71. Implement direct retracement formula
G14.

### T72. Materialize only explicitly approved retracement relationships
No arbitrary A-B-C combinations; zero rows valid if no tuple list.

## Phase 8 — Dictionary/manifests/extraction

### T80. Generate canonical feature dictionary
Define every metric once, including macro anchor/refinement fields, `safe_*` semantics, source-coordinate metrics, geometry and retracements. G20/G34.

### T81. Generate deterministic manifests/catalog
All logical tables including `macro_anchors`; G22.

### T82. Implement deterministic Parquet extraction
Support time/market/segment/timeframe/rolling/calculation resolution, candle/observation/pair/macro-leg/macro-anchor/retracement ids, feature families, availability/as-of.

Must extract boundary candles and safe-interior rows without hidden recomputation. G23.

## Phase 9 — Checkpoint/resume

### T90. Stage/work-unit checkpoints
<=20 minutes validated work at risk.

### T91. Resume verification
G24; reject incompatible/corrupt state; no duplicates.

### T92. Atomic artifact promotion
Temporary write -> validate -> promote -> manifest.

## Phase 10 — QA

### T100. Implement golden suite G01-G40
Every applicable critical golden executes/passes.

### T101. Independent persisted-artifact QA
Inspect actual Parquet/manifests, not builder flags. Verify source gaps, grid alignment, macro anchor candidates, uncertainty windows, safe-interior membership, market/provenance separation, retrospective availability, referential integrity and causal exclusion.

### T102. Forbidden-label/name regression
G19/G34.

### T103. Higher-TF reference trust classification
G25; legacy inconsistent caches remain diagnostic where not validated.

## Phase 11 — Bounded smoke only

### T110. Select representative smoke coverage
Include ordinary continuous data, source gap/boundary behavior, geometry, rolling features, and at least one macro leg with coarse/refined anchor handling. Prefer a case exercising mixed provenance and boundary uncertainty.

### T111. Run smoke pipeline
Prerequisite G01-G40 PASS. Verify persisted QA/manifests/extraction including macro anchors and boundary candles.

### T112. Stop and report
Report exact coverage, outputs, QA/golden results, source limitations and measured runtime/storage. STOP.

## Phase 12 — Full production deferred

### T120. Full-history run
Planning only. Execute only after explicit approval following successful implementation/golden/smoke review.
