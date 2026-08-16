# Macro Trade Boundary Refinement Contract

## Purpose

Define the preparatory aggregate-trade refinement required before Structure Research v5 assigns exact macro-leg boundaries. The approved macro segmentation remains unchanged; this stage only determines where each approved macro pivot occurred inside its already-localized candidate window(s), preserves ambiguity when equal extrema repeat, and prepares boundary fragments for later macro calculations.

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

The refinement stage SHALL use the approved existing same-market official Binance `aggTrades` stream covering each complete source-localization window, locate all exact anchor-price touches, and then record the canonical 5m candle containing the resolved touch when resolution is unique at aggTrade-source granularity. It SHALL NOT pretend an off-grid source-window start is a canonical 5m candle start.

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
- maker-side source field.

The deterministic source ordering key is:

`(event_time, agg_trade_id)`.

If `first_trade_id != last_trade_id`, the row contains multiple underlying trades. The pipeline SHALL NOT invent their individual timestamps, ordering, quantities, or a within-aggregate LEFT/RIGHT split.

Any timestamp/sequence exactness claimed by this stage means exact at the approved `aggTrades` source resolution.

## Price identity

### Requirement: Exact price identity uses Decimal/fixed point, never binary float

The completed candle audit established a maximum of two significant decimal places for relevant BTCUSDT spot/futures prices and macro anchor prices.

Parse price from the source decimal string/`Decimal`, verify that no relevant approved `aggTrades` price has more than two significant decimal places, and then use:

`price_units = exact_decimal_price * 100`

as an integer identity representation.

Examples:

- `4039.79000000` -> `403979`;
- `13918.04` -> `1391804`.

If a relevant official `aggTrades` price cannot be represented exactly at `N=2`, fail the precision QA and stop rather than round silently.

## Pivot refinement

### Requirement: Trade refinement never changes macro structure

The stage SHALL NOT create new macro pivots, delete pivots, move an anchor to a different price, alter leg direction, or create impulse/correction labels.

It refines only the time/sequence location of the approved anchor price inside approved candidate window(s).

### Requirement: All exact anchor-price aggTrade touches are preserved

For each macro anchor, scan every approved candidate window and collect every eligible `aggTrades` row whose exact `price_units` equals the anchor `price_units`.

Refinement statuses include at minimum:

- `exact_unique_trade_touch`: exactly one eligible matching aggTrade row across all candidate windows and complete approved source coverage;
- `multiple_exact_trade_touches`: two or more eligible matching aggTrade rows; preserve all and do not choose first/last/nearest;
- `no_exact_trade_touch`;
- `incomplete_trade_coverage`;
- `source_unavailable`.

The status names are retained for schema compatibility, but `trade_source_granularity=agg_trade` SHALL make clear that uniqueness/exactness is at aggregate-source resolution, not reconstructed raw-trade resolution.

A unique 5m localization window does not imply a unique aggTrade touch.

### Requirement: Exact pivot coordinate is materialized only for one unique aggTrade touch

For `exact_unique_trade_touch`, preserve:

- `exact_pivot_time` = matching aggTrade event time;
- `exact_pivot_sequence_id` = matching `agg_trade_id`;
- exact anchor price/price units;
- canonical 5m candle start/end containing that event time;
- source market/granularity/artifact ids;
- first/last underlying trade ids;
- whether the pivot aggTrade contains one or multiple underlying trades.

For multiple matching aggTrade rows, `exact_pivot_time` and exact sequence id remain null. Preserve touch count, every matching row/key, first/last touch time, candidate windows and canonical 5m candle(s) containing those touches.

No semantic rule such as first touch, last touch, nearest touch, or the touch before the largest move is authorized.

## Boundary fragments

### Requirement: Canonical 5m candles remain unchanged

Refinement SHALL NOT split, replace, or rewrite canonical fixed 5m candles.

Boundary fragments are additional retrospective macro-analysis entities.

### Requirement: Unique aggTrade touch creates deterministic LEFT and RIGHT canonical-5m source fragments

After one unique matching aggTrade row is located, use the canonical 5m interval `[B0,B1)` containing its event time. With pivot aggregate ordering key `K=(event_time,agg_trade_id)` and pivot price `P`:

- LEFT source records contain approved aggTrade rows from canonical `B0` through ordering key `<=K`;
- RIGHT source records contain approved aggTrade rows with ordering key `>K` through canonical `B1`;
- RIGHT begins from price state `P` for price-path continuity even though the pivot aggregate row is not counted again as a RIGHT source record.

The pivot aggTrade row belongs to LEFT exactly once as an indivisible approved source record. It SHALL NOT be duplicated in RIGHT.

If the pivot aggTrade contains multiple underlying trades, its aggregate quantity/count SHALL NOT be split internally between LEFT and RIGHT. Record `volume_split_precision=aggregate_boundary_indivisible` or equivalent explicit status.

If RIGHT has no later aggTrade row, its starting/ending price state remains `P`, its post-pivot aggregate volume/count are zero, and this fact is explicit; it is not a synthetic canonical candle.

### Requirement: Boundary fragments retain objective aggTrade-level measurements separately

For exact LEFT/RIGHT canonical-5m fragments preserve, where source semantics permit:

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

For an exact macro leg from pivot `(t0,P0)` to `(t1,P1)`, the canonical close-path sequence at calculation resolution `R` is:

- `Q0=P0`;
- chronological closes of complete canonical `R` candles with `t0 < candle.end_time <= t1`;
- append `P1` if the last sequence value is not already the exact end-anchor price/state.

The same Q sequence defines displacement, directional close-path components, alternation and close-path efficiency at that resolution.

### Requirement: Higher-resolution boundary fragments are composed without additional source downloads

For a resolved pivot and calculation resolution `R` in `5m,15m,1H,4H,1D`, define the LEFT/RIGHT partial `R` interval around the pivot.

The canonical-5m partial piece comes from approved aggTrade refinement. Any remaining portion between the adjacent canonical 5m boundary and enclosing `R` boundary is composed only from complete canonical 5m candles.

This permits boundary OHLCV/geometry/activity at higher resolutions without acquiring a different trade source for the whole higher-TF interval.

Composition SHALL preserve coverage and SHALL fail exactness across a canonical 5m gap/source incompatibility.

### Requirement: Exact macro membership uses fragments plus complete interior candles

For macro volume/activity/geometry/overlap at calculation resolution `R`, a uniquely aggTrade-resolved leg is represented by the non-overlapping union of:

- the start RIGHT boundary fragment at `R`;
- complete canonical `R` candles wholly between the start and end boundary intervals;
- the end LEFT boundary fragment at `R`.

A full canonical boundary candle SHALL NOT be included together with its partial fragment in the same macro metric.

Pairs involving boundary fragments are explicitly identified as fragment pairs and are not stored as ordinary canonical fixed-candle pairs.

### Requirement: Ambiguous aggTrade touches use conservative fallback rather than forced exact fragments

If an anchor has multiple exact aggTrade touches or otherwise lacks one unique aggregate-source pivot key:

- do not materialize one authoritative LEFT/RIGHT split;
- preserve all candidate touch rows and candidate-specific diagnostics if useful;
- macro exact duration/speed and exact boundary-dependent metrics remain null;
- fallback macro metrics may use only complete calculation candles whose entire intervals are unambiguously between all possible boundary touches.

The fallback is an uncertainty mechanism, not the primary path when approved aggTrade evidence resolves the anchor uniquely.

## Gate

### Requirement: Main Structure Research v5 is gated on a frozen refinement artifact

Before real macro production, persist a deterministic aggregate-trade refinement artifact/manifest for all 138 anchors and freeze its checksum in the v5 run configuration.

The main pipeline SHALL consume that artifact rather than independently re-selecting touches.

Raw trade files are outside the approved calculation path unless the user later explicitly authorizes a source change.

Implementation/golden tests may use synthetic fixtures before the real artifact exists, but full-history macro production requires the reviewed real artifact.
