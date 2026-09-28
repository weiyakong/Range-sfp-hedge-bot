# Stage 2I-B1 — Diagnostics of 1,583 UNRESOLVED Pivot Events

## 1. Executive Summary & Authoritative Scope

This study provides a rigorous code-level and empirical diagnostic analysis of the **1,583 pivot events** that currently remain `UNRESOLVED` (`scale = None`, `confidence = UNRESOLVED`) within the canonical **Stage 2I-B1 Layered Retrospective Reference Contract**.

- **Authoritative Worktree:** `/Users/yeshevika/Documents/Codex/2026-09-27/range-sfp-pa-structure`
- **Branch:** `archive/btc-macro-nautilus-2026-09-03`
- **Starting HEAD:** `15e70f8579a1268725e1940647886172d46750f8`
- **Data Root:** `/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data`
- **Generated Diagnostic Artifact Root:** `/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_unresolved_diagnostics/`
- **Methodological Scope & Guardrails:**
  - This is **STRICTLY A DIAGNOSTIC STUDY**.
  - **NO** canonical contract is modified.
  - `PA_STRUCTURE_CANONICAL.md` is strictly **BYTE-IDENTICAL TO HEAD**.
  - **NO** fictional values (`0`, `False`, arbitrary labels) are inserted into production artifacts.
  - **NO** Stage 2I-B2 predictive research is launched.
  - **NO** methodological choice or "winner" is selected on behalf of the user.
  - All claims and numbers trace directly to computed data artifacts and explicit code dependencies.

---

## 2. Fixed Baseline State & Population Accounting

Across the complete historical calibration period (15,445 contiguous 4H candles, 2019-09-08 to 2026-09-03), the frozen Stage 2I-A generator defines exactly **4,450 raw 4H pivots**.

Under the user-approved **Layered Retrospective Reference Contract** (`PA_STRUCTURE_CANONICAL.md §7.8`), the reference population is partitioned into:

| Category | Population Count ($N$) | Percentage of Master | Current Contract State |
|---|---:|---:|---|
| **Ordinary Resolved Sequence Events** | **2,867** | **64.43%** | Fully resolved across all 4 layers |
| **Total UNRESOLVED Events** | **1,583** | **35.57%** | `None` in Layers 1–3; `UNRESOLVED` in Layer 4 |
| — Group A: `dual_unordered` | 300 | 6.74% | 150 dual HIGH+LOW candles (unordered on 4H) |
| — Group B: `technical_same_type_exclusion` | 865 | 19.44% | Non-extreme same-type pivots preserved under B+C |
| — Group C: `dual_separator_boundary` | 416 | 9.35% | Segment endpoints and segment hierarchy survivors |
| — Group D: `dataset_edge_censored` | 2 | 0.04% | Leftmost and rightmost boundaries of the dataset |
| **Total Master Population** | **4,450** | **100.00%** | Zero rows dropped, duplicated, or synthesized |

---

## 3. Code-Path Dependency Trace: Where Information Becomes Unavailable

The B1 reference pipeline processes raw pivots through a strict 7-stage sequence. The exact step at which each unresolved group diverges from the resolved pipeline is shown below:

```
[Raw 4H Pivots (4,450)]
       │
       ├─► [Step 1: Dual Candle Partitioning]
       │         │
       │         ├─► Dual Candles (300 events) ───► STOP: Sequence-ineligible barrier
       │         │                                        (special_state = "dual_unordered")
       │         ▼
       ├─► [Step 2: Non-Dual Candidate Stream (4,150 events in 145 segments)]
       │         │
       │         ├─► [Step 3: Segment Same-Type Prepass]
       │                   │
       │                   ├─► Non-extreme same-type (865 events) ──► STOP: Excluded from alternating sequence
       │                   │                                               (special_state = "technical_same_type_exclusion")
       │                   ▼
       ├─► [Step 4: Alternating Sequence Candidates (3,285 events across 145 segments)]
       │         │
       │         ├─► [Step 5: Segment Endpoints Identification]
       │         │         │
       │         │         ├─► Dataset Edges (2 events) ────────► STOP: Missing external history
       │         │         │                                             (dataset_left/right_edge_censored)
       │         │         ├─► Segment Endpoints (283 events) ──► STOP: Missing 1 alternating neighbor
       │         │                                                       (dual_separator_boundary - endpoints)
       │         ▼
       ├─► [Step 6: Segment Hierarchical Simplification]
       │         │
       │         ├─► Last 2 survivors in segment (133 events) ──► STOP: Never removed by interior excursion (scale = None)
       │         │                                                       (dual_separator_boundary - interior survivors)
       │         ▼
       └─► [Step 7: Interior Removed Events (2,867 events)] ────► FULL RESOLUTION: Layers 1, 2, 3, 4
```

---

## 4. In-Depth Diagnosis of the 4 Unresolved Groups

### Group A: `dual_unordered` ($N = 300$)

#### A. Why Currently Unresolved?
- 150 4H candles qualify simultaneously as a raw strict five-bar HIGH and LOW.
- 4H candles provide OHLC summary statistics but **no intrabar temporal ordering**. Whether the HIGH occurred before the LOW or the LOW occurred before the HIGH is causally and structurally unknown on 4H data alone.
- Under the fixed B1 candidate-preservation contract, fabricating an intrabar temporal order (e.g. HIGH-first or LOW-first) is strictly forbidden.
- Dual candles partition the timeline into contiguous segments: they act as **structural barriers** and are marked `sequence_eligible = False`.
- Because they never enter `segment_alternating`, they have no left or right alternating neighbors, never enter hierarchical simplification, and receive `scale = None`.

#### B. Existing Quantities Computable Without Changing Approved Semantics
- **Local Volatility Scale:** In `master_event_reference.parquet`, the local TR-42 true range median is **already computed for 298 of the 300 dual events** (only 2 events at bar index 3 lack the 10-bar historical lookback).
- **Intra-Candle Range:** The log range $\log(\text{high} / \text{low})$ is well-defined, physically observable, and invariant to temporal order. Across the 150 dual candles:
  - Minimum intra-candle range: `0.0042` ($0.42\%$)
  - Median intra-candle range: `0.0262` ($2.62\%$)
  - Maximum intra-candle range: `0.2062` ($20.62\%$)
- **Normalized Intra-Candle Excursion:** $(\text{high} - \text{low}) / \text{scale}_{\text{TR42}}$ is well-defined as an auxiliary metric.
- **Canonical Layer 1–4 Fields:** **NONE** of the 19 canonical fields can be populated under current semantics because all canonical prominence and hierarchy metrics explicitly require alternating temporal sequence neighbors.

#### C. Quantities Blocked Without a New Methodological Choice
- All 6 Layer 1 fields (`prominence_min_log`, `prominence_geo_log`, `prominence_balance`, `prominence_vol_norm`, `hierarchy_min_scale`, `hierarchy_geo_scale`).
- All Layer 2 ranks, Layer 3 survival scale, and Layer 4 agreement states.

#### D. Methodological Choices Required from User
1. **Option A1 (Lower-Timeframe Tie-Breaking):** Use 1m/5m/1h historical candle data to reconstruct the historical order of extremes.
   - *Impact:* Integrates up to 300 events into the alternating sequence, but **eliminates dual barriers**, merges the 145 segments into larger chains, and alters the hierarchy and percentile ranks of the existing 2,867 resolved events!
2. **Option A2 (Joint Dual-Box / Structural Interval Node):** Model the dual candle as an unordered 2-dimensional price interval $(\text{low}, \text{high})$ rather than two distinct chronological points.
   - *Impact:* Preserves single-timeframe 4H integrity; requires defining how alternating sequences interact with an interval boundary. Does not change existing resolved events if treated as a distinct object.
3. **Option A3 (Permanent Unresolved Category):** Retain dual events as a distinct, permanent, unsequenced structural class (`special_state = "dual_unordered"`).
   - *Impact:* Zero alteration to existing contracts; fully honest about 4H data limits.

#### E. Potential Event Coverage
- Under Option A1: up to 300 events could potentially enter an expanded sequence (at the cost of recalculating existing resolved events).
- Under Option A2/A3: 0 canonical point-pivot fields, but 300 events could receive auxiliary interval-scale metadata.

---

### Group B: `technical_same_type_exclusion` ($N = 865$)

#### B. Why Currently Unresolved?
- Formed by consecutive same-type pivots in the raw candidate stream (e.g. HIGH followed by another HIGH without an intervening LOW, after dual barrier partitioning).
- B1 prepass consolidates same-type runs by selecting the single most extreme pivot (highest HIGH or lowest LOW) to enter the alternating sequence.
- The remaining 865 non-extreme pivots are marked `excluded_from_alternating_sequence = True`.
- Under the fixed B+C preservation contract, these 865 pivots are explicitly preserved in the master population with `scale = None`. They are **NOT** labeled micro, noise, or assigned scale 0.
- Because they are excluded before `segment_alternating`, they have no alternating neighbors and never enter the segment hierarchy.

#### B. Existing Quantities Computable Without Changing Approved Semantics
- **Local Volatility Scale:** Available for **100% (865 of 865)** events in `master_event_reference.parquet`.
- **Prepass Realized Adverse Departure:** As established in `stage2i_b1_same_type_prepass_audit.md`, the excursion from the excluded pivot to its winning sibling is empirically measurable:
  - Median adverse departure: `2.176%`
  - 271 of 924 audit events exceeded 3.0%, 88 exceeded 5.0%, 31 exceeded 7.5%.
- **Canonical Layer 1–4 Fields:** **NONE** under current contract. Canonical prominence requires opposite-type alternating neighbors; immediate raw neighbors are of the same type.

#### C. Quantities Blocked Without a New Methodological Choice
- Two-sided prominence (requires defining what constitutes a valid left/right neighbor for an excluded sibling).
- Hierarchy scale (requires either non-alternating hierarchy simplification or surrogate removal assignment).
- Ranks, Survival, and Agreement states.

#### D. Methodological Choices Required from User
1. **Option B1 (Adverse Departure as Structural Metric):** Adopt the realized departure relative to the winning sibling as an auxiliary structural scale.
   - *Impact:* Yields a 1-sided metric for 865 events. Does not alter existing resolved 2,867 events. Does not populate canonical 2-sided prominence.
2. **Option B2 (Bracketed Prominence Inheritance):** Excluded same-type pivots inherit the alternating left and right neighbors of their winning sibling in `segment_alternating`.
   - *Impact:* Computes two-sided prominence (`prominence_min_log`, `prominence_geo_log`, `prominence_balance`, `prominence_vol_norm`) for all 865 events! Does **NOT** alter the alternating sequence or the 2,867 resolved events. Hierarchy scale remains None unless surrogate logic is adopted.
3. **Option B3 (Abolish Prepass / Full Non-Alternating Hierarchy):** Eliminate same-type prepass and run hierarchical simplification directly on all 4,150 non-dual events.
   - *Impact:* Radically alters the simplification order, segment topology, and **invalidates the verified empirical results and ranks of the 2,867 resolved events**!
4. **Option B4 (Retain as Canonical UNRESOLVED):** Keep `scale = None` in canonical reference, but expose audit departure metrics in diagnostics.

#### E. Potential Event Coverage
- Under Option B2: **865 events** could obtain 4 canonical Layer 1 prominence fields (`prominence_min_log`, `prominence_geo_log`, `prominence_balance`, `prominence_vol_norm`) without changing existing resolved events!
- Under Option B3: 865 events obtain full Layer 1–4, but breaks backward compatibility with existing 2,867 resolved events.

---

### Group C: `dual_separator_boundary` ($N = 416$)

#### A. Why Currently Unresolved? (Crucial Structural Discovery)
A rigorous inspection of pipeline code (`build_stage2i_b1_comparison.py`, lines 580–656) reveals that the 416 `dual_separator_boundary` events consist of **two structurally distinct populations**:

1. **Subgroup C1: Segment Endpoints ($N = 283$)**
   - 139 left endpoints (`pos = 0`, right neighbor exists, left neighbor missing due to dual candle).
   - 139 right endpoints (`pos = len - 1`, left neighbor exists, right neighbor missing due to dual candle).
   - 5 singletons (`pos = 0` and `pos = len - 1`, length = 1, bounded by dual candles on both sides; zero neighbors).
   - *Blocking reason:* True geometric boundary truncation within the segment. Two-sided prominence is mathematically impossible because one or both alternating neighbors are missing.
   - In hierarchical simplification, segment endpoints are permanent boundary survivors: they are never removed by interior excursion (`scale = None`, `boundary_survivor = True`).

2. **Subgroup C2: Interior Hierarchy Survivors ($N = 133$)**
   - 133 events located at interior positions ($0 < \text{pos} < \text{len} - 1$) in segments of length $> 2$.
   - **BOTH left and right alternating neighbors exist in `bplusc_sequence_reference.parquet`!**
   - In fact, the build pipeline **ACTUALLY COMPUTED** `prominence_min_log`, `prominence_geo_log`, `prominence_balance`, and `prominence_vol_norm` for all 133 events during execution!
   - *Why are they None in the output artifacts?*
     In `build_stage2i_b1_comparison.py`:
     ```python
     boundary_ids = initial_endpoints | survivors_across_designs
     interior_resolved_ids = alternating_ids - boundary_ids
     ...
     p_info = prominence_metrics_by_id.get(eid, {}) if is_resolved else {}
     ```
     Because these 133 events survived iterative simplification down to the last 2 events in their segment, they were flagged `boundary_survivor = True`.
     The pipeline defined `interior_resolved_ids` by excluding **all** boundary survivors (including hierarchy survivors), and then gated output writing on `is_resolved`!
     Thus, **valid, already-computed two-sided prominence was discarded in the final output table solely because their hierarchy scale was None**!

#### B. Existing Quantities Computable Without Changing Approved Semantics
- **For Subgroup C2 (133 Interior Survivors):**
  - Two-sided prominence (`prominence_min_log`, `prominence_geo_log`, `prominence_balance`, `prominence_vol_norm`) is **100% mathematically valid and already verified in pipeline memory**.
  - Local volatility scale is available for 133/133.
  - Path geometry metrics (`path_efficiency`, `path_persistence`, `path_alternation`) are 100% valid.
- **For Subgroup C1 (283 Endpoints):**
  - Local volatility scale is available for 283/283.
  - One-sided excursion (outgoing for left endpoints, incoming for right endpoints) is computable for 278 events (139 left + 139 right). Singletons (5) have no neighbor.
  - Canonical two-sided prominence is structurally blocked.

#### C. Quantities Blocked Without a New Methodological Choice
- For all 416 events: `hierarchy_min_scale` and `hierarchy_geo_scale` are `None`. Because they survived to the end of segment simplification, their removal cost was never triggered.
- `ord_survival_scale` is `None` for all 416 events.
- For 283 endpoints: two-sided prominence is blocked.

#### D. Methodological Choices Required from User
1. **Option C1 (Decouple Prominence from Hierarchy Resolution — HIGHLY COMPATIBLE):**
   - Allow pivots with `hierarchy_min_scale = None` to expose their valid, already-computed two-sided prominence fields.
   - *Impact:* Instantly recovers 4 canonical Layer 1 fields for **133 events** without creating new metrics, without altering existing resolved events, and without changing segment geometry!
2. **Option C2 (One-Sided Excursion for Segment Endpoints):**
   - Introduce an explicit one-sided excursion metric for the 278 single-neighbor endpoints.
   - *Impact:* Requires defining a separate one-sided contract. Cannot be placed into canonical two-sided `prominence_min_log` without conflating one-sided and two-sided definitions.
3. **Option C3 (Censored Survival Scale for Boundary Survivors):**
   - For boundary survivors, define survival scale as right-censored at the maximum excursion observed within the segment (e.g. "survived at least $X\%$").
   - *Impact:* Avoids falsely assigning Tier 10 ($\ge 25\%$) to small-segment survivors while recognizing that they were not removed.
4. **Option C4 (Cross-Barrier Hierarchical Simplification):**
   - Allow simplification to bridge across dual candle barriers into adjacent segments.
   - *Impact:* Violates the dual-barrier isolation rule and alters existing 2,867 resolved events.

#### E. Potential Event Coverage
- Under Option C1: **133 events** immediately receive 4 canonical Layer 1 fields (`prominence_min_log`, `prominence_geo_log`, `prominence_balance`, `prominence_vol_norm`).
- Under Option C2: 278 events receive auxiliary one-sided metrics.

---

### Group D: `dataset_edge_censored` ($N = 2$)

#### A. Why Currently Unresolved?
- **`P4H_000006_HIGH` (bar index 6):** Left boundary of the dataset. Preceding 4H market history prior to 2019-09-08 is unobserved in the 15,445-bar dataset. TR-42 volatility lookback has only 6 bars (requires $\ge 10$), so volatility scale is also `None`.
- **`P4H_015442_LOW` (bar index 15442):** Right boundary of the dataset. Subsequent 4H market history after 2026-09-03 is unobserved. (TR-42 volatility scale is available: 840.25 USDT).

#### B. Existing Quantities Computable Without Changing Approved Semantics
- Neither event can receive two-sided prominence or finite hierarchy scale within the fixed dataset.

#### C. Quantities Blocked Without a New Methodological Choice
- All 19 canonical fields.

#### D. Methodological Choices Required from User
1. **Option D1 (Data Ingestion Resolution):**
   - Expand the canonical candle dataset: prepend 4H history prior to 2019-09-08 (resolving `P4H_000006_HIGH`); append 4H history after 2026-09-03 as new candles close (resolving `P4H_015442_LOW`).
   - *Impact:* Natural resolution via data coverage. Zero methodological distortion.
2. **Option D2 (Permanent Dataset Boundary Censoring):**
   - Accept that boundary pivots of any finite dataset are fundamentally right- and left-censored (`special_state = "dataset_edge_censored"`).

#### E. Potential Event Coverage
- Under Option D1: 2 events become ordinary sequence events once data is expanded.
- Under Option D2: 2 events remain permanently unresolved.

---

## 5. Exact Dependencies Across the 4 Canonical Layers

| Layer | Canonical Field | Required Upstream Inputs | Blocking Dependency for Unresolved Events | Downstream Reranking Impact if Expanded |
|---|---|---|---|---|
| **Layer 1** | `prominence_min_log` | Left + right alternating neighbors | Missing for 300 duals, 865 same-type, 283 endpoints, 2 edges. **EXISTS for 133 interior DSB survivors.** | None on existing raw values. |
| **Layer 1** | `prominence_geo_log` | Left + right alternating neighbors | Same as above. | None on existing raw values. |
| **Layer 1** | `prominence_balance` | Left + right alternating neighbors | Same as above. | None on existing raw values. |
| **Layer 1** | `prominence_vol_norm` | Prominence min + TR-42 vol scale | Blocked whenever prominence is None. (Vol scale exists for 1579/1583). | None on existing raw values. |
| **Layer 1** | `hierarchy_min_scale` | Finite removal in segment hierarchy | Blocked for all 1,583 (duals/same-type unsequenced; DSB/edges are boundary survivors). | None on existing raw values unless sequence rebuilt. |
| **Layer 1** | `hierarchy_geo_scale` | Finite removal in segment hierarchy | Same as above. | None on existing raw values unless sequence rebuilt. |
| **Layer 2** | `rank_prominence_min` | `prominence_min_log` | Blocked whenever prominence is None. | **CRITICAL:** Adding new events to in-sample ranking denominator ($N = 2867 \to 2867 + \Delta N$) **shifts percentile ranks of the 2,867 resolved events!** Preserved only if evaluated against frozen distribution. |
| **Layer 2** | `rank_hierarchy_min` | `hierarchy_min_scale` | Blocked for all 1,583 events. | Shifts existing ranks if denominator expanded. |
| **Layer 2** | `rank_consensus_mean` | All 3 constituent view ranks | Blocked for all 1,583 events (missing constituent ranks). | Shifts existing consensus if constituent ranks shift. |
| **Layer 2** | `rank_consensus_median`| All 3 constituent view ranks | Blocked for all 1,583 events. | Shifts existing consensus if constituent ranks shift. |
| **Layer 3** | `ord_survival_scale` | `hierarchy_min_scale` | Blocked for all 1,583 events. Boundary survivors have `scale = None`. | Assigning Tier 10 would falsely distort short segments. |
| **Layer 4** | `conf_unanimous_t10..30`| All 3 constituent view ranks | Blocked for all 1,583 events. Unanimous rule requires 3 of 3 views. | None to existing classifications. |
| **Layer 4** | `conf_majority_t10..30` | All 3 constituent view ranks | Blocked for all 1,583 events. Current voting contract requires 3 views. | None to existing classifications. |

---

## 6. The Percentile Reranking Dilemma (Layer 2 Invariant)

A critical mathematical finding of this diagnostic study concerns **Layer 2 Continuous Ordering**:

In the canonical B1 contract, percentile ranks are computed empirically as:
$$\text{rank}(v) = \frac{\text{searchsorted}(\text{finite\_values}, v, \text{side="right"})}{N}$$
where $N = 2,867$ is the resolved reference population.

If any currently unresolved events (e.g. the 133 interior DSB survivors, or the 865 same-type exclusions) obtain a valid Layer 1 metric and are incorporated into the ranking population:
1. **In-Sample Reranking ($N \to N + \Delta N$):**
   - The ranking denominator expands from $2,867$ to $2,867 + \Delta N$ (e.g. $3,000$ or $3,732$).
   - Dividing by a larger denominator **mathematically alters the exact percentile ranks of the already resolved 2,867 events**!
   - This would alter downstream quantile bins (ORD-Q3/Q4/Q5) and could shift boundary events across agreement tail thresholds (CONF-T10/T20/T25/T30).
2. **Frozen Reference Projection (Out-of-Sample Ranking):**
   - Newly resolved events are evaluated against the **fixed, frozen 2,867 distribution**:
     $$\text{rank}_{\text{new}}(v) = \frac{\text{searchsorted}(\text{frozen\_2867}, v, \text{side="right"})}{2,867}$$
   - This **guarantees 100% invariance** for the existing 2,867 resolved ranks.
   - However, the ranks of the new events represent a projection relative to the reference population rather than a strict uniform empirical distribution over the combined set.

This choice is a **fundamental methodological decision** that must be explicitly resolved before any new continuous ranks are published.

---

## 7. Master Summary Table

| Unresolved Group | Event Count ($N$) | Layer 1 Recoverable? | Layer 2 Recoverable? | Layer 3 Recoverable? | Layer 4 Recoverable? | Needs New Methodology? | Would Affect Existing 2,867? |
|---|---:|---|---|---|---|---|---|
| **Group A: `dual_unordered`** | 300 | **NO** | **NO** | **NO** | **NO** | **YES** | **OPEN** (YES if LTF ordering; NO if auxiliary interval) |
| **Group B: `technical_same_type_exclusion`** | 865 | **PARTIAL** | **PARTIAL** | **NO** | **NO** | **YES** | **OPEN** (NO if bracketed prominence + frozen rank; YES if non-alternating hierarchy or in-sample rerank) |
| **Group C: `dual_separator_boundary`** | 416 | **PARTIAL** | **PARTIAL** | **NO** | **NO** | **YES** | **OPEN** (NO if decoupling 133 interior survivors + frozen rank; YES if in-sample rerank or cross-barrier hierarchy) |
| — *Subgroup C1: Segment Endpoints* | 283 | NO | NO | NO | NO | YES | NO (unless cross-barrier hierarchy) |
| — *Subgroup C2: Interior Hierarchy Survivors* | 133 | YES (prominence) | PARTIAL (prominence rank) | NO | NO | YES (decoupling gate) | NO (under frozen reference ranking) |
| **Group D: `dataset_edge_censored`** | 2 | **NO** | **NO** | **NO** | **NO** | **YES** | **NO** (resolved by external data ingestion) |
| **Total Unresolved** | **1,583** | **PARTIAL (133–998)** | **PARTIAL (133–998)** | **NO** | **NO** | **YES** | **OPEN** |

*Table Semantics:*
- **YES:** Recoverable using already existing mathematical code/geometry.
- **PARTIAL:** Some fields (e.g. prominence min/geo/balance/vol-norm) are recoverable, but others (e.g. hierarchy removal scale, full consensus) remain blocked.
- **NO:** Fundamentally uncomputable without violating physical reality or manufacturing arbitrary values.
- **OPEN:** Affect on existing resolved events depends on the specific policy chosen by the user.

---

## 8. Conditional Scenario Counts

To assist user decision-making without pre-selecting a solution, five explicit, mutually exclusive scenarios are modeled:

```
Scenario 0 (Strict Baseline):        [1,583 Unresolved] (0% recovered)
Scenario 1 (Decouple 133 DSB):       [1,450 Unresolved] ──► 133 events gain Layer 1 prominence
Scenario 2 (Scenario 1 + Same-Type): [  585 Unresolved] ──► 998 events gain Layer 1 prominence
Scenario 3 (Scenario 2 + Endpoints): [  305 Unresolved] ──► 1,278 events gain 1-sided/2-sided metrics
Scenario 4 (LTF Dual Sequencing):    Alters 145 segments ──► Recalculates 2,867 existing events
Scenario 5 (Non-Alternating DAG):    Abolishes Prepass   ──► Invalidates 2,867 existing hierarchy
```

### Exact Numerical Breakdown by Scenario:

1. **Scenario 0: Strict Current Contract (Zero Methodological Changes)**
   - Events gaining $\ge 1$ Layer 1 field: **0**
   - Events gaining full Layer 1: **0**
   - Events gaining Layer 2, 3, or 4: **0**
   - Remaining completely unresolved: **1,583** ($100.0\%$)
   - Downstream impact on 2,867 resolved: **ZERO (100% invariant)**.

2. **Scenario 1: Decouple Prominence from Hierarchy Resolution for 133 Interior Segment Survivors**
   - *Logic:* Expose the two-sided prominence metrics that were already computed for the 133 interior hierarchy survivors, leaving their `hierarchy_min_scale` as `None`.
   - Events gaining $\ge 1$ Layer 1 field: **133** ($8.40\%$ of unresolved)
   - Events gaining full Layer 1: **0** (hierarchy scale remains None)
   - Events gaining Layer 2 (`rank_prominence_min` under frozen reference): **133**
   - Events gaining Layer 3 (survival scale): **0**
   - Events gaining Layer 4 (agreement states): **0**
   - Remaining completely unresolved: **1,450** ($91.60\%$)
   - Downstream impact on 2,867 resolved: **ZERO** if frozen reference ranking is used; **shifts percentiles** if in-sample reranking is used.

3. **Scenario 2: Bracketed Prominence for Same-Type Exclusions (Combined with Scenario 1)**
   - *Logic:* Inherit the cluster-bracketed alternating neighbors of the winning sibling for the 865 same-type exclusions.
   - Events gaining $\ge 1$ Layer 1 field: **998** ($133 + 865 = 63.04\%$ of unresolved)
   - Events gaining full Layer 1: **0**
   - Events gaining Layer 2 (`rank_prominence_min` under frozen reference): **998**
   - Events gaining Layer 3 or 4: **0**
   - Remaining completely unresolved: **585** ($36.96\%$ — 300 duals, 283 endpoints, 2 edges)
   - Downstream impact on 2,867 resolved: **ZERO** if frozen reference ranking is used.

4. **Scenario 3: Auxiliary One-Sided Excursion for Segment Endpoints and Edges**
   - *Logic:* Introduce a non-canonical one-sided excursion metric for the 280 single-neighbor boundary events (139 left endpoints, 139 right endpoints, 1 left edge, 1 right edge).
   - Events gaining auxiliary metric: **280** (or **1,278** combined with Scenario 2)
   - Remaining completely unresolved: **305** ($19.27\%$ — 300 duals + 5 singletons)
   - Downstream impact on 2,867 resolved: **ZERO** if kept as separate auxiliary namespace (`reference__excursion_onesided_log`).

5. **Scenario 4: Lower-Timeframe Dual Sequencing**
   - *Logic:* Reconstruct 1m/5m/1h temporal order for the 150 dual candles.
   - Potential sequence integration: up to **300 dual events**.
   - Downstream impact on 2,867 resolved: **HIGH (DESTRUCTIVE TO BASELINE)**. Eliminating dual candle barriers merges segments, changes alternating neighbor pairings, alters hierarchy iteration sequences, and forces a full recalculation of the 2,867 resolved events.

6. **Scenario 5: Full Non-Alternating DAG/Tree Hierarchy**
   - *Logic:* Abolish same-type prepass and run tree simplification across all 4,150 non-dual events.
   - Potential integration: **1,148 events** (865 same-type + 283 endpoints).
   - Downstream impact on 2,867 resolved: **HIGH (DESTRUCTIVE TO BASELINE)**. Completely invalidates existing hierarchy scales, survival tiers, and agreement states.

---

## 9. Final Claim Audit & Methodological Integrity

In strict adherence to `docs/research/RESEARCH_CLAIM_DISCIPLINE.md` and `AGENTS.md`:

| Claim / Item | Audit Status | Evidence & Resolution |
|---|---|---|
| **Total Unresolved Count** | **VERIFIED** | Exactly 1,583 rows in `master_event_reference.parquet` have `representation_resolved == False`. |
| **Category Breakdown** | **VERIFIED** | Exactly 300 dual_unordered, 865 technical_same_type_exclusion, 416 dual_separator_boundary, 2 dataset_edge_censored. |
| **DSB Subgroup Split** | **VERIFIED** | Exactly 133 interior survivors (both alternating neighbors exist) and 283 endpoints (one or both missing). |
| **No Fictional Values** | **VERIFIED** | Zero `0`, `False`, or placeholder values substituted into production tables. |
| **No Semantic Degradation** | **VERIFIED** | Unresolved events are strictly NOT labeled micro, noise, insignificant, or scale=0. |
| **Production B1 Integrity** | **VERIFIED** | All 23 production artifacts in `stage2i_b1_reference_contract_comparison/` match original SHA-256 checksums. |
| **Canonical Spec Invariance** | **VERIFIED** | `PA_STRUCTURE_CANONICAL.md` is 100% byte-identical to starting HEAD `15e70f8579a1268725e1940647886172d46750f8`. |
| **No B2 Leakage / Launch** | **VERIFIED** | `stage2i_b2_predictiveness/` does not exist; B2 was not launched. |
| **No Silent Winner Selection**| **VERIFIED** | All 5 scenarios are presented with factual trade-offs; no option is declared "best" or "preferred". |

---

## 10. Summary for User Review

1. **Root Cause:** 1,583 events are unresolved because the current B1 pipeline applies strict single-timeframe 4H boundaries, requiring two-sided alternating neighbors within isolated non-dual segments and finite hierarchy removal.
2. **Immediate Non-Destructive Opportunity:** 133 interior DSB events already possess mathematically valid two-sided prominence in pipeline memory; exposing them requires only decoupling prominence output from hierarchy removal status.
3. **Cluster Opportunity:** 865 same-type exclusions could receive two-sided prominence if the user approves cluster-bracketed neighbor inheritance (Scenario 2).
4. **Key Constraint:** Adding newly resolved events to Layer 2 continuous ranking requires deciding between **in-sample reranking** (which shifts the percentile ranks of the existing 2,867 events) versus **frozen reference projection** (which preserves the existing 2,867 ranks).
5. **No Action Taken:** All 1,583 events remain `None` and `UNRESOLVED` in canonical artifacts pending user evaluation.
