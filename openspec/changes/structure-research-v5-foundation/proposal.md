# Proposal: Structure Research v5 Foundation

## Summary
Build a reproducible first-pass BTC research dataset preserving objective multi-timeframe movement measurements without prematurely classifying impulse/correction/range/chop/parent/Elliott/Fibonacci structure.

## Core architecture
Canonical layer: strict observed 1m spot/futures chronology, deterministic 5m/15m/1H/4H/1D, explicit gaps/source transitions, geometry and objective fixed/rolling measurements.

Macro layer:
- approved 128 `macro_legs_log20` legs;
- reviewed 138-pivot/145-candidate localization artifact;
- same-market official Binance aggTrades refinement before exact macro production;
- exact source-anchor price -> earliest exact aggTrade touch;
- no exact source-anchor price -> highest realized price for high pivot / lowest realized price for low pivot;
- source anchor coordinate preserved separately;
- LEFT/RIGHT retrospective boundary fragments;
- conservative fallback when authoritative time remains unresolved.

Repeated equal selected directional extrema remain an explicitly deferred tie-break decision. Until that rule is approved, realized price is preserved but authoritative time/id and endpoint-dependent exact metrics remain unresolved. No implementation may infer a time threshold, retest/range classification, or first/last selection.

## Approved refinement source and access
Only already downloaded official Binance BTCUSDT aggTrades for the corresponding market are approved. Raw individual trades are outside the calculation path unless separately approved.

Every localization candidate is half-open `[candidate_start,candidate_start+5m)`.

Source access is bounded and archive-aware. Per-anchor/per-fragment code may not repeatedly parse whole day/month archives. Multiple requested windows/buckets in one physical archive must be served by one shared streaming scan, validated indexed/range access, or validated bounded cache. One whole-archive scan per different 5m bucket is prohibited.

Fragment source is exactly its canonical `[B0,B1)` 5m bucket. Higher-TF fragments reuse the 5m fragment plus canonical 5m candles. ZIP/CSV hot paths use robust streaming/bounded parsing; pandas whole-file DataFrame parsing is prohibited. Parser failure is `source_reader_failure`, not missing coverage and not permission for raw fallback.

## Approved localization facts
Macro SHA-256 `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.
Localization SHA-256 `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`.
138 pivots: 131 unique-window, 7 multiple-window, 0 localization unresolved. 145 candidate windows: 142 canonical-grid starts; E00059/E00065/E00070 are known +20.799s off-grid source-localization windows.

## Exact macro measurement
When both endpoint times resolve at approved aggTrade granularity:
- duration/speed use refined realized endpoints;
- one whole-leg speed exists;
- TF path uses refined start price, qualifying canonical closes and refined end price;
- aggTrade fragment path remains separate microstructure;
- volume/activity uses non-overlapping boundary fragments plus complete interiors.

Canonical fixed candles are never split/replaced. AggTrade rows are indivisible approved source records.

If authoritative boundary time is unresolved, exact endpoint-dependent metrics stay null and fallback uses only guaranteed fixed-grid interior. No guaranteed slot -> boundary-dependent fallback null.

## Price and volatility
Prices use Decimal/string identity and exact integer `price_units=price*100`; approved evidence requiring greater than two fractional decimal places fails QA rather than rounding.

Materialize both `atr14_sma` and `atr14_wilder`. Continuity breaks reset TR/ATR; first following TR is null and 14 new consecutive valid TRs are required.

## Retracement
First-pass retracement is the immediately following opposite-direction macro leg when adjacent legs share one pivot. Approved count: 118 relationships; 9 discontinuous adjacent transitions excluded. No arbitrary tuples/Fibonacci labels.

## Storage/resume
Canonical analytical storage is Parquet/Zstandard. Targeted CSV is for review/exchange. Persist validated collected/derived progress no later than every 20 minutes. Restart-safe bounded source caches may be used only with source checksum + exact interval identity and validation.

## Scope
In scope: canonical history/features, macro source/localization/refinement, bounded aggTrade source access, fragments, exact/fallback macro metrics, 118 retracements, Parquet/manifests/extraction/checkpoint/resume, independent QA and bounded smoke.

Deferred: repeated-directional-extremum time tie-break; raw individual trade refinement unless separately approved; new swing hierarchy; impulse/correction/range/breakout/chop/parent/Fib/FibTime/Elliott labels; macro RV; broad full-history tick path reconstruction.

## Availability and gate
Macro entities remain retrospective (`available_at=null`). Implementation/smoke requires synchronized formula/source/bounded-I/O QA. Real full-history macro production additionally requires a reviewed frozen aggTrade-refinement artifact and explicit user authorization after bounded smoke.
