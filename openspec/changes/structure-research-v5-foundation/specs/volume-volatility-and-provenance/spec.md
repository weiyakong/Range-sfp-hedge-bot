# Volume, Volatility, and Provenance Contract

## Purpose

Preserve volume and volatility information across approved resolutions while making source availability, formulas, missingness, and provenance explicit.

## ADDED Requirements

### Requirement: Raw volume and valid native additive fields are preserved

For each valid canonical candle resolution, preserve raw volume. Additional native fields such as quote volume, trade count, or taker-side volume MAY be preserved only under source-accurate names when actually supplied/validated.

Unavailable fields SHALL NOT be fabricated.

### Requirement: Derived target volume is additive only across complete same-segment constituents

For complete derived target candle:

`volume = sum(constituent_volume)`.

Additional source-native additive fields MAY be summed only when semantics support addition.

Incomplete/boundary target intervals have null complete volume. `observed_only_*` diagnostics may be stored explicitly.

### Requirement: Volume direction has two independent mechanical conventions

Body direction:

- up when `close>open`;
- down when `close<open`;
- flat when equal.

Close-step direction requires valid adjacent previous close in same canonical segment:

- up when `close_t>close_(t-1)`;
- down when lower;
- flat when equal.

Observation summaries preserve:

- `volume_body_up`, `volume_body_down`, `volume_body_flat` and shares;
- `volume_close_step_up`, `volume_close_step_down`, `volume_close_step_flat` and shares.

Shares use `volume_sum` denominator when >0; else null.

No ambiguous generic `up_volume/down_volume` names.

### Requirement: Rolling volume comparison uses canonical names and adjacent equal windows

For current complete rolling `[t-W,t)` and immediately previous complete `[t-2W,t-W)`:

- `volume_sum_change_vs_prev = V_cur - V_prev`
- `volume_sum_ratio_vs_prev = V_cur/V_prev` when `V_prev>0`, else null.

Current window also preserves `volume_sum`, arithmetic `volume_mean`, and `volume_median`.

Equivalent mean/median comparisons are optional and must be explicitly named/dictionary-declared.

### Requirement: Effort-versus-result remains numeric and neutral

Approved ratios MAY compare volume with explicitly documented price-result denominators. Zero/undefined denominator -> null. No accumulation/distribution/absorption/exhaustion label.

### Requirement: True Range requires valid temporal adjacency

For candle `t` with valid same-resolution adjacent previous close in same segment:

`TR_t = max(high_t-low_t, abs(high_t-close_(t-1)), abs(low_t-close_(t-1)))`.

At segment start/gap/source boundary TR is null. No previous close may be borrowed across discontinuity.

### Requirement: ATR14 SMA and Wilder initialization are exact

Per calculation resolution and source segment:

- `atr14_sma` at first eligible endpoint = mean of first 14 consecutive valid TRs;
- `atr14_wilder` initializes to the same first-14 mean;
- next Wilder value = `((13*prev_atr)+TR_t)/14`.

Gap/boundary resets Wilder state; 14 new consecutive valid TRs are required.

### Requirement: Realized volatility uses the same full-interval Q sequence as close path for fixed/rolling observations

For complete fixed/rolling observation at approved calculation resolution:

- `Q0` = observation start price/open first constituent;
- `Q1...Qn` = chronological constituent closes;
- `Qn` = observation end price.

For positive Q:

`r_i=ln(Q_i/Q_(i-1))`

- `realized_variance=sum(r_i^2)`
- `realized_volatility=sqrt(realized_variance)`
- `realized_volatility_per_sqrt_day=realized_volatility/sqrt(duration_days)` when duration_days>0.

No annualization in this pass.

Any required gap/boundary/nonpositive price -> complete RV null.

Macro RV is not a required first-pass feature because macro source anchors are mixed/resolution-limited and the fixed/rolling boundary sequence cannot be silently reused.

### Requirement: Numeric compression/expansion components use canonical names

For every complete supported fixed/rolling observation/calculation-resolution combination preserve where defined:

- `observation_high_low_width = observation_high-observation_low`
- `observation_high_low_width_pct_start = 100*width/P0` when `P0>0`
- `observation_log_high_low_width = ln(observation_high/observation_low)` for positive prices
- `mean_full_range`, `median_full_range`
- `mean_log_full_range`, `median_log_full_range`
- `true_range_mean`, `true_range_median`
- `normalized_true_range_mean`
- `atr14_sma_at_end`, `atr14_wilder_at_end` where initialized.

For rolling observations, only dictionary-declared components receive:

- `{component}_change_vs_prev = X_cur-X_prev`
- `{component}_ratio_vs_prev = X_cur/X_prev` when `X_prev != 0`.

No composite compression/expansion score or threshold label.

### Requirement: Feature calculation matrices are governed by the schema contract

Fixed, rolling, and macro calculation-resolution applicability SHALL follow the exact matrices in `research-table-schema`.

Macro observations may receive complete canonical volume/TR/activity summaries at approved resolutions where coverage permits, but SHALL NOT receive RV by silent reuse of fixed/rolling semantics.

### Requirement: Source inventory validates canonical timestamp alignment and coverage before features

Inventory/canonicalization SHALL record source identity, market type, source type, timeframe, first/last timestamps, row count, duplicates, invalid numerics, alignment anomalies, and detected gaps.

A source row intended for canonical 1m SHALL start exactly on a UTC minute boundary. Non-minute-aligned rows are explicit anomalies and SHALL NOT be silently rounded into valid candles.

Final canonical gap inventory SHALL be recomputed from validated minute-grid coverage.

### Requirement: Missing market data is never synthesized silently

Canonical history SHALL preserve real gaps.

A missing candle MAY become canonical only when approved same-market lower-level official data directly determine the required OHLCV under an approved deterministic rule.

A diagnostic flat/no-trade bucket created from neighboring values rather than observed within-minute price evidence is synthetic and SHALL remain outside strict canonical data unless a later explicit source-contract change approves that semantics.

Spot cannot repair futures and futures cannot repair spot. No interpolation, forward/backward fill, or third-party substitution.

### Requirement: Sequential calculations use canonical source segments

Returns, close-step volume direction, TR/ATR, RV, rolling speed, path, pair geometry, alternation, and adjacent-window comparisons SHALL require canonical source continuity and exact temporal adjacency.

Archive/package/provenance change alone does not reset state. A real gap or market boundary does.

The spot/futures transition price difference is a diagnostic only and SHALL NOT enter ordinary sequential metrics.

### Requirement: Feature dictionary is mandatory

Every materialized metric has feature-dictionary definition with exact name, meaning, formula, units, source/calculation resolution, observation-kind applicability, availability/available-at, null meaning, and provenance.

### Requirement: Causal and retrospective availability remain distinct

Fixed/rolling fields computed only from closed data through observation end are causal from their documented `available_at`.

Macro endpoint/direction/context fields are retrospective and SHALL NOT be exposed as live-known causal features.
