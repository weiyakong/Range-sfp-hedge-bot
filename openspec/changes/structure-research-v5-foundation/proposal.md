# Proposal: Structure Research v5 Foundation

## Summary

Build a reproducible first-pass BTC market-structure research dataset that preserves objective multi-timeframe measurements without prematurely classifying market behavior as impulse, correction, range, breakout, chop, parent impulse, Elliott wave, or Fibonacci structure.

The dataset preserves strict canonical market data, candle geometry, path/overlap/speed/volume/volatility behavior, approved retracement relationships, and audited macro-leg context with honest anchor-time uncertainty.

## Why this change

Previous work exposed failure modes including source/gap misinterpretation, synthetic candle contamination, fixed/rolling conflation, formula/name divergence, retrospective leakage, nominal resume without equivalence, mixed macro-source provenance, and coarse macro anchor timestamps being treated as if they were exact extreme times.

A 4H anchor timestamp may only identify the 4H bucket containing a high/low. Assigning all 5m/15m movement from that bucket start to one macro leg can incorrectly include price action that occurred before the actual pivot or after the actual pivot.

Structure Research v5 therefore requires macro-anchor refinement against compatible canonical 1m data before macro-specific canonical path/activity membership is calculated.

## Goals

The first production dataset SHALL:

1. retain full approved BTC history;
2. preserve strict observed canonical 1m data;
3. derive canonical 5m/15m/1H/4H/1D intervals from 1m;
4. keep true source gaps and market transitions explicit;
5. exclude unobserved synthetic rows from strict canonical data;
6. materialize target candle geometry;
7. measure objective price/log movement, speed, path, efficiency, directional path, alternation, extrema, overlap/penetration, volume, TR/ATR and fixed/rolling RV;
8. measure rolling 30m/1h/4h/12h/24h/3d windows;
9. preserve approved macro source legs unchanged as retrospective research containers;
10. preserve historical macro provenance separately from current canonical market scope;
11. refine coarse macro anchors against compatible complete canonical 1m data before assigning safe macro interior membership;
12. preserve ambiguous boundary minutes/zones rather than arbitrarily assigning them to adjacent legs;
13. calculate macro canonical path/activity/overlap/volume only on the guaranteed safe interior when exact boundary timing remains unknown;
14. materialize complete anchor-inclusive macro path only when full boundary ordering/path is actually established;
15. materialize direct retracement only for explicitly approved A-B-C relationships;
16. keep causal and retrospective layers separate;
17. store canonical outputs as Parquet with deterministic extraction/manifests/checkpoints/resume;
18. gate smoke/full-history execution behind golden tests and independent persisted-artifact QA.

## Macro anchor refinement principle

For a coarse source anchor, first define the bucket in which the extreme could have occurred. Search compatible canonical 1m data inside that bucket for the exact source high/low price.

Outcomes remain explicit:

- unique 1m match;
- multiple 1m matches;
- no match;
- incomplete search coverage;
- source incompatibility.

A unique 1m match narrows timing to that minute, but the extremum may occur anywhere inside the minute. Therefore the matching 1m candle remains a boundary uncertainty interval shared by the adjacent legs.

If a pivot is localized to `[05:23,05:24)`, the previous leg's safe interior may end at 05:23 and the next leg's safe interior may begin at 05:24. The 05:23 minute remains stored and queryable but is not assigned wholesale to either safe interior.

If several 1m candles hit the same anchor price, the pipeline does not choose one arbitrarily. The uncertainty zone spans the candidate interval conservatively.

For start uncertainty `[S0,S1)` and end uncertainty `[E0,E1)`, macro safe interior is `[S1,E0)`.

## Canonical market scope versus historical macro provenance

These are separate facts.

Example: an October-2019 macro leg may have:

- canonical `market_type=usdt_m_futures` under the current v5 chronology;
- historical `leg_source_classification=mixed` because its old daily parent came from spot while refinement came from futures 4H.

`mixed` historical provenance SHALL NOT make canonical market type null or replace it.

## Macro availability

Macro legs/anchors/refinement are retrospective research entities, not live signals.

In the first-pass schema macro rows use `availability_class=retrospective` and `available_at=null`. Source bucket timestamps remain source-coordinate metadata and do not pretend that the completed leg was known at that time.

## Scope

### In scope

- approved Binance BTCUSDT spot/futures history;
- strict canonical 1m;
- deterministic target interval grid;
- candle geometry;
- fixed/rolling observations;
- approved macro source legs;
- shared macro anchor/refinement records;
- safe-interior macro feature calculation;
- explicitly approved retracement tuples;
- objective price/path/overlap/volume/volatility features;
- cross-timeframe containment;
- Parquet/manifests/extraction/checkpoints/resume;
- deterministic golden tests and bounded smoke.

### Deferred

- new swing/internal-leg discovery;
- validated parent-impulse construction;
- impulse/correction thresholds/labels;
- final range-boundary/breakout labels;
- composite choppiness score;
- Fibonacci/FibTime;
- Elliott labels/ranking;
- full-history tick-level path reconstruction;
- unapproved microstructure sources;
- macro realized volatility unless separately specified;
- exact intra-minute pivot time unless future approved finer source evidence supports it.

## Finalized canonical source facts

- first actual futures trade `2019-09-08T17:57:50.575000Z`;
- canonical futures 1m boundary `2019-09-08T17:57:00Z`;
- post-boundary spot excluded from combined canonical chronology;
- native early futures omitted 19:00 and the prior flat repair is synthetic diagnostic evidence, so strict canonical data keeps a one-minute gap;
- raw spot gap inventory 6235; cutoff audit expectation 5972 canonical-relevant minutes / 16 intervals, subject to strict minute-grid recomputation;
- legacy inconsistent higher-TF caches are diagnostic where trust is not established.

## Audited macro source facts

Approved macro checksum:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

Old daily source stayed spot through 2019-12-30 and switched to futures 2019-12-31, while futures4H refinement was used from September. Late-2019 macro provenance may therefore be mixed.

## Validation strategy

Golden/production QA now covers G01-G40 including canonical source/gap behavior, geometry, formulas, extraction/resume, macro historical provenance, 1m anchor refinement, multiple/no/incomplete matches, boundary-minute exclusion, safe-interior membership, canonical market/provenance separation and retrospective availability.

QA status is mechanically derived and cannot be overwritten by process success.

## Success criteria

The change is ready for implementation only when all specs/schema/proposal/design/tasks are internally consistent.

Implementation is ready for a full-history decision only after G01-G40 pass, bounded real-data smoke passes independent QA, and no unresolved critical failures remain.

Full-history execution remains a separate explicit authorization gate.
