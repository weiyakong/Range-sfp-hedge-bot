# Design: Structure Research v5 Foundation

## 1. Design intent
Structure Research v5 is a staged descriptive research-data pipeline, not a trading-decision engine. Priorities are source fidelity, deterministic construction, stable identity, exact price handling, bounded/resumable processing and independent QA.

## 2. Canonical market source
Strict canonical 1m uses spot before `2019-09-08T17:57:00Z` and USDT-M futures from that boundary. Documented gaps remain real, including futures 19:00. Post-boundary spot and the synthetic 19:00 diagnostic are excluded. Canonical 5m/15m/1H/4H/1D derive from strict canonical 1m. Proven continuous off-grid source series require source-specific mapping and retained raw timestamp provenance.

## 3. Macro prerequisites
Approved macro source is `macro_legs_log20.csv`, SHA-256 `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

Reviewed localization is `macro_pivots_5m_all.csv`, SHA-256 `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`: 138 pivots, 131 unique-window and 7 multiple-window, 145 candidate windows total. Three known spot windows E00059/E00065/E00070 are off-grid source-localization windows with +20.799s offset.

Every candidate is scanned as half-open `[candidate_start,candidate_start+5m)` using already downloaded same-market official Binance BTCUSDT aggTrades. Raw individual trades are outside the approved path unless separately explicitly approved.

## 4. Macro boundary model
Every anchor preserves its original source coordinate separately from refined realized coordinate.

Refinement is deterministic:
- preserve all exact source-anchor-price aggTrade touches;
- if one or more exact touches exist with complete approved coverage, select the earliest by `(event_time,agg_trade_id)`;
- if no exact touch exists, a high pivot selects the maximum realized aggTrade price and a low pivot selects the minimum realized aggTrade price across all approved candidate windows;
- preserve every row attaining that selected extremum;
- if the selected extremum occurs once, its time/id resolves the pivot;
- if the selected extremum repeats, realized pivot price is known but authoritative time/id remain unresolved pending the separately deferred tie-break decision. No implementation may invent that rule.

A resolved timestamp is exact only at aggTrade source granularity. For one authoritative pivot aggTrade key, create LEFT/RIGHT boundary fragments without changing canonical candles. Pivot aggregate belongs LEFT once; RIGHT begins from pivot price state and excludes that aggregate row. Multi-underlying aggregate is indivisible.

## 5. Bounded aggTrade access
Candidate and fragment calculations are small logical requests and SHALL NOT cause repeated whole-day/month source parsing.

The source-access layer groups requests by physical archive. For multiple windows/buckets from one archive it uses one shared streaming pass, validated indexed/range access, or a validated restart-safe bounded cache. It is forbidden to sequentially rescan the same whole archive once per different 5m bucket.

Fragment construction requests exactly the canonical 5m bucket containing the resolved pivot. Higher-TF fragments reuse that 5m fragment plus complete canonical 5m candles; they do not rescan aggTrades.

ZIP/CSV hot-path parsing is streaming/bounded. `pandas.read_csv`/whole-file DataFrame materialization is prohibited for per-anchor/per-fragment access. Parser/read failure is explicit `source_reader_failure`; it is not missing coverage and never enables raw-trade fallback.

Instrumentation records logical requests separately from archive opens/scans, scanned/returned rows, cache/index hits and bounded-memory evidence. B01-B07 in the bounded-source-access contract are critical gates.

## 6. Macro measurements
Exact whole-leg duration/speed use refined realized endpoints only when both endpoint times are resolved. Original source duration/speed remain separate provenance.

Exact macro close-path at resolution R is `refined start price -> chronological complete R closes with start < candle.end <= end -> refined end price if needed`. Aggregate-trade fragment path is separate and never added to TF close path.

Exact macro volume/activity uses start RIGHT fragment + complete interior intervals + end LEFT fragment, without full boundary candle duplication.

If boundary time remains unresolved, exact boundary metrics are null and fallback uses only fixed-grid intervals guaranteed inside all possible boundary occurrences. If no guaranteed interior slot exists, counts are zero and boundary-dependent metrics are null with explicit status.

Macro RV remains deferred.

## 7. Retracement
First-pass production retracement is the immediately following opposite-direction macro leg when adjacent legs share the same pivot. Approved source count is 118 relationships among 127 adjacent transitions; 9 discontinuous transitions are excluded. A/B/C are macro anchors. No Fibonacci labels.

## 8. Causal separation
Fixed/rolling closed-data features are causal. Macro legs/anchors/aggTrade evidence/fragments/retracements/context are retrospective with `available_at=null` and excluded from causal extraction.

## 9. Pipeline stages
S00 contract/config; S01 inventory; S02 canonical1m; S03 gaps/segments; S04 fixed candles; S05 geometry; S06 cross-TF; S07 macro sources/refinement; S08 observations; S09 speed; S10 pairs; S11 path/activity; S12 overlap; S13 volume/volatility; S14 macro context; S15 retracement; S16 dictionary/manifests; S17 independent QA; S18 bounded extraction smoke.

S07 validates checksums/counts, all 145 windows, aggTrade-only source rule, bounded archive access, exact Decimal identity, earliest-exact-touch rule, no-exact directional-extremum rule, all supporting evidence, canonical containment when time resolves, and uncertainty when it does not.

S13 materializes both `atr14_sma` and `atr14_wilder`. TR requires valid adjacent previous close inside the same source segment/resolution. A continuity break resets state; first following TR is null and both ATRs require 14 new consecutive valid TRs.

## 10. Storage/resume
Canonical analytical storage is Parquet/Zstandard. Persist validated work no later than every 20 minutes so at most 20 minutes completed work is at risk. Resume validates source/config/schema/refinement checksums and skips only proven completed units. Restart-safe bounded window/bucket caches may be persisted when source checksum and exact interval are part of cache identity.

## 11. Execution gate
Implementation/golden tests and bounded smoke may proceed only after all applicable formula/source/bounded-I/O gates pass. Full-history real macro production additionally requires reviewed frozen aggTrade-refinement artifact and explicit user authorization after smoke review.
