# Objective Movement Features Specification

## Purpose

Define the objective measurement families to collect in the first research pass. This pass records how price behaved through time and across resolutions; it does not classify movements as impulse, correction, range, breakout, or chop.

## ADDED Requirements

### Requirement: Existing macro legs are source research containers, not validated hierarchy

For each approved macro leg preserve source identity/provenance, anchors, source direction where present, duration, signed/absolute price change and percentage change.

Calculate price-derived direction as `up/down/flat` and compare to source direction as QA. Do not infer impulse/correction.

Historical macro provenance, including mixed daily/refinement source, SHALL remain distinct from current canonical market assignment.

### Requirement: Movement geometry and timing are objective

For each complete approved observation preserve start/end anchors, signed/absolute displacement, signed/absolute percentage change, log movement, and duration according to approved formula contracts.

### Requirement: Retracements use only explicitly approved A-B-C relationships

Direct retracement measurement is permitted only when:

1. A, B, and C each come from approved anchor sources; and
2. the relationship tuple `A -> B -> C` itself is explicitly configured/approved.

The pipeline SHALL NOT generate arbitrary triples from every fixed/rolling/macro anchor merely because each anchor is individually approved.

Approved tuples are stored in `retracement_measurements` using direct percentage formulas. No Fibonacci conversion/label.

If no production tuple list is approved, zero production retracement rows is valid.

### Requirement: Speed and speed change remain numeric

Collect signed, local-direction, rolling recent-speed, speed-change and acceleration fields under the canonical names/formulas. Do not create accelerating/decelerating/exhausted labels.

### Requirement: Path and directional efficiency remain objective

Measure net displacement, close path at approved calculation resolutions, path efficiency, directional components and activity without inventing intra-candle event order.

Macro source movement, internal canonical path, and anchor-inclusive canonical path are distinct; anchor-inclusive metrics require compatible source and sufficient anchor-time precision.

### Requirement: Atomic target candle geometry is retained separately from observation aggregates

For every complete target candle `5m/15m/1H/4H/1D`, materialize its body, wicks, full range, normalized shares and approved log geometry in `candle_geometry`.

Observation-level sums/means of geometry do not replace the atomic candle geometry layer.

### Requirement: Pairwise overlap/penetration/extension remains atomic and inspectable

Collect pairwise range overlap, overlap position, body overlap, neutral upper/lower extension and mirrored extreme/body/close/wick-only penetration sufficient to distinguish materially different geometries.

### Requirement: Volatility and volume remain numeric

Preserve raw/additive volume where valid and collect approved volume groupings, TR/ATR, fixed/rolling realized volatility, and numeric contraction/expansion components without semantic market-state labels.

Macro RV is not required in this pass unless separately specified.

### Requirement: Extremum information remains objective

The system MAY collect high/low values, repeated first/last/count at stated calculation resolution, elapsed time since approved extrema, and update behavior where no new swing classifier is introduced.

Repeated equal extrema follow the explicit tie contract.

### Requirement: Cross-scale relationships are descriptive

Preserve deterministic calendar containment, macro temporal intersection and objective relative measurements. Containment does not imply validated parent impulse.

### Requirement: Fixed and rolling measurements remain distinguishable

A fixed 4H calendar candle and a rolling 4h window ending at an arbitrary eligible endpoint SHALL never share semantics/identity.

### Requirement: Feature evolution is stored across the full path

Approved dynamic fixed/rolling observations are computed at every eligible closed point across available history, preserving acceleration, slowdown, overlap/path-efficiency evolution and renewed continuation without semantic labels.

### Requirement: Deferred structural interpretation is outside first pass

Do not construct new internal swing/leg hierarchy, parent impulse, final range boundaries, breakout labels/outcomes, composite choppiness score, Fib price/FibTime, or Elliott labels.

### Requirement: Feature families remain separately inspectable

Source candles, candle geometry, price/speed, path/activity, atomic pairs, overlap summaries, volume/volatility, retracement relationships, cross-timeframe mappings and retrospective macro context SHALL remain separately queryable under the canonical schema.
