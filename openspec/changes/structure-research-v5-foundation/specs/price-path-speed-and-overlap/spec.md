# Price, Path, Speed, and Overlap Measurement Contract

## Purpose

Define objective formulas for price movement, speed, path, directional components, candle geometry, and overlap without embedding impulse/correction/chop classifications.

## ADDED Requirements

### Requirement: Basic price geometry uses explicit formulas

For an observation starting at price `P0` and ending at price `P1`:

- `signed_price_change = P1 - P0`
- `absolute_price_change = abs(P1 - P0)`
- `signed_return_pct = 100 * (P1 / P0 - 1)` when `P0 != 0`
- `absolute_return_pct = abs(signed_return_pct)`
- `duration_seconds = end_time - start_time`

Undefined divisions SHALL be stored as null with an explicit null meaning, not replaced by zero.

### Requirement: Log-scale movement is preserved alongside ordinary price and percentage movement

For strictly positive start and end prices, the system SHALL calculate:

- `signed_log_move = ln(P1 / P0)`
- `absolute_log_move = abs(signed_log_move)`

Ordinary USD change and ordinary percentage return SHALL remain available for human interpretation, but log-scale movement SHALL be preserved for cross-era and up-versus-down comparisons of large market moves.

If a display-scaled log value is exported as `100 * signed_log_move`, its name and feature-dictionary entry SHALL make clear that it is a scaled log return and not an ordinary percentage return.

#### Scenario: Reciprocal up and down moves are compared

* **GIVEN** one move changes price by a multiplicative factor `k`
* **AND** another move reverses that factor by changing price by `1/k`
* **WHEN** log-scale movement is calculated
* **THEN** the two signed log moves SHALL have equal absolute magnitude and opposite signs
* **AND** the system SHALL retain ordinary percentage returns separately rather than treating log return as ordinary percent change.

### Requirement: Global macro-leg comparison includes log-scale movement and speed

For every approved existing macro leg with positive prices and positive duration, the research output SHALL preserve `signed_log_move`, `absolute_log_move`, and time-normalized log-speed measures such as:

- `signed_log_speed_per_day = signed_log_move / duration_days`
- `absolute_log_speed_per_day = absolute_log_move / duration_days`

Equivalent per-hour fields MAY be stored where useful, but units SHALL be explicit.

No threshold on log move or log speed SHALL classify a leg as impulse or correction in the first pass.

### Requirement: Local direction is a mechanical sign, not a semantic class

For an observation window:

- `local_price_direction = up` when `P1 > P0`
- `local_price_direction = down` when `P1 < P0`
- `local_price_direction = flat` when `P1 == P0`

`local_price_direction` SHALL mean only the sign of start-to-end price displacement. It SHALL NOT mean that the observation is an impulse, trend, correction, or chop.

Macro-regime alignment, when an approved macro regime direction is available, SHALL be stored separately from local direction.

### Requirement: Speed is percentage displacement per unit time

For an observation with non-zero duration in hours:

`raw_signed_speed_pct_per_hour = signed_return_pct / duration_hours`.

Where local-direction-normalized speed is required, the system SHALL store it under an explicitly local name and SHALL NOT confuse it with macro-direction alignment.

Where macro-direction-aligned speed is calculated from an approved macro direction, it SHALL be stored under a separate explicitly macro-aligned name.

### Requirement: Log speed is available for multiplicative price comparison

For strictly positive prices and non-zero duration, the system SHALL support time-normalized log speed:

`signed_log_speed = ln(P1 / P0) / elapsed_time`.

Its absolute version SHALL be available for direction-neutral comparison of movement magnitude per unit time.

Log speed SHALL be stored separately from ordinary percentage-per-time speed because the two measures are numerically different for large moves.

### Requirement: Rolling recent speed is measured over approved durations

At each eligible closed observation point `t`, rolling speed for duration `W` SHALL use the price at the start of the eligible rolling interval and the price at `t`, with the result normalized by the actual elapsed hours.

Approved rolling durations are defined by the time contract: `30m`, `1h`, `4h`, `12h`, `24h`, and `3d` where supported by the calculation resolution and coverage.

Where both ordinary percentage speed and log speed are exported, their names and units SHALL remain distinct.

### Requirement: Numeric speed change and acceleration remain unlabeled

For two consecutive non-overlapping windows of equal duration `W`:

`speed_change_W = current_speed_W - previous_speed_W`.

When time-normalized acceleration is exported:

`acceleration_W = speed_change_W / W_hours`.

The same change/acceleration logic MAY be applied to log speed under explicitly log-named fields.

The first-pass output SHALL store numeric values and SHALL NOT convert them into threshold-based `accelerating` or `decelerating` labels.

Short-versus-long speed deltas and ratios MAY be exported with explicit window names. Ratios with zero or undefined denominators SHALL be null.

### Requirement: Close-path does not invent intra-candle order

For a larger observation measured through a finer candle resolution, close-path SHALL be calculated from the larger observation start price followed by the chronologically ordered closes of eligible finer bars:

`close_path = sum(abs(P_i - P_(i-1)))`.

The system SHALL NOT assume an unsupported sequence such as `open -> high -> low -> close` inside a candle.

### Requirement: Log close-path is available for cross-era path comparison

For a sequence of strictly positive prices `P_0 ... P_n` at an approved finer resolution:

`log_close_path = sum(abs(ln(P_i / P_(i-1))))`.

This SHALL be stored separately from dollar close-path and SHALL preserve the finer calculation resolution used.

### Requirement: Path is measured at multiple approved resolutions

Where source coverage permits, the system SHALL calculate:

- `1D` path via `4H`, `1H`, `15m`, and `5m`;
- `4H` path via `1H`, `15m`, and `5m`;
- `1H` path via `15m` and `5m`;
- `15m` path via `5m`.

Each path metric SHALL identify both the observation interval and the finer calculation resolution.

Where log-path is available, the same observation and calculation resolutions SHALL be identifiable.

### Requirement: Path efficiency is net displacement divided by close-path

For non-zero `close_path`:

`path_efficiency = abs(P1 - P0) / close_path`.

A signed/local-direction-aware companion MAY be stored, but SHALL be explicitly named and SHALL NOT replace the neutral absolute efficiency.

If `close_path == 0`, the efficiency SHALL be null unless a later approved contract explicitly defines another convention.

### Requirement: Log path efficiency is preserved for multiplicative comparison

For positive prices and non-zero `log_close_path`:

`log_path_efficiency = absolute_log_move / log_close_path`.

The system SHALL preserve ordinary path efficiency and log path efficiency as separate fields. Neither SHALL be used as a first-pass impulse/correction threshold.

### Requirement: Local-direction path components are separate from macro-direction path components

For a non-flat observation, let `d_local = sign(P1 - P0)` and let each finer close-to-close step be `delta_i`.

- `path_with_local_direction = sum(max(d_local * delta_i, 0))`
- `path_against_local_direction = sum(max(-d_local * delta_i, 0))`
- `counter_local_path_share = path_against_local_direction / close_path` when `close_path > 0`.

If equivalent metrics are calculated relative to an approved macro direction, they SHALL use separate names such as `path_with_macro_direction` and `path_against_macro_direction`.

Equivalent log-step direction components MAY be stored for cross-era comparison, but SHALL use explicitly log-prefixed names.

### Requirement: Alternation is measured from observed finer-step signs

Zero finer-step changes SHALL be treated explicitly according to the feature dictionary and SHALL NOT be silently assigned up or down direction.

For the sequence of non-zero finer-step signs, the system SHALL store the number of sign changes and, when at least two non-zero steps exist:

`alternation_rate = sign_change_count / (nonzero_step_count - 1)`.

### Requirement: Candle geometry is preserved in absolute and price-normalized form

For every candle:

- `full_range = high - low`
- `body_size = abs(close - open)`
- `body_high = max(open, close)`
- `body_low = min(open, close)`
- `upper_wick = high - body_high`
- `lower_wick = body_low - low`

When `full_range > 0`, the system SHALL also store `body_share`, `upper_wick_share`, and `lower_wick_share` relative to full range.

For strictly positive `open`, the system SHALL additionally preserve multiplicative/log-normalized candle geometry sufficient for cross-price-era comparison, including at minimum:

- `log_full_range = ln(high / low)` when `low > 0`;
- `log_body_size = abs(ln(close / open))` when `close > 0`;
- price-normalized or log-normalized upper/lower wick magnitudes under explicitly documented formulas.

Undefined ratios or logs SHALL be null.

### Requirement: Candle activity complements close-path

For an observation built from finer candles, the system SHALL preserve at minimum:

- sum of finer full ranges;
- sum of finer absolute body sizes;
- sum of finer upper wicks;
- sum of finer lower wicks;
- sum of finer True Range where available.

For cross-era comparison, corresponding price-normalized/log activity summaries SHALL be available where the underlying prices are strictly positive.

These SHALL be described as activity measures, not exact market path, because intra-candle event order is unknown.

### Requirement: Pairwise overlap preserves explicit geometry and normalization

For consecutive candles `prev` and `curr`:

- `range_overlap_low = max(prev.low, curr.low)`
- `range_overlap_high = min(prev.high, curr.high)`
- `range_overlap_abs = max(0, range_overlap_high - range_overlap_low)`
- `prev_range = prev.high - prev.low`
- `curr_range = curr.high - curr.low`
- `range_union_abs = max(prev.high, curr.high) - min(prev.low, curr.low)`.

Where denominators are positive, the system SHALL calculate separately named overlap normalizations rather than one ambiguous `overlap_ratio`:

- `overlap_share_prev = range_overlap_abs / prev_range`
- `overlap_share_curr = range_overlap_abs / curr_range`
- `overlap_jaccard = range_overlap_abs / range_union_abs`.

The system SHALL also preserve body-to-body overlap and the current candle's upper/lower extension beyond the previous candle. Undefined ratios SHALL be null.

### Requirement: Overlap penetration preserves direction-aware raw geometry

For every consecutive candle pair, the atomic record SHALL preserve enough raw values to reconstruct penetration relative to either local direction later, including both candles' OHLC/body bounds, overlap bounds, and upper/lower extensions.

When direction-aware penetration fields are exported for a specified observation direction, their formulas and normalization denominators SHALL be explicitly documented in the feature dictionary before implementation. No implementation SHALL silently choose a penetration formula or call it macro-directional when it is relative to a local observation direction.

### Requirement: Pairwise overlap supports arbitrary later aggregation

The atomic pairwise overlap records SHALL retain both candle identifiers/timestamps and calculation resolution so that overlap can later be aggregated over arbitrary periods without rerunning source-data collection.

For approved rolling windows, the system SHALL export at least:

- mean and median `overlap_share_prev`;
- mean and median `overlap_share_curr`;
- mean and median `overlap_jaccard`;
- `any_overlap_share`, defined as the share of eligible consecutive pairs with `range_overlap_abs > 0`.

The output SHALL identify the rolling duration, calculation resolution, eligible pair count, and coverage status explicitly.

### Requirement: Choppiness remains decomposed

The first pass SHALL NOT create a composite `choppiness` label or score.

It SHALL preserve the objective components required for later research, including net displacement, close-path, path efficiency, local-direction path components, alternation, pairwise and rolling overlap, candle geometry, speed evolution, and activity measures.
