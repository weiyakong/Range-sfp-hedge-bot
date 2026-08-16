# Design: Structure Research v5 Foundation

## 1. Design intent

Structure Research v5 is a staged descriptive research-data pipeline, not a trading-decision engine.

Priorities: source fidelity, deterministic time construction, explicit causality, stable identities, exact price identity, bounded memory, resumability, independent QA, exact aggTrade-resolved macro boundaries where evidence permits, and conservative fallback where they do not.

## 2. Canonical market source

Strict canonical 1m:
- spot before `2019-09-08T17:57:00Z`
- USDT-M futures from that boundary
- documented gaps preserved, including futures 19:00
- post-boundary spot excluded from combined canonical chronology
- synthetic 19:00 diagnostic excluded from canonical 1m.

Canonical `5m/15m/1H/4H/1D` derive from strict canonical 1m.

Source inventory distinguishes true gaps from continuous off-grid source timestamps. A continuous `+20.799s` source series is not automatically missing; canonicalization requires proven source-specific mapping and retained raw timestamp provenance.

## 3. Macro prerequisites

Approved macro source:
`macro_legs_log20.csv`
SHA-256 `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

Reviewed localization:
`macro_pivots_5m_all.csv`
SHA-256 `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`.

It contains 138 unique pivots: 131 unique localization windows and 7 multiple-window pivots, no unresolved coverage.

There are 145 candidate windows total. 142 are canonical-grid 5m windows. Three spot windows (`E00059`,`E00065`,`E00070`) inherit the known `+20.799s` source offset and are not canonical 5m candles. The refinement stage must resolve their pivot from the approved official Binance `aggTrades` source and then assign the actual canonical 5m candle containing that aggTrade event time.

Before real macro production, a separate refinement stage examines all 145 candidate windows using the already downloaded same-market official Binance BTCUSDT `aggTrades` data and freezes a reviewed refinement artifact/checksum.

`aggTrades` are the approved source for this stage. Raw individual trade files are not preferred and are not part of the approved calculation path. Raw trade files already downloaded during the earlier unapproved attempt may remain on disk, but their presence does not authorize their use. They may enter the project only after a separate explicit user decision.

If approved `aggTrades` coverage is missing for a required candidate interval, record/report that limitation. Do not substitute or download raw trades automatically.

The main v5 pipeline consumes the frozen aggTrade-refinement artifact. It does not independently choose touches or switch source type.

## 4. Macro boundary model

Every anchor preserves:
- original source coordinate/precision/provenance;
- localization candidate windows and whether each is canonical-grid or off-grid source-localization;
- every exact matching aggTrade row considered;
- canonical 5m containment after aggTrade resolution;
- exact pivot time + `agg_trade_id` only when one unique matching aggTrade row exists;
- first/last underlying trade ids and whether the pivot aggTrade contains one or multiple underlying trades;
- fallback uncertainty otherwise.

Localization is not exact timing. A resolved timestamp is exact only at the approved aggTrade source resolution; the pipeline does not reconstruct unobserved individual raw-trade timing inside an aggregate.

For one unique matching aggTrade row, create LEFT/RIGHT boundary fragments inside the canonical 5m candle containing that row, without altering canonical candles. The pivot aggTrade is an indivisible approved source record and belongs to LEFT once; RIGHT starts from the pivot price state and excludes that aggregate row. If the pivot aggTrade contains multiple underlying trades, its quantity/count is not split internally between LEFT and RIGHT.

At higher TFs, partial boundaries are composed from the aggTrade-resolved partial canonical 5m piece plus complete canonical 5m intervals.

## 5. Macro measurements

Exact whole-leg duration/speed use endpoint coordinates resolved at approved aggTrade resolution. Original source duration/speed remain separate provenance.

Exact macro close-path at resolution R uses:
`exact start price -> chronological complete R closes ending after start and no later than end -> exact end price if needed`.

Aggregate-trade fragment path remains a separate microstructure family and is never added to TF close path.

Exact macro volume/activity uses:
start RIGHT fragment + complete interior intervals + end LEFT fragment, with no full boundary candle double-counting. Any multi-underlying pivot aggregate remains indivisible at the boundary and carries an explicit aggregate-boundary precision flag.

If a pivot remains ambiguous after aggTrade refinement, exact boundary metrics remain null and fallback uses only fixed-grid intervals guaranteed to lie between all possible matching aggTrade touches. Expected fallback count is grid-slot count, not duration/resolution.

Macro RV remains deferred.

## 6. Retracement

First-pass production retracement is the immediately following opposite-direction macro leg relative to the preceding macro leg when the two share the same boundary pivot.

Approved source: 118 such relationships among 127 adjacent transitions; 9 discontinuous transitions are excluded.

A/B/C are macro anchors only. No arbitrary triples and no Fibonacci labels.

## 7. Causal separation

Fixed/rolling closed-data features are causal from documented availability.

Macro legs/anchors/aggTrade touches/boundary fragments/retracements/context are retrospective with `available_at=null` and excluded from causal extraction.

## 8. Pipeline stage graph

0. external/preparatory: reviewed localization (already complete, including three known off-grid source windows) and reviewed aggTrade-refinement artifact (must be complete before real macro production)
1. `S00_contract_and_config`
2. `S01_source_inventory`
3. `S02_canonical_1m`
4. `S03_source_segments_and_gaps`
5. `S04_fixed_candles`
6. `S05_candle_geometry`
7. `S06_cross_timeframe_map`
8. `S07_macro_sources_and_refinement_artifacts`
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

### S07 details

Validate:
- macro checksum and 128 legs
- localization checksum and 138 pivots/status counts
- 145 candidate windows, including exactly three known off-grid source windows
- aggTrade-refinement artifact checksum/statuses
- approved source type is `aggTrades` for spot/futures as applicable
- raw individual trade artifacts, if present on disk, are excluded from calculation/QA truth unless separately user-approved
- canonical 5m containment for every exact aggTrade-resolved pivot
- anchor-level provenance
- exact-price Decimal/fixed-point QA
- all exact matching aggTrade rows/`agg_trade_id` ordering
- exact/fallback boundary status
- canonical market vs historical provenance.

No real macro exact metric may run before S07 validates.

### S09

Fixed/rolling speed under canonical names.

Macro:
- preserve source-coordinate source speed separately;
- calculate one endpoint-to-endpoint whole-leg macro speed only if both pivots are uniquely aggTrade-resolved.

### S11

Fixed/rolling use approved Q sequences.

Exact macro uses exact-pivot-to-exact-pivot Q sequence per calculation resolution.

Ambiguous macro fallback starts with first eligible constituent open and uses grid-based expected membership.

AggTrade-level fragment path is stored separately and never mixed with close path.

### S12/S13

Exact macro overlap/volume/activity may use typed boundary-fragment relationships plus interior intervals without double counting.

Fallback uses only guaranteed interior set.

Macro RV deferred.

### S15

Materialize the 118 approved adjacent shared-pivot opposite-direction macro retracements. Referential QA must prove A/B/C anchor foreign keys and the 9 excluded discontinuities.

## 9. Storage/resume

Canonical analytical storage is Parquet/Zstandard with schema partition plan. Targeted CSV only for review/exchange.

Persist validated work so <=20 minutes completed work is at risk. Resume validates source/config/schema/refinement checksums and skips only proven completed units.

## 10. Execution gate

Implementation/golden tests and bounded smoke may proceed.

Full-history real macro production additionally requires the reviewed aggTrade-refinement artifact and explicit user authorization after smoke review.
