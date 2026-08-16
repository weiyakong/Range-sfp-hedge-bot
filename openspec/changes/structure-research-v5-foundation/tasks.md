# Tasks: Structure Research v5 Foundation

## Execution policy

Implement in order. Do not launch full-history production without explicit approval. A file-writing step is not complete until semantic validation passes.

## Phase 0 — Freeze contracts

### T00 Source/config truth
Freeze canonical boundary/gap evidence, macro checksum, 5m localization checksum, price-unit rule, calculation matrices, output/checkpoint roots and code/config hash.

### T01 Typed schemas
Implement all logical tables including macro anchors, trade touches, boundary fragments and 118 macro retracement relationships.

### T02 Stable ids
Implement UUIDv5 identities including macro anchors/retracements and exact golden fixtures.

## Phase 1 — Canonical source spine

### T10 Inventory
Validate source provenance/market/timeframe/coverage/duplicates/OHLC/numerics/checksums and source-native timestamp alignment.

Distinguish real missing coverage from a continuous 60-second off-grid series. Required fixture: December-2017 `+20.799s` source rows must not become 1440 missing minutes.

### T11 Canonical 1m
Observed approved data only. Preserve raw timestamp provenance; canonicalize off-grid sources only under a proven source-specific rule. Exclude post-boundary spot and synthetic futures 19:00.

### T12 Gaps/segments
Recompute strict canonical gaps/segments. Real gaps/market transition split continuity; archive changes do not.

### T13 Fixed UTC grid
Build 5m/15m/1H/4H/1D from canonical 1m with explicit incomplete boundary/gap rows.

### T14 Geometry
Complete target candle geometry.

### T15 Cross-TF map
Deterministic containment/ordinal mappings.

## Phase 2 — Macro refinement artifacts MUST precede real macro metrics

### T20 Macro source
Verify exact `macro_legs_log20.csv` checksum and 128 legs.

### T21 5m localization artifact
Verify checksum `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`, 138 unique pivots, 131 unique-5m, 7 multiple-5m, zero unresolved.

Use this artifact for anchor-level source precision/market/refinement fields. Do not derive anchor precision from per-leg `duration_precision`.

### T22 Trade-refinement artifact
Before real macro production, load/freeze separately reviewed trade-refinement output generated under `macro-trade-boundary-refinement`.

Verify official same-market provenance, checksums, source granularity, all candidate 5m intervals, exact price_units, every touch and native sequence ordering.

### T23 Shared macro anchors
Create one `macro_anchor_id` per source event. Store separate source window, 5m localization, trade status/exact time, and fallback uncertainty fields.

### T24 Boundary fragments
For unique exact pivots create LEFT/RIGHT fragments at 5m and compose higher-TF fragments from 5m + complete canonical 5m intervals.

Pivot source record count/volume belongs to LEFT once. Canonical candles unchanged.

### T25 Ambiguity fallback
Multiple/no/unavailable trade touch never gets an arbitrary exact pivot. Derive only conservative fallback unambiguous interval.

### T26 Market/provenance
Canonical market scope and historical macro provenance remain separate.

## Phase 3 — Observation identity and movement

### T30 Observation index
Macro exact start/end/duration only when both endpoints exact; otherwise source coordinates stay explicitly source-named and exact fields null.

### T31 Price/speed
Fixed/rolling canonical metrics.

Macro:
- source speed preserved under `source_*`;
- exact endpoint-to-endpoint whole-leg macro speed only when both pivots exact;
- no separate whole-leg speed definition per TF.

## Phase 4 — Path/activity

### T40 Atomic canonical pairs
Same-segment/resolution/exact adjacency.

### T41 Fixed/rolling path/activity
Approved matrices and Q sequence.

### T42 Exact macro close path
For each R in 5m/15m/1H/4H/1D:
`Q0=start pivot price -> qualifying R closes -> end pivot price if needed`.

Never add trade fragment path to TF close path.

### T43 Boundary microstructure
Persist separate `trade_*` LEFT/RIGHT path/activity/volume metrics from ordered trade evidence.

### T44 Fallback macro path
Only guaranteed fixed-grid constituents. Sequence starts at open of first eligible candle. Expected count is grid-contained slot count; persist measured start/end.

## Phase 5 — Overlap

### T50 Observation overlap
Fixed/rolling canonical pairs. Exact macro uses typed fragment/interior relationships without double counting. Fallback uses only guaranteed interior pairs.

## Phase 6 — Volume/volatility

### T60 Directional volume
Body and close-step conventions.

### T61 TR/ATR
Continuity-aware reset/init.

### T62 Fixed/rolling RV/range
Macro RV remains deferred.

### T63 Rolling volume comparisons
Canonical names.

### T64 Macro volume/activity
Exact: start RIGHT fragment + interior + end LEFT fragment. Fallback: guaranteed interior only. Never full boundary candle + fragment together.

## Phase 7 — Macro context/retracement

### T70 Retrospective macro context
Exact temporal fractions only with exact pivots; otherwise explicitly source/fallback.

### T71 Retracement formula
Direct percentage formula, no Fib.

### T72 Production retracement set
Generate exactly the adjacent opposite-direction shared-pivot relationships from approved source. Expected count 118; 9 discontinuous adjacent transitions excluded. A/B/C are macro anchor ids.

## Phase 8 — Dictionary/manifests/extraction

### T80 Feature dictionary
Define exact/fallback/source/trade feature semantics once.

### T81 Manifests
All logical tables including trade touches/fragments.

### T82 Extraction
Support macro source/localization/trade/fallback fields, boundary fragments, retracements and causal exclusion without hidden recomputation.

## Phase 9 — Checkpoint/resume

### T90/T91/T92
<=20 min validated work at risk; validate source/config/schema/localization/trade-refinement checksums; atomic promotion; clean vs resumed equivalence.

## Phase 10 — QA

### T100 Golden suite
Implement/pass G01-G49 (or later synchronized highest number).

### T101 Independent artifact QA
Inspect persisted Parquet/manifests, not builder flags.

### T102 Forbidden labels/names
No impulse/correction/range/chop/Fib/FibTime/Elliott labels.

### T103 Reference trust
Legacy inconsistent higher-TF caches remain diagnostic unless independently validated.

## Phase 11 — Bounded smoke only

### T110
Choose representative continuous/gap/boundary/off-grid-source and macro exact/ambiguous fixtures.

### T111
Run bounded smoke after all applicable golden tests pass.

### T112
Report outputs/coverage/QA/runtime/storage and STOP.

## Phase 12 — Full production deferred

### T120
Planning only. Full-history execution requires:
- reviewed real trade-refinement artifact
- successful implementation/golden/smoke review
- explicit user authorization.
