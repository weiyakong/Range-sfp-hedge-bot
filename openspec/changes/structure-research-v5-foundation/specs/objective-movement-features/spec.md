# Objective Movement Features Specification

## Purpose

Define the objective measurements to collect in the first research pass. Exact formulas, schemas, units, observation boundaries, and validation examples SHALL be finalized in the detailed design and feature contracts before implementation of each feature family.

## ADDED Requirements

### Requirement: Movement geometry and timing

For each approved movement observation, the system SHALL preserve its start and end anchors and measure its direction, price displacement, percentage price change, and duration.

### Requirement: Retracements are measured as percentages

Countertrend retracements and pullbacks SHALL be measured directly as price percentages and other approved neutral measurements rather than being converted to Fibonacci ratios in this research pass.

### Requirement: Movement speed and speed change

The system SHALL collect movement-speed measurements and approved recent-speed windows sufficient to study continuation, acceleration, deceleration, and loss of directional momentum.

### Requirement: Path efficiency

The system SHALL measure how directly price travels between relevant anchors, including approved higher-resolution path measurements where source coverage permits, so that direct directional movement can be distinguished from heavily oscillating movement.

### Requirement: Internal movement structure

The system SHALL collect objective properties of internal movement structure, including the number, direction, amplitude, duration, and retracement characteristics of observable internal submovements or pullbacks where the approved source resolution permits them to be measured without inventing structure.

### Requirement: Overlap and neighboring-movement relationships

The system SHALL measure objective overlap and relative relationships between neighboring movements, including relative amplitude and duration, without assigning a predefined parent-impulse role.

### Requirement: Extremum sequence and update behavior

The system SHALL collect objective information about extrema and their updates, including observable HH, HL, LH, and LL relationships where they are defined by the approved observation contract, elapsed time since relevant extrema, and whether/when an extremum is subsequently updated.

### Requirement: Volatility

The system SHALL collect approved volatility measurements needed to compare directional movement with noisy or expanding/contracting market conditions.

### Requirement: Compression and expansion

The system SHALL collect objective measurements of price-range compression and expansion over approved observation windows.

### Requirement: Range behavior

The system SHALL collect descriptive range characteristics over approved candidate windows, including range width, slope, occupancy, midpoint crossings, boundary interactions, alternation behavior, and contraction/expansion characteristics where those measurements are well-defined.

### Requirement: Breakout and excursion behavior

The system SHALL record objective behavior when price interacts with or exits an observed range, including whether the interaction occurs by wick or close, excursion magnitude, and other approved contemporaneously observable breakout characteristics.

### Requirement: Retrospective outcomes remain separate

Outcomes that require future bars, including continuation after an excursion, return-inside behavior, MFE, MAE, or future-horizon measurements, SHALL be stored as retrospective research outcomes and SHALL NOT be represented as information available at the original observation time.

### Requirement: Cross-scale relationships are descriptive

The system SHALL preserve and measure objective temporal and price relationships between observations at different approved scales or resolutions, including containment and relative movement characteristics where observable.

#### Scenario: One movement lies within a larger observed movement interval

* **GIVEN** two independently defined observations at different approved scales
* **WHEN** the smaller observation lies temporally within the larger observation interval
* **THEN** the system MAY record that containment relationship and its objective relative measurements
* **AND** SHALL NOT infer solely from containment that the larger observation is a validated parent impulse.

### Requirement: Feature families remain separately inspectable

The feature families defined by this specification SHALL remain separately inspectable in final research outputs according to the research-output persistence specification so that each family can be independently reviewed and uploaded for analysis.
