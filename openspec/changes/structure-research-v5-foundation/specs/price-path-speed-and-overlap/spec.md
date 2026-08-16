# Price, Path, Speed, and Overlap Measurement Contract

## Purpose
Define objective movement, speed, path, overlap and retracement formulas without semantic impulse/correction classification.

## Basic price movement
For valid endpoints `P0,P1`:
- `signed_price_change=P1-P0`
- `absolute_price_change=abs(P1-P0)`
- `signed_return_pct=100*(P1/P0-1)` when `P0!=0`
- `absolute_return_pct=abs(signed_return_pct)`
- `signed_log_move=ln(P1/P0)` for positive prices
- `absolute_log_move=abs(signed_log_move)`.

Local direction is mechanical `up/down/flat`.

## Speed
For duration hours > 0:
- `raw_signed_speed_pct_per_hour=signed_return_pct/duration_hours`
- `signed_log_speed_per_hour=signed_log_move/duration_hours`
- `absolute_log_speed_per_hour=absolute_log_move/duration_hours`.

Macro source speed remains `source_*`; refined whole-leg speed exists only when both refined endpoint times are resolved. One whole-leg speed exists; TF-specific rows describe internal evolution.

## Rolling speed change
Current `[t-W,t)` vs previous `[t-2W,t-W)`:
- `speed_change=current_speed-previous_speed`
- `acceleration=speed_change/W_hours`.

## Fixed/rolling close path
For complete constituent candles:
- `Q0=open(first constituent)`
- `Q1...Qn=chronological constituent closes`.

`close_path=sum(abs(Qi-Qi-1))`; log counterpart sums absolute log ratios. Efficiency uses the same sequence.

## Refined macro close path
At calculation resolution `R`:
- `Q0=refined start pivot price`
- chronological closes of complete canonical `R` candles satisfying `start_pivot_time < candle.end_time <= end_pivot_time`
- append refined end pivot price if needed.

AggTrade fragment path SHALL NOT be added to TF close path.

## Fallback macro path
Use only fixed-grid constituents wholly inside guaranteed fallback interval. For `B1...Bn`: `Q0=open(B1)` and `Qi=close(Bi)`. Persist measured bounds, expected grid-slot count, observed count and coverage.

## Alternation
Exact zero steps are excluded from sign-change sequence but counted separately. `alternation_rate=sign_change_count/(nonzero_step_count-1)` when at least two nonzero steps exist.

## Candle geometry
For every complete candle:
- `full_range=high-low`
- `body_size=abs(close-open)`
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

Undefined divisions/logs are null.

## Atomic pair eligibility
Eligible canonical pair requires same source segment, same calculation resolution, both complete, and `curr.start_time==prev.end_time`. Boundary-fragment relationships are separately typed.

## Range overlap
For eligible pair:
- `range_overlap_low=max(prev.low,curr.low)`
- `range_overlap_high=min(prev.high,curr.high)`
- `range_overlap_abs=max(0,range_overlap_high-range_overlap_low)`
- `prev_range=prev.high-prev.low`
- `curr_range=curr.high-curr.low`
- `range_union_abs=max(prev.high,curr.high)-min(prev.low,curr.low)`.

Where denominators >0:
- `overlap_share_prev=range_overlap_abs/prev_range`
- `overlap_share_curr=range_overlap_abs/curr_range`
- `overlap_jaccard=range_overlap_abs/range_union_abs`.

If positive-width overlap exists, `overlap_mid=(range_overlap_low+range_overlap_high)/2` and normalized positions are:
- `overlap_low_pos_prev=(range_overlap_low-prev.low)/prev_range`
- `overlap_high_pos_prev=(range_overlap_high-prev.low)/prev_range`
- `overlap_mid_pos_prev=(overlap_mid-prev.low)/prev_range`
- equivalent `*_pos_curr` normalized by `curr_range`.
Otherwise position fields are null.

## Body overlap
Define:
- `prev_body=prev.body_high-prev.body_low`
- `curr_body=curr.body_high-curr.body_low`
- `body_overlap_low=max(prev.body_low,curr.body_low)`
- `body_overlap_high=min(prev.body_high,curr.body_high)`
- `body_overlap_abs=max(0,body_overlap_high-body_overlap_low)`
- `body_union_abs=max(prev.body_high,curr.body_high)-min(prev.body_low,curr.body_low)`.

Where denominators >0:
- `body_overlap_share_prev=body_overlap_abs/prev_body`
- `body_overlap_share_curr=body_overlap_abs/curr_body`
- `body_overlap_jaccard=body_overlap_abs/body_union_abs`.

Zero-body denominators produce null.

## Neutral extensions
- `upper_extension_abs=max(0,curr.high-prev.high)`
- `lower_extension_abs=max(0,prev.low-curr.low)`.
When `prev_range>0`, divide each by `prev_range` for `_share_prev`.

## Symmetric penetration
Use previous full range `[prev.low,prev.high]` as common reference. Let `clamp(x,0,R)=min(max(x,0),R)`, `R=prev_range`.

From top:
- `extreme_penetration_from_top_abs=clamp(prev.high-curr.low,0,R)`
- `body_penetration_from_top_abs=clamp(prev.high-curr.body_low,0,R)`
- `close_penetration_from_top_abs=clamp(prev.high-curr.close,0,R)`
- `wick_only_penetration_from_top_abs=max(0,extreme_penetration_from_top_abs-body_penetration_from_top_abs)`.

From bottom:
- `extreme_penetration_from_bottom_abs=clamp(curr.high-prev.low,0,R)`
- `body_penetration_from_bottom_abs=clamp(curr.body_high-prev.low,0,R)`
- `close_penetration_from_bottom_abs=clamp(curr.close-prev.low,0,R)`
- `wick_only_penetration_from_bottom_abs=max(0,extreme_penetration_from_bottom_abs-body_penetration_from_bottom_abs)`.

Every penetration field has `_share_prev = abs_value/prev_range` when `prev_range>0`.

Atomic pairs store both neutral orientations and do not choose `against_move`. Observation-relative selection:
- observation up -> choose corresponding `from_top`
- observation down -> choose corresponding `from_bottom`
- flat -> relative penetration null, neutral orientations retained.

## Aggregation
For complete fixed/rolling observations aggregate eligible canonical pairs with at least mean and median of overlap shares/Jaccard, body-overlap normalizations, penetration and extension shares; preserve eligible pair count, coverage, and `any_overlap_share=count(range_overlap_abs>0)/eligible_pair_count`.

For resolved macro observations, apply the same pair formulas to the explicitly typed non-overlapping constituent sequence `start RIGHT fragment -> complete interior intervals -> end LEFT fragment`, comparing immediately adjacent constituents at the same calculation resolution. Do not duration/volume/range-weight unless a separately named weighted metric is explicitly approved. Never include a full boundary candle together with its fragment.

Fallback macro aggregation uses only canonical pairs whose two whole intervals lie inside guaranteed fallback interval.

## Macro retracement
For immediately consecutive opposite-direction macro legs sharing a pivot, `A->B` then `B->C`:
- `reference_delta=P_B-P_A`
- `candidate_delta=P_C-P_B`
- `candidate_vs_reference_pct=100*abs(candidate_delta)/abs(reference_delta)`
- `d_ref=sign(reference_delta)`
- `opposing_retracement_abs=max(0,-d_ref*candidate_delta)`
- `retracement_pct=100*opposing_retracement_abs/abs(reference_delta)`.

Approved production count is 118. No Fibonacci labels.
