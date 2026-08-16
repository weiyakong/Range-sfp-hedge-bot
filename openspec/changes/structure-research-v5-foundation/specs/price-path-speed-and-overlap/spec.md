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

### Requirement: Global macro-leg comparison includes log-scale movement and speed

For every approved existing macro leg with positive prices and positive duration, the research output SHALL preserve `signed_log_move`, `absolute_log_move`, and time-normalized log-speed measures including:

- `signed_log_speed_per_day = signed_log_move / duration_days`
- `absolute_log_speed_per_day = absolute_log_move / duration_days`

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

For strictly positive prices and non-zero duration:

`signed_log_speed = ln(P1 / P0) / elapsed_time`.

Its absolute version SHALL be available for direction-neutral comparison of movement magnitude per unit time.

### Requirement: Rolling recent speed is measured over approved durations without historical recomputation

At each eligible newly closed calculation candle with endpoint `t`, a rolling observation of duration `W` SHALL describe the immediately preceding complete interval ending at `t`.

For a rolling observation constructed from complete constituent calculation candles, `P0` SHALL be the open of the first constituent candle and `P1` SHALL be the close of the last constituent candle.

Approved rolling durations are `30m`, `1h`, `4h`, `12h`, `24h`, and `3d`.

A calculation resolution is eligible for rolling duration `W` only when the resolution divides `W` exactly and the window contains at least two complete constituent candles. The output SHALL identify both rolling duration and calculation resolution.

The historical production run SHALL process eligible endpoints incrementally/linearly: closing a new calculation candle creates the new rolling observation(s) ending at that candle. It SHALL NOT require recomputing previously finalized historical rolling rows from scratch at every endpoint.

A rolling observation crossing a source-segment boundary or required data gap SHALL be incomplete/null under the coverage contract.

### Requirement: Numeric speed change and acceleration remain unlabeled

For two consecutive non-overlapping windows of equal duration `W`:

`speed_change_W = current_speed_W - previous_speed_W`.

When time-normalized acceleration is exported:

`acceleration_W = speed_change_W / W_hours`.

The same change/acceleration logic MAY be applied to log speed under explicitly log-named fields. Ratios with zero or undefined denominators SHALL be null.

### Requirement: Close-path does not invent intra-candle order

For a larger observation measured through a finer candle resolution, close-path SHALL be calculated from the larger observation start price followed by the chronologically ordered closes of eligible finer bars:

`close_path = sum(abs(P_i - P_(i-1)))`.

The system SHALL NOT assume an unsupported sequence such as `open -> high -> low -> close` inside a candle.

### Requirement: Log close-path is available for cross-era path comparison

For a sequence of strictly positive prices `P_0 ... P_n` at an approved finer resolution:

`log_close_path = sum(abs(ln(P_i / P_(i-1))))`.

### Requirement: Path is measured at multiple approved resolutions

Where source coverage permits, the system SHALL calculate:

- `1D` path via `4H`, `1H`, `15m`, and `5m`;
- `4H` path via `1H`, `15m`, and `5m`;
- `1H` path via `15m` and `5m`;
- `15m` path via `5m`.

Each path metric SHALL identify both observation interval and finer calculation resolution.

Canonical `1m` data SHALL remain available for later targeted drill-down, but full-market path feature families are not required to be materialized at 1m resolution in this pass unless separately approved.

### Requirement: Path efficiency is net displacement divided by close-path

For non-zero `close_path`:

`path_efficiency = abs(P1 - P0) / close_path`.

If `close_path == 0`, efficiency SHALL be null.

### Requirement: Log path efficiency is preserved for multiplicative comparison

For positive prices and non-zero `log_close_path`:

`log_path_efficiency = absolute_log_move / log_close_path`.

### Requirement: Local-direction path components are separate from macro-direction path components

For a non-flat observation, let `d_local = sign(P1 - P0)` and each finer close-to-close step be `delta_i`:

- `path_with_local_direction = sum(max(d_local * delta_i, 0))`
- `path_against_local_direction = sum(max(-d_local * delta_i, 0))`
- `counter_local_path_share = path_against_local_direction / close_path` when `close_path > 0`.

Equivalent macro-direction metrics SHALL use separate macro-explicit names.

### Requirement: Alternation is measured from observed finer-step signs

Zero finer-step changes SHALL be treated explicitly according to the feature dictionary and SHALL NOT be silently assigned up or down direction.

For the sequence of non-zero finer-step signs:

`alternation_rate = sign_change_count / (nonzero_step_count - 1)`

when at least two non-zero steps exist.

### Requirement: Candle geometry is preserved in absolute and price-normalized form

For every candle:

- `full_range = high - low`
- `body_size = abs(close - open)`
- `body_high = max(open, close)`
- `body_low = min(open, close)`
- `upper_wick = high - body_high`
- `lower_wick = body_low - low`

When `full_range > 0`, the system SHALL also store `body_share`, `upper_wick_share`, and `lower_wick_share` relative to full range.

For strictly positive prices, the system SHALL preserve `log_full_range = ln(high / low)`, `log_body_size = abs(ln(close / open))`, and explicitly documented price/log-normalized wick magnitudes.

### Requirement: Candle activity complements close-path

For an observation built from finer candles, the system SHALL preserve at minimum sums of finer full ranges, absolute bodies, upper wicks, lower wicks, and True Range where available, plus price/log-normalized counterparts where defined.

### Requirement: Pairwise overlap preserves explicit geometry and normalization

For consecutive candles `prev` and `curr` inside one continuous source segment:

- `range_overlap_low = max(prev.low, curr.low)`
- `range_overlap_high = min(prev.high, curr.high)`
- `range_overlap_abs = max(0, range_overlap_high - range_overlap_low)`
- `prev_range = prev.high - prev.low`
- `curr_range = curr.high - curr.low`
- `range_union_abs = max(prev.high, curr.high) - min(prev.low, curr.low)`
- `overlap_share_prev = range_overlap_abs / prev_range` when `prev_range > 0`
- `overlap_share_curr = range_overlap_abs / curr_range` when `curr_range > 0`
- `overlap_jaccard = range_overlap_abs / range_union_abs` when `range_union_abs > 0`.

Body-to-body overlap SHALL use the same interval-intersection geometry on `[prev.body_low, prev.body_high]` and `[curr.body_low, curr.body_high]`:

- `body_overlap_low = max(prev.body_low, curr.body_low)`
- `body_overlap_high = min(prev.body_high, curr.body_high)`
- `body_overlap_abs = max(0, body_overlap_high - body_overlap_low)`.

Where denominators are positive, the system SHALL preserve body overlap normalized by previous body, current body, and body union under separately named fields.

The current candle's neutral extensions beyond the previous candle SHALL include:

- `upper_extension_abs = max(0, curr.high - prev.high)`
- `lower_extension_abs = max(0, prev.low - curr.low)`.

### Requirement: Atomic penetration stores both mirrored orientations before observation direction is applied

For each consecutive same-source candle pair, penetration SHALL be stored in neutral mirrored form rather than choosing an up/down market interpretation at pair-construction time.

Let the previous candle provide reference range `[prev.low, prev.high]` and body `[prev.body_low, prev.body_high]`. The current candle SHALL preserve at minimum:

- `wick_penetration_from_top_abs = max(0, prev.high - max(curr.low, prev.low))`
- `wick_penetration_from_bottom_abs = max(0, min(curr.high, prev.high) - prev.low)`
- `body_penetration_from_top_abs = max(0, prev.body_high - max(curr.body_low, prev.body_low))`
- `body_penetration_from_bottom_abs = max(0, min(curr.body_high, prev.body_high) - prev.body_low)`
- `close_penetration_from_top_abs = max(0, prev.high - max(curr.close, prev.low))` when `curr.close <= prev.high`, capped to `prev_range`
- `close_penetration_from_bottom_abs = max(0, min(curr.close, prev.high) - prev.low)` when `curr.close >= prev.low`, capped to `prev_range`.

Each raw penetration SHALL have a separately named normalization by the applicable previous reference width when that width is positive. Values beyond the opposite boundary SHALL be capped at `1` for the normalized penetration depth; extension beyond the boundary remains represented separately by extension fields rather than penetration > 100%.

No atomic pair SHALL choose which mirrored orientation means `against_move`.

For a later observation with mechanically known observation direction:

- if observation direction is `up`, `*_penetration_against_move` SHALL select the corresponding `*_from_top` value;
- if observation direction is `down`, it SHALL select the corresponding `*_from_bottom` value;
- if observation direction is `flat`, `*_penetration_against_move` SHALL be null and both neutral mirrored fields remain available.

Observation-relative penetration SHALL identify the observation whose direction was used. A completed macro-leg direction is retrospective; a fixed/rolling observation direction becomes known only at that observation's close.

### Requirement: Pairwise overlap supports arbitrary later aggregation

Atomic pairwise overlap records SHALL retain both candle identifiers/timestamps and calculation resolution so overlap can later be aggregated over arbitrary periods without rerunning source-data collection.

For approved rolling windows, the system SHALL export at least mean and median `overlap_share_prev`, `overlap_share_curr`, and `overlap_jaccard`, plus `any_overlap_share`, eligible pair count, and coverage status.

### Requirement: Choppiness remains decomposed

The first pass SHALL NOT create a composite `choppiness` label or score.

It SHALL preserve the objective components required for later research, including net displacement, close-path, path efficiency, local-direction path components, alternation, pairwise and rolling overlap, candle geometry, penetration, speed evolution, and activity measures.
