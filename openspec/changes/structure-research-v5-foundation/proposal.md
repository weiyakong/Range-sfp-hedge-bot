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
- same-market official trade refinement of all localization candidate windows before exact macro production
- exact pivot time + native sequence id only when one exact anchor-price touch exists
- canonical 5m containment determined from the exact trade pivot
- LEFT/RIGHT boundary fragments as retrospective macro-analysis entities
- conservative fallback only when trade evidence remains ambiguous.

## Approved macro localization facts

Macro checksum:
`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`

Localization checksum:
`77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`

138 pivots:
- 131 unique localization windows
- 7 multiple-window pivots
- 0 incomplete/unresolved.

145 candidate windows exist in total. 142 are canonical-grid 5m windows. Three spot windows (`E00059`,`E00065`,`E00070`) inherited the proven `+20.799s` source offset and are not canonical 5m candles. They remain valid source-localization search windows, but the trade stage must determine the exact pivot and therefore its true canonical 5m containment.

Localization is not treated as exact pivot timing.

## Exact macro measurement principle

When both endpoints are uniquely trade-resolved:
- exact whole-leg duration/speed use exact pivot times/prices;
- one whole-leg speed exists;
- macro path at each TF uses exact start price, chronological canonical closes at that TF, and exact end price;
- trade-level LEFT/RIGHT path remains separate microstructure;
- macro volume/activity uses non-overlapping boundary fragments + complete interior intervals.

Canonical fixed candles are never split/replaced.

If trade touches remain ambiguous, exact endpoint-dependent metrics stay null and only the guaranteed fallback interior is aggregated.

## Source timestamp integrity

Non-minute source timestamps do not automatically mean missing data.

The proven December-2017 `+20.799s` local spot kline series is a required regression case: a continuous 60-second source series must be classified as off-grid source data, not 1440 missing minutes. Canonicalization may occur only under a proven source-specific mapping with raw provenance retained.

## Price identity

Relevant audited BTCUSDT spot/futures/macro prices have maximum two significant decimal places.

Use Decimal/string parsing and exact integer `price_units=price*100`; binary float identity/nearest-price matching is prohibited. New trade evidence with >2 significant decimals fails QA rather than being rounded silently.

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
- trade-refinement ingestion
- macro boundary fragments
- exact/fallback macro metrics
- 118 macro retracements
- Parquet/manifests/extraction/checkpoint/resume
- independent QA and bounded smoke.

Deferred:
- new internal swing/leg hierarchy
- impulse/correction thresholds/labels
- parent impulse
- range/breakout/chop labels
- Fib/FibTime
- Elliott
- macro RV
- broad full-history tick path reconstruction.

Later, after macro analysis identifies meaningful internal-leg/correction boundaries, the same trade-boundary method may be applied selectively to those boundaries.

## Availability

Macro source/refinement/fragments/retracements remain retrospective (`available_at=null`) even when historical pivot time is exact.

## Execution gate

Implementation is ready only when all specs/schema/design/tasks/QA are synchronized.

Real full-history macro production additionally requires a reviewed frozen trade-refinement artifact and explicit user authorization after bounded smoke.
