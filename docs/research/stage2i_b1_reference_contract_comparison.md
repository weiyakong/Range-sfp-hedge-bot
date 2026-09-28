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
  - A methodological patch audit was applied to eliminate ungrounded claims (zero false tail assertions, independent families terminology, unverified disagreement bounds, semantic micro labeling, longitudinal stability overstatements, hardcoded macro overlap metrics, preferred contract selection, and boundary censoring double counts).

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
| Boundary Censored Candidates (`boundary_ids`) | 418 | 9.39% | Segment endpoints, dual neighbors, and dataset edges (416 dual boundaries + 2 dataset edges); `scale = None`. |
| — Dataset Left-Edge Censored | 1 | 0.02% | `P4H_000006_HIGH` (start of dataset; no preceding 4H history). |
| — Dataset Right-Edge Censored | 1 | 0.02% | `P4H_015442_LOW` (end of dataset; no following 4H history). |
| — Dual-Separator Boundary Candidates | 416 | 9.35% | Segment endpoints / boundary survivors adjacent to dual barriers; `scale = None`. |
| Total Unresolved / Censored Candidates | 1,583 | 35.57% | Preserved without semantic degradation ($300 \text{ dual} + 865 \text{ same-type} + 418 \text{ boundary}$). |
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
| **Confidence** | **CONF-UNANIMOUS-T10** | 2,867 | 64.43% | 91.11% | 35.57% | Strict unanimous consensus of 3 retrospective views | Discards 91.1% resolved as AMBIGUOUS | Categorical: Strong (104), Weak (151) |
| **Confidence** | **CONF-MAJORITY-T10** | 2,867 | 64.43% | 81.93% | 35.57% | Majority voting ($\ge 2$ of 3 retrospective views) | Discards 81.9% resolved as AMBIGUOUS | Categorical: Strong (236), Weak (282) |
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
- Macro structural pivots at scales $\ge 15\%$ and $\ge 25\%$ exhibit high empirical consistency, but are not identical sets: at the tested thresholds, the Min hierarchy set happens to be fully contained within the Geo hierarchy set ($100\%$ empirical containment: 61/61 at $\ge 15\%$, 22/22 at $\ge 25\%$), with Jaccard similarities of $58.65\%$ and $62.86\%$ respectively. For any fixed triplet, the local removal cost satisfies $\sqrt{ab} \ge \min(a, b)$, but this local inequality alone does not establish global set containment for the full iterative hierarchy across all arbitrary thresholds.

### 2. Is there evidence of natural ordinal boundaries?
**NOT DETECTED / NOT SUPPORTED IN TESTED DIAGNOSTICS.**
Natural ordinal boundaries were not detected / not supported in the tested representations and diagnostics.
Adjacent-gap analysis reveals:
- Maximum adjacent scale gap: `0.2541` (at the extreme right tail of historical cycle peaks).
- Median adjacent scale gap: `0.00000278` ($2.78 \times 10^{-6}$).
- The ratio of maximum gap to median gap is large, but there are no persistent empty gaps separating intermediate levels.
- Across the entire spectrum from 0.5% to 15%, the distribution forms an unbroken continuum. While this does not prove that natural ordinal structure can never exist under any conceivable scheme, forced clustering under the tested representations would impose artificial boundaries that do not correspond to observed market geometry.

### 3. How strongly do Q3/Q4/Q5 categories depend on arbitrary binning?
**SUBSTANTIALLY.**
Quantile boundaries divide an unbroken distribution into equal-frequency slices by mathematical definition.
- In ORD-Q3, ~955 continuous ranks are collapsed into each bin, resulting in a within-bin rank IQR of `0.333` and 33.3% of pairs becoming tied.
- Events situated at rank 0.32 and 0.34 differ by only 0.02 in rank but are split across separate classes, while events at rank 0.01 and 0.32 are grouped into the same category.
- Therefore, quantile classes must be recognized as arbitrary discretization tools, not genuine structural regimes.

### 4. What does ORD-SURVIVAL preserve and what does it lose?
- **Preserved:** Clear, physical interpretation. An event's tier directly indicates up to what log percentage excursion (from 0.5% to 25%) the pivot remained unabsorbed by larger moves. Tiers 9 ($\ge 15\%$) and 10 ($\ge 25\%$) act as stable macro structural anchors.
- **Lost:** Fine intra-tier distinctions. Approximately 16.4% of event pairs become tied. A move that survived 2.9% is placed in the same bucket (Tier 4: $\ge 2\%$) as a move that survived 2.1%.

### 5. Can stable agreement tails be constructed?
**YES (WITH REGIME-DEPENDENT DRIFT).**
By requiring agreement across distinct retrospective evidence views (Prominence A-min, Hierarchy B-min, and Volatility-Normalized Sensitivity), robust strong and weak concordance tails emerge:
- Top macro events (major reversals) exhibit 100% agreement across all evidence views.
- However, tail proportions are not static across years; they drift significantly with market regimes. In high-volatility regimes (e.g. the 2021 bull market), the STRONG tail share reaches $40.58\%$ under Majority T20 while the WEAK tail share drops to $1.33\%$. Conversely, in quiet consolidation regimes (e.g. 2023), the WEAK tail expands to $35.15\%$ while the STRONG tail contracts to $13.91\%$. Tail procedures remain stable, but empirical event distributions reflect underlying volatility regimes.

### 6. How does the ambiguous population behave across 10%, 20%, 25%, and 30% tail sizes?
As tail size widens, the ambiguous middle contracts steadily, but remains dominant:
- **10% Tail:** Unanimous ambiguous share = `91.11%` (Majority: `81.93%`). Downstream information loss if discarding ambiguous cases = `94.27%` of master events.
- **20% Tail:** Unanimous ambiguous share = `79.94%` (Majority: `61.63%`). Downstream loss = `87.08%` (Majority: `75.28%`).
- **25% Tail:** Unanimous ambiguous share = `72.41%` (Majority: `52.46%`). Downstream loss = `82.22%` (Majority: `69.37%`).
- **30% Tail:** Unanimous ambiguous share = `65.68%` (Majority: `42.20%`). Downstream loss = `77.89%` (Majority: `62.76%`).

### 7. How do unanimous and majority definitions differ?
- **Unanimous (`CONF-UNANIMOUS`):** Strict intersection requiring 100% concordance across all three retrospective evidence views. Enforces maximum cross-view consensus, but labels 65.7% to 91.1% of resolved pivots as ambiguous. It cannot claim "zero false tails" because no objective ground truth exists.
- **Majority (`CONF-MAJORITY`):** 2-out-of-3 consensus. Expands tail coverage by 2.0x to 2.3x while tolerating single-view metric idiosyncrasies (e.g., quiet-market excursions that rank high in volatility normalization but moderate in raw log excursion).

### 8. Which findings are robust across evidence views?
- **Coarse macro pivots ($\ge 15\%$ scale):** Min hierarchy is 100% contained in Geo hierarchy ($61/61$ at $\ge 15\%$, $22/22$ at $\ge 25\%$). Geo retains additional pivots, yielding Jaccard similarities of $58.65\%$ and $62.86\%$.
- **Small-scale fluctuations ($< 1\%$ scale):** Across the 135 resolved pivots with hierarchy scale $<1.0\%$, $100\%$ (135/135) fall in the WEAK tail under Majority T20. Under Unanimous T20, $85.93\%$ (116/135) fall in the WEAK tail while $14.07\%$ (19/135) are AMBIGUOUS. The label "micro" is strictly avoided in compliance with the B+C preservation contract.
- **Disagreement distribution:** Disagreement is predominantly concentrated in the 1.5%–5.0% band ($90.15\%$ under Majority T20, $75.61\%$ under Unanimous T20), but is **not** strictly confined to it. A non-negligible fraction extends into 5.0%–10.0% ($9.34\%$ Majority, $15.75\%$ Unanimous) and $\ge 10.0\%$ ($0.51\%$ Majority, $2.14\%$ Unanimous).

### 9. Stability across years, volatility regimes, and hierarchy formulations
- **Across Years (2019–2026):**
  - Resolved scale median tracks market volatility (2021 bull run median scale = `0.0497`, while 2023 quiet regime median scale = `0.0223`).
  - Rank distributions remain uniform across all calendar years.
- **Across Volatility Regimes (Tertiles):**
  - Raw log excursion median expands from `0.0192` in low vol to `0.0440` in high vol (~2.3x expansion).
  - Volatility normalization substantially reduces volatility-regime drift relative to raw-log scale (raw scale median expands ~2.3x from 0.0192 to 0.0440, whereas volatility-normalized prominence median exhibits residual variation of 2.10x in low vol, 2.00x in medium vol, and 1.87x in high vol).
- **Across Hierarchy Formulations:**
  - Minimum vs Geometric hierarchy exhibits $r = 0.968$. Disagreements are localized to intermediate boundary merges and the AM-GM expansion in Geo hierarchy.

### 10. Where does information loss occur in ordinal and partial-tail representations?
- **Ordinal Loss:** Loss of relative rank resolution. Up to 33.3% of event pairs become tied. Fine structural spacing is lost.
- **Partial-Tail Loss:** Truncation of the middle distribution. If a downstream pipeline only consumes strong/weak tails, between `62.8%` and `94.3%` of all market events are discarded as ambiguous or unresolved.

### 11. Are coarse / high-survival pivots preserved across representations?
**YES (WITH EMPIRICAL CONTAINMENT AT TESTED MACRO SCALES).**
Across all tested continuous, ordinal, and confidence representations, coarse macro turning points (e.g. March 2020 low, November 2021 high, November 2022 low) are preserved:
- They achieve rank $> 0.95$ in continuous representations.
- They fall into Tier 9 or 10 in ORD-SURVIVAL.
- They fall into Q3 in ORD-Q3, Q4 in ORD-Q4, and Q5 in ORD-Q5.
- They belong to the STRONG tail under both unanimous and majority confidence rules.
- Between Min and Geo hierarchy formulations, Min at $\ge 15\%$ is empirically 100% contained in Geo ($61/61$), while Geo retains 43 additional pivots (Jaccard similarity = $58.65\%$). At $\ge 25\%$, Min is empirically 100% contained in Geo ($22/22$), with Geo retaining 13 additional pivots (Jaccard similarity = $62.86\%$).

### 12. Handling of special states and censoring
The pipeline maintains a strict 6-state taxonomy with zero data loss across all 4,450 raw pivots:
1. `dataset_left_edge_censored` (1 event): Left boundary survivor at bar 6.
2. `dataset_right_edge_censored` (1 event): Right boundary survivor at bar 15,442.
3. `dual_unordered` (300 events): Dual HIGH+LOW candles. Retained as unordered events.
4. `dual_separator_boundary` (416 events): Segment endpoints adjacent to dual candles. Preserved with `scale = None`.
5. `technical_same_type_exclusion` (865 events): Preserved with `scale = None` (no semantic scale 0 or micro label).
6. `ordinary_resolved_sequence_event` (2,867 events): Fully resolved sequence events with two-sided context.

### 13. Is there empirical evidence favoring a single representation?
**NO TESTED SINGLE REPRESENTATION DOMINATED.**
No tested single representation dominated all evaluated criteria:
- A continuous scalar collapses multi-dimensional structural attributes into a single projection.
- Ordinal representations suffer from arbitrary boundary placement and high tie rates.
- Confidence tails discard the majority of market events as ambiguous.
This finding reflects the trade-offs observed across the tested formulations; it does not assert a universal impossibility theorem for all single representations.

### 14. Does the evidence support a layered representation?
**COMPATIBLE CANDIDATE ARCHITECTURE (NO CANONICAL SELECTION).**
The observed trade-offs are compatible with a layered representation as a candidate architecture for user review:
1. **Foundation Layer (Continuous Components):** Retains the full multi-dimensional structural geometry (`CONT-COMPONENTS`: prominence min/geo/balance, hierarchy min/geo, local volatility normalization).
2. **Standardized Comparison Layer (Continuous Rank):** Provides normalized percentile ranks (`CONT-RANK` / `CONT-CONSENSUS`) for scale-free ranking.
3. **Discrete Structural Tier View (ORD-SURVIVAL):** Translates continuous scale into actionable physical log survival tiers without arbitrary equal-frequency distortion.
4. **Agreement Concordance Filter (Confidence Tails):** Provides explicit strong/weak concordance subsets for downstream consumers requiring high agreement across retrospective views, while preserving ambiguous and unresolved candidates.

*Note:* A layered representation remains a plausible candidate for user review, but is not selected as canonical or final architecture. No preferred sensitivity variant is selected by this comparison study. The final B1 reference contract remains OPEN pending user review, and must be selected or refined before Stage 2I-B2 is launched. Confidence represents cross-view concordance, not objective certainty.

---

## 5. Methodological Patch Audit & Claim Validation

A rigorous methodological patch audit was conducted on the Stage 2I-B1 findings to resolve overstatements, clarify definitions, and correct formula errors.

### 5.1 Claim Validation Audit Catalog

| Claim ID | Original Claim Statement | Original Status | Audited Verdict | Audited Correction & Empirical Resolution |
|---|---|---|---|---|
| **CLM-01** | Confidence tails achieve zero false tail claims | Asserted as definitive guarantee | **REJECTED_METHODOLOGICALLY** | Zero false tail claims cannot be asserted without ground truth. Replaced with empirical concordance across retrospective evidence views. |
| **CLM-02** | Confidence rules combine 3 independent evidence families | Asserted as independent families | **REJECTED_METHODOLOGICALLY** | Views derive from the same underlying 4H price series and exhibit $r=0.86\text{–}0.97$. Replaced with "distinct retrospective evidence views". |
| **CLM-03** | Disagreement is strictly concentrated in 1.5% to 5.0% scale | Asserted as strictly concentrated | **REFUTED_EMPIRICALLY** | Predominantly in 1.5%–5.0% (90.15% Majority T20, 75.61% Unanimous T20), but 9.85% (Majority) and 24.39% (Unanimous) extend outside this band (up to 10%+). |
| **CLM-04** | Scale < 1% fluctuations are micro and consistently identified in weak tail | Asserted as micro fluctuations | **REJECTED_METHODOLOGICALLY** | Preservation contract prohibits semantic micro label. Under Unanimous T20, 14.07% of <1% events are AMBIGUOUS rather than WEAK. |
| **CLM-05** | Tail membership is stable across years | Asserted as stable membership | **REFUTED_CONCEPTUALLY_AND_EMPIRICALLY** | Events occur at single points in time. Annual tail shares drift significantly with market regimes (Strong share 9.01% in 2025 to 40.58% in 2021). |
| **CLM-06** | Coarse macro pivots >=15% are 100% invariant across hierarchy formulations | Hardcoded as 1.0 (100% identical sets) | **QUALIFIED_EMPIRICALLY** | Min hierarchy ($N=61$) is empirically 100% contained in Geo hierarchy ($N=104$), but Geo contains 43 additional pivots at $\ge 15\%$. Jaccard similarity is 58.65%. Local inequality does not establish a universal global containment theorem. |
| **CLM-07** | CONF-MAJORITY-T20 is the preferred reference representation | Selected as preferred winner | **REJECTED_BY_SCOPE** | Stage 2I-B1 is purely exploratory. No preferred sensitivity variant is selected by this comparison study. The final B1 reference contract remains OPEN pending user review, and must be selected/refined before Stage 2I-B2 is launched. |
| **CLM-08** | Censored share is $(\text{len}(\text{boundary\_ids}) + 2) / 4450$ | Calculated as $420 / 4450$ (9.4382%) | **CORRECTED_MATHEMATICALLY** | `boundary_ids` already includes the 2 dataset edge survivors. Correct formula is $\text{len}(\text{boundary\_ids}) / \text{len}(\text{events}) = 418 / 4450$ ($9.3933\%$). |

### 5.2 Coarse Structure Overlap ($\ge 15\%$ and $\ge 25\%$)

Computed directly from empirical sets in `coarse_structure_overlap.parquet`:

| Scale Threshold | Min Hierarchy N | Geo Hierarchy N | Intersection N | Union N | Min in Geo Containment | Geo in Min Containment | Jaccard Similarity | Empirical Full Containment |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **$\ge 15\%$** | 61 | 104 | 61 | 104 | **100.00%** | 58.65% | **58.65%** | **TRUE** (Min $\subseteq$ Geo observed) |
| **$\ge 25\%$** | 22 | 35 | 22 | 35 | **100.00%** | 62.86% | **62.86%** | **TRUE** (Min $\subseteq$ Geo observed) |

*Methodological Note:* For a single isolated triplet, the arithmetic-geometric inequality ensures that $\sqrt{ab} \ge \min(a, b)$. However, because removal costs determine the dynamic removal sequence and therefore alter subsequent structural neighbor pairings in an iterative simplification algorithm, this local inequality alone does not establish global set containment for the full iterative hierarchy. The 100% containment of Min in Geo ($61/61$ at $\ge 15\%$ and $22/22$ at $\ge 25\%$) is an empirical observation for these tested macro thresholds, not a proven universal theorem for every arbitrary threshold $\theta$.

### 5.3 Disagreement Scale Diagnostics

Distribution of ambiguous event scales from `disagreement_scale_diagnostics.parquet`:

| Confidence Rule | Tail Size | Ambiguous N | $< 1.5\%$ Count (Share) | 1.5%–5.0% Count (Share) | 5.0%–10.0% Count (Share) | $\ge 10.0\%$ Count (Share) | Strictly Confined to 1.5%–5.0%? |
|---|---:|---:|---:|---:|---:|---:|---|
| **Majority** | 10% | 2,349 | 141 (6.00%) | 1,766 (75.18%) | 417 (17.75%) | 25 (1.06%) | **FALSE** |
| **Majority** | 20% | 1,767 | 0 (0.00%) | 1,593 (90.15%) | 165 (9.34%) | 9 (0.51%) | **FALSE** |
| **Majority** | 25% | 1,504 | 0 (0.00%) | 1,406 (93.48%) | 90 (5.98%) | 8 (0.53%) | **FALSE** |
| **Majority** | 30% | 1,210 | 0 (0.00%) | 1,141 (94.30%) | 63 (5.21%) | 6 (0.50%) | **FALSE** |
| **Unanimous** | 10% | 2,612 | 266 (10.18%) | 1,772 (67.84%) | 496 (18.99%) | 78 (2.99%) | **FALSE** |
| **Unanimous** | 20% | 2,292 | 149 (6.50%) | 1,733 (75.61%) | 361 (15.75%) | 49 (2.14%) | **FALSE** |
| **Unanimous** | 25% | 2,076 | 116 (5.59%) | 1,645 (79.24%) | 276 (13.29%) | 39 (1.88%) | **FALSE** |
| **Unanimous** | 30% | 1,883 | 93 (4.94%) | 1,520 (80.72%) | 234 (12.43%) | 36 (1.91%) | **FALSE** |

---

## 6. 2026 Human Calibration Window Analysis

The three 2026 non-label calibration intervals demonstrate how representations behave in dense areas:

| Interval | Total Raw Pivots | B+C Alternating Candidates | Prepass Excluded | Dual Boundary | Ordinary Resolved | Dominant Confidence State (T=20%) |
|---|---:|---:|---:|---:|---:|---|
| **59.0–60.5k** | 6 (all LOW) | 5 | 1 | 1 | 4 | Mixed Intermediate / Ambiguous |
| **61.5–62.5k** | 15 (13 LOW, 2 HIGH) | 12 | 3 | 2 | 10 | Primarily Ambiguous / Moderate Scale |
| **66.5–69.0k** | 46 (23 HIGH, 23 LOW) | 37 | 9 | 5 | 32 | Multiscale Continuum (Strong to Weak) |

In the dense 66.5–69.0k interval:
- The 46 raw pivots span across all structural scales: 8 events qualify as STRONG tail, 7 as WEAK tail, and 17 as AMBIGUOUS under Majority T20.
- This proves empirically that dense trading areas contain a mixture of minor fluctuations and meaningful turning points that cannot be treated as a uniform structural zone.

---

## 7. Representative QA Visual Charts

Seven canonical 4H SVG plots have been generated in `plots/`:
1. `b1_comp_01_clear_large_turn.svg`: March 2020 reversal (bars 1074–1164) showing macro turning point classification (STRONG confidence).
2. `b1_comp_02_small_local_fluctuation.svg`: Bars 7280–7330 showing sub-1% local noise consolidated or assigned WEAK status.
3. `b1_comp_03_ambiguous_middle_scale.svg`: Bars 8400–8480 showing intermediate rotations where evidence views diverge.
4. `b1_comp_04_dual_mediated.svg`: Bars 6065–6115 demonstrating dual candles acting as structural separators.
5. `b1_comp_05_choppy_range.svg`: Bars 3816–3906 showing dense range trading with preserved candidates.
6. `b1_comp_06_directional_move.svg`: Bars 2832–2922 showing trending leg with same-type candidates preserved alongside alternating run.
7. `b1_comp_07_calibration_2026.svg`: 2026 calibration intervals (59k, 62k, 66.5–69k) showing multiscale candidate distribution.

---

## 8. QA and Verification Status

- Master Population Invariance: PASS (all 4,450 frozen IDs preserved).
- B+C Dual-Barrier Semantics: PASS (145 segments, no cross-barrier hierarchy edge).
- Candidate Preservation: PASS (865 technical exclusions preserved with `scale = None`).
- Boundary Censoring Consistency: PASS (418 boundary candidates = 9.39% of master; zero double count).
- Common Denominator Consistency: PASS ($N = 2,867$ for all resolved comparisons).
- Unresolved Candidate Handling: PASS (zero forced scale 0 or arbitrary values).
- Methodological Audit Verification: PASS (all 8 audit claims validated and reflected in code/data).
- Deterministic Output: PASS (byte-identical rerun verified).
- Checksums & Manifest: PASS (all 23 production artifacts validated).
