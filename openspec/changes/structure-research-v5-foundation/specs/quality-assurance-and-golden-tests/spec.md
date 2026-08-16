# Quality Assurance and Golden-Test Contract

## Purpose

Make Structure Research v5 fail loudly and reproducibly when formulas, time boundaries, source continuity, causality, schema, resume behavior, or extraction semantics are wrong. A successful process exit is not evidence of a valid research dataset; success SHALL be derived from explicit assertions against deterministic fixtures and production invariants.

## ADDED Requirements

### Requirement: Golden tests are a hard gate before smoke or full-history production

The implementation SHALL provide automated golden tests covering the contracts below.

- No smoke run SHALL be treated as approved until all critical golden tests pass.
- No full-history production run SHALL begin until golden tests and the separately reviewed smoke gate pass.
- A failed critical assertion SHALL make the test stage fail and SHALL NOT be overwritten by a later unconditional success status.
- `COMPLETE`, `PASS`, or equivalent success SHALL be derived from assertion results, not assigned unconditionally.

The implementation SHALL emit at minimum:

- `golden_test_report.json` with every test id, expected result, observed result, and pass/fail status;
- `failure_report.json` containing every failed critical assertion and relevant evidence;
- `qa_summary.md` summarizing total/pass/fail counts and whether downstream smoke/full-run gates are open.

A zero-row or not-executed test SHALL NOT count as passed unless that test explicitly defines a valid not-applicable state.

### Requirement: Golden numeric tolerance is explicit

Synthetic fixture tests SHALL compare integers, booleans, enums, timestamps, identifiers, counts, and exact decimal OHLCV values exactly after canonical normalization.

For formulas involving logarithms or other floating operations, expected and observed values SHALL satisfy both the documented finite/null semantics and numerical closeness using at most:

- relative tolerance `1e-10`;
- absolute tolerance `1e-12`.

A looser tolerance requires an explicit test-specific justification in the report.

Real source-vs-source OHLCV QA SHALL compare normalized source precision exactly where feasible; otherwise tolerance SHALL NOT exceed one unit of the documented source precision/tick/quantity step without explicit review.

### Requirement: Golden fixture G01 validates deterministic 1m-to-5m OHLCV aggregation

Use five complete consecutive same-segment 1m candles:

| minute | open | high | low | close | volume |
|---|---:|---:|---:|---:|---:|
| 00:00 | 100 | 102 | 99 | 101 | 1 |
| 00:01 | 101 | 104 | 100 | 103 | 2 |
| 00:02 | 103 | 105 | 102 | 104 | 3 |
| 00:03 | 104 | 106 | 101 | 102 | 4 |
| 00:04 | 102 | 103 | 98 | 99 | 5 |

The canonical `00:00-00:05` 5m candle SHALL be:

- `open = 100`
- `high = 106`
- `low = 98`
- `close = 99`
- `volume = 15`
- `expected_constituent_count = 5`
- `observed_constituent_count = 5`
- `coverage_ratio = 1`
- `completeness_status = complete`.

### Requirement: Golden fixture G02 validates gap propagation and observed-only diagnostics

Remove the `00:02` candle from G01 while leaving the other four unchanged.

The canonical 5m row SHALL:

- have `expected_constituent_count = 5`;
- have `observed_constituent_count = 4`;
- have `coverage_ratio = 0.8`;
- be `incomplete_gap`;
- have complete canonical `open/high/low/close/volume = null`.

If observed-only diagnostics are emitted, they SHALL equal:

- `observed_only_open = 100`
- `observed_only_high = 106`
- `observed_only_low = 98`
- `observed_only_close = 99`
- `observed_only_volume = 12`.

Every containing 15m/1H/4H/1D interval whose canonical construction requires that missing 1m candle SHALL also be incomplete rather than silently complete.

The missing minute SHALL be represented in source-gap/coverage evidence and SHALL NOT be replaced by a synthetic flat or zero-volume candle.

### Requirement: Golden fixture G03 validates source-boundary isolation

Construct two timestamp-adjacent candles where the first belongs to `spot` segment A and the second to `usdt_m_futures` segment B.

Even when `curr.start_time == prev.end_time`:

- the cross-boundary pair SHALL be `pair_eligible = false`;
- no close-step return/log-return SHALL bridge the pair;
- True Range on the first futures candle SHALL be null because the spot close is not a valid previous close;
- ATR/Wilder state SHALL not continue across the boundary;
- rolling observations crossing the boundary SHALL be incomplete/null for complete metrics;
- path, RV, alternation, overlap, penetration, and previous-window comparison SHALL not bridge the boundary;
- any source-transition price difference SHALL remain a separate diagnostic only.

### Requirement: Golden fixture G04 validates archive/provenance changes do not create false source boundaries

Construct timestamp-adjacent same-market candles with identical venue/instrument/market type but different `raw_artifact_id` or monthly/daily archive provenance.

When no real gap exists:

- both SHALL remain in the same `source_segment_id`;
- the pair SHALL remain eligible;
- sequential TR/return/path logic SHALL continue normally.

A same-market candle reconstructed from approved lower-level official data SHALL likewise remain in the continuous segment when it completely repairs the missing interval; its row-level reconstruction provenance SHALL remain distinct.

### Requirement: Golden fixture G05 validates fixed versus rolling time semantics

At endpoint `20:25:00Z`:

- a rolling 4h observation SHALL represent `[16:25:00Z,20:25:00Z)`;
- the fixed 4H candle relevant to that area SHALL remain calendar aligned, e.g. `[16:00:00Z,20:00:00Z)`;
- the rolling and fixed observations SHALL have different observation identities and SHALL never be substituted for one another.

### Requirement: Cross-timeframe child ordinal is zero-based

`child_ordinal_in_parent` SHALL be zero-based in chronological order.

For a 5m child candle beginning `00:15:00Z` inside a fixed 1H parent `[00:00,01:00)`, the ordinal SHALL be `3`. A 5m candle beginning `00:55:00Z` SHALL have ordinal `11`.

G06 SHALL assert the correct parent ids, expected child count `12`, and these ordinals.

### Requirement: Golden fixture G07 validates rolling endpoint, adjacent-window speed change, and no historical recomputation semantics

Use 12 consecutive complete 5m candles covering `[00:00,01:00)` with continuous opens/closes such that:

- first 30m window `[00:00,00:30)` starts at `100` and ends at `110`;
- second 30m window `[00:30,01:00)` starts at `110` and ends at `115.5`.

At `01:00` the current 30m observation SHALL use `P0=110`, `P1=115.5`, so:

- `signed_return_pct = 5`;
- `raw_signed_speed_pct_per_hour = 10`.

The immediately preceding 30m observation SHALL have:

- `signed_return_pct = 10`;
- `raw_signed_speed_pct_per_hour = 20`.

Therefore:

- `speed_change_30m = -10` percentage-points-per-hour;
- `acceleration_30m = -20` percentage-points-per-hour-squared.

The implementation SHALL be able to produce the `01:00` row by advancing rolling state without mutating already-finalized earlier rolling rows.

### Requirement: Golden fixture G08 validates zero-net movement still preserves path and realized volatility

Use a complete 10m observation calculated from two 5m candles with price sequence:

`Q = [100, 200, 100]`

where `Q0` is the first candle open and subsequent values are constituent closes.

Expected:

- net signed price change `0`;
- local direction `flat`;
- `close_path = 200`;
- `path_efficiency = 0`;
- `upward_close_path = 100`;
- `downward_close_path = 100`;
- local with/against-direction path fields = null because observation direction is flat;
- non-zero step signs are `+,-`;
- `sign_change_count = 1`;
- `alternation_rate = 1`;
- `log_close_path = 2 * ln(2) = 1.3862943611198906`;
- `realized_variance = 2 * ln(2)^2 = 0.9609060278364028`;
- `realized_volatility = sqrt(2) * ln(2) = 0.9802581434685472`.

A zero net close-to-close displacement SHALL NOT zero out path, volatility, excursions, or activity.

### Requirement: Golden fixture G09 validates zero-step alternation convention

Use path step signs corresponding to `+, 0, -`.

Expected:

- `zero_step_count = 1`;
- `nonzero_step_count = 2`;
- non-zero sign sequence = `+,-`;
- `sign_change_count = 1`;
- `alternation_rate = 1`.

The zero step SHALL not be reclassified as up or down.

### Requirement: Golden fixture G10 validates repeated extrema and excursion semantics

For one observation with start price `P0=100` and four constituent candles whose highs are `[110,110,105,110]` and lows are `[95,96,95,97]` at consecutive constituent start times `t0,t1,t2,t3`:

Expected:

- `observation_high = 110`;
- `high_first_time = t0`;
- `high_last_time = t3`;
- `high_occurrence_count = 3`;
- `observation_low = 95`;
- `low_first_time = t0`;
- `low_last_time = t2`;
- `low_occurrence_count = 2`;
- `upward_excursion_abs = 10`;
- `downward_excursion_abs = 5`;
- `upward_excursion_pct = 10`;
- `downward_excursion_pct = 5`.

Occurrence timestamps/counts SHALL remain explicitly limited to the stated candle calculation resolution.

### Requirement: Golden fixture G11 validates range overlap, body overlap, position, extensions, and mirrored penetration

Use eligible pair:

Previous candle:

- `open=100`
- `high=110`
- `low=90`
- `close=108`
- body `[100,108]`
- range `20`.

Current candle:

- `open=107`
- `high=112`
- `low=94`
- `close=96`
- body `[96,107]`
- range `18`.

Expected range overlap:

- interval `[94,110]`
- `range_overlap_abs = 16`
- `overlap_share_prev = 0.8`
- `overlap_share_curr = 8/9`
- `overlap_jaccard = 8/11`
- previous-range overlap positions: low `0.2`, high `1`, midpoint `0.6`
- current-range overlap positions: low `0`, high `8/9`, midpoint `4/9`.

Expected body overlap:

- interval `[100,107]`
- `body_overlap_abs = 7`
- `body_overlap_share_prev = 7/8`
- `body_overlap_share_curr = 7/11`
- `body_overlap_jaccard = 7/12`.

Expected neutral extensions:

- `upper_extension_abs = 2`
- `lower_extension_abs = 0`
- `upper_extension_share_prev = 0.1`
- `lower_extension_share_prev = 0`.

Expected penetration from top, using previous full range:

- extreme `16`, share `0.8`
- body `14`, share `0.7`
- close `14`, share `0.7`
- wick-only `2`, share `0.1`.

Expected penetration from bottom:

- extreme `20`, share `1`
- body `17`, share `0.85`
- close `6`, share `0.3`
- wick-only `3`, share `0.15`.

For an `up` observation, against-move penetration SHALL select the from-top values. For a `down` observation it SHALL select from-bottom values. For a flat observation, direction-relative fields SHALL be null while neutral mirrored fields remain unchanged.

### Requirement: Golden fixture G12 validates the two volume-direction conventions independently

Let the valid temporally adjacent previous candle close at `100`.

For current candle:

- `open=105`
- `close=102`
- `volume=7`.

The candle SHALL be:

- `body_direction = down` because `102 < 105`;
- `close_step_direction = up` because `102 > 100`.

Therefore, for a one-bar grouping where the prior close is valid:

- body-direction volume contributes `7` to body-down;
- close-step-direction volume contributes `7` to close-step-up.

The implementation SHALL NOT force the two conventions to agree.

### Requirement: Golden fixture G13 validates True Range, ATR14 initialization, update, and reset

Construct one continuous resolution/segment where the first candle has no valid prior close and therefore `TR=null`.

Then provide 14 consecutive candles each with valid `TR=2`.

At the 14th valid TR endpoint:

- `atr14_sma = 2`;
- `atr14_wilder = 2`.

For the next adjacent candle with `TR=4`:

- `atr14_wilder = ((13*2)+4)/14 = 15/7 = 2.142857142857143`;
- `atr14_sma` over the latest 14 valid TR values also equals `15/7` in this fixture.

After an unresolved gap/source-boundary reset:

- the first following candle SHALL have `TR=null` if no valid adjacent previous close exists;
- Wilder ATR SHALL be null until 14 new consecutive valid TR observations reinitialize it.

### Requirement: Golden fixture G14 validates direct retracement without Fibonacci semantics

For approved anchors `A=100`, `B=120`:

- if `C=110`, `candidate_vs_reference_pct=50` and `retracement_pct=50`;
- if `C=90`, `candidate_vs_reference_pct=150` and `retracement_pct=150`;
- if `C=130`, `candidate_vs_reference_pct=50` but `retracement_pct=0` because the move continues in the reference direction.

No Fib ratio/label SHALL be emitted.

### Requirement: Golden fixture G15 validates macro-leg anchor-inclusive path separately from internal path

For an approved macro leg with `P0=100`, `P1=112` and eligible internal chronological finer closes `[105,103,110]` inside one complete continuous source segment:

- `internal_close_path = abs(105-103) + abs(103-110) = 9`;
- `anchor_inclusive_close_path = abs(105-100) + 9 + abs(112-110) = 16`;
- absolute macro-leg displacement = `12`;
- anchor-inclusive path efficiency = `12/16 = 0.75`.

Internal path SHALL not silently include source anchors; anchor-inclusive path SHALL not silently omit them.

If the same macro leg fixture is modified so the path crosses a source boundary or unresolved required gap, the complete whole-leg sequential path and efficiency SHALL become null while the source macro anchor movement/duration remains preserved as retrospective source information.

### Requirement: Golden fixture G16 validates rolling calculation-resolution eligibility matrix

The implementation SHALL reproduce exactly this first-pass matrix:

- `30m`: `5m`, `15m`
- `1h`: `5m`, `15m`
- `4h`: `5m`, `15m`, `1H`
- `12h`: `5m`, `15m`, `1H`, `4H`
- `24h`: `5m`, `15m`, `1H`, `4H`
- `3d`: `5m`, `15m`, `1H`, `4H`, `1D`.

No ineligible combination SHALL be materialized as a valid complete feature row.

### Requirement: Golden fixture G17 validates deterministic stable identifiers

Using UUIDv5 namespace `87411ce4-8483-55b7-a348-700b7ad4b9ab`, the implementation SHALL reproduce these exact examples:

- `uuid5(namespace, "segment|binance|BTCUSDT|spot|2018-01-01T00:00:00Z") = adeeb6f8-cff1-5738-a02b-a75bd176b546`
- `uuid5(namespace, "candle|binance|BTCUSDT|spot|5m|2018-01-01T00:00:00Z") = cdf2383a-744c-5140-a130-cac2de6044be`
- fixed observation for that candle = `251296be-22d3-5ba5-9745-bead7257333f`
- rolling `30m` observation ending `2018-01-01T00:30:00Z` = `c5aab5b5-f528-5c9f-a7b4-81345bfb3270`
- next 5m candle at `00:05` = `e5f9c683-3ad6-5235-be04-a7fe331ee0d1`
- pair of the two listed 5m candles = `e3ce7198-17dd-5e2e-b03a-09636992e345`.

Changing `run_id`, raw local path, or archive filename without changing canonical entity identity SHALL reproduce the same entity ids.

### Requirement: Golden fixture G18 validates causal availability and future-data invariance

For a complete fixed/rolling observation ending at time `t`:

- its causal close-known fields SHALL have `available_at=t`;
- a causal extraction with `as_of < t` SHALL exclude them;
- a causal extraction with `as_of >= t` MAY include them.

After causal rows through time `t` are finalized, append or modify only market data strictly after `t` and recompute from a clean state.

Every causal feature whose contract uses only data available at or before `t` SHALL reproduce the same value/id/status as before. A future-data-induced change to such a row is a critical leakage failure.

Macro-leg endpoint-dependent context SHALL remain retrospective and SHALL be excluded from causal-only extraction.

### Requirement: Golden fixture G19 validates no forbidden first-pass semantic labels leak into canonical research features

Generated feature/schema names SHALL be scanned for newly created first-pass semantic classifications.

The pipeline SHALL fail if it creates unapproved generated fields such as:

- `is_impulse`
- `is_correction`
- `impulse_label`
- `correction_label`
- `choppiness_score`
- `range_state`
- `breakout_label`
- `parent_impulse_id`
- `fib_*`
- `fibtime_*`

Source-provenance fields retained verbatim from approved inputs are allowed only when clearly identified as source provenance and not treated as validated research truth.

### Requirement: Golden fixture G20 validates feature-dictionary completeness and consistency

Every materialized research metric column SHALL have exactly one applicable feature-dictionary definition containing formula/derivation, units, calculation-resolution semantics, availability class, available-at rule, null meaning, and provenance.

Identity, partition-pruning, run, schema, and pure provenance metadata fields MAY use a documented metadata whitelist rather than feature entries.

The QA stage SHALL fail on:

- a metric column without dictionary definition;
- incompatible duplicate definitions for the same logical table/feature;
- a dictionary feature not present in the declared schema unless explicitly marked planned/non-materialized;
- mismatch between dictionary availability class and physical table/extraction behavior.

### Requirement: Golden fixture G21 validates canonical schema keys and referential integrity

For every canonical logical table:

- declared primary/natural keys SHALL be unique;
- `observation_id` foreign keys SHALL resolve to `observation_index`;
- candle ids SHALL resolve to the appropriate candle table;
- eligible pair ids SHALL reference valid candle ids at the declared calculation resolution;
- macro context SHALL resolve both observation and macro-leg ids;
- source-segment ids SHALL resolve when non-null;
- manifests SHALL not contain overlapping duplicate canonical rows across parts.

Any orphaned required foreign key or duplicate canonical primary key is a critical failure.

### Requirement: Golden fixture G22 validates Parquet manifests and partition reconstruction

For each logical table manifest:

- manifest part row counts SHALL sum to the logical-table row count;
- listed parts SHALL exist and match schema/version;
- min/max temporal coverage SHALL agree with actual part data;
- declared partition values SHALL agree with row pruning columns;
- checksums/integrity evidence SHALL validate where required;
- reading all listed parts SHALL reconstruct the logical table without duplicate canonical keys.

The extraction utility SHALL use the deterministic catalog/manifest rather than guessing unlisted files from a directory.

### Requirement: Golden fixture G23 validates extraction from Parquet without hidden recomputation

Build a small canonical fixture containing at least:

- multiple market types or source segments;
- multiple target/calculation resolutions;
- one macro leg;
- causal and retrospective fields.

An extraction request filtering by time range/market type, selected observation ids or macro-leg id, calculation resolution, selected feature families, and `availability_class=causal` SHALL return exactly the matching stored canonical rows/columns.

The test SHALL assert:

- unrelated partitions/rows are excluded;
- retrospective macro context is excluded from causal-only output;
- requested CSV contents equal the selected canonical Parquet values;
- extraction does not recalculate a canonical metric into a different value;
- CSV partitioning, if triggered, preserves identical schema and deterministic row order/manifest reconstruction.

### Requirement: Golden fixture G24 validates resume equivalence and incompatible-checkpoint rejection

Run a deterministic synthetic dataset once from clean start to completion and record canonical key sets/content hashes.

Run the same dataset/configuration again but interrupt after at least one persisted checkpoint and resume.

The resumed result SHALL have:

- identical canonical primary-key sets;
- identical metric values/statuses;
- no duplicate canonical rows;
- no missing finalized rows;
- equivalent logical-table manifests apart from explicitly run-specific metadata.

Then attempt resume with a deliberately changed input checksum, schema version, or calculation configuration. The stale/incompatible checkpoint SHALL be rejected explicitly rather than silently reused.

### Requirement: Golden fixture G25 validates native higher-timeframe QA against canonical 1m-derived candles

Where an approved native Binance higher-timeframe QA reference exists for the same venue/instrument/market type and a complete canonical interval:

- canonical 1m-derived OHLCV SHALL be compared with the native QA candle;
- interval alignment/timestamp semantics SHALL be normalized first;
- mismatches SHALL be reported with candle id/timeframe/time, derived value, native value, and source provenance.

A material unexplained OHLCV mismatch SHALL be a critical QA failure for that source/interval rather than being silently resolved by replacing the canonical derived candle with the native value.

Known documented source limitations MAY be marked explicitly not-applicable only with evidence in the QA report.

### Requirement: Production QA validates irrecoverable gaps rather than hiding them

The final source contract SHALL provide the approved unresolved-gap inventory.

Production QA SHALL assert that:

- every approved irrecoverable gap is represented in `source_gaps`;
- no canonical 1m candle exists for a minute documented as irrecoverably missing unless a later explicitly approved repair changes the source contract;
- no path/rolling/RV/ATR/pair calculation bridges such a gap as complete;
- segment boundaries around the gap are consistent with the source-segment contract.

The already investigated Binance spot gaps that remain unrecoverable after official aggTrades recovery attempts SHALL be treated under this rule once their final artifact paths/counts are inserted into the source contract.

### Requirement: QA tests actual source-boundary timestamp from final source contract

The spot-to-futures boundary SHALL NOT be hardcoded independently inside test code.

After the early-futures source investigation is finalized, the approved exact boundary timestamp and evidence SHALL be represented once in the source contract/configuration. QA SHALL read that approved value and assert:

- candles before/after the boundary use the correct market type;
- no source segment crosses the boundary;
- no complete sequential feature bridges it;
- macro-leg handling follows the approved cross-boundary rule.

A test suite with a separately hardcoded conflicting boundary SHALL fail configuration validation.

### Requirement: QA final status is mechanically derived

Define three test severities:

- `critical`: failure closes the smoke/full-run gate;
- `warning`: dataset MAY remain usable but evidence requires review;
- `info`: diagnostic only.

All G01-G25 requirements and source/schema/referential integrity checks described above are `critical` unless a requirement explicitly permits documented not-applicability.

`qa_status = PASS` only when:

- every applicable critical test passed;
- no critical test was skipped without an approved not-applicable reason;
- `failure_report.json` contains zero unresolved critical failures.

If any critical assertion fails, `qa_status = FAIL`.

No post-processing step SHALL overwrite `FAIL` with a success-like status because the pipeline completed or because failures are considered "known coverage limits". Known approved coverage gaps are represented as expected source conditions and tested accordingly; unexpected contract violations remain failures.
