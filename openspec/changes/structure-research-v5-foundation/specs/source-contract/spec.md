# Final BTC Source Contract

## Purpose

Define the exact approved BTCUSDT market-source chronology, source precedence, unresolved gaps, and spot-to-futures boundary used by Structure Research v5.

This specification is the single source of truth for canonical market-source chronology. Feature code and tests SHALL consume this contract/configuration and SHALL NOT independently hardcode a different boundary.

## ADDED Requirements

### Requirement: Spot and futures are separate market populations

Structure Research v5 SHALL use two explicit Binance BTCUSDT market populations:

- Binance BTCUSDT spot;
- Binance BTCUSDT USDT-M perpetual futures.

The canonical 1m analytical history SHALL preserve market type and row-level provenance. Sequential calculations SHALL never treat the spot-to-futures transition as an ordinary market-price step.

### Requirement: Exact futures market inception evidence is separate from the canonical 1m bucket boundary

Official Binance USD-M `daily trades` evidence establishes the first actual BTCUSDT futures trade at:

`2019-09-08T17:57:50.575000Z`.

The first real futures 1m bucket begins at:

`2019-09-08T17:57:00Z`.

These timestamps have different meanings and SHALL both be preserved:

- `first_futures_trade_time = 2019-09-08T17:57:50.575000Z` is exact trade-level market-inception evidence;
- `first_futures_1m_start_time = 2019-09-08T17:57:00Z` is the canonical candle-grid boundary.

For candle-based source assignment, `2019-09-08T17:57:00Z` SHALL be the spot-to-futures boundary.

A canonical 1m interval beginning before that boundary belongs to the approved spot regime. A canonical 1m interval beginning at or after that boundary belongs to the approved USDT-M futures regime.

Spot source rows after the boundary MAY remain in raw/source inventory for provenance but SHALL NOT enter the canonical combined research chronology.

### Requirement: Higher-timeframe cache starts are not market-inception timestamps

Previously observed local `cache_futures_1d` and `cache_futures_4h` data beginning on enclosing higher-timeframe bucket boundaries SHALL NOT be interpreted as exact futures market inception.

Those caches MAY remain historical provenance/diagnostic QA material, but SHALL NOT override the exact trade-level and fresh 1m source evidence in this contract.

### Requirement: Fresh official early-futures pull is the authoritative early futures source

The fresh official Binance `fapi/v1/klines` early futures pull covers native rows from `2019-09-08T17:57:00Z` through `2019-12-30T23:59:00Z` and produced `163082` native API rows.

The native API omitted exactly one 1m bucket at:

`2019-09-08T19:00:00Z`.

Official Binance daily-trades evidence establishes:

- no native `fapi/v1/klines` row exists for that minute in the audited pull;
- `0` official trades occurred in `[2019-09-08T19:00:00Z,2019-09-08T19:01:00Z)`;
- `0` official trades occurred even in the wider audited interval `[2019-09-08T18:59:00Z,2019-09-08T19:01:59.999Z]`;
- neighboring official 18:59 and 19:01 candles are flat at `10000` with zero volume/trades.

A previous repair artifact inserted `10000/10000/10000/10000`, zero-volume, zero-trade data for 19:00. The forensic audit classifies that row as a `deterministic synthetic no-trade bucket`, not an observed official native kline.

Because Structure Research v5 prohibits synthetic canonical market candles when OHLC is not directly observed from approved source data, that inserted 19:00 row SHALL NOT be promoted into strict canonical `candles_1m`.

The 19:00 minute SHALL instead be represented as one documented canonical futures source gap with reason equivalent to:

`native_kline_missing_no_trades_no_observed_ohlc`.

The synthetic row MAY be retained outside canonical data as diagnostic recovery evidence with explicit provenance, but SHALL NOT satisfy complete-coverage checks.

Therefore strict canonical early-futures history contains one unresolved 1m source gap at 19:00 and source continuity SHALL split around it.

### Requirement: Public futures archive continues the same futures market population after the documented early gap

The approved early futures native block otherwise continues through `2019-12-30T23:59:00Z` and joins timestamp-continuously to the approved public futures archive beginning `2019-12-31T00:00:00Z`.

The change from fresh API provenance to public-archive provenance SHALL NOT itself create a new source segment.

The public archive start SHALL NOT be described as futures market inception.

### Requirement: Legacy higher-timeframe futures caches are diagnostic references, not canonical truth

The prior local `cache_futures_1d/4h` material confirms early futures existence and official API provenance but contains at least one materially inconsistent area near `2019-09-24`.

Those caches SHALL therefore be treated as diagnostic/reference material only. They SHALL NOT overwrite fresh canonical 1m-derived values and SHALL NOT act as critical ground truth for QA in known or unexplained inconsistent regions.

A separately validated trustworthy native higher-timeframe reference MAY be used for critical aggregation QA.

### Requirement: Raw spot gap count and canonical spot gap count remain distinct

The full raw historical spot inventory contains `6235` missing spot minutes.

After applying the canonical spot cutoff `2019-09-08T17:57:00Z`:

- raw spot missing minutes = `6235`;
- canonical-relevant spot missing minutes reported by the recovery audit = `5972`;
- excluded post-boundary raw spot missing minutes = `263`;
- reported canonical-relevant continuous gap intervals = `16`.

The post-boundary 263 raw spot missing minutes SHALL NOT be treated as gaps in the canonical combined market chronology because canonical research uses futures after the boundary.

The 5972/16 values are source-audit evidence, but production `source_gaps` boundaries SHALL be derived from the validated canonical UTC 1m grid, not copied blindly from audit timestamp strings.

The uploaded canonical-gap audit contains several boundary timestamps with non-minute seconds/milliseconds (for example `...20.799` and `...14.789`). Such values are evidence of source/alignment irregularity and SHALL trigger canonical alignment validation. They SHALL NOT become canonical 1m gap boundaries without normalization justified by the actual source rows.

Every strict canonical unresolved spot gap SHALL remain a real gap. No interpolation, forward/backward fill, synthetic flat candle, futures substitution, or third-party substitution is permitted.

### Requirement: Canonical 1m timestamps must be minute-grid aligned

Every canonical 1m candle start SHALL lie exactly on the UTC minute grid and every canonical interval SHALL be `[minute, minute+1m)`.

Source rows with non-minute-aligned timestamps SHALL NOT be silently rounded and accepted as valid candles.

Source inventory/canonicalization SHALL classify them explicitly and determine the resulting valid minute-grid coverage. Final production gap counts/intervals and source-segment counts SHALL be recomputed from the validated canonical grid and reported against the 5972/16 audit expectation.

Any unexplained difference is a source-contract QA failure requiring review, not an automatic rewrite of the expected evidence.

### Requirement: Canonical source chronology is explicit

The strict first-pass canonical candle chronology SHALL be interpreted as:

1. approved Binance BTCUSDT spot 1m history before `2019-09-08T17:57:00Z`, with validated canonical spot gaps preserved;
2. approved Binance BTCUSDT USDT-M futures 1m history beginning at `2019-09-08T17:57:00Z`, with the documented native/source gap at `2019-09-08T19:00:00Z`, then continuing through the remaining fresh early API rows, the public archive, and later approved futures parts.

The spot-to-futures transition SHALL never contribute an ordinary return, TR, ATR update, RV return, path step, overlap pair, alternation step, or adjacent-window comparison.

The 19:00 futures source gap likewise SHALL break complete sequential calculations.

### Requirement: Old macro source provenance is not identical to canonical chronology

The approved `macro_legs_log20.csv` was built from an older mixed research source.

For its parent daily source:

- old merged daily data remain `spot` through `2019-12-30T00:00:00Z`;
- old merged daily data switch to `futures` at `2019-12-31T00:00:00Z`.

However, the macro build also used futures 4H refinement beginning in September 2019. Audited Oct-Nov 2019 anchors match futures 4H rows while their parent daily regime remains spot.

Therefore late-2019 macro provenance is explicitly `mixed` (`spot daily + futures 4H refinement`) and SHALL NOT be reassigned solely by the current canonical spot/futures boundary.

Canonical market type for a research interval and historical macro-source provenance SHALL be stored as separate concepts.

### Requirement: Approved source evidence artifacts are recorded

The source contract SHALL configure/reference the following audit evidence:

Spot recovery/canonical-gap audit:

- `btc_spot_recovery_report.md`
- `btc_spot_missing_minutes_intervals.csv`
- `btc_spot_recovery_manifest.csv`
- `btc_canonical_spot_gap_intervals.csv`
- `btc_canonical_spot_gap_summary.md`

Early futures:

- `btc_early_futures_1m_report.md`
- `btc_early_futures_1m_manifest.csv`
- `btc_futures_20190908_1900_reconstruction_audit.md`
- `btc_futures_20190908_1900_row.csv`

Macro provenance:

- `macro_legs_source_transition_audit.md`
- `macro_legs_2019_source_audit.csv`.

Production configuration SHOULD record exact paths and fingerprints/checksums of the locally approved copies rather than discover files by similar names.

### Requirement: Source-contract validation status is explicit

Source acquisition/recovery is sufficiently investigated to implement Structure Research v5, with known source limitations represented rather than hidden:

- canonical historical spot: `COMPLETE_WITH_DOCUMENTED_SOURCE_GAPS`;
- strict canonical early futures: `COMPLETE_WITH_DOCUMENTED_SOURCE_GAP` because native 19:00 OHLC is unobserved and the synthetic repair is excluded from canonical data;
- later validated futures archive: subject to its normal manifest/inventory QA.

Known approved gaps are expected source limitations. Fabricating or bridging them as complete is a critical QA failure.
