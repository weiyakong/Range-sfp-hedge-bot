# Tasks: Structure Research v5 Foundation

## Execution policy

Implement in the order below unless a task explicitly permits parallel work.

Do not launch the full-history production run as part of implementation completion.

Each task must satisfy its acceptance criteria and applicable golden/regression tests before downstream tasks rely on its outputs. A task that merely writes files but fails semantic validation is incomplete.

## Phase 0 — Contract freeze and scaffolding

### T00. Freeze final source contract

Record exactly:

- first futures trade `2019-09-08T17:57:50.575000Z`;
- first futures 1m bucket/canonical boundary `2019-09-08T17:57:00Z`;
- raw spot gaps 6235;
- cutoff-audit expectation 5972 canonical-relevant spot missing minutes / 16 intervals, subject to strict minute-grid revalidation;
- native/source futures gap at `2019-09-08T19:00:00Z`;
- diagnostic synthetic 19:00 row exclusion from canonical data;
- macro forensic source provenance including mixed Sep-Dec 2019 behavior;
- approved evidence artifact paths/fingerprints.

Acceptance:

- one source-contract/config source of truth exists;
- no feature/test code hardcodes a conflicting market boundary;
- synthetic diagnostic rows cannot satisfy canonical completeness;
- source/audit expectations are machine-readable.

### T01. Define typed runtime schemas

Implement typed contracts for all canonical logical tables, manifests, checkpoints, and run configuration, including `cross_market`, anchor precision/source provenance, `candle_geometry`, and `retracement_measurements`.

Acceptance:

- required columns/dtypes/nullability/enums/keys validated at material boundaries;
- public production functions/config typed;
- configured type checker passes.

### T02. Implement deterministic ids

Implement UUIDv5 identities exactly as schema specifies, including retracement ids.

Acceptance: G17 and idempotency tests pass.

## Phase 1 — Source/canonical spine

### T10. Inventory approved sources

Inventory provenance, market type, timeframe, first/last timestamp, rows, duplicates, timestamp alignment, gaps, OHLC/numeric validity, and checksums.

Explicitly distinguish raw spot files, canonical pre-cutoff spot candidates, native early futures, diagnostic synthetic 19:00 row, public futures archives, and legacy higher-TF diagnostic references.

Acceptance:

- no unapproved downloads;
- non-minute source timestamps are reported, not silently rounded;
- inventory failures affect QA/status.

### T11. Build strict canonical 1m Parquet

Requirements:

- UTC half-open minute intervals;
- observed approved OHLCV only;
- stable ids;
- row-level provenance;
- no synthetic missing candles;
- exclude post-boundary spot rows from canonical combined chronology;
- exclude diagnostic synthetic futures 19:00 row;
- bounded/chunked processing;
- Zstandard, partition `market_type/year/month`.

Acceptance:

- natural keys unique;
- every start time minute-aligned;
- synthetic 19:00 absent;
- source gaps remain absent rows;
- manifest/schema validation passes.

### T12. Build canonical source gaps and segments

Derive strict source continuity from canonical 1m plus source contract.

Acceptance:

- spot/futures boundary splits continuity;
- 19:00 futures gap splits continuity;
- validated historical spot gaps split continuity;
- archive/provenance changes alone do not;
- all canonical gap boundaries minute-aligned;
- production spot gap totals compared against 5972/16 audit expectation with explicit discrepancy handling;
- G03, G04, G27, G30 pass.

### T13. Build canonical fixed UTC interval grid

Build 5m/15m/1H/4H/1D directly from canonical 1m.

Acceptance:

- G01/G02 pass;
- gap intervals have null complete OHLCV;
- source-boundary-crossing intervals exist as `cross_market/incomplete_boundary`, complete OHLCV null;
- G26 passes;
- native higher TF never replaces canonical derived values.

### T14. Build atomic target candle geometry

Materialize `candle_geometry` for every complete 5m-and-higher canonical candle.

Acceptance:

- one geometry row per complete target candle;
- no valid geometry for incomplete/boundary intervals;
- exact absolute/log geometry formulas;
- G31 passes.

### T15. Build cross-timeframe containment

Persist target-to-target mappings with zero-based ordinals.

Acceptance: G06 passes; no exploded 1m→all-parent map.

## Phase 2 — Observations and basic movement

### T20. Build observation index

Create fixed, rolling, macro observations.

Acceptance:

- fixed/rolling distinct;
- `expected_base_resolution`: fixed=1m, rolling=5m, macro=null unless explicitly materialized;
- incomplete fixed/rolling ordinary endpoints/net features not presented as complete;
- rolling identity reused across calculation resolutions;
- G05/G16 pass.

### T21. Build price/speed features

Use canonical field names only.

Acceptance:

- G07 passes;
- `local_direction_speed_pct_per_hour` and `local_direction_log_speed_per_hour` used;
- deprecated normalized-name variants absent;
- future-data invariance passes.

## Phase 3 — Pair/path/activity

### T30. Build atomic pair geometry

Eligibility: same source segment, same resolution, exact adjacency.

Acceptance:

- boundary/gap candidates cannot be eligible;
- neutral overlap/body overlap/position/penetration/extension formulas exact;
- G11 passes.

### T31. Build path/activity/extrema using exact matrices

Fixed matrix:

- 15m via 5m
- 1H via 5m,15m
- 4H via 5m,15m,1H
- 1D via 5m,15m,1H,4H.

Rolling matrix:

- 30m via 5m,15m
- 1h via 5m,15m
- 4h via 5m,15m,1H
- 12h via 5m,15m,1H,4H
- 24h via 5m,15m,1H,4H
- 3d via 5m,15m,1H,4H,1D.

Acceptance:

- G08/G09/G10/G16/G32 pass;
- incomplete coverage nulls complete metrics.

### T32. Build macro internal path/activity

At 5m/15m/1H/4H/1D when at least two eligible complete constituents exist.

Acceptance:

- source macro displacement preserved independently;
- no path bridges canonical gaps/boundaries;
- historical macro provenance is not overwritten by current boundary;
- G28/G33 pass.

### T33. Build gated macro anchor-inclusive path

Use source anchors only when market/source compatibility and anchor-time precision are sufficient for the requested calculation resolution.

Acceptance:

- a 4H-bucket-start refined extreme is not treated as exact event time;
- insufficient precision => anchor-inclusive metrics null with explicit status;
- G15 synthetic exact-anchor fixture still tests the math engine;
- G29 passes.

## Phase 4 — Overlap

### T40. Build observation overlap summaries

Aggregate eligible pairs fully internal to observations under the exact fixed/rolling/macro matrices.

Acceptance:

- start-boundary crossing pair excluded from internal aggregation;
- direction-relative summaries computed only when valid direction exists;
- coverage/status exact.

## Phase 5 — Volume/volatility

### T50. Build dual volume-direction groupings

Acceptance: G12; no ambiguous generic up/down volume.

### T51. Build TR/ATR

Acceptance:

- G13;
- state resets at every true source gap/boundary, including futures 19:00;
- no previous close borrowed across discontinuity.

### T52. Build realized volatility and numeric range/TR/ATR components

Fixed/rolling only for RV in first pass.

Use canonical names:

- `observation_high_low_width`
- `observation_high_low_width_pct_start`
- `observation_log_high_low_width`
- `mean_full_range`, `median_full_range`
- `mean_log_full_range`, `median_log_full_range`
- declared current-vs-prev rolling deltas/ratios.

Acceptance:

- G08 RV;
- macro RV not materialized as valid first-pass metric;
- no composite compression/expansion label;
- G33/G34 pass.

### T53. Build rolling volume comparisons

Use `volume_sum_change_vs_prev` and `volume_sum_ratio_vs_prev`.

Acceptance:

- exact adjacent non-overlap window semantics;
- denominator-null behavior;
- deprecated `volume_delta/volume_ratio` absent;
- G34 passes.

## Phase 6 — Macro provenance/context + retracement

### T60. Load/validate approved macro source

Verify exact `macro_legs_log20.csv` checksum.

Enrich source rows with forensic evidence:

- old parent daily regime;
- refinement source market/timeframe;
- effective source class;
- anchor-time precision;
- canonical-compatibility status.

Acceptance:

- late-2019 audited mixed provenance preserved;
- current source boundary does not relabel historical source;
- source-vs-derived direction QA emitted;
- G28 passes.

### T61. Build retrospective observation-macro context

Calculate approved temporal intersection/progress and macro-aligned numeric context only in retrospective table.

Acceptance: no endpoint-derived macro leakage into causal tables; no parent hierarchy.

### T62. Implement direct retracement formula engine

Implement exact approved A-B-C formula independently of relationship discovery.

Acceptance: G14 passes including >100% retracement and same-direction continuation=0.

### T63. Materialize explicitly approved retracement relationships only

Build `retracement_measurements` only from a configured list of approved A-B-C tuples.

Acceptance:

- no arbitrary anchor combinations;
- tuple provenance/precision/availability stored;
- zero rows is valid if no production tuple list configured;
- G14 tests formula regardless of row count.

## Phase 7 — Dictionary/manifests/extraction

### T70. Generate canonical feature dictionary

Acceptance:

- every materialized metric defined once with exact canonical name/formula/units/availability/null/provenance;
- deprecated conflicting names absent;
- G20/G34 pass.

### T71. Generate deterministic manifests/catalog

Acceptance: G22; reconstruct all logical tables without duplicate keys.

### T72. Implement deterministic Parquet extraction

Support time/market/source segment/timeframe/rolling duration/calculation resolution/observation ids/macro ids/retracement ids/feature families/availability/as-of filters.

Acceptance:

- predicate/column pruning;
- no full conversion before filtering;
- no hidden recomputation;
- geometry and retracement tables extractable;
- G23.

## Phase 8 — Checkpoint/resume

### T80. Stage/work-unit checkpoints

Acceptance: <=20 minutes validated work at risk.

### T81. Resume verification

Acceptance: G24; incompatible/corrupt state rejected; no duplicate rows.

### T82. Atomic artifact promotion

Temporary write -> validate -> atomic promote -> manifest update.

Acceptance: manifests never reference partial/unvalidated parts.

## Phase 9 — QA

### T90. Implement complete golden suite G01-G34

Acceptance: every applicable critical golden test executes and passes.

### T91. Independent persisted-artifact QA

Inspect actual canonical Parquet/manifests, not builder flags.

Acceptance:

- schema/keys/references;
- minute-grid alignment;
- strict 19:00 gap;
- source-boundary isolation;
- historical macro provenance;
- anchor precision;
- fixed/rolling/macro matrices;
- causal leakage;
- final QA status derived mechanically.

### T92. Forbidden-label/name regression

Acceptance:

- G19/G34;
- no impulse/correction/range/breakout/choppiness/parent/Fib/FibTime generated labels;
- no deprecated conflicting feature names.

### T93. Higher-timeframe reference QA with trust classification

Every QA reference classified `critical_validated_reference` or `diagnostic_reference`.

Known legacy inconsistent 1D/4H caches remain diagnostic where trust is not established.

Acceptance: G25; diagnostic mismatch cannot overwrite canonical data or fail critical QA by itself.

## Phase 10 — Bounded real-data smoke only

### T100. Select representative smoke slice

Exercise:

- ordinary continuous futures;
- source gap behavior including 19:00 if practical;
- boundary-crossing fixed rows;
- multiple target resolutions;
- rolling features;
- geometry;
- pairs/path/overlap/volume/volatility;
- at least one approved macro leg, preferably including a mixed-provenance test case;
- extraction.

### T101. Run smoke pipeline

Acceptance:

- golden G01-G34 already PASS;
- independent smoke QA PASS;
- manifests reconstruct;
- causal extraction clean;
- row counts/coverage independently plausible.

### T102. Stop and report

Report exact smoke coverage, output/manifests, QA/golden results, warnings/source limitations, and measured storage/runtime evidence. STOP.

Do not run full history without explicit authorization.

## Phase 11 — Full production (deferred gate)

### T110. Full-history run

Defined for planning only. Execute only after explicit approval following successful implementation/golden/smoke review.
