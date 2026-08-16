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
- exact pivot time + `agg_trade_id` only when one exact anchor-price aggTrade row exists
- canonical 5m containment determined from that resolved aggTrade event time
- LEFT/RIGHT boundary fragments as retrospective macro-analysis entities
- conservative fallback only when aggTrade evidence remains ambiguous.

## Approved refinement source

The approved source for the pre-v5 macro-boundary refinement stage is the already downloaded official Binance BTCUSDT `aggTrades` dataset for the corresponding market:

- spot anchors -> spot `aggTrades`;
- futures anchors -> USDT-M futures `aggTrades`.

Raw individual trade data are NOT the preferred source and are NOT part of the approved calculation path.

Raw trade files already downloaded during an earlier unapproved attempt may remain on disk, but they SHALL NOT be used for pivot selection, boundary construction, feature calculation, QA truth or refinement outputs unless the user later explicitly approves that source change.

If `aggTrades` are insufficient for a particular pivot or metric, preserve/report the limitation and ask for a separate source decision rather than silently switching to raw trades.

## Approved macro localization facts

Macro checksum:
`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`

Localization checksum:
`77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`

138 pivots:
- 131 unique localization windows
- 7 multiple-window pivots
- 0 incomplete/unresolved.

145 candidate windows exist in total. 142 are canonical-grid 5m windows. Three spot windows (`E00059`,`E00065`,`E00070`) inherited the proven `+20.799s` source offset and are not canonical 5m candles. They remain valid source-localization search windows, but the aggTrade stage must determine the resolved pivot coordinate and therefore its true canonical 5m containment.

Localization is not treated as exact pivot timing.

## Exact macro measurement principle

When both endpoints are uniquely resolved at approved aggTrade-source granularity:
- whole-leg duration/speed use the resolved aggTrade event times/prices;
- one whole-leg speed exists;
- macro path at each TF uses exact start price, chronological canonical closes at that TF, and exact end price;
- aggTrade-level LEFT/RIGHT path remains separate microstructure;
- macro volume/activity uses non-overlapping boundary fragments + complete interior intervals.

Canonical fixed candles are never split/replaced.

An aggTrade is an indivisible approved source record. If a pivot aggTrade contains multiple underlying raw trades, the pipeline must not invent their internal timestamps/order/volume split. That boundary carries an explicit aggregate-source precision flag.

If aggTrade touches remain ambiguous, exact endpoint-dependent metrics stay null and only the guaranteed fallback interior is aggregated.

## Source timestamp integrity

Non-minute source timestamps do not automatically mean missing data.

The proven December-2017 `+20.799s` local spot kline series is a required regression case: a continuous 60-second source series must be classified as off-grid source data, not 1440 missing minutes. Canonicalization may occur only under a proven source-specific mapping with raw provenance retained.

## Price identity

Relevant audited BTCUSDT spot/futures/macro prices have maximum two significant decimal places.

Use Decimal/string parsing and exact integer `price_units=price*100`; binary float identity/nearest-price matching is prohibited. New approved aggTrade evidence with >2 significant decimals fails QA rather than being rounded silently.

## Retracement

First-pass retracement is specifically the following opposite-direction macro leg relative to the immediately preceding macro leg when they share one pivot.

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

Later, after macro analysis identifies meaningful internal-leg/correction boundaries, the same approved boundary method may be applied selectively to those boundaries.

## Availability

Macro source/refinement/fragments/retracements remain retrospective (`available_at=null`) even when historical pivot time is resolved.

## Execution gate

Implementation is ready only when all specs/schema/design/tasks/QA are synchronized.

Real full-history macro production additionally requires a reviewed frozen aggTrade-refinement artifact and explicit user authorization after bounded smoke.
