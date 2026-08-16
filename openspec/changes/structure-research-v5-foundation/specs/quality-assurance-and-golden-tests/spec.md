# Quality Assurance and Golden-Test Contract

## Purpose

Make Structure Research v5 fail loudly and reproducibly when formulas, source chronology, time boundaries, continuity, macro-anchor refinement, causality, schema, resume behavior, or extraction semantics are wrong. Process completion is not evidence of valid data.

## ADDED Requirements

### Requirement: Golden tests are a hard gate

No smoke or full-history run is approved until all applicable critical tests pass.

Emit at minimum `golden_test_report.json`, `failure_report.json`, and `qa_summary.md`.

`PASS/COMPLETE` is mechanically derived from assertions. A later step cannot overwrite a critical failure.

### Requirement: Numeric tolerance is explicit

Integers/enums/timestamps/ids/normalized decimal OHLCV compare exactly. Floating/log formulas use at most relative tolerance `1e-10` and absolute `1e-12` unless a test-specific justification is recorded.

## Golden fixtures

### G01 — Complete 1m -> 5m OHLCV
Five aligned 1m rows aggregate to exact O/H/L/C, additive volume, count 5/5, coverage 1 and complete status.

### G02 — Gap propagation
Remove one required 1m row: containing target count/coverage reflect missing row, complete OHLCV is null, status `incomplete_gap`; observed-only values if emitted are explicitly named.

### G03 — Spot/futures sequential isolation
Timestamp-adjacent spot and futures rows remain different source segments; no return/TR/ATR/RV/path/alternation/overlap/adjacent-window comparison bridges them.

### G04 — Archive/provenance change is not source boundary
Same-market exact-adjacent observed candles remain one segment despite archive/provenance changes.

### G05 — Fixed vs rolling
Rolling 4h `[16:25,20:25)` is distinct from fixed 4H `[16:00,20:00)` and identities differ.

### G06 — Cross-timeframe ordinal
5m 00:15 inside 1H 00:00 has zero-based ordinal 3; 00:55 ordinal 11.

### G07 — Rolling speed/change/acceleration
Previous 30m 100->110 gives 20 percentage-points/hour; current 110->115.5 gives 10; expected speed change -10 and acceleration -20 per hour².

### G08 — Zero-net still has path and RV
For Q `[100,200,100]`: net 0, path 200, efficiency 0, upward/downward 100/100, alternation 1, log path `2*ln2`, RV `2*ln2^2`, realized volatility `sqrt(RV)`.

### G09 — Zero-step alternation
Signs `+,0,-`: zero count 1, nonzero 2, sign changes 1, alternation 1.

### G10 — Repeated extrema
Repeated equal highs/lows preserve first, last and count; excursions follow exact formulas.

### G11 — Pair overlap/body/penetration
Synthetic previous/current candles assert exact range/body overlap, Jaccard, position, extensions and mirrored penetration formulas from the price contract.

### G12 — Two volume-direction systems
Current O105 C102 V7 with previous close100 contributes V7 to body-down and independently to close-step-up.

### G13 — TR/ATR initialization/reset
First TR without valid previous close null; 14 consecutive valid TRs initialize SMA/Wilder; gap resets state and requires new initialization.

### G14 — Direct retracement formula and tuple authorization
A100,B120,C110 => 50/50; C90 =>150/150; C130=>50/0. Production must not materialize tuple unless relationship itself is explicitly configured.

### G15 — Anchor-inclusive formula only for exact compatible synthetic fixture
Exact synthetic anchors P0=100,P1=112 and internal closes `[105,103,110]` give internal path9, anchor-inclusive path16, displacement12, efficiency .75. This tests math, not general production applicability.

### G16 — Rolling calculation matrix
Exactly 30m:5m/15m; 1h:5m/15m; 4h:5m/15m/1H; 12h and24h:5m/15m/1H/4H; 3d additionally1D.

### G17 — Stable UUID examples
Namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`; documented segment/candle/fixed/rolling/pair UUID fixtures SHALL match exactly. Run/path/provenance changes do not change ids.

### G18 — Causality/future-data invariance
Causal rows through t cannot change from future-only input changes. Macro context/anchors excluded from causal-only extraction.

### G19 — Forbidden semantic labels
Fail on newly generated impulse/correction/choppiness/range/breakout/parent/Fib/FibTime labels except explicitly source-provenance-only fields.

### G20 — Feature dictionary consistency
Every materialized metric has exactly one compatible dictionary definition; no orphan/conflicting/undeclared feature.

### G21 — Schema/referential integrity
Primary/natural keys unique; foreign keys including macro anchor/leg/retracement ids resolve; no duplicate canonical rows across parts.

### G22 — Parquet manifests
Manifest parts/schema/counts/time/partition values reconcile with physical data and reconstruct each logical table without duplicate keys.

### G23 — Extraction
Fixture proves time/market/resolution/family pruning, macro leg/anchor extraction, geometry and retracement extraction, causal exclusion, deterministic ordering, CSV equality and no hidden canonical recomputation/relationship generation.

### G24 — Resume equivalence
Clean vs interrupted+resumed output identical; changed checksum/schema/config rejects stale checkpoint.

### G25 — Higher-timeframe QA trust classification
Every native reference is `critical_validated_reference` or `diagnostic_reference`; known inconsistent legacy cache cannot act as critical truth in unvalidated region.

### G26 — Boundary-crossing fixed interval representation
Intervals containing canonical spot/futures boundary exist as `cross_market/incomplete_boundary`, source segment null, complete OHLCV/features null.

### G27 — Synthetic no-trade futures bucket excluded
`2019-09-08T19:00`: no native kline, no trades, diagnostic flat synthetic row. Strict canonical 1m excludes it; `source_gaps` contains `[19:00,19:01)` and sequential completeness breaks.

### G28 — Historical macro provenance remains mixed where audited
Late-2019 audited anchors retain old spot parent daily + futures 4H refinement evidence. Current canonical boundary never overwrites historical provenance.

### G29 — Coarse anchor blocks false exact whole-leg path
A source high/low timestamped only as 4H bucket start cannot by itself authorize complete anchor-inclusive path. Source displacement survives; whole-leg anchor-inclusive path null absent stronger boundary evidence.

### G30 — Canonical spot-gap grid alignment
Production recomputes minute-aligned gaps; post-boundary raw spot gaps excluded; totals compared to audit 5972/16 and unexplained mismatch fails review.

### G31 — Atomic candle geometry
Complete O100,H110,L90,C105 gives range20, body5, upper5, lower10, shares .25/.25/.5 and exact log geometry. Incomplete target has no valid geometry row.

### G32 — Fixed calculation matrix
15m via5m; 1H via5m/15m; 4H via5m/15m/1H; 1D via5m/15m/1H/4H. No lower-target path for fixed5m.

### G33 — Macro calculation matrix and RV exclusion
Macro safe-interior path/activity/overlap/volume may materialize at 5m/15m/1H/4H/1D when enough eligible complete candles exist. Macro RV remains non-required/null in first pass.

### G34 — Canonical field-name regression
Fail deprecated conflicts including `local_direction_normalized_speed_pct_per_hour`, `volume_delta`, `volume_ratio`, `rolling_high_low_width`, `mean_candle_range` in place of canonical names.

### G35 — Unique 1m macro-anchor refinement and boundary-minute exclusion
Source pivot is a low in coarse 4H bucket `[04:00,08:00)`, source price 90. Complete canonical 1m coverage contains that low in exactly one minute `[05:23,05:24)`.

Expected:

- `refinement_status=unique_1m_match`;
- candidate count1;
- refined possible interval `[05:23,05:24)`;
- the 05:23 candle remains boundary-ambiguous and is not assigned wholesale to either adjacent leg safe interior;
- preceding leg safe end=05:23;
- following leg safe start=05:24;
- source pivot price remains 90.

### G36 — Multiple 1m matches are never arbitrarily resolved
Same source pivot price occurs in 1m lows at 05:23,05:41,06:10 with otherwise complete search coverage.

Expected:

- `refinement_status=multiple_1m_matches`;
- candidate count3;
- first candidate05:23, last06:10;
- possible interval conservatively `[05:23,06:11)`;
- no first/last/nearest candidate is selected as exact pivot;
- adjacent safe interiors stop/start outside the full uncertainty interval.

### G37 — Incomplete 1m search coverage cannot claim uniqueness
One matching minute exists but another minute inside the coarse anchor bucket is missing from canonical 1m.

Expected:

- no `unique_1m_match` claim;
- `refinement_status=incomplete_search_coverage`;
- original coarse possible-time interval retained;
- uncertainty explicitly propagated into safe-interior boundaries.

### G38 — Canonical market scope and historical macro provenance coexist
Audited October-2019 macro leg entirely after canonical futures boundary but built from old spot daily + futures4H refinement.

Expected simultaneously:

- canonical `market_type=usdt_m_futures`;
- historical `leg_source_classification=mixed`;
- market_type non-null;
- partition value is canonical futures, never `mixed` or null.

### G39 — Macro retrospective availability cannot fake live knowledge
For every macro observation/anchor:

- `availability_class=retrospective`;
- `available_at=null`;
- source bucket timestamp remains source-coordinate field only;
- causal/as-of extraction excludes the macro entity.

### G40 — Safe macro interior excludes both uncertain boundary zones
Start possible interval `[05:23,05:24)`, end possible interval `[11:17,11:18)`.

Expected safe interior `[05:24,11:17)`.

At 5m resolution only candles wholly contained in this interval qualify. Any candle overlapping 05:23 minute or the end uncertainty is excluded from safe metrics but remains queryable. `safe_internal_*` fields describe only this guaranteed interior; generic/anchor-inclusive whole-leg path remains null unless full boundary path becomes known.

### G41 — Exact UUID fixtures for new macro-anchor and retracement identities
Using namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`:

- identity string `macro_anchor|c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3|E00210` SHALL produce `macro_anchor_id=3adfa46c-f5f9-5580-b083-ed22f2d5a696`;
- identity string `retracement|ANCHOR_A|ANCHOR_B|ANCHOR_C|REL_001` SHALL produce `retracement_id=ccdc33cf-94bf-5362-ae36-b060e81f6648`.

Changing run id, local path, or mutable provenance SHALL NOT change either id. Changing one identity component SHALL change the UUID deterministically.

## Production invariants

### Requirement: Approved source gaps are visible, never hidden
Every unresolved canonical gap appears in `source_gaps`; synthetic OHLC never silently fills it; complete sequential features never bridge it.

### Requirement: Source boundary is read from one finalized contract
Tests/features consume configured canonical boundary, not duplicated conflicting constants.

### Requirement: Macro ambiguity is preserved, never guessed away
Coarse/multiple/incomplete anchor timing SHALL remain explicit. The builder SHALL NOT choose a convenient candidate merely to complete a leg.

### Requirement: QA status is mechanically derived
G01-G41 and schema/source/referential invariants are critical unless explicitly documented not-applicable by contract.

`qa_status=PASS` only when all applicable critical tests pass and `failure_report.json` has zero unresolved critical failures. Otherwise `FAIL`.
