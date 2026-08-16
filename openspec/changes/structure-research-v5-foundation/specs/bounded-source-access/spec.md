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

Per-anchor, per-candidate and per-fragment loops SHALL NOT repeatedly load, materialize, or sequentially parse an entire daily/monthly aggTrade archive and then filter it down to the requested interval.

When multiple requested windows/buckets belong to the same physical archive during one refinement/finalize pass, the access layer SHALL amortize archive access. It SHALL use one of these equivalent bounded patterns:
- one sequential streaming pass over the archive that dispatches rows to all requested windows/buckets for that archive;
- a validated index/offset/range-access structure that permits direct bounded reads;
- a restart-safe bounded cache produced by an earlier validated pass and keyed by source checksum plus exact requested interval.

It is NOT acceptable to reopen or rescan the same whole daily/monthly archive once per different 5m bucket merely because each individual call returns only one bucket.

A previously returned identical bucket/window within the same pass SHALL be reused rather than reread from the physical archive unless the cached result failed validation.

## Parser requirement

For ZIP/CSV aggTrade archives, the per-window/per-bucket hot path SHALL use a robust streaming CSV parser/filter over the archive member or a validated bounded cache/index produced by such a pass.

`pandas.read_csv`, DataFrame materialization of the entire archive, or an equivalent whole-file parser SHALL NOT be the fragment-stage bucket reader or per-anchor source reader.

A source-reader/parser exception is `source_reader_failure`. It is distinct from market-data absence/incomplete coverage. It SHALL NOT trigger raw individual-trade fallback, silently convert to an empty bucket, or be reclassified as `incomplete_trade_coverage`.

## Exact 5m fragment-source equality

For requested canonical `[B0,B1)`, the returned fragment source rows SHALL be exactly all approved aggTrade rows with `B0 <= event_time < B1`, ordered by `(event_time,agg_trade_id)`. No row outside the bucket may enter; no row inside may be omitted.

The LEFT/RIGHT split then applies the pivot key within that exact returned bucket.

## Candidate-window equality

For a reviewed localization candidate `[C0,C1)`, the returned refinement rows SHALL be exactly all approved aggTrade rows with `C0 <= event_time < C1`, subject only to explicit source-coverage failure. Off-grid source-localization windows use the same half-open rule.

## Memory bound

Source-access memory SHALL scale with parser buffering plus the requested/result windows being retained, not with the total uncompressed archive size. If one streaming archive pass serves many requested buckets, completed bucket results SHALL be emitted/persisted or held in a bounded cache rather than accumulating the complete archive in memory.

## Instrumentation

The bounded reader SHALL expose enough instrumentation for QA, at minimum where measurable:
- requested start/end;
- source archive/member identity and checksum;
- archive open count;
- full/archive sequential scan count;
- scanned row count;
- returned row count;
- bytes scanned/read where available;
- cache/index hit/miss;
- peak buffered rows/bytes or equivalent bounded-memory evidence;
- parser status.

Instrumentation SHALL distinguish `archive_open_count`, `archive_scan_count`, and logical bucket/window request count so repeated rescans cannot be hidden behind a narrow returned result.

## Critical QA scenarios

### B01 — One 5m fragment does not materialize a full day/month
Given a large official aggTrade archive and one requested canonical 5m bucket, fragment construction returns exactly the expected bucket rows while instrumentation proves the operation did not materialize the complete daily/monthly archive in memory.

### B02 — Repeated same-bucket access is reused
Two requests for the same physical bucket within one pass SHALL reuse the validated bounded result or equivalent index lookup. They SHALL NOT cause two physical archive scans.

### B03 — No pandas whole-file fragment parser
Instrumentation/code-path assertion fails if fragment-stage bucket access invokes `pandas.read_csv` or equivalent whole-file DataFrame materialization.

### B04 — Parser failure is not missing data
A synthetic parser failure produces `source_reader_failure`; it does not produce an empty valid bucket, `incomplete_trade_coverage`, or raw-trade fallback.

### B05 — Exact bucket equality
For a fixture with rows immediately before B0, at B0, inside, at B1 and after B1, returned rows are exactly those satisfying `B0 <= event_time < B1`, with timestamp ties ordered by `agg_trade_id`.

### B06 — Different buckets in one archive do not cause repeated whole-archive scans
Given multiple requested 5m buckets/candidate windows from the same physical daily/monthly archive in one pass, all requested results SHALL be produced by a single shared sequential archive scan, validated indexed access, or validated restart-safe cache. A design that performs one whole-archive sequential scan per requested bucket fails this test even if every individual returned bucket is correct.

### B07 — Memory remains bounded during shared archive pass
A fixture with many requested buckets from one large archive SHALL demonstrate that peak retained parser/source rows are bounded and do not approach total archive row count merely to service those requests.

## Gate

All applicable B01-B07 tests are critical and SHALL pass before bounded smoke or full-history macro refinement/fragment production is approved.
