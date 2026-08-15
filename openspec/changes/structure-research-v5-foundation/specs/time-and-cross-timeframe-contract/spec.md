# Time and Cross-Timeframe Contract

## Purpose

Define the unambiguous UTC time grid, fixed-versus-rolling semantics, cross-timeframe containment, incomplete-window handling, and partial overlap between existing macro legs and calendar candles.

## ADDED Requirements

### Requirement: UTC is the canonical time basis

All candle boundaries, fixed intervals, rolling-window endpoints, containment relationships, coverage calculations, and exported timestamps SHALL use UTC.

Local time zones and daylight-saving transitions SHALL NOT change research interval boundaries.

### Requirement: Fixed candle intervals are calendar aligned

Fixed intervals SHALL use the exchange/source UTC calendar grid and SHALL NOT be shifted to arbitrary observation times.

For the approved target resolutions:

- `1D`: `00:00:00` to next-day `00:00:00` UTC.
- `4H`: `00:00-04:00`, `04:00-08:00`, `08:00-12:00`, `12:00-16:00`, `16:00-20:00`, `20:00-24:00` UTC.
- `1H`: each `HH:00` to the next `HH:00` UTC.
- `15m`: `:00-:15`, `:15-:30`, `:30-:45`, `:45-:00`.
- `5m`: source-aligned five-minute intervals beginning at minute values divisible by five.

Intervals SHALL be treated as half-open `[start_time, end_time)` intervals for containment logic.

#### Scenario: A four-hour fixed observation is built from 5m bars

* **GIVEN** the fixed interval `12:00-16:00` UTC
* **WHEN** the system selects 5m bars for that observation
* **THEN** it SHALL select only bars whose intervals belong to `12:00-16:00` UTC
* **AND** SHALL NOT create an alternative four-hour block such as `12:25-16:25` and call it a fixed 4H candle.

### Requirement: Fixed and rolling windows are separate concepts

A fixed calendar interval and a rolling lookback of the same nominal duration SHALL be stored and named separately.

A rolling lookback ending at eligible time `t` SHALL describe the immediately preceding duration ending at `t`; it SHALL NOT be snapped to the fixed calendar grid.

#### Scenario: Rolling four-hour observation

* **GIVEN** an eligible closed observation time of `20:25` UTC
* **WHEN** a rolling four-hour metric is calculated
* **THEN** its conceptual interval SHALL be the immediately preceding four hours ending at `20:25` UTC
* **AND** it SHALL NOT be labeled as the fixed `16:00-20:00` 4H candle.

### Requirement: Approved rolling durations

The first-pass research SHALL support rolling durations of `30m`, `1h`, `4h`, `12h`, `24h`, and `3d` where the source resolution provides enough closed observations to calculate the metric without interpolation.

A rolling metric SHALL record the source/calculation resolution used to derive it.

### Requirement: Target candle resolutions

The target first-pass candle resolutions are `1D`, `4H`, `1H`, `15m`, and `5m`, subject to source inventory and actual local coverage.

Missing target data SHALL NOT be silently synthesized or downloaded without explicit approval.

### Requirement: Cross-timeframe containment is deterministic

For every eligible finer candle, the system SHALL record the identifiers of containing larger fixed calendar candles where available and SHALL record the finer candle's ordinal position within each containing interval.

Expected and observed finer-bar counts SHALL be preserved so that gaps are visible.

### Requirement: Incomplete fixed and rolling observations are explicit

For every metric requiring constituent bars, the system SHALL record enough coverage information to distinguish complete from incomplete observations, including expected constituent count, observed constituent count, coverage ratio, and gap status where applicable.

Missing constituent data SHALL NOT be silently treated as complete coverage.

### Requirement: Macro-leg boundaries do not shift the candle grid

When an existing macro leg starts or ends inside a fixed candle, the fixed candle SHALL retain its normal UTC calendar boundaries.

The system SHALL separately record the exact temporal intersection between the macro leg and the candle, including intersection start, intersection end, and the fraction of the candle interval covered by the macro leg.

#### Scenario: Macro leg starts inside a 4H candle

* **GIVEN** a fixed 4H candle `12:00-16:00` UTC
* **AND** an existing macro leg starts at `13:35` UTC
* **WHEN** their relationship is stored
* **THEN** the 4H candle SHALL remain `12:00-16:00`
* **AND** the intersection SHALL begin at `13:35`
* **AND** the system SHALL record the partial temporal coverage rather than shifting the 4H candle to `13:35`.

### Requirement: Zero net displacement does not imply zero activity

For every fixed or rolling observation, the system SHALL preserve net displacement separately from intraperiod high/low range, high and low timestamps where available at the calculation resolution, upward and downward excursion from the observation start, close-path, and approved range/body/wick activity measurements.

#### Scenario: Price leaves and returns to its starting level

* **GIVEN** an observation whose start and end prices are equal
* **AND** price moved materially above or below the start during the interval
* **WHEN** the observation is exported
* **THEN** net displacement MAY equal zero
* **BUT** the intraperiod range, excursions, path, and activity fields SHALL preserve the observed movement.
