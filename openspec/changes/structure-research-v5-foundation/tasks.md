# Tasks: Structure Research v5 Foundation

## Execution policy

Implement in the order below unless a task explicitly permits parallel work.

Do not launch the full-history production run as part of implementation completion.

Each task must satisfy its acceptance criteria and applicable golden/regression tests before downstream tasks rely on its outputs.

A task that produces files but fails semantic validation is incomplete.

## Phase 0 — Contract freeze and implementation scaffolding

### T00. Finalize source contract

- Incorporate the completed early-futures investigation.
- Record exact first usable BTCUSDT USDT-M futures timestamp.
- Record exact canonical spot-to-futures boundary.
- Record unresolved spot/futures gaps and evidence.
- Record approved source artifacts/manifests and fingerprints.
- Preserve the already accepted 6,235 irrecoverable spot minutes as documented gaps unless a later explicitly approved source repair changes that result.

Acceptance:

- one source-contract/configuration source of truth exists;
- feature/test code does not independently hardcode a conflicting market boundary;
- source gaps and market transitions are explicit and machine-readable.

### T01. Define runtime schemas and typed domain contracts

Implement typed runtime contracts for:

- source segment;
- source gap;
- canonical 1m candle;
- canonical fixed candle;
- observation identity;
- atomic candle pair;
- feature-family outputs;
- manifests/checkpoints/run config.

Acceptance:

- required columns/dtypes/nullability/enums/keys are validated at material pipeline boundaries;
- public production functions and structured config are type-annotated;
- the repository-configured type checker passes.

### T02. Implement deterministic identity helpers

Implement UUIDv5 ids exactly as specified.

Acceptance:

- G17 exact identifier fixture passes;
- ids are independent of run id/local path/archive filename where specified.

## Phase 1 — Source and canonical candle spine

### T10. Implement source inventory

Read approved local market-data artifacts and report:

- provenance;
- market type;
- timeframe;
- first/last timestamp;
- row count;
- duplicates;
- gaps;
- OHLC/numeric validity;
- checksums where feasible.

Acceptance:

- inventory is reproducible;
- no unapproved downloads occur;
- inventory failures affect QA/status.

### T11. Build canonical 1m Parquet

Normalize approved source rows into canonical `candles_1m`.

Requirements:

- UTC half-open intervals;
- exact OHLCV preservation;
- row-level provenance;
- no synthetic missing candles;
- stable ids;
- bounded/chunked processing;
- partitioning `market_type/year/month`;
- Zstandard compression.

Acceptance:

- natural keys unique;
- source-gap minutes absent rather than fabricated;
- schema and manifest validation pass.

### T12. Build source segments and source gaps

Assign continuity segments from canonical 1m and finalized source contract.

Acceptance:

- real gaps split continuity;
- spot/futures boundary splits continuity;
- archive/provenance changes alone do not split continuity;
- G03 and G04 pass;
- `source_segments` and `source_gaps` referentially agree with 1m rows.

### T13. Build canonical fixed candles from 1m

Build `5m`, `15m`, `1H`, `4H`, `1D` directly from canonical 1m.

Acceptance:

- G01/G02 pass;
- incomplete target intervals have null complete OHLCV and explicit coverage;
- canonical construction never recursively substitutes native higher-TF candles.

### T14. Build cross-timeframe containment

Persist target-to-target containment map.

Acceptance:

- zero-based ordinals;
- deterministic parent membership;
- G06 passes;
- no required exploded 1m-to-parent mapping is created.

## Phase 2 — Observation identity and base geometry

### T20. Build observation index

Create fixed, rolling, and macro observation identities.

Rolling observations:

- evaluated on 5m endpoint grid;
- durations `30m`, `1h`, `4h`, `12h`, `24h`, `3d`;
- one observation id per interval/duration.

Acceptance:

- fixed vs rolling remain distinct;
- G05 and G16 pass;
- availability class/available-at semantics are valid.

### T21. Build price/speed features

Calculate basic movement, log movement, local direction, speed, rolling adjacent-window speed change and acceleration.

Acceptance:

- G07 passes;
- no threshold labels are emitted;
- future-data invariance applies to causal rows.

## Phase 3 — Pair geometry and path/activity

### T30. Build atomic candle-pair table

For each target calculation resolution, create chronological neighbor candidates and calculate neutral pair geometry only for eligible pairs.

Acceptance:

- same-segment + same-resolution + exact adjacency required;
- source/gap boundary candidates cannot masquerade as eligible;
- overlap/body overlap/position/penetration/extension formulas match spec;
- G11 passes.

### T31. Build path/activity/extrema features

For supported observation/calculation-resolution combinations compute:

- close/log path;
- path efficiencies;
- upward/downward path;
- local-direction path;
- alternation/zero-step behavior;
- range/body/wick/TR activity;
- extrema first/last/count;
- excursions.

Acceptance:

- G08/G09/G10 pass;
- incomplete required constituent coverage nulls complete metrics;
- calculation-resolution matrix respected.

### T32. Build macro internal and anchor-inclusive path

Reuse tested path engine where semantics match; add explicit approved macro anchor transitions.

Acceptance:

- G15 passes;
- boundary/gap-crossing macro legs do not bridge complete path;
- macro source movement remains preserved independently.

## Phase 4 — Overlap aggregation

### T40. Build observation overlap summaries

Aggregate only eligible atomic pairs fully internal to each observation.

Acceptance:

- pair crossing observation start boundary is not included as internal pair;
- mean/median/share metrics match atomic source rows;
- direction-relative summaries are derived only after observation direction exists;
- causal/retrospective availability remains correct.

## Phase 5 — Volume and volatility

### T50. Build dual volume-direction groupings

Implement body-direction and close-step-direction totals/shares independently.

Acceptance:

- G12 passes;
- generic ambiguous `up_volume/down_volume` outputs are prohibited.

### T51. Build TR and ATR state

Implement per-resolution/per-source-segment TR, ATR14 SMA, and Wilder ATR.

Acceptance:

- G13 passes;
- gap/source boundary resets state;
- first invalid previous-close TR is null.

### T52. Build realized volatility and numeric compression/expansion components

Use the same boundary-aware Q sequence as path for RV.

Calculate required range/TR/ATR comparison fields without semantic state labels.

Acceptance:

- G08 RV values pass;
- no annualization;
- incomplete/gap-crossing observations have null complete RV;
- no composite compression/expansion score is created.

### T53. Build rolling volume comparisons

Implement current versus immediately previous equal complete window comparisons.

Acceptance:

- exact adjacent-window semantics;
- zero/undefined denominator null handling;
- no semantic accumulation/exhaustion labels.

## Phase 6 — Macro retrospective context

### T60. Load and validate approved macro source

Load exact configured `macro_legs_log20.csv` and verify expected fingerprint/provenance.

Acceptance:

- no similarly named substitute file is auto-selected;
- source fields preserved distinctly from recomputed fields;
- source-vs-derived direction QA emitted.

### T61. Build observation-to-macro retrospective context

Calculate temporal intersection, leg-time progress, macro-aligned numeric features where approved.

Acceptance:

- table is explicitly retrospective;
- no macro endpoint-derived values written into causal feature tables;
- no validated parent hierarchy is invented.

## Phase 7 — Dictionary, manifests, extraction

### T70. Generate canonical feature dictionary

Build dictionary from declared schema/feature definitions.

Acceptance:

- G20 passes;
- every materialized metric has formula/units/null/availability/provenance definition;
- small CSV review copy emitted.

### T71. Generate deterministic manifests/catalog

For every logical table record parts, schemas, partitions, coverage, row counts, run id, integrity evidence.

Acceptance:

- G22 passes;
- logical tables reconstruct without duplicate canonical keys.

### T72. Implement deterministic Parquet extraction utility

Support filtering by:

- time range;
- market/source segment;
- fixed timeframe;
- rolling duration;
- calculation resolution;
- observation ids;
- macro leg ids;
- feature families/columns;
- availability class;
- as-of time.

Acceptance:

- predicate/column pruning used where supported;
- no full Parquet-to-CSV conversion before filtering;
- no hidden feature recomputation;
- G23 passes;
- review CSV size/partition rules respected.

## Phase 8 — Checkpoint/resume and artifact safety

### T80. Implement stage/work-unit checkpoints

Checkpoint only validated completed units.

Acceptance:

- <=20 minutes validated work at risk between persistence points during long stages;
- checkpoint records semantic compatibility and artifact evidence.

### T81. Implement resume verification

Resume must validate config/input/schema/stage/checkpoint/artifact compatibility and skip only proven completed units.

Acceptance:

- G24 passes;
- stale/incompatible/corrupt checkpoints are rejected;
- no duplicate rows on resume.

### T82. Implement atomic artifact promotion

Use temporary write -> validation -> atomic promotion -> manifest update.

Acceptance:

- interrupted writes cannot appear as valid final canonical parts;
- manifests never reference unvalidated partial artifacts.

## Phase 9 — QA

### T90. Implement golden fixture suite G01-G25

Tests SHALL be written/updated before relying on corresponding implementation behavior.

Acceptance:

- every applicable critical golden test executes and passes;
- exact failure evidence recorded.

### T91. Implement independent persisted-artifact QA

Validate produced Parquet/manifests independently of builder success flags.

Acceptance:

- key/reference/schema/source/gap/boundary/causality checks inspect real artifacts;
- final QA status derived mechanically.

### T92. Implement forbidden-label regression check

Acceptance:

- G19 passes;
- first-pass generated features contain no new impulse/correction/range/breakout/choppiness/parent/Fib/FibTime labels.

### T93. Implement native higher-timeframe reference QA

Compare selected/available complete canonical 1m-derived candles against approved native Binance higher-TF references.

Acceptance:

- G25 passes where applicable;
- unexplained material mismatches fail QA rather than replacing canonical values silently.

## Phase 10 — Bounded real-data smoke only

### T100. Select representative smoke coverage

Choose the smallest real-data slice that exercises:

- normal continuous futures data;
- multiple target resolutions;
- rolling windows;
- atomic pairs/path/volume/volatility;
- at least one approved macro leg;
- extraction;
- where practical, a documented gap/boundary-adjacent condition.

Do not change formulas based on smoke results without updating approved specs/tests.

### T101. Run smoke pipeline

Run through persisted canonical outputs and independent QA.

Acceptance:

- golden tests already PASS;
- smoke QA PASS;
- manifests reconstruct;
- causal extraction contains no retrospective leakage;
- row counts/coverage are plausible and independently checked.

### T102. Stop and report

After smoke:

- report exact coverage;
- report output paths/manifests;
- report QA/golden results;
- report warnings/known source limitations;
- report approximate production storage/runtime evidence if measured;
- STOP.

Do not run full history without the next explicit authorization/review gate.

## Phase 11 — Full production (deferred execution gate)

### T110. Full-history run

This task is defined for planning but SHALL NOT be executed as part of the implementation/smoke assignment unless explicitly authorized after smoke review.

Prerequisites:

- source contract finalized;
- all critical golden tests PASS;
- bounded smoke QA PASS;
- no unresolved critical failures;
- user/approved process authorizes full production.

Production acceptance criteria are the full applicable OpenSpec contracts, manifests, independent QA, and honest coverage status.
