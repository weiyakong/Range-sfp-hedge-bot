# Stage 2I-A pivot structure review

## 1. Executive factual summary

This review analyzes the frozen Stage 2I-A population from commit `71b6158a61503fde9145f3565fe0be3149bbab76`: 15,445 complete canonical BTCUSDT futures 4H candles and all 4,450 strict raw pivot events (2,243 HIGH, 2,207 LOW, 150 dual HIGH+LOW candles). Stage 2I-A was not rebuilt or modified.

The raw population does not exhibit an obvious empty interval that separates micro fluctuations from independent reactions. Across the central 98% of opposite-pivot observations, the largest adjacent gap is only 0.187 IQR for percentage move and 0.078 IQR for absolute move. This is evidence of a broad, largely continuous spectrum—not proof that latent regimes do not exist.

The typical opposite-pivot movement is short but highly dispersed: median 4 bars / 16 hours and 3.25%, with a 10–90% range of 1–9 bars and 1.33–7.93%. The outgoing/incoming move ratio has median 0.883 and IQR 0.563–1.482. These overlapping distributions do not supply a defensible natural cutoff.

Absolute movement is strongly price-era dependent: yearly median absolute opposite-pivot move ranges from 272.8 USDT to 2,638.0 USDT. Percentage medians are much less scale-sensitive but still vary from 2.48% to 5.47%. Median duration is stable at 4 bars in every year except 2025 (3 bars), and event density varies in a narrower band of 27.49–31.24 events per 100 bars.

Dual events are not gap artifacts. A dual candle is necessarily an outside candle relative to all four comparison candles. Empirically, its median range is 2.49 times the four-neighbor mean; relative volume is 2.50 and relative trade count is 2.25. Median open gap is zero. Relative to non-dual pivot candles, these ratios are approximately 1.95, 1.97, and 1.84 times larger, respectively.

No Stage B labels, thresholds, clusters, structural zones, trends, or trading rules are created here.

## 2. Population and causal boundary

| Item | Value |
|---|---:|
| Complete 4H candles | 15,445 |
| Raw HIGH events | 2,243 |
| Raw LOW events | 2,207 |
| Total raw events | 4,450 |
| Pivot-bearing candles | 4,300 |
| Dual candles | 150 |
| Consecutive event pairs | 4,449 |
| Opposite-pivot diagnostic pairs | 4,449 |

Stage A causal fields remain available at `available_from`, the close of the second right-hand candle. Next-pivot, departure, breach-time, and full post-pivot path measures in this review are explicitly retrospective diagnostics. They cannot become live predictors merely because they are useful for describing the population.

The event-level sequence contains 150 zero-time HIGH→LOW pairs from dual candles. `HIGH` then `LOW` is only the Stage A storage tie-break; 4H data contain no intrabar ordering evidence. Positive-gap transitions are therefore reported separately.

## 3. Pivot-density distributions

For clarity, `bar_gap` is the difference between pivot candle indices. Thus 0 means the same dual candle, 1 means adjacent candles, and 2 means one candle lies between the two pivot candles.

| Metric | p10 | p25 | Median | p75 | p90 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| All event-pair bar gap | 1 | 2 | 3 | 5 | 6 | 10 | 16 |
| Positive bar gap only | 1 | 2 | 3 | 5 | 6 | 10 | 16 |
| Positive time gap, hours | 4 | 8 | 12 | 20 | 24 | 40 | 64 |

Explicit gap buckets:

| Relationship | Count | Share |
|---|---:|---:|
| Same dual candle | 150 | 3.37% |
| Adjacent candles | 560 | 12.59% |
| One intervening bar | 802 | 18.03% |
| Two intervening bars | 1,039 | 23.35% |
| 3–5 intervening bars | 1,551 | 34.86% |
| 6–12 intervening bars | 343 | 7.71% |
| More than 12 intervening bars | 4 | 0.09% |

Positive-gap transitions:

| Transition | N | Median bars | IQR bars | p90 | Max |
|---|---:|---:|---:|---:|---:|
| HIGH → LOW | 1,570 | 3 | 2–4 | 6 | 13 |
| LOW → HIGH | 1,719 | 3 | 2–5 | 6 | 16 |
| HIGH → HIGH | 523 | 4 | 3–5 | 7 | 13 |
| LOW → LOW | 487 | 4 | 3–5 | 7 | 15 |

Same-type transitions cannot occur closer than 3 bars under the strict five-bar definition; opposite types can occur on adjacent candles. This is a mechanical property of the raw generator, not a structural classification.

## 4. Opposite-pivot movement and duration

Each row links a raw pivot to its next strictly later opposite-type raw pivot. The paths overlap by design; this is a diagnostic relation, not an alternating segmentation.

| Metric | p10 | p25 | Median | p75 | p90 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Absolute move, USDT | 259.0 | 544.0 | 1,339.97 | 2,543.3 | 4,157.14 | 8,856.34 | 20,980.5 |
| Absolute move, % | 1.33 | 2.04 | 3.25 | 5.24 | 7.93 | 19.01 | 64.86 |
| Absolute log move | 0.0133 | 0.0204 | 0.0325 | 0.0526 | 0.0792 | 0.1898 | 0.4999 |
| Duration, bars | 1 | 2 | 4 | 6 | 9 | 15 | 26 |
| Duration, days | 0.17 | 0.33 | 0.67 | 1.00 | 1.50 | 2.50 | 4.33 |
| Price excursion, % of start | 1.63 | 2.38 | 3.68 | 5.74 | 8.86 | 20.51 | 74.02 |
| Close-path efficiency | 0.152 | 0.358 | 0.683 | 1.000 | 1.000 | 1.000 | 1.000 |

Central-98% continuity diagnostics found no large empty interval: the largest adjacent percentage-move gap is 0.60 percentage points (0.187 IQR), and the largest absolute-move gap is 156.1 USDT (0.078 IQR). Duration is discrete in four-hour bars and therefore naturally advances in one-bar steps.

Canonical Stage 2 definitions were reused unchanged for close-path efficiency, direction-normalized persistence, nonzero-step alternation, body overlap, and retracement from the internal favorable extreme. Opposite paths have median persistence 0.333, median alternation 0.5, and median close-path efficiency 0.683. The canonical `end_retention` ratio is unstable when maximum favorable excursion is nearly zero, so its extreme tail must not be interpreted without a denominator policy.

## 5. Micro-fluctuation diagnostic distributions

These are raw diagnostics, not candidate rules.

| Diagnostic | p10 | p25 | Median | p75 | p90 | p99 |
|---|---:|---:|---:|---:|---:|---:|
| Incoming opposite move, % | 1.44 | 2.18 | 3.51 | 5.64 | 8.86 | 20.58 |
| Outgoing opposite move, % | 1.33 | 2.04 | 3.25 | 5.24 | 7.93 | 19.01 |
| Outgoing / incoming move ratio | 0.365 | 0.563 | 0.883 | 1.482 | 2.375 | 8.445 |
| Incoming duration, bars | 1 | 2 | 4 | 6 | 9 | 16 |
| Outgoing duration, bars | 1 | 2 | 4 | 6 | 9 | 15 |
| Same-type extension, % | -3.36 | -1.37 | -0.10 | 1.25 | 3.31 | 11.78 |
| Five-bar context span, % | 1.45 | 2.08 | 3.15 | 4.64 | 6.91 | 14.79 |
| Three-event price span, % | 1.80 | 2.63 | 4.14 | 6.47 | 9.93 | 21.62 |
| Five-event price span, % | 2.80 | 4.01 | 5.93 | 8.99 | 13.22 | 28.42 |
| Incoming path efficiency | 0.176 | 0.412 | 0.714 | 1.000 | 1.000 | 1.000 |
| Outgoing path efficiency | 0.152 | 0.358 | 0.683 | 1.000 | 1.000 | 1.000 |

Strict breach means a later candle exceeds a HIGH pivot price or falls below a LOW pivot price. Because the two confirmation candles must remain inside the strict pivot extreme, breach cannot occur before bar +3. Of all 4,450 events, 4,286 eventually breach within available history and 164 are right-censored or never breach. Shares of the full population breached by +3/+6/+12/+24 bars are 14.63%, 37.08%, 55.66%, and 69.03%. Among observed breaches, the median is 9 bars, but the tail reaches thousands of bars; this variable therefore mixes rapid failure, long survival, and right-edge censoring.

“Locally trapped” is intentionally not converted into a boolean. The review instead preserves five-bar span, 6/12-bar post-event range, close displacement, and 3/5-event price-span distributions. A band width and time horizon would be a Stage B methodology choice.

Likewise, no single field is named “retracement fraction.” The outgoing/incoming pivot-move ratio, canonical internal-extreme retracement, close-path geometry, and prior-same-type extension are all reported separately because they use different denominators and answer different questions.

## 6. Dual HIGH+LOW candles

All 150 dual candles satisfy both strict conditions and are retained as 300 events. They are outside all four neighboring candles by definition.

| Diagnostic | Dual median | Non-dual pivot-candle median | Dual / non-dual |
|---|---:|---:|---:|
| Candle range, % | 2.607 | 1.783 | 1.462 |
| Range / four-neighbor mean | 2.490 | 1.278 | 1.948 |
| Volume / four-neighbor mean | 2.497 | 1.267 | 1.971 |
| Trades / four-neighbor mean | 2.247 | 1.221 | 1.840 |

The dual candle’s median body occupies 31.4% of its range; median upper and lower wick shares are 31.6% and 32.9%. Thus the population is not explained by large bodies alone. Median open gap from the previous close is 0.000%; its 1–99% interval is approximately −0.012% to +0.014%, so exchange-session gaps are not the mechanism. The factual picture is an unusually broad outside candle with elevated activity relative to immediate neighbors. The data do not decide whether Stage B should treat its two events separately, jointly, or defer them.

## 7. Price-scale and year comparison

| Year | Events / 100 bars | Pivot candles / 100 bars | Median abs move, USDT | Median move, % | Median duration, bars |
|---|---:|---:|---:|---:|---:|
| 2019* | 31.24 | 29.93 | 272.78 | 3.20 | 4 |
| 2020 | 29.14 | 27.91 | 351.33 | 3.48 | 4 |
| 2021 | 27.53 | 26.94 | 2,585.73 | 5.47 | 4 |
| 2022 | 28.90 | 27.95 | 988.00 | 3.57 | 4 |
| 2023 | 30.96 | 29.36 | 719.70 | 2.48 | 4 |
| 2024 | 28.05 | 27.46 | 2,167.10 | 3.33 | 4 |
| 2025 | 28.49 | 27.95 | 2,638.05 | 2.61 | 3 |
| 2026* | 27.49 | 26.24 | 1,962.00 | 2.69 | 4 |

`*` 2019 and 2026 are partial calendar years in the canonical coverage.

Absolute movement is strongly scale-dependent; its largest yearly median is about 9.7 times the smallest. Percentage movement reduces but does not eliminate era dependence: 2021 remains materially larger than 2023/2025/2026. Duration is comparatively stable. Density changes less than movement scale, though partial-year and market-regime composition prevent treating yearly differences as a causal result.

## 8. Representative chart review

All charts use canonical 4H candles and plot every raw HIGH/LOW in the selected window. No structural zones, trend labels, or signals are drawn.

| Chart | Window | Selection fact |
|---|---|---|
| `chart_high_pivot_density.svg` | 2025-12-06 to 2025-12-21 | 37 events in 90 bars; net close move 0.84% |
| `chart_low_pivot_density.svg` | 2024-06-19 to 2024-07-04 | 18 events in 90 bars |
| `chart_high_directional_efficiency_with_raw_pivots.svg` | 2020-12-23 to 2021-01-07 | 68.38% absolute close move with 25 raw events |
| `chart_low_efficiency_high_path_window.svg` | 2021-06-05 to 2021-06-20 | 0.06% net close move, 29.42% span, 24 events |
| `chart_large_two_sided_opposite_move.svg` | 2020-03-05 to 2020-03-20 | large two-sided opposite-pivot movement around the March dislocation |
| `chart_2026_human_calibration_area.svg` | 2026-06-01 to 2026-07-16 | fixed visual-calibration period; 73 events on 69 pivot candles |

Selection metrics are diagnostic conveniences for chart coverage, not market-state labels. Visual QA confirms that strong directional movement can contain multiple mathematically valid internal pivots, while low-net/high-path windows can contain frequent alternating extrema.

## 9. 2026 human-calibration observations

The approximate price intervals are queried only by raw pivot price. They are not zones or labels.

| Price interval | Events | HIGH / LOW | Dual events | Median incoming move | Median outgoing move | Median bars to breach* |
|---|---:|---:|---:|---:|---:|---:|
| 59.0–60.5k | 6 | 0 / 6 | 0 | 13.21% | 5.37% | 111 |
| 61.5–62.5k | 15 | 2 / 13 | 1 | 4.23% | 2.87% | 16.5 |
| 66.5–69.0k | 46 | 23 / 23 | 2 | 3.36% | 2.90% | 6 |

`*` Median among events that eventually breach within available coverage.

The 59.0–60.5k interval contains only raw LOW events in 2026, but they occur from February through July and have very heterogeneous incoming moves (approximately 2.0–24.6%). The 61.5–62.5k interval is also LOW-heavy, while 66.5–69.0k is balanced. The June–July chart visibly contains both dense small oscillations and larger swings; raw geometry alone does not authorize calling one set micro and another independent.

## 10. What the data already support

- Raw pivots form a dense multiscale population: 28.81 events per 100 complete bars overall.
- Opposite-pivot move, duration, efficiency, persistence, and departure ratios overlap broadly rather than separating at an obvious empty interval.
- Same-type and opposite-type transition densities differ mechanically under the strict five-bar definition.
- Absolute move is unsuitable for cross-era comparison without an explicit scale decision; percentage/log measures reduce but do not erase regime dependence.
- Dual events are outside-range, elevated-activity candles rather than ordinary gap events.
- Future departure, next opposite pivot, breach time, and full outgoing path add retrospective information but are not known at `available_from`.
- Real charts confirm the motivating ambiguity: internal raw pivots appear inside both directional and low-efficiency paths.

## 11. What the data do not support

- No defensible micro/independent boundary has been found.
- No natural threshold, ATR cutoff, fixed-percent cutoff, or zone width is established.
- No Stage B label semantics are established.
- No claim is made that a price interval is support, resistance, a range boundary, or a repeat-reaction zone.
- No trend, SFP, Volume Profile, Order Block, Fibonacci, classifier, cluster solution, or trading result is produced.
- Visual examples cannot substitute for an explicit causal or retrospective label contract.

## 12. OPEN METHODOLOGY QUESTIONS

1. **Dual-event representation.** Keep two unordered same-candle events, introduce a distinct outside-bar state, or defer them? This changes transition counts and any sequence objective.
2. **Retracement denominator.** Use outgoing/incoming pivot-price move, close-path displacement, or prior same-type extreme? Each answers a different question; the review keeps the components separate.
3. **Trapped/invalidated horizon and scale.** Use fixed bars/percent, causal rolling volatility, or next-event time? Any choice introduces thresholds and changes regime sensitivity.
4. **Target time.** Is Stage B a retrospective movement segmentation, a label known at pivot confirmation, or a retrospective target followed by a separately evaluated causal approximation? This determines whether next-pivot information is legal.

## 13. Unranked Stage B research designs

### Design A — two-sided reaction prominence

- Idea: retrospectively compare incoming and next opposite-pivot movement, duration, efficiency, and canonical path geometry.
- Stage A fields: `causal__previous_opposite__*`, `causal__from_previous_opposite__*`, `postevent__next_opposite__*`.
- Advantage: directly describes whether a pivot separates two measurable moves.
- Risk: future leakage in live use; same-type intervening pivots and dual candles complicate pair identity.
- Arbitrary choice: minimum ratio, movement, duration, or efficiency.
- Scale: low with percent/log features, high with absolute move.
- Causality: retrospective until the next opposite pivot is confirmed.
- Likely errors: slow departures, volatile outside bars, nested same-type pivots.

### Design B — confirmation-window independence

- Idea: use the incoming path plus the two right-hand candles already required for strict pivot confirmation.
- Stage A fields: prior-opposite geometry and `causal__bar_-2__*` through `causal__bar_+2__*`.
- Advantage: fully available at `available_from`.
- Risk: two bars may be too short for slow reactions and may favor volatility spikes.
- Arbitrary choice: early-departure ratio/percentile and minimum context conditions.
- Scale: moderate unless distances are percentage/log or causally normalized.
- Causality: causal at `available_from`.
- Likely errors: delayed reversals, wick-only pivots, brief bounces that fail on bar +3.

### Design C — causal historical prominence

- Idea: compare incoming movement, duration, efficiency, volatility, activity, and same-type extension with rolling distributions frozen before each `available_from`.
- Stage A fields: causal prior-pivot, prior-same, local geometry, and immediate-candle fields.
- Advantage: adapts to price scale and evolving volatility.
- Risk: lookback choice controls results; early history is sparse; regime shifts make old reference data stale.
- Arbitrary choice: historical window and percentile boundary.
- Scale: low to moderate with percentage/log inputs.
- Causality: causal only if reference distributions exclude all later observations.
- Likely errors: early samples, abrupt regime shifts, meaningful low-volatility turns.

### Design D — retrospective sequence segmentation

- Idea: model the complete raw-pivot chain and merge nested oscillations under an explicit global segmentation objective; study any causal approximation separately.
- Stage A fields: event type/price/index, neighbor relations, and local path geometry.
- Advantage: directly addresses nested raw pivots and sequence consistency.
- Risk: the objective can encode the desired answer; global optimization is future-dependent; dual events need a contract.
- Arbitrary choice: merge/complexity penalty and movement scale.
- Scale: depends on absolute versus percentage/normalized objective.
- Causality: retrospective by default.
- Likely errors: legitimate nested reactions, long sideways structures, sharp outside bars.

The four designs are intentionally not ranked and none is implemented.

## 14. Artifacts and QA

Machine-readable summary:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_a_raw_4h_pivots/stage2i_a_pivot_structure_review.json`

Tables, charts, review manifest, progress state, and checksums:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_a_raw_4h_pivots/pivot_structure_review/`

`review_data_dictionary.json` states the row/key contract for every CSV and marks every pivot diagnostic as causal or post-event.

| Requirement | Implementation/output | Verification |
|---|---|---|
| Density and transition distributions | `consecutive_pivot_pairs.csv`, JSON summary, histogram/ECDF | exact pair count and nonnegative chronology |
| Opposite-pivot geometry | `opposite_pivot_pairs.csv` | forward-only pairs; efficiency bounds |
| Micro diagnostics | `pivot_diagnostics.csv` | Stage A path efficiency independently reproduced |
| Dual analysis | dual and all-pivot geometry CSVs | 150 unique candles; strict positive extensions |
| Year/scale comparison | `year_comparison.csv`, JSON year distributions | candle/event totals reconcile |
| Real chart review | six deterministic SVGs | canonical candles, all in-window pivots, visual inspection |
| Causal separation | `review_data_dictionary.json` | dedicated unit test |

QA verifies canonical and Stage A checksums/populations, unique event IDs, exact pair counts, nonnegative chronology, dual zero-gap integrity, forward opposite pairs, bounded efficiencies, 150 unique dual candles, positive dual extensions, and independent reproduction of Stage A incoming close-path efficiency. Real-data smoke and production runs passed. SVGs were rendered and visually inspected. Static type checking is `NOT CONFIGURED` in this repository; syntax compilation and annotated public functions were checked without adding a dependency.
