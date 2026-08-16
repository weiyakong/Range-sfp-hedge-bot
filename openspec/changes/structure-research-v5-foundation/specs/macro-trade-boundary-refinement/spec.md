# Macro Trade Boundary Refinement Contract

## Purpose

Define the preparatory aggregate-trade refinement required before Structure Research v5 assigns macro-leg boundaries. The approved macro segmentation remains unchanged. This stage refines each approved macro pivot inside its reviewed source-localization window(s), preserves all supporting aggTrade evidence, and prepares retrospective boundary fragments for later macro calculations.

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

Every source-localization candidate is scanned as a half-open five-minute interval `[candidate_start, candidate_start + 5m)`. A stored historical end such as `...59.999` is provenance only and SHALL NOT change half-open scan semantics.

The refinement stage SHALL use the approved existing same-market official Binance `aggTrades` stream covering each complete source-localization window. It SHALL NOT pretend an off-grid source-window start is a canonical 5m candle start.

The localization artifact, rather than per-leg `duration_precision`, is the approved anchor-level source for `source_time_precision`, `source_market`, `source_refinement_market`, and `source_refinement_timeframe`.

## Approved source rule

### Requirement: Existing official Binance aggTrades are the primary and approved source

This stage SHALL use the already downloaded official Binance BTCUSDT `aggTrades` data as its approved source:

- spot pivot -> Binance BTCUSDT spot `aggTrades`;
- futures pivot -> Binance BTCUSDT USDT-M futures `aggTrades`.

Raw individual `trades` are NOT preferred, NOT required, and SHALL NOT be downloaded or substituted automatically.

Raw trade files that were already downloaded during an earlier unapproved attempt MAY remain on disk as supplemental evidence, but SHALL NOT participate in pivot selection, boundary construction, feature calculation, QA truth, or canonical refinement outputs unless the user explicitly approves their use in a later decision.

If approved existing `aggTrades` coverage is missing for a required candidate interval, record the coverage limitation and stop/report that case. Do not acquire a different source type without explicit user approval.

Every used `aggTrades` artifact SHALL have provenance and SHA-256 recorded.

### Requirement: aggTrade granularity is represented honestly

An `aggTrade` row is an aggregate source record, not an individual raw trade.

Preserve at minimum where supplied by the source:

- `agg_trade_id`;
- price;
- quantity;
- first underlying trade id;
- last underlying trade id;
- event time;
- source field `m` under an unambiguous canonical name such as `buyer_is_maker`.

For Binance aggTrades, `m` means whether the buyer is the market maker. Do not rename it to a vague generic `maker_side` field.

The deterministic source ordering key is:

`(event_time, agg_trade_id)`.

If `first_trade_id != last_trade_id`, the row contains multiple underlying trades. The pipeline SHALL NOT invent their individual timestamps, ordering, quantities, or a within-aggregate LEFT/RIGHT split.

Any timestamp/sequence exactness claimed by this stage means exact at the approved `aggTrades` source resolution.

## Price identity

### Requirement: Exact price identity uses Decimal/fixed point, never binary float

The completed candle audit established a maximum of two fractional decimal places for relevant BTCUSDT spot/futures prices and macro anchor prices.

Parse price from the source decimal string/`Decimal`, verify that no relevant approved `aggTrades` price has more than two non-zero fractional decimal places after exact decimal normalization, and then use:

`price_units = exact_decimal_price * 100`

as an integer identity representation.

Examples:

- `4039.79000000` -> `403979`;
- `13918.04` -> `1391804`.

If a relevant official `aggTrades` price cannot be represented exactly at scale 2, fail the precision QA and stop rather than round silently.

## Pivot refinement

### Requirement: Trade refinement preserves source macro structure but refines the realized pivot coordinate

The stage SHALL NOT create new macro pivots, delete pivots, alter leg ordering, alter source leg direction, or create impulse/correction labels.

The approved source macro anchor price/time remains preserved under explicit `source_*` fields.

The refinement stage MAY assign a resolved realized pivot price/time from approved aggTrade evidence according to the deterministic rules below. When no exact source-anchor price is traded, the resolved realized price is the directional extremum reached inside the approved candidate window(s), while the original source anchor price remains unchanged as provenance.

### Requirement: All exact source-anchor price aggTrade touches are preserved

For each macro anchor, scan every approved candidate window and collect every eligible `aggTrades` row whose exact `price_units` equals the source anchor `price_units`.

All matching rows are preserved in deterministic `(event_time, agg_trade_id)` order.

If one or more exact matching rows exist with complete approved aggTrade coverage, the resolved pivot is the earliest exact touch by that ordering key.

Therefore multiple exact touches are evidence, not ambiguity: preserve their count and every row, but select the earliest exact touch as the authoritative resolved pivot.

### Requirement: If no exact touch exists, resolve by the furthest directional extremum

With complete approved aggTrade coverage and no exact source-anchor price touch:

- for a `high` pivot, resolved pivot price is the maximum eligible aggTrade price across all approved candidate windows;
- for a `low` pivot, resolved pivot price is the minimum eligible aggTrade price across all approved candidate windows.

This is the furthest realized extremum in the direction of the pivot, not the nearest price to the source anchor.

Preserve the source anchor price separately and preserve every aggTrade row that attains the selected directional extremum.

If the selected extremum price occurs exactly once, its `(event_time, agg_trade_id)` becomes the resolved pivot coordinate.

If the selected extremum price occurs more than once, the resolved realized pivot price is known but the authoritative time/sequence remains unresolved until a separate explicit tie-break rule is approved. Do not silently choose first/last/nearest among repeated equal extrema.

### Requirement: Refinement statuses are explicit

Refinement statuses include at minimum:

- `exact_trade_touch_resolved`: one or more exact source-anchor price touches exist with complete approved source coverage; earliest exact touch selected;
- `extreme_trade_price_resolved`: no exact touch exists, complete approved source coverage exists, directional extremum occurs once and resolves price/time/sequence;
- `repeated_extreme_trade_price`: no exact touch exists, complete approved source coverage exists, directional extremum price occurs multiple times; resolved realized price known but time/sequence unresolved;
- `incomplete_trade_coverage`;
- `source_unavailable`.

A unique 5m localization window does not itself imply a resolved aggTrade pivot.

### Requirement: Resolved pivot coordinate is materialized only when deterministic at approved aggTrade granularity

For `exact_trade_touch_resolved` and `extreme_trade_price_resolved`, preserve:

- `resolved_pivot_time` = selected aggTrade event time;
- `resolved_pivot_sequence_id` = selected `agg_trade_id`;
- `resolved_pivot_price` and `resolved_pivot_price_units`;
- original `source_anchor_price` and `source_anchor_price_units` separately;
- `resolution_method = earliest_exact_touch | directional_extreme`;
- canonical 5m candle start/end containing the selected event time;
- source market/granularity/artifact ids;
- first/last underlying trade ids;
- whether the selected pivot aggTrade contains one or multiple underlying trades.

For exact-touch cases also preserve touch count, every matching row/key, first/last exact-touch time and candidate windows.

For `repeated_extreme_trade_price`, preserve the selected extremum price, occurrence count, every equal-extremum row/key, first/last occurrence time and candidate windows, while `resolved_pivot_time` and `resolved_pivot_sequence_id` remain null.

## Boundary fragments

### Requirement: Canonical 5m candles remain unchanged

Refinement SHALL NOT split, replace, or rewrite canonical fixed 5m candles.

Boundary fragments are additional retrospective macro-analysis entities.

### Requirement: Deterministically resolved aggTrade pivot creates LEFT and RIGHT canonical-5m source fragments

When a pivot has one authoritative aggTrade ordering key, use the canonical 5m interval `[B0,B1)` containing its event time. With pivot aggregate ordering key `K=(event_time,agg_trade_id)` and resolved pivot price `P`:

- LEFT source records contain approved aggTrade rows from canonical `B0` through ordering key `<=K`;
- RIGHT source records contain approved aggTrade rows with ordering key `>K` through canonical `B1`;
- RIGHT begins from price state `P` for price-path continuity even though the pivot aggregate row is not counted again as a RIGHT source record.

The pivot aggTrade row belongs to LEFT exactly once as an indivisible approved source record. It SHALL NOT be duplicated in RIGHT.

If the pivot aggTrade contains multiple underlying trades, its aggregate quantity/count SHALL NOT be split internally between LEFT and RIGHT. Record `volume_split_precision=aggregate_boundary_indivisible` or equivalent explicit status.

If RIGHT has no later aggTrade row, its starting/ending price state remains `P`, its post-pivot aggregate volume/count are zero, and this fact is explicit; it is not a synthetic canonical candle.

### Requirement: Boundary fragments retain objective aggTrade-level measurements separately

For resolved LEFT/RIGHT canonical-5m fragments preserve, where source semantics permit:

- exact source-resolution start/end time and duration;
- open/high/low/close price state;
- signed/absolute ordinary and log displacement;
- `trade_price_path` and `trade_log_price_path` over the ordered aggTrade price sequence;
- upward/downward aggregate-price path;
- path efficiency;
- positive/negative/zero price-step counts;
- sign-change/alternation measures under the zero-step convention;
- first/last/count of fragment extrema at aggTrade resolution;
- base/quote volume where source-accurate;
- aggTrade source-row count;
- underlying trade count only where exactly derivable from source-native first/last ids;
- source-granularity and boundary-volume precision flags;
- provenance and coverage status.

These are explicitly aggregate-trade/boundary-fragment measurements. They are not raw-trade measurements and not canonical 5m close-path measurements.

### Requirement: Aggregate-trade path is never mixed into timeframe close path

A macro path at `5m`, `15m`, `1H`, `4H`, or `1D` SHALL NOT be computed by adding an aggTrade-level fragment path to candle-close path values.

For a resolved macro leg from pivot `(t0,P0)` to `(t1,P1)`, the canonical close-path sequence at calculation resolution `R` is:

- `Q0=P0`;
- chronological closes of complete canonical `R` candles with `t0 < candle.end_time <= t1`;
- append `P1` if the last sequence value is not already the resolved end-pivot price/state.

The same Q sequence defines displacement, directional close-path components, alternation and close-path efficiency at that resolution.

### Requirement: Higher-resolution boundary fragments are composed without additional source downloads

For a resolved pivot and calculation resolution `R` in `5m,15m,1H,4H,1D`, define the LEFT/RIGHT partial `R` interval around the pivot.

The canonical-5m partial piece comes from approved aggTrade refinement. Any remaining portion between the adjacent canonical 5m boundary and enclosing `R` boundary is composed only from complete canonical 5m candles.

This permits boundary OHLCV/geometry/activity at higher resolutions without acquiring a different trade source for the whole higher-TF interval.

Composition SHALL preserve coverage and SHALL fail exactness across a canonical 5m gap/source incompatibility.

### Requirement: Exact macro membership uses fragments plus complete interior candles

For macro volume/activity/geometry/overlap at calculation resolution `R`, a deterministically aggTrade-resolved leg is represented by the non-overlapping union of:

- the start RIGHT boundary fragment at `R`;
- complete canonical `R` candles wholly between the start and end boundary intervals;
- the end LEFT boundary fragment at `R`.

A full canonical boundary candle SHALL NOT be included together with its partial fragment in the same macro metric.

Pairs involving boundary fragments are explicitly identified as fragment pairs and are not stored as ordinary canonical fixed-candle pairs.

### Requirement: Unresolved pivot time uses conservative fallback rather than a forced split

If an anchor has `repeated_extreme_trade_price`, incomplete approved aggTrade coverage, unavailable source, or otherwise lacks one authoritative aggregate-source pivot key:

- do not materialize one authoritative LEFT/RIGHT split;
- preserve all candidate/equal-extremum rows and diagnostics;
- exact duration/speed and exact boundary-dependent metrics remain null;
- fallback macro metrics may use only complete calculation candles whose entire intervals are guaranteed to lie between all possible unresolved boundary occurrences.

If no guaranteed interior fixed-grid slot exists, fallback expected/observed constituent counts are zero and boundary-dependent fallback metrics are null with an explicit `no_unambiguous_interior` status.

The fallback is an uncertainty mechanism, not the primary path when approved aggTrade evidence deterministically resolves the pivot.

## Gate

### Requirement: Main Structure Research v5 is gated on a frozen refinement artifact

Before real macro production, persist a deterministic aggregate-trade refinement artifact/manifest for all 138 anchors and freeze its checksum in the v5 run configuration.

The main pipeline SHALL consume that artifact rather than independently re-selecting touches/extrema.

Raw trade files are outside the approved calculation path unless the user later explicitly authorizes a source change.

Implementation/golden tests may use synthetic fixtures before the real artifact exists, but full-history macro production requires the reviewed real artifact.
