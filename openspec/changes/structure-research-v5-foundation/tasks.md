# Tasks: Structure Research v5 Foundation

## Execution policy
Implement in order. Do not launch full-history production without explicit approval. A file-writing step is not complete until semantic validation passes.

## Phase 0 — Freeze contracts
### T00 Source/config truth
Freeze canonical boundary/gap evidence, macro checksum, localization checksum, approved aggTrade source rule, price-unit rule, calculation matrices, output/checkpoint roots and code/config hash.
### T01 Typed schemas
Implement all logical tables including macro anchors, aggTrade evidence, boundary fragments and 118 macro retracement relationships.
### T02 Stable ids
Implement UUIDv5 identities including macro anchors/retracements/fragments and exact golden fixtures.

## Phase 1 — Canonical source spine
### T10 Inventory
Validate source provenance/market/timeframe/coverage/duplicates/OHLC/numerics/checksums and timestamp alignment. Distinguish real gaps from continuous off-grid series.
### T11 Canonical 1m
Observed approved data only. Preserve raw timestamp provenance; canonicalize off-grid sources only under proven source-specific rule. Exclude post-boundary spot and synthetic futures 19:00.
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
Verify `macro_legs_log20.csv` checksum and 128 legs.
### T21 Localization artifact
Verify checksum, 138 pivots, 131 unique-window, 7 multiple-window, 145 candidates, including E00059/E00065/E00070. Every candidate is half-open `[candidate_start,candidate_start+5m)`.

### T22 Approved aggTrade refinement
Use already downloaded official same-market Binance BTCUSDT `aggTrades`; raw individual trades are excluded unless separately approved.

For every anchor:
- scan all approved candidate windows;
- preserve every exact source-anchor-price aggTrade touch ordered by `(event_time,agg_trade_id)`;
- if exact touches exist, select earliest exact touch;
- otherwise high pivot selects maximum realized aggTrade price and low pivot selects minimum realized aggTrade price;
- preserve every occurrence of selected extremum;
- unique selected extremum resolves price/time/id;
- repeated selected extremum preserves price but leaves time/id unresolved pending separate explicit tie-break;
- preserve source anchor coordinate separately;
- use exact Decimal/fixed-point identity;
- preserve `buyer_is_maker`.

Missing/incomplete aggTrades are reported; never switch automatically to raw trades.

### T22A Bounded aggTrade source reader
Implement one bounded official-aggTrade access layer used by candidate refinement and fragment construction.

Mandatory:
- candidate reads return only requested candidate-window rows;
- fragment reads return only the complete requested canonical 5m bucket `[B0,B1)`;
- no per-anchor/per-fragment whole-day or whole-month materialization;
- no repeated whole-archive parsing inside hot loops;
- same bucket/window should be reused within the pass when practical;
- ZIP/CSV sources are iterated with a robust streaming parser/filter;
- `pandas.read_csv` or equivalent whole-file parser is prohibited as the fragment-stage bucket reader;
- parser/read failure is `source_reader_failure`, not market-data absence and not permission for raw fallback;
- instrument counters for archive opens, bytes/rows scanned, requested interval, returned rows, cache hits/misses and peak buffered rows/bytes.

### T23 Shared macro anchors
Create one `macro_anchor_id` per source event. Store source coordinate, localization, refinement method/status, refined realized price, resolved time/id when deterministic, evidence and uncertainty.

### T24 Boundary fragments
For one authoritative pivot aggTrade key create LEFT/RIGHT fragments. Pivot aggTrade belongs LEFT once; RIGHT begins from pivot price state and excludes pivot row. Multi-underlying aggregate is indivisible. Canonical candles unchanged.

Boundary fragment identity is deterministic from `macro_anchor_id + side + calculation_resolution`; leg membership is separate context.

Fragment source read MUST use T22A bounded 5m bucket reader and SHALL NOT load a complete day/month.

### T25 Unresolved-time fallback
Do not force a split when time remains unresolved. Derive only guaranteed fixed-grid interior. If none exists, expected/observed counts are zero and boundary-dependent fallback metrics null with `no_unambiguous_interior`.
### T26 Market/provenance
Canonical market scope and historical macro provenance remain separate.

## Phase 3 — Observation identity and movement
### T30 Observation index
Exact macro start/end/duration only when both endpoint times resolve.
### T31 Price/speed
Fixed/rolling canonical metrics; macro source speed separate; refined whole-leg speed only with resolved endpoints.

## Phase 4 — Path/activity
### T40 Atomic canonical pairs
Same-segment/resolution/exact adjacency.
### T41 Fixed/rolling path/activity
Approved matrices/Q sequence.
### T42 Refined macro close path
For R in 5m/15m/1H/4H/1D: refined start pivot -> qualifying R closes -> refined end pivot if needed. Never mix aggTrade fragment path into TF path.
### T43 Boundary microstructure
Persist separate aggregate-trade LEFT/RIGHT path/activity/volume metrics.
### T44 Fallback macro path
Only guaranteed fixed-grid constituents; Q begins with first eligible open.

## Phase 5 — Overlap
### T50 Observation overlap
Use exact self-contained formulas in `price-path-speed-and-overlap/spec.md`. Resolved macro uses typed non-overlapping sequence `start RIGHT fragment -> interiors -> end LEFT fragment` with same pair formulas/aggregation and no boundary-candle duplication. Fallback uses only guaranteed interior pairs.

## Phase 6 — Volume/volatility
### T60 Directional volume
Body and close-step conventions.
### T61 TR/ATR
Materialize both `atr14_sma` and `atr14_wilder`. TR requires valid adjacent previous close same segment/resolution. Reset across gap/source break; first following TR null; both ATRs require 14 new consecutive valid TRs. Fallback may not import previous close from outside guaranteed interval.
### T62 Fixed/rolling RV/range
Macro RV deferred.
### T63 Rolling volume comparisons
Canonical names.
### T64 Macro volume/activity
Resolved: start RIGHT + interior + end LEFT. Fallback: guaranteed interior only.

## Phase 7 — Macro context/retracement
### T70 Retrospective macro context
Exact temporal fractions only with resolved endpoint times.
### T71 Retracement formula
Direct percentage, no Fib.
### T72 Production retracement set
Exactly 118 adjacent opposite-direction shared-pivot relationships; 9 discontinuous excluded.

## Phase 8 — Dictionary/manifests/extraction
### T80 Feature dictionary
Define exact/fallback/source/aggTrade semantics once.
### T81 Manifests
All logical tables including aggTrade evidence/fragments.
### T82 Extraction
Support macro source/localization/refinement/fallback/fragments/retracements without hidden recomputation/raw substitution. Use partition/column pruning and bounded source access where source archives are involved.

## Phase 9 — Checkpoint/resume
### T90/T91/T92
Persist validated collected/derived data no later than every 20 minutes so <=20 minutes completed work is at risk; validate source/config/schema/localization/refinement checksums; atomic promotion; clean vs resumed equivalence.

## Phase 10 — QA
### T100 Golden suite
Implement/pass synchronized golden suite. Fixtures are self-contained.
### T100A Bounded-I/O QA gate
Instrumented tests MUST fail if:
- one fragment request reads/parses a complete aggTrade day/month instead of only its 5m bucket;
- an anchor loop repeatedly reopens/reparses the same archive/bucket unnecessarily when reusable bounded result exists;
- fragment hot path invokes pandas/full-file materialization;
- parser failure causes raw-trade fallback;
- returned fragment source rows do not exactly equal the official aggTrade rows in requested `[B0,B1)` after deterministic ordering.

The QA report records source interval requested, archive/member, scanned/returned row counts, bytes if available, archive open count and cache statistics.

### T101 Independent artifact QA
Inspect persisted Parquet/manifests, not builder flags.
### T102 Forbidden labels/names
No impulse/correction/range/chop/Fib/FibTime/Elliott labels.
### T103 Reference trust
Legacy inconsistent higher-TF caches remain diagnostic unless independently validated.

## Phase 11 — Bounded smoke only
### T110
Representative continuous/gap/boundary/off-grid-source and macro exact/extreme/repeated-extreme fixtures, including at least one large aggTrade archive whose fragment request proves bounded 5m streaming access.
### T111
Run bounded smoke after all applicable golden and bounded-I/O tests pass.
### T112
Report outputs/coverage/QA/runtime/storage/I/O counters and STOP.

## Phase 12 — Full production deferred
### T120
Full-history execution requires reviewed real refinement artifact, successful implementation/golden/I/O/smoke review and explicit user authorization.
