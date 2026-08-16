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

### T21 Localization artifact
Verify checksum `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`, 138 unique pivots, 131 unique localization windows, 7 multiple-window pivots, zero unresolved.

Verify 145 distinct candidate windows total:
- 142 canonical-grid 5m windows;
- exactly three known off-grid source-localization windows: E00059/E00065/E00070 with `+20.799s` starts.

Use this artifact for anchor-level source precision/market/refinement fields. Do not derive anchor precision from per-leg `duration_precision`.

### T22 Approved aggTrade-refinement artifact
Before real macro production, load/freeze separately reviewed refinement output generated under `macro-trade-boundary-refinement`.

The approved source is already downloaded official Binance BTCUSDT `aggTrades` for the corresponding spot/futures market.

Verify:
- official same-market aggTrade provenance/checksums;
- source granularity explicitly equals `agg_trade`;
- all 145 candidate windows are examined;
- exact `price_units` matching;
- every matching `agg_trade_id` touch is preserved and ordered by `(event_time,agg_trade_id)`;
- first/last underlying trade ids retained where supplied.

Raw individual trade files are outside the approved calculation path. If they exist on disk from the earlier unapproved download, do not read/use them for pivot selection, fragments, feature calculation or QA truth. Any future use requires a separate explicit user decision.

If approved aggTrades are insufficient/missing for a case, report that case rather than switching source type automatically.

For E00059/E00065/E00070, official aggTrade evidence must locate the resolved pivot event and actual canonical 5m candle containing it; the off-grid source window start must never become canonical candle identity.

### T23 Shared macro anchors
Create one `macro_anchor_id` per source event. Store separate source window, localization windows/kinds, aggTrade refinement status/time/id, canonical pivot 5m containment and fallback uncertainty.

### T24 Boundary fragments
For one unique matching aggTrade pivot create LEFT/RIGHT fragments inside canonical 5m containment and compose higher-TF fragments from canonical 5m + complete canonical 5m intervals.

The pivot aggTrade row belongs to LEFT once as an indivisible approved source record. RIGHT begins from pivot price state and excludes that row. If the pivot aggTrade contains multiple underlying trades, do not split its internal quantity/count; mark aggregate boundary precision explicitly. Canonical candles remain unchanged.

### T25 Ambiguity fallback
Multiple/no/unavailable aggTrade touch never gets an arbitrary exact pivot. Derive only conservative fallback unambiguous interval.

### T26 Market/provenance
Canonical market scope and historical macro provenance remain separate.

## Phase 3 — Observation identity and movement

### T30 Observation index
Macro exact start/end/duration only when both endpoints have one unique approved aggTrade touch; otherwise source coordinates stay explicitly source-named and exact fields null.

### T31 Price/speed
Fixed/rolling canonical metrics.

Macro:
- source speed preserved under `source_*`;
- endpoint-to-endpoint whole-leg macro speed only when both pivots are uniquely aggTrade-resolved;
- no separate whole-leg speed definition per TF.

## Phase 4 — Path/activity

### T40 Atomic canonical pairs
Same-segment/resolution/exact adjacency.

### T41 Fixed/rolling path/activity
Approved matrices and Q sequence.

### T42 Exact macro close path
For each R in 5m/15m/1H/4H/1D:
`Q0=start pivot price -> qualifying R closes -> end pivot price if needed`.

Never add aggTrade boundary path to TF close path.

### T43 Boundary microstructure
Persist separate aggregate-trade LEFT/RIGHT path/activity/volume metrics from ordered aggTrade evidence. Do not label them raw-trade metrics.

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
Exact: start RIGHT fragment + interior + end LEFT fragment. Fallback: guaranteed interior only. Never full boundary candle + fragment together. Multi-underlying pivot aggTrade stays indivisible and carries an explicit aggregate-boundary volume precision flag.

## Phase 7 — Macro context/retracement

### T70 Retrospective macro context
Exact temporal fractions only with exact approved aggTrade pivots; otherwise explicitly source/fallback.

### T71 Retracement formula
Direct percentage formula, no Fib.

### T72 Production retracement set
Generate exactly the adjacent opposite-direction shared-pivot relationships from approved source. Expected count 118; 9 discontinuous adjacent transitions excluded. A/B/C are macro anchor ids.

## Phase 8 — Dictionary/manifests/extraction

### T80 Feature dictionary
Define exact/fallback/source/aggTrade feature semantics once.

### T81 Manifests
All logical tables including aggTrade touches/fragments.

### T82 Extraction
Support macro source/localization/aggTrade/fallback fields, boundary fragments, retracements and causal exclusion without hidden recomputation or hidden raw-trade substitution.

## Phase 9 — Checkpoint/resume

### T90/T91/T92
<=20 min validated work at risk; validate source/config/schema/localization/aggTrade-refinement checksums; atomic promotion; clean vs resumed equivalence.

## Phase 10 — QA

### T100 Golden suite
Implement/pass G01-G50 (or later synchronized highest number).

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
- reviewed real approved aggTrade-refinement artifact
- successful implementation/golden/smoke review
- explicit user authorization.
