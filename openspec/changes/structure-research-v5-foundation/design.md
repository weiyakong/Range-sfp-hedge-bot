# Design: Structure Research v5 Foundation

## 1. Design intent

Structure Research v5 is a staged descriptive research-data pipeline, not a trading-decision engine.

Priorities: source fidelity, deterministic time construction, explicit causality, stable identities, exact price identity, bounded memory, resumability, independent QA, exact trade-resolved macro boundaries where evidence permits, and conservative fallback where they do not.

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

Approved 5m localization:
`macro_pivots_5m_all.csv`
SHA-256 `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`.

It contains 138 unique pivots: 131 unique 5m candidates and 7 multiple-5m pivots, no unresolved coverage.

Before real macro production, a separate trade-refinement stage examines the 145 candidate 5m intervals with same-market official Binance trades/aggTrades and freezes a reviewed refinement artifact/checksum.

The main v5 pipeline consumes that artifact. It does not independently choose trade touches.

## 4. Macro boundary model

Every anchor preserves:
- original source coordinate/precision/provenance;
- 5m localization candidates;
- every exact trade touch considered;
- exact pivot time + native sequence id only when one unique touch exists;
- fallback uncertainty otherwise.

5m localization is not exact timing.

For a unique exact pivot, create LEFT/RIGHT boundary fragments without altering canonical candles. Pivot record count/volume belongs to LEFT once; RIGHT starts from pivot price state and excludes that record.

At higher TFs, partial boundaries are composed from the trade-resolved partial 5m piece plus complete canonical 5m intervals.

## 5. Macro measurements

Exact whole-leg duration/speed use exact endpoint pivots. Original source duration/speed remain separate provenance.

Exact macro close-path at resolution R uses:
`exact start price -> chronological complete R closes ending after start and no later than end -> exact end price if needed`.

Trade fragment path remains a separate microstructure family and is never added to TF close path.

Exact macro volume/activity uses:
start RIGHT fragment + complete interior intervals + end LEFT fragment, with no full boundary candle double-counting.

If a pivot remains ambiguous after trade refinement, exact boundary metrics remain null and fallback uses only fixed-grid intervals guaranteed to lie between all possible boundary touches. Expected fallback count is grid-slot count, not duration/resolution.

Macro RV remains deferred.

## 6. Retracement

First-pass production retracement is the immediately following opposite-direction macro leg relative to the preceding macro leg when the two share the same boundary pivot.

Approved source: 118 such relationships among 127 adjacent transitions; 9 discontinuous transitions are excluded.

A/B/C are macro anchors only. No arbitrary triples and no Fibonacci labels.

## 7. Causal separation

Fixed/rolling closed-data features are causal from documented availability.

Macro legs/anchors/trade touches/boundary fragments/retracements/context are retrospective with `available_at=null` and excluded from causal extraction.

## 8. Pipeline stage graph

0. external/preparatory: reviewed 5m localization (already complete) and reviewed trade-refinement artifact (must be complete before real macro production)
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
- trade-refinement artifact checksum/statuses
- anchor-level provenance
- exact-price Decimal/fixed-point QA
- all exact touches/native sequence ids
- exact/fallback boundary status
- canonical market vs historical provenance.

No real macro exact metric may run before S07 validates.

### S09

Fixed/rolling speed under canonical names.

Macro:
- preserve source-coordinate source speed separately;
- calculate exact one whole-leg macro speed only if both trade pivots exact.

### S11

Fixed/rolling use approved Q sequences.

Exact macro uses exact-pivot-to-exact-pivot Q sequence per calculation resolution.

Ambiguous macro fallback starts with first eligible constituent open and uses grid-based expected membership.

Trade-level fragment path is stored separately and never mixed with close path.

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

Full-history real macro production additionally requires the reviewed trade-refinement artifact and explicit user authorization after smoke review.
