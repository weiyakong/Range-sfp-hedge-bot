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

There are 145 distinct candidate windows: 59 spot and 86 USDT-M futures. 142 starts are on the canonical 5m grid. Three spot candidates inherit the proven `+20.799s` source-kline offset:
- E00059 `2017-12-07T23:55:20.799Z`
- E00065 `2017-12-10T04:30:20.799Z`
- E00070 `2017-12-17T12:10:20.799Z`.

Every source-localization candidate is scanned as half-open `[candidate_start,candidate_start+5m)`. Stored historical ends such as `...59.999` are provenance only.

## Approved source rule

Use already downloaded official Binance BTCUSDT `aggTrades` only:
- spot pivot -> spot aggTrades;
- futures pivot -> USDT-M futures aggTrades.

Raw individual trades are outside the approved calculation path unless the user later explicitly approves a source-contract change. Missing/incomplete aggTrade coverage is reported; it SHALL NOT trigger raw-trade substitution.

Every used aggTrade artifact records provenance and SHA-256.

### Bounded source access is mandatory

The implementation SHALL NOT repeatedly load or parse an entire daily/monthly aggTrade archive inside anchor, candidate-window, or fragment loops.

Required access behavior:
- candidate refinement reads only rows needed for the specific approved candidate window(s);
- fragment construction reads only the complete canonical 5m bucket `[B0,B1)` containing the resolved pivot;
- higher-TF fragments reuse the 5m fragment plus complete canonical 5m candles and SHALL NOT rescan aggTrades for the whole 15m/1H/4H/1D interval;
- when several anchors/fragments require the same source window/bucket within one pass, the already parsed bounded result SHOULD be reused instead of reopening/reparsing the source archive;
- memory use SHALL be bounded by the requested window/bucket plus parser buffer, not by whole archive size.

For ZIP/CSV aggTrade archives, the hot-path reader SHALL use robust streaming iteration/filtering over the archive member and select only the requested time/bucket rows. A `pandas.read_csv` or equivalent whole-file parser/materialization SHALL NOT be used as the per-anchor/per-fragment bucket reader.

If a parser cannot read the official aggTrade archive reliably, the run SHALL stop/report an explicit source-reader failure. Parser failure SHALL NOT be reclassified as missing market coverage and SHALL NOT authorize raw individual-trade fallback.

## aggTrade granularity

An aggTrade row is an aggregate source record, not an individual raw trade. Preserve where supplied: `agg_trade_id`, price, quantity, first/last underlying trade ids, event time, and source field `m` under the canonical name `buyer_is_maker`.

Deterministic source ordering key: `(event_time,agg_trade_id)`.

If first underlying trade id differs from last, do not invent internal timestamps/order/quantities or split the aggregate internally between LEFT/RIGHT.

## Price identity

Parse exact Decimal strings. Relevant approved prices must be exactly representable at scale 2 after decimal normalization.

`price_units = exact_decimal_price * 100`.

Examples: `4039.79000000 -> 403979`; `13918.04 -> 1391804`. Greater required scale fails QA; do not round silently.

## Pivot refinement

The source macro anchor coordinate remains preserved under `source_*` fields.

For each anchor, scan all approved candidate windows and preserve every exact aggTrade row whose price equals the source anchor price.

If one or more exact matching rows exist with complete coverage, select the earliest by `(event_time,agg_trade_id)`. Multiple exact touches remain preserved as evidence but are not ambiguous.

If no exact touch exists with complete coverage:
- high pivot -> maximum eligible aggTrade price across all approved candidate windows;
- low pivot -> minimum eligible aggTrade price across all approved candidate windows.

This is the furthest directional realized extremum, not nearest-price matching. Preserve every row attaining the selected extremum.

If selected extremum occurs once, its key resolves the pivot. If it occurs multiple times, resolved realized price is known but authoritative time/id remain unresolved until a separate explicit tie-break rule is approved.

Statuses include:
- `exact_trade_touch_resolved`
- `extreme_trade_price_resolved`
- `repeated_extreme_trade_price`
- `incomplete_trade_coverage`
- `source_unavailable`
- `source_reader_failure`.

For resolved cases preserve refined time/id/price, source anchor coordinate separately, resolution method, canonical 5m containment, source ids/checksums and aggregate metadata.

## Boundary fragments

Canonical fixed 5m candles remain unchanged.

For one authoritative pivot key `K=(event_time,agg_trade_id)` inside canonical `[B0,B1)` and refined pivot price `P`:
- LEFT contains approved aggTrade rows within `[B0,B1)` with key `<=K`;
- RIGHT contains rows within `[B0,B1)` with key `>K`;
- RIGHT starts from price state `P`;
- pivot aggregate belongs LEFT exactly once.

If RIGHT has no later row, its price state remains P and post-pivot aggregate volume/count are zero.

Persist objective fragment OHLCV/geometry/activity/path features at aggTrade granularity. These are not raw-trade measurements.

Higher-resolution fragments compose from the resolved partial canonical 5m fragment plus complete canonical 5m intervals only.

## Macro membership/path

Resolved macro volume/activity/geometry/overlap at R uses the non-overlapping union:
start RIGHT fragment + complete interior canonical R intervals + end LEFT fragment.

A full boundary candle never coexists with its partial fragment in one metric.

TF close path uses refined start price, qualifying complete canonical R closes with `start < candle.end <= end`, then refined end price if needed. AggTrade fragment path is separate and never added to TF close path.

## Unresolved-time fallback

If authoritative pivot time is unresolved/unavailable, do not force a split. Preserve all evidence. Exact endpoint-dependent metrics remain null. Fallback uses only complete fixed-grid intervals guaranteed inside all possible boundary occurrences.

If no guaranteed interior slot exists, expected/observed counts are zero and boundary-dependent fallback metrics are null with `no_unambiguous_interior`.

## Gate

Before real macro production persist/freeze a deterministic refinement artifact for all 138 anchors. Main v5 consumes that artifact and SHALL NOT independently reselect touches/extrema or switch source type.
