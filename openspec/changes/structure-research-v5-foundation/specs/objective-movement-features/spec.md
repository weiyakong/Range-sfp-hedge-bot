# Objective Movement Features Specification

## Purpose

Define the objective measurement families to collect in the first research pass. This pass records how price behaved through time and across resolutions; it does not classify movements as impulse, correction, range, breakout, or chop.

## ADDED Requirements

### Requirement: Existing macro legs are directional research containers

For each approved existing macro leg, the system SHALL preserve its source identity and provenance and SHALL record at minimum `start_time`, `end_time`, `start_price`, `end_price`, source `direction` when present, duration, signed price change, absolute price change, signed percentage change, and absolute percentage change.

The first-pass dataset SHALL NOT assign the macro leg a new semantic type such as `impulse` or `correction`.

#### Scenario: A macro leg is processed

* **GIVEN** an approved source macro leg has start and end anchors
* **WHEN** the research pipeline processes the leg
* **THEN** it SHALL calculate the price-derived direction from `end_price - start_price`
* **AND** SHALL store that derived direction as `up`, `down`, or `flat`
* **AND** SHALL compare it with any source direction field as a QA check
* **AND** SHALL NOT infer `impulse` or `correction` from the source role or event label.

### Requirement: Movement geometry and timing

For each approved observation interval, the system SHALL preserve its start and end anchors and measure signed displacement, absolute displacement, signed percentage change, absolute percentage change, and duration using the approved measurement contracts.

### Requirement: Retracements are measured as percentages when an approved anchor pair exists

When a retracement can be measured from already-approved anchors without inventing a new internal-leg algorithm, the system SHALL store the direct retracement percentage and neutral supporting measurements rather than converting the result to Fibonacci ratios or labels.

### Requirement: Speed and speed change are numeric measurements

The system SHALL collect signed and direction-aware speed measurements, rolling recent-speed measurements, and numeric speed-change/acceleration measurements defined by the approved formula contract.

The first-pass dataset SHALL NOT create threshold-based labels such as `accelerating`, `decelerating`, or `exhausted`.

### Requirement: Path and directional efficiency

The system SHALL measure net displacement, close-to-close path at approved finer resolutions, path efficiency, direction-aware path components, and supporting candle activity measurements without inventing an intra-candle event order that is not present in the source data.

### Requirement: Candle geometry and overlap

The system SHALL collect body, wick, full-range, pairwise overlap, overlap position, body overlap, wick penetration, body penetration, close penetration, and directional extension measurements sufficient to distinguish materially different overlap geometries.

### Requirement: Volatility and volume

The system SHALL preserve raw volume where present and SHALL collect approved volume-derived, True Range, ATR, realized-volatility, and compression/expansion measurements without threshold-based market-state labels.

### Requirement: Extremum information remains objective

The system MAY collect objective high/low timestamps, elapsed time since approved extrema, and high/low update behavior where these can be derived without introducing a new swing or internal-leg classifier.

### Requirement: Cross-scale relationships are descriptive

The system SHALL preserve and measure temporal, price, and path relationships between observations at approved resolutions, including calendar containment, partial containment by macro legs, and relative movement characteristics where observable.

#### Scenario: A finer bar lies inside a larger calendar bar

* **GIVEN** two approved candle resolutions
* **WHEN** a finer closed bar lies within a larger fixed calendar interval
* **THEN** the system SHALL record the deterministic containment relationship
* **AND** SHALL NOT infer from that containment that either object is a validated structural parent impulse.

### Requirement: Fixed and rolling measurements remain distinguishable

Fixed calendar-bar measurements and truly rolling measurements SHALL be stored and named distinctly so that a fixed 4H candle can never be confused with the most recent rolling four hours ending at the current eligible timestamp.

### Requirement: Feature evolution is stored across the full path

Approved dynamic features SHALL be computed at every eligible closed observation point across the available movement, not only at the start, midpoint, or end of a macro leg.

This SHALL preserve periods of acceleration, slowdown, overlap growth, path-efficiency change, renewed continuation, and other observable transitions without assigning them semantic labels.

### Requirement: Deferred structural interpretation is not required in the first pass

The first-pass pipeline SHALL NOT be required to construct a new internal-leg/swing algorithm, final range boundaries, breakout classifications, future breakout horizons, or a composite choppiness score.

The source OHLCV, candle geometry, overlap, path, timing, volume, volatility, and cross-timeframe data required to research those definitions later SHALL be preserved.

### Requirement: Feature families remain separately inspectable

The feature families defined by this specification SHALL remain separately inspectable in final research outputs according to the research-output persistence specification so that each family can be independently reviewed and extracted for later analysis.
