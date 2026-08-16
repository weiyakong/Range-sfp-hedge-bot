# Quality Assurance and Golden-Test Contract

## Purpose

Make Structure Research v5 fail loudly when source chronology, timestamp canonicalization, price identity, formulas, approved aggTrade macro refinement, exact/fallback boundaries, causality, schema, resume, or extraction semantics are wrong.

## Hard gate

No bounded smoke or full-history production is approved until all applicable critical tests pass.

Emit at minimum:
- `golden_test_report.json`
- `failure_report.json`
- `qa_summary.md`.

`PASS` is mechanically derived. Later stages cannot overwrite a critical failure.

Exact integers/enums/timestamps/ids/normalized Decimal OHLCV compare exactly. Floating/log formulas use relative tolerance <=`1e-10` and absolute <=`1e-12` unless a test records another justified tolerance.

## Golden fixtures

### G01 — Complete 1m -> 5m OHLCV
Five aligned complete 1m rows produce exact O/H/L/C/additive volume, count5, coverage1.

### G02 — Gap propagation
One missing required minute makes containing target incomplete; complete OHLCV null; observed-only diagnostics explicitly named.

### G03 — Spot/futures sequential isolation
No return/TR/ATR/RV/path/alternation/overlap/adjacent comparison crosses canonical market transition.

### G04 — Archive change is not source break
Timestamp-continuous same-market rows remain one segment despite archive/provenance change.

### G05 — Fixed vs rolling
Rolling 4h `[16:25,20:25)` differs from fixed 4H `[16:00,20:00)` and identities differ.

### G06 — Cross-TF ordinal
5m 00:15 within 1H 00:00 has ordinal3; 00:55 ordinal11.

### G07 — Rolling speed/change/acceleration
Preserve the documented synthetic numeric fixture and exact expected values.

### G08 — Zero-net still has path and RV
Q `[100,200,100]`: net0, path200, efficiency0, upward/downward100/100, alternation1, log path/RV exact.

### G09 — Zero-step alternation
Signs `+,0,-`: zero count1, nonzero2, sign changes1, alternation1.

### G10 — Repeated extrema
First/last/count and excursions follow exact tie formulas.

### G11 — Pair overlap/body/penetration
Synthetic pair asserts exact approved neutral formulas.

### G12 — Two volume-direction systems
Body and close-step direction are independently correct.

### G13 — TR/ATR reset/init
Segment start/gap resets state; 14 new consecutive TRs required.

### G14 — Direct retracement formula
A100,B120,C110 => candidate/reference50%, retracement50%; C90=>150/150; C130=>50/0.

### G15 — Exact macro close-path fixture
Resolved start P0=100, eligible closes `[105,103,110]`, resolved end P1=112:
Q=`[100,105,103,110,112]`; path16; displacement12; efficiency.75.

### G16 — Rolling calculation matrix
Exactly the approved matrix.

### G17 — Stable UUID examples
Namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`; segment/candle/fixed/rolling/pair documented fixtures match exactly.

### G18 — Causality/future-data invariance
Causal rows through t do not change from future-only input; all macro retrospective entities excluded from causal extraction.

### G19 — Forbidden semantic labels
Fail newly generated impulse/correction/choppiness/range/breakout/parent/Fib/FibTime/Elliott labels except source-provenance-only fields.

### G20 — Feature dictionary
Every materialized metric has exactly one compatible definition.

### G21 — Referential integrity
Keys unique; macro anchor/aggTrade-touch/fragment/leg/retracement foreign keys resolve; no duplicate canonical rows.

### G22 — Parquet manifests
Parts/schema/counts/time/partitions reconcile and reconstruct logical tables uniquely.

### G23 — Extraction
Filters/pruning/deterministic order/CSV equality/causal exclusion work; no hidden feature or retracement generation.

### G24 — Resume equivalence
Clean vs interrupted+resumed outputs identical; checksum/schema/config/refinement changes reject stale checkpoints.

### G25 — Higher-TF reference trust
Legacy inconsistent caches cannot act as critical truth where not validated.

### G26 — Boundary-crossing fixed interval
Cross-market fixed row exists with incomplete status and null complete metrics.

### G27 — Futures 19:00
Synthetic no-trade repair excluded; canonical source gap preserved and sequential completeness breaks.

### G28 — Historical macro provenance vs canonical market
Late-2019 can simultaneously be historical `mixed` and canonical futures.

### G29 — Localization is not exact event timing
A unique localization window alone SHALL NOT populate `exact_pivot_time` or exact macro duration/speed.

### G30 — Canonical spot gap audit
Production recomputes valid canonical gaps and reports against audited evidence; unexplained differences fail.

### G31 — Atomic candle geometry
Synthetic candle asserts exact range/body/wicks/shares/log geometry.

### G32 — Fixed calculation matrix
Exactly approved fixed matrix.

### G33 — Macro calculation matrix / RV
Macro path/activity/overlap/volume attempted at 5m/15m/1H/4H/1D under exact/fallback rules; macro RV remains null.

### G34 — Canonical field-name regression
Fail deprecated/conflicting names.

### G35 — Reviewed localization artifact
Checksum `77a6fa1339794a96ddff327e038d66b17347914dcfa8fbb0d9a90765fd3900bc`; 138 unique event ids; 131 unique-window; 7 multiple-window; 0 unresolved/incomplete; 145 distinct candidate windows total.

Exactly 142 candidate windows are canonical 5m-grid aligned. Exactly three are known `off_grid_source_5m` windows inherited from the December-2017 `+20.799s` source offset:
- E00059 `2017-12-07T23:55:20.799Z`
- E00065 `2017-12-10T04:30:20.799Z`
- E00070 `2017-12-17T12:10:20.799Z`.

These three SHALL NOT be assigned canonical candle ids from their off-grid start times.

### G36 — Multiple localization windows preserved
A two-candidate anchor passes both windows to approved aggTrade refinement; no automatic window selection.

### G37 — Decimal price identity
`4039.79000000` and `4039.79` parse to exact `price_units=403979`; `13918.04` -> `1391804`. Binary float/epsilon/nearest matching is prohibited. Any relevant approved aggTrade price with >2 significant decimals triggers precision failure rather than rounding.

### G38 — Anchor-level provenance not copied from leg duration precision
Fixture where shared anchor belongs to a `1D_fallback` leg and adjacent `4H` leg must retain anchor-level provenance from reviewed localization artifact, not blindly inherit either leg's duration precision.

### G39 — Approved aggTrade unique touch
One exact same-market anchor-price matching aggTrade row with complete approved source coverage yields `exact_unique_trade_touch`, event time, `agg_trade_id`, first/last underlying ids and canonical 5m containment.

For E00059/E00065/E00070 the canonical 5m start must be derived from the resolved aggTrade event time, never copied from the off-grid localization-window start.

The result is exact at approved `agg_trade` source granularity; it SHALL NOT claim reconstructed individual raw-trade timing.

### G40 — Approved aggTrade multiple touches
Two or more exact matching aggTrade rows preserve every row; exact pivot time/sequence remains null; no first/last/nearest selection.

### G41 — Exact UUID fixtures
Using namespace above:
- `macro_anchor|c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3|E00210`
  -> `3adfa46c-f5f9-5580-b083-ed22f2d5a696`
- `retracement|ANCHOR_A|ANCHOR_B|ANCHOR_C|REL_001`
  -> `ccdc33cf-94bf-5362-ae36-b060e81f6648`.

### G42 — Pivot aggregate counted once
Synthetic ordered aggTrade records around pivot prove pivot aggTrade row belongs LEFT once, RIGHT starts from pivot price state but excludes pivot row. LEFT+RIGHT aggregate source-row sets reproduce the unsplit canonical 5m aggTrade record set without overlap or loss.

If pivot aggTrade has multiple underlying trades, its aggregate quantity/count remains indivisible and `aggregate_boundary_precision` reflects that fact.

### G43 — Timestamp tie uses agg_trade_id
Two aggTrade rows share identical event timestamp but different `agg_trade_id`; split/order is deterministic by `(event_time,agg_trade_id)`, not timestamp alone.

### G44 — Aggregate path and TF close path remain separate
Synthetic boundary fragment with oscillatory aggTrade price path plus canonical 5m closes proves aggregate-level `trade_price_path` is not added into `5m_close_path`.

### G45 — Exact macro TF Q sequence
Start pivot inside a candle and end pivot inside another:
Q begins at resolved start price, includes only qualifying complete R closes with `start < candle.end <= end`, then resolved end price. Pre-start candle movement and post-end candle close are excluded.

### G46 — Higher-TF boundary composition
A 1H boundary fragment is composed from aggTrade-resolved partial canonical 5m plus complete canonical 5m candles to hour edge; no different trade-source download is required; gap breaks exact composition.

### G47 — Fallback path includes first candle open and grid count
Off-grid fallback interval fixture:
- expected count equals number of wholly contained fixed-grid slots, not duration/R;
- Q starts with open of first eligible candle;
- measured start/end equal actual first/last eligible constituent bounds.

### G48 — Off-grid source is not a fake gap
A full 1440-row source day at exact 60-second cadence with stable `+20.799s` open-time offset is classified `continuous_off_grid_source` (or canonical equivalent), not `missing_1m=1440`. Raw timestamps remain provenance; canonical mapping requires approved proof.

### G49 — Production macro retracement set
Approved 128-leg source yields:
- 127 adjacent transitions;
- 118 shared-pivot opposite-direction relationships;
- 59 up->down and 59 down->up;
- 9 discontinuous transitions excluded.
A/B/C resolve to macro anchors and exactly 118 production retracement relationships materialize.

### G50 — Raw individual trades remain outside approved calculation path
Fixture/run environment contains both approved official `aggTrades` and previously downloaded raw individual trade files for the same candidate interval.

The refinement output, pivot selection, boundary fragments, feature values, checksums used as QA truth and run lineage SHALL derive only from approved `aggTrades`.

Presence of raw trade files SHALL NOT:
- change a pivot status;
- replace an `agg_trade_id` boundary with a raw `trade_id` boundary;
- alter LEFT/RIGHT features;
- improve precision silently;
- satisfy missing aggTrade coverage.

Any attempted raw-trade read/use in the approved stage without a separate explicit user-approved source-contract change is a critical QA failure.

## Production invariants

- every unresolved canonical gap is visible;
- no synthetic row silently repairs canonical completeness;
- canonical source boundary comes from one contract/config truth;
- historical macro provenance never overwrites canonical market;
- localization never masquerades as exact aggTrade timing;
- off-grid source-localization windows never become canonical candle identities;
- ambiguous aggTrade touches are never guessed away;
- approved refinement source is existing official Binance `aggTrades`;
- raw individual trades are excluded unless later explicitly user-approved;
- macro path never mixes aggregate-level boundary path and candle-close path;
- full boundary candle and its fragment never both contribute to one macro metric;
- macro rows remain retrospective even with resolved historical timestamps;
- QA `PASS` requires all applicable G01-G50 plus schema/source/referential invariants and zero unresolved critical failures.
