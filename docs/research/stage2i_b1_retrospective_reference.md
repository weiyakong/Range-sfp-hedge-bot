# Stage 2I-B1 — retrospective structural reference research

## 1. Scope / question

Stage 2I-B1 asks which strict five-bar raw 4H pivots continue to represent distinct movements under progressively coarser retrospective representations, and which disappear as internal fluctuations. This is an offline reference study. It uses realized price paths, creates no live predictor, does not run Stage 2I-B2, and does not assign final MICRO/INDEPENDENT labels.

All realized-path output fields are explicitly `reference__*` or `postevent__*`. Identity/provenance columns are the only unprefixed fields.

## 2. Frozen source population

The only inputs are the canonical BTCUSDT Binance USD-M futures 4H candles and the frozen Stage 2I-A raw pivots.

| Item | Count |
|---|---:|
| Complete canonical 4H candles | 15,445 |
| Raw pivot events | 4,450 |
| HIGH / LOW | 2,243 / 2,207 |
| Dual candles / events | 150 / 300 |
| Non-dual events entering the primary prepass | 4,150 |
| Same-type less-extreme events removed by the deterministic prepass | 924 |
| Primary alternating sequence | 3,226 |
| Interior primary pivots with two-sided Design A support | 3,224 |

Stage 2I-A checksums, the canonical 4H manifest checksums and the Stage 2I-A review checksums are verified before calculation. All 4,450 output IDs reproduce the Stage 2I-A identity and order exactly.

## 3. Why no single Stage-A threshold was used

Stage 2I-A found a broad continuum, material year/price-regime dependence, and no empty interval supporting one universal USDT, percentage, duration or move-ratio cutoff. B1 therefore preserves complete continuous diagnostics, removal hierarchies and parameter sweeps. Every population descriptor below is explicitly diagnostic, not a label contract.

## 4. Design A — exact definition and results

The primary sequence excludes dual events and first makes the non-dual sequence alternating: consecutive same-type HIGHs retain the higher price, and consecutive same-type LOWs retain the lower price. This prepass is deterministic and recorded rather than hidden.

For each interior pivot with adjacent opposite-type pivots:

- `incoming_log = abs(log(pivot_price / left_price))`;
- `outgoing_log = abs(log(right_price / pivot_price))`;
- minimum prominence = `min(incoming_log, outgoing_log)`;
- geometric prominence = `sqrt(incoming_log * outgoing_log)`;
- harmonic prominence = `2 * incoming_log * outgoing_log / (incoming_log + outgoing_log)`;
- balance = `min(incoming_log, outgoing_log) / max(incoming_log, outgoing_log)`.

Incoming/outgoing duration, endpoint-inclusive log close path, path efficiency, directional persistence and alternation are retained separately. No composite score is silently substituted for these components.

| Metric | p10 | p25 | Median | p75 | p90 |
|---|---:|---:|---:|---:|---:|
| Minimum log prominence | 0.01284 | 0.01824 | 0.02728 | 0.04180 | 0.06082 |
| Geometric log prominence | 0.01719 | 0.02489 | 0.03668 | 0.05427 | 0.07865 |
| Two-sided balance | 0.302 | 0.448 | 0.622 | 0.790 | 0.901 |

Minimum versus geometric prominence has Pearson correlation `0.951`; minimum versus harmonic has `0.981`. Formulation choice changes ranks but not the overall continuous shape. The largest adjacent gap in normalized minimum-prominence rank is only `0.00062` (`0.00124` IQR), so Design A does not expose a natural binary split.

## 5. Design B — exact definition and results

Design B applies deterministic sequence simplification to the primary alternating sequence:

1. score each interior pivot from its current left/right structural neighbours;
2. remove the lowest-cost pivot, breaking ties by bar index and event ID;
3. when its neighbours become the same type, retain the more extreme neighbour and record the other at the same iteration/scale;
4. repeat and preserve every removal iteration, effective removal scale, reason and boundary-censored survivor;
5. enforce a non-decreasing effective removal scale with `max(raw_cost, previous_effective_cost)`.

Two variants were retained:

- primary: minimum adjacent absolute-log excursion;
- sensitivity: geometric mean of adjacent absolute-log excursions.

No final scale was selected. Counts below are scale snapshots only.

| Absolute-log scale | Primary retained | Geometric retained |
|---:|---:|---:|
| 0.000 | 3,226 | 3,226 |
| 0.005 | 3,200 | 3,210 |
| 0.010 | 3,078 | 3,150 |
| 0.020 | 2,390 | 2,690 |
| 0.030 | 1,620 | 2,056 |
| 0.050 | 856 | 1,132 |
| 0.075 | 440 | 614 |
| 0.100 | 254 | 360 |
| 0.150 | 120 | 184 |
| 0.250 | 48 | 72 |

The lightest structural operation is the same-type prepass: 924 of 4,150 non-dual events disappear at scale zero. At 0.5% log scale, 950 have disappeared in total. Primary versus geometric survival ranks correlate `0.984`, with top-quartile Jaccard `0.847`. The largest adjacent gap in the primary survival rank is only `0.00048` (`0.00096` IQR), again supporting a continuum rather than a discovered binary boundary.

## 6. Design C — exact definition and results

Design C re-extracts the sequence over three explicit parameter families. At each family, the least-supported current interior turn is removed first and same-type neighbours are consolidated deterministically. All tested scales and structural neighbours are saved.

### C1 — relative-to-previous-move retracement

Support is `outgoing_abs_log_move / incoming_abs_log_move`; tested ratios are 0.1 through 1.0 in 0.1 steps.

Retained counts are `3,214, 3,148, 2,546, 322, 24, 20, 14, 8, 6, 2`. The collapse between 0.3 and 0.4 is a strong cascade sensitivity. This tested formulation has weak correlation with A (`0.168`) and B-primary (`0.174`) and top-quartile Jaccard below `0.007` with either. It is not supported as a standalone reference authority; the result does not reject retracement research generally.

### C2 — absolute log-price reversal scale

Tested absolute-log scales are 0.5%, 1%, 1.5%, 2%, 3%, 5%, 7.5%, 10%, 15% and 25%. Retained counts are `3,200, 3,078, 2,774, 2,390, 1,620, 856, 440, 254, 120, 48`.

This arm is intentionally a threshold view of the same minimum-log removal ordering used by Design B-primary. Its matched-scale retained sets are therefore not independent corroboration. It provides the required survival range/structural-neighbour sweep.

### C3 — local-volatility-normalized sensitivity

The scale denominator is the median true range of the preceding 42 complete 4H bars, excluding the pivot bar. This normalization is a sensitivity variant, not a fixed contract. Tested multiples are 0.5, 1, 1.5, 2, 3, 4, 6, 8 and 12. Retained counts are `3,204, 3,028, 2,468, 1,822, 1,004, 610, 260, 154, 64`.

It has moderate-to-strong correlation with A (`0.615`), B-primary (`0.766`) and C-log (`0.785`). Its top-quartile overlap with C-log is `0.444`, materially below identity.

## 7. Dual-candle sensitivity

The primary A/B/C sequence defers all 300 dual events; zero same-bar HIGH→LOW or LOW→HIGH transitions are created. Both extrema remain in the event-level output as unordered same-time events.

As a non-sequence sensitivity, each dual side is compared only with strictly earlier/later opposite-type non-dual pivots. Two-sided support is available for 298 of 300 events; median unordered minimum log prominence is `0.02022` (p10–p90 `0.00837–0.05193`). The two boundary events remain explicitly unresolved. This diagnostic does not determine whether a future contract should defer duals or model an outside-bar state.

## 8. Cross-design agreement

| Pair | N | Correlation | Mean absolute normalized difference | Top-quartile Jaccard |
|---|---:|---:|---:|---:|
| A minimum vs B minimum hierarchy | 3,224 | 0.916 | 0.124 | 0.695 |
| A minimum vs B geometric hierarchy | 3,224 | 0.889 | 0.133 | 0.634 |
| B minimum vs B geometric | 4,150 | 0.984 | 0.029 | 0.847 |
| B minimum vs C log | 3,226 | 0.951 | 0.154 | 0.244 |
| B minimum vs C local volatility | 3,226 | 0.766 | 0.190 | 0.244 |
| B minimum vs C retracement ratio | 3,226 | 0.174 | 0.333 | 0.0067 |

The B/C-log top-quartile Jaccard is lower than their correlation because C stores coarse survival fractions over ten scales rather than the complete removal rank; they still share the same underlying minimum-log removal order.

Diagnostic intersections—not labels—produce:

- 1 pivot in the top quartile of all five normalized views;
- 34 pivots in the bottom quartile of all five views;
- 972 of 4,150 non-dual events with cross-design score range at least 0.50.

The single strict all-design “stable core” is driven by the incompatible ratio arm and must not be interpreted as evidence that only one pivot is structural. The factual result is high A/B/log agreement, moderate volatility-normalized agreement and systematic disagreement from the asymmetric ratio sweep.

## 9. Multiscale stability

Large turns survive progressively coarser A/B/log/volatility representations, while many small internal turns disappear early. However, survival declines smoothly across the hierarchy: 3,200 pivots remain at 0.5% log scale, 1,620 at 3%, 440 at 7.5%, 254 at 10% and 48 at 25%. No tested scale revealed a stable empty interval or a uniquely justified cutoff.

The hierarchy is therefore more faithful than a forced binary cutoff for this dataset: it preserves both removal order and the scale at which a turn becomes redundant. It does not by itself choose the downstream semantics.

## 10. Year / regime stability

| Year | Raw | Primary eligible | Median B survival rank | Median cross-design stability |
|---|---:|---:|---:|---:|
| 2019 partial | 214 | 148 | 0.623 | 0.492 |
| 2020 | 640 | 456 | 0.635 | 0.486 |
| 2021 | 603 | 482 | 0.798 | 0.569 |
| 2022 | 633 | 440 | 0.665 | 0.488 |
| 2023 | 678 | 452 | 0.501 | 0.399 |
| 2024 | 616 | 471 | 0.597 | 0.450 |
| 2025 | 624 | 475 | 0.481 | 0.383 |
| 2026 partial | 442 | 302 | 0.515 | 0.394 |

The absolute-log variants retain regime dependence: 2021 is materially more prominent/stable than 2023/2025/2026. Direct correlation with log BTC price is small but non-zero: A `-0.119`, B `-0.093`, C-log `-0.100`, C-local-volatility `-0.041`. This indicates that price era alone is not the full explanation and that volatility normalization reduces, but does not erase, temporal variation.

Across trailing-volatility tertiles, median cross-design stability rises from `0.336` (low) to `0.420` (middle) and `0.525` (high). By contrast, median local-volatility-normalized survival is `0.444` in every tertile. Thus the normalization arm specifically reduces volatility-regime density drift, while raw-log prominence still treats high-volatility turns as larger.

## 11. Representative charts

Six deterministic SVG charts use canonical 4H candles and no zones, signals or human labels.

| Window | Raw events | B retained at 1% / 3% / 7.5% |
|---|---:|---:|
| Strong directional move with many internal pivots | 25 | 18 / 16 / 7 |
| Choppy / low-efficiency high-path | 24 | 21 / 19 / 5 |
| Large reversal | 24 | 19 / 13 / 9 |
| High-density | 37 | 23 / 13 / 2 |
| Low-density | 18 | 13 / 5 / 2 |
| 2026 calibration window | 73 | 44 / 20 / 3 |

Visual QA confirms that many raw turns inside strong directional and high-density paths disappear as scale rises, while the largest reversal extrema persist longer. Choppy paths retain several turns at light scales but thin substantially at coarse scales. Visual inspection is diagnostic only and was not used to tune parameters.

## 12. 2026 calibration observations

The supplied price intervals remain non-labels.

| Interval | Events | HIGH / LOW | Median cross-design stability | High disagreement | Strict all-design stable core |
|---|---:|---:|---:|---:|---:|
| 59.0–60.5k | 6 | 0 / 6 | 0.534 | 3 | 0 |
| 61.5–62.5k | 15 | 2 / 13 | 0.449 | 5 | 0 |
| 66.5–69.0k | 46 | 23 / 23 | 0.369 | 6 | 0 |

The 66.5–69.0k stress case does not behave as 46 independent reactions: the full June–July window has 73 raw events, 44 retained at 1% log scale, 20 at 3% and only 3 at 7.5%. Within the 66.5–69.0k price interval itself, stability is heterogeneous and no strict all-design core appears.

## 13. What all designs agree on

- The raw sequence is genuinely multiscale; many local pivots become redundant under modest simplification.
- Large two-sided turns generally rank higher under A, B and log/volatility C variants.
- A and B agree strongly despite using a local two-sided measurement versus an iterative sequence hierarchy.
- No single tested scale supplies a natural binary boundary.
- Absolute/log scale still carries regime dependence; normalization choice matters.
- Boundary and dual events require explicit unresolved/deferred states rather than fabricated values.

## 14. Where designs disagree

- Asymmetric outgoing/incoming retracement filtering creates a cascade between 0.3 and 0.4 and weak agreement with the magnitude-based representations.
- Local-volatility normalization materially changes top-ranked membership even when overall rank association is positive.
- Minimum versus geometric hierarchy changes survival at coarse scales, although their complete ranks remain very close.
- Dual outside bars can be measured two-sided without ordering, but cannot enter a unique alternating sequence on 4H data.

## 15. Evidence status

The evidence supports a continuous/ordinal multiscale representation. It does not support a canonical binary structure at this stage. The tested asymmetric retracement-ratio sweep is unstable as a standalone reference; it remains evidence/sensitivity only. No final B1 reference contract is selected.

## 16. OPEN METHODOLOGY QUESTIONS

1. Should the future contract expose raw continuous A/B diagnostics, ordinal scale bands, or a confidence-weighted combination?
2. Should minimum or geometric two-sided support be primary, given their high but non-identical ranks?
3. Should the local-volatility normalization be part of the contract or remain a regime-sensitivity view?
4. Should the asymmetric retracement ratio be redesigned before any future use, or excluded from consensus entirely?
5. Should dual outside bars remain deferred, or become a separate unordered structural state?
6. How should left/right boundary-censored pivots be represented in a future reference contract?
7. If a partial binary target is later needed for B2 evaluation, which confidence/ambiguity policy is acceptable?

## 17. Exact options for a future B1 reference contract

These are unranked options; none is selected here.

1. **Continuous multiscale contract:** publish A components, B removal scale/depth and C survival curves without categories.
2. **Ordinal contract:** define reviewed scale bands over B/log/volatility survival, keeping an explicit ambiguous class.
3. **Confidence-weighted consensus:** combine only methodologically distinct A, B and volatility-normalized evidence; do not count C-log as independent support.
4. **Partial high-confidence contract:** identify only reviewed stable/fragile tails and leave the broad middle unresolved.
5. **Dual-state extension:** combine one of the above with a distinct unordered outside-bar state rather than forcing dual extrema into temporal order.

## Artifacts and reproducibility

Generated research root:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_retrospective_reference/`

Implementation and factual-report commit:

`97533acadccf591a9aa026610b7fa00b69e7aebd`

Required artifacts:

- `b1_pivot_reference_diagnostics.parquet` — 4,450 rows;
- `b1_segmentations_long.parquet` — 227,250 rows;
- `b1_design_comparison.csv` and `.parquet`;
- `b1_summary.json`;
- `b1_schema.json`;
- `manifest.json` and `checksums.sha256`;
- `progress.json`;
- six SVG charts in `plots/`;
- smoke artifacts in `smoke/`.

Verification performed:

- 10 stage unit/regression tests pass;
- real-data smoke pass;
- production pass;
- independent artifact QA: 4,450 source/output IDs, 227,250 long rows, 300 dual rows, six charts, zero causal namespace fields, zero final binary-label fields, zero fabricated dual transitions;
- 14 canonical artifact checksums pass;
- deterministic production rerun is byte-identical for Parquet, manifest and checksum set;
- syntax compilation pass;
- static type checker: NOT CONFIGURED in this repository;
- six representative charts rendered inside the authorized data root and visually inspected;
- no external market data, legacy structural levels, Stage 2I-B2 predictors, classifier, reaction zones or trading evaluation used.

Production build runtime is approximately 17 seconds on the local host; independent artifact QA is approximately 9 seconds. Intermediate progress is persisted after source load/Design A, after Designs B/C and at final publication. Generated data remains outside Git.
