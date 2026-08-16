# Tasks: Structure Research v5 Foundation

## Execution policy

Implement in order. Do not launch full-history production without explicit approval. A file-writing step is not complete until semantic validation passes.

## Phase 0 — Freeze contracts

### T00 Source/config truth
Freeze canonical boundary/gap evidence, macro checksum, localization checksum, approved aggTrade source rule, price-unit rule, calculation matrices, output/checkpoint roots and code/config hash.

### T01 Typed schemas
Implement all logical tables including macro anchors, aggTrade touches, boundary fragments and 118 macro retracement relationships.

### T02 Stable ids
Implement UUIDv5 identities including macro anchors/retracements and exact golden fixtures.

## Phase 1 — Canonical source spine

### T10 Inventory
Validate source provenance/market/timeframe/coverage/duplicates/OHLC/numerics/checksums and source-native timestamp alignment. Distinguish real missing coverage from continuous off-grid series.

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

### T21 Localization artifact
Verify checksum, 138 unique pivots, 131 unique localization windows, 7 multiple-window pivots, zero unresolved and 145 candidate windows. Treat every candidate as half-open `[candidate_start,candidate_start+5m)`. Exactly three known off-grid source-localization windows are E00059/E00065/E00070.

### T22 Approved aggTrade-refinement artifact
Use already downloaded official same-market Binance BTCUSDT `aggTrades`; raw individual trades are excluded unless separately approved.

For every anchor:
- scan all approved candidate windows;
- preserve every exact source-anchor-price aggTrade touch ordered by `(event_time,agg_trade_id)`;
- if exact touches exist, select the earliest exact touch;
- otherwise high pivot selects maximum realized aggTrade price and low pivot selects minimum realized aggTrade price;
- preserve every row attaining the selected extremum;
- if selected extremum occurs once, resolve price/time/id;
- if it repeats, preserve resolved realized price but leave authoritative time/id unresolved pending explicit tie-break approval;
- preserve source anchor price/time separately;
- use exact Decimal/fixed-point price identity;
- record `buyer_is_maker` rather than vague maker-side semantics.

If approved aggTrades are missing/incomplete, report the case; do not switch source automatically.

### T23 Shared macro anchors
Create one `macro_anchor_id` per source macro event. Store source coordinate, localization windows/kinds, refinement method/status, refined realized price, resolved time/id when deterministic, evidence rows, canonical pivot 5m containment and uncertainty.

### T24 Boundary fragments
For one authoritative pivot aggTrade key create LEFT/RIGHT fragments. Pivot aggTrade belongs to LEFT once; RIGHT begins from pivot price state and excludes that row. Multi-underlying aggregate is indivisible. Canonical candles remain unchanged.

Boundary fragment identity SHALL be deterministic from `macro_anchor_id + side + calculation_resolution`; associated macro leg membership is stored separately and does not redefine fragment identity.

### T25 Unresolved-time fallback
Do not force a split when authoritative pivot time remains unresolved. Derive only guaranteed fixed-grid interior. If no guaranteed slot exists, expected/observed counts are zero and boundary-dependent fallback metrics are null with `no_unambiguous_interior` or equivalent explicit status.

### T26 Market/provenance
Canonical market scope and historical macro provenance remain separate.

## Phase 3 — Observation identity and movement

### T30 Observation index
Exact macro start/end/duration only when both endpoint times are deterministically resolved. Source coordinates remain explicit provenance.

### T31 Price/speed
Fixed/rolling canonical metrics. Macro source speed preserved under `source_*`; refined endpoint-to-endpoint whole-leg speed only when both endpoint times are resolved.

## Phase 4 — Path/activity

### T40 Atomic canonical pairs
Same-segment/resolution/exact adjacency.

### T41 Fixed/rolling path/activity
Approved matrices and Q sequence.

### T42 Exact macro close path
For each R in 5m/15m/1H/4H/1D:
`Q0=refined start pivot price -> qualifying R closes -> refined end pivot price if needed`.

Never add aggTrade boundary path to TF close path.

### T43 Boundary microstructure
Persist separate aggregate-trade LEFT/RIGHT path/activity/volume metrics. Do not label them raw-trade metrics.

### T44 Fallback macro path
Only guaranteed fixed-grid constituents. Sequence starts at open of first eligible candle. Expected count is grid-contained slot count; persist measured start/end.

## Phase 5 — Overlap

### T50 Observation overlap
Use the exact self-contained formulas in `price-path-speed-and-overlap/spec.md`. Fixed/rolling use eligible canonical pairs. Exact macro uses the non-overlapping typed constituent sequence `start RIGHT fragment -> complete interiors -> end LEFT fragment`, comparing immediately adjacent constituents at the same calculation resolution, with the same mean/median/count aggregation and no full-boundary-candle duplication. Fallback uses only canonical pairs wholly inside guaranteed interior.

## Phase 6 — Volume/volatility

### T60 Directional volume
Body and close-step conventions.

### T61 TR/ATR
Materialize both `atr14_sma` and `atr14_wilder`. TR requires a valid immediately adjacent previous close in the same source segment/resolution. After gap/source reset, first following TR is null. Both ATRs initialize/reinitialize only after 14 consecutive valid TR values; Wilder then uses recursive update while SMA uses rolling latest-14 valid TR values.

### T62 Fixed/rolling RV/range
Macro RV remains deferred.

### T63 Rolling volume comparisons
Canonical names.

### T64 Macro volume/activity
Exact: start RIGHT fragment + interior + end LEFT fragment. Fallback: guaranteed interior only. Never full boundary candle + fragment together.

## Phase 7 — Macro context/retracement

### T70 Retrospective macro context
Exact temporal fractions only with deterministically timed approved aggTrade pivots; otherwise explicitly source/fallback.

### T71 Retracement formula
Direct percentage formula, no Fib.

### T72 Production retracement set
Generate exactly adjacent opposite-direction shared-pivot relationships. Expected count 118; 9 discontinuous transitions excluded. A/B/C are macro anchor ids.

## Phase 8 — Dictionary/manifests/extraction

### T80 Feature dictionary
Define exact/fallback/source/aggTrade feature semantics once.

### T81 Manifests
All logical tables including aggTrade touches/fragments.

### T82 Extraction
Support macro source/localization/refinement/fallback fields, boundary fragments, retracements and causal exclusion without hidden recomputation or raw-trade substitution.

## Phase 9 — Checkpoint/resume

### T90/T91/T92
Persist validated collected/derived data no later than every 20 minutes so <=20 minutes completed work is at risk; validate source/config/schema/localization/aggTrade-refinement checksums; atomic promotion; clean vs resumed equivalence.

## Phase 10 — QA

### T100 Golden suite
Implement/pass the synchronized golden suite. Fixtures must be self-contained in the QA spec; tests may not depend on an undocumented external example.

### T101 Independent artifact QA
Inspect persisted Parquet/manifests, not builder flags.

### T102 Forbidden labels/names
No impulse/correction/range/chop/Fib/FibTime/Elliott labels.

### T103 Reference trust
Legacy inconsistent higher-TF caches remain diagnostic unless independently validated.

## Phase 11 — Bounded smoke only

### T110
Choose representative continuous/gap/boundary/off-grid-source and macro exact/extreme/repeated-extreme fixtures.

### T111
Run bounded smoke after all applicable golden tests pass.

### T112
Report outputs/coverage/QA/runtime/storage and STOP.

## Phase 12 — Full production deferred

### T120
Planning only. Full-history execution requires reviewed real approved aggTrade-refinement artifact, successful implementation/golden/smoke review and explicit user authorization.
