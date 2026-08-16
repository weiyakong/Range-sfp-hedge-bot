# Research Data Layout and Extraction Contract

## Purpose

Keep the large research dataset queryable and reviewable without monolithic CSV duplication, hidden recomputation, or accidental large-source rescans.

## Canonical logical families

Separately queryable at minimum:
- source segments/gaps
- canonical 1m/fixed candles
- candle geometry
- cross-timeframe map
- observation index
- price/speed
- path/activity
- atomic canonical pairs
- overlap summaries
- volume/volatility
- macro anchors
- macro aggTrade evidence
- macro boundary fragments
- macro legs/context
- retracement measurements
- feature dictionary/manifests.

Stable ids are authoritative join keys.

## Macro extraction

For macro anchor/leg extraction support simultaneous access to:
- source anchor time/price/provenance/precision
- source possible-time interval
- all localization candidates and status
- refinement status and method
- all exact source-price aggTrade touches
- selected directional-extremum evidence when no exact touch exists
- refined realized pivot price
- resolved pivot time + native sequence id when deterministic
- unresolved-time evidence when selected extremum repeats or source coverage is insufficient
- canonical 5m containment when resolved time exists
- LEFT/RIGHT boundary fragments
- refined/fallback macro feature rows.

Do not use the obsolete criterion “unique exact touch only”. Multiple exact touches resolve to the earliest exact touch under the approved rule.

Do not collapse historical `mixed` provenance into canonical market type.

## Retracement extraction

A/B/C are macro anchor ids in this pass. Preserve previous/next leg ids, relationship source id, direct percentages and boundary precision/refinement status. No arbitrary A-B-C tuple is generated on demand.

## Causal extraction

Causal-only extraction excludes macro anchors, aggTrade evidence, boundary fragments, macro observations/legs/context, retracement rows and every retrospective feature. Refined historical aggTrade timing does not make macro rows causal.

## Parquet and pruning

Read canonical Parquet/manifests directly. Support filters by ids, time, market, source segment, timeframe, rolling duration, calculation resolution, observation kind, family/table and availability.

Use partition/column pruning. Small unpartitioned macro dimension tables may be scanned directly.

For approved aggTrade source archives used during refinement/fragment construction, helpers SHALL use bounded streaming/range-filtered reads for the requested candidate window or canonical 5m bucket. They SHALL NOT repeatedly materialize whole daily/monthly archives in per-anchor/per-fragment loops. Reusable bucket/window results should be cached within a pass where practical.

ZIP/CSV archive access in the hot path SHALL use a robust streaming parser/filter. A pandas full-file read/parser is not permitted as the fragment-stage per-bucket access method. Parser errors are explicit failures/coverage limitations and do not authorize raw individual-trade fallback.

## Human review

CSV is targeted review/exchange output, not a wholesale duplicate of canonical Parquet. Keep small review outputs near 10 MB; split larger exports deterministically with manifest.

## No hidden recomputation

Extraction returns materialized canonical values by default. Missing features/relationships do not trigger undocumented recalculation. Resume/checkpoint logic cannot duplicate finalized stable rows.
