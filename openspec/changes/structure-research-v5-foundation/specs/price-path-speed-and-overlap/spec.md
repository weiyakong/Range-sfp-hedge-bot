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

### Requirement: Rolling recent speed is measured over approved durations

At each eligible closed observation point `t`, rolling speed for duration `W` SHALL use the price at the start of the eligible rolling interval and the price at `t`, with the result normalized by the actual elapsed hours.

Approved rolling durations are defined by the time contract: `30m`, `1h`, `4h`, `12h`, `24h`, and `3d` where supported by the calculation resolution and coverage.

### Requirement: Numeric speed change and acceleration remain unlabeled

For two consecutive non-overlapping windows of equal duration `W`:

`speed_change_W = current_speed_W - previous_speed_W`.

When time-normalized acceleration is exported:

`acceleration_W = speed_change_W / W_hours`.

The first-pass output SHALL store numeric values and SHALL NOT convert them into threshold-based `accelerating` or `decelerating` labels.

Short-versus-long speed deltas and ratios MAY be exported with explicit window names. Ratios with zero or undefined denominators SHALL be null.

### Requirement: Close-path does not invent intra-candle order

For a larger observation measured through a finer candle resolution, close-path SHALL be calculated from the larger observation start price followed by the chronologically ordered closes of eligible finer bars:

`close_path = sum(abs(P_i - P_(i-1)))`.

The system SHALL NOT assume an unsupported sequence such as `open -> high -> low -> close` inside a candle.

### Requirement: Path is measured at multiple approved resolutions

Where source coverage permits, the system SHALL calculate:

- `1D` path via `4H`, `1H`, `15m`, and `5m`;
- `4H` path via `1H`, `15m`, and `5m`;
- `1H` path via `15m` and `5m`;
- `15m` path via `5m`.

Each path metric SHALL identify both the observation interval and the finer calculation resolution.

### Requirement: Path efficiency is net displacement divided by close-path

For non-zero `close_path`:

`path_efficiency = abs(P1 - P0) / close_path`.

A signed/local-direction-aware companion MAY be stored, but SHALL be explicitly named and SHALL NOT replace the neutral absolute efficiency.

If `close_path == 0`, the efficiency SHALL be null unless a later approved contract explicitly defines another convention.

### Requirement: Local-direction path components are separate from macro-direction path components

For a non-flat observation, let `d_local = sign(P1 - P0)` and let each finer close-to-close step be `delta_i`.

- `path_with_local_direction = sum(max(d_local * delta_i, 0))`
- `path_against_local_direction = sum(max(-d_local * delta_i, 0))`
- `counter_local_path_share = path_against_local_direction / close_path` when `close_path > 0`.

If equivalent metrics are calculated relative to an approved macro direction, they SHALL use separate names such as `path_with_macro_direction` and `path_against_macro_direction`.

### Requirement: Alternation is measured from observed finer-step signs

Zero finer-step changes SHALL be treated explicitly according to the feature dictionary and SHALL NOT be silently assigned up or down direction.

For the sequence of non-zero finer-step signs, the system SHALL store the number of sign changes and, when at least two non-zero steps exist:

`alternation_rate = sign_change_count / (nonzero_step_count - 1)`.

### Requirement: Candle geometry is preserved

For every candle:

- `full_range = high - low`
- `body_size = abs(close - open)`
- `body_high = max(open, close)`
- `body_low = min(open, close)`
- `upper_wick = high - body_high`
- `lower_wick = body_low - low`

When `full_range > 0`, the system SHALL also store `body_share`, `upper_wick_share`, and `lower_wick_share` relative to full range. Undefined ratios SHALL be null.

### Requirement: Candle activity complements close-path

For an observation built from finer candles, the system SHALL preserve at minimum:

- sum of finer full ranges;
- sum of finer absolute body sizes;
- sum of finer upper wicks;
- sum of finer lower wicks;
- sum of finer True Range where available.

These SHALL be described as activity measures, not exact market path, because intra-candle event order is unknown.

### Requirement: Pairwise overlap preserves geometry, not only magnitude

For consecutive candles `prev` and `curr`:

- `range_overlap_low = max(prev.low, curr.low)`
- `range_overlap_high = min(prev.high, curr.high)`
- `range_overlap_abs = max(0, range_overlap_high - range_overlap_low)`.

The system SHALL preserve normalized overlap magnitude, overlap position within both candles, body-to-body overlap, and the current candle's upper and lower extensions beyond the previous candle.

### Requirement: Overlap penetration is direction-aware relative to local movement

The system SHALL preserve enough numeric geometry to distinguish shallow wick-only return, body penetration, close penetration, and extension relative to the current local observation direction.

For an upward local observation, return/penetration into the previous candle is measured from the previous candle's upper side downward; for a downward local observation the formulas SHALL be mirrored from the previous candle's lower side upward.

The contract SHALL expose separately named numeric fields for at least:

- `wick_penetration_against_local_move`;
- `body_penetration_against_local_move`;
- `close_penetration_against_local_move`;
- `extension_with_local_move`;
- `extension_against_local_move`.

No field name SHALL imply macro direction when the formula is relative to local direction.

### Requirement: Pairwise overlap supports arbitrary later aggregation

The atomic pairwise overlap records SHALL retain timestamps and calculation resolution so that overlap can later be aggregated over arbitrary periods without rerunning source-data collection.

For approved rolling windows, the system SHALL also export at least:

- mean normalized overlap;
- median normalized overlap;
- `any_overlap_share`, defined as the share of eligible consecutive pairs with positive overlap.

The output SHALL identify the rolling duration and calculation resolution explicitly.

### Requirement: Choppiness remains decomposed

The first pass SHALL NOT create a composite `choppiness` label or score.

It SHALL preserve the objective components required for later research, including net displacement, close-path, path efficiency, local-direction path components, alternation, pairwise and rolling overlap, candle geometry, speed evolution, and activity measures.
