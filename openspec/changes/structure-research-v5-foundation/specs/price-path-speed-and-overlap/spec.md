# Price, Path, Speed, and Overlap Measurement Contract

## Purpose

Define objective formulas for price movement, speed, path, directional components, candle geometry, overlap, retracement, penetration, and extension without embedding impulse/correction/chop classifications.

## ADDED Requirements

### Requirement: Basic price geometry uses explicit formulas

For a complete observation starting at `P0` and ending at `P1`:

- `signed_price_change = P1 - P0`
- `absolute_price_change = abs(P1 - P0)`
- `signed_return_pct = 100 * (P1/P0 - 1)` when `P0 != 0`
- `absolute_return_pct = abs(signed_return_pct)`
- `duration_seconds = end_time - start_time`.

Undefined divisions are null. Incomplete fixed/rolling observations SHALL NOT expose ordinary complete net-move/speed metrics from partial observed-only endpoints.

### Requirement: Log movement is separate from ordinary percent movement

For strictly positive `P0`,`P1`:

- `signed_log_move = ln(P1/P0)`
- `absolute_log_move = abs(signed_log_move)`.

A scaled log value is not an ordinary percentage return and must be explicitly log-named.

### Requirement: Local direction is mechanical

- `up` when `P1>P0`
- `down` when `P1<P0`
- `flat` when equal.

This is not a semantic trend/impulse classification.

### Requirement: Speed names and formulas are canonical

For positive duration in hours:

`raw_signed_speed_pct_per_hour = signed_return_pct / duration_hours`.

For positive prices:

`signed_log_speed_per_hour = signed_log_move / duration_hours`

`absolute_log_speed_per_hour = absolute_log_move / duration_hours`.

For non-flat observation and `d_local=sign(P1-P0)`:

- `local_direction_speed_pct_per_hour = d_local * raw_signed_speed_pct_per_hour`
- `local_direction_log_speed_per_hour = d_local * signed_log_speed_per_hour`.

These local-direction values are nonnegative progress magnitudes in the observation's eventual mechanical direction.

For approved retrospective macro direction `d_macro`:

- `macro_aligned_speed_pct_per_hour = d_macro * raw_signed_speed_pct_per_hour`
- `macro_aligned_log_speed_per_hour = d_macro * signed_log_speed_per_hour`.

Macro-aligned fields are retrospective when the macro direction/endpoint is retrospective.

For approved macro source legs with positive duration in days:

- `signed_log_speed_per_day = signed_log_move / duration_days`
- `absolute_log_speed_per_day = absolute_log_move / duration_days`.

### Requirement: Rolling windows have exact boundary semantics

At eligible endpoint `t`, duration `W` means `[t-W,t)`.

For complete constituent calculation candles:

- `P0 = open` of first constituent;
- `P1 = close` of last constituent.

Approved durations: `30m`,`1h`,`4h`,`12h`,`24h`,`3d`.

Eligibility follows the exact schema matrix. A rolling window crossing a canonical source segment/gap/boundary is incomplete for complete metrics.

Historical production is incremental: finalizing a new endpoint SHALL NOT require recomputing already-finalized older rolling rows.

### Requirement: Speed change uses immediately preceding equal non-overlapping window

For current `[t-W,t)` and previous `[t-2W,t-W)`:

- `speed_change_pct_per_hour = current.raw_signed_speed_pct_per_hour - previous.raw_signed_speed_pct_per_hour`
- `acceleration_pct_per_hour2 = speed_change_pct_per_hour / W_hours`.

Equivalent log fields use explicit log names. Both windows must be complete and continuity-compatible.

### Requirement: Direct retracement formula is exact but tuple discovery is not authorized

For explicitly approved relationship `A -> B -> C` with prices `P_A,P_B,P_C`:

- `reference_delta = P_B - P_A`
- `candidate_delta = P_C - P_B`
- `candidate_vs_reference_pct = 100 * abs(candidate_delta)/abs(reference_delta)` when `reference_delta != 0`
- `d_ref = sign(reference_delta)`
- `opposing_retracement_abs = max(0, -d_ref*candidate_delta)`
- `retracement_pct = 100 * opposing_retracement_abs/abs(reference_delta)`.

Continuation in reference direction therefore has retracement 0; full return to A is 100%; movement beyond A may exceed 100%.

A/B/C may be drawn only from approved anchor sources, AND the relationship tuple itself must be explicitly configured/approved. The pipeline SHALL NOT form arbitrary triples from all available fixed/rolling/macro anchors.

Production outputs use `retracement_measurements`. If no approved tuple list is configured, zero production retracement rows is valid; the formula remains covered by golden tests.

No Fibonacci ratio/label is produced.

### Requirement: Close path uses one canonical price sequence

For complete fixed/rolling observation measured via constituent calculation candles:

- `Q0=P0` = observation start/open;
- `Q1...Qn` = chronological constituent closes;
- `Qn=P1`.

`close_path = sum(abs(Q_i-Q_(i-1)))`.

For positive values:

`log_close_path = sum(abs(ln(Q_i/Q_(i-1))))`.

The system SHALL NOT invent open-high-low-close intra-candle order.

Macro internal/anchor-inclusive sequencing is governed by the macro contract.

### Requirement: Path efficiency uses the same sequence

When `close_path>0`:

`path_efficiency = abs(P1-P0)/close_path`.

When `log_close_path>0`:

`log_path_efficiency = absolute_log_move/log_close_path`.

Zero denominator -> null.

### Requirement: Fixed path calculation matrix is exact

- 15m via 5m;
- 1H via 5m,15m;
- 4H via 5m,15m,1H;
- 1D via 5m,15m,1H,4H.

Rolling and macro matrices are defined in the schema contract.

### Requirement: Directional path components partition the exact same steps

For `delta_i=Q_i-Q_(i-1)`:

- `upward_close_path = sum(max(delta_i,0))`
- `downward_close_path = sum(max(-delta_i,0))`.

For non-flat `d_local`:

- `path_with_local_direction = sum(max(d_local*delta_i,0))`
- `path_against_local_direction = sum(max(-d_local*delta_i,0))`
- `counter_local_path_share = path_against_local_direction/close_path` when path > 0.

Flat observations keep upward/downward path but local with/against fields are null.

Equivalent log components are available under explicit `log_*` names.

### Requirement: Alternation has explicit zero-step convention

Positive step sign `+1`, negative `-1`, exact zero excluded from sign-change sequence but counted separately.

`alternation_rate = sign_change_count/(nonzero_step_count-1)` when at least two nonzero steps exist; otherwise null.

Sequence `+,0,-` has one sign change.

### Requirement: Atomic target-candle geometry has exact formulas

For a complete target candle:

- `full_range = high-low`
- `body_size = abs(close-open)`
- `body_high=max(open,close)`
- `body_low=min(open,close)`
- `upper_wick=high-body_high`
- `lower_wick=body_low-low`.

When `full_range>0`:

- `body_share=body_size/full_range`
- `upper_wick_share=upper_wick/full_range`
- `lower_wick_share=lower_wick/full_range`.

For positive prices:

- `log_full_range=ln(high/low)`
- `log_body_size=abs(ln(close/open))`
- `log_upper_wick=ln(high/body_high)`
- `log_lower_wick=ln(body_low/low)`.

Atomic target geometry SHALL be materialized in `candle_geometry`; observation activity summaries do not replace it.

### Requirement: Observation candle activity is explicitly aggregate, not exact path

At each approved calculation resolution preserve sums/means as specified of full range, body, wicks, log geometry, and valid TR/normalized TR. These are activity measurements, not invented intra-candle path.

### Requirement: Atomic pair eligibility requires exact adjacency and continuity

A pair is eligible only when:

- same canonical source segment;
- same calculation resolution;
- `curr.start_time == prev.end_time`;
- both complete.

Rows across a gap/boundary are not eligible even if adjacent in storage.

### Requirement: Range overlap is exact

For eligible previous/current candle:

- `range_overlap_low=max(prev.low,curr.low)`
- `range_overlap_high=min(prev.high,curr.high)`
- `range_overlap_abs=max(0,range_overlap_high-range_overlap_low)`
- `prev_range=prev.high-prev.low`
- `curr_range=curr.high-curr.low`
- `range_union_abs=max(prev.high,curr.high)-min(prev.low,curr.low)`.

Where denominators positive:

- `overlap_share_prev=range_overlap_abs/prev_range`
- `overlap_share_curr=range_overlap_abs/curr_range`
- `overlap_jaccard=range_overlap_abs/range_union_abs`.

For positive-width overlap preserve normalized low/high/mid position in both previous and current ranges. Otherwise position is null.

### Requirement: Body overlap is exact

With previous/current body intervals:

- `body_overlap_abs=max(0,min(prev.body_high,curr.body_high)-max(prev.body_low,curr.body_low))`
- normalize by previous body, current body, and union where denominator positive.

Doji/zero-body denominator -> null.

### Requirement: Neutral extensions are exact

- `upper_extension_abs=max(0,curr.high-prev.high)`
- `lower_extension_abs=max(0,prev.low-curr.low)`.

Normalize by positive previous range.

For up observation, with-move=upper and against-move=lower; for down, reverse; flat direction-relative fields null.

### Requirement: Penetration uses previous full range as common reference

For `R=prev.high-prev.low>0`, `clamp(x)=min(max(x,0),R)`.

From top:

- extreme = `clamp(prev.high-curr.low)`
- body = `clamp(prev.high-curr.body_low)`
- close = `clamp(prev.high-curr.close)`
- wick-only = `max(0,extreme-body)`.

From bottom:

- extreme = `clamp(curr.high-prev.low)`
- body = `clamp(curr.body_high-prev.low)`
- close = `clamp(curr.close-prev.low)`
- wick-only = `max(0,extreme-body)`.

Each has `_share_prev = abs/R`.

Atomic pairs retain both neutral orientations. Observation-relative against-move orientation is selected only later from observation direction.

### Requirement: Pairwise geometry supports later arbitrary aggregation

Atomic pairs retain both candle ids/timestamps, calculation resolution, source continuity, eligibility, and complete geometry. Observation summaries preserve at minimum mean/median overlap/body-overlap/penetration/extension measures, eligible count/coverage, and:

`any_overlap_share = count(eligible pairs with range_overlap_abs>0)/eligible_pair_count`

when denominator >0.

No threshold-based impulse/correction/chop label is created.
