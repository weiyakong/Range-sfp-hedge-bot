# Research Data Layout and Extraction Contract

## Purpose

Keep a very large multi-timeframe research dataset queryable and human-reviewable without forcing all information into one monolithic table or requiring repeated full-market recomputation.

## ADDED Requirements

### Requirement: Research data uses stable join keys

Final and internal research tables SHALL use stable identifiers and timestamps sufficient to join macro legs, candles, cross-timeframe containment, feature families, and retrospective context without relying on row order.

### Requirement: Raw candle and cross-timeframe relationships remain queryable

The research outputs SHALL preserve or expose queryable candle-level records for target resolutions and a deterministic cross-timeframe mapping sufficient to reconstruct which finer candles formed each larger fixed calendar candle.

The mapping SHALL preserve ordinal position, expected constituent count, observed constituent count, and coverage status where applicable.

### Requirement: Feature families remain separate logical tables

Momentum/speed, path/overlap/candle geometry, volume/volatility, cross-timeframe mapping, macro-leg context, and other approved semantic families SHALL remain separately queryable logical tables rather than one monolithic wide table.

Physical CSV partitioning rules are governed by the research-output persistence specification.

### Requirement: Macro-leg context is descriptive

The macro-leg context table SHALL preserve approved existing macro-leg anchors and source metadata, including start/end time and price, price-derived direction, duration, and movement size.

It SHALL NOT assign a new `impulse` or `correction` class in the first-pass research output.

### Requirement: Completed macro-leg position is retrospective

For completed macro legs, the system MAY export retrospective temporal coordinates such as elapsed time from leg start, remaining time to known leg end, and normalized temporal position:

`leg_time_progress = (t - leg_start_time) / (leg_end_time - leg_start_time)`

when the denominator is positive.

Such fields SHALL be marked retrospective because the final leg endpoint is not known to a live strategy before completion.

### Requirement: Extraction utility supports targeted human-review slices

The repository SHALL provide a deterministic extraction utility that can select a small research slice from the stored dataset without requiring manual concatenation of all files.

The utility SHALL support filtering by available stable identifiers/time ranges, one or more target/calculation resolutions, selected feature families/columns, and causal versus retrospective fields where applicable.

Where retrospective macro-leg position exists, the utility SHOULD support selecting portions of completed legs by normalized temporal position.

### Requirement: Extracted outputs are CSV

Human-review extraction results SHALL follow the final CSV output rules, including the approximate 10 MB target and deterministic partitioning when needed.

### Requirement: Internal storage may remain optimized

The extraction contract SHALL NOT require internal analytical storage to be CSV. Internal Parquet or other approved formats MAY be used for efficient filtering and joins, provided required human-review exports are produced as CSV.

### Requirement: Manifests make logical tables reconstructable

For partitioned logical tables, manifests SHALL identify logical table name, part filenames, row counts, temporal coverage, schema/version, and sufficient metadata to reconstruct the table deterministically.

### Requirement: Resume cannot create duplicate research rows

Checkpoint/resume implementation SHALL validate enough input/configuration identity to reject incompatible or stale state and SHALL resume from a proven completed unit of work without duplicating already committed research rows.

Corrupted or incompatible checkpoints SHALL fail explicitly rather than being silently accepted.
