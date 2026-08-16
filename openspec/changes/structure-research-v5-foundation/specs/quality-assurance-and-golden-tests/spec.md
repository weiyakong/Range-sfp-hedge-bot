# Quality Assurance and Golden-Test Contract

## Purpose
Make Structure Research v5 fail loudly when source chronology, timestamp canonicalization, price identity, formulas, approved aggTrade refinement, exact/fallback boundaries, bounded source access, causality, schema, resume, or extraction semantics are wrong.

## Hard gate
No bounded smoke or full-history production is approved until all applicable critical tests pass. Emit `golden_test_report.json`, `failure_report.json`, `qa_summary.md`. PASS is mechanically derived. Exact integers/enums/timestamps/ids/normalized Decimal OHLCV compare exactly. Floating/log formulas use relative tolerance <=`1e-10` and absolute <=`1e-12` unless justified.

## Golden fixtures

### G01 — Complete 1m -> 5m OHLCV
Five complete same-segment 1m candles: `00:00 O100 H102 L99 C101 V1`; `00:01 O101 H104 L100 C103 V2`; `00:02 O103 H105 L102 C104 V3`; `00:03 O104 H106 L101 C102 V4`; `00:04 O102 H103 L98 C99 V5`. Expected 5m O100 H106 L98 C99 V15, expected/observed5, coverage1, complete.

### G02 — Gap propagation
Remove 00:02. Expected5 observed4 coverage0.8 `incomplete_gap`; complete OHLCV null; observed-only O100 H106 L98 C99 V12. Higher TFs requiring it remain incomplete.

### G03 — Spot/futures sequential isolation
No return/TR/ATR/RV/path/alternation/overlap/adjacent comparison crosses canonical market transition.

### G04 — Archive change is not source break
Timestamp-continuous same-market rows remain one segment despite archive/provenance change.

### G05 — Fixed vs rolling
Rolling 4h `[16:25,20:25)` differs from fixed 4H `[16:00,20:00)` and identities differ.

### G06 — Cross-TF ordinal
5m 00:15 within 1H 00:00 ordinal3; 00:55 ordinal11.

### G07 — Rolling speed/change/acceleration
12 complete 5m candles. First30m starts100 ends110; second starts110 ends115.5. At 01:00 current return5%, speed10 pp/h; previous return10%, speed20; change -10; acceleration -20 pp/h². Future production cannot mutate finalized earlier rows.

### G08 — Zero-net still has path and RV
Q `[100,200,100]`: net0, path200, efficiency0, upward/downward100/100, alternation1, log path `2*ln2`, RV `2*ln(2)^2`, realized volatility `sqrt(2)*ln2`.

### G09 — Zero-step alternation
Signs `+,0,-`: zero1, nonzero2, sign changes1, alternation1.

### G10 — Repeated extrema
P0=100; highs `[110,110,105,110]`, lows `[95,96,95,97]`: high110 first t0 last t3 count3; low95 first t0 last t2 count2; upward excursion10/10%; downward5/5%.

### G11 — Pair overlap/body/penetration
Previous O100 H110 L90 C108; current O107 H112 L94 C96. Expected range overlap [94,110], abs16, shares prev0.8/curr8/9, Jaccard8/11; prev positions .2/1/.6; curr 0/8/9/4/9. Body overlap [100,107], abs7, shares7/8 and7/11, Jaccard7/12. Extensions upper2/lower0, shares .1/0. Penetration top extreme16(.8), body14(.7), close14(.7), wick-only2(.1); bottom extreme20(1), body17(.85), close6(.3), wick-only3(.15). Up selects from-top; down from-bottom; flat relative null.

### G12 — Two volume-direction systems
Previous close100; current O105 C102 V7 => body down, close-step up; V7 contributes independently to both systems.

### G13 — TR/ATR reset/init
First candle no prior valid close => TR null. Then 14 consecutive TR=2 => both ATR14=2. Next TR=4 => SMA and Wilder both `15/7` in fixture. After gap/source reset first following TR null; both ATRs require 14 new consecutive valid TRs. Fallback cannot import previous close from outside guaranteed interval.

### G14 — Direct retracement
A100,B120,C110 => candidate/reference50%, retracement50%; C90=>150/150; C130=>50/0.

### G15 — Refined macro close path
P0=100, eligible closes `[105,103,110]`, P1=112 => Q `[100,105,103,110,112]`, path16, displacement12, efficiency.75.

### G16 — Rolling calculation matrix
Exactly: 30m=5m/15m; 1h=5m/15m; 4h=5m/15m/1H; 12h=5m/15m/1H/4H; 24h=5m/15m/1H/4H; 3d=5m/15m/1H/4H/1D.

### G17 — Stable UUID examples
Namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`: segment example -> `adeeb6f8-cff1-5738-a02b-a75bd176b546`; candle -> `cdf2383a-744c-5140-a130-cac2de6044be`; fixed observation -> `251296be-22d3-5ba5-9745-bead7257333f`; rolling30m -> `c5aab5b5-f528-5c9f-a7b4-81345bfb3270`; next candle -> `e5f9c683-3ad6-5235-be04-a7fe331ee0d1`; pair -> `e3ce7198-17dd-5e2e-b03a-09636992e345`. Run/path/archive changes do not alter ids.

### G18 — Causality/future-data invariance
Causal rows through t unchanged by future-only input; all macro retrospective entities excluded.

### G19 — Forbidden semantic labels
Fail newly generated impulse/correction/choppiness/range/breakout/parent/Fib/FibTime/Elliott labels except source-provenance-only fields.

### G20 — Feature dictionary
Every materialized metric has exactly one compatible definition.

### G21 — Referential integrity
Keys unique; macro anchor/evidence/fragment/leg/retracement FKs resolve; no duplicate canonical rows. Fragment id deterministic from `macro_anchor_id|side|calculation_resolution`.

### G22 — Parquet manifests
Parts/schema/counts/time/partitions reconcile and reconstruct logical tables uniquely.

### G23 — Extraction
Filters/pruning/deterministic order/CSV equality/causal exclusion work; no hidden feature/retracement generation.

### G24 — Resume equivalence
Clean vs interrupted+resumed outputs identical; checksum/schema/config/refinement changes reject stale checkpoints; validated progress persisted no later than every 20 minutes.

### G25 — Higher-TF reference trust
Legacy inconsistent caches cannot act as critical truth where not validated.

### G26 — Boundary-crossing fixed interval
Cross-market fixed row exists incomplete with null complete metrics.

### G27 — Futures 19:00
Synthetic repair excluded; canonical gap preserved and sequential completeness breaks.

### G28 — Historical provenance vs canonical market
Late-2019 may simultaneously be historical `mixed` and canonical futures.

### G29 — Localization is not event timing
Unique localization alone cannot populate resolved pivot time or exact macro duration/speed.

### G30 — Canonical spot gap audit
Production recomputes canonical gaps and compares audited evidence; unexplained differences fail.

### G31 — Atomic candle geometry
Synthetic candle asserts exact range/body/wicks/shares/log geometry.

### G32 — Fixed calculation matrix
Exactly approved fixed matrix.

### G33 — Macro matrix / RV
Macro path/activity/overlap/volume attempted at 5m/15m/1H/4H/1D under refined/fallback rules; macro RV null.

### G34 — Canonical names
Fail deprecated/conflicting names including vague maker-side name where `buyer_is_maker` required.

### G35 — Reviewed localization artifact
Checksum `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`; 138 ids; 131 unique-window; 7 multiple-window; 145 candidates; exactly three off-grid E00059/E00065/E00070. Half-open scans.

### G36 — Multiple localization windows
Two-candidate anchor scans both; no automatic window selection before evidence evaluation.

### G37 — Decimal price identity
`4039.79000000`/`4039.79` ->403979; `13918.04`->1391804. At most two fractional decimal places after normalization. Binary float/epsilon/nearest matching forbidden; greater precision fails.

### G38 — Anchor provenance
Comes from reviewed localization artifact, not adjacent-leg duration precision.

### G39 — Earliest exact touch wins
Three exact rows `(t1,id10),(t2,id20),(t2,id21)`: preserve all; resolve `(t1,id10)`, method `earliest_exact_touch`.

### G40 — No exact touch uses directional extremum
High prices `[99,101,103,102]` ->103; low `[101,99,97,98]` ->97. Nearest-price forbidden. Source anchor preserved.

### G41 — Repeated directional extremum is intentionally unresolved
No exact touch; selected maximum103 occurs at two distinct keys. Preserve price103 and all occurrences; authoritative time/id null. No implicit first/last/time-gap/retest/range rule is allowed until the deferred tie-break decision is explicitly approved and OpenSpec updated.

### G42 — Exact UUID macro fixtures
`macro_anchor|...|E00210` -> `3adfa46c-f5f9-5580-b083-ed22f2d5a696`; retracement fixture -> `ccdc33cf-94bf-5362-ae36-b060e81f6648`.

### G43 — Pivot aggregate counted once
Pivot row belongs LEFT once; RIGHT starts from pivot price state and excludes pivot row. Multi-underlying aggregate indivisible.

### G44 — Timestamp tie
Same timestamp orders by `agg_trade_id`.

### G45 — Aggregate path separate
AggTrade fragment path is not added to 5m close path.

### G46 — Macro TF Q sequence
Start/end inside candles: Q begins refined start, qualifying closes only, then refined end; pre/post movement excluded.

### G47 — Higher-TF composition
1H fragment uses resolved partial canonical5m plus complete canonical5m; gap breaks exact composition.

### G48 — Fallback count/no interior
Expected count = wholly contained fixed-grid slots; Q starts first eligible open. No slot => expected=observed=0 and boundary-dependent metrics null `no_unambiguous_interior`.

### G49 — Off-grid source is not fake gap
1440 rows at 60-second cadence +20.799s are continuous off-grid source, not missing_1m=1440.

### G50 — Production retracement set
128 legs ->127 adjacent transitions ->118 shared-pivot opposite-direction (59 each direction), 9 discontinuous excluded.

### G51 — Raw trades excluded
Presence of raw individual-trade files cannot affect approved outputs/QA/lineage. Any unapproved read/use is critical failure.

## Bounded-source critical tests

### B01 — One bucket does not materialize whole archive
One 5m request returns exact bucket rows without whole day/month materialization in memory.

### B02 — Same bucket reused
Repeated identical request does not trigger another physical archive scan.

### B03 — No pandas whole-file hot path
Fail if per-anchor/per-fragment access invokes `pandas.read_csv` or equivalent whole-file DataFrame materialization.

### B04 — Parser failure distinct
Parser failure -> `source_reader_failure`; never empty valid bucket, incomplete coverage, or raw fallback.

### B05 — Exact half-open bucket
Returned rows exactly satisfy `B0 <= event_time < B1`, ordered `(event_time,agg_trade_id)`.

### B06 — Different buckets in same archive are amortized
Multiple requested buckets/windows from one physical archive are served by one shared sequential scan, validated indexed/range access, or validated restart-safe cache. One whole-archive sequential scan per different bucket is a critical failure.

### B07 — Shared pass memory remains bounded
Many requested buckets from a large archive do not cause retention/materialization approaching total archive row count. Completed results are emitted/persisted or held in bounded validated cache.

## Production invariants
Every canonical gap visible; no synthetic completeness repair; one canonical source-boundary truth; historical provenance separate; localization not event timing; earliest exact touch rule; directional extremum rule; repeated equal selected extrema remain unresolved until explicit decision; aggTrades-only refinement; raw trades excluded; bounded archive access B01-B07; fragment path separate from TF close path; no full boundary candle + fragment duplication; both ATR14 forms; macro retrospective; QA PASS requires all applicable synchronized tests and zero unresolved critical failures other than explicitly documented deferred design decisions that block only the affected exact outputs rather than being silently resolved.
