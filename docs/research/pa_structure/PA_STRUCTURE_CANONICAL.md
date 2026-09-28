# PA Structure — Canonical Research Specification

Status: **ACTIVE RESEARCH AUTHORITY**

Branch: `archive/btc-macro-nautilus-2026-09-03`

This document is the canonical methodology handoff for the BTC price-action structure research line. It exists so that a later Codex session, Nautilus component, rule-based bot, ML pipeline, or another implementation can reconstruct not only the code but the intended meaning, causal contract, accepted results, unresolved choices, and deprecated approaches.

If this file conflicts with an older PA-structure note or legacy structural-level artifact, this file takes precedence unless a later explicitly versioned canonical document supersedes it.

---

## 1. Research goal

Build a causal, reproducible representation of BTC price-action structure that can eventually support:

1. raw local turning points;
2. distinction between internal micro-fluctuation and independent reaction/movement;
3. repeated reaction areas;
4. structural boundaries and active ranges/corridors;
5. distance / available movement potential to the next relevant boundary;
6. later overlays such as Fibonacci, Volume Profile, SFP, Order Blocks, trend/regime context, and lower-timeframe trade logic.

The research must not assume that every mathematically valid pivot is a structural level.

The intended conceptual pipeline is:

`canonical candles -> raw pivots -> independent reactions -> reaction zones -> structural boundaries/ranges -> contextual overlays -> trading logic`

Only the raw-pivot layer and the Stage 2I-B research architecture are currently fixed. The semantic rules that convert raw pivots into independent reactions remain under research.

---

## 2. Status vocabulary

Every methodological item in this research line must be marked with one of these states:

- **FIXED** — accepted project contract; safe to reproduce and use downstream.
- **PROVISIONAL** — useful working hypothesis or diagnostic, not final semantics.
- **OPEN** — unresolved methodological choice; downstream code must not silently choose.
- **REJECTED / DEPRECATED** — explicitly not authoritative for the canonical line.

A later implementation must not promote PROVISIONAL or OPEN logic to production semantics without an explicit research decision and version update here.

---

## 3. Authoritative data and scope

### 3.1 Current calibration timeframe

**FIXED for Stage 2I-A and its review:** BTCUSDT futures `4H` only.

The 4H timeframe is a calibration layer for the PA-structure methodology. It is not a claim that the final trading system should operate only on 4H.

### 3.2 Canonical Stage 2I-A source population

From `docs/research/stage2i_a_raw_4h_pivots.md`:

- canonical BTCUSDT futures 4H rows: `15,446`;
- complete rows used: `15,445`;
- incomplete rows excluded: `1`;
- complete population is contiguous after excluding the first partial 4H candle.

Canonical data root:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/`

Stage 2I-A research artifacts:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_a_raw_4h_pivots/`

### 3.3 Data-pipeline rule

Any future data build / feature build / collection in this line must read and obey:

`docs/DATA_PIPELINE_RULES.md`

Long-running generated data and progress must be persisted to disk **no later than every 20 minutes**. Large datasets remain outside Git; code, tests, methodology, lightweight reports, manifests or references belong in Git as appropriate.

---

## 4. Stage 2I-A — raw 4H pivots

Status: **FIXED**

Implementation commit:

`71b6158a61503fde9145f3565fe0be3149bbab76`

Authoritative report:

`docs/research/stage2i_a_raw_4h_pivots.md`

### 4.1 Purpose

Stage 2I-A is a **raw candidate generator**, not a structural-level model.

It deliberately keeps mathematically valid local extrema that may later prove to be:

- micro-fluctuation inside one continuing movement;
- local reaction;
- larger structural reaction;
- part of a dense sideways area;
- otherwise non-useful for structural boundaries.

No significance filter is applied at this stage.

### 4.2 Strict five-bar pivot definition

For complete 4H candles, candle `i` is a raw HIGH when:

`high[i] > high[i-2], high[i-1], high[i+1], high[i+2]`

Candle `i` is a raw LOW when:

`low[i] < low[i-2], low[i-1], low[i+1], low[i+2]`

Strict inequality is required. Equal values do not qualify that side.

A candle may satisfy both HIGH and LOW conditions. Such cases are retained as two raw events until Stage B treatment is explicitly decided.

### 4.3 Stage 2I-A population result

- raw HIGH events: `2,243`;
- raw LOW events: `2,207`;
- total raw pivot events: `4,450`;
- pivot-bearing candles: `4,300`;
- dual HIGH+LOW candles: `150`;
- raw event density: `28.812 events / 100 complete bars`.

### 4.4 Causality contract

**FIXED.**

A pivot's center-candle timestamp is the event timestamp, but the pivot is not known at that time.

The event becomes available only when the second candle to the right has closed.

Therefore:

- `pivot_timestamp` = center candle time;
- `confirmation_timestamp` = close of the second right-hand candle;
- `available_from` = same causal availability point.

Fields are separated by information status:

- `causal__*` — known by `available_from`;
- `postevent__*` — uses future-relative information and is diagnostic only unless a later contract explicitly authorizes it.

Future implementations must preserve this distinction. A useful post-event diagnostic does not become a live predictor merely because it correlates with a later label.

### 4.5 Stage 2I-A artifacts

Authoritative data artifact:

`raw_4h_pivots.parquet`

Authoritative schema:

`raw_4h_pivots_schema.json`

The Stage 2I-A dataset has `4,450` rows and `237` columns, with schema/data dictionary, report, manifest, checksums, QA charts and deterministic rerun verification.

Stage 2I-A QA at completion:

- Stage-specific tests: `10 passed, 0 failed`;
- production QA: PASS;
- two production reruns produced byte-identical artifacts;
- internal checksums: PASS.

---

## 5. Stage 2I-A structure review

Status: **FIXED AS DIAGNOSTIC EVIDENCE**

Review commit:

`b38aff90e2d6d056ebd14ae9bbecece1fefe0bb8`

Authoritative report:

`docs/research/stage2i_a_pivot_structure_review.md`

The review does **not** define Stage B labels or thresholds. Its results constrain what Stage B may reasonably assume.

### 5.1 Key empirical findings

- positive-gap median between pivot events: `3 bars / 12 hours`;
- `54.0%` of consecutive event pairs have no more than two intervening candles;
- same-candle dual pairs are `3.37%` of consecutive event pairs;
- opposite-pivot move median: `3.25%`;
- opposite-pivot move IQR: `2.04–5.24%`;
- opposite-pivot duration median: `4 bars`;
- p10–p90 duration: `1–9 bars`;
- outgoing/incoming move ratio median: `0.883`;
- outgoing/incoming move ratio IQR: `0.563–1.482`.

Across the central 98% of the examined opposite-pivot move distributions there is no obvious empty interval that supplies a defensible natural cutoff between micro-fluctuation and independent movement.

This means Stage B must not claim that the raw data discovered an obvious universal threshold when they did not.

### 5.2 Scale dependence

Yearly median absolute opposite-pivot movement ranges from approximately `272.8` to `2,638 USDT`.

Yearly median percentage movement ranges from approximately `2.48%` to `5.47%`.

Pivot density is more stable: approximately `27.49–31.24 events / 100 bars` by year.

Consequences:

- one fixed absolute-USDT cutoff would be strongly price-era dependent;
- one fixed percentage cutoff would reduce but not eliminate regime dependence;
- neither is currently authorized as the Stage B definition.

### 5.3 Dual HIGH+LOW candles

Status: **OBSERVED / TREATMENT OPEN**

The 150 dual candles are not ordinary temporal HIGH→LOW transitions. The storage tie-break creates two event rows with the same bar/time, but 4H candles provide no intrabar ordering evidence.

Empirically, dual candles show elevated local activity:

- median range / neighbor mean: approximately `2.49x`;
- median volume / neighbor mean: approximately `2.50x`;
- median trades / neighbor mean: approximately `2.25x`;
- median open gap: approximately `0%`.

Zero-gap dual pairs must therefore remain distinguishable from positive-gap transitions.

No canonical decision yet exists on whether Stage B should treat the two raw events separately, jointly, or defer them.

### 5.4 Breach-time construction effect

A strict five-bar pivot cannot be breached before bar `+3` after the pivot center because bars `+1` and `+2` are part of its confirmation condition.

Observed full-population breach shares by horizon:

- by `+3`: `14.63%`;
- by `+6`: `37.08%`;
- by `+12`: `55.66%`;
- by `+24`: `69.03%`.

Any future "rapid invalidation" or survival feature must respect `available_from` and this mechanical construction effect. It must not interpret the protected confirmation window as behavioral evidence.

---

## 6. Human calibration examples

Status: **PROVISIONAL / NON-LABEL**

The following 2026 price intervals were used only to compare raw data with human visual inspection:

- approximately `59.0–60.5k`;
- approximately `61.5–62.5k`;
- approximately `66.5–69.0k`.

Observed raw pivot counts in the review:

- `59.0–60.5k`: 6 events, all LOW;
- `61.5–62.5k`: 15 events, 13 LOW / 2 HIGH;
- `66.5–69.0k`: 46 events, 23 HIGH / 23 LOW.

These intervals are **not canonical zones**, **not labels**, and must not be used as ground truth.

Their purpose is to expose a central problem: many raw HIGH/LOW events may occur inside one traded price area. Simple price coincidence or raw pivot count does not by itself prove repeated independent structural reactions.

---

## 7. Stage 2I-B — micro fluctuation vs independent reaction

Overall semantic status: **OPEN**

Research architecture status: **FIXED — DUAL-LAYER APPROACH**

The project has explicitly chosen to develop **both** a retrospective structural reference and a separate causal recognition layer. This architecture is canonical. The concrete algorithms inside B1 and B2 remain open until researched and approved.

### 7.1 Research question

Determine whether a raw pivot marks only an internal fluctuation inside a continuing movement or separates movements sufficiently distinct to be treated as an independent reaction event.

Example conceptual distinction:

`61.0 -> 61.5 -> 61.4 -> 62.0`

A mathematical pivot around 61.5/61.4 may still be an internal fluctuation of one larger upward movement.

Versus:

`63.0 -> 61.5 -> 62.8`

The pivot near 61.5 may mark the end of a distinct downward movement and the start of a distinct upward movement.

Price equality or proximity alone does not decide this distinction.

### 7.2 Fixed Stage B architecture

**FIXED:** Stage 2I-B is split into two layers.

#### Stage 2I-B1 — Retrospective structural reference

Purpose:

Use the full realized path around/after raw pivots to investigate which raw pivots actually separated distinct movements when viewed post factum.

B1 may use future-relative information because it is an offline research/reference layer.

B1 output is **not** a live signal and **not** a feature available at pivot time.

Its role is to provide a transparent structural reference against which causal schemes can later be evaluated.

The overall B1 reference semantics remain OPEN, but the candidate-preservation policy below is FIXED for the B1 research/reference module. Candidate retrospective families include:

- two-sided retrospective prominence;
- retrospective sequence segmentation;
- refinements derived from Stage A diagnostics.

B1 must compare plausible designs rather than silently choosing an arbitrary cutoff.

**FIXED candidate-preservation policy (B + C):**

- same-type prepass is a technical transform used to construct an alternating representation; it is not a semantic significance filter;
- a same-type pivot excluded from an alternating representation must remain preserved in the research population with explicit provenance such as `excluded_from_alternating_sequence = true`;
- such an excluded pivot must not be labelled `micro`, `independent = false`, or assigned semantic `structural scale = 0` solely because of the prepass;
- dual HIGH+LOW candles remain unordered on 4H data and must not receive fabricated intrabar HIGH→LOW or LOW→HIGH ordering;
- a dual candle acts as a barrier for same-type prepass runs: pivots of the same type on opposite sides of a dual candle must not be automatically consolidated across that candle;
- when ambiguity remains, B1 research should preserve the additional candidate rather than discard a potentially meaningful reaction prematurely.

This policy applies to the retrospective research/reference module only. It is not a live Nautilus rule, not a Stage 2I-B2 causal rule, and not a trading filter.

#### Stage 2I-B2 — Causal recognition

Purpose:

Determine when and from which information available after `available_from` a live system could recognize the same type of independent reaction without access to future data.

B2 must use only information genuinely available by each tested recognition time.

B2 is evaluated against the B1 reference while keeping the information boundary strict.

B2 must measure at least:

- agreement with the retrospective reference;
- false recognition / missed recognition;
- recognition delay in bars/time;
- sensitivity to market regime/scale;
- treatment of right-edge unresolved cases;
- whether performance is stable across time periods.

Candidate causal families include:

- causal confirmation-window independence;
- causal rolling historical prominence;
- later causal schemes justified by the B1 findings.

The concrete B2 recognition rule is still OPEN.

### 7.3 Hard separation between B1 and B2

**FIXED.**

Retrospective information used to construct B1 reference labels must never leak into B2 predictors or live inference.

Every Stage B field/output must explicitly identify whether it is:

- `reference/postevent` — allowed only for retrospective labeling/evaluation;
- `causal` — available to a live recognizer at a stated time;
- `metadata` — identifiers/provenance only.

A B1 label can be used as a training/evaluation target only if its exact generation method and hindsight window are versioned and documented.

A B1 diagnostic cannot be reused as a B2 feature merely because it predicts the B1 label.

### 7.4 What remains open

The dual-layer architecture resolves the previous either/or question of retrospective versus causal research: **the project will do both**.

The following methodological questions remain OPEN:

1. exact B1 retrospective reference definition;
2. exact B2 causal confirmation/recognition definition;
3. exact downstream representation of dual HIGH+LOW candles beyond their fixed unordered/barrier treatment in B1;
4. denominator choice for any retracement-style measure;
5. horizon and scale for concepts such as trapped / invalidated;
6. how to handle ambiguous/unresolved B1 cases rather than forcing a binary label;
7. how to score B2 when B1 itself is uncertain or design-dependent.

A downstream implementation must not silently answer these questions.

### 7.5 Next research order

**FIXED order:**

1. run Stage 2I-B1 research first;
2. inspect/compare retrospective reference designs;
3. explicitly choose or refine the B1 reference contract;
4. only then run Stage 2I-B2 causal recognition research against that reference;
5. do not proceed to Stage 2I-C reaction-zone semantics until Stage B is sufficiently resolved for independent-reaction events to be reproducible.

This ordering prevents a causal recognizer from being optimized against an unexamined or unstable target.

### 7.6 Stage 2I-B1 completed research evidence

Status: **RESEARCH COMPLETE / REFERENCE SEMANTICS REMAIN OPEN**

Implementation and factual-report commit:

`97533acadccf591a9aa026610b7fa00b69e7aebd`

Authoritative factual report:

`docs/research/stage2i_b1_retrospective_reference.md`

Generated artifact root:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_retrospective_reference/`

Verified empirical findings:

- all 4,450 frozen Stage 2I-A pivot IDs are preserved;
- the primary sequence defers all 300 dual events and creates no fictitious same-bar temporal transition;
- deterministic same-type consolidation leaves 3,226 pivots in the primary alternating sequence;
- two-sided prominence, minimum/geometric removal hierarchies, and log/volatility scale sweeps show a continuous multiscale population rather than a natural binary separation;
- minimum two-sided prominence and the primary hierarchy agree strongly (`r = 0.916` on normalized scores);
- minimum and geometric hierarchy ranks are highly stable (`r = 0.984`);
- local-volatility normalization changes membership but reduces volatility-regime density drift;
- the tested asymmetric `outgoing / incoming` retracement-ratio sweep has weak agreement with the magnitude-based designs and a cascade between parameter 0.3 and 0.4;
- dual extrema can receive unordered two-sided diagnostics, but 4H data still cannot place them in one temporal alternating sequence;
- year/regime differences remain, while direct dependence on absolute BTC price level is small after log/volatility normalization;
- no final MICRO/INDEPENDENT labels, reference cutoff, B2 features, zones, signals or trading results were created.

Rejected as a standalone authority:

- the specific tested asymmetric retracement-ratio sweep. Its cascade and weak cross-design agreement make it unsuitable as the sole B1 reference. This does not reject all future retracement formulations.

### 7.7 Same-type prepass sensitivity audit and accepted B1 preservation policy

Audit commit:

`6d707801bd2af4b81d046614b19bca4475a49eed`

Authoritative audit report:

`docs/research/stage2i_b1_same_type_prepass_audit.md`

Generated artifact root:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_same_type_prepass_audit/`

Verified audit findings:

- the current prepass removed 924 non-dual same-type pivots before the hierarchy;
- only 88/924 (`9.5%`) had realized adverse departure below 1%;
- median realized adverse departure was `2.176%`;
- 271/924 (`29.3%`) exceeded 3%, 88/924 (`9.5%`) exceeded 5%, and 31/924 (`3.4%`) exceeded 7.5%;
- therefore prepass exclusion alone does not empirically justify semantic `structural scale = 0` or a `micro` label;
- 77 removals were dual-mediated; dual-aware handling rescued 59 events;
- dual-aware changes are concentrated in the local hierarchy and coarse structure remained invariant at the 15% and 25% log scales;
- the audit found no natural binary separation inside the removed population.

**FIXED B1 research/reference decision:** adopt the conservative B + C preservation policy described in §7.2. This decision governs candidate preservation and prepass semantics only. It does not yet choose the full B1 independent-reaction target contract.

Remaining OPEN questions (after sensitivity audit):

1. ~~continuous versus ordinal versus confidence-weighted versus partial-tail reference contract~~ — **RESOLVED: user selected LAYERED contract; see §7.8.**
2. minimum versus geometric hierarchy emphasis;
3. whether local-volatility normalization belongs in the reference or remains sensitivity-only;
4. whether to redesign or exclude the asymmetric retracement arm from consensus;
5. whether dual outside bars remain deferred or become a distinct unordered state;
6. boundary-censoring semantics in a future reference;
7. an explicit ambiguity policy before any B2 target is fixed.

This study does not promote B1 semantics from OPEN to FIXED for all questions. Question 1 above has been explicitly resolved by user decision; see §7.8. Stage 2I-B2 must not start against an implicit target; questions 2–7 remain OPEN.

---

### 7.8 B1 reference contract — user-approved decision: LAYERED

**Status: FIXED by explicit user decision.**

Decision commit: see commit message `docs: Stage 2I-B1 fix layered reference contract` on branch `archive/btc-macro-nautilus-2026-09-03`.

**Decision:** The Stage 2I-B1 retrospective reference contract is LAYERED.

**Rationale (user-stated):** At the research stage, the maximum amount of already-computed retrospective structural information must be preserved per pivot for later analysis rather than discarding any dimension prematurely.

This is an information-preservation decision, not an empirical proof that a layered representation is superior to alternatives. No alternative is declared inferior.

**What the layered contract means:**

For each B1 pivot event, the reference contract simultaneously exposes all of the following already-computed retrospective outputs, joined by `event_id`:

#### Layer 1 — Structural Components (CONT-COMPONENTS)

**Status: FIXED.**

Source artifact: `reference_continuous.parquet` (artifact root: `stage2i_b1_reference_contract_comparison/`).

Fields retained in canonical contract:

| Field name | Description |
|---|---|
| `reference__prominence_min_log` | Two-sided retrospective prominence, minimum of left/right excursion (log scale) |
| `reference__prominence_geo_log` | Two-sided retrospective prominence, geometric mean of left/right excursion (log scale) |
| `reference__prominence_balance` | Balance ratio: `min / geo` — relative symmetry of the two-sided excursion |
| `reference__prominence_vol_norm` | Prominence normalized by local TR-42 volatility estimate |
| `reference__hierarchy_min_scale` | Removal scale under minimum-cost iterative simplification |
| `reference__hierarchy_geo_scale` | Removal scale under geometric-mean-cost iterative simplification |

These are the raw retrospective structural coordinates of a pivot. They are not reduced to a single score. Downstream consumers may use any combination or projection.

Unresolved/censored events carry `None` for all Layer 1 fields. No `0` or placeholder is substituted.

#### Layer 2 — Continuous Ordering (CONT-RANK and CONT-CONSENSUS)

**Status: FIXED.**

Source artifact: `reference_continuous.parquet`.

Fields retained in canonical contract:

| Field name | Description |
|---|---|
| `reference__rank_prominence_min` | Percentile rank of `prominence_min_log` across the resolved population |
| `reference__rank_hierarchy_min` | Percentile rank of `hierarchy_min_scale` across the resolved population |
| `reference__rank_consensus_mean` | Unweighted mean of multiple retrospective view ranks — scale-free consensus |
| `reference__rank_consensus_median` | Unweighted median of multiple retrospective view ranks — outlier-resistant consensus |

None of these ranks is declared the "true strength" of a pivot. They are distinct retrospective structural rankings. `CONT-CONSENSUS-MEAN` and `CONT-CONSENSUS-MEDIAN` are not selected as preferred over the other; both are preserved.

Unresolved/censored events carry `None` for all Layer 2 fields.

#### Layer 3 — Structural Survival Scale (ORD-SURVIVAL)

**Status: FIXED.**

Source artifact: `reference_ordinal.parquet`.

Field retained in canonical contract:

| Field name | Description |
|---|---|
| `reference__ord_survival_scale` | Integer tier 0–10: the log-excursion threshold (0.5%–25%) up to which this pivot survived hierarchical simplification |

Tier 9 = survived ≥ 15%; Tier 10 = survived ≥ 25%. These are the empirically stable macro anchor tiers.

This field must NOT be used to apply semantic labels such as `micro`, `noise`, `non-structural`, `important`, or `unimportant`. A low survival tier indicates early removal under the retrospective simplification algorithm. Its downstream semantic interpretation requires a separate, explicitly approved contract.

**ORD-Q3, ORD-Q4, ORD-Q5:** These quantile discretizations remain as exploratory research diagnostics in the artifact (`reference__ord_q3_band`, `reference__ord_q4_band`, `reference__ord_q5_band` in `reference_ordinal.parquet`). They are NOT part of the canonical layered B1 contract because they impose arbitrary equal-frequency boundaries on an unbroken distribution.

Unresolved/censored events carry `None` for the Layer 3 field.

#### Layer 4 — Cross-View Agreement States (CONF)

**Status: FIXED.**

Source artifact: `reference_confidence.parquet`.

All eight tested agreement-state views are preserved in the canonical contract:

| Field name | Rule | Tail size |
|---|---|---|
| `reference__conf_unanimous_t10` | Unanimous (all 3 retrospective views) | 10% each side |
| `reference__conf_majority_t10` | Majority (≥ 2 of 3 retrospective views) | 10% each side |
| `reference__conf_unanimous_t20` | Unanimous | 20% each side |
| `reference__conf_majority_t20` | Majority | 20% each side |
| `reference__conf_unanimous_t25` | Unanimous | 25% each side |
| `reference__conf_majority_t25` | Majority | 25% each side |
| `reference__conf_unanimous_t30` | Unanimous | 30% each side |
| `reference__conf_majority_t30` | Majority | 30% each side |

Permitted state values per field: `STRONG`, `WEAK`, `AMBIGUOUS`, `UNRESOLVED`.

No tail size or rule is selected as preferred. All 8 views are equally canonical reference views.

`STRONG` and `WEAK` denote agreement-based retrospective tail state only. They do NOT mean:
- ground-truth structural importance;
- probability that the pivot is a genuine structural event;
- correctness;
- trading signal.

`AMBIGUOUS` events are preserved explicitly. They are NOT promoted to `STRONG` or `WEAK` by default. `UNRESOLVED` events (censored/non-resolved) carry `UNRESOLVED` in all agreement fields.

#### Canonical contract: artifact join

The four layers are physically located in three artifacts, all joinable by `event_id`:

| Layer | Artifact | Key field |
|---|---|---|
| 1 + 2 (Components + Continuous Rank) | `reference_continuous.parquet` | `event_id` |
| 3 (Structural Survival) | `reference_ordinal.parquet` | `event_id` |
| 4 (Agreement States) | `reference_confidence.parquet` | `event_id` |

Population anchor: `master_event_reference.parquet` (4,450 rows, all pivots, `event_id` as primary key).

No new merged artifact is created. The logical contract joins by `event_id` across existing artifacts.

#### Invariants preserved by the layered contract

- Master population: 4,450 raw pivot events. Zero events dropped.
- `dual_unordered` events (300): `None` for all layer fields. `UNRESOLVED` in agreement fields.
- `technical_same_type_exclusion` events (865): `None` for all layer fields. `UNRESOLVED` in agreement fields.
- `dual_separator_boundary` events (416): `None` for all layer fields. `UNRESOLVED` in agreement fields.
- `dataset_left_edge_censored` + `dataset_right_edge_censored` (2): `None` for all layer fields. `UNRESOLVED` in agreement fields.
- `ordinary_resolved_sequence_event` events (2,867): all four layers populated.

No `0`, `False`, `micro`, `weak`, or other fictional value is substituted for `None` in unresolved events.

#### B1 retrospective / B2 causal separation — unchanged

The layered B1 contract is entirely retrospective. All fields in all four layers use post-event information (full realized path around/after pivots). They must never be used as B2 predictor inputs or live inference features.

B2 is NOT launched as part of this decision. The B2 causal recognition design remains OPEN and must be researched separately.

---

## 8. Stage 2I-C — repeated reaction zones

Status: **OPEN**

Working research concept:

A reaction zone is a price area formed by multiple **independent reaction events** occurring in a similar price region.

The key unit is the independent visit/reaction, not the number of raw pivots.

Conceptually:

`visit -> rejection/departure -> later separate return -> new rejection/departure`

may support a repeated reaction area.

By contrast, several adjacent candles/pivots inside one continuous movement or one prolonged visit must not automatically count as several reactions.

### 8.1 Zone width

Status: **OPEN**

The project does not currently authorize a fixed width such as:

- X USDT;
- X percent;
- X ATR.

The intended research direction is that the actual prices of the independent reactions should inform the empirical width of a candidate zone.

How to operationalize this without hindsight or circularity remains Stage C research.

### 8.2 Price discovery / ATH

Status: **OPEN WITH CAUSAL CONSTRAINT**

The system must not invent a historical PA resistance above prices that have never previously traded there.

A new reaction area may, however, form causally in price discovery after the market itself creates sufficient independent reaction history in that new area.

The required number/structure of reactions has not yet been fixed.

---

## 9. Stage 2I-D — structural boundaries and ranges

Status: **OPEN**

Working concept only:

- an upper repeated-reaction area may become an upper structural boundary candidate;
- a lower repeated-reaction area may become a lower structural boundary candidate;
- evidence that price repeatedly moves between the two may support a range/corridor representation.

No final rule exists for:

- minimum reaction count;
- boundary lifetime;
- invalidation;
- polarity flip after break;
- range start/end;
- relevance decay;
- interaction across timeframes.

These must be researched rather than hard-coded by assumption.

---

## 10. Separate research branches — do not mix prematurely

The following are intended future context layers but are not part of the current Stage A definition and must not be silently folded into Stage B labels:

### 10.1 Trend / regime

Separate research topic.

Future goal may include uptrend / downtrend / range / ambiguous structure, potentially using HH/HL/LH/LL or other empirical structure features.

No final trend algorithm is currently canonical.

### 10.2 Trendline breakout structure

Separate branch over shared structure.

Causal constraint: a trendline must be defined from already formed points before its breakout. A descending line through formed lower highs may support an upside breakout candidate; an ascending line through formed higher lows may support a downside breakout candidate.

No live entry rule is fixed here.

### 10.3 Fibonacci

Future research may compute continuous retracement ratios between accepted structural points and inspect empirical distributions around conventional levels.

Do not force Fib labels before structural points are defined.

### 10.4 Volume Profile

Future layer may include POC / VAH / VAL / HVN / LVN.

It must be evaluated as a separate feature family before combination with PA structure.

### 10.5 SFP

Future event logic based on established relevant boundaries/zones. Do not use SFP to define Stage B independent-reaction labels unless a later explicit methodology says so.

### 10.6 Order Blocks

Future multitimeframe context layer. Exact OB semantics remain undefined and require a separate contract covering candle/body/wick basis, displacement, BOS/CHOCH relation, causal `available_from`, invalidation, and final timeframes.

### 10.7 Movement potential / minimum 2R

The eventual trading system must be able to evaluate whether sufficient room exists to a relevant obstacle/boundary for at least `2R` under the chosen entry/stop definition.

The obstacle semantics and entry/stop logic are not yet fixed and must not contaminate the current structural-boundary research.

---

## 11. Deprecated / rejected inputs

### 11.1 Legacy `structural_levels.csv`

Status: **DEPRECATED / NON-AUTHORITATIVE**

The old structural-level artifact must not be used in the canonical research line.

Its exact generating methodology, builder, manifest/checksum, and complete category provenance were not recovered with enough confidence. Some historical methodologies were reconstructable, but they had mixed causal status and could not establish exact provenance for the artifact.

Do not train on it, use it as ground truth, or use it to validate the new PA-structure methodology.

### 11.2 Generated/synthetic chart annotations

Assistant-generated illustrative chart labels, rounded prices, fake/synthetic redraws, or manually guessed levels are not authoritative data.

Only canonical market data and explicitly identified human-calibration annotations may be used, with the latter clearly marked as non-label unless formally promoted later.

---

## 12. Requirements for a future Nautilus / bot implementation

A future rule-based implementation must consume an explicitly versioned methodology from this document and executable code/tests. It must not reconstruct semantics from chat history.

At minimum, the production handoff must include:

1. exact candle source and timeframe;
2. exact object definitions;
3. exact `available_from` semantics for every derived object;
4. code that generates each object;
5. unit/integration tests;
6. schema and units;
7. lifecycle/invalidation rules;
8. deterministic fixtures or reproducible artifacts;
9. methodology version / commit hash;
10. explicit list of fields forbidden at live inference because they are post-event.

If the implementation is rule-based, the eventual executable pipeline should reproduce:

`candles -> raw pivots -> independent reactions -> reaction zones -> structural boundaries -> contextual features`

with each arrow backed by a FIXED methodology contract.

---

## 13. Requirements for a future ML training pipeline

If any later system learns Stage B/C/D behavior statistically, the training handoff must additionally preserve:

- label-generation code;
- label methodology version;
- training population definition;
- feature-generation code;
- feature units and semantics;
- causal cutoff for every feature;
- train/validation/test split logic;
- leakage checks;
- dataset manifests and checksums;
- model configuration and random seeds where applicable;
- out-of-sample evaluation protocol;
- explicit distinction between descriptive/post-event diagnostics and predictor-eligible features.

No model may be trained against a retrospective label whose meaning or live availability has not been documented.

Under the fixed Stage 2I-B dual-layer architecture, B1 retrospective labels may serve as offline training/evaluation targets only after their label-generation contract is explicitly fixed. B2 features must remain causal and must never contain B1 post-event information.

---

## 14. Change-control rule

Any future task that changes one of the following must update this canonical document in the same research cycle:

- raw pivot definition;
- Stage B research architecture;
- B1 retrospective reference semantics;
- B2 causal recognition semantics;
- zone formation semantics;
- boundary/range semantics;
- causal availability time;
- feature definition/units;
- source population;
- label generation;
- invalidation/lifecycle rule;
- deprecated/accepted methodology status.

Routine implementation refactors that preserve semantics do not require a methodology change, but code/tests should still carry the relevant version or commit references.

Methodological ambiguity must be surfaced as OPEN rather than silently resolved by an implementation agent.

---

## 15. Current canonical state

As of the Stage 2I-B1 layered-contract decision (§7.8):

| Layer | Status | Canonical meaning |
|---|---|---|
| Canonical 4H candles | FIXED | Stage 2I-A source population |
| Strict five-bar raw pivots | FIXED | Raw local candidate generator |
| Pivot `available_from` | FIXED | After second right-hand candle closes |
| Causal vs post-event namespace | FIXED | Information-status contract |
| Stage 2I-B architecture | FIXED | Dual-layer: B1 retrospective reference + B2 causal recognition |
| B1 retrospective research | COMPLETE EVIDENCE | A/B/C multiscale artifacts and factual report completed |
| B1 candidate-preservation / same-type prepass policy | FIXED | Conservative B + C: dual-aware barrier; excluded same-type pivots preserved and not semantically scale-zero |
| B1 independent-reaction reference semantics | FIXED (LAYERED) | User-approved: LAYERED 4-layer retrospective contract; see §7.8 |
| B2 causal recognition semantics | OPEN | Must be researched after B1 reference is fixed; B1 layered contract is now the target |
| Dual-candle B1 prepass treatment | FIXED | Unordered on 4H and acts as a barrier for same-type consolidation; no fabricated intrabar order |
| Reaction-zone formation | OPEN | Stage 2I-C research |
| Zone width | OPEN | Must not be assumed fixed yet |
| Structural boundaries/ranges | OPEN | Stage 2I-D research |
| Trend/regime | OPEN / SEPARATE | Separate research branch |
| Fib / VP / SFP / OB overlays | OPEN / LATER | Separate feature families |
| Legacy `structural_levels.csv` | DEPRECATED | Must not be used as authority |

The B1 retrospective reference contract is now fixed as LAYERED (see §7.8). Stage 2I-B2 causal recognition research may now be designed, to be evaluated against the fixed B1 layered reference. B2 must remain strictly causal and must not use any B1 post-event field as a predictor input.

