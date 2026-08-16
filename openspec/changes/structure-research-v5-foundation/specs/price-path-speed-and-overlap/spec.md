# Price, Path, Speed, and Overlap Measurement Contract

## Purpose

Define objective movement, speed, path, overlap and retracement formulas without semantic impulse/correction classification.

## Basic price movement

For valid observation endpoints `P0,P1`:
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

Local-direction forms use the mechanical endpoint direction.

Fixed/rolling speed uses exact observation endpoints.

For macro:
- retain original source-coordinate source speed under explicit `source_*` names;
- calculate exact whole-leg `macro_*` speed only when both trade pivots are exact;
- there is one whole-leg macro speed, not a different whole-leg speed per TF.

Timeframe-specific speed/evolution fields describe internal windows/candles.

## Rolling speed change

Current `[t-W,t)` vs preceding non-overlapping `[t-2W,t-W)`:
- `speed_change=current speed - previous speed`
- `acceleration=speed_change/W_hours`.

Both windows require complete compatible continuity.

## Fixed/rolling close path

For complete constituent candles:
- `Q0=open(first constituent)`
- `Q1...Qn=chronological constituent closes`.

`close_path=sum(abs(Qi-Qi-1))`
and log counterpart uses absolute log ratios.

Efficiency uses the same sequence.

## Exact macro close path

At calculation resolution `R`, exact macro sequence is:
- `Q0=exact start pivot price`
- every complete canonical `R` close whose candle end satisfies `start_pivot_time < end <= end_pivot_time`
- append exact end pivot price if necessary.

Do not add trade-level boundary path to candle close-path.

The same Q sequence defines:
- displacement
- close/log path
- path efficiency
- upward/downward path
- with/against mechanical macro direction
- alternation.

## Fallback macro path

When boundary remains ambiguous, use only fixed-grid constituents wholly inside fallback interval.

For eligible `B1...Bn`:
- `Q0=open(B1)`
- `Qi=close(Bi)`.

This explicitly includes the first constituent's open->close move.

Persist fallback measured start/end, grid-based expected count, observed count and coverage.

## Trade-boundary microstructure path

LEFT/RIGHT boundary fragment trade sequence is a separate feature family:
- `trade_price_path`
- `trade_log_price_path`
- directional trade path
- trade alternation
- trade-path efficiency.

These SHALL NOT be presented as 5m/15m/1H/4H/1D close path.

## Alternation

Exact zero price steps are excluded from sign-change sequence but counted separately.

`alternation_rate=sign_change_count/(nonzero_step_count-1)` when at least two nonzero steps exist.

## Candle geometry / overlap / penetration

Complete canonical candles retain:
- full range/body/wicks/shares/log geometry.

Canonical adjacent candle pair eligibility requires same segment/resolution, exact adjacency and completeness.

Range/body overlap, Jaccard, normalized positions, upper/lower extensions and mirrored penetration retain the previously approved neutral formulas. Boundary-fragment relationships are explicitly typed and never masquerade as ordinary canonical fixed-candle pairs.

## Macro retracement

Production macro retracement is automatic only for immediately consecutive opposite-direction source macro legs sharing the same pivot:

`A->B`, then `B->C`.

Formula:
- `reference_delta=P_B-P_A`
- `candidate_delta=P_C-P_B`
- `candidate_vs_reference_pct=100*abs(candidate_delta)/abs(reference_delta)`
- `d_ref=sign(reference_delta)`
- `opposing_retracement_abs=max(0,-d_ref*candidate_delta)`
- `retracement_pct=100*opposing_retracement_abs/abs(reference_delta)`.

A/B/C are macro anchors. Continuation direction would yield retracement 0, but the first-pass production set includes the approved adjacent opposite-direction macro pairs only.

The approved source contains 118 such relationships. No arbitrary triples and no Fibonacci labels.
