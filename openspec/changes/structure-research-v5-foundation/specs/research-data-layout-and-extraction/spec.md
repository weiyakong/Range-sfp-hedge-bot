# Research Data Layout and Extraction Contract

## Purpose

Keep a very large multi-timeframe research dataset queryable and human-reviewable without forcing all information into one monolithic table or requiring repeated full-market recomputation.

## ADDED Requirements

### Requirement: Research data uses stable join keys

Final and internal research tables SHALL use stable identifiers and timestamps sufficient to join macro legs, source segments, candles, cross-timeframe containment, feature families, and retrospective context without relying on row order.

### Requirement: Raw candle and cross-timeframe relationships remain queryable

The canonical analytical store SHALL preserve queryable candle-level records for retained `1m` source data and target resolutions, plus deterministic cross-timeframe mappings sufficient to reconstruct which finer candles formed each larger fixed calendar candle.

The mapping SHALL preserve ordinal position, expected constituent count, observed constituent count, coverage status, and source-segment identity where applicable.

### Requirement: Feature families remain separate logical tables

Momentum/speed, path/overlap/candle geometry, volume/volatility, cross-timeframe mapping, macro-leg context, and other approved semantic families SHALL remain separately queryable logical tables rather than one monolithic wide table.

Physical analytical storage is governed by the research-output persistence specification.

### Requirement: Macro-leg context is descriptive and retrospective where endpoint-dependent

The macro-leg context table SHALL preserve approved `macro_legs_log20.csv` anchors and source metadata, including start/end time and price, price-derived direction, duration, and movement size.

It SHALL NOT assign a new `impulse` or `correction` class in the first-pass research output.

Fields that require the completed macro-leg endpoint or whole-leg direction SHALL be explicitly marked retrospective.

### Requirement: Completed macro-leg position is retrospective

For completed macro legs, the system MAY export retrospective temporal coordinates such as elapsed time from leg start, remaining time to known leg end, and normalized temporal position:

`leg_time_progress = (t - leg_start_time) / (leg_end_time - leg_start_time)`

when the denominator is positive.

Such fields SHALL be marked retrospective because the final leg endpoint is not known to a live strategy before completion.

### Requirement: Extraction utility reads the canonical analytical store directly

The repository SHALL provide a deterministic extraction utility that reads the canonical Parquet/approved columnar analytical store directly and selects a small research slice without requiring conversion of the full dataset to CSV or manual concatenation of all parts.

The utility SHALL support filtering by available stable identifiers/time ranges, market type/source segment, one or more target/calculation resolutions, selected feature families/columns, and causal versus retrospective fields where applicable.

Where retrospective macro-leg position exists, the utility SHOULD support selecting portions of completed legs by normalized temporal position.

### Requirement: Extracted human-review outputs are CSV

Human-review extraction results SHALL follow the CSV output rules in the persistence specification, including the approximate 10 MB target and deterministic partitioning when needed.

### Requirement: Manifests make logical tables reconstructable

For partitioned logical tables, manifests SHALL identify logical table name, part filenames/paths, row counts, temporal coverage, schema/version, source segment where applicable, and sufficient metadata to reconstruct the table deterministically.

### Requirement: Resume cannot create duplicate research rows

Checkpoint/resume implementation SHALL validate enough input/configuration identity to reject incompatible or stale state and SHALL resume from a proven completed unit of work without duplicating already committed research rows.

Corrupted or incompatible checkpoints SHALL fail explicitly rather than being silently accepted.
