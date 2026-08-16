# Research Output Persistence Specification

## Purpose

Define how long-running Structure Research v5 calculations preserve recoverable progress, retain canonical analytical data efficiently, and produce human-reviewable extracts.

## ADDED Requirements

### Requirement: Recoverable progress within 20 minutes

The system SHALL persist recoverable progress during long-running calculations so that no more than 20 minutes of completed work is at risk between successful persistence points.

A completed validated stage SHALL be persisted immediately even when less than 20 minutes have elapsed since the previous persistence point.

### Requirement: Canonical analytical storage is Parquet

Full-resolution canonical market data, atomic pair records, large feature tables, cross-timeframe mappings, whole-leg analytical tables, and other large canonical research datasets SHALL be retained as Parquet.

This includes the retained canonical `1m` OHLCV/provenance layer and the complete target-resolution candle/feature tables.

Canonical Parquet storage SHALL preserve schema/version, stable join keys, provenance, temporal coverage, and partition metadata needed for deterministic reconstruction.

A different canonical analytical format SHALL NOT be substituted without explicit user approval and an OpenSpec update.

### Requirement: Human-review outputs are targeted CSV extracts rather than full-dataset duplication

The system SHALL NOT duplicate every large canonical Parquet analytical table as a complete CSV solely for compliance.

CSV SHALL be used for human-reviewable summaries and targeted extraction outputs intended for upload, manual inspection, or compact downstream exchange.

A deterministic extraction utility SHALL read the canonical Parquet store directly and export selected rows/columns/time ranges/feature families to CSV.

### Requirement: Keep small review tables as one CSV

A human-review logical table or extraction SHALL remain a single CSV file when its complete export is approximately 10 MB or smaller.

### Requirement: Partition oversized review CSV outputs

When a requested human-review CSV logical table materially exceeds approximately 10 MB, the system SHALL export multiple ordered CSV parts with identical schema and a manifest rather than one oversized file.

### Requirement: Partitioned analytical tables remain reconstructable

For partitioned canonical Parquet or review CSV tables, manifests SHALL identify logical table name, part filenames/paths, row counts, temporal coverage, schema/version, source segment where applicable, and sufficient metadata to reconstruct the logical table deterministically.

### Requirement: Resume state does not redefine canonical output

Checkpoint, cache, and resume artifacts MAY use Parquet or another repository-approved internal format but SHALL remain distinguishable from validated canonical Parquet analytical outputs.

A resumed run SHALL validate input/configuration identity and SHALL NOT duplicate already finalized canonical rows.
