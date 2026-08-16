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

TR requires valid same-resolution same-segment previous close.

ATR14 SMA/Wilder initialize from 14 consecutive valid TRs; gaps/boundaries reset state.

## RV

Fixed/rolling RV uses the same Q sequence as their close path.

Macro RV remains deferred and SHALL NOT be created by silently combining trade-fragment returns with candle returns.

## Exact macro volume/activity

When both macro boundaries are exact, resolution-dependent macro volume/activity uses the non-overlapping union:

start RIGHT boundary fragment
+ complete interior canonical intervals
+ end LEFT boundary fragment.

The pivot source record's volume/count is counted once in LEFT; RIGHT does not count it again.

A full canonical boundary candle SHALL NOT be included together with a fragment from that same interval.

Higher-resolution fragments may be composed from the trade-resolved 5m piece plus complete canonical 5m intervals.

## Ambiguous macro fallback

If an anchor remains ambiguous, macro volume/TR/activity uses only the fixed-grid constituents wholly inside the fallback unambiguous interval.

The same grid-based expected/observed membership and coverage used by macro path SHALL be used here.

No boundary-overlapping candle/pair contributes to fallback macro summaries.

## Trade/aggTrade provenance

Raw trades and aggTrades are different source granularities. Preserve exact source kind, native sequence ids, underlying trade-id ranges where available, artifact checksum and coverage.

Do not call an aggTrade row an individual trade. Underlying trade count may be calculated only when source-native ids prove it.

## Source timestamp validation

Inventory records source-native timestamp alignment anomalies separately from real missing coverage.

A continuous 60-second off-grid source series (required regression: `+20.799s` December-2017 spot rows) SHALL NOT be counted as a day of missing candles solely because timestamps are not aligned to `:00`.

Canonicalization requires a proven source-specific mapping; original timestamps/provenance remain stored.

## Feature dictionary

Every materialized volume/volatility/activity metric must have one canonical definition with units, source/resolution, availability, null meaning and provenance.
