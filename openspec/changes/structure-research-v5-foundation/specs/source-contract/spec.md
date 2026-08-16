# Final BTC Source Contract

## Purpose

Define the exact approved BTCUSDT market-source chronology, source precedence, unresolved gaps, and spot-to-futures boundary used by Structure Research v5.

This specification is the single source of truth for market-source chronology. Feature code and tests SHALL consume this contract/configuration and SHALL NOT independently hardcode a different boundary.

## ADDED Requirements

### Requirement: Spot and futures are separate market populations

Structure Research v5 SHALL use two explicit Binance BTCUSDT market populations:

- Binance BTCUSDT spot;
- Binance BTCUSDT USDT-M perpetual futures.

The canonical 1m analytical history SHALL preserve market type and row-level provenance. Sequential calculations SHALL never treat the spot-to-futures transition as an ordinary market-price step.

### Requirement: Exact futures market inception evidence is preserved separately from the canonical 1m bucket boundary

Official Binance USD-M `daily trades` evidence establishes the first actual BTCUSDT futures trade at:

`2019-09-08T17:57:50.575000Z`.

The first real futures 1m candle bucket begins at:

`2019-09-08T17:57:00Z`.

These timestamps have different meanings and SHALL both be preserved:

- `first_futures_trade_time = 2019-09-08T17:57:50.575000Z` is exact trade-level market-inception evidence;
- `first_futures_1m_start_time = 2019-09-08T17:57:00Z` is the canonical candle-grid boundary.

For candle-based source assignment, `2019-09-08T17:57:00Z` SHALL be the spot-to-futures boundary.

A canonical 1m interval beginning before `2019-09-08T17:57:00Z` belongs to the approved spot regime. A canonical 1m interval beginning at or after `2019-09-08T17:57:00Z` belongs to the approved USDT-M futures regime.

No feature implementation SHALL infer futures inception from the start of a higher-timeframe bucket or from the later start of a public archive package.

### Requirement: Higher-timeframe cache starts are not market-inception timestamps

Previously observed local `cache_futures_1d` and `cache_futures_4h` data beginning on higher-timeframe bucket boundaries SHALL NOT be interpreted as exact futures market inception.

Those caches were produced from official Binance `fapi/v1/klines` data and can start at the enclosing higher-timeframe bucket even though the first actual trade inside that bucket occurred later.

They MAY be retained as historical provenance/QA evidence, but SHALL NOT override the exact trade-level and fresh 1m source evidence in this contract.

### Requirement: Fresh official early-futures 1m pull is canonical source of truth for the pre-public-archive period

The approved early futures canonical block covers:

`2019-09-08T17:57:00Z` through `2019-12-30T23:59:00Z`.

The fresh official Binance `fapi/v1/klines` pull produced:

- native API rows: `163082`;
- exactly one native API missing 1m bucket at `2019-09-08T19:00:00Z`.

That missing minute was deterministically resolved using official Binance `daily trades` evidence establishing the no-trade condition under the validated reconstruction rule documented by the early-futures recovery report.

The final combined early-futures block contains:

- `163083` rows;
- `0` duplicate canonical 1m timestamps;
- `0` remaining 1m gaps.

The recovered/no-trade-derived row SHALL preserve distinct row-level provenance and SHALL NOT be relabeled as a native API kline.

The early block joins continuously to the approved public futures 1m archive beginning:

`2019-12-31T00:00:00Z`.

The change from fresh API/reconstruction provenance to public-archive provenance SHALL NOT create a new source segment when timestamps and market continuity remain valid.

### Requirement: Old local higher-timeframe caches are not canonical where materially inconsistent

The prior local `cache_futures_1d/4h` material confirms early futures existence and official API provenance but contains at least one materially inconsistent area near `2019-09-24`.

Therefore those caches SHALL be treated as QA/reference/provenance material only for this source contract. They SHALL NOT replace the fresh official early-futures 1m pull as canonical source of truth for the early futures interval.

An unexplained mismatch between an old cache and fresh canonical 1m-derived data SHALL be reported as a QA/reference discrepancy, not resolved by overwriting canonical values with the old cache.

### Requirement: Public futures archive continues the same futures market population

From `2019-12-31T00:00:00Z` onward, the approved Binance public BTCUSDT USDT-M futures 1m archive and subsequently approved official futures source parts form the canonical futures 1m history, subject to normal validation.

The public archive start date SHALL NOT be described as futures market inception.

### Requirement: Historical spot source remains canonical before the futures candle boundary

Before `2019-09-08T17:57:00Z`, the canonical Structure Research v5 market history uses the approved Binance BTCUSDT spot 1m source.

Spot rows after that boundary SHALL NOT be substituted for futures rows in the canonical combined research chronology merely because spot data remain available.

### Requirement: The 6,235 historical spot missing minutes are accepted irrecoverable official gaps

The approved spot-gap recovery investigation tested exactly the known `6,235` missing Binance spot 1m minutes against official Binance spot `aggTrades`.

Recovery result:

- missing spot minutes investigated: `6235`;
- recovered from official spot aggTrades: `0`;
- remaining irrecoverable spot minutes: `6235`.

Official aggTrades were empty in the corresponding missing windows, including explicitly checked examples:

- `2017-09-06T16:00:00Z` through `2017-09-06T22:59:00Z`;
- `2018-10-19T06:00:00Z` through `2018-10-19T09:29:00Z`.

The exact unresolved intervals SHALL be read from the approved spot recovery interval artifact rather than re-derived from a rounded monthly count.

These minutes SHALL remain real source gaps. They SHALL NOT be filled by interpolation, forward/backward fill, synthetic flat candles, futures substitution, or third-party data without a later explicit source-contract change.

Each unresolved gap SHALL split source continuity for sequential calculations.

### Requirement: Approved source evidence artifacts are recorded

The finalized source contract SHALL record or configure the following approved evidence artifacts from the source-acquisition/recovery work:

Spot recovery:

- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_spot_recovery_report.md`
- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_spot_missing_minutes_intervals.csv`
- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_spot_recovery_manifest.csv`
- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_spot_missing_minutes_recovered_from_aggtrades.csv`

Early futures:

- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_early_futures_1m_report.md`
- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/btc_early_futures_1m_manifest.csv`

Implementation SHALL verify configured artifact existence/fingerprints where feasible before treating them as the approved source evidence for a production run.

### Requirement: Canonical source chronology is explicit

The first-pass canonical candle chronology SHALL be interpreted as:

1. approved Binance BTCUSDT spot 1m history before `2019-09-08T17:57:00Z`, with the documented irrecoverable spot gaps preserved;
2. approved Binance BTCUSDT USDT-M futures 1m history beginning with the candle bucket `2019-09-08T17:57:00Z` and continuing forward through the fresh early API block, public archive block, and later approved futures parts.

The spot-to-futures transition itself SHALL be a market-source boundary. It SHALL never contribute an ordinary return, TR, ATR update, RV return, path step, overlap pair, alternation step, or adjacent-window comparison.

### Requirement: Source-contract validation status is complete

The early-futures source investigation has final status:

`COMPLETE`.

The old spot recovery has final source conclusion:

`COMPLETE_WITH_DOCUMENTED_SOURCE_GAPS` for the historical spot population because the 6,235 missing minutes are confirmed irrecoverable from the tested official lower-level source.

These known spot gaps are expected source limitations, not hidden QA failures. A production pipeline that fabricates or bridges them as complete is a QA failure.
