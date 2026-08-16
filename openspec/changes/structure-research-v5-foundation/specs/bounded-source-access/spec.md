# Bounded Source Access Contract

## Purpose

Prevent Structure Research v5 from turning small anchor/window/fragment calculations into repeated full-day/full-month source scans, and make source-reader correctness/performance mechanically testable.

## Approved aggTrade access pattern

The approved macro refinement source remains official Binance BTCUSDT `aggTrades` only. Raw individual trades are outside the approved calculation path unless separately explicitly approved.

For each operation:
- candidate refinement requests only its approved candidate window(s);
- canonical 5m boundary-fragment construction requests exactly the full canonical bucket `[B0,B1)` containing the resolved pivot;
- higher-TF boundary composition reuses the resolved 5m fragment plus complete canonical 5m candles and does not rescan aggTrades across the larger TF interval.

## No repeated whole-archive hot-loop reads

Per-anchor, per-candidate and per-fragment loops SHALL NOT repeatedly load/materialize/parse an entire daily or monthly aggTrade archive and then filter it down to the requested interval.

If the physical source is a daily/monthly ZIP/CSV archive, the access layer SHALL stream/filter to the requested time range with bounded memory. Repeated requests for an already-read identical window/bucket within the same pass SHOULD reuse the bounded result.

## Parser requirement

For ZIP/CSV aggTrade archives, the per-window/per-bucket hot path SHALL use a robust streaming CSV parser/filter over the archive member.

`pandas.read_csv`, DataFrame materialization of the entire archive, or an equivalent whole-file parser SHALL NOT be the fragment-stage bucket reader.

A source-reader/parser exception is `source_reader_failure`. It is distinct from market-data absence/incomplete coverage. It SHALL NOT trigger raw individual-trade fallback or silently convert to an empty bucket.

## Exact 5m fragment-source equality

For requested canonical `[B0,B1)`, the returned fragment source rows SHALL be exactly all approved aggTrade rows with `B0 <= event_time < B1`, ordered by `(event_time,agg_trade_id)`. No row outside the bucket may enter; no row inside may be omitted.

The LEFT/RIGHT split then applies the pivot key within that exact returned bucket.

## Instrumentation

The bounded reader SHALL expose enough instrumentation for QA, at minimum where measurable:
- requested start/end;
- source archive/member identity and checksum;
- archive open count;
- scanned row count;
- returned row count;
- bytes scanned/read where available;
- cache hit/miss;
- peak buffered rows/bytes or equivalent bounded-memory evidence;
- parser status.

## Critical QA scenarios

### B01 — One 5m fragment does not materialize a full day/month
Given a large official aggTrade archive and one requested canonical 5m bucket, fragment construction returns exactly the expected bucket rows while instrumentation proves the hot-path operation did not materialize the complete daily/monthly archive.

### B02 — Repeated same-bucket access is bounded
Two fragment requests for the same physical bucket within one pass SHALL NOT require two independent full-archive materializations. Reuse/cache or equivalent bounded access is required.

### B03 — No pandas whole-file fragment parser
Instrumentation/code-path assertion fails if fragment-stage bucket access invokes `pandas.read_csv` or equivalent whole-file DataFrame materialization.

### B04 — Parser failure is not missing data
A synthetic parser failure produces `source_reader_failure`; it does not produce an empty valid bucket, `incomplete_trade_coverage`, or raw-trade fallback.

### B05 — Exact bucket equality
For a fixture with rows immediately before B0, at B0, inside, at B1 and after B1, returned rows are exactly those satisfying `B0 <= event_time < B1`, with timestamp ties ordered by `agg_trade_id`.

## Gate

All applicable B01-B05 tests are critical and SHALL pass before bounded smoke or full-history macro refinement/fragment production is approved.
