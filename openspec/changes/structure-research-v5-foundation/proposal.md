# Proposal: Structure Research v5 Foundation

## Summary

Build a reproducible first-pass BTC research dataset that preserves objective multi-timeframe movement measurements without prematurely classifying impulse/correction/range/chop/parent/Elliott/Fibonacci structure.

## Core architecture

Canonical market layer:
- strict observed 1m spot/futures chronology
- deterministic 5m/15m/1H/4H/1D
- explicit gaps/source transitions
- candle geometry, rolling/fixed path/speed/overlap/volume/volatility.

Macro layer:
- approved 128 `macro_legs_log20` legs
- reviewed 138-pivot localization artifact
- same-market official Binance `aggTrades` refinement of all localization candidate windows before exact macro production
- exact source-anchor price: earliest exact aggTrade touch wins
- no exact source-anchor price: high pivot uses highest realized aggTrade price, low pivot uses lowest realized aggTrade price
- source anchor coordinate remains preserved separately from refined realized pivot coordinate
- canonical 5m containment determined from resolved aggTrade event time
- LEFT/RIGHT boundary fragments as retrospective macro-analysis entities
- conservative fallback only when one authoritative boundary time remains unresolved.

## Approved refinement source

The approved source is the already downloaded official Binance BTCUSDT `aggTrades` dataset for the corresponding market. Raw individual trade data are outside the approved calculation path unless later explicitly approved.

Every candidate localization window is scanned as half-open `[candidate_start,candidate_start+5m)`.

If `aggTrades` are insufficient for a particular pivot or metric, preserve/report the limitation rather than silently switching source.

## Approved macro localization facts

Macro checksum:
`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`

Localization checksum:
`77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`

138 pivots:
- 131 unique localization windows
- 7 multiple-window pivots
- 0 incomplete/unresolved.

145 candidate windows exist in total. 142 are canonical-grid 5m windows. Three spot windows (`E00059`,`E00065`,`E00070`) inherited the proven `+20.799s` source offset and remain source-localization windows only.

Localization is not treated as exact pivot timing.

## Exact macro measurement principle

When both endpoint times are deterministically resolved at approved aggTrade-source granularity:
- whole-leg duration/speed use refined realized event times/prices;
- one whole-leg speed exists;
- macro path at each TF uses refined start price, chronological canonical closes at that TF, and refined end price;
- aggTrade-level LEFT/RIGHT path remains separate microstructure;
- macro volume/activity uses non-overlapping boundary fragments + complete interior intervals.

Canonical fixed candles are never split/replaced.

An aggTrade is indivisible. If it contains multiple underlying raw trades, the pipeline does not invent internal timestamps/order/volume split.

If one authoritative boundary time remains unresolved, exact endpoint-dependent metrics stay null and only guaranteed fallback interior is aggregated. If no guaranteed interior slot exists, boundary-dependent fallback metrics are null.

## Source timestamp integrity

Non-minute source timestamps do not automatically mean missing data. Proven off-grid source series require source-specific mapping with raw provenance retained.

## Price identity

Relevant audited BTCUSDT spot/futures/macro prices have maximum two fractional decimal places after exact decimal normalization.

Use Decimal/string parsing and exact integer `price_units=price*100`; binary float identity/nearest-price matching is prohibited. New approved aggTrade evidence that cannot be represented exactly at scale 2 fails QA rather than being rounded silently.

## Volatility

Materialize both approved ATR14 forms:
- `atr14_sma`
- `atr14_wilder`.

Both initialize only after 14 consecutive valid TR values. A real gap/source boundary resets continuity; the first following TR is null when there is no valid adjacent previous close, and both ATR series reinitialize from a new run of 14 valid TR values.

## Retracement

First-pass retracement is the following opposite-direction macro leg relative to the immediately preceding macro leg when they share one pivot.

The approved 128-leg source yields 118 production retracement relationships; 9 adjacent transitions are discontinuous and excluded.

No arbitrary tuples/Fibonacci labels.

## Scope

In scope:
- full approved history
- canonical candles and objective fixed/rolling features
- macro source/provenance
- localization ingestion
- approved aggTrade-refinement ingestion
- macro boundary fragments
- exact/fallback macro metrics
- 118 macro retracements
- Parquet/manifests/extraction/checkpoint/resume
- independent QA and bounded smoke.

Deferred:
- raw individual trade refinement unless separately approved
- new internal swing/leg hierarchy
- impulse/correction thresholds/labels
- parent impulse
- range/breakout/chop labels
- Fib/FibTime
- Elliott
- macro RV
- broad full-history tick path reconstruction.

## Availability

Macro source/refinement/fragments/retracements remain retrospective (`available_at=null`) even when historical pivot time is resolved.

## Execution gate

Implementation is ready only when all specs/schema/design/tasks/QA are synchronized.

Real full-history macro production additionally requires a reviewed frozen aggTrade-refinement artifact and explicit user authorization after bounded smoke.
