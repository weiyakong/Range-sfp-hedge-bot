# Price, Path, Speed, and Overlap Measurement Contract

## Purpose

Define objective formulas for price movement, speed, path, directional components, candle geometry, overlap, retracement, penetration, and extension without embedding impulse/correction/chop classifications.

## ADDED Requirements

### Requirement: Basic price geometry uses explicit formulas

For an observation starting at price `P0` and ending at price `P1`:

- `signed_price_change = P1 - P0`
- `absolute_price_change = abs(P1 - P0)`
- `signed_return_pct = 100 * (P1 / P0 - 1)` when `P0 != 0`
- `absolute_return_pct = abs(signed_return_pct)`
- `duration_seconds = end_time - start_time`.

Undefined divisions SHALL be null with an explicit null meaning, not replaced by zero.

### Requirement: Log-scale movement is preserved alongside ordinary movement

For strictly positive `P0` and `P1`:

- `signed_log_move = ln(P1 / P0)`
- `absolute_log_move = abs(signed_log_move)`.

Ordinary USD change and ordinary percentage return SHALL remain available separately. A display-scaled value such as `100 * signed_log_move` SHALL be named as a scaled log return, not an ordinary percentage return.

### Requirement: Direct retracement uses only approved anchors and has an exact formula

For an approved reference movement `A -> B` with prices `P_A`, `P_B` and a subsequent approved endpoint `C` with price `P_C`, let:

- `reference_delta = P_B - P_A`
- `candidate_delta = P_C - P_B`.

When `reference_delta != 0`, preserve the neutral magnitude ratio:

`candidate_vs_reference_pct = 100 * abs(candidate_delta) / abs(reference_delta)`.

Also preserve directional opposition explicitly. Let `d_ref = sign(reference_delta)`:

`opposing_retracement_abs = max(0, -d_ref * candidate_delta)`

and:

`retracement_pct = 100 * opposing_retracement_abs / abs(reference_delta)`.

Thus a continuation in the same direction has `retracement_pct = 0`, a full return to `P_A` has `retracement_pct = 100`, and movement beyond `P_A` MAY exceed 100. The value SHALL NOT be converted to Fibonacci labels or semantic correction classes.

The anchors themselves are governed by the approved-anchor contract; this formula SHALL NOT authorize discovery of new swing anchors.

### Requirement: Global macro-leg comparison includes log-scale movement and speed

For every approved macro leg with positive prices and duration:

- `signed_log_speed_per_day = signed_log_move / duration_days`
- `absolute_log_speed_per_day = absolute_log_move / duration_days`.

No threshold on distance or speed SHALL classify a leg as impulse or correction in this pass.

### Requirement: Local direction is a mechanical sign

For an observation:

- `local_price_direction = up` when `P1 > P0`
- `local_price_direction = down` when `P1 < P0`
- `local_price_direction = flat` when `P1 == P0`.

This field SHALL mean only the sign of start-to-end displacement. Macro-regime or macro-leg alignment SHALL use separately named fields.

### Requirement: Ordinary and log speed remain distinct and direction normalization is exact

For positive duration in hours:

`raw_signed_speed_pct_per_hour = signed_return_pct / duration_hours`.

For positive prices and elapsed time:

`signed_log_speed = ln(P1 / P0) / elapsed_time`.

For a non-flat observation with `d_local = sign(P1-P0)`:

- `local_direction_speed_pct_per_hour = d_local * raw_signed_speed_pct_per_hour`
- `local_direction_log_speed = d_local * signed_log_speed`.

These values are non-negative by construction and mean magnitude of progress in the observation's own eventual mechanical direction; they SHALL NOT be interpreted as trend/impulse classifications.

When an approved macro direction `d_macro` in `{+1,-1}` is available:

- `macro_aligned_speed_pct_per_hour = d_macro * raw_signed_speed_pct_per_hour`
- `macro_aligned_log_speed = d_macro * signed_log_speed`.

Positive macro-aligned values mean movement with the approved macro direction; negative values mean movement against it. If the relevant direction is unavailable/flat, the corresponding direction-normalized field SHALL be null.

### Requirement: Rolling observations are incremental and have exact boundary prices

At each eligible newly closed calculation candle with endpoint `t`, rolling duration `W` SHALL describe `[t-W, t)`.

For complete constituent calculation candles:

- `P0 = open` of the first constituent candle;
- `P1 = close` of the last constituent candle.

Approved rolling durations are `30m`, `1h`, `4h`, `12h`, `24h`, and `3d`.

A calculation resolution is eligible only when it divides `W` exactly and provides at least two complete constituent candles. The output SHALL identify rolling duration and calculation resolution.

Historical production SHALL process endpoints incrementally/linearly. Creating the row ending at a newly closed candle SHALL NOT require recomputing already-finalized historical rows.

A window crossing a source-segment boundary or real gap SHALL be incomplete/null for complete metrics.

### Requirement: Speed change compares immediately adjacent non-overlapping windows

For current window `[t-W,t)` and previous equal window `[t-2W,t-W)`:

`speed_change_W = current_speed_W - previous_speed_W`.

When exported:

`acceleration_W = speed_change_W / W_hours`.

Equivalent log-speed fields SHALL be explicitly log-named. Undefined ratios SHALL be null.

### Requirement: Close-path has one canonical price sequence

For a fixed/rolling observation measured through complete finer candles, define:

- `Q0 = observation start price P0`;
- `Q1 ... Qn = chronological closes of all constituent finer candles`.

For fixed/rolling observations `Qn` SHALL equal `P1`.

Then:

`close_path = sum(i=1..n, abs(Q_i - Q_(i-1)))`.

For strictly positive sequence values:

`log_close_path = sum(i=1..n, abs(ln(Q_i / Q_(i-1))))`.

The system SHALL NOT invent intra-candle order such as `open -> high -> low -> close`.

Macro-leg anchor-inclusive sequencing is governed by the macro-leg contract.

### Requirement: Path is measured at multiple approved resolutions

Where complete coverage permits:

- `1D` path via `4H`, `1H`, `15m`, `5m`;
- `4H` path via `1H`, `15m`, `5m`;
- `1H` path via `15m`, `5m`;
- `15m` path via `5m`.

Each metric SHALL identify observation resolution and calculation resolution. Canonical `1m` remains available for targeted drill-down but full-market path features are not required at 1m in this pass.

### Requirement: Path efficiency uses the same path sequence

When `close_path > 0`:

`path_efficiency = abs(P1 - P0) / close_path`.

When `log_close_path > 0` and prices are positive:

`log_path_efficiency = absolute_log_move / log_close_path`.

Zero denominators SHALL produce null.

### Requirement: Directional path components partition the same steps as close-path

For every step in the canonical path sequence:

`delta_i = Q_i - Q_(i-1)`.

Regardless of net direction, preserve:

- `upward_close_path = sum(max(delta_i, 0))`
- `downward_close_path = sum(max(-delta_i, 0))`.

Thus, apart from exact zero steps:

`upward_close_path + downward_close_path = close_path`.

For non-flat observations with `d_local = sign(P1-P0)`:

- `path_with_local_direction = sum(max(d_local * delta_i, 0))`
- `path_against_local_direction = sum(max(-d_local * delta_i, 0))`
- `counter_local_path_share = path_against_local_direction / close_path` when `close_path > 0`.

For flat observations, local-direction with/against fields SHALL be null while upward/downward path remains available.

Equivalent macro-direction fields SHALL use macro-explicit names. For strictly positive prices, equivalent upward/downward and with/against components based on `log_delta_i = ln(Q_i/Q_(i-1))` SHALL be available under explicit `log_*` names for cross-era comparison.

### Requirement: Alternation has an explicit zero-step convention

For path steps `delta_i`:

- positive steps have sign `+1`;
- negative steps have sign `-1`;
- exact zero steps are excluded from the sign-change sequence but SHALL be counted separately as `zero_step_count` and, when total step count is positive, `zero_step_share`.

For the remaining non-zero sign sequence:

`alternation_rate = sign_change_count / (nonzero_step_count - 1)`

when at least two non-zero steps exist; otherwise alternation rate SHALL be null.

A sequence `+ , 0 , -` therefore contains one non-zero-sign change.

### Requirement: Candle geometry has exact absolute and log formulas

For every candle:

- `full_range = high - low`
- `body_size = abs(close - open)`
- `body_high = max(open, close)`
- `body_low = min(open, close)`
- `upper_wick = high - body_high`
- `lower_wick = body_low - low`.

When `full_range > 0`:

- `body_share = body_size / full_range`
- `upper_wick_share = upper_wick / full_range`
- `lower_wick_share = lower_wick / full_range`.

For strictly positive prices:

- `log_full_range = ln(high / low)`
- `log_body_size = abs(ln(close / open))`
- `log_upper_wick = ln(high / body_high)`
- `log_lower_wick = ln(body_low / low)`.

Undefined logs SHALL be null.

### Requirement: Candle activity complements close-path under explicit normalization

For an observation built from finer candles, preserve sums of:

- `full_range`;
- `body_size`;
- `upper_wick`;
- `lower_wick`;
- True Range where available;
- `log_full_range`;
- `log_body_size`;
- `log_upper_wick`;
- `log_lower_wick`.

Where previous close is positive and True Range is valid, also define:

`normalized_true_range = TR / previous_close`.

Its observation-level sum/mean MAY be retained under explicit normalized names. Activity fields SHALL NOT be described as exact intra-candle path.

### Requirement: Atomic candle pairs require temporal adjacency as well as source continuity

A pair is eligible for sequential overlap/penetration/alternation research only when:

- both candles belong to the same `source_segment_id`;
- both use the same calculation resolution;
- `curr.start_time == prev.end_time`.

Rows separated by a real missing interval SHALL NOT be treated as a valid consecutive pair even if they are adjacent rows in a file.

### Requirement: Pairwise range overlap has exact geometry, normalization, and position

For an eligible pair:

- `range_overlap_low = max(prev.low, curr.low)`
- `range_overlap_high = min(prev.high, curr.high)`
- `range_overlap_abs = max(0, range_overlap_high - range_overlap_low)`
- `prev_range = prev.high - prev.low`
- `curr_range = curr.high - curr.low`
- `range_union_abs = max(prev.high, curr.high) - min(prev.low, curr.low)`.

Where denominators are positive:

- `overlap_share_prev = range_overlap_abs / prev_range`
- `overlap_share_curr = range_overlap_abs / curr_range`
- `overlap_jaccard = range_overlap_abs / range_union_abs`.

When `range_overlap_abs > 0`, let `overlap_mid = (range_overlap_low + range_overlap_high)/2`. Preserve overlap location in each candle:

- `overlap_low_pos_prev = (range_overlap_low - prev.low) / prev_range`
- `overlap_high_pos_prev = (range_overlap_high - prev.low) / prev_range`
- `overlap_mid_pos_prev = (overlap_mid - prev.low) / prev_range`
- equivalent `*_pos_curr` fields normalized by `curr_range`.

If the relevant range denominator is zero or there is no positive-width overlap, position fields SHALL be null.

### Requirement: Body overlap has exact normalization

Define:

- `prev_body = prev.body_high - prev.body_low`
- `curr_body = curr.body_high - curr.body_low`
- `body_overlap_low = max(prev.body_low, curr.body_low)`
- `body_overlap_high = min(prev.body_high, curr.body_high)`
- `body_overlap_abs = max(0, body_overlap_high - body_overlap_low)`
- `body_union_abs = max(prev.body_high, curr.body_high) - min(prev.body_low, curr.body_low)`.

Where denominators are positive:

- `body_overlap_share_prev = body_overlap_abs / prev_body`
- `body_overlap_share_curr = body_overlap_abs / curr_body`
- `body_overlap_jaccard = body_overlap_abs / body_union_abs`.

Doji/zero-body denominators SHALL produce null rather than zero.

### Requirement: Neutral and direction-relative extensions are explicit

For an eligible pair:

- `upper_extension_abs = max(0, curr.high - prev.high)`
- `lower_extension_abs = max(0, prev.low - curr.low)`.

When `prev_range > 0`:

- `upper_extension_share_prev = upper_extension_abs / prev_range`
- `lower_extension_share_prev = lower_extension_abs / prev_range`.

For an observation with known mechanical direction:

- if observation direction is `up`, `extension_with_move = upper_extension` and `extension_against_move = lower_extension`;
- if observation direction is `down`, `extension_with_move = lower_extension` and `extension_against_move = upper_extension`;
- if observation direction is `flat`, direction-relative extension fields SHALL be null while neutral upper/lower fields remain available.

The observation-relative extension fields SHALL identify the observation/direction basis. Fixed/rolling versions become known at observation close; completed macro-leg-relative versions are retrospective.

### Requirement: Penetration uses one common previous-range reference and stores both orientations

For every eligible pair with `prev_range > 0`, all extreme/body/close penetration depths SHALL use the previous candle full range `[prev.low, prev.high]` as the common reference.

Define `clamp(x,0,R) = min(max(x,0),R)` for `R = prev_range`.

From the top:

- `extreme_penetration_from_top_abs = clamp(prev.high - curr.low, 0, prev_range)`
- `body_penetration_from_top_abs = clamp(prev.high - curr.body_low, 0, prev_range)`
- `close_penetration_from_top_abs = clamp(prev.high - curr.close, 0, prev_range)`
- `wick_only_penetration_from_top_abs = max(0, extreme_penetration_from_top_abs - body_penetration_from_top_abs)`.

From the bottom:

- `extreme_penetration_from_bottom_abs = clamp(curr.high - prev.low, 0, prev_range)`
- `body_penetration_from_bottom_abs = clamp(curr.body_high - prev.low, 0, prev_range)`
- `close_penetration_from_bottom_abs = clamp(curr.close - prev.low, 0, prev_range)`
- `wick_only_penetration_from_bottom_abs = max(0, extreme_penetration_from_bottom_abs - body_penetration_from_bottom_abs)`.

Every penetration field SHALL also have a `_share_prev` companion equal to its absolute value divided by `prev_range`.

`extreme_penetration` records the farthest current-candle price reach. `wick_only_penetration` records the extra penetration depth reached beyond the current body. Body and close penetration remain separately inspectable.

No atomic pair SHALL choose an `against_move` orientation.

For an observation whose mechanical direction is known:

- observation `up` -> `*_penetration_against_move` selects the corresponding `*_from_top` value;
- observation `down` -> selects `*_from_bottom`;
- observation `flat` -> observation-relative penetration is null while both neutral orientations remain stored.

The observation identifier and its direction basis SHALL be retained. Fixed/rolling observation-relative fields become known at observation close; completed macro-leg-relative fields are retrospective.

### Requirement: Pairwise overlap supports arbitrary later aggregation

Atomic pair records SHALL retain both candle identifiers/timestamps, calculation resolution, source segment, pair eligibility, and coverage state.

For complete approved rolling windows, export at least mean and median of:

- `overlap_share_prev`;
- `overlap_share_curr`;
- `overlap_jaccard`;
- body overlap normalizations;
- approved penetration/extension shares where applicable.

Also preserve:

`any_overlap_share = count(eligible pairs with range_overlap_abs > 0) / eligible_pair_count`

when `eligible_pair_count > 0`, plus eligible pair count and coverage status.

### Requirement: Choppiness remains decomposed

The first pass SHALL NOT create a composite `choppiness` label or score.

It SHALL preserve net displacement, close-path, path efficiency, directional path components, alternation, zero-step behavior, pairwise/rolling overlap, overlap position, candle geometry, penetration, extension, speed evolution, and activity measures as separately inspectable numeric components.
