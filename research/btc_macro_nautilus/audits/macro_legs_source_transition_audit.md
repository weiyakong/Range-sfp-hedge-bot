# Macro Legs Source Transition Audit

## Scope
This audit is read-only and covers the approved `macro_legs_log20.csv` whose SHA-256 matches `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

Approved file inspected:
- `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_legs_log20.csv`

## Old macro daily source boundary
Evidence from `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/continuous_spot_to_futures_regime_v6_20260717/merge_summary.json` and direct row matching against `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/continuous_spot_to_futures_regime_v6_20260717/BTCUSDT_SPOT_TO_FUTURES_1D_MERGED.parquet` establishes:
- old merged daily source = `spot` through `2019-12-30T00:00:00Z`
- old merged daily source = `futures` from `2019-12-31T00:00:00Z`
- transition seam = `2019-12-31T00:00:00Z`

## What the build script actually used
`/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/macro_structure_review_log20_fibtime_fixed_local.py` reads:
- daily input from `--daily-parquet` or default `BTCUSDT_UMFUT_1D.parquet`
- H4 input from `--h4-parquet` or default `BTCUSDT_UMFUT_4H.parquet`
- event refinement through `refine_day_extreme_with_meta(...)`
- chronological macro legs from `refined_timestamp_4h` and `refined_price_4h`

The build summary at `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/summary_log20_fibtime_fixed.json` shows:
- daily first = `2017-08-17T00:00:00+00:00`
- H4 first = `2019-09-08T16:00:00+00:00`

That means Sep-Dec 2019 legs can still inherit a `spot` parent day from the merged 1D file while their exact anchor timestamp/price is refined from the futures H4 file.

## Direct anchor evidence
For disputed anchors the refined values match exact rows in `/Users/yeshevika/Documents/Codex/2026-05-30/sfp-vah-val-poc-cvd-one/Новое начало/cache_futures_btcusdt/BTCUSDT_UMFUT_4H.parquet`:
- `2019-10-23T16:00:00Z` low = `7172.76`
- `2019-10-26T00:00:00Z` high = `10408.48`
- `2019-11-25T04:00:00Z` low = `6510.19`
- `2019-11-29T16:00:00Z` high = `7850.00`

At the same time, the parent daily rows for `2019-10-23`, `2019-10-26`, `2019-11-25`, and `2019-11-29` still belong to the old merged daily `spot` regime because all are before `2019-12-31T00:00:00Z`.

## Conclusion
`MACRO_ANCHORS_2019_09_TO_12_SOURCE = mixed`

Reason:
- parent daily regime in the old merged source remains `spot` until `2019-12-30`
- several exact macro anchor timestamps/prices in Oct-Nov 2019 are refined from futures `4H` rows starting `2019-09-08T16:00:00Z`
- therefore these late-2019 macro legs are not provably pure spot and not pure futures; they are `spot daily + futures 4H refinement`
