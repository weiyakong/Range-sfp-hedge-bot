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

If the canonical spot/futures boundary falls inside a fixed target interval, retain that interval row as:

- logical `market_type=cross_market`;
- `source_segment_id=null`;
- `completeness_status=incomplete_boundary`;
- complete OHLCV and complete feature metrics null.

Observed-only diagnostics may remain explicitly named.

Example for boundary `2019-09-08T17:57:00Z`:

- 5m `[17:55,18:00)` is incomplete_boundary;
- 15m `[17:45,18:00)` is incomplete_boundary;
- 1H `[17:00,18:00)` is incomplete_boundary;
- 4H `[16:00,20:00)` is incomplete_boundary;
- 1D `[00:00,next 00:00)` is incomplete_boundary.

The grid SHALL NOT be shifted to make the boundary align.

### Requirement: Fixed and rolling are separate concepts

A rolling lookback ending at `t` is `[t-W,t)` and is not snapped to calendar grid.

Example: rolling 4h ending `20:25` = `[16:25,20:25)`, distinct from fixed 4H `[16:00,20:00)`.

### Requirement: Approved rolling durations

`30m`,`1h`,`4h`,`12h`,`24h`,`3d`, according to exact calculation-resolution matrix in schema.

### Requirement: Target feature-producing resolutions

`5m`,`15m`,`1H`,`4H`,`1D`. Canonical `1m` remains source/drill-down layer.

### Requirement: Cross-timeframe containment is deterministic

For target-to-target mappings preserve parent ids, zero-based child ordinal, expected/observed counts and coverage.

A child or parent may be incomplete; mapping status must preserve that fact.

### Requirement: Incomplete observations are explicit

Every metric requiring constituents records expected count, observed valid count, coverage ratio and completeness/gap/boundary status.

Missing/boundary constituents SHALL NOT be treated as complete.

For incomplete fixed/rolling intervals, ordinary complete `start_price/end_price`, displacement, direction and speed SHALL not be inferred from partial observed-only constituents. Diagnostic observed-only endpoints may be stored under explicit names.

### Requirement: Macro-leg boundaries do not shift candle grid

A macro leg beginning/ending inside a fixed candle does not alter the fixed candle boundaries. Store exact temporal intersection separately.

### Requirement: Macro anchor timestamps retain their true time precision

A macro anchor timestamp representing the start of a 4H bucket whose price is that bucket high/low is a resolution-limited bucket timestamp, not exact extreme touch time.

Such a timestamp SHALL NOT be used to assert finer temporal ordering for anchor-inclusive path unless additional exact timing evidence exists.

### Requirement: Repeated extrema preserve first, last and count at calculation resolution

For observation maximum/minimum preserve:

- first constituent start time at that resolution;
- last constituent start time;
- occurrence count.

These are candle-resolution observations, not tick touch times.

### Requirement: Excursions from observation start have exact formulas

For valid complete observation start `P0`, maximum `H`, minimum `L`:

- `upward_excursion_abs=max(0,H-P0)`
- `downward_excursion_abs=max(0,P0-L)`
- `upward_excursion_pct=100*(H/P0-1)` when `P0>0`
- `downward_excursion_pct=100*(1-L/P0)` when `P0>0`
- log counterparts may be retained for positive prices.

### Requirement: Zero net displacement does not imply zero activity

Start=end may coexist with nonzero path, range, excursions, overlap/activity and volatility. These measurements remain separate.
