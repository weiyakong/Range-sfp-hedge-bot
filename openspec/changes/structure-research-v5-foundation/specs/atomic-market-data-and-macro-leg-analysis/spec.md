# Atomic Market Data and Macro-Leg Analysis Contract

## Purpose

Ensure that one approved research run leaves enough atomic market data and whole-leg measurements across the full approved BTC history to investigate movement behavior later without rerunning market-data download or inventing missing semantics.

## ADDED Requirements

### Requirement: Production coverage uses the full approved history

The first production research dataset SHALL target the full approved BTC history from the earliest approved source timestamp through the latest approved source timestamp, subject to actual coverage and integrity.

The pipeline SHALL NOT impose `2023-01-01` or `2024-01-01` as collection cutoffs. Those periods MAY receive higher analytical priority later without reducing stored historical coverage.

### Requirement: Source segment means canonical 1m market continuity, not file provenance or target timeframe

Every canonical 1m candle SHALL carry row-level provenance and a `source_segment_id`.

`source_segment_id` SHALL identify one temporally continuous sequence of canonical 1m candles for the same venue, instrument, and market type. It is defined on the canonical 1m market spine and inherited by complete target candles/observations that lie wholly within one such segment.

It SHALL NOT change merely because a new archive file begins, a different local path stores the next raw part, a candle was downloaded in another run, or row-level provenance changes while canonical market continuity remains valid.

A new source segment SHALL begin at a real unresolved canonical gap, market-type transition, venue/instrument change, or another documented discontinuity that invalidates sequential calculations.

A synthetic diagnostic bucket whose OHLC is not observed from approved source data SHALL NOT repair canonical continuity merely because it fills a timestamp.

### Requirement: Canonical 1m source layer is retained without heavy 1m feature materialization

The approved canonical `1m` OHLCV history SHALL remain queryable as the finest candle source/drill-down layer.

Each retained 1m candle SHALL preserve at minimum stable identity, instrument, venue, market type, `source_segment_id`, canonical UTC `[start_time,end_time)`, OHLC, source-native volume, row-level provenance, validation status, and completeness status.

Every canonical 1m start SHALL be exactly minute-grid aligned. Non-minute-aligned source rows SHALL be explicitly validated/classified rather than silently rounded.

The first production pass SHALL NOT be required to materialize the complete heavy feature family on every 1m candle. Full-market feature production begins at `5m` unless a separately approved feature requires 1m calculation.

### Requirement: Canonical target candles are deterministically derived from canonical 1m

Canonical `5m`, `15m`, `1H`, `4H`, and `1D` intervals SHALL be evaluated from the strict canonical `1m` spine.

Native/local higher-timeframe candle datasets are QA/reference sources only unless a future approved source-contract change says otherwise.

### Requirement: Complete target-candle aggregation has exact formulas

For a target interval whose exact expected 1m constituents are present, aligned, and all belong to one source segment:

- `open = first constituent open`
- `high = max(constituent high)`
- `low = min(constituent low)`
- `close = last constituent close`
- additive volume/native additive fields follow the volume contract.

Expected counts:

- `5m`: 5
- `15m`: 15
- `1H`: 60
- `4H`: 240
- `1D`: 1440.

Each target row preserves expected count, observed valid canonical count, coverage ratio, source scope, and completeness state.

### Requirement: Boundary-crossing and gap-containing target intervals remain explicit rows but cannot masquerade as complete candles

The fixed UTC grid remains complete as an interval index even where a target interval intersects the spot/futures boundary, a canonical source gap, or more than one source segment.

Such a row is retained with an explicit incomplete status. If more than one market type contributes, logical `market_type=cross_market` and `source_segment_id=null`.

Complete OHLC/volume used by research SHALL be null for an incomplete interval. Explicit `observed_only_*` diagnostics MAY remain, but no interpolation or synthetic constituent is permitted.

### Requirement: Atomic target-candle records remain queryable

For target resolutions `5m`, `15m`, `1H`, `4H`, and `1D`, retain candle-level rows with stable id, venue/instrument, market type/source scope, source segment when single-segment complete, timeframe, canonical times, complete OHLCV when valid, construction provenance, 1m source resolution, constituent counts, coverage, and completeness status.

### Requirement: Source construction map is explicit

Before full production, run provenance SHALL record the exact canonical 1m source artifacts/manifests and deterministic 1m->target construction contract.

Native higher-timeframe QA sources MAY be listed separately as diagnostic or validated QA references and SHALL NOT be confused with canonical target-candle provenance.

### Requirement: Canonical timestamp semantics are explicit

Canonical candles use UTC half-open `[start_time,end_time)` intervals. Source-native inclusive close timestamps may be retained only as provenance.

### Requirement: Approved macro-leg source is explicit

Whole-leg research SHALL use the approved `macro_legs_log20.csv` unless the user explicitly approves a replacement.

The configured source SHALL be exact and fingerprinted; the pipeline SHALL NOT substitute similarly named files.

The reviewed SHA-256 is:

`c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`.

The reviewed source has 128 legs and explicit start/end event ids, times, prices, movement and duration fields.

### Requirement: Macro historical provenance is separate from current canonical market scope

The forensic audit establishes that the old merged daily source remained spot through `2019-12-30`, switched to futures on `2019-12-31`, and the macro build also used futures 4H refinement beginning in September 2019.

Therefore audited late-2019 source provenance may be `mixed` (`spot daily + futures 4H refinement`). This historical provenance SHALL be retained separately from the current canonical market scope of the same wall-clock interval.

A late-2019 macro leg may therefore simultaneously have:

- canonical `market_type=usdt_m_futures`; and
- historical `leg_source_classification=mixed`.

Historical mixed provenance SHALL NOT cause canonical `market_type` to become null.

### Requirement: Coarse macro anchor timestamps are uncertainty intervals, not exact extreme times

A source anchor timestamp that denotes the start of a 4H or 1D bucket while the anchor price is the bucket high/low identifies a bucket containing the extreme; it does not prove the extreme occurred at the bucket start.

For every macro anchor preserve source time, source price, extreme type, source/refinement market and timeframe, source time precision, and a possible-time interval.

Examples:

- `4H_bucket` at 16:00 => initial possible-time interval `[16:00,20:00)`;
- `1D_bucket` at 00:00 => initial possible-time interval `[00:00,next 00:00)`.

### Requirement: Every compatible coarse macro anchor SHALL first be refined against canonical 1m

Before assigning macro-specific canonical candles to a leg, the pipeline SHALL attempt to localize every non-exact source anchor inside its source/refinement bucket using the strict canonical 1m data from the compatible market population.

The search uses the anchor's source price and extreme type:

- low anchor: canonical 1m `low` matching the source anchor price;
- high anchor: canonical 1m `high` matching the source anchor price.

Price matching SHALL use deterministic source/canonical decimal normalization, not a heuristic nearest-price search. Any non-exact tolerance requires an explicit separately tested rule.

The entire search bucket must have complete canonical 1m coverage before an observed single match may be called unique. A gap inside the bucket prevents a uniqueness claim.

If the historical refinement price came from futures 4H, the 1m search uses compatible canonical futures. If it came from spot, the search uses compatible canonical spot. If source and canonical markets are incompatible for the anchor, refinement status is explicit and the coarse uncertainty is retained.

### Requirement: 1m refinement preserves uniqueness versus ambiguity

For a coarse anchor search bucket:

- exactly one matching complete canonical 1m candle with complete search coverage => `unique_1m_match` and possible-time interval becomes that minute `[m,m+1m)`;
- multiple matching 1m candles => `multiple_1m_matches`; no candidate is chosen arbitrarily; possible-time interval conservatively spans from the first candidate minute start through the last candidate minute end;
- zero matches => `no_1m_match`; retain the original coarse bucket uncertainty;
- incomplete search coverage => `incomplete_search_coverage`; retain the original coarse bucket uncertainty unless a later approved source provides stronger evidence;
- incompatible source/canonical market => `source_incompatible`; retain source uncertainty.

The candidate count plus first/last candidate times SHALL be preserved. The pipeline SHALL NOT silently select first, last, or nearest match when multiple candidates exist.

### Requirement: A unique 1m anchor minute is still a boundary minute

A unique 1m match does not reveal the exact intra-minute event order. The extremum may occur anywhere inside that minute.

Therefore the matching 1m candle is an ambiguous boundary interval for adjacent macro legs: part of that minute may precede the extremum and part may follow it.

The boundary minute remains fully preserved in canonical market data but SHALL NOT be assigned wholesale to either adjacent leg's safe interior.

### Requirement: Shared macro pivots remain shared boundaries

When one source event is the end anchor of one macro leg and the start anchor of the next, both legs SHALL reference the same refined anchor/uncertainty record.

For anchor possible-time interval `[U0,U1)`:

- the preceding leg's safe interior ends at `U0`;
- the following leg's safe interior begins at `U1`;
- the uncertainty interval `[U0,U1)` remains a preserved ambiguous boundary zone and is not arbitrarily assigned to either safe interior.

Thus if an extremum is uniquely localized to minute `[05:23,05:24)`, the previous safe leg can contain complete intervals ending no later than 05:23, the next safe leg can contain complete intervals starting no earlier than 05:24, and the 05:23 minute itself remains boundary-ambiguous.

### Requirement: Safe macro interior is defined from anchor uncertainty, not source bucket starts

For a macro leg with start-anchor possible interval `[S0,S1)` and end-anchor possible interval `[E0,E1)`, define:

- `safe_interior_start_time = S1`
- `safe_interior_end_time = E0`.

A canonical calculation candle belongs to the safe interior only when its entire half-open interval lies inside `[S1,E0)`.

If `S1 >= E0`, that leg has no non-empty safe interior at that resolution.

This rule prevents candles before the actual start extremum or after the actual end extremum from being attributed to the leg merely because the source anchor timestamp was a bucket start.

### Requirement: Boundary-ambiguous market data are never discarded

Candles overlapping an anchor uncertainty interval remain queryable in `candles_1m`/`candles_fixed` and can be extracted together with the anchor record.

They are excluded only from macro metrics that require unambiguous leg membership. They are not deleted, filled, or reassigned to another leg.

### Requirement: Macro source displacement remains first-class even when timing is coarse

For every approved macro leg preserve the original source start/end prices, source movement, source direction, source duration fields and their provenance exactly as source research measurements.

Coarse or ambiguous anchor timing SHALL NOT alter the source leg prices or rewrite the original macro segmentation.

Source duration/speed based on source timestamps remains explicitly source-coordinate/retrospective and SHALL NOT be represented as newly exact canonical event timing.

### Requirement: Macro canonical path/activity uses only the safe interior unless exact full-boundary reconstruction is available

At an approved calculation resolution, macro canonical path/activity/overlap/volume summaries SHALL use only complete canonical candles fully inside the safe interior.

For safe interior closes `C1...Cn`, where `n>=2`:

- `safe_internal_close_path = sum(abs(C_i-C_(i-1)))`;
- equivalent log path uses absolute log ratios for positive prices;
- `safe_internal_displacement = C_n-C_1`;
- `safe_internal_path_efficiency = abs(safe_internal_displacement)/safe_internal_close_path` when path > 0.

Directional path, alternation, activity, overlap and volume summaries use the same safe constituent set and explicit coverage status.

These metrics describe the guaranteed interior portion of the macro leg and SHALL NOT be named or interpreted as complete whole-leg canonical path when boundary portions remain uncertain.

### Requirement: Complete anchor-inclusive whole-leg path is strongly gated

A complete source-anchor-inclusive canonical path may be materialized only when the implementation can establish the full ordered price sequence from each source anchor through the canonical path without unobserved/ambiguous boundary portions, source gaps, or market incompatibility.

A `4H_bucket`, `1D_bucket`, unique `1m_bucket`, or multiple-1m uncertainty by itself is insufficient for a complete whole-leg path because some within-boundary path remains unobserved or unassignable.

In those cases:

- source macro displacement remains valid;
- safe interior metrics may be valid;
- complete `anchor_inclusive_*` whole-leg metrics SHALL be null with an explicit status such as `boundary_path_unobserved`, `anchor_time_precision_insufficient`, `source_incompatible`, or `coverage_incomplete`.

The synthetic exact-anchor golden fixture may test the complete formula independently of production applicability.

### Requirement: Macro realized volatility is not required in this pass

Macro observations MAY receive safe-interior volume/activity/overlap summaries according to the approved calculation matrix.

Realized variance/volatility for macro observations is NOT a required first-pass feature unless a separate approved formula defines an exact complete boundary sequence. Fixed/rolling RV semantics SHALL NOT be silently reused.

### Requirement: Macro observations are retrospective and do not fake live availability

Macro observations and macro-anchor refinement records are retrospective research entities.

For macro `observation_index` rows:

- `availability_class=retrospective`;
- `available_at=null`.

Source anchor timestamps, possible-time intervals and source duration remain separate fields. A bucket-start timestamp SHALL NOT be used as a fake live availability timestamp.

Causal/as-of extraction SHALL exclude macro observations/context regardless of source timestamps.

### Requirement: Gaps cannot masquerade as valid macro path

Every macro resolution-dependent metric SHALL preserve safe expected/observed constituent count, coverage ratio, source-segment status and boundary/refinement status.

No safe interior metric may bridge a canonical gap or market boundary. Any observed-only/partial diagnostic remains explicitly incomplete.

### Requirement: Whole-leg overlap summaries remain reconstructable from atomic pairs

Eligible atomic pairs remain timestamped/keyed so safe macro interiors and later arbitrary intervals can be reaggregated without recollecting market data.

Where safe pair coverage exists, preserve at minimum overlap-share, Jaccard, body-overlap, any-overlap, penetration and extension summaries plus contributing pair count/coverage.

### Requirement: Modern contrast cases are directly extractable without limiting historical storage

Extraction SHALL support selection of macro legs, their anchor-refinement records, safe-interior feature rows, ambiguous boundary candles, and underlying atomic pairs by `macro_leg_id`/anchor id, including multiple ids in one request.

This supports direct comparison of modern movements with similar log distance but different internal behavior while retaining full approved history.
