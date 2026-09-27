# Research Claim Discipline

## Purpose

This document defines mandatory claim-discipline rules for research and data-analysis work in this repository.

The goal is to prevent a correct calculation from being turned into an unsupported interpretation, semantic label, preferred parameter, or canonical decision.

For every research/data-analysis task, read this document after `AGENTS.md` and `docs/DATA_PIPELINE_RULES.md`, and before the task-specific canonical methodology.

A research task is not complete until a FINAL CLAIM AUDIT has been performed.

---

## 1. Claim -> metric -> artifact

Every numerical or strong qualitative claim in a final report must trace to:

`claim -> computed metric -> artifact/column -> denominator -> population`

If that trace does not exist, weaken or remove the claim.

Claims using words such as `strictly`, `always`, `zero`, `100%`, `invariant`, `robust`, `stable`, `independent`, `false`, `true`, `best`, `preferred`, `decisive`, or `strongly supports` require an explicit dedicated check.
## 2. Agreement is not truth

Agreement among methods means cross-method agreement only.

Without independent ground truth, do not infer or report accuracy, precision, false-positive rate, zero false claims, probability of truth, or correctness relative to an unknown truth.

## 3. Confidence is not probability

Any `confidence` score/state must define what confidence means.

If it represents agreement among retrospective views, call it agreement-based confidence or cross-view agreement. Do not present it as calibrated probability or probability that an event is truly structural.

## 4. Numerical scale is not a semantic label

Do not automatically convert measurements such as low prominence, early removal, weak tail membership, or `<1%` scale into semantic labels such as `micro`, `noise`, `non-structural`, or `independent = false`.

A semantic mapping requires separate evidence and explicit approval.

## 5. Distinct is not independent

Metrics built from the same source path, shared variables, or related algorithms are not automatically independent evidence sources.

Use terms such as `distinct views`, `complementary views`, or `separately constructed views` unless independence has actually been established.
## 6. Empirical metrics must not be hard-coded

Any value presented as an empirical result — overlap, correlation, share, coverage, Jaccard, stability, invariance, precision, rate, or similar — must be computed from actual data/event sets.

Hard-coded values are permitted only for configuration, tested thresholds, or explicit contract constants, and must be identified as such.

## 7. Denominator discipline

For every rate/share/overlap/stability metric record:

- numerator;
- denominator;
- eligible population;
- unresolved population;
- excluded/censored population.

Head-to-head comparisons must use the same denominator unless a difference is explicitly justified and reported.

Do not collapse distinct states such as dataset censoring, structural unresolved state, dual boundary, technical exclusion, and ordinary resolved event.

## 8. No silent winner selection

A sensitivity sweep does not create a preferred parameter automatically.

Do not select a threshold, tail size, model, representation, or parameter as `best` or `preferred` without an objective selection criterion defined before or independently of the observed result.
## 9. Research result is not a canonical decision

Research may report `supported`, `compatible with evidence`, `candidate`, `trade-off`, or `no clear advantage`.

Do not promote a research finding to `canonical`, `selected architecture`, or `final contract` without explicit approval.

## 10. Distribution stability is not membership stability

If different periods contain different events, do not claim event membership is stable across periods.

Measure and name the actual quantity: distribution stability, share stability, rank drift, category proportions, or regime sensitivity.

## 11. Exhaustive language requires exhaustive checks

Claims such as `all`, `strictly confined`, `100% invariant`, or `zero disagreements` require an exhaustive population check.

For claimed ranges, preserve at least N, min, p05, p10, p25, median, p75, p90, p95, max, and shares outside the claimed interval where applicable.

A single counterexample invalidates an absolute claim.

## 12. Examples do not prove population claims

Representative events or charts may illustrate a result but cannot prove a population-wide claim.

Population claims require population-level computation.
## 13. FINAL CLAIM AUDIT

Before final report, commit, or push for any research/data-analysis task, create and review a claim-audit table with at least:

- claim;
- claim type;
- supporting metric;
- artifact/column;
- population N;
- numerator/denominator where relevant;
- computed vs interpreted;
- whether ground truth is required;
- supported status;
- wording strength.

Every strong/absolute claim must pass this audit or be weakened/removed.

## 14. Code-report consistency

Final QA must verify that report text matches computed artifacts.

Regression checks should cover, where applicable:

- no hard-coded empirical metrics;
- stated counts/ranges/overlaps equal computed values;
- no accuracy language without ground truth;
- no semantic labels from unapproved thresholds;
- no preferred sensitivity parameter without a selection rule;
- no canonical promotion without explicit approval.
## 15. Default behavior under ambiguity

If data support multiple materially different interpretations, do not choose one silently.

Either:

- preserve multiple variants;
- leave the question OPEN;
- or ask the user when the choice changes methodology, semantics, population, or downstream contract.

Routine implementation choices inside an already approved contract do not require escalation.

---

## Mandatory reading order for research/data-analysis tasks

1. `AGENTS.md`
2. `docs/DATA_PIPELINE_RULES.md`
3. `docs/research/RESEARCH_CLAIM_DISCIPLINE.md`
4. task-specific canonical methodology / approved specification

Before completion:

`tests -> artifact QA -> deterministic verification -> FINAL CLAIM AUDIT -> report review -> commit/push if authorized`
