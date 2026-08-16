# Volume, Volatility, and Provenance Contract

## Purpose

Preserve volume and volatility information across approved resolutions while making source availability, formulas, missingness, and provenance explicit.

## ADDED Requirements

### Requirement: Raw volume is preserved at every available target resolution

For each target candle resolution with valid source volume, the system SHALL preserve raw volume.

If the approved source provides additional native fields such as quote volume, trade count, or taker-side volume, those fields MAY be preserved under source-accurate names and provenance.

The system SHALL NOT fabricate unavailable volume fields.

### Requirement: Derived candle volume is additive only across complete same-source constituents

For a derived candle built from canonical finer candles, base volume SHALL be:

`derived_volume = sum(constituent_volume)`

only when all required constituent candles are present, belong to the same approved source segment, and the source-native volume field is additive.

Any additional additive native fields such as quote volume, trade count, or taker-side volume MAY be summed under their source-accurate names when their source semantics support addition.

A derived candle SHALL NOT silently sum volume across a spot/futures source boundary or across an incomplete constituent set. Incomplete-window diagnostics MAY preserve observed-only sums under explicitly `observed_only_*` names, but those values SHALL NOT be exposed as complete derived volume.

### Requirement: Rolling volume behavior is measurable

For approved rolling durations supported by the calculation resolution and coverage, the system SHALL support numeric summaries including volume sum, mean, median, change versus the previous equal-duration window, and ratio versus the previous equal-duration window where the denominator is non-zero.

The system SHALL also preserve enough information to compare volume on objectively defined finer-bar price-direction groupings without assigning accumulation, distribution, absorption, or exhaustion labels. The exact grouping convention SHALL be explicit in the feature dictionary and SHALL NOT be inferred from an ambiguous `up_bar` or `down_bar` name.

### Requirement: Effort-versus-result measurements remain numeric

Where defined, the system MAY calculate volume relative to absolute net displacement and other explicitly documented price-result denominators.

Zero or undefined price-result denominators SHALL produce null ratios rather than infinities or silently substituted zeros.

Such fields SHALL be described as numeric effort-versus-result measurements and SHALL NOT be labeled as absorption, exhaustion, or another market-state conclusion.

### Requirement: True Range uses the explicit standard formula

For candle `t` with previous close available within the same continuous source segment:

`TR_t = max(high_t - low_t, abs(high_t - close_(t-1)), abs(low_t - close_(t-1)))`.

The first eligible candle of a source segment, or a candle following a real data gap, SHALL follow an explicitly documented null/initialization convention in the feature dictionary. A previous close from another market type/source segment SHALL NOT be used.

### Requirement: ATR14 SMA and Wilder ATR are both preserved

The system SHALL calculate and store both `atr14_sma` and `atr14_wilder` when at least 14 required observations are available continuously under the approved source-resolution contract.

`atr14_sma` SHALL use the arithmetic mean of the applicable True Range values.

After its documented initialization, Wilder ATR SHALL update as:

`ATR_t = ((13 * ATR_(t-1)) + TR_t) / 14`.

Values before sufficient initialization, after a source-boundary reset, or across a data gap SHALL be null until the required continuous initialization history is available rather than silently backfilled with another formula.

### Requirement: Realized volatility uses an explicit non-annualized log-return contract

For an approved observation containing consecutive closed prices `P_0 ... P_n` from one continuous source segment, strictly positive prices SHALL define log returns:

`r_i = ln(P_i / P_(i-1))`.

When at least two constituent candles provide at least one valid consecutive log return, the system SHALL calculate:

- `realized_variance = sum(r_i^2)`
- `realized_volatility = sqrt(sum(r_i^2))`

The system SHALL NOT annualize realized volatility in this research pass.

For cross-duration comparison, when the observation duration is positive in days, the system SHALL additionally support:

`realized_volatility_per_sqrt_day = realized_volatility / sqrt(duration_days)`.

Every realized-volatility field SHALL identify the observation duration and calculation resolution.

If an observation contains a required candle gap, crosses a source boundary, contains a non-positive required price, or otherwise lacks the complete constituent sequence, the complete realized-volatility value SHALL be null. A separately named observed-only diagnostic MAY be retained but SHALL be marked incomplete and SHALL NOT bridge the missing/source-transition interval.

### Requirement: Compression and expansion remain numeric

The system MAY preserve rolling high-low width, True Range/ATR evolution, candle-range evolution, and current-versus-previous equal-window ratios/deltas as objective numeric measurements.

The first pass SHALL NOT convert those values into threshold-based `compression` or `expansion` market-state labels.

### Requirement: Source inventory precedes assumptions about coverage

Before full implementation, the pipeline SHALL inventory the actual local candle sources for `1D`, `4H`, `1H`, `15m`, and `5m`, and any available finer source such as `1m` used for canonical construction, validation, or later focused research.

The inventory SHALL record instrument/venue identity, source type, timeframe, first timestamp, last timestamp, row count, and detected gaps where feasible.

The system SHALL NOT infer from a derived-feature manifest alone that all higher timeframes were built from a particular finer source.

### Requirement: Missing data is not synthesized silently

The research pipeline SHALL preserve actual source gaps and coverage limitations. It SHALL NOT synthesize missing market history or download additional data without explicit approval.

### Requirement: Sequential calculations do not cross source boundaries

Every canonical candle SHALL belong to an explicit continuous `source_segment_id` that identifies at minimum venue, market type, source identity, and a continuous coverage segment.

Sequential calculations including close-to-close returns, log returns, True Range, ATR, realized volatility, rolling speed, path, overlap pairs, alternation, and previous-window comparisons SHALL NOT treat candles from different `source_segment_id` values as one continuous sequence.

The spot-to-futures transition MAY be stored as a separate source-transition diagnostic, but the price difference between the last spot candle and first futures candle SHALL NOT enter ordinary market-path, volatility, overlap, ATR, or rolling-feature calculations.

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
