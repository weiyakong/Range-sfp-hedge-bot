# Macro Trade Boundary Refinement Contract

## Purpose

Define the preparatory trade-level refinement required before Structure Research v5 assigns exact macro-leg boundaries. The approved macro segmentation remains unchanged; this stage only determines where each approved macro pivot occurred inside its already-localized candidate window(s), preserves ambiguity when equal extrema repeat, and prepares exact boundary fragments for later macro calculations.

## Approved prerequisite inputs

The approved macro source is `macro_legs_log20.csv` with SHA-256:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

The reviewed localization artifact is `macro_pivots_5m_all.csv` with SHA-256:

`77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`.

It contains 138 unique macro pivots:

- 131 `unique_5m_match`;
- 7 `multiple_5m_matches`;
- 0 incomplete/unresolved.

There are 145 distinct candidate windows: 59 spot and 86 USDT-M futures.

Important source anomaly: 142 candidate starts are on the canonical 5m grid, but three spot candidates inherited the proven `+20.799s` source-kline offset and are therefore 5-minute source-localization windows, not canonical fixed 5m candles:

- `E00059`: `2017-12-07T23:55:20.799Z`
- `E00065`: `2017-12-10T04:30:20.799Z`
- `E00070`: `2017-12-17T12:10:20.799Z`.

The trade stage SHALL use the official same-market trade stream covering each complete off-grid window (plus enough neighboring coverage to identify the enclosing canonical 5m interval), locate the exact pivot touch, and then record the canonical 5m candle containing that exact pivot. It SHALL NOT pretend the off-grid window start is a canonical 5m candle start.

The localization artifact, rather than per-leg `duration_precision`, is the approved anchor-level source for `source_time_precision`, `source_market`, `source_refinement_market`, and `source_refinement_timeframe`.

## Requirements

### Requirement: Trade refinement never changes macro structure

The stage SHALL NOT create new macro pivots, delete pivots, move an anchor to a different price, alter leg direction, or create impulse/correction labels.

It refines only the time/sequence location of the approved anchor price inside approved candidate window(s).

### Requirement: Same-market official trade evidence is used

For every candidate window, use the matching Binance market population:

- spot pivot -> Binance BTCUSDT spot trade evidence;
- futures pivot -> Binance BTCUSDT USDT-M futures trade evidence.

Prefer already available local official archives. If required data are absent locally, download only the necessary candidate interval/day/archive from an official Binance source.

Raw `trades` are preferred when available. Official `aggTrades` are allowed when raw trades are unavailable, but the source granularity SHALL be recorded and aggregate rows SHALL NOT be described as individual raw trades.

Every downloaded/used artifact SHALL have provenance and SHA-256 recorded.

### Requirement: Exact price identity uses Decimal/fixed point, never binary float

The completed candle audit established a maximum of two significant decimal places for relevant BTCUSDT spot/futures prices and macro anchor prices.

Parse price from the source decimal string/`Decimal`, verify that no downloaded trade price used by this stage has more than two significant decimal places, and then use:

`price_units = exact_decimal_price * 100`

as an integer identity representation.

Examples:

- `4039.79000000` -> `403979`;
- `13918.04` -> `1391804`.

If a relevant official trade price cannot be represented exactly at `N=2`, fail the precision QA and stop rather than round it silently.

### Requirement: Native sequence identity disambiguates equal timestamps

Timestamp alone is insufficient to cut a trade stream because multiple records may share one event time.

Each candidate record SHALL preserve the native monotonic sequence identifier appropriate to the source, such as raw `trade_id` or `agg_trade_id` plus first/last underlying trade ids when supplied.

The deterministic ordering key is at minimum:

`(event_time, native_sequence_id)`.

### Requirement: All exact anchor-price touches are preserved

For each macro anchor, scan every approved candidate window and collect every eligible source record whose exact `price_units` equals the anchor `price_units`.

Refinement statuses include at minimum:

- `exact_unique_trade_touch`: exactly one eligible touch across all candidate windows and complete required source coverage;
- `multiple_exact_trade_touches`: two or more eligible touches; preserve all and do not choose first/last/nearest;
- `no_exact_trade_touch`;
- `incomplete_trade_coverage`;
- `source_unavailable`.

A unique 5m localization window does not imply the trade touch is unique.

### Requirement: Exact pivot time is materialized only for a unique touch

For `exact_unique_trade_touch`, preserve:

- `exact_pivot_time`;
- `exact_pivot_sequence_id`;
- exact anchor price/price units;
- canonical 5m candle start/end containing the exact pivot;
- source market/granularity/artifact ids.

For multiple touches, `exact_pivot_time` and exact sequence id remain null. Preserve touch count, every touch row/key, first/last touch time, candidate windows and canonical 5m candle(s) containing those touches.

No semantic rule such as “first touch”, “last touch”, or “the touch before the largest move” is authorized in this descriptive pass.

### Requirement: Canonical 5m candles remain unchanged

Trade refinement SHALL NOT split, replace, or rewrite canonical fixed 5m candles.

Boundary fragments are additional retrospective macro-analysis entities.

### Requirement: Unique pivot creates deterministic LEFT and RIGHT canonical-5m fragments

After the exact pivot is located, use the canonical 5m interval `[B0,B1)` containing it. With ordered pivot record key `K` and pivot price `P`:

- LEFT contains source records from canonical `B0` through ordering key `<=K`;
- RIGHT contains source records with ordering key `>K` through canonical `B1`;
- RIGHT starts from price state `P` even though the pivot record itself is not counted again as a RIGHT trade.

The pivot source record's volume/count belongs to LEFT exactly once. It SHALL NOT be double-counted in RIGHT.

If RIGHT has no later trade, its starting/ending price state remains `P`, its trade volume/count are zero, and this fact is explicit; it is not a synthetic canonical candle.

### Requirement: 5m trade fragments retain objective microstructure measurements separately

For exact LEFT/RIGHT canonical-5m fragments preserve, where source semantics permit:

- exact start/end time and duration;
- open/high/low/close price state;
- signed/absolute ordinary and log displacement;
- `trade_price_path` and `trade_log_price_path` over the ordered source-price sequence;
- upward/downward trade-price path;
- trade-path efficiency;
- positive/negative/zero price-step counts;
- sign-change/alternation measures under the zero-step convention;
- first/last/count of fragment extrema;
- base/quote volume where source-accurate;
- source row/aggregate count;
- underlying trade count only where exactly derivable from source-native ids;
- provenance and coverage status.

These are explicitly `trade_*`/boundary-fragment measurements. They are not canonical 5m close-path measurements.

### Requirement: Tick/trade path is never mixed into timeframe close path

A macro path at `5m`, `15m`, `1H`, `4H`, or `1D` SHALL NOT be computed by adding a trade-level fragment path to candle-close path values.

For an exact macro leg from pivot `(t0,P0)` to `(t1,P1)`, the canonical close-path sequence at calculation resolution `R` is:

- `Q0=P0`;
- chronological closes of complete canonical `R` candles with `t0 < candle.end_time <= t1`;
- append `P1` if the last sequence value is not already the exact end-anchor price/state.

The same Q sequence defines displacement, directional close-path components, alternation and close-path efficiency at that resolution.

### Requirement: Higher-resolution boundary fragments are composed without additional tick downloads

For an exact pivot and calculation resolution `R` in `5m,15m,1H,4H,1D`, define the LEFT/RIGHT partial `R` interval around the pivot.

The canonical-5m partial piece comes from trade refinement. Any remaining portion between the adjacent canonical 5m boundary and enclosing `R` boundary is composed only from complete canonical 5m candles.

This permits exact boundary OHLCV/geometry/activity at higher resolutions without downloading trades for the whole higher-TF interval.

Composition SHALL preserve coverage and SHALL fail exactness across a canonical 5m gap/source incompatibility.

### Requirement: Exact macro membership uses fragments plus complete interior candles

For macro volume/activity/geometry/overlap at calculation resolution `R`, an exact leg is represented by the non-overlapping union of:

- the start RIGHT boundary fragment at `R`;
- complete canonical `R` candles wholly between the start and end boundary intervals;
- the end LEFT boundary fragment at `R`.

A full canonical boundary candle SHALL NOT be included together with its partial fragment in the same macro metric.

Pairs involving boundary fragments are explicitly identified as fragment pairs and are not stored as ordinary canonical fixed-candle pairs.

### Requirement: Ambiguous trade touches use conservative fallback rather than forced exact fragments

If an anchor has multiple exact touches or otherwise lacks a unique pivot sequence key:

- do not materialize one authoritative LEFT/RIGHT split;
- preserve all candidate touch rows and candidate-specific diagnostics if useful;
- macro exact duration/speed and exact boundary-dependent metrics remain null;
- fallback macro metrics may use only complete calculation candles whose entire intervals are unambiguously between all possible boundary touches.

The fallback is an uncertainty mechanism, not the primary path when exact trade refinement succeeds.

### Requirement: Main Structure Research v5 is gated on a frozen refinement artifact

Before real macro production, persist a deterministic trade-refinement artifact/manifest for all 138 anchors and freeze its checksum in the v5 run configuration.

The main pipeline SHALL consume that artifact rather than independently re-selecting trade touches.

Implementation/golden tests may use synthetic fixtures before the real artifact exists, but full-history macro production requires the reviewed real artifact.
