# Volume, Volatility, and Provenance Contract

## Purpose

Preserve volume and volatility information across approved resolutions while making source availability, formulas, missingness, and provenance explicit.

## ADDED Requirements

### Requirement: Raw volume is preserved at every available target resolution

For each target candle resolution with valid source volume, the system SHALL preserve raw volume.

If the approved source provides additional native fields such as quote volume, trade count, or taker-side volume, those fields MAY be preserved under source-accurate names and provenance.

The system SHALL NOT fabricate unavailable volume fields.

### Requirement: Rolling volume behavior is measurable

For approved rolling durations supported by the calculation resolution and coverage, the system SHALL support numeric summaries including volume sum, mean, median, change versus the previous equal-duration window, and ratio versus the previous equal-duration window where the denominator is non-zero.

The system SHALL also preserve enough information to compare volume on up, down, and zero-change finer bars within an observation without assigning accumulation, distribution, absorption, or exhaustion labels.

### Requirement: Effort-versus-result measurements remain numeric

Where defined, the system MAY calculate volume relative to absolute net displacement and other explicitly documented price-result denominators.

Zero or undefined price-result denominators SHALL produce null ratios rather than infinities or silently substituted zeros.

Such fields SHALL be described as numeric effort-versus-result measurements and SHALL NOT be labeled as absorption, exhaustion, or another market-state conclusion.

### Requirement: True Range uses the explicit standard formula

For candle `t` with previous close available:

`TR_t = max(high_t - low_t, abs(high_t - close_(t-1)), abs(low_t - close_(t-1)))`.

The first eligible candle without a previous close SHALL follow an explicitly documented null/initialization convention in the feature dictionary.

### Requirement: ATR14 SMA and Wilder ATR are both preserved

The system SHALL calculate and store both `atr14_sma` and `atr14_wilder` when at least 14 required observations are available under the approved source-resolution contract.

`atr14_sma` SHALL use the arithmetic mean of the applicable True Range values.

After its documented initialization, Wilder ATR SHALL update as:

`ATR_t = ((13 * ATR_(t-1)) + TR_t) / 14`.

Values before sufficient initialization SHALL be null rather than silently backfilled with another formula.

### Requirement: Realized volatility remains a numeric measurement

Where rolling realized volatility is calculated, log returns SHALL be based on consecutive closes:

`r_i = ln(close_i / close_(i-1))`.

The exact statistical estimator, window, minimum observation count, and annualization behavior, if any, SHALL be explicitly documented before implementation. The system SHALL NOT silently choose these unresolved details.

### Requirement: Compression and expansion remain numeric

The system MAY preserve rolling high-low width, True Range/ATR evolution, candle-range evolution, and current-versus-previous equal-window ratios/deltas as objective numeric measurements.

The first pass SHALL NOT convert those values into threshold-based `compression` or `expansion` market-state labels.

### Requirement: Source inventory precedes assumptions about coverage

Before full implementation, the pipeline SHALL inventory the actual local candle sources for `1D`, `4H`, `1H`, `15m`, and `5m`, and any available finer source such as `1m` used for validation or later focused research.

The inventory SHALL record instrument/venue identity, source type, timeframe, first timestamp, last timestamp, row count, and detected gaps where feasible.

The system SHALL NOT infer from a derived-feature manifest alone that all higher timeframes were built from a particular finer source.

### Requirement: Missing data is not synthesized silently

The research pipeline SHALL preserve actual source gaps and coverage limitations. It SHALL NOT synthesize missing market history or download additional data without explicit approval.

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

Fields available using only data closed/known at the observation time SHALL be identified as causal.

Fields requiring a known future endpoint, future price path, or completed macro leg SHALL be identified as retrospective.

Retrospective fields SHALL NOT be exposed or named as though they were available to a live strategy at the historical observation time.
