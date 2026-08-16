# Volume, Volatility, and Provenance Contract

## Purpose

Preserve volume and volatility information across approved resolutions while making source availability, formulas, missingness, and provenance explicit.

## ADDED Requirements

### Requirement: Raw volume is preserved at every available target resolution

For each target candle resolution with valid source volume, the system SHALL preserve raw volume.

If the approved source provides additional native fields such as quote volume, trade count, or taker-side volume, those fields MAY be preserved under source-accurate names and provenance.

The system SHALL NOT fabricate unavailable volume fields.

### Requirement: Derived candle volume is additive only across complete same-source constituents

For a derived candle built from canonical finer candles:

`derived_volume = sum(constituent_volume)`

only when all required constituent candles are present, belong to the same approved continuous source segment, and the source-native volume field is additive.

Additional additive native fields such as quote volume, trade count, or taker-side volume MAY be summed under source-accurate names when source semantics support addition.

A derived candle SHALL NOT sum volume across a source-segment boundary or incomplete constituent set. Observed-only diagnostics MAY use explicit `observed_only_*` names but SHALL NOT be exposed as complete volume.

### Requirement: Volume direction is preserved under two distinct mechanical conventions

Body-direction convention:

- `body_direction = up` when `close > open`;
- `body_direction = down` when `close < open`;
- `body_direction = flat` when `close == open`.

Close-step-direction convention, when a valid temporally adjacent previous close exists in the same continuous source segment:

- `close_step_direction = up` when `close_t > close_(t-1)`;
- `close_step_direction = down` when `close_t < close_(t-1)`;
- `close_step_direction = flat` when equal.

Observation/window summaries SHALL preserve separately named volume totals for body-up/body-down/body-flat and close-step-up/close-step-down/close-step-flat constituent bars where volume is valid.

When total observation volume is positive, corresponding shares SHALL equal each grouped volume total divided by total observation volume. With zero/undefined total volume, shares SHALL be null.

No ambiguous generic `up_volume` or `down_volume` name is permitted without the convention in the field name/dictionary.

### Requirement: Rolling volume behavior uses explicit adjacent-window comparison

For complete rolling window `[t-W,t)` preserve at minimum constituent volume sum, arithmetic mean, and median.

Let `V_cur` be current-window volume sum and `V_prev` the immediately preceding equal complete window `[t-2W,t-W)`:

- `volume_sum_change_vs_prev = V_cur - V_prev`
- `volume_sum_ratio_vs_prev = V_cur / V_prev` when `V_prev > 0`, otherwise null.

Equivalent explicitly named comparisons MAY be retained for mean/median, but SHALL not substitute for the required sum comparison.

The approved body-direction and close-step-direction volume groupings SHALL remain separately inspectable without semantic labels such as accumulation, distribution, absorption, or exhaustion.

### Requirement: Effort-versus-result measurements remain numeric

Where defined, the system MAY calculate volume relative to absolute net displacement and other explicitly documented price-result denominators.

Zero or undefined price-result denominators SHALL produce null ratios rather than infinities or substituted zeros. Such fields SHALL remain numeric and semantically neutral.

### Requirement: True Range requires a valid temporally adjacent previous close

For candle `t` whose previous candle is temporally adjacent, same-resolution, and in the same continuous source segment:

`TR_t = max(high_t - low_t, abs(high_t - close_(t-1)), abs(low_t - close_(t-1)))`.

If no such previous candle exists because of segment start, source boundary, or real gap, `TR_t` SHALL be null. The system SHALL NOT borrow a previous close across that discontinuity.

### Requirement: ATR14 SMA and Wilder ATR have exact initialization

ATR calculations SHALL operate separately per calculation resolution and continuous source segment using valid consecutive non-null TR values.

For `atr14_sma`, once 14 consecutive valid TR values `TR_(t-13)...TR_t` exist:

`atr14_sma_t = mean(TR_(t-13)...TR_t)`.

For Wilder ATR, the first value SHALL be initialized at the same first eligible endpoint as the arithmetic mean of the first 14 consecutive valid TR values:

`atr14_wilder_init = mean(first 14 consecutive valid TR values)`.

Each subsequent temporally adjacent valid candle updates:

`atr14_wilder_t = ((13 * atr14_wilder_(t-1)) + TR_t) / 14`.

A gap/source-boundary discontinuity SHALL reset Wilder state; values remain null until 14 new consecutive valid TR observations reinitialize it.

### Requirement: Realized volatility uses the full observation interval and exact price sequence

For a complete fixed/rolling observation built from complete calculation candles, use the same boundary-aware sequence concept as path:

- `Q0 = observation start price`, equal to the open of the first constituent calculation candle;
- `Q1...Qn = chronological closes of all constituent calculation candles`;
- `Qn = observation end price`.

For strictly positive `Q` values:

`r_i = ln(Q_i / Q_(i-1))`, for `i=1...n`.

Then:

- `realized_variance = sum(r_i^2)`
- `realized_volatility = sqrt(realized_variance)`.

The system SHALL NOT annualize realized volatility in this research pass.

When observation duration in days is positive:

`realized_volatility_per_sqrt_day = realized_volatility / sqrt(duration_days)`.

Every RV field SHALL identify observation duration and calculation resolution.

A complete RV metric SHALL be null if any required constituent candle is missing, the observation crosses a source segment, a required price is non-positive, or the complete sequence is otherwise unavailable. Observed-only diagnostics MAY be retained under explicitly incomplete names but SHALL NOT bridge the discontinuity.

### Requirement: Numeric compression/expansion components are mandatory and unlabeled

For each complete approved observation/calculation-resolution combination, the first pass SHALL preserve objective components sufficient to study volatility contraction/expansion without assigning a state label.

At minimum preserve:

- `observation_high_low_width = observation_high - observation_low`;
- `observation_high_low_width_pct_start = 100 * observation_high_low_width / P0` when `P0 > 0`;
- `observation_log_high_low_width = ln(observation_high / observation_low)` when prices are positive;
- arithmetic mean and median of constituent `full_range`;
- arithmetic mean and median of constituent `log_full_range` where defined;
- arithmetic mean and median of constituent valid True Range;
- arithmetic mean of constituent valid `normalized_true_range` where defined;
- endpoint `atr14_sma` and `atr14_wilder` when initialized.

For rolling observations, let any current numeric component `X_cur` be compared with the same component on the immediately preceding equal complete window `X_prev`:

- `X_delta_vs_prev = X_cur - X_prev`;
- `X_ratio_vs_prev = X_cur / X_prev` when `X_prev != 0`, otherwise null.

Only components explicitly enumerated in the feature dictionary SHALL receive such delta/ratio fields; the implementation SHALL NOT invent a composite compression/expansion score or threshold label.

### Requirement: Source inventory precedes assumptions about coverage

Before full implementation, the pipeline SHALL inventory actual local/approved candle sources for target resolutions and any finer source such as `1m` used for canonical construction, validation, or later research.

The inventory SHALL record instrument/venue identity, market type, source type, timeframe, first timestamp, last timestamp, row count, and detected gaps where feasible.

The system SHALL NOT infer source construction from a derived-feature manifest alone.

### Requirement: Missing data is not synthesized silently

The research pipeline SHALL preserve actual source gaps and coverage limitations. It SHALL NOT synthesize missing market history or download additional data without explicit approval.

If an approved source-repair pass is performed, missing candles MAY be reconstructed only from lower-level official data for the same venue, instrument, and market type under a deterministic documented aggregation rule.

A reconstructed candle SHALL preserve distinct reconstruction provenance, contributing source interval/count, and validation status. It SHALL NOT be relabeled as an original archived kline.

Futures data SHALL NOT reconstruct spot candles and spot data SHALL NOT reconstruct futures candles.

If same-market lower-level official data is incomplete/unavailable, the gap SHALL remain documented. Interpolation, forward/backward fill, synthetic candles, and cross-market substitution are prohibited.

### Requirement: Sequential calculations use canonical source-segment semantics

`source_segment_id` SHALL use the continuity definition in the atomic-market-data contract. It represents one continuous market sequence, not a raw archive filename, local path, download batch, or row-level provenance label.

Sequential calculations including close-step returns, log returns, True Range, ATR, realized volatility, rolling speed, path, overlap pairs, alternation, and previous-window comparisons SHALL NOT treat different source segments or non-adjacent timestamps as one continuous sequence.

A change from one monthly/daily archive part to another SHALL NOT itself reset sequential state when market continuity remains valid. Likewise, a validated reconstructed candle from approved same-market lower-level official data SHALL NOT itself force a segment reset when it fully repairs the continuity.

The spot-to-futures transition MAY be stored as a separate source-transition diagnostic, but its price difference SHALL NOT enter ordinary path, volatility, overlap, ATR, volume-window comparison, or rolling-feature calculations.

### Requirement: Feature dictionary is mandatory

Every exported research feature SHALL have a dictionary entry containing at minimum:

- feature name;
- human-readable meaning;
- exact formula or derivation rule;
- units;
- source timeframe/resolution;
- calculation timeframe/resolution;
- fixed or rolling semantics where applicable;
- causal or retrospective availability;
- when the value becomes known;
- null meaning;
- source/provenance.

### Requirement: Causal and retrospective fields remain distinguishable

Fields available using only data closed/known at observation time SHALL be identified as causal.

Fields requiring a known future endpoint, future path, or completed macro leg SHALL be identified as retrospective and SHALL NOT be exposed/named as live-available historical features.
