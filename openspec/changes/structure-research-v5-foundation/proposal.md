# Proposal: Structure Research v5 Foundation

## Summary

Build a reproducible first-pass BTC market-structure research dataset that preserves objective multi-timeframe measurements without prematurely classifying market behavior as impulse, correction, range, breakout, chop, parent impulse, Elliott wave, or Fibonacci structure.

The dataset will preserve enough canonical candle data, path geometry, overlap/penetration behavior, speed evolution, volume/volatility behavior, cross-timeframe relationships, and approved macro-leg context to support later quantitative research into structural hierarchy and regime behavior without repeatedly recollecting market data.

## Why this change

Previous structure-research work exposed several failure modes that make a new foundation necessary:

- source provenance and spot/futures continuity can be misinterpreted;
- missing source candles can silently contaminate path and rolling calculations;
- fixed and rolling intervals can be conflated;
- formulas can remain underspecified and be implemented inconsistently;
- retrospective macro information can leak into causal/live-style features;
- long calculations can report success without independent semantic validation;
- resume/checkpoint functionality can exist nominally without proving equivalent output;
- large monolithic outputs are difficult to inspect, reproduce, and extract safely.

This change replaces those implicit assumptions with explicit source, time, formula, schema, storage, causality, and QA contracts.

## Goals

The first production research dataset SHALL:

1. retain the full approved BTC source history rather than limiting collection to the modern era;
2. preserve canonical 1m market data as the finest reproducible candle layer;
3. derive canonical `5m`, `15m`, `1H`, `4H`, and `1D` candles deterministically from canonical 1m;
4. keep spot and USDT-M futures provenance and continuity explicitly separate;
5. preserve real source gaps rather than interpolating or fabricating candles;
6. measure objective price geometry, ordinary/log returns, speed, path, path efficiency, directional path, alternation, extrema, excursions, candle geometry, overlap, penetration, extension, volatility, and volume;
7. measure approved rolling windows `30m`, `1h`, `4h`, `12h`, `24h`, and `3d` incrementally;
8. retain the approved `macro_legs_log20.csv` observations as retrospective research containers without promoting them to validated hierarchy truth;
9. maintain causal and retrospective data as separately identifiable and extractable layers;
10. store large canonical analytical outputs as partitioned Parquet and provide deterministic targeted CSV extraction;
11. checkpoint long-running stages so no more than 20 minutes of validated completed work is at risk;
12. gate smoke/full-history execution behind deterministic golden tests and independent QA.

## Research objective

The immediate research objective is descriptive rather than classificatory.

The dataset must support later comparison of movements that cover similar log-scale distance but differ materially in elapsed time and internal path, including cases where one movement is fast/efficient and another is slow, overlapping, alternating, or highly counter-directional.

The resulting data should support later research into:

- quantitative impulse-versus-correction signatures;
- movement hierarchy and parent relationships;
- local impulses inside larger opposing/corrective environments;
- slowdown, renewed continuation, and false slowdown;
- RangeBot regime gating and exit logic;
- later structural/Elliott scenario work using objective structure plus separate interpretation layers.

Those later classifications are explicitly outside this first-pass production pipeline.

## Scope

### In scope

- approved BTCUSDT Binance spot and Binance USDT-M futures candle history under the finalized source contract;
- canonical retained 1m layer;
- deterministic 1m-to-target resampling;
- fixed and rolling observations;
- approved macro-leg observations;
- objective price/path/overlap/volume/volatility feature families;
- cross-timeframe containment;
- stable identifiers and table contracts;
- Parquet storage, manifests, extraction, checkpoints/resume;
- deterministic golden tests, real-data smoke validation, and production QA.

### Explicitly deferred

- new swing/internal-leg discovery algorithm;
- new validated parent-impulse construction;
- impulse/correction labels or thresholds;
- final range-boundary algorithm;
- breakout classification/outcome labels;
- composite choppiness score;
- Fibonacci price features;
- FibTime features;
- Elliott-wave labels or ranking;
- full-history tick-level path reconstruction;
- order-book, funding, open-interest, liquidation, or other microstructure data not already approved.

## Finalized source contract

The source chronology is finalized from direct official-source evidence rather than inferred bucket or archive start dates.

Accepted facts:

- the first actual Binance BTCUSDT USDT-M futures trade is `2019-09-08T17:57:50.575000Z`, established from official Binance USD-M daily-trades data;
- the first real futures 1m bucket begins at `2019-09-08T17:57:00Z`;
- `2019-09-08T17:57:00Z` is therefore the canonical candle-based spot-to-futures boundary;
- the fresh official early-futures 1m block covers `2019-09-08T17:57:00Z` through `2019-12-30T23:59:00Z`;
- native `fapi/v1/klines` supplied `163082` rows with one missing native bucket at `2019-09-08T19:00:00Z`;
- that one minute was deterministically resolved from official daily-trades no-trade evidence under the approved recovery rule;
- the final combined early-futures block contains `163083` rows, zero duplicates, and zero remaining gaps;
- the early block joins continuously to the public futures archive at `2019-12-31T00:00:00Z`;
- legacy local futures 1D/4H caches are QA/reference evidence only and do not override the fresh canonical 1m pull because a materially inconsistent area was found near `2019-09-24`;
- historical Binance spot 1m contains `6,235` minutes that remained unrecoverable after official spot aggTrades recovery attempts (`0/6235` recovered); these remain explicit source gaps.

The exact chronology and evidence artifacts are defined once in the dedicated source-contract specification. Feature code and tests SHALL consume that contract/configuration rather than maintain separate market-boundary constants.

## Storage and data model

Large canonical research data will be stored as Parquet with explicit manifests and stable identifiers.

The logical data model separates:

- source segments and source gaps;
- canonical 1m candles;
- canonical fixed target candles;
- cross-timeframe containment;
- fixed/rolling/macro observation identity;
- price/speed features;
- path/activity/extrema features;
- atomic candle-pair geometry;
- observation overlap summaries;
- observation volume/volatility summaries;
- retrospective macro context;
- source macro legs;
- feature dictionary.

Human-review outputs will be targeted CSV extracts rather than full duplicated CSV copies of large Parquet tables.

## Validation strategy

Implementation is test-first and gate-based.

The change defines deterministic synthetic golden fixtures for:

- OHLCV resampling;
- gap propagation;
- source-boundary isolation;
- fixed-versus-rolling semantics;
- rolling speed/change;
- path and realized volatility;
- alternation;
- extrema/excursions;
- overlap/body overlap/penetration/extensions;
- dual volume-direction semantics;
- TR/ATR;
- retracement;
- macro anchor-inclusive path;
- stable identifiers;
- causality/future-data invariance;
- schema/referential integrity;
- extraction;
- resume equivalence;
- native higher-timeframe QA.

Smoke and full-history production are blocked until critical golden tests pass.

## Success criteria

This change is ready for implementation when:

- the finalized source contract is present and internally consistent;
- all specifications are internally consistent;
- `proposal.md`, `design.md`, and `tasks.md` are complete;
- golden-test requirements are defined before implementation;
- no first-pass semantic labels or retrospective leakage are permitted by the contracts.

Implementation is ready for a full-history production decision only after:

- golden tests are implemented and pass;
- a bounded real-data smoke run passes independent QA;
- no unresolved critical failures remain.

A full-history run is a separate execution decision after smoke review; completing implementation does not itself authorize an expensive production run.
