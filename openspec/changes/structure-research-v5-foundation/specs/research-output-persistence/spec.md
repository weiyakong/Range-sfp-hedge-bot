# Research Output Persistence Specification

## Purpose

Define how long-running Structure Research v5 calculations preserve recoverable progress, retain canonical analytical data efficiently, and produce human-reviewable extracts.

## Recoverable progress within 20 minutes

The system SHALL persist recoverable validated progress so that no more than 20 minutes of completed work is at risk between successful persistence points. A completed validated stage/unit SHALL be persisted immediately even when less than 20 minutes have elapsed.

Progress persistence does not excuse inefficient source access: a unit that repeatedly reparses oversized source archives instead of using bounded reads violates the source-access contract even if checkpoints are written on time.

## Bounded processing state

Checkpoint/resume units SHALL align with deterministic bounded work units where practical: source partition, candidate window, canonical bucket, anchor group, calculation partition or equivalent.

A resume implementation SHALL NOT require rereading/reparsing an entire day/month aggTrade archive merely to reconstruct one already-known candidate window or 5m fragment. Parsed bounded source results MAY be cached as restart-safe intermediate artifacts when this reduces repeated I/O, provided source checksum and requested interval are part of cache identity.

For long-running source collection/derivation, collected or derived data SHALL be written no later than every 20 minutes.

## Canonical analytical storage is Parquet

Full-resolution canonical market data, atomic pairs, large feature tables, cross-timeframe mappings and other large analytical datasets SHALL be retained as Parquet/Zstandard with schema/version, stable join keys, provenance, temporal coverage and partition metadata.

A different canonical analytical format SHALL NOT be substituted without explicit user approval and OpenSpec update.

## Human-review outputs

Do not wholesale-duplicate every large Parquet table as CSV. CSV is for targeted review/exchange extracts.

A deterministic extraction utility reads canonical Parquet directly and exports selected rows/columns/time ranges/feature families.

Keep a complete human-review logical table as one CSV when approximately 10 MB or smaller. If materially larger, split into ordered identical-schema CSV parts with manifest.

## Reconstructability

For partitioned Parquet or review CSV outputs, manifests identify logical table, part paths, row counts, temporal coverage, schema/version, source segment where applicable, and sufficient metadata for deterministic reconstruction.

## Resume state does not redefine canonical output

Checkpoint/cache artifacts remain distinguishable from validated canonical outputs. Resume validates input/config/schema/refinement/source checksums and SHALL NOT duplicate finalized canonical rows.
