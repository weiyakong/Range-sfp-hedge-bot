# Quality Assurance and Golden-Test Contract

## Purpose

Make Structure Research v5 fail loudly when source chronology, timestamp canonicalization, price identity, formulas, approved aggTrade macro refinement, exact/fallback boundaries, causality, schema, resume, or extraction semantics are wrong.

## Hard gate

No bounded smoke or full-history production is approved until all applicable critical tests pass. Emit `golden_test_report.json`, `failure_report.json`, `qa_summary.md`. PASS is mechanically derived.

Exact integers/enums/timestamps/ids/normalized Decimal OHLCV compare exactly. Floating/log formulas use relative tolerance <=`1e-10` and absolute <=`1e-12` unless justified.

## Golden fixtures

### G01 — Complete 1m -> 5m OHLCV
Use five complete consecutive same-segment 1m candles:
`00:00 O100 H102 L99 C101 V1`; `00:01 O101 H104 L100 C103 V2`; `00:02 O103 H105 L102 C104 V3`; `00:03 O104 H106 L101 C102 V4`; `00:04 O102 H103 L98 C99 V5`.
Expected 5m: O100 H106 L98 C99 V15, expected/observed count 5, coverage1, complete.

### G02 — Gap propagation
Remove 00:02 from G01. Expected count5, observed4, coverage0.8, `incomplete_gap`, complete OHLCV null; observed-only O100 H106 L98 C99 V12. Containing higher TFs requiring that minute remain incomplete.

### G03 — Spot/futures sequential isolation
No return/TR/ATR/RV/path/alternation/overlap/adjacent comparison crosses canonical market transition.

### G04 — Archive change is not source break
Timestamp-continuous same-market rows remain one segment despite archive/provenance change.

### G05 — Fixed vs rolling
Rolling 4h `[16:25,20:25)` differs from fixed 4H `[16:00,20:00)` and identities differ.

### G06 — Cross-TF ordinal
5m 00:15 within 1H 00:00 has ordinal3; 00:55 ordinal11.

### G07 — Rolling speed/change/acceleration
Use 12 consecutive complete 5m candles covering `[00:00,01:00)`. First 30m `[00:00,00:30)` starts100 ends110; second `[00:30,01:00)` starts110 ends115.5. At 01:00 current return=5%, speed=10 percentage-points/hour; previous return=10%, speed=20; `speed_change_30m=-10`; `acceleration_30m=-20` percentage-points/hour². Producing 01:00 must not mutate finalized earlier rows.

### G08 — Zero-net still has path and RV
Q `[100,200,100]`: net0, path200, efficiency0, upward/downward100/100, alternation1, log path `2*ln2`, RV `2*ln(2)^2`, realized volatility `sqrt(2)*ln2`.

### G09 — Zero-step alternation
Signs `+,0,-`: zero count1, nonzero2, sign changes1, alternation1.

### G10 — Repeated extrema
Start P0=100; highs `[110,110,105,110]`, lows `[95,96,95,97]` at t0..t3. Expected high110 first t0 last t3 count3; low95 first t0 last t2 count2; upward excursion10/10%; downward5/5%.

### G11 — Pair overlap/body/penetration
Previous O100 H110 L90 C108, body[100,108], range20. Current O107 H112 L94 C96, body[96,107], range18.
Expected range overlap [94,110], abs16, shares prev0.8/curr8/9, Jaccard8/11; prev positions .2/1/.6; curr 0/8/9/4/9. Body overlap [100,107], abs7, shares7/8 and7/11, Jaccard7/12. Extensions upper2/lower0, shares .1/0. Penetration from top extreme16(.8), body14(.7), close14(.7), wick-only2(.1); from bottom extreme20(1), body17(.85), close6(.3), wick-only3(.15). Up observation selects from-top against-move; down selects from-bottom; flat relative fields null.

### G12 — Two volume-direction systems
Previous close100; current O105 C102 V7 => body down, close-step up; volume7 contributes independently to body-down and close-step-up.

### G13 — TR/ATR reset/init and both ATR forms
First candle has no valid prior close => TR null. Then 14 consecutive valid TR=2 => `atr14_sma=2`, `atr14_wilder=2`. Next adjacent TR=4 => both equal `15/7` in this fixture; Wilder update is `((13*2)+4)/14`. After gap/source reset first following TR is null and both ATRs remain null until 14 new consecutive valid TR values. A fallback fixture must prove the first eligible fallback candle cannot use previous_close from outside the guaranteed interval.

### G14 — Direct retracement formula
A100,B120,C110 => candidate/reference50%, retracement50%; C90=>150/150; C130=>50/0.

### G15 — Exact macro close-path fixture
Resolved P0=100, eligible closes `[105,103,110]`, P1=112 => Q `[100,105,103,110,112]`, path16, displacement12, efficiency.75.

### G16 — Rolling calculation matrix
Exactly: 30m=5m/15m; 1h=5m/15m; 4h=5m/15m/1H; 12h=5m/15m/1H/4H; 24h=5m/15m/1H/4H; 3d=5m/15m/1H/4H/1D.

### G17 — Stable UUID examples
Namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`:
- `segment|binance|BTCUSDT|spot|2018-01-01T00:00:00Z` -> `adeeb6f8-cff1-5738-a02b-a75bd176b546`
- `candle|binance|BTCUSDT|spot|5m|2018-01-01T00:00:00Z` -> `cdf2383a-744c-5140-a130-cac2de6044be`
- fixed observation for that candle -> `251296be-22d3-5ba5-9745-bead7257333f`
- rolling30m ending 00:30 -> `c5aab5b5-f528-5c9f-a7b4-81345bfb3270`
- next 5m candle at 00:05 -> `e5f9c683-3ad6-5235-be04-a7fe331ee0d1`
- pair of the two 5m candles -> `e3ce7198-17dd-5e2e-b03a-09636992e345`.
Run id/local path/archive filename changes do not change entity ids.

### G18 — Causality/future-data invariance
Causal rows through t do not change from future-only input; all macro retrospective entities excluded from causal extraction.

### G19 — Forbidden semantic labels
Fail newly generated impulse/correction/choppiness/range/breakout/parent/Fib/FibTime/Elliott labels except source-provenance-only fields.

### G20 — Feature dictionary
Every materialized metric has exactly one compatible definition.

### G21 — Referential integrity
Keys unique; macro anchor/aggTrade-touch/fragment/leg/retracement foreign keys resolve; no duplicate canonical rows. Boundary fragment id is deterministic from `macro_anchor_id|side|calculation_resolution`.

### G22 — Parquet manifests
Parts/schema/counts/time/partitions reconcile and reconstruct logical tables uniquely.

### G23 — Extraction
Filters/pruning/deterministic order/CSV equality/causal exclusion work; no hidden feature/retracement generation.

### G24 — Resume equivalence
Clean vs interrupted+resumed outputs identical; checksum/schema/config/refinement changes reject stale checkpoints; validated outputs/checkpoints are persisted at least every 20 minutes of collection/processing work.

### G25 — Higher-TF reference trust
Legacy inconsistent caches cannot act as critical truth where not validated.

### G26 — Boundary-crossing fixed interval
Cross-market fixed row exists with incomplete status and null complete metrics.

### G27 — Futures 19:00
Synthetic no-trade repair excluded; canonical source gap preserved and sequential completeness breaks.

### G28 — Historical macro provenance vs canonical market
Late-2019 can simultaneously be historical `mixed` and canonical futures.

### G29 — Localization is not exact event timing
A unique localization window alone cannot populate resolved pivot time or exact macro duration/speed.

### G30 — Canonical spot gap audit
Production recomputes valid canonical gaps and reports against audited evidence; unexplained differences fail.

### G31 — Atomic candle geometry
Synthetic candle asserts exact range/body/wicks/shares/log geometry.

### G32 — Fixed calculation matrix
Exactly approved fixed matrix.

### G33 — Macro calculation matrix / RV
Macro path/activity/overlap/volume attempted at 5m/15m/1H/4H/1D under exact/fallback rules; macro RV remains null.

### G34 — Canonical field-name regression
Fail deprecated/conflicting names including vague aggTrade maker-side names where `buyer_is_maker` is required.

### G35 — Reviewed localization artifact
Checksum `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`; 138 unique event ids; 131 unique-window; 7 multiple-window; 0 unresolved/incomplete; 145 candidate windows. Exactly 142 starts canonical-grid aligned and three off-grid E00059/E00065/E00070. Every candidate scan uses half-open `[start,start+5m)`.

### G36 — Multiple localization windows preserved
A two-candidate anchor scans both windows; no automatic window selection before aggregate evidence is evaluated.

### G37 — Decimal price identity
`4039.79000000` and `4039.79` -> `price_units=403979`; `13918.04` -> `1391804`. Relevant prices must be exactly representable with at most two fractional decimal places after decimal normalization. Binary float/epsilon/nearest matching prohibited; greater required precision fails rather than rounds.

### G38 — Anchor-level provenance
Shared anchor provenance comes from reviewed localization artifact, not adjacent leg duration precision.

### G39 — Earliest exact aggTrade touch wins
Fixture has complete approved coverage and three exact source-anchor-price aggTrade rows ordered `(t1,id10),(t2,id20),(t2,id21)`. All three are preserved; resolved pivot is `(t1,id10)`, method `earliest_exact_touch`, source and resolved prices equal, canonical 5m containment derives from t1. Multiple exact touches are not ambiguous.

### G40 — No exact touch uses furthest directional extremum
With complete approved coverage and no exact source-price touch: high-pivot prices `[99,101,103,102]` resolve price103 and its unique time/id; low-pivot prices `[101,99,97,98]` resolve price97. Nearest-price selection is forbidden. Source anchor price remains separately preserved.

### G41 — Repeated directional extremum leaves time unresolved
No exact touch; high pivot reaches selected maximum103 at two distinct aggTrade keys. Preserve resolved realized price103 and both rows/count/first-last occurrence, but authoritative resolved time/id remain null until a separately approved tie-break rule exists. Exact boundary fragments and endpoint-dependent exact metrics remain null.

### G42 — Exact UUID fixtures
Using namespace above:
- `macro_anchor|c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3|E00210` -> `3adfa46c-f5f9-5580-b083-ed22f2d5a696`
- `retracement|ANCHOR_A|ANCHOR_B|ANCHOR_C|REL_001` -> `ccdc33cf-94bf-5362-ae36-b060e81f6648`.

### G43 — Pivot aggregate counted once
Synthetic ordered aggTrade records prove pivot row belongs LEFT once; RIGHT starts from pivot price state but excludes pivot row. Multi-underlying aggregate remains indivisible.

### G44 — Timestamp tie uses agg_trade_id
Two rows share event timestamp; deterministic ordering uses `(event_time,agg_trade_id)`.

### G45 — Aggregate path and TF close path remain separate
Oscillatory aggTrade fragment path is not added into 5m close path.

### G46 — Exact macro TF Q sequence
Start/end pivots inside candles: Q begins at resolved start price, includes only complete R closes with `start < candle.end <= end`, then resolved end price; pre-start/post-end movement excluded.

### G47 — Higher-TF boundary composition
1H fragment composes trade-resolved partial canonical5m plus complete canonical5m to hour edge; gap breaks exact composition.

### G48 — Fallback grid count/no interior
Expected count equals wholly contained fixed-grid slots, not duration/R; Q starts with first eligible open; measured bounds are actual constituent bounds. If possible start/end uncertainty leaves no wholly contained slot, expected=observed=0 and boundary-dependent fallback metrics null with `no_unambiguous_interior`.

### G49 — Off-grid source is not fake gap
1440 source rows at exact 60-second cadence with stable +20.799s offset are continuous off-grid source, not missing_1m=1440.

### G50 — Production macro retracement set
Approved 128-leg source yields 127 adjacent transitions, 118 shared-pivot opposite-direction relationships, 59 up->down, 59 down->up, 9 discontinuous excluded.

### G51 — Raw individual trades remain outside approved calculation path
Presence of raw individual trade files cannot change refinement, pivot selection, fragments, feature values, QA truth or lineage derived from approved aggTrades. Any unapproved raw-trade read/use is critical failure.

## Production invariants

- every unresolved canonical gap is visible;
- no synthetic row silently repairs canonical completeness;
- canonical source boundary comes from one contract/config truth;
- historical macro provenance never overwrites canonical market;
- localization never masquerades as exact aggTrade timing;
- exact source-price touches select the earliest exact aggTrade touch while preserving all touches;
- no-exact cases use directional furthest extremum, not nearest price;
- repeated selected extrema do not receive an invented time tie-break;
- approved refinement source is existing official Binance aggTrades;
- raw individual trades are excluded unless explicitly approved;
- macro path never mixes aggregate-level boundary path and candle-close path;
- full boundary candle and its fragment never both contribute to one macro metric;
- both ATR14 SMA and Wilder are materialized under strict reset rules;
- macro rows remain retrospective;
- QA PASS requires all applicable synchronized golden tests plus schema/source/referential invariants and zero unresolved critical failures.
