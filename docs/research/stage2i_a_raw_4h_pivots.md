# Stage 2I-A — raw 4H pivots and context

## Scope and source

Stage 2I-A is a raw candidate-generator dataset, not a structural-level model. It preserves every strict five-bar pivot and does not classify significance, remove micro fluctuations, create zones, infer trend, or test trades.

The only price source is the canonical Binance USD-M futures BTCUSDT 4H dataset at `/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/derived/BTCUSDT/4h/`. Its manifest and all eight Parquet partitions passed SHA256 and row-count verification.

| Source fact | Value |
|---|---:|
| Coverage | 2019-09-08 16:00 UTC to 2026-09-26 00:00 UTC exclusive |
| Canonical rows | 15,446 |
| Complete rows used | 15,445 |
| Incomplete rows excluded | 1 |
| Contiguous complete runs | 1 |

The excluded row is the first partial 4H candle. It is never used in pivot generation. The remaining complete population is contiguous.

## Result

| Measure | Value |
|---|---:|
| Raw HIGH events | 2,243 |
| Raw LOW events | 2,207 |
| Total raw pivot events | 4,450 |
| Dual HIGH+LOW candles | 150 |
| Events per 100 complete bars | 28.812 |
| Median gap between distinct pivot candles | 3 bars / 12 hours |

Pivots per year:

| Year | HIGH | LOW | Total |
|---|---:|---:|---:|
| 2019 | 108 | 106 | 214 |
| 2020 | 320 | 320 | 640 |
| 2021 | 303 | 300 | 603 |
| 2022 | 315 | 318 | 633 |
| 2023 | 340 | 338 | 678 |
| 2024 | 324 | 292 | 616 |
| 2025 | 311 | 313 | 624 |
| 2026 | 222 | 220 | 442 |

The median distance to the previous opposite pivot is 4 bars (16 hours); the maximum is 32 bars (128 hours). The median absolute pivot-price move from the previous opposite pivot is 1,444.9 USDT. These are descriptive raw-population measurements, not thresholds.

## Causality contract

The event timestamp remains the center candle timestamp, but the event is not available until the second right-hand candle closes. Both `confirmation_timestamp` and `available_from` store that later instant.

- `causal__*`: known by `available_from`, including the five candles required for confirmation and prior-pivot geometry.
- `postevent__*`: future-relative diagnostics, including all next-pivot relations and fixed horizons. These fields are prohibited as pivot-time predictors without a later explicit contract.

The authoritative schema JSON records name, Arrow type, definition, units, nullability, and information status for all 237 columns.

## QA

Smoke and production runs passed. Production QA independently checked the strict definition, edge/gap behavior, ordering, uniqueness, right-two-bar confirmation time, source-row references, causal naming, and Parquet schema/row count. Five calendar-window candlestick charts—including a 2026 window—plot every raw pivot without zones or labels. Artifact checksums passed.

Automated unit tests cover strict HIGH/LOW, equality exclusion, edge exclusion, incomplete-candle gaps, dual events, confirmation timing, ordering, uniqueness, causal naming, non-negative excursions, and deterministic Parquet bytes.

No canonical-data conflict was found. The sole PyArrow `sysctlbyname` cache-detection warning in the sandbox is environmental and does not affect data or QA. A repository static type checker is not configured; syntax compilation is included in verification and no new dependency was introduced.

## Artifacts

Generated research data remains outside Git:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_a_raw_4h_pivots/`

The directory contains the authoritative Parquet, schema, JSON report, manifest, SHA256 file, progress state, and five SVG QA charts. Outliers, null counts, year counts, distributions, and several real five-event sequences are recorded in `stage2i_a_report.json` without good/bad classification.
