# Design: Structure Research v5 Foundation

## 1. Design intent

Structure Research v5 is a staged research-data pipeline, not a trading-decision engine.

The design prioritizes:

- source fidelity;
- deterministic time-series construction;
- explicit causality;
- stable analytical identities;
- decomposed feature families;
- bounded memory use;
- resumability;
- independent semantic validation;
- efficient later extraction without full-history recomputation.

Business semantics and formulas are defined by the specs. This design defines how those contracts are assembled into a safe implementation.

## 2. Architectural principles

### 2.1 One canonical market-data spine

The canonical market-data spine is approved 1m BTCUSDT data with explicit market type and source continuity.

Canonical target candles `5m`, `15m`, `1H`, `4H`, `1D` are derived from this 1m spine.

Native higher-timeframe Binance candles are QA references only unless a future approved source-contract change says otherwise.

### 2.2 Source continuity is separate from file provenance

Sequential calculations use `source_segment_id`, which represents one continuous market stream.

Raw archive filename, monthly/daily package, local path, download run, or reconstruction provenance remain row-level metadata and do not themselves break continuity.

Real unresolved gaps and spot/futures transitions do break continuity.

### 2.3 Causal and retrospective layers are structurally separate

Fixed and rolling observation features are causal from their documented `available_at` time.

Completed macro-leg identity, endpoint-relative progress, final macro direction, and whole-leg context are retrospective.

Retrospective fields live in dedicated tables and are excluded by causal-only extraction.

### 2.4 Atomic facts are retained before aggregate interpretation

Canonical candles and atomic candle-pair geometry are retained so later research can recompute alternative interval summaries without returning to raw downloads.

The first pass does not collapse path/overlap/speed/volume into semantic market-state labels.

### 2.5 Expensive history is written once and queried many times

Large canonical outputs are partitioned Parquet.

Downstream review/exploration uses extraction with predicate and column pruning rather than loading or converting the full dataset.

## 3. Pipeline stage graph

The implementation SHALL use explicit stages with validated persisted outputs.

Recommended stage ids:

1. `S00_contract_and_config`
2. `S01_source_inventory`
3. `S02_canonical_1m`
4. `S03_source_segments_and_gaps`
5. `S04_fixed_candles`
6. `S05_cross_timeframe_map`
7. `S06_observation_index`
8. `S07_price_speed`
9. `S08_atomic_pairs`
10. `S09_path_activity`
11. `S10_overlap_summary`
12. `S11_volume_volatility`
13. `S12_macro_context`
14. `S13_feature_dictionary_and_manifests`
15. `S14_independent_qa`
16. `S15_extraction_smoke`

A stage SHALL be considered complete only after its output artifacts have passed the validation required for that stage.

## 4. Stage details

### 4.1 S00 — Contract and configuration freeze

Inputs:

- finalized OpenSpec change;
- exact approved macro-leg source path/checksum;
- finalized source contract including actual spot/futures boundary and unresolved gap inventory;
- repository code version;
- run configuration.

Produce a normalized immutable run configuration containing at minimum:

- `schema_version`;
- `source_contract_version`;
- approved source roots/manifests;
- exact market boundary configuration;
- approved macro source path/checksum;
- target timeframes;
- rolling durations and eligible calculation-resolution matrix;
- output root;
- checkpoint root;
- QA mode;
- code commit identifier and dirty-tree state.

Compute a deterministic `config_hash` from normalized semantic configuration.

Do not include mutable runtime-only values such as current clock time in the semantic hash.

### 4.2 S01 — Source inventory

Read approved local source artifacts only.

Inventory:

- market type;
- source/provenance type;
- first/last timestamp;
- row count;
- duplicate timestamps;
- alignment;
- OHLC validity;
- non-finite/invalid numeric values;
- detected gaps;
- source artifact checksum where feasible.

This stage SHALL not derive target candles or research features.

### 4.3 S02 — Canonical 1m construction

Normalize approved source rows into the `candles_1m` contract.

Responsibilities:

- canonical UTC `[start_time,end_time)`;
- stable candle ids;
- source-native OHLCV preservation;
- reconstruction provenance where explicitly approved;
- no synthetic rows for unresolved gaps;
- sorted uniqueness by canonical natural key;
- row-level validation.

Process in bounded chunks/partitions, not one full-history in-memory dataframe.

### 4.4 S03 — Source segments and gap table

Derive continuity from canonical 1m plus finalized source contract.

Create:

- `source_segments`;
- `source_gaps`;
- final `source_segment_id` assignment on canonical rows.

Rules:

- unresolved real gaps split segments;
- spot/futures transition splits segments;
- archive/package/provenance changes alone do not split segments;
- a fully validated same-market repair can restore continuity while retaining row-level reconstruction provenance.

Because stable candle identity excludes segment id, segment reassignment after an approved repair does not change candle ids.

### 4.5 S04 — Canonical fixed candles

Derive all target fixed candles independently from canonical 1m using UTC calendar boundaries.

Target resolutions:

- `5m`
- `15m`
- `1H`
- `4H`
- `1D`.

A complete target candle requires the exact expected set of aligned 1m constituents from one continuous source segment.

If incomplete:

- canonical OHLCV used by research = null;
- coverage fields remain populated;
- optional `observed_only_*` diagnostics may be stored.

Do not recursively build 15m from 5m or 1H from 15m as the canonical method; all canonical target candles derive from 1m to minimize inherited aggregation ambiguity.

### 4.6 S05 — Cross-timeframe containment map

Build deterministic target-to-target mappings using timestamps and canonical ids.

Do not explode persisted 1m-to-every-parent membership.

Persist only approved target-to-target mappings.

Ordinal is zero-based.

### 4.7 S06 — Observation index

Create one identity layer for fixed, rolling, and approved macro observations.

Fixed:

- one-to-one with canonical target candle.

Rolling:

- evaluated on every eligible 5m endpoint;
- one observation id per interval/duration;
- coarser calculation-resolution feature rows reuse the same observation id.

Macro:

- one observation per approved `macro_legs_log20.csv` leg;
- retrospective availability.

This stage calculates only common observation identity/interval geometry needed by later feature stages, not the full feature families.

### 4.8 S07 — Price and speed

Calculate observation-level non-resolution-specific price movement and speed.

Fixed/rolling features use only data available through observation close.

Macro observation movement from approved anchors is retrospective source context.

Adjacent equal-window speed change/acceleration requires both complete windows and no continuity break.

### 4.9 S08 — Atomic candle pairs

For each target calculation resolution, produce chronological neighbor candidate pairs.

Eligibility requires:

- same market/source segment;
- same resolution;
- exact temporal adjacency.

Calculate neutral pair facts:

- range/body overlap;
- overlap location;
- upper/lower extension;
- mirrored penetration from top/bottom.

Do not attach observation-direction semantics at atomic pair construction time.

Boundary candidates may be retained with `pair_eligible=false` for QA, but sequential metrics are null.

### 4.10 S09 — Path/activity/extrema

For each supported `(observation_id, calculation_resolution)`:

- assemble the exact approved constituent sequence;
- enforce coverage and continuity;
- calculate canonical close/log path;
- directional components;
- path efficiency;
- alternation/zero-step behavior;
- range/body/wick/TR activity;
- observation extrema and repeated-extrema timing/count;
- excursions.

Use streaming/grouped partition processing so a whole multi-year dataset is not loaded into memory.

Macro-leg anchor-inclusive path is calculated separately from internal path and only when the required source semantics are valid.

### 4.11 S10 — Overlap summaries

Aggregate eligible atomic pairs fully internal to each observation interval.

Do not include a pair merely because its current candle lies inside the observation if the previous candle lies outside the observation start.

Calculate the required mean/median/share fields and direction-relative fields only after observation direction is known.

### 4.12 S11 — Volume and volatility

Per supported observation/calculation resolution calculate:

- volume totals/mean/median;
- body-direction volume grouping;
- close-step-direction volume grouping;
- adjacent-window volume comparison;
- TR/ATR endpoints;
- realized variance/volatility;
- range/TR/ATR compression-expansion numeric components.

Wilder ATR state is maintained independently per resolution and continuous source segment.

A real gap resets state.

The stage SHALL not assign semantic accumulation, absorption, exhaustion, compression, or expansion labels.

### 4.13 S12 — Macro context

Join fixed/rolling observations to approved macro legs as retrospective context.

Calculate only explicitly approved relationships:

- temporal intersection;
- leg-time progress;
- source/derived macro direction;
- macro-aligned speed/path/penetration where defined.

Do not reinterpret macro legs as validated parent hierarchy.

Do not write macro endpoint-derived values back into causal feature tables.

### 4.14 S13 — Feature dictionary and manifests

Generate the canonical feature dictionary from declared schema/feature definitions, not by heuristically inferring meaning from output columns.

Validate dictionary-to-schema correspondence.

Generate deterministic table manifests/catalog containing:

- schema/version;
- partition keys;
- physical part paths;
- row counts;
- coverage;
- producing run id;
- integrity/checksum evidence;
- validation status.

### 4.15 S14 — Independent QA

QA SHALL read persisted canonical artifacts independently of the producing calculation functions where externally observable.

Run:

- golden fixture suite;
- schema/key/reference checks;
- source gap/boundary invariants;
- Parquet/manifest reconstruction;
- causal leakage checks;
- native higher-timeframe QA on selected/available intervals;
- resume/determinism tests as applicable.

The final QA status is mechanically derived from assertions.

### 4.16 S15 — Extraction smoke

Exercise the real extraction utility against persisted canonical Parquet.

Verify:

- time/market/resolution pruning;
- selected feature-family retrieval;
- causal-only exclusion of retrospective macro data;
- macro-leg extraction;
- CSV export and manifest behavior;
- no hidden recomputation.

## 5. Data dependency graph

Canonical dependencies:

`approved raw/local source data`

-> `candles_1m`

-> `source_segments + source_gaps`

-> `candles_fixed`

-> `cross_timeframe_map`

-> `observation_index`

From `candles_fixed + observation_index`:

- `observation_price_speed`
- `atomic_candle_pairs`
- `observation_path_activity`
- `observation_volume_volatility`

From `atomic_candle_pairs + observation_index`:

- `observation_overlap_summary`

From `macro_legs + observation_index + causal/local feature tables`:

- `observation_macro_context`

All canonical tables:

-> `feature_dictionary + manifests`

-> `independent QA`

-> `extraction`.

No downstream feature table becomes the authoritative input for reconstructing canonical candles.

## 6. Materialization strategy

### 6.1 Materialize once

Materialize:

- canonical 1m;
- canonical target candles;
- target-to-target containment;
- observation index;
- atomic pair geometry;
- approved feature-family tables;
- macro context;
- manifests/dictionary.

These are the expensive/full-history canonical outputs.

### 6.2 Compute only during extraction

Extraction MAY compute presentation-only operations that do not alter canonical research semantics, for example:

- column selection/renaming for human display;
- deterministic row sorting;
- simple display formatting;
- user-requested small CSV subset;
- joins among already materialized canonical tables.

Extraction SHALL NOT silently calculate a missing canonical metric or substitute a newly computed value for the stored canonical metric.

If later research needs a new genuine feature, that is a new materialization/versioned-research change, not an extraction side effect.

## 7. Parquet physical design

Use Zstandard compression.

Use the approved partition plan from the schema contract.

Practical rules:

- avoid one file per day/observation;
- write bounded batches;
- target approximately 128–512 MB compressed parts where table size permits;
- compact small fragments after validated stage completion;
- never expose partially written final parts.

Physical writes follow:

`temporary path -> close/write success -> schema/content validation -> atomic promotion -> manifest update`.

Manifest update occurs only after part validation.

## 8. Checkpoint and resume design

### 8.1 Checkpoint granularity

A checkpoint represents a validated completed work unit, not an arbitrary loop counter.

Recommended unit:

- one canonical physical partition or bounded partition chunk;
- plus stage id and schema/source/config identity.

Persist often enough that no more than 20 minutes of validated completed work is at risk.

### 8.2 Checkpoint identity

Every checkpoint SHALL include at minimum:

- stage id/version;
- input/source fingerprint;
- `config_hash`;
- schema version;
- source-contract version;
- partition/work-unit key;
- produced artifact path(s);
- artifact checksum/integrity evidence;
- validation result;
- producing run id.

### 8.3 Resume behavior

On resume:

1. discover checkpoint;
2. validate semantic compatibility;
3. validate referenced completed artifacts;
4. skip only proven valid completed units;
5. continue at the first incomplete/invalid unit.

Do not trust checkpoint metadata without revalidating referenced final artifacts.

Stale/incompatible/corrupt state fails explicitly.

### 8.4 Idempotency

Stable ids and natural keys guarantee that rerun/resume does not create duplicate canonical entities.

Writers SHALL validate uniqueness before promotion.

## 9. Incremental rolling design

Rolling observations are evaluated chronologically on the 5m endpoint grid.

For each approved duration maintain bounded deques/state per continuous market segment.

For coarser calculation resolutions, update the relevant constituent state only when that resolution closes.

At an eligible endpoint:

- select the exact complete duration;
- require all expected constituents;
- produce the one observation identity for that interval;
- write resolution-specific feature row(s).

Historical production is linear/incremental. Previously finalized historical rolling rows are not recomputed at every later endpoint.

For implementation simplicity and deterministic replay, partition-level recomputation after a process restart is allowed only for the bounded uncommitted work unit; previously validated/promoted partitions are reused.

## 10. Causality implementation

Each feature definition declares:

- availability class;
- available-at rule.

Causal fixed/rolling features must be functions only of input whose timestamps/availability are <= observation `available_at`.

Retrospective joins occur after causal/local feature materialization.

The extraction API accepts an `availability_class` filter and optional `as_of`.

A causal-only query never implicitly left-joins macro context.

Future-data invariance is a critical regression test.

## 11. Source-boundary and gap implementation

The exact source boundary is configuration supplied by the finalized source contract.

It is not duplicated in feature code.

Every sequential algorithm uses the same continuity predicate:

- same market type/segment;
- expected temporal adjacency;
- complete required rows.

This predicate is shared conceptually across:

- returns;
- TR/ATR;
- path;
- RV;
- overlap pairs;
- alternation;
- rolling windows;
- adjacent-window comparisons.

Where implementation uses shared helper code, tests must prove that helper semantics match each spec rather than assuming reuse is correct.

## 12. Macro-leg architecture

The approved macro CSV is an input dimension, not a source of new classifications.

Store:

1. original/source macro leg fields;
2. independent QA/recomputed descriptive fields;
3. macro observation id;
4. source-regime/boundary status.

Whole-leg feature calculation reuses the same feature engines where semantics match, with explicit macro anchor handling.

Do not duplicate separate untested formula implementations for macro legs if the fixed/rolling formula is mathematically identical.

Where macro semantics differ, such as anchor-inclusive path or retrospective direction, implement/test that difference explicitly.

## 13. Extraction utility design

Provide a deterministic CLI or repository-standard callable interface.

Required filter dimensions:

- time range;
- market type;
- source segment;
- fixed timeframe;
- rolling duration;
- calculation resolution;
- observation id(s);
- macro leg id(s);
- logical feature family;
- explicit columns;
- availability class;
- optional as-of time.

Operation:

1. read logical-table manifest/catalog;
2. choose candidate Parquet partitions via predicates;
3. read only requested/needed columns where supported;
4. apply joins/filters;
5. validate result schema;
6. sort deterministically;
7. export CSV according to review-size contract.

Do not require a full Parquet-to-CSV conversion before filtering.

## 14. Error and status model

Distinguish:

- expected documented source limitation;
- incomplete calculation because coverage is insufficient;
- invalid source/schema;
- calculation bug;
- QA failure;
- system/runtime failure.

A documented irrecoverable gap is not itself a pipeline bug.

Incorrectly bridging or hiding that gap is a critical bug.

Stages SHALL not catch critical exceptions and emit successful empty outputs.

Failure state remains visible to final QA.

## 15. Testing and validation architecture

### 15.1 Unit/golden tests

Use isolated synthetic fixtures with exact expected outputs.

### 15.2 Integration tests

Verify real persisted Parquet and manifests, not only in-memory results.

### 15.3 Regression tests

Protect confirmed historical failure classes listed in repository `AGENTS.md` and the golden-test spec.

### 15.4 Real-data smoke

After golden tests pass, run a bounded representative real-data interval.

The smoke should include where practical:

- normal futures continuity;
- a documented historical source gap or boundary-adjacent case;
- multiple target timeframes;
- rolling observations;
- at least one approved macro leg;
- extraction.

Do not use the smoke to discover/change business formulas silently.

## 16. Full production execution policy

Full-history production is not automatically launched when implementation/tests complete.

Before full production:

- source contract finalized;
- critical golden tests pass;
- real-data smoke passes independent QA;
- smoke outputs are reviewed;
- user explicitly authorizes the expensive full run when required by the surrounding task/process.

## 17. Dependency policy

Prefer the existing repository stack.

Do not add new dependencies without checking repository configuration and the `AGENTS.md` dependency rule.

If existing Parquet/dataframe tooling can meet the contract correctly, use it.

A new dependency requires explicit approval before addition.

## 18. Open design dependency

At the time this design is written, one source-contract item remains externally pending: the exact earliest usable Binance BTCUSDT USDT-M futures 1m history and final actual spot-to-futures boundary.

The architecture does not depend on a guessed date.

When the source investigation completes, update the single source-contract/configuration value and associated gap/coverage evidence; feature code and QA shall consume that configuration rather than require redesign.
