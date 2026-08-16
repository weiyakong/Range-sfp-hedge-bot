# Research Data Layout and Extraction Contract

## Purpose

Keep a very large multi-timeframe research dataset queryable and human-reviewable without forcing all information into one monolithic table or requiring repeated full-market recomputation.

## ADDED Requirements

### Requirement: Research data follows the canonical table schema

The analytical store SHALL implement the logical tables, row grain, stable identifiers, keys, availability classes, and partitioning defined by the approved `research-table-schema` specification.

Implementation SHALL NOT collapse those logical families into one monolithic wide table or invent incompatible alternative primary keys without explicit approval and an OpenSpec update.

### Requirement: Stable join keys are authoritative

Canonical entities SHALL be joined by the stable identifiers defined in `research-table-schema`, including `candle_id`, `observation_id`, `pair_id`, `macro_leg_id`, and `source_segment_id` where applicable.

Row order, physical file order, or local path SHALL NOT be used as a semantic join key.

### Requirement: Raw candle and cross-timeframe relationships remain queryable

The canonical analytical store SHALL preserve queryable candle-level records for retained `1m` source data and target resolutions.

Direct 1m constituent membership of a fixed target candle SHALL be deterministically reconstructable from canonical time intervals and source continuity and SHALL NOT require an exploded 1m-to-parent mapping table.

The persisted `cross_timeframe_map` SHALL preserve target-to-target containment and ordinal relationships according to the canonical table-schema contract.

### Requirement: Feature families remain separate logical tables

Price/speed, path/activity, atomic candle-pair geometry, overlap summaries, volume/volatility, cross-timeframe mapping, macro-leg context, and approved source/dimension tables SHALL remain separately queryable logical tables according to the canonical table schema.

This separation SHALL allow one feature family to be inspected, validated, recomputed, or extracted without rewriting unrelated families.

### Requirement: Macro-leg context is isolated from causal feature data

Approved `macro_legs_log20.csv` anchors and whole-leg observations SHALL remain explicitly retrospective where endpoint-dependent.

Fixed/rolling causal features SHALL remain queryable without joining retrospective macro context.

`observation_macro_context` SHALL be the explicit relationship layer for retrospective alignment to macro legs; it SHALL NOT be silently merged into causal tables.

### Requirement: Completed macro-leg temporal position is retrospective

For completed macro legs, retrospective temporal coordinates MAY include:

- elapsed time from leg start;
- remaining time to known leg end;
- `leg_time_progress = (t - leg_start_time) / (leg_end_time - leg_start_time)` when the denominator is positive.

Such fields SHALL be stored only in retrospective macro context and SHALL NOT be exposed as live-known features.

### Requirement: Extraction utility reads canonical Parquet directly

The repository SHALL provide a deterministic extraction utility that reads the canonical Parquet store and its manifests/catalog directly.

It SHALL NOT require conversion of the full dataset to CSV or manual concatenation of all physical parts before filtering.

The utility SHALL support filtering by available dimensions including:

- exact stable identifiers such as `macro_leg_id`, `observation_id`, `candle_id`;
- UTC time range;
- market type;
- source segment;
- fixed timeframe;
- rolling duration;
- calculation resolution;
- observation kind;
- selected logical feature families/columns;
- causal versus retrospective availability.

Where retrospective macro-leg progress exists, the utility SHOULD support selection by normalized temporal position within completed legs.

### Requirement: Extraction uses partition and column pruning

The extraction utility SHALL use canonical Parquet partition predicates and column projection where possible so a request for a small interval/feature subset does not scan or deserialize unrelated years, market types, calculation resolutions, or columns.

The utility MAY join only the logical tables required by the requested extract.

### Requirement: Extraction does not silently recompute canonical features

By default, extraction SHALL return already-materialized canonical features and relationships.

If a requested value is intentionally computed on demand rather than materialized, the utility SHALL identify it as an on-demand derivation, use only formulas already approved in OpenSpec/feature dictionary, and SHALL NOT overwrite or masquerade as a canonical stored feature.

A missing canonical feature SHALL NOT trigger an undocumented alternative calculation.

### Requirement: Causal-only extraction is enforced

When a user/request asks for causal-only data, the extraction utility SHALL enforce the causal filtering rules in `research-table-schema`, including exclusion of retrospective macro-leg observations/context and retrospective feature columns.

If an `as_of_time` is supplied, rows/features with `available_at > as_of_time` SHALL be excluded.

### Requirement: Extracted human-review outputs are CSV

Human-review extraction results SHALL follow the CSV output rules in the persistence specification, including the approximate 10 MB target and deterministic partitioning when needed.

Large canonical Parquet tables SHALL NOT be duplicated wholesale as CSV merely to support review.

### Requirement: Manifests make logical tables reconstructable

For every partitioned canonical logical table, manifests/catalog metadata SHALL identify enough physical parts and schema/version information to reconstruct the logical table deterministically according to the table-schema contract.

The extraction utility SHALL use this deterministic catalog/manifest rather than guessing paths from directory names.

### Requirement: Resume cannot create duplicate research rows

Checkpoint/resume implementation SHALL validate input/configuration/schema identity and SHALL resume only from proven completed units of work.

A resumed run SHALL preserve canonical stable identifiers and natural uniqueness constraints and SHALL NOT duplicate already finalized research rows.

Corrupted, incompatible, or stale checkpoints SHALL fail explicitly rather than being silently accepted.
