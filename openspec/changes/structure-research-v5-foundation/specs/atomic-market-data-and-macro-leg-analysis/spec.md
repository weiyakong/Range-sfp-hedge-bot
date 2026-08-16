# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure one approved Structure Research v5 run preserves enough atomic market data and refined/fallback macro-leg measurements to analyze movement behavior later without inventing missing semantics.

## Canonical market coverage

The production dataset targets the full approved BTC history. Canonical 1m chronology:
- Binance BTCUSDT spot before `2019-09-08T17:57:00Z`;
- Binance BTCUSDT USDT-M futures from `2019-09-08T17:57:00Z`;
- native futures 19:00 remains a real canonical gap;
- post-boundary spot is provenance only;
- synthetic diagnostic rows never satisfy canonical completeness.

A `source_segment_id` identifies continuous same-market canonical 1m data. Archive/provenance changes alone do not split continuity. Canonical `5m/15m/1H/4H/1D` derive strictly from canonical 1m.

## Timestamp-source validation

Canonical 1m starts are on the UTC minute grid, but source validation distinguishes true absence from continuous off-grid source timestamps. The proven December-2017 `+20.799s` series SHALL NOT be counted as 1440 missing minutes. Off-grid rows are not silently rounded; source-specific mapping must be proven and preserved as provenance.

## Approved macro source and localization

Approved macro source: `macro_legs_log20.csv`, SHA-256 `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`, 128 legs.

Reviewed localization: `macro_pivots_5m_all.csv`, SHA-256 `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`, 138 pivots: 131 unique-window, 7 multiple-window, 0 unresolved. There are 145 candidate windows, 142 canonical-grid and three off-grid source-localization windows E00059/E00065/E00070 with +20.799s starts.

Every candidate window is scanned as half-open `[candidate_start,candidate_start+5m)`.

## Trade refinement precedes exact macro production

Localization is not exact event timing. Refinement uses only approved same-market official Binance `aggTrades` according to `macro-trade-boundary-refinement`.

For each anchor:
- preserve all exact source-anchor-price aggTrade touches;
- if one or more exact touches exist with complete approved coverage, select the earliest by `(event_time,agg_trade_id)`;
- if no exact touch exists, a high pivot selects the maximum realized aggTrade price and a low pivot selects the minimum realized aggTrade price across all approved candidate windows;
- preserve every aggTrade row attaining the selected directional extremum;
- if the selected extremum occurs once, its event time/id resolve the pivot;
- if the selected extremum repeats, refined realized price is known but authoritative time/id remain unresolved until a separate tie-break rule is explicitly approved.

Multiple exact touches are therefore not ambiguous: earliest exact touch wins while all touches remain evidence.

## Price identity

Parse prices from exact decimal strings/`Decimal`. Relevant approved prices must be exactly representable with no more than two fractional decimal places after exact decimal normalization.

Use `price_units = exact_decimal_price * 100` as integer identity. If new approved aggTrade evidence requires greater scale, fail precision QA rather than rounding.

## Refined macro boundaries and fragments

When one authoritative pivot aggTrade key exists:
- resolved time/id/price become the refined macro boundary coordinate;
- original source anchor time/price remain separately preserved;
- canonical 5m containment derives from the resolved event time;
- canonical candles remain unchanged;
- LEFT/RIGHT boundary fragments are created;
- pivot aggTrade belongs LEFT once;
- RIGHT starts from resolved pivot price state but excludes pivot aggTrade from its source-row volume/count.

For higher resolutions, fragments compose from the trade-resolved partial canonical 5m piece plus complete canonical 5m candles to the enclosing boundary. A macro metric never includes both a full boundary candle and its partial fragment.

## Bounded aggTrade access

Anchor and fragment processing SHALL NOT repeatedly load whole daily/monthly aggTrade archives.

- candidate refinement reads only rows needed for the candidate window(s);
- canonical 5m fragment construction reads only the complete required `[B0,B1)` bucket;
- higher-TF composition uses that 5m fragment plus canonical 5m data, not larger aggTrade rescans;
- identical source buckets/windows encountered repeatedly within a pass should be cached/reused where practical;
- per-anchor/per-fragment helpers must be streaming/range-filtered/partition-pruned and bounded in memory.

For ZIP/CSV aggTrade archives, fragment-stage access SHALL use a robust streaming parser/filter that can select the required 5m bucket without materializing the whole archive. A pandas full-file parser/read is prohibited inside the per-anchor/per-fragment hot loop. Parser failure must be surfaced explicitly; it may not trigger raw-trade fallback.

## Macro duration, speed and path

When both endpoint times are deterministically resolved, whole-leg duration is exact time difference and whole-leg speed is calculated once from refined endpoint prices/times. Original source duration/speed remains separate retrospective provenance.

At resolution `R`, refined macro path sequence is:
- `Q0 = refined start pivot price`;
- chronological closes of complete canonical `R` candles with `start_pivot_time < candle.end_time <= end_pivot_time`;
- append refined end pivot price if needed.

Trade-fragment path remains separate `trade_*` microstructure and is never added to TF close path.

## Unresolved-time fallback

If authoritative pivot time remains unresolved/unavailable, exact duration/speed/boundary-dependent metrics remain null. Fallback uses only canonical fixed-grid intervals guaranteed to lie between all possible boundary occurrences.

For fallback constituents `B1...Bn`, `Q0=open(B1)` followed by each `close(Bi)`. Expected count is the number of wholly contained fixed-grid slots, not `duration/R`. If no guaranteed slot exists, expected/observed counts are zero and boundary-dependent fallback metrics are null with explicit `no_unambiguous_interior` status.

## Macro overlap/volume/activity

For resolved boundaries use non-overlapping union: start RIGHT fragment + complete interior canonical intervals + end LEFT fragment. For unresolved boundaries use only guaranteed fallback set. Macro RV remains deferred.

## Historical provenance, availability and retracement

Historical old-source provenance and current canonical market remain separate. Macro entities are retrospective with `available_at=null` and excluded from causal extraction.

First-pass retracement applies to consecutive opposite-direction macro legs sharing a pivot. Approved source contains 118 such relationships among 127 adjacent transitions; 9 discontinuous transitions excluded. No Fibonacci labeling.
