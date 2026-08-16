# Research Data Layout and Extraction Contract

## Purpose

Keep a very large multi-timeframe research dataset queryable and human-reviewable without forcing all information into one monolithic table or requiring repeated full-market recomputation.

## ADDED Requirements

### Requirement: Research data follows the canonical table schema

The analytical store SHALL implement the logical tables, row grain, stable identifiers, keys, availability classes, macro-anchor records, and partitioning defined by `research-table-schema`.

Implementation SHALL NOT collapse those families into one monolithic wide table or invent incompatible alternative keys without explicit approval/OpenSpec change.

### Requirement: Stable join keys are authoritative

Canonical joins use stable ids including where applicable:

- `candle_id`
- `observation_id`
- `pair_id`
- `macro_leg_id`
- `macro_anchor_id`
- `source_segment_id`
- `retracement_id`.

Row order, physical file order, or local path is never a semantic join key.

### Requirement: Candle geometry and cross-timeframe relationships remain queryable

Canonical 1m/source candles and target candles remain queryable.

Atomic `candle_geometry` remains independently queryable by `candle_id`, timeframe, canonical market type and time range.

Direct 1m constituent membership of fixed target candles is reconstructable from canonical time/source continuity without an exploded 1m-to-parent map.

`cross_timeframe_map` preserves target-to-target containment and ordinal relationships.

### Requirement: Feature families remain separate logical tables

At minimum separately queryable:

- source segments/gaps;
- canonical 1m/fixed candles;
- candle geometry;
- observation index;
- price/speed;
- path/activity;
- atomic candle pairs;
- overlap summaries;
- volume/volatility;
- macro anchors;
- macro legs and retrospective macro context;
- retracement measurements;
- cross-timeframe mapping;
- feature dictionary/manifests.

### Requirement: Macro historical provenance and canonical market scope remain separately extractable

Macro extraction SHALL allow the researcher to see at the same time:

- canonical `market_type` for the macro wall-clock interval;
- historical `leg_source_classification`;
- parent/refinement markets;
- anchor refinement status and candidate times;
- safe interior boundaries;
- ambiguous boundary intervals.

The extraction layer SHALL NOT collapse `mixed` historical provenance into canonical market scope.

### Requirement: Macro-anchor uncertainty and boundary candles are directly extractable

For a selected `macro_leg_id` or `macro_anchor_id`, extraction SHALL support returning:

- source anchor time/price/precision;
- initial/refined possible-time interval;
- 1m refinement status;
- candidate count and first/last candidate minute;
- `safe_interior_start_time/safe_interior_end_time`;
- canonical 1m/target candles overlapping the uncertainty interval;
- safe-interior feature rows.

Boundary-ambiguous candles remain visible even though they are excluded from safe macro metrics.

### Requirement: Completed macro temporal position is retrospective source-coordinate information

Source start/end timestamps and source-coordinate progress MAY be extracted for completed macro legs, but SHALL be explicitly described as retrospective source coordinates when anchor timing is bucket-limited.

They SHALL NOT be exposed as live-known exact extreme timing.

### Requirement: Extraction utility reads canonical Parquet directly

The repository SHALL provide deterministic extraction from canonical Parquet/manifests without converting the full dataset to CSV first.

Supported filters include where applicable:

- `candle_id`
- `observation_id`
- `pair_id`
- `macro_leg_id`
- `macro_anchor_id`
- `retracement_id`
- retracement `relationship_source_id`
- UTC time range
- canonical `market_type`
- source segment
- fixed timeframe
- rolling duration
- calculation resolution
- observation kind
- feature family/table/columns
- availability class.

### Requirement: Extraction uses partition and column pruning

Use canonical partition predicates and column projection where possible. A small request SHALL NOT scan unrelated years/market types/resolutions/columns when the physical layout permits pruning.

Small unpartitioned dimension/retracement/macro-anchor tables may be scanned directly when appropriate.

### Requirement: Extraction does not silently recompute canonical features or relationships

By default extraction returns materialized canonical values.

A missing feature does not trigger undocumented recalculation.

A missing retracement A-B-C tuple SHALL NOT be generated on demand merely because component anchors exist.

### Requirement: Causal-only extraction is enforced

Causal-only extraction excludes:

- macro observations;
- `macro_anchors`;
- `macro_legs` endpoint-dependent retrospective fields;
- `observation_macro_context`;
- retrospective retracement rows;
- every feature whose dictionary availability is retrospective.

For causal rows with non-null `available_at`, an `as_of_time` filter requires `available_at <= as_of_time`.

`available_at=null` on a retrospective entity SHALL NOT make it causal.

### Requirement: Retracement extraction preserves tuple provenance

When `retracement_measurements` is populated, extraction preserves relationship source, A/B/C ids, prices/times, anchor precision/provenance, availability and metric status.

### Requirement: Human-review outputs are targeted CSV extracts

Human-review extracts follow the persistence CSV rules, including approximate 10 MB target and deterministic splitting/manifest when needed.

Large canonical Parquet tables are not wholesale duplicated as CSV solely for review.

### Requirement: Manifests make every logical table reconstructable

Partitioned and unpartitioned canonical tables SHALL be discoverable through deterministic manifests/catalog metadata with schema/version/path/coverage information sufficient to reconstruct the logical table.

The extraction utility uses the catalog/manifests rather than path guessing.

### Requirement: Resume cannot create duplicate research rows

Resume validates input/config/schema identity and skips only proven completed units. Stable ids/natural uniqueness prevent duplicate finalized rows. Corrupt/incompatible checkpoints fail explicitly.
