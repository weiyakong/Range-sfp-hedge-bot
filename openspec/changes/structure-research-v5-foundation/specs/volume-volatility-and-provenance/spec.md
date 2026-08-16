# Volume, Volatility, and Provenance Contract

## Purpose

Preserve source-accurate volume, volatility and provenance across fixed/rolling observations and exact/fallback macro boundaries.

## Canonical volume

Complete derived candle volume is the sum of complete same-segment 1m constituents. Additional native additive fields are retained/summed only when their source semantics support it.

Incomplete/boundary target intervals have null complete volume; observed-only diagnostics must be explicitly named.

## Directional volume

Preserve two independent mechanical conventions:

- body direction: close vs open;
- close-step direction: close vs valid adjacent previous close.

Use explicit names `volume_body_*` and `volume_close_step_*`; no ambiguous generic up/down volume.

## Rolling comparisons

For current and preceding equal non-overlapping rolling windows:
- `volume_sum_change_vs_prev`
- `volume_sum_ratio_vs_prev` when previous > 0.

## TR/ATR

For a complete candle with a valid immediately adjacent previous complete candle at the same resolution and in the same source segment:

`TR = max(high-low, abs(high-previous_close), abs(low-previous_close))`.

If no such previous candle exists because of start-of-segment, real gap, source boundary, incomplete predecessor or other continuity break, `TR=null`.

Materialize both ATR14 forms:

- `atr14_sma`: simple mean of the latest 14 consecutive valid TR values;
- `atr14_wilder`: initialize as the simple mean of the first 14 consecutive valid TR values after a reset, then update for each next adjacent valid TR as `((previous_atr14_wilder*13)+TR)/14`.

A continuity break resets both ATR states. The first following candle has `TR=null` when no valid adjacent previous close exists. Neither ATR becomes valid again until 14 new consecutive valid TR values have accumulated.

This same rule applies inside fallback calculations: a pre-fallback candle cannot supply `previous_close` to the first fallback candle. Therefore the first eligible fallback candle has no fallback TR; fallback TR/ATR may use only adjacency wholly contained inside the guaranteed fallback interval.

## RV

Fixed/rolling RV uses the same Q sequence as their close path.

Macro RV remains deferred and SHALL NOT be created by silently combining trade-fragment returns with candle returns.

## Exact macro volume/activity

When both macro boundary times are resolved, resolution-dependent macro volume/activity uses the non-overlapping union:

start RIGHT boundary fragment
+ complete interior canonical intervals
+ end LEFT boundary fragment.

The pivot source record's volume/count is counted once in LEFT; RIGHT does not count it again.

A full canonical boundary candle SHALL NOT be included together with a fragment from that same interval.

Higher-resolution fragments may be composed from the trade-resolved 5m piece plus complete canonical 5m intervals.

## Unresolved-time macro fallback

If an anchor lacks one authoritative boundary time, macro volume/TR/activity uses only fixed-grid constituents wholly inside the guaranteed fallback interval.

The same grid-based expected/observed membership and coverage used by macro path SHALL be used here.

No boundary-overlapping candle/pair contributes to fallback macro summaries. If no guaranteed interior slot exists, counts are zero and boundary-dependent fallback metrics are null with explicit status.

## Trade/aggTrade provenance

Raw trades and aggTrades are different source granularities. Preserve exact source kind, native sequence ids, underlying trade-id ranges where available, artifact checksum and coverage.

For Binance aggTrades, source field `m` is stored under an unambiguous name such as `buyer_is_maker`; it SHALL NOT be represented by a vague generic `maker_side` field.

Do not call an aggTrade row an individual trade. Underlying trade count may be calculated only when source-native ids prove it.

## Source timestamp validation

Inventory records source-native timestamp alignment anomalies separately from real missing coverage.

A continuous 60-second off-grid source series (required regression: `+20.799s` December-2017 spot rows) SHALL NOT be counted as a day of missing candles solely because timestamps are not aligned to `:00`.

Canonicalization requires a proven source-specific mapping; original timestamps/provenance remain stored.

## Feature dictionary

Every materialized volume/volatility/activity metric must have one canonical definition with units, source/resolution, availability, null meaning and provenance.
