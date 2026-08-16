# Time and Cross-Timeframe Contract

## Purpose

Define the unambiguous UTC time grid, fixed-versus-rolling semantics, cross-timeframe containment, incomplete-window handling, and macro/calendar intersection behavior.

## ADDED Requirements

### Requirement: UTC is canonical

All candle boundaries, rolling endpoints, containment, coverage and exported timestamps use UTC. Local time/DST never changes interval boundaries.

### Requirement: Canonical intervals are half-open

Canonical candle interval is `[start_time,end_time)`.

Source-native inclusive close timestamps such as `...59.999` may be retained as provenance but do not define canonical interval end.

### Requirement: Canonical 1m starts are exactly minute-grid aligned

A canonical 1m candle start must be `HH:MM:00.000000Z` and end exactly one minute later.

Non-minute-aligned source timestamps are anomalies requiring explicit source validation. They SHALL NOT be silently rounded into canonical rows or gap boundaries.

### Requirement: Fixed target intervals are calendar aligned

- `1D`: UTC 00:00 -> next 00:00
- `4H`: 00-04,04-08,08-12,12-16,16-20,20-24
- `1H`: HH:00 -> next hour
- `15m`: :00/:15/:30/:45
- `5m`: minute divisible by 5.

The fixed interval grid remains calendar aligned even where the market source changes inside an interval.

### Requirement: A fixed interval crossing market-source boundary remains a grid row, not a complete candle

If the canonical spot/futures boundary falls inside a fixed target interval, retain that interval row as `market_type=cross_market`, `source_segment_id=null`, `completeness_status=incomplete_boundary`, and complete OHLCV/features null.

Observed-only diagnostics may remain explicitly named. The grid SHALL NOT be shifted to make the boundary align.

### Requirement: Fixed and rolling are separate concepts

A rolling lookback ending at `t` is `[t-W,t)` and is not snapped to calendar grid.

Example: rolling 4h ending `20:25` = `[16:25,20:25)`, distinct from fixed 4H `[16:00,20:00)`.

Approved rolling durations are `30m`,`1h`,`4h`,`12h`,`24h`,`3d` according to the schema matrix.

### Requirement: Target feature-producing resolutions

`5m`,`15m`,`1H`,`4H`,`1D`. Canonical `1m` remains source/drill-down and macro-anchor refinement layer.

### Requirement: Cross-timeframe containment is deterministic

For target-to-target mappings preserve parent ids, zero-based child ordinal, expected/observed counts and coverage. Incomplete child/parent status remains explicit.

### Requirement: Incomplete observations are explicit

Every metric requiring constituents records expected count, observed valid count, coverage ratio and completeness/gap/boundary status.

For incomplete fixed/rolling intervals, ordinary complete `start_price/end_price`, displacement, direction and speed SHALL not be inferred from partial observed-only constituents.

### Requirement: Macro-leg boundaries do not shift the canonical candle grid

A macro leg beginning/ending inside a candle does not alter canonical candle boundaries. Macro membership/uncertainty is represented separately.

### Requirement: Coarse macro anchor timestamps define possible-time intervals

A macro source timestamp that is the start of a bucket whose anchor price is that bucket high/low is not an exact extreme time.

Represent the possible-time interval as:

- `4H_bucket` timestamp T => `[T,T+4h)`;
- `1D_bucket` timestamp T => `[T,T+1d)`;
- equivalent rules for any other explicitly supported bucket precision.

The source timestamp remains preserved, but the whole possible-time interval is the temporal uncertainty of the anchor until stronger evidence is found.

### Requirement: Coarse macro anchors are refined against canonical 1m before macro membership is assigned

For every source-compatible non-exact macro anchor, search the complete canonical 1m rows inside its possible-time interval for the exact source high/low price according to anchor type.

The search outcome is one of:

- `unique_1m_match`;
- `multiple_1m_matches`;
- `no_1m_match`;
- `incomplete_search_coverage`;
- `source_incompatible`.

A unique claim requires complete canonical 1m search coverage of the bucket. Multiple matching minutes SHALL NOT be reduced to a chosen first/last/nearest candidate.

### Requirement: 1m refinement narrows but does not eliminate intra-minute uncertainty

If exactly one canonical 1m candle matches, the anchor possible-time interval becomes that minute `[m,m+1m)`.

The exact event order inside that minute is still unknown. The minute is therefore a boundary-uncertainty interval, not a candle wholly belonging to one adjacent macro leg.

If multiple matches exist, the possible-time interval conservatively spans from the first candidate minute start through the last candidate minute end.

If no unique valid refinement is possible, retain the coarser source interval.

### Requirement: Shared pivots define complementary adjacent-leg safe boundaries

When the same pivot ends one macro leg and begins the next, both legs SHALL reference the same anchor uncertainty interval `[U0,U1)`.

- previous leg safe membership ends at `U0`;
- next leg safe membership begins at `U1`;
- `[U0,U1)` remains ambiguous and is not arbitrarily assigned to either leg.

Example: if an extremum is uniquely localized to minute `[05:23,05:24)`, complete data before 05:23 may belong safely to the preceding leg, complete data from 05:24 onward may belong safely to the following leg, and the 05:23 minute itself remains a boundary interval.

### Requirement: Safe macro interior has exact temporal definition

For macro start-anchor possible interval `[S0,S1)` and end-anchor possible interval `[E0,E1)`:

`safe_interior = [S1,E0)`.

A canonical calculation candle belongs to the safe interior only if its entire half-open candle interval lies within `[S1,E0)`.

Candles overlapping either uncertainty interval are retained in canonical market data but are not assigned to safe macro interior metrics.

If `S1 >= E0`, the safe interior is empty.

### Requirement: Macro source coordinates remain separate from canonical safe-interior coordinates

Preserve source start/end timestamps, prices and source duration exactly as retrospective source fields even when their timing is bucket-limited.

Also preserve refined possible-time intervals and `safe_interior_start_time/safe_interior_end_time` separately.

Source-coordinate duration/time progress SHALL NOT be described as exact canonical event timing.

### Requirement: Macro observations are retrospective, not live signals

Macro observations and macro-anchor refinement records have `availability_class=retrospective`.

Macro `available_at` SHALL be null in the first-pass canonical schema rather than pretending the source bucket-start/end timestamp was a live-known availability time.

Causal/as-of extraction excludes these rows.

### Requirement: Repeated extrema preserve first, last and count at calculation resolution

For observation maximum/minimum preserve first constituent start time, last constituent start time and occurrence count at the stated calculation resolution. These are candle-resolution observations, not tick touch times.

### Requirement: Excursions from observation start have exact formulas

For valid complete observation start `P0`, maximum `H`, minimum `L`:

- `upward_excursion_abs=max(0,H-P0)`
- `downward_excursion_abs=max(0,P0-L)`
- `upward_excursion_pct=100*(H/P0-1)` when `P0>0`
- `downward_excursion_pct=100*(1-L/P0)` when `P0>0`
- log counterparts may be retained for positive prices.

### Requirement: Zero net displacement does not imply zero activity

Start=end may coexist with nonzero path, range, excursions, overlap/activity and volatility. These measurements remain separate.
