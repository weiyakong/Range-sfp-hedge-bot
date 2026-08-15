# First-Pass Research Scope Guards

## Purpose

Prevent known assumptions from earlier Structure Research work from contaminating the first-pass descriptive dataset.

## ADDED Requirements

### Requirement: Do not use Fibonacci price calculations in this research pass

The first-pass research pipeline SHALL NOT use Fibonacci price levels or Fibonacci price ratios as inputs to feature construction, movement hierarchy, classification, or research labels.

Direct percentage measurements such as retracement percentage remain permitted and required where specified.

#### Scenario: Countertrend retracement is measured

* **GIVEN** a countertrend price movement is observed
* **WHEN** its retracement depth is calculated
* **THEN** the system SHALL store the direct percentage measurement
* **AND** SHALL NOT convert that measurement into a Fibonacci label for this research pass.

### Requirement: Do not use FibTime in this research pass

The first-pass research pipeline SHALL NOT use FibTime calculations from previous Structure Research work as inputs to feature construction, hierarchy construction, classification, or research labels.

Existing FibTime work associated with the separate global market-structure project is outside this research pass and SHALL remain independent.

### Requirement: Do not define parent impulse in this research pass

The first-pass research pipeline SHALL NOT create a new rule that declares a movement to be the validated `parent impulse` of another movement.

The purpose of the collected descriptive data is to support later research into how parent impulse and structural hierarchy should be defined and on what scale.

#### Scenario: Multiple plausible higher-order movements exist

* **GIVEN** a smaller movement could plausibly belong to more than one larger structural movement
* **WHEN** the first-pass dataset is built
* **THEN** the system SHALL preserve measurable relationships to candidate larger observations where defined
* **AND** SHALL NOT resolve the ambiguity by inventing a parent-impulse rule.
