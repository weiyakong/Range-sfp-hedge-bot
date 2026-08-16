# Research Data Layout and Extraction Contract

## Purpose

Keep the large research dataset queryable and reviewable without monolithic CSV duplication or hidden recomputation.

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
- macro trade touches
- macro boundary fragments
- macro legs/context
- retracement measurements
- feature dictionary/manifests.

Stable ids are authoritative join keys.

## Macro extraction

For macro anchor/leg extraction support simultaneous access to:
- source anchor time/price/provenance/precision
- source possible-time interval
- all 5m candidates and localization status
- trade refinement status/touches
- exact pivot time + native sequence id when unique
- fallback uncertainty when not exact
- LEFT/RIGHT boundary fragments
- exact/fallback macro feature rows.

Do not collapse historical `mixed` provenance into canonical market type.

## Retracement extraction

A/B/C are macro anchor ids in this pass. Preserve previous/next leg ids, relationship source id, direct percentages and boundary precision status.

No arbitrary A-B-C tuple is generated on demand.

## Causal extraction

Causal-only extraction excludes:
- macro anchors
- trade touches
- boundary fragments
- macro observations/legs/context
- retracement rows
- every retrospective feature.

Exact historical trade timing does not make macro rows causal.

## Parquet and pruning

Read canonical Parquet/manifests directly. Support filters by ids, time, market, source segment, timeframe, rolling duration, calculation resolution, observation kind, family/table and availability.

Use partition/column pruning. Small unpartitioned macro dimension tables may be scanned directly.

## Human review

CSV is targeted review/exchange output, not a wholesale duplicate of canonical Parquet. Keep small review outputs near 10 MB; split larger exports deterministically with manifest.

## No hidden recomputation

Extraction returns materialized canonical values by default. Missing features/relationships do not trigger undocumented recalculation.

Resume/checkpoint logic cannot duplicate finalized stable rows.
