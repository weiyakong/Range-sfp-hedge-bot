# Quality Assurance and Golden-Test Contract

## Purpose

Make Structure Research v5 fail loudly and reproducibly when formulas, source chronology, time boundaries, continuity, causality, schema, resume behavior, or extraction semantics are wrong. Process completion is not evidence of valid data.

## ADDED Requirements

### Requirement: Golden tests are a hard gate

No smoke or full-history run is approved until all applicable critical tests pass.

Emit at minimum:

- `golden_test_report.json`
- `failure_report.json`
- `qa_summary.md`.

`PASS/COMPLETE` SHALL be mechanically derived from assertions. A later step may not overwrite a critical failure with a success-like status.

### Requirement: Numeric tolerance is explicit

Exact integers/enums/timestamps/ids/normalized decimal OHLCV compare exactly. Floating/log formulas use at most relative tolerance `1e-10` and absolute `1e-12` unless a test-specific justification is recorded.

## Golden fixtures

### G01 — Complete 1m -> 5m OHLCV

Five 1m rows:

| minute | open | high | low | close | volume |
|---|---:|---:|---:|---:|---:|
|00:00|100|102|99|101|1|
|00:01|101|104|100|103|2|
|00:02|103|105|102|104|3|
|00:03|104|106|101|102|4|
|00:04|102|103|98|99|5|

Expected 5m: O=100,H=106,L=98,C=99,V=15,count=5/5,coverage=1,complete.

### G02 — Gap propagation

Remove 00:02 from G01.

Expected 5m: count 4/5, coverage .8, `incomplete_gap`, complete OHLCV null. If observed-only emitted: O=100,H=106,L=98,C=99,V=12. Containing larger intervals requiring the missing minute are incomplete.

### G03 — Spot/futures sequential isolation

Timestamp-adjacent spot and futures candles still form different source segments. Cross-boundary pair ineligible; no return/TR/ATR/RV/path/alternation/overlap/adjacent-window comparison bridges them.

### G04 — Archive/provenance change is not a source boundary

Same-market exact-adjacent candles from different archive files remain same segment. A truly observed/approved same-market repaired row may preserve continuity; provenance remains distinct.

### G05 — Fixed vs rolling

At 20:25, rolling 4h = `[16:25,20:25)`, fixed 4H remains `[16:00,20:00)`; distinct identities.

### G06 — Cross-timeframe ordinal

5m 00:15 inside 1H 00:00 has zero-based ordinal 3; 00:55 ordinal 11; expected children 12.

### G07 — Rolling speed/change/acceleration

Previous 30m: 100 -> 110 => return 10%, speed 20 percentage-points/hour.
Current 30m: 110 -> 115.5 => return 5%, speed 10.

Expected:

- `speed_change_pct_per_hour=-10`
- `acceleration_pct_per_hour2=-20`.

### G08 — Zero-net still has path and RV

For Q=`[100,200,100]`:

- net=0, direction=flat
- close_path=200
- efficiency=0
- upward=100, downward=100
- local with/against null
- sign changes=1, alternation=1
- log path=`2*ln(2)=1.3862943611198906`
- RV=`2*ln(2)^2=0.9609060278364028`
- realized volatility=`0.9802581434685472`.

### G09 — Zero-step alternation

Signs `+,0,-`: zero_count=1, nonzero_count=2, sign_change_count=1, alternation=1.

### G10 — Repeated extrema

P0=100, highs `[110,110,105,110]`, lows `[95,96,95,97]` at t0..t3.

Expected high=110 first=t0 last=t3 count=3; low=95 first=t0 last=t2 count=2; excursions +10/-5 abs and 10%/5%.

### G11 — Pair overlap/body/penetration

Previous O100 H110 L90 C108; current O107 H112 L94 C96.

Expected:

- range overlap [94,110], abs16, prev .8, curr 8/9, Jaccard 8/11;
- prev positions low .2, high1, mid .6;
- curr positions low0, high8/9, mid4/9;
- body overlap [100,107], abs7, prev7/8,curr7/11,Jaccard7/12;
- upper extension2/share.1; lower0;
- penetration from top extreme16/.8, body14/.7, close14/.7, wick-only2/.1;
- from bottom extreme20/1, body17/.85, close6/.3, wick-only3/.15.

Up observation selects top as against-move; down selects bottom; flat relative fields null.

### G12 — Two volume-direction systems

Prev close100; current O105 C102 V7.

Body direction=down; close-step direction=up. Volume 7 contributes independently to body-down and close-step-up.

### G13 — TR/ATR initialization/reset

First candle without valid previous close: TR null. Then 14 consecutive TR=2 => SMA14=2,Wilder=2. Next TR=4 => both fixture values `15/7`. Gap resets; first following TR null and Wilder waits for 14 new valid TRs.

### G14 — Direct retracement formula and tuple authorization

A=100,B=120:

- C110 => candidate/reference50, retracement50
- C90 => 150/150
- C130 => 50/0.

Also assert production engine does NOT materialize the tuple merely because A/B/C are individually available; relationship must be explicitly configured.

### G15 — Macro anchor-inclusive formula for exact compatible synthetic fixture

For exact compatible anchors P0=100,P1=112 and internal closes `[105,103,110]`:

- internal path=9
- anchor-inclusive path=16
- displacement=12
- anchor-inclusive efficiency=.75.

This tests formula only; production macro source must separately satisfy source/time-precision gate.

### G16 — Rolling calculation matrix

Exactly:

- 30m: 5m,15m
- 1h: 5m,15m
- 4h: 5m,15m,1H
- 12h: 5m,15m,1H,4H
- 24h: 5m,15m,1H,4H
- 3d: 5m,15m,1H,4H,1D.

### G17 — Stable UUID examples

Namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`:

- segment `segment|binance|BTCUSDT|spot|2018-01-01T00:00:00Z` = `adeeb6f8-cff1-5738-a02b-a75bd176b546`
- 5m candle = `cdf2383a-744c-5140-a130-cac2de6044be`
- fixed observation = `251296be-22d3-5ba5-9745-bead7257333f`
- rolling 30m ending 00:30 = `c5aab5b5-f528-5c9f-a7b4-81345bfb3270`
- next 5m candle = `e5f9c683-3ad6-5235-be04-a7fe331ee0d1`
- pair = `e3ce7198-17dd-5e2e-b03a-09636992e345`.

Run/path/provenance changes do not change these ids.

### G18 — Causality/future-data invariance

Causal fields ending t have `available_at=t`; excluded before t. Appending/changing data strictly after t cannot alter already causal rows through t. Macro context excluded from causal-only extraction.

### G19 — Forbidden semantic labels

Fail on newly generated first-pass fields such as `is_impulse`, `is_correction`, `impulse_label`, `correction_label`, `choppiness_score`, `range_state`, `breakout_label`, `parent_impulse_id`, `fib_*`, `fibtime_*` unless explicitly source-provenance-only and not treated as research truth.

### G20 — Feature dictionary consistency

Every materialized metric has exactly one compatible dictionary definition; no orphan metric, conflicting duplicate, availability mismatch, or undeclared schema feature.

### G21 — Schema/referential integrity

Primary/natural keys unique; observation/candle/macro/segment foreign keys resolve; no overlapping duplicate canonical rows across parts.

### G22 — Parquet manifests

Manifest row counts/parts/schema/time/partition values reconcile with physical data; all listed parts reconstruct one logical table without duplicate keys.

### G23 — Extraction

Small fixture must prove time/market/resolution/feature pruning, macro id extraction, causal exclusion, CSV equality with canonical Parquet, deterministic ordering and no hidden canonical-feature recomputation.

### G24 — Resume equivalence

Clean run vs interrupted+resumed run have identical canonical keys/values/statuses. Changed input checksum/schema/config rejects stale checkpoint.

### G25 — Native higher-timeframe QA source classification

A QA reference must be classified as either:

- `critical_validated_reference`; or
- `diagnostic_reference`.

Known legacy `cache_futures_1d/4h` with material inconsistency near 2019-09-24 SHALL NOT be used as critical ground truth there. A diagnostic mismatch is reported, not used to overwrite canonical values.

### G26 — Boundary-crossing fixed interval representation

With canonical boundary `2019-09-08T17:57:00Z`, fixed 5m `[17:55,18:00)`, 15m `[17:45,18:00)`, 1H `[17:00,18:00)`, 4H `[16:00,20:00)`, and 1D containing the boundary SHALL:

- exist as interval rows;
- have `market_type=cross_market`;
- `source_segment_id=null`;
- `completeness_status=incomplete_boundary`;
- complete OHLCV null;
- produce no valid complete fixed observation speed/path/RV.

### G27 — Synthetic no-trade futures bucket is excluded from strict canonical 1m

For `2019-09-08T19:00:00Z` audit facts:

- no native kline;
- zero official trades in the minute;
- diagnostic synthetic row OHLC=10000, volume/trades=0.

Strict canonical output SHALL NOT contain that synthetic row. `source_gaps` SHALL contain one futures gap `[19:00,19:01)` with appropriate reason; source segments split around it; complete higher intervals/windows requiring it become incomplete.

### G28 — Historical macro provenance remains mixed

For audited late-2019 macro anchors, assert parent daily regime remains old spot while refinement source may be futures 4H. `leg_source_classification=mixed` where audit says mixed. Current canonical boundary SHALL NOT overwrite historical macro provenance.

### G29 — Resolution-limited macro anchor blocks anchor-inclusive path

Fixture: macro anchor price is H/L of a 4H candle but timestamp is only that 4H bucket start and no exact extreme time is known.

Expected:

- source macro displacement remains preserved;
- internal canonical path may be calculated if coverage allows;
- anchor-inclusive path/efficiency null;
- `anchor_inclusive_status=anchor_time_precision_insufficient`.

### G30 — Canonical spot-gap grid alignment

Source audit evidence reports raw spot missing 6235, canonical-relevant 5972, 16 intervals before cutoff. Production SHALL recompute gaps from strict minute-grid canonical rows.

Audit interval strings containing non-minute seconds/milliseconds SHALL NOT be copied directly into `source_gaps`.

QA asserts:

- every canonical gap boundary is minute-aligned;
- no post-boundary raw spot gap enters canonical chronology;
- final canonical missing-minute total/interval count are compared against 5972/16 audit evidence;
- any difference requires explicit source-alignment explanation and review rather than silent acceptance.

### G31 — Atomic candle geometry materialization

For complete candle O100,H110,L90,C105:

- full_range20
- body_size5
- body_high105
- body_low100
- upper_wick5
- lower_wick10
- body_share.25
- upper_wick_share.25
- lower_wick_share.5
- body_direction=up
- log fields match exact formulas.

A complete target candle must resolve to exactly one `candle_geometry` row; incomplete boundary/gap candle must not masquerade as valid geometry.

### G32 — Fixed calculation matrix

Exactly:

- 15m via5m
- 1H via5m,15m
- 4H via5m,15m,1H
- 1D via5m,15m,1H,4H.

No lower-resolution path row for fixed 5m in first pass.

### G33 — Macro calculation matrix and RV exclusion

When enough canonical constituents exist, macro internal path/activity/overlap/volume may materialize at 5m,15m,1H,4H,1D. Macro RV fields SHALL remain null/not materialized as valid first-pass metrics unless a later approved macro RV contract exists.

### G34 — Canonical field-name regression

Fail if deprecated conflicting names are generated instead of canonical names, including:

- `local_direction_normalized_speed_pct_per_hour` instead of `local_direction_speed_pct_per_hour`;
- `volume_delta` instead of `volume_sum_change_vs_prev`;
- `volume_ratio` instead of `volume_sum_ratio_vs_prev`;
- `rolling_high_low_width` instead of `observation_high_low_width`;
- `mean_candle_range` instead of `mean_full_range`.

## Production invariants

### Requirement: Approved source gaps are visible, never hidden

Every canonical unresolved gap appears in `source_gaps`; no strict canonical row fills it with unobserved synthetic OHLC; no complete sequential feature bridges it.

### Requirement: Source boundary is read from one finalized contract

Tests/features SHALL consume configured canonical boundary, not duplicate a separate conflicting constant.

### Requirement: QA status is mechanically derived

Severities: `critical`, `warning`, `info`.

G01-G34 and schema/source/referential invariants are critical unless explicitly documented not-applicable by contract.

`qa_status=PASS` only when all applicable critical tests pass and `failure_report.json` has zero unresolved critical failures. Otherwise `FAIL`.
