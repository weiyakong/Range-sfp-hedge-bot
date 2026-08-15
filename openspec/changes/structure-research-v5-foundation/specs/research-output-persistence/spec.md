# Research Output Persistence Specification

## Purpose

Define how long-running Structure Research v5 calculations preserve recoverable progress and how final research outputs are exported for human review and downstream analysis.

## ADDED Requirements

### Requirement: Recoverable progress within 20 minutes

The system SHALL persist recoverable progress during long-running calculations so that no more than 20 minutes of completed work is at risk between successful persistence points.

#### Scenario: Long-running calculation continues beyond 20 minutes

* **GIVEN** a research calculation is still running
* **WHEN** 20 minutes have elapsed since the last successful recoverable persistence point
* **THEN** the system SHALL persist a new recoverable state no later than that point
* **AND** the saved state SHALL be sufficient for resume without recomputing all previously completed work.

#### Scenario: Stage completes before 20 minutes

* **GIVEN** a processing stage completes less than 20 minutes after the previous persistence point
* **WHEN** the stage has completed and its required validation has passed
* **THEN** the system SHALL persist the completed stage immediately rather than waiting for the 20-minute interval.

### Requirement: Internal storage may use Parquet

The system MAY use Parquet or another repository-approved internal format for intermediate processing, caches, checkpoints, or resume state when this improves reliability or efficiency.

#### Scenario: Internal Parquet is used

* **WHEN** an internal Parquet artifact is created for processing, cache, checkpoint, or resume purposes
* **THEN** it SHALL be treated as an internal artifact
* **AND** it SHALL NOT replace the required final CSV research output.

### Requirement: Final research outputs are CSV

All final research datasets intended for human review, upload, inspection, or downstream research analysis SHALL be exported as CSV.

#### Scenario: Research topic completes successfully

* **GIVEN** a logical research topic has completed successfully
* **WHEN** its final reviewable output is produced
* **THEN** the system SHALL export that output as CSV
* **AND** internal Parquet files SHALL NOT be considered a substitute for the CSV export.

### Requirement: Separate logical tables by research topic

Each semantic research topic SHALL be exported as its own logical table rather than combining unrelated research topics into one oversized output table.

#### Scenario: Multiple research topics are produced

* **GIVEN** a run produces data for multiple semantic topics
* **WHEN** final outputs are exported
* **THEN** each topic SHALL have its own logical CSV table or CSV partition set
* **AND** unrelated topics SHALL NOT be combined merely to reduce the number of files.

### Requirement: Keep small logical tables as one CSV

A logical research table SHALL remain a single CSV file when its complete final export is approximately 10 MB or smaller.

#### Scenario: Complete table fits within target size

* **GIVEN** the complete final CSV for a logical research topic is approximately 10 MB or smaller
* **WHEN** the topic is exported
* **THEN** the system SHALL write one complete CSV file for that topic
* **AND** SHALL NOT partition it unnecessarily.

### Requirement: Partition oversized CSV outputs

When a logical research table would materially exceed the approximately 10 MB target size, the system SHALL export it as multiple ordered CSV parts with the same schema instead of creating a very large final CSV.

#### Scenario: Logical table exceeds target size

* **GIVEN** a logical research table would materially exceed approximately 10 MB as one final CSV
* **WHEN** it is exported
* **THEN** the writer SHALL split the table into multiple CSV parts during export
* **AND** every part SHALL use the same columns and schema
* **AND** rows SHALL not be lost or duplicated because of partitioning
* **AND** the parts SHALL use deterministic ordered names such as `part_001`, `part_002`, and so on.

### Requirement: Partitioned tables remain one logical table

A partitioned CSV output SHALL remain straightforward to reconstruct and query as one logical table.

#### Scenario: A topic is exported in multiple CSV parts

* **GIVEN** a logical table has been partitioned into multiple CSV files
* **WHEN** final output is produced
* **THEN** the system SHALL produce a manifest describing the parts
* **AND** the manifest SHALL identify the logical topic, part filenames, row counts, and coverage needed to reconstruct the table
* **AND** the repository SHALL provide a deterministic way to read all parts as one logical table for terminal-based inspection and downstream analysis.
