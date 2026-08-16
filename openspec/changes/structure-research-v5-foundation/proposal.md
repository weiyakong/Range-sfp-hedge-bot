# Proposal: Structure Research v5 Foundation

## Summary

Build a reproducible first-pass BTC market-structure research dataset that preserves objective multi-timeframe measurements without prematurely classifying market behavior as impulse, correction, range, breakout, chop, parent impulse, Elliott wave, or Fibonacci structure.

The dataset will preserve canonical candle data, candle geometry, path geometry, overlap/penetration behavior, speed evolution, volume/volatility behavior, cross-timeframe relationships, approved retracement measurements, and audited macro-leg context so later research can study structural hierarchy/regime behavior without repeatedly recollecting market data.

## Why this change

Previous research exposed several failure modes:

- source provenance and spot/futures continuity can be misinterpreted;
- missing/native-absent candles can be hidden by synthetic rows;
- fixed and rolling intervals can be conflated;
- formulas and field names can diverge between specs/schema;
- retrospective macro information can leak into causal features;
- macro anchors can have mixed historical source provenance and coarse timestamp precision;
- long calculations can report success without semantic validation;
- resume/checkpoint behavior can exist nominally without output equivalence;
- monolithic outputs are hard to inspect and extract safely.

This change replaces those assumptions with explicit source, time, formula, schema, storage, causality, and QA contracts.

## Goals

The first production research dataset SHALL:

1. retain full approved BTC history rather than imposing a modern-era collection cutoff;
2. preserve a strict observed canonical 1m market-data spine;
3. derive canonical `5m`, `15m`, `1H`, `4H`, `1D` UTC intervals from canonical 1m;
4. keep spot and USDT-M futures provenance/continuity explicit;
5. preserve true source gaps rather than filling them with unobserved synthetic candles;
6. materialize objective candle geometry at target resolutions;
7. measure price/log movement, speed, path, efficiency, directional path, alternation, extrema, excursions, overlap, penetration, extension, volume, TR/ATR and fixed/rolling RV;
8. measure approved rolling windows `30m`, `1h`, `4h`, `12h`, `24h`, `3d` incrementally;
9. retain approved `macro_legs_log20.csv` as retrospective research containers while preserving their actual historical mixed-source provenance and anchor precision;
10. materialize direct retracement measurements only for explicitly approved A-B-C relationships;
11. maintain causal and retrospective layers separately;
12. store canonical analytical outputs as partitioned Parquet with deterministic targeted CSV extraction;
13. checkpoint long stages so no more than 20 minutes of validated work is at risk;
14. gate smoke/full-history execution behind deterministic golden tests and independent persisted-artifact QA.

## Research objective

The immediate objective is descriptive rather than classificatory.

The dataset must support comparisons of movements with similar log-scale price distance but materially different elapsed time, internal path, overlap, volatility, volume and directional efficiency.

Later research may use these data to study:

- impulse-versus-correction signatures;
- movement hierarchy and parent relationships;
- local impulses inside larger opposing/corrective environments;
- slowdown, renewed continuation and false slowdown;
- RangeBot regime gating and exits;
- later structural/Elliott scenario ranking using objective structure plus a separate interpretation layer.

Those classifications are outside the first-pass production pipeline.

## Scope

### In scope

- approved Binance BTCUSDT spot/futures history under finalized source contract;
- strict canonical 1m layer;
- deterministic fixed target interval grid;
- atomic target candle geometry;
- fixed and rolling observations;
- audited macro-leg observations/context;
- explicitly approved retracement tuples;
- objective price/path/overlap/volume/volatility feature families;
- cross-timeframe containment;
- stable identifiers/table contracts;
- Parquet/manifests/extraction/checkpoints/resume;
- deterministic golden tests, bounded real-data smoke, production QA.

### Explicitly deferred

- new swing/internal-leg discovery algorithm;
- new validated parent-impulse construction;
- impulse/correction labels or thresholds;
- final range-boundary algorithm;
- breakout classification/outcome labels;
- composite choppiness score;
- Fibonacci price features;
- FibTime features;
- Elliott-wave labels/ranking;
- full-history tick-level path reconstruction;
- order-book/funding/open-interest/liquidation or other unapproved microstructure sources;
- macro realized-volatility family unless separately specified later.

## Finalized canonical source contract

Accepted source facts:

- first actual Binance BTCUSDT USDT-M futures trade: `2019-09-08T17:57:50.575000Z`;
- first futures 1m bucket and canonical candle-based spot→futures boundary: `2019-09-08T17:57:00Z`;
- spot rows after this cutoff are raw provenance only, not canonical combined chronology;
- native early futures `fapi/v1/klines` produced `163082` rows through `2019-12-30T23:59:00Z` and omitted native `2019-09-08T19:00:00Z`;
- official trades show zero trades in that minute and the previously inserted flat `10000` row is a deterministic synthetic no-trade bucket, not a native/observed candle;
- strict canonical data therefore keeps `2019-09-08T19:00:00Z` as an unresolved one-minute futures source gap and excludes the synthetic row;
- the remaining early native futures history joins to public archive at `2019-12-31T00:00:00Z`; provenance change alone does not create a segment;
- full raw spot inventory has `6235` missing minutes; cutoff audit reports `5972` canonical-relevant minutes across `16` intervals and excludes `263` post-boundary minutes;
- production must recompute canonical spot gaps from minute-aligned canonical rows because some audit interval timestamps are not minute aligned;
- legacy futures 1D/4H caches are diagnostic references, not canonical/critical truth where inconsistency is known.

## Audited macro-source contract

The approved macro source checksum remains:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

Its historical source construction differs from the new canonical chronology:

- old merged daily source remains spot through `2019-12-30`;
- old daily source switches to futures `2019-12-31`;
- macro refinement used futures 4H rows from September 2019;
- audited late-2019 macro anchors are therefore capable of `mixed` provenance (`spot daily + futures 4H refinement`).

Current canonical market assignment SHALL NOT overwrite this historical macro provenance.

A 4H-refined source anchor timestamp identifies the 4H bucket used for refinement, not necessarily the exact intrabar time of the source high/low. Source macro displacement remains preserved, but canonical anchor-inclusive path/efficiency is gated by market compatibility and anchor-time precision.

## Storage/data model

Canonical logical data include:

- source segments;
- source gaps;
- canonical 1m candles;
- fixed target interval/candle table;
- atomic target `candle_geometry`;
- target-to-target cross-timeframe map;
- observation index;
- price/speed;
- path/activity/extrema;
- atomic pair geometry;
- overlap summaries;
- volume/volatility;
- macro legs and retrospective macro context;
- explicitly approved retracement measurements;
- feature dictionary.

Large canonical outputs use partitioned Parquet. Human-review outputs are targeted CSV extracts rather than wholesale duplicated CSV tables.

## Validation strategy

Implementation is test-first and gate-based.

Golden/production QA covers:

- OHLCV resampling and incomplete propagation;
- strict source-boundary isolation;
- fixed-versus-rolling semantics;
- deterministic containment/ids;
- speed/path/RV/alternation/extrema;
- overlap/body overlap/penetration/extensions;
- dual volume direction;
- TR/ATR;
- direct retracement formula;
- macro internal versus anchor-inclusive path;
- causality/future-data invariance;
- schema/referential integrity;
- extraction/resume/manifests;
- trusted-versus-diagnostic higher-TF QA;
- cross-market boundary interval representation;
- synthetic 19:00 exclusion and gap propagation;
- historical mixed macro provenance;
- anchor-time precision gating;
- canonical spot-gap minute-grid alignment;
- target candle geometry materialization;
- exact fixed/rolling/macro calculation matrices;
- canonical feature-name regression.

QA status is mechanically derived; a failed critical assertion cannot be overwritten by a successful process exit.

## Success criteria

The change is ready for implementation when all specs, schema, proposal/design/tasks and QA contracts are internally consistent.

Implementation is ready for a full-history production decision only after:

- complete golden suite passes;
- bounded real-data smoke passes independent persisted-artifact QA;
- no unresolved critical failures remain.

Full-history execution remains a separate explicit authorization gate.
