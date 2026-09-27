# Stage 2I-B1 — Reference Contract Comparison

## 1. Executive Summary & Authoritative Scope

This study compares alternative representations of retrospective price-action structural reference on canonical BTCUSDT futures 4H data following the adopted **B + C candidate-preservation policy**.

- **Authoritative Worktree:** `/Users/yeshevika/Documents/Codex/2026-09-27/range-sfp-pa-structure`
- **Branch:** `archive/btc-macro-nautilus-2026-09-03`
- **Starting HEAD:** `5896cbae620d0662c2a7952ddf3cc51c6240c0cf`
- **Data Root:** `/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data`
- **Generated Artifact Root:** `/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_reference_contract_comparison/`
- **Methodological Status:** **RESEARCH COMPLETE / CANONICAL REFERENCE CONTRACT REMAINS OPEN**.
  - Stage 2I-B2 is **NOT** launched.
  - Canonical B1 reference contract is **NOT** chosen in this study.
  - `PA_STRUCTURE_CANONICAL.md` is strictly **UNMODIFIED**.

---

## 2. Fixed B+C Contract & Segment-Aware Rebuild

Under the fixed B+C candidate-preservation contract:
1. Same-type prepass is purely a technical transform used to construct an alternating sequence; it is not a semantic significance filter.
2. Excluded same-type pivots are **NOT** labelled micro and are **NOT** assigned semantic `structural scale = 0`.
3. Dual HIGH+LOW candles (150 candles / 300 events) remain unordered without fabricated intrabar ordering.
4. Dual candles act as **structural separators**: they partition the timeline into contiguous non-dual segments.
5. The hierarchical simplification does **NOT** bridge across dual separators. Each segment is simplified independently.
6. When ambiguity or boundary censoring occurs, candidates are preserved with explicit unresolved status (`scale = None`) rather than forced values.

### Population Accounting

| Category | Count | % of Master | Meaning / Treatment |
|---|---:|---:|---|
| **Master Population (Stage 2I-A Raw Pivots)** | **4,450** | **100.00%** | Frozen source pivot set. Zero rows dropped or duplicated. |
| Dual Unordered Events | 300 | 6.74% | 150 dual HIGH+LOW candles. Unordered on 4H; sequence-ineligible. |
| Non-Dual Candidate Stream | 4,150 | 93.26% | Enters segment-aware sequence processing. |
| Non-Dual Alternating Segments | 145 | — | Continuous timeline segments separated by dual barriers. |
| Technical Same-Type Prepass Exclusions | 865 | 19.44% | Preserved with `excluded_from_alternating_sequence = True`; `scale = None`. |
| Alternating Sequence Candidates | 3,285 | 73.82% | Candidates entering segment-aware hierarchy across 145 segments. |
| Dataset Left-Edge Censored | 1 | 0.02% | `P4H_000006_HIGH` (start of dataset; no preceding 4H history). |
| Dataset Right-Edge Censored | 1 | 0.02% | `P4H_015442_LOW` (end of dataset; no following 4H history). |
| Dual-Separator Boundary Candidates | 416 | 9.35% | Segment endpoints / boundary survivors adjacent to dual barriers; `scale = None`. |
| **Ordinary Resolved Sequence Events** | **2,867** | **64.43%** | **Identical common resolved evaluation denominator for all head-to-head comparisons.** |

---

## 3. Master Contract Comparison Table

All comparisons are evaluated across the exact same common resolved population ($N = 2,867$, coverage $64.43\%$).

| Representation Family | Variant | Resolved N | Coverage | Ambiguous Share | Unresolved Share | Cross-Design Agreement | Information Retention / Loss | Target Properties & Dimensionality |
|---|---|---:|---:|---:|---:|---|---|---|
| **Continuous** | **CONT-SCALE** | 2,867 | 64.43% | 0.00% | 35.57% | Min vs geo hierarchy $r=0.968$; vs prominence min $r=0.930$ | Preserves continuous metric; zero ties | 1D float $[0, \infty)$, deterministic, continuous |
| **Continuous** | **CONT-RANK** | 2,867 | 64.43% | 0.00% | 35.57% | Rank vs prominence min $r=0.930$; vs vol-norm $r=0.667$ | Uniform distribution; full ordering preserved | 1D float $[0, 1]$, scale-invariant |
| **Continuous** | **CONT-COMPONENTS** | 2,867 | 64.43% | 0.00% | 35.57% | Exposes prominence, hierarchy, and volatility dimensions | Zero loss; complete geometry preserved | Multi-dimensional vector (6 features) |
| **Continuous** | **CONT-CONSENSUS-MEAN** | 2,867 | 64.43% | 0.00% | 35.57% | High correlation with constituents ($r=0.94-0.97$) | Unweighted synthesis; collapses 3D to 1D rank | 1D float $[0, 1]$, robust consensus |
| **Continuous** | **CONT-CONSENSUS-MEDIAN**| 2,867 | 64.43% | 0.00% | 35.57% | Almost identical to mean ($r=0.978$, max diff $<0.08$) | Unweighted median; outlier resistant | 1D float $[0, 1]$, robust consensus |
| **Ordinal** | **ORD-SURVIVAL** | 2,867 | 64.43% | 0.00% | 35.57% | Spearman $r=0.981$ with continuous rank | 11 discrete tiers; 16.4% tied pairs | 1D discrete integer $[0..10]$ |
| **Ordinal** | **ORD-Q3** | 2,867 | 64.43% | 0.00% | 35.57% | Rank correlation $r=0.96-0.98$ | Collapses ~955 ranks/bin; 33.3% tied pairs | 1D categorical (3 levels) |
| **Ordinal** | **ORD-Q4** | 2,867 | 64.43% | 0.00% | 35.57% | Rank correlation $r=0.96-0.98$ | Collapses ~716 ranks/bin; 25.0% tied pairs | 1D categorical (4 levels) |
| **Ordinal** | **ORD-Q5** | 2,867 | 64.43% | 0.00% | 35.57% | Rank correlation $r=0.96-0.98$ | Collapses ~573 ranks/bin; 20.0% tied pairs | 1D categorical (5 levels) |
| **Confidence** | **CONF-UNANIMOUS-T10** | 2,867 | 64.43% | 91.11% | 35.57% | Strict unanimous consensus of 3 families | Discards 91.1% resolved as AMBIGUOUS | Categorical: Strong (104), Weak (151) |
| **Confidence** | **CONF-MAJORITY-T10** | 2,867 | 64.43% | 81.93% | 35.57% | Majority voting ($\ge 2$ of 3 families) | Discards 81.9% resolved as AMBIGUOUS | Categorical: Strong (236), Weak (282) |
| **Confidence** | **CONF-UNANIMOUS-T20** | 2,867 | 64.43% | 79.94% | 35.57% | Strict unanimous consensus in 20% tails | Discards 79.9% resolved as AMBIGUOUS | Categorical: Strong (268), Weak (307) |
| **Confidence** | **CONF-MAJORITY-T20** | 2,867 | 64.43% | 61.63% | 35.57% | Majority voting in 20% tails | Discards 61.6% resolved as AMBIGUOUS | Categorical: Strong (539), Weak (561) |
| **Confidence** | **CONF-UNANIMOUS-T25** | 2,867 | 64.43% | 72.41% | 35.57% | Strict unanimous consensus in 25% tails | Discards 72.4% resolved as AMBIGUOUS | Categorical: Strong (375), Weak (416) |
| **Confidence** | **CONF-MAJORITY-T25** | 2,867 | 64.43% | 52.46% | 35.57% | Majority voting in 25% tails | Discards 52.5% resolved as AMBIGUOUS | Categorical: Strong (676), Weak (687) |
| **Confidence** | **CONF-UNANIMOUS-T30** | 2,867 | 64.43% | 65.68% | 35.57% | Strict unanimous consensus in 30% tails | Discards 65.7% resolved as AMBIGUOUS | Categorical: Strong (477), Weak (507) |
| **Confidence** | **CONF-MAJORITY-T30** | 2,867 | 64.43% | 42.20% | 35.57% | Majority voting in 30% tails | Discards 42.2% resolved as AMBIGUOUS | Categorical: Strong (826), Weak (831) |

---

## 4. Detailed Empirical Evidence & Answers to Authoritative Questions

### 1. Is continuous multiscale representation supported after the B+C rebuild?
**YES.**
The segment-aware B+C rebuild confirms that price-action structure is inherently multiscale and continuous.
- Segment-aware hierarchical simplification scales correlate strongly between minimum-cost and geometric-cost formulations ($r = 0.968$).
- Minimum hierarchy removal scale correlates strongly with two-sided retrospective prominence ($r = 0.930$).
- Consensus mean and median continuous ranks agree at $r = 0.978$.
- Macro structural anchors at scales $\ge 15\%$ and $\ge 25\%$ remain 100% identical across formulations.

### 2. Is there evidence of natural ordinal boundaries?
**NO.**
Adjacent-gap analysis reveals:
- Maximum adjacent scale gap: `0.2541` (at the extreme right tail of historical cycle peaks).
- Median adjacent scale gap: `0.00000278` ($2.78 \times 10^{-6}$).
- The ratio of maximum gap to median gap is large, but there are no persistent empty gaps separating intermediate levels.
- Across the entire spectrum from 0.5% to 15%, the distribution forms an unbroken continuum. Forced clustering would impose artificial boundaries that do not exist in market geometry.

### 3. How strongly do Q3/Q4/Q5 categories depend on arbitrary binning?
**SUBSTANTIALLY.**
Quantile boundaries divide an unbroken distribution into equal-frequency slices by mathematical definition.
- In ORD-Q3, ~955 continuous ranks are collapsed into each bin, resulting in a within-bin rank IQR of `0.333` and 33.3% of pairs becoming tied.
- Events situated at rank 0.32 and 0.34 differ by only 0.02 in rank but are split across separate classes, while events at rank 0.01 and 0.32 are grouped into the same category.
- Therefore, quantile classes must be recognized as arbitrary discretization tools, not genuine structural regimes.

### 4. What does ORD-SURVIVAL preserve and what does it lose?
- **Preserved:** Clear, physical interpretation. An event's tier directly indicates up to what log percentage excursion (from 0.5% to 25%) the pivot remained unabsorbed by larger moves. Tiers 9 ($\ge 15\%$) and 10 ($\ge 25\%$) act as stable macro invariants.
- **Lost:** Fine intra-tier distinctions. Approximately 16.4% of event pairs become tied. A move that survived 2.9% is placed in the same bucket (Tier 4: $\ge 2\%$) as a move that survived 2.1%.

### 5. Can stable agreement tails be constructed?
**YES.**
By requiring agreement across independent evidence families (Prominence A-min, Hierarchy B-min, and Volatility-Normalized Sensitivity), robust strong and weak tails emerge:
- Top macro events (major reversals) exhibit 100% agreement across all evidence families.
- Tail membership remains stable across years and market regimes.

### 6. How does the ambiguous population behave across 10%, 20%, 25%, and 30% tail sizes?
As tail size widens, the ambiguous middle contracts steadily, but remains dominant:
- **10% Tail:** Unanimous ambiguous share = `91.11%` (Majority: `81.93%`). Downstream information loss if discarding ambiguous cases = `94.27%` of master events.
- **20% Tail:** Unanimous ambiguous share = `79.94%` (Majority: `61.63%`). Downstream loss = `87.08%` (Majority: `75.28%`).
- **25% Tail:** Unanimous ambiguous share = `72.41%` (Majority: `52.46%`). Downstream loss = `82.22%` (Majority: `69.37%`).
- **30% Tail:** Unanimous ambiguous share = `65.68%` (Majority: `42.20%`). Downstream loss = `77.89%` (Majority: `62.76%`).

### 7. How do unanimous and majority definitions differ?
- **Unanimous (`CONF-UNANIMOUS`):** Strict intersection. Requires 100% concordance among all three independent families. Generates zero false tail claims, but labels 65% to 91% of resolved pivots as ambiguous.
- **Majority (`CONF-MAJORITY`):** 2-out-of-3 consensus. Expands tail coverage by 2.0x to 2.3x while tolerating single-family metric idiosyncrasies (e.g., quiet-market excursions that rank high in volatility normalization but moderate in raw log excursion).

### 8. Which findings are robust across evidence families?
- Macro structural pivots ($\ge 15\%$ scale) are invariant across A prominence, B hierarchy, and volatility normalization.
- Micro fluctuations ($< 1\%$ scale) are consistently identified in the weak tail across all three families.
- Disagreement is strictly concentrated in the intermediate range (excursions between 1.5% and 5.0%), where path efficiency and local volatility scaling can diverge.

### 9. Stability across years, volatility regimes, and hierarchy formulations
- **Across Years (2019–2026):**
  - Resolved scale median tracks market volatility (2021 bull run median scale = `0.0497`, while 2023 quiet regime median scale = `0.0223`).
  - Rank distributions remain uniform across all calendar years.
- **Across Volatility Regimes (Tertiles):**
  - Raw log excursion median expands from `0.0192` in low vol to `0.0440` in high vol (~2.3x expansion).
  - Volatility-normalized prominence median remains remarkably invariant across regimes: `2.10x` in low vol, `2.00x` in medium vol, and `1.87x` in high vol.
- **Across Hierarchy Formulations:**
  - Minimum vs Geometric hierarchy exhibits $r = 0.968$. Disagreements are localized to intermediate boundary merges.

### 10. Where does information loss occur in ordinal and partial-tail representations?
- **Ordinal Loss:** Loss of relative rank resolution. Up to 33.3% of event pairs become tied. Fine structural spacing is lost.
- **Partial-Tail Loss:** Truncation of the middle distribution. If a downstream pipeline only consumes strong/weak tails, between `62.8%` and `94.3%` of all market events are discarded as ambiguous or unresolved.

### 11. Are coarse / high-survival pivots preserved across representations?
**YES, 100% INVARIANT.**
Across all tested continuous, ordinal, and confidence representations, coarse macro turning points (e.g. March 2020 low, November 2021 high, November 2022 low) are preserved without exception:
- They achieve rank $> 0.95$ in continuous representations.
- They fall into Tier 9 or 10 in ORD-SURVIVAL.
- They fall into Q3 in ORD-Q3, Q4 in ORD-Q4, and Q5 in ORD-Q5.
- They belong to the STRONG tail under both unanimous and majority confidence rules.

### 12. Handling of special states and censoring
The pipeline maintains a strict 6-state taxonomy with zero data loss across all 4,450 raw pivots:
1. `dataset_left_edge_censored` (1 event): Left boundary survivor at bar 6.
2. `dataset_right_edge_censored` (1 event): Right boundary survivor at bar 15,442.
3. `dual_unordered` (300 events): Dual HIGH+LOW candles. Retained as unordered events.
4. `dual_separator_boundary` (416 events): Segment endpoints adjacent to dual candles. Preserved with `scale = None`.
5. `technical_same_type_exclusion` (865 events): Preserved with `scale = None` (no semantic scale 0 or micro label).
6. `ordinary_resolved_sequence_event` (2,867 events): Fully resolved sequence events with two-sided context.

### 13. Is there empirical evidence favoring a single representation?
**NO.**
The empirical evidence decisively demonstrates that no single representation is universally sufficient:
- A continuous scalar collapses multi-dimensional structural attributes into a single projection.
- Ordinal representations suffer from arbitrary boundary placement and high tie rates.
- Confidence tails discard the majority of market events as ambiguous.

### 14. Does the evidence support a layered representation?
**YES (EMPIRICAL CONCLUSION).**
The data strongly support a **layered structural output**:
1. **Foundation Layer (Continuous Components):** Retains the full multi-dimensional structural geometry (`CONT-COMPONENTS`: prominence min/geo/balance, hierarchy min/geo, local volatility normalization).
2. **Standardized Comparison Layer (Continuous Rank):** Provides normalized percentile ranks (`CONT-RANK` / `CONT-CONSENSUS`) for scale-free ranking.
3. **Discrete Structural Tier View (ORD-SURVIVAL):** Translates continuous scale into actionable physical log survival tiers without arbitrary equal-frequency distortion.
4. **Confidence / High-Conviction Filter (CONF-MAJORITY-T20 / UNANIMOUS):** Provides explicit strong/weak anchor subsets for downstream components that require high-conviction agreement, while explicitly preserving ambiguous and unresolved candidates.

---

## 5. 2026 Human Calibration Window Analysis

The three 2026 non-label calibration intervals demonstrate how representations behave in dense areas:

| Interval | Total Raw Pivots | B+C Alternating Candidates | Prepass Excluded | Dual Boundary | Ordinary Resolved | Dominant Confidence State (T=20%) |
|---|---:|---:|---:|---:|---:|---|
| **59.0–60.5k** | 6 (all LOW) | 5 | 1 | 1 | 4 | Mixed Intermediate / Ambiguous |
| **61.5–62.5k** | 15 (13 LOW, 2 HIGH) | 12 | 3 | 2 | 10 | Primarily Ambiguous / Moderate Scale |
| **66.5–69.0k** | 46 (23 HIGH, 23 LOW) | 37 | 9 | 5 | 32 | Multiscale Continuum (Strong to Weak) |

In the dense 66.5–69.0k interval:
- The 46 raw pivots span across all structural scales: 8 events qualify as STRONG tail, 7 as WEAK tail, and 17 as AMBIGUOUS.
- This proves empirically that dense trading areas contain a mixture of minor micro-rotations and meaningful turning points that cannot be treated as a uniform structural zone.

---

## 6. Representative QA Visual Charts

Seven canonical 4H SVG plots have been generated in `plots/`:
1. `b1_comp_01_clear_large_turn.svg`: March 2020 reversal (bars 1074–1164) showing unambiguous macro invariant classification.
2. `b1_comp_02_small_local_fluctuation.svg`: Bars 7280–7330 showing sub-1% local noise consolidated or assigned WEAK status.
3. `b1_comp_03_ambiguous_middle_scale.svg`: Bars 8400–8480 showing intermediate rotations where evidence families diverge.
4. `b1_comp_04_dual_mediated.svg`: Bars 6065–6115 demonstrating dual candles acting as structural separators.
5. `b1_comp_05_choppy_range.svg`: Bars 3816–3906 showing dense range trading with preserved candidates.
6. `b1_comp_06_directional_move.svg`: Bars 2832–2922 showing trending leg with same-type candidates preserved alongside alternating run.
7. `b1_comp_07_calibration_2026.svg`: 2026 calibration intervals (59k, 62k, 66.5–69k) showing multiscale candidate distribution.

---

## 7. QA and Verification Status

- Master Population Invariance: PASS (all 4,450 frozen IDs preserved).
- B+C Dual-Barrier Semantics: PASS (145 segments, no cross-barrier hierarchy edge).
- Candidate Preservation: PASS (865 technical exclusions preserved with `scale = None`).
- Common Denominator Consistency: PASS ($N = 2,867$ for all resolved comparisons).
- Unresolved Candidate Handling: PASS (zero forced scale 0 or arbitrary values).
- Deterministic Output: PASS (byte-identical rerun verified).
- Checksums & Manifest: PASS (all 20 production artifacts validated).
