# Objective Movement Features Specification

## Purpose

Define the objective measurement families to collect in the first research pass. This pass records how price behaved through time and across resolutions; it does not classify movements as impulse, correction, range, breakout, or chop.

## ADDED Requirements

### Requirement: Existing macro legs are source research containers, not validated hierarchy

For each approved macro leg preserve source identity/provenance, source anchors, source direction where present, duration, signed/absolute price change and percentage change.

Calculate price-derived direction as `up/down/flat` and compare to source direction as QA. Do not infer impulse/correction.

Historical macro provenance, including mixed daily/refinement source, SHALL remain distinct from current canonical market assignment.

### Requirement: Macro source anchors are refined before canonical leg-membership metrics are assigned

A coarse macro anchor SHALL first be checked against compatible complete canonical 1m data inside its source bucket.

Preserve whether the result is a unique 1m match, multiple matches, no match, incomplete search coverage, or source incompatibility.

A unique 1m match narrows the possible extreme time to that minute but does not establish intra-minute order. The matching minute remains a boundary uncertainty interval shared by adjacent legs.

### Requirement: Ambiguous macro boundary data remain data, not discarded observations

Canonical candles that overlap a macro-anchor uncertainty interval remain fully stored/queryable.

They SHALL NOT be assigned wholesale to either adjacent leg's unambiguous interior when the exact pivot time inside those candles is unknown.

Multiple possible 1m matches SHALL NOT be resolved by arbitrarily picking first, last or nearest.

### Requirement: Movement geometry and timing are objective

For complete fixed/rolling observations preserve start/end anchors, signed/absolute displacement, signed/absolute percentage change, log movement and duration according to approved formulas.

For macro observations preserve source displacement/duration separately from refined anchor uncertainty and safe canonical interior timing.

### Requirement: Retracements use only explicitly approved A-B-C relationships

Direct retracement measurement is permitted only when A/B/C each come from approved anchor sources and the tuple itself is explicitly configured/approved.

The pipeline SHALL NOT generate arbitrary triples merely because individual anchors exist.

Approved tuples are stored in `retracement_measurements` using direct percentage formulas. No Fibonacci conversion/label. Zero production rows is valid if no tuple list is approved.

### Requirement: Speed and speed change remain numeric

Collect signed, local-direction, rolling recent-speed, speed-change and acceleration fields under canonical names/formulas. Do not create accelerating/decelerating/exhausted labels.

Macro source-coordinate speed may be retained as retrospective source measurement, but bucket-limited source duration SHALL NOT be represented as exact canonical event timing.

### Requirement: Path and directional efficiency remain objective

Fixed/rolling observations measure net displacement, close path, path efficiency, directional components and activity without inventing intra-candle order.

For macro observations distinguish explicitly:

1. source whole-leg displacement between approved source anchor prices;
2. `safe_*` canonical interior measurements using only candles guaranteed to lie after the start-anchor uncertainty and before the end-anchor uncertainty;
3. complete `anchor_inclusive_*` whole-leg path only when full boundary ordering/path is actually established.

A coarse/unique-minute anchor does not by itself authorize complete whole-leg path because within-boundary path remains unknown.

### Requirement: Safe macro interior preserves only unambiguous leg membership

For start-anchor possible interval `[S0,S1)` and end-anchor possible interval `[E0,E1)`, the safe interior is `[S1,E0)`.

Only complete calculation candles fully contained in that interval may contribute to macro safe-interior path/activity/overlap/volume metrics.

Boundary-overlapping candles remain queryable separately.

### Requirement: Atomic target candle geometry is retained separately from observation aggregates

For every complete target candle `5m/15m/1H/4H/1D`, materialize body, wicks, full range, normalized shares and approved log geometry in `candle_geometry`.

Observation aggregates do not replace atomic geometry.

### Requirement: Pairwise overlap/penetration/extension remains atomic and inspectable

Collect pairwise range overlap, overlap position, body overlap, neutral upper/lower extension and mirrored extreme/body/close/wick-only penetration sufficient to distinguish materially different geometries.

### Requirement: Volatility and volume remain numeric

Preserve raw/additive volume where valid and collect approved volume groupings, TR/ATR, fixed/rolling realized volatility and numeric contraction/expansion components without semantic market-state labels.

Macro RV is not required in this pass. Macro volume/activity summaries use safe-interior membership when macro boundaries remain uncertain.

### Requirement: Extremum information remains objective

The system MAY collect high/low values, repeated first/last/count at stated calculation resolution, elapsed time since approved extrema, anchor-refinement candidates and update behavior where no new swing classifier is introduced.

Repeated equal extrema follow the explicit tie contract.

### Requirement: Cross-scale relationships are descriptive

Preserve deterministic calendar containment, macro temporal intersection, anchor uncertainty and objective relative measurements. Containment does not imply validated parent impulse.

### Requirement: Fixed and rolling measurements remain distinguishable

A fixed 4H calendar candle and a rolling 4h window ending at an arbitrary eligible endpoint SHALL never share semantics/identity.

### Requirement: Feature evolution is stored across the full path

Approved dynamic fixed/rolling observations are computed at every eligible closed point across available history, preserving acceleration, slowdown, overlap/path-efficiency evolution and renewed continuation without semantic labels.

### Requirement: Deferred structural interpretation is outside first pass

Do not construct new internal swing/leg hierarchy, parent impulse, final range boundaries, breakout labels/outcomes, composite choppiness score, Fib price/FibTime, or Elliott labels.

### Requirement: Feature families remain separately inspectable

Source candles, candle geometry, price/speed, path/activity, atomic pairs, overlap summaries, volume/volatility, macro anchors/refinement, safe-interior macro measurements, retracement relationships, cross-timeframe mappings and retrospective macro context SHALL remain separately queryable under the canonical schema.
