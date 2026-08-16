# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure one approved Structure Research v5 run preserves enough atomic market data and exact/fallback macro-leg measurements to analyze movement behavior later without inventing missing semantics.

## Canonical market coverage

The production dataset targets the full approved BTC history. The canonical 1m chronology is:

- Binance BTCUSDT spot before `2019-09-08T17:57:00Z`;
- Binance BTCUSDT USDT-M futures from `2019-09-08T17:57:00Z`;
- the native futures 19:00 gap remains a real canonical gap;
- post-boundary spot is provenance only;
- synthetic diagnostic rows never satisfy canonical completeness.

A `source_segment_id` identifies continuous same-market canonical 1m data. Archive/provenance changes alone do not split continuity.

Canonical `5m/15m/1H/4H/1D` are derived from strict canonical 1m. Native higher-TF data are QA/reference unless explicitly approved otherwise.

## Timestamp-source validation

Canonical 1m starts are exactly on the UTC minute grid, but source validation SHALL distinguish:

1. true absence of source bars;
2. a continuous 60-second source series whose stored timestamps are consistently off-grid.

The December-2017 spot source proved that a full 1m series can be stored with `open_time` offset `+20.799s`; such a series SHALL NOT be counted as 1440 missing minutes merely because timestamps are not `:00`.

Off-grid rows SHALL NOT be silently rounded. The source-specific canonicalization rule must first be proven from continuity/provenance and recorded. True gaps remain gaps.

## Approved macro source and 5m localization

Macro legs use the approved `macro_legs_log20.csv`, SHA-256:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`

with 128 legs.

The reviewed 5m localization artifact is `macro_pivots_5m_all.csv`, SHA-256:

`77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`

with 138 unique macro pivots:

- 131 unique 5m candidates;
- 7 pivots with two 5m candidates;
- no incomplete/unresolved pivots.

This localization artifact supplies anchor-level source precision/market/refinement fields. Per-leg `duration_precision` is preserved as source leg provenance and SHALL NOT be copied blindly onto each anchor.

## Trade refinement precedes exact macro production

The 5m localization is not exact event timing. Before exact macro-leg duration/path/speed/membership are materialized, the approved candidate 5m intervals SHALL be refined with same-market official Binance trade evidence according to `macro-trade-boundary-refinement`.

A unique exact touch must be identified by exact price plus deterministic native sequence identity. Timestamp alone is insufficient when multiple source records share one event time.

If multiple exact touches remain, no first/last/nearest touch is selected automatically.

## Price identity

Parse prices from exact decimal strings/`Decimal`. Relevant audited spot/futures/macro prices have at most two significant decimal places.

Use integer:

`price_units = exact_decimal_price * 100`.

If new official trade evidence cannot be represented exactly at two decimals, fail precision QA instead of rounding silently.

## Exact macro boundaries and fragments

When a pivot has one exact trade touch:

- exact pivot time and native sequence id become the macro boundary;
- canonical fixed candles remain unchanged;
- a LEFT and RIGHT boundary fragment are created for macro analysis;
- the pivot source record's volume/count belongs to LEFT exactly once;
- RIGHT starts from the pivot price state but excludes the pivot source record from its own trade volume/count.

For higher resolutions, boundary fragments are composed from the trade-resolved partial 5m piece plus complete canonical 5m candles up to the enclosing resolution boundary. No extra trade download for an entire 15m/1H/4H/1D interval is required.

A macro metric never includes both a full boundary candle and its partial boundary fragment.

## Macro whole-leg duration and speed

When both endpoint pivots are exact, whole-leg duration is the exact time difference and whole-leg speed is calculated once from the exact endpoint prices/times.

Original source duration/speed from `macro_legs_log20` remains separately preserved as retrospective source-coordinate provenance.

Timeframe-specific features describe how the leg evolved internally; they do not create different definitions of whole-leg speed.

## Macro path

Trade-level fragment path and timeframe close-path are different measurements and SHALL NOT be added together.

For exact macro path at calculation resolution `R`:

- `Q0` = exact start pivot price;
- then chronological closes of complete canonical `R` candles with `start_pivot_time < candle.end_time <= end_pivot_time`;
- append exact end pivot price if needed.

This same sequence defines close path, log path, displacement, efficiency, directional path and alternation at `R`.

Trade-level LEFT/RIGHT path remains separately named `trade_*` microstructure data.

## Ambiguity fallback

Exact trade refinement is the primary path.

If a pivot remains ambiguous/unavailable after trade refinement, exact duration/speed/boundary-inclusive metrics remain null. Fallback macro metrics may use only canonical calculation intervals guaranteed to lie between all possible boundary touches.

For fallback constituents `B1...Bn`, the sequence begins at `Q0=open(B1)` followed by each `close(Bi)`, so the first eligible candle's open-to-close movement is retained.

At resolution `R`, expected fallback count is the number of fixed-grid `R` slots wholly contained in the unambiguous interval, not `duration/R`.

Persist measured start/end of the actual eligible constituent sequence.

## Macro overlap/volume/activity

For exact boundaries, resolution-dependent macro summaries use the non-overlapping union:

start RIGHT boundary fragment
+ complete interior canonical intervals
+ end LEFT boundary fragment.

For ambiguous boundaries, only the fallback unambiguous set contributes.

Macro RV remains deferred in this pass.

## Historical provenance vs canonical market

Historical old-source provenance and current canonical market scope are separate facts. Late-2019 macro provenance may be mixed while canonical market type is futures.

## Retrospective availability

Macro legs/anchors/trade refinement/fragments/retracements are retrospective research entities with `availability_class=retrospective`, `available_at=null`. Causal extraction excludes them.

## Retracement

First-pass macro retracement is defined for consecutive opposite-direction macro legs sharing a pivot:

`A -> B` followed immediately by `B -> C`.

Retracement of `B->C` is measured relative to the preceding `A->B`.

In the approved 128-leg file, 118 of 127 adjacent transitions share one boundary pivot and are opposite-direction; these 118 are the production retracement relationships. The 9 discontinuous transitions are excluded.

No Fibonacci labeling is produced.
