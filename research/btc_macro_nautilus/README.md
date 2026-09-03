# BTC macro movement / Nautilus research archive

Status snapshot: 2026-09-03.

## Goal

Use an already-fixed BTC macro-leg structure as the segmentation layer, then collect sufficiently rich raw/derived market data for each movement so that impulse vs correction behaviour can be studied without repeatedly running the expensive collector. The collector must not redefine macro legs or silently repair upstream structure.

## Current state

The macro structure exists. The later Structure Research v4 branch is **not trusted as a finished dataset pipeline**. Work then moved to exact macro-anchor refinement using Binance aggTrades. That refinement stopped with 44 / 138 anchors marked `source_unavailable`, so a final authoritative Nautilus collection was not completed.

## File register

| File / directory | Role | Current status | Known problem / note |
|---|---|---|---|
| `macro_legs_log20.csv` | Approved macro-leg boundaries used as the structural basis. | **AUTHORITATIVE SOURCE, NOT COPIED HERE YET** | Exact approved SHA-256: `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`. Local path: `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_legs_log20.csv`. File contents are not currently accessible to ChatGPT, so no reconstructed substitute was committed. |
| `summary_log20_fibtime_fixed.json` | Summary of the log20/FibTime macro-structure run: parameters, coverage and counts. | **COPIED HERE** | The JSON itself points to a v1 output directory; the later source-transition audit identifies the approved `macro_legs_log20.csv` in v2. Treat the summary as run metadata, not as proof that every referenced output is the approved final copy. |
| `macro_structure_review_log20_fibtime_fixed_local.py` | Script that generated/refined the macro structure using daily + 4H inputs. | **NOT COPIED HERE YET** | Confirmed local path: `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/macro_structure_review_log20_fibtime_fixed_local.py`. Contents are not currently accessible as a complete file. |
| `macro_structure_review_log20_fibtime_fixed_v8_20260718/` | Read-only upstream directory later used by Structure Research v4. | **NOT COPIED HERE YET** | Expected upstream files include `macro_legs_log20.csv`, `movement_segments_log20_fibtime.csv`, `structural_impulses_log20_fibtime.csv`, `corrections_log20_fibtime.csv`, `fibtime_events_log20.csv`. Do not assume these are byte-identical to the approved v2 macro file unless hashes are checked. |
| `build_structure_research_dataset_v2.py` | Earlier research-dataset builder. | **LEGACY / NOT COPIED** | Known earlier run had missing early 4H coverage and boundary mismatches. The full file is not currently extractable without truncation, so it was not copied. |
| `build_structure_research_dataset_v4.py` | Later entrypoint intended to build causal/retrospective research tables. | **COPIED HERE, BROKEN / UNTRUSTED** | Imports a separate `structure_research_v4` package that was not supplied with the entrypoint. `--resume` is parsed but the entrypoint does not use it. After `run_qa()`, it unconditionally sets `qa["final_status"] = "complete_with_known_coverage_limits"`, so status can be misleading. |
| `test_structure_research_v4.py` | Tests for v4 components and smoke integration. | **COPIED HERE, INCOMPLETE AS SAFETY NET** | Depends on the missing `structure_research_v4` package. Existing tests do not prevent the unconditional final-status overwrite in the builder. |
| original v4 Codex specification (`Вставлено файл розмітки .md`) | Requirements for a clean-room Structure Research v4 implementation. | **NOT COPIED HERE YET** | The complete source is available in ChatGPT File Library but extraction is truncated in the current tool surface; committing a partial specification would be unsafe. |
| `macro_legs_source_transition_audit.md` | Audit of the approved macro source around the 2019 spot/futures transition. | **COPIED HERE** | Establishes that Sep-Dec 2019 is mixed-source: spot parent daily rows + futures 4H refinement. |
| `macro_trade_refinement_report.md` | Report from `aggTrades-first, no raw finalize fallback` anchor refinement. | **COPIED HERE** | 138 anchors: 23 exact unique, 71 multiple exact touches, 44 source unavailable; only 46 authoritative 5m boundary fragments. |
| `macro_trade_refinement_anchors.csv` | Per-anchor refinement status/result. | **NOT COPIED HERE YET** | Local path confirmed under `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/`; contents are not currently accessible. |
| `macro_trade_touches.csv` | Preserved exact aggTrade touches for macro anchor prices. | **NOT COPIED HERE YET** | Report says 1320 touch rows. Contents are not currently accessible. |
| `macro_boundary_fragments_5m.csv` | Authoritative 5-minute boundary fragments where anchor localization was sufficiently resolved. | **NOT COPIED HERE YET** | Report says only 46 rows. Contents are not currently accessible. |
| `partial_macro_trade_touches.csv` | Partial/diagnostic refinement data from the same workstream. | **NOT COPIED HERE YET** | Exact contents/path not currently recoverable from accessible files. |
| `partial_source_days.csv` | Partial/diagnostic list of source days used or missing during refinement. | **NOT COPIED HERE YET** | Exact contents/path not currently recoverable from accessible files. |

## Confirmed blocking point

The last confirmed anchor-refinement run processed 138 macro anchors. Results:

- `exact_unique_trade_touch`: 23
- `multiple_exact_trade_touches`: 71
- `source_unavailable`: 44
- preserved touch rows: 1320
- authoritative 5m boundary-fragment rows: 46

The 44 unavailable anchors prevent treating all macro-leg endpoints as being localized to one consistent trade-level standard. This is the point that must be resolved or explicitly accepted with a documented fallback policy before a final expensive Nautilus collection is considered authoritative.

## Rules for continuation

1. Never silently regenerate or modify approved macro legs.
2. Verify the approved macro source by SHA-256 before use.
3. Keep spot/futures provenance explicit, especially around late 2019.
4. Do not treat Structure Research v4's `complete_with_known_coverage_limits` as proof of correctness.
5. Any future data-collection task must point Codex to this GitHub documentation and must write collected data/checkpoints **at least every 20 minutes**.
