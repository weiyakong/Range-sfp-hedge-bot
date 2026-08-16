# Structure Research Objective Specification

## Purpose

Define the first-pass research objective: collect objective, inspectable measurements of market movement so that later research can formulate and validate criteria for movement hierarchy, parent impulse construction, impulse/correction distinction, and the relevant structural timeframe.

## ADDED Requirements

### Requirement: First-pass output is descriptive research data

The system SHALL produce descriptive measurements of observed market movements and their context for later analysis.

#### Scenario: A movement is processed

* **GIVEN** an observed movement, swing, or leg is available from approved project inputs
* **WHEN** the first-pass research pipeline processes it
* **THEN** the system SHALL preserve the observation identity and provenance
* **AND** SHALL attach objective measurements defined by the approved feature specifications
* **AND** SHALL keep those measurements available for later comparison across movements and scales.

### Requirement: Existing structural observations are not promoted to validated hierarchy

Existing upstream swing or leg boundaries MAY be used as observation anchors, but any pre-existing parent/reference relationship SHALL NOT be treated as validated ground truth for this research pass.

#### Scenario: Upstream data contains parent or reference labels

* **GIVEN** an input contains a pre-existing parent, reference, or similar hierarchy field
* **WHEN** the first-pass research dataset is built
* **THEN** that field SHALL NOT be used to define the research target hierarchy
* **AND** any retained source field SHALL remain explicitly marked as source provenance rather than validated truth.

### Requirement: Research data must support later criteria discovery

The collected data SHALL make it possible to compare movements by log-scale distance, timing, speed, internal close-path, path efficiency, directional path components, alternation, candle geometry, overlap geometry, volatility, volume, and cross-scale relationships.

#### Scenario: Final first-pass dataset is reviewed

* **WHEN** the first-pass research outputs are complete
* **THEN** the outputs SHALL contain enough objective measurements to compare candidate structural relationships without requiring a predefined parent-impulse rule.

### Requirement: Modern BTC behavior is the primary research era

The research SHALL distinguish a primary modern-market era from older historical data rather than pooling the complete BTC history with equal analytical weight.

The primary research era SHALL be `2023-01-01` onward, with `2024-01-01` onward treated as the highest-priority modern subset when source coverage permits.

Data before `2023-01-01` MAY be retained as a historical robustness/reference era, but it SHALL NOT determine thresholds or first-pass criteria with equal weight to the primary modern era unless a later approved analysis explicitly requests that comparison.

#### Scenario: Criteria are explored from the research dataset

* **GIVEN** both modern and older BTC observations are available
* **WHEN** researchers compare candidate quantitative signatures of market movement
* **THEN** the primary analysis SHALL report modern-era results separately
* **AND** SHALL NOT allow the larger count or larger historical volatility of early BTC observations to dominate modern-market conclusions by default.

### Requirement: Research focuses on how comparable price distances are traversed

A central comparison target SHALL be movements that cover similar log-scale price distance but differ materially in elapsed time and internal path.

The first pass SHALL preserve the measurements needed to compare such cases, including log distance, duration, log speed, close-path, log close-path, path efficiency, counter-direction path, alternation, overlap geometry, candle geometry, volatility, and volume.

No single duration, speed, distance, or efficiency threshold SHALL itself define `impulse` or `correction` in this pass.

#### Scenario: Two movements cover similar log distance with different behavior

* **GIVEN** two observations have similar absolute log movement
* **AND** one reaches that distance much faster and/or through a materially more efficient internal path
* **WHEN** the observations are exported for research
* **THEN** both SHALL remain descriptively measurable as distinct market behaviors
* **AND** neither SHALL be automatically assigned an impulse/correction label by the first-pass pipeline.
