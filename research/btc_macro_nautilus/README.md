# BTC macro movement / Nautilus research archive

Status snapshot: 2026-09-03.

## Goal

Use an already-fixed BTC macro-leg structure as the segmentation layer, then collect sufficiently rich raw/derived market data for each movement so that impulse vs correction behaviour can be studied without repeatedly running the expensive collector. The collector must not redefine macro legs or silently repair upstream structure.

## Search scope used for this archive completion

Filesystem search was run across `/Users/yeshevika/Documents/Codex/` with the required keywords:

- `macro_structure_review_log20`
- `macro_legs_log20`
- `structure_research`
- `macro_trade_refinement`
- `macro_trade_touches`
- `macro_boundary_fragments`
- `partial_source_days`
- `fibtime_fixed`
- `aggfirst`

Confirmed source runs used by this archive update:

- `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/`
- `/Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/`
- `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/`

## Archive layout

New byte-preserved imports were added under:

- `research/btc_macro_nautilus/macro_structure/v2/`
- `research/btc_macro_nautilus/macro_structure/v8/`
- `research/btc_macro_nautilus/trade_refinement/aggfirst/`
- `research/btc_macro_nautilus/structure_research/v2/`
- `research/btc_macro_nautilus/structure_research/v3/`
- `research/btc_macro_nautilus/structure_research/v4/`
- `research/btc_macro_nautilus/FILE_MANIFEST.csv`

Earlier archive-era files remain in their original legacy locations (`audits/`, `macro_structure/summary_log20_fibtime_fixed.json`, `structure_research_v4/`) so prior branch history stays readable.

## Authoritative macro structure decision

The approved macro structure remains:

- `research/btc_macro_nautilus/macro_structure/v2/macro_legs_log20.csv`
- SHA-256: `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`
- Original local path: `/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_legs_log20.csv`

Observed comparison result:

- `macro_structure/v8/macro_legs_log20.csv` has the same SHA-256: `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`
- This proves the archived v8 copy is byte-identical to the approved v2 file.
- This does **not** change the documentation rule that v2 is the approved authoritative designation and v8 is a later upstream directory.

## Current state after archival completion

The archive now contains the missing approved macro output set, the original macro-structure generator script, the `aggTrades-first` trade-refinement result set, the previously missing `structure_research_v4/` package, and the key v2/v3/v4 structure-research scripts plus QA/failure metadata.

## Confirmed blocking point for further Nautilus work

The last confirmed trade-level anchor-refinement run stopped here:

- total macro anchors: 138
- `exact_unique_trade_touch`: 23
- `multiple_exact_trade_touches`: 71
- `source_unavailable`: 44
- preserved trade touches: 1320
- authoritative 5m boundary fragments: 46

The blocking issue is unchanged: 44 macro anchors still lack resolved trade-level source coverage, so a final authoritative Nautilus collection still needs either:

- missing-source recovery for those anchors, or
- an explicit written fallback policy accepting incomplete trade-level localization.

## What is authoritative vs usable now

- Authoritative now: `macro_structure/v2/macro_legs_log20.csv`
- Authoritative but partial: `trade_refinement/aggfirst/macro_boundary_fragments_5m.csv`
- Working but not authoritative: most companion v2/v8 macro outputs and trade-refinement result tables
- Legacy: `structure_research/v2/*` and `structure_research/v3/*`
- Broken / untrusted as finished pipeline: `structure_research/v4/build_structure_research_dataset_v4.py`

## Newly discovered inconsistencies

1. Earlier archive text said the `structure_research_v4` package was missing. Filesystem search on 2026-09-03 found the original package at `/Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/`, and it has now been archived under `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/`. The old flat archive copy at `research/btc_macro_nautilus/structure_research_v4/build_structure_research_dataset_v4.py` therefore reflects an outdated availability assessment.
2. Earlier archive text warned not to assume `macro_structure_review_log20_fibtime_fixed_v8_20260718/macro_legs_log20.csv` matched the approved v2 file. SHA verification on 2026-09-03 shows both files are byte-identical: `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3`. This resolves the equality question, but does not change the authoritative designation rule.
3. The original aggfirst refinement report was already represented in legacy form at `research/btc_macro_nautilus/audits/macro_trade_refinement_report.md`, but the original source file actually lives at `/Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/macro_trade_refinement_report.md`. That original byte-preserved file is now also archived under `research/btc_macro_nautilus/trade_refinement/aggfirst/`.

## Files required to continue the project now

Minimum files another Codex/ChatGPT run should use first:

- `research/btc_macro_nautilus/README.md`
- `research/btc_macro_nautilus/FILE_MANIFEST.csv`
- `research/btc_macro_nautilus/macro_structure/v2/macro_legs_log20.csv`
- `research/btc_macro_nautilus/audits/macro_legs_source_transition_audit.md`
- `research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_refinement_anchors.csv`
- `research/btc_macro_nautilus/trade_refinement/aggfirst/macro_boundary_fragments_5m.csv`
- `research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_refinement_report.md`

If someone attempts to reuse Structure Research v4, they must also inspect:

- `research/btc_macro_nautilus/structure_research/v4/build_structure_research_dataset_v4.py`
- `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/`
- `research/btc_macro_nautilus/structure_research/v4/run_20260726/structure_research_qa_v4.json`
- `research/btc_macro_nautilus/structure_research/v4/run_20260726/failure_report.json`

## Machine-readable manifest

Per-file machine-readable metadata is in `research/btc_macro_nautilus/FILE_MANIFEST.csv`.

## Per-file register for files added in this archival completion

The table below records, for every located/imported file:

- source local path
- role/purpose
- project stage
- status class (`authoritative` / `working` / `legacy` / `diagnostic` / `broken`)
- known problems
- dependencies
- whether the file is usable now
- SHA-256 of the original file
- whether the file was modified during transfer (`NO` for every imported file)

| GitHub path | Source local path | Purpose | Stage | Status | Authoritative | Usable now | Known problems | Dependencies | SHA-256 | Modified on transfer |
|---|---|---|---|---|---|---|---|---|---|---|
| research/btc_macro_nautilus/macro_structure/v2/macro_legs_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_legs_log20.csv | Approved macro-leg boundaries. | macro_structure_v2 | authoritative | YES | YES | Mixed-source Sep-Dec 2019 provenance remains and is documented separately. | Consumed by downstream structure and Nautilus research. | `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3` | NO |
| research/btc_macro_nautilus/macro_structure/v2/movement_segments_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/movement_segments_log20_fibtime.csv | Movement segmentation derived from approved legs. | macro_structure_v2 | working | NO | YES | Only meaningful together with the same run inputs and approved legs. | Depends on macro_legs_log20.csv and same run outputs. | `43944a22ae2e22903e19e63f23900f7b9eab7319d9f342bd46ee2ed8335c4c5f` | NO |
| research/btc_macro_nautilus/macro_structure/v2/structural_impulses_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/structural_impulses_log20_fibtime.csv | Impulse classification artifacts for macro movements. | macro_structure_v2 | working | NO | YES | Interpret only with same-run segmentation. | Depends on movement_segments_log20_fibtime.csv. | `d043d48bc417a27c1a917f571013dcc3a0239c4a781c8926ff006c84f15c82eb` | NO |
| research/btc_macro_nautilus/macro_structure/v2/corrections_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/corrections_log20_fibtime.csv | Correction classification artifacts for macro movements. | macro_structure_v2 | working | NO | YES | Interpret only with same-run segmentation. | Depends on movement_segments_log20_fibtime.csv. | `8d93dfd1b030c89c0acd9c62ada8a3e5db67ac31a905f6f06b97c13620285f52` | NO |
| research/btc_macro_nautilus/macro_structure/v2/fibtime_events_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/fibtime_events_log20.csv | FibTime event markers used in the run. | macro_structure_v2 | working | NO | YES | Run-specific derived events; not a standalone authority. | Depends on macro structure run state. | `557725d1622f17b8e1f43475ddd5981eafa5d9914273f99af530879854de4c21` | NO |
| research/btc_macro_nautilus/macro_structure/v2/macro_events_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_events_log20.csv | Macro event table emitted by the approved run. | macro_structure_v2 | working | NO | YES | Run-specific derived events; not a standalone authority. | Depends on macro structure run state. | `3f7dd68fe13197b50811f197176a0e80832fb575c894d4e255248ccbeb5f4fb4` | NO |
| research/btc_macro_nautilus/macro_structure/v2/market_regime_log20_fibtime_daily.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/market_regime_log20_fibtime_daily.csv | Daily regime labels used in v2 outputs. | macro_structure_v2 | working | NO | YES | Regime labels are run metadata, not the approved macro-leg authority. | Depends on daily market-regime processing in the same run. | `3ff48630c6b138ed116d569d51538f7f07ed3a9001a80c915dfd4fafc523cc8a` | NO |
| research/btc_macro_nautilus/macro_structure/v2/market_regime_log20_fibtime_events.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/market_regime_log20_fibtime_events.csv | Regime transition events for v2. | macro_structure_v2 | working | NO | YES | Diagnostic/derived view of regime processing. | Depends on regime segmentation in the same run. | `0107553fda4776094e0df065c8ab869330da7823d73f7d06beda9cde7fb654cf` | NO |
| research/btc_macro_nautilus/macro_structure/v2/market_regime_log20_fibtime_segments.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/market_regime_log20_fibtime_segments.csv | Regime segment table for v2. | macro_structure_v2 | working | NO | YES | Diagnostic/derived view of regime processing. | Depends on regime segmentation in the same run. | `8b1b1cbf687b8b634ef3d0d723512664a1cd5dfa314aaad63fde27198874482f` | NO |
| research/btc_macro_nautilus/macro_structure/v2/summary_log20_fibtime_fixed.json | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/summary_log20_fibtime_fixed.json | Run summary and parameter metadata. | macro_structure_v2 | working | NO | YES | JSON still references a v1 output directory, so it is metadata only. | Depends on macro structure run context. | `520ad8fed53c7eff69134d1a564c91d9d2403ec01932e7d516e0a04c275dd60e` | NO |
| research/btc_macro_nautilus/macro_structure/v2/macro_structure_review_log20.html | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_structure_review_log20.html | Human review HTML for macro structure. | macro_structure_v2 | diagnostic | NO | YES | Review artifact only; not a machine-readable source of truth. | Opens against bundled assets only. | `1ea6803605880025dc24fa3414ecbaa7f47cf28fde691a89fe541c6b25977891` | NO |
| research/btc_macro_nautilus/macro_structure/v2/macro_structure_with_market_regime_log20_fibtime_fixed.html | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v2_20260718/macro_structure_with_market_regime_log20_fibtime_fixed.html | Combined visual review of structure plus regime overlay. | macro_structure_v2 | diagnostic | NO | YES | Review artifact only; not a machine-readable source of truth. | Opens against bundled assets only. | `768587d073806a6d3fbf61ba4ea2a3618adb3e7f1d7e79038c16645d4da5d91f` | NO |
| research/btc_macro_nautilus/macro_structure/v8/macro_legs_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/macro_legs_log20.csv | Later upstream macro-leg file used by Structure Research v4. | macro_structure_v8 | working | NO | YES | Not separately designated as approved, even though its SHA matches the approved v2 file. | Consumed by later structure-research work. | `c7f7166a72f57ee9af75ddc0d5711d45d8371b546d83c10cdc77bc129523d0d3` | NO |
| research/btc_macro_nautilus/macro_structure/v8/movement_segments_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/movement_segments_log20_fibtime.csv | Later upstream movement segmentation. | macro_structure_v8 | working | NO | YES | Later upstream output, not the approval artifact itself. | Depends on v8 macro structure run outputs. | `43944a22ae2e22903e19e63f23900f7b9eab7319d9f342bd46ee2ed8335c4c5f` | NO |
| research/btc_macro_nautilus/macro_structure/v8/structural_impulses_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/structural_impulses_log20_fibtime.csv | Later upstream impulse classification output. | macro_structure_v8 | working | NO | YES | Later upstream output, not the approval artifact itself. | Depends on v8 movement segmentation. | `d043d48bc417a27c1a917f571013dcc3a0239c4a781c8926ff006c84f15c82eb` | NO |
| research/btc_macro_nautilus/macro_structure/v8/corrections_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/corrections_log20_fibtime.csv | Later upstream correction classification output. | macro_structure_v8 | working | NO | YES | Later upstream output, not the approval artifact itself. | Depends on v8 movement segmentation. | `8d93dfd1b030c89c0acd9c62ada8a3e5db67ac31a905f6f06b97c13620285f52` | NO |
| research/btc_macro_nautilus/macro_structure/v8/fibtime_events_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/fibtime_events_log20.csv | Later upstream FibTime event output. | macro_structure_v8 | working | NO | YES | Later upstream output, not the approval artifact itself. | Depends on v8 run state. | `557725d1622f17b8e1f43475ddd5981eafa5d9914273f99af530879854de4c21` | NO |
| research/btc_macro_nautilus/macro_structure/v8/macro_events_log20.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/macro_events_log20.csv | Later upstream macro event table. | macro_structure_v8 | working | NO | YES | Later upstream output, not the approval artifact itself. | Depends on v8 run state. | `3f7dd68fe13197b50811f197176a0e80832fb575c894d4e255248ccbeb5f4fb4` | NO |
| research/btc_macro_nautilus/macro_structure/v8/market_state_candidate_diagnostics_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/market_state_candidate_diagnostics_log20_fibtime.csv | Candidate diagnostics for v8 market-state logic. | macro_structure_v8 | diagnostic | NO | YES | Diagnostic artifact only. | Depends on v8 state-generation logic. | `2980f1391df9adbaab5cb615727e4eeea2c95d81a82cc589c2bf1e4652aad24e` | NO |
| research/btc_macro_nautilus/macro_structure/v8/market_state_log20_fibtime_daily.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/market_state_log20_fibtime_daily.csv | Daily state labels for v8. | macro_structure_v8 | working | NO | YES | State labels are upstream metadata, not final macro-leg authority. | Depends on v8 state-generation logic. | `2a2a6cc061c42c4c772560dacd5003f43a699a7416f7470cd61a2c1bf947c996` | NO |
| research/btc_macro_nautilus/macro_structure/v8/market_state_log20_fibtime_events.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/market_state_log20_fibtime_events.csv | Market-state transition events for v8. | macro_structure_v8 | working | NO | YES | Derived state event view only. | Depends on v8 state-generation logic. | `945a4848712a2d05a538f7bb78f1366ce671ea739396fbde28eea3c658a2c2b9` | NO |
| research/btc_macro_nautilus/macro_structure/v8/market_state_log20_fibtime_segments.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/market_state_log20_fibtime_segments.csv | Market-state segmentation for v8. | macro_structure_v8 | working | NO | YES | Derived state segment view only. | Depends on v8 state-generation logic. | `848d576b7547d2078c708e6ec93cc040a1252ca0d326e734565ba5d631dfd6af` | NO |
| research/btc_macro_nautilus/macro_structure/v8/structural_regime_segments_log20_fibtime.csv | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/structural_regime_segments_log20_fibtime.csv | Structural regime segmentation output for v8. | macro_structure_v8 | working | NO | YES | Later upstream output, not an approval artifact. | Depends on v8 run state. | `7f782848a1ba33198a36ebccb6162b15e6112561de502fd7f0c0d958121ce5cb` | NO |
| research/btc_macro_nautilus/macro_structure/v8/summary_log20_fibtime_fixed.json | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/summary_log20_fibtime_fixed.json | Run summary and parameter metadata for v8. | macro_structure_v8 | working | NO | YES | Summary metadata only. | Depends on v8 run context. | `ddd974d3f64c52146aeea7f5699e9bdd3c011b40498da7ee9090fcdde2baa974` | NO |
| research/btc_macro_nautilus/macro_structure/v8/macro_structure_review_log20.html | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/macro_structure_review_log20.html | Human review HTML for v8 macro structure. | macro_structure_v8 | diagnostic | NO | YES | Review artifact only. | Opens against bundled assets only. | `1ea6803605880025dc24fa3414ecbaa7f47cf28fde691a89fe541c6b25977891` | NO |
| research/btc_macro_nautilus/macro_structure/v8/macro_structure_with_market_regime_log20_fibtime_fixed.html | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/macro_structure_review_log20_fibtime_fixed_v8_20260718/macro_structure_with_market_regime_log20_fibtime_fixed.html | Combined visual review for v8. | macro_structure_v8 | diagnostic | NO | YES | Review artifact only. | Opens against bundled assets only. | `f18d37107e6c9261064d80eff24ed3c0e57caca3298e06c0fdd7ecaf7f0ab0a4` | NO |
| research/btc_macro_nautilus/macro_structure/macro_structure_review_log20_fibtime_fixed_local.py | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/macro_structure_review_log20_fibtime_fixed_local.py | Script that generated/refined the log20/FibTime macro structure. | macro_structure_generation | working | NO | NO | Should not be rerun to redefine approved legs without explicit provenance review. | Requires the original daily/4H upstream inputs and local Python environment. | `4ad5b38f7388b9b61048e0e744e03efe98c612cf351371759e1ee51797131185` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_refinement_anchors.csv | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/macro_trade_refinement_anchors.csv | Per-anchor refinement results and statuses. | trade_refinement_aggfirst | working | NO | YES | Run stopped with 44/138 anchors source_unavailable. | Depends on approved macro anchors and Binance aggTrades provenance. | `5822eab8c6b12499202aaf2d486204374b5cc77073d7d6d00e37c27e8506fce4` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_touches.csv | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/macro_trade_touches.csv | Preserved exact aggTrade touches for anchor prices. | trade_refinement_aggfirst | working | NO | YES | Not complete coverage for all anchors. | Depends on refinement anchor search and aggTrades inputs. | `a3f03c28f0e02732295bf3af02198de2c4d83d3d6916c3827477693a77e9fc45` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/macro_boundary_fragments_5m.csv | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/macro_boundary_fragments_5m.csv | Resolved authoritative 5m boundary fragments. | trade_refinement_aggfirst | authoritative | YES | YES | Only 46 rows were authoritative; coverage is partial. | Depends on successful refinement of boundary-localized anchors. | `bbd860dd258fd4558b897bd9cede51406f8457107b63cf7e9acb7f7145f1a15f` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/partial_macro_trade_touches.csv | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/partial_macro_trade_touches.csv | Partial/diagnostic touch results from incomplete refinement. | trade_refinement_aggfirst | diagnostic | NO | NO | Incomplete by design. | Depends on refinement debugging flow. | `5b63f79d38a4cbd5149d02128266295477379b1cf4439cafb270a0ed22bc914b` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/partial_source_days.csv | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/partial_source_days.csv | Partial/diagnostic source-day inventory. | trade_refinement_aggfirst | diagnostic | NO | NO | Incomplete by design. | Depends on refinement debugging flow. | `efa09bc7a688a8b255a8cb2c21167139d13c6ff9aea2ff0e678307f7e2a43460` | NO |
| research/btc_macro_nautilus/trade_refinement/aggfirst/macro_trade_refinement_report.md | /Users/yeshevika/Documents/Codex/2026-08-16/files-pasted-by-the-user-read/outputs/macro_trade_refinement_aggfirst/macro_trade_refinement_report.md | Narrative report for aggTrades-first refinement. | trade_refinement_aggfirst | working | NO | YES | Documents unresolved 44-anchor source gap. | Depends on the refinement CSV outputs in the same directory. | `977233062ffad948a382ed978538fe2cb7d1ac60a946eea2a02a31e067ba2484` | NO |
| research/btc_macro_nautilus/structure_research/v2/build_structure_research_dataset_v2.py | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/build_structure_research_dataset_v2.py | Builds the v2 structure research dataset. | structure_research_v2 | legacy | NO | NO | Earlier documentation reports missing early 4H coverage and boundary mismatches. | Depends on macro structure outputs and original raw market data. | `9113d9d01898f6bf4536e7c1f0818499531f208245a54d23e371873b690355db` | NO |
| research/btc_macro_nautilus/structure_research/v2/run_20260718/structure_research_qa_v2.json | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/structure_research_dataset_v2_20260718/structure_research_qa_v2.json | QA report for the v2 structure research dataset. | structure_research_v2 | diagnostic | NO | NO | QA belongs to the legacy v2 dataset lineage. | Depends on the v2 dataset build output. | `bd27f22dbea84fb3c39b08b150cb348dc26f2eee7075eda56c33c78e7f3eef0f` | NO |
| research/btc_macro_nautilus/structure_research/v2/run_20260718/structure_research_summary_v2.json | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/outputs/structure_research_dataset_v2_20260718/structure_research_summary_v2.json | Summary metadata for the v2 structure research dataset. | structure_research_v2 | diagnostic | NO | NO | Summary belongs to the legacy v2 dataset lineage. | Depends on the v2 dataset build output. | `5eb083e52cf3ce1845149c89c6f0921996f4d9ed320f8f34bc3cdba9ee0ca5d9` | NO |
| research/btc_macro_nautilus/structure_research/v3/build_structure_research_dataset_v3.py | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/build_structure_research_dataset_v3.py | Builds the v3 structure research dataset attempt. | structure_research_v3 | legacy | NO | NO | Superseded by later work and not documented as a trustworthy final pipeline. | Depends on macro structure outputs and the original local Python environment. | `8cc1e2778ae2f8d8b21e3b2f7690f08cc7f066ef7fa294784633c3fe21dc30d9` | NO |
| research/btc_macro_nautilus/structure_research/v3/test_structure_research_v3.py | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/test_structure_research_v3.py | Tests/smoke checks for the v3 dataset attempt. | structure_research_v3 | legacy | NO | NO | Superseded by later work and not documented as a trustworthy final pipeline. | Depends on macro structure outputs and the original local Python environment. | `d7e59b6799773d4193c0091f005373fdab4dc412d18c5f08de6008161c0c8f38` | NO |
| research/btc_macro_nautilus/structure_research/v3/render_structure_research_v3_html.py | /Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/render_structure_research_v3_html.py | Renders HTML review output for v3 research data. | structure_research_v3 | legacy | NO | NO | Superseded by later work and not documented as a trustworthy final pipeline. | Depends on macro structure outputs and the original local Python environment. | `d975f7ef422a2efe8b5954cc4633b6c82648257c6ea514b8ff7f41ecc6a17d50` | NO |
| research/btc_macro_nautilus/structure_research/v4/build_structure_research_dataset_v4.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/build_structure_research_dataset_v4.py | Main entrypoint for the v4 structure research dataset. | structure_research_v4 | broken | NO | NO | Entry point remains untrusted as a finished dataset pipeline. | Depends on the structure_research_v4 package and upstream macro/raw data. | `0aba779aa3024f211e185a05faade62472cb58bd918275c5ef6b6ea67406537d` | NO |
| research/btc_macro_nautilus/structure_research/v4/render_structure_research_v4_html.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/render_structure_research_v4_html.py | Renderer for v4 HTML inspection outputs. | structure_research_v4 | working | NO | NO | Useful for inspection, but the underlying v4 dataset lineage is not authoritative. | Depends on v4 outputs and local Python environment. | `323192349d909fc76746bd8db8504c50c60e093cfe1469404c6ae84832642f4c` | NO |
| research/btc_macro_nautilus/structure_research/v4/test_structure_research_v4.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/test_structure_research_v4.py | Tests and smoke checks for the v4 codepath. | structure_research_v4 | diagnostic | NO | NO | Existing tests do not make the overall v4 pipeline trustworthy. | Depends on the structure_research_v4 package and test fixtures. | `477758e96172b6b316cfc590ffab081a149ecaa28ffbb42b9acae000095ef161` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/__init__.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/__init__.py | Package initializer for v4 support code. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `167699b3fa54993b5b58e6bc891de10420ce61a4830dd24c81ec2866efc80809` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/canonical.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/canonical.py | Canonicalization helpers for v4 dataset construction. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `f223f62952ae87e8e33d3e8a60055fd5ba92eebf9798595e6f39670832088908` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/causal_features.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/causal_features.py | Causal feature generation helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `30f942124a53924d19a95c00da1b970d6ddb29d55f76e74c93e36849f9f48cfc` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/checkpoint.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/checkpoint.py | Checkpoint/resume helpers for v4 processing. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `455244e64d94e3b0858e2766778b4f8d4cd992dbd52a63c4c5222fee5ae28337` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/config.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/config.py | Configuration objects and defaults for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `6db84add04d18e7e25f59fbcfab509e54d16abfa207550cb9f7d08bdac370dd1` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/decision_support.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/decision_support.py | Decision-support feature helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `1ddecfc8ae6c320e1d85c810380edd50d24d2e6a4df75227ae0964be587c00d8` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/dynamic_ranges.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/dynamic_ranges.py | Dynamic range calculations for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `1b75c643d6aaad996e17af532c14db31913fa91919f097d542e613426d048325` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/events.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/events.py | Event extraction helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `89f1180aa59576dcf57a7e811998cabcbee68fc2e4e4c520e74b96b3c7a7316d` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/excursions.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/excursions.py | Excursion metrics/helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `9276407e3aaf8bf62c18907eae3dfb1ff880ee408c7aa26d6ac3a238f62c5985` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/fibtime.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/fibtime.py | FibTime-related helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `2cd401ca0e0784ab4f66a6c715f3070e0c86fa16a7689a886d404e11ed5859e9` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/io.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/io.py | I/O helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `b221b31a918d1370a3ae67e3df6dd8e4b02ff828217289f2acd7c8962a037188` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/qa.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/qa.py | QA helpers for v4 output validation. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `566a158dede87e04cb3727d82f8b77cb71f8fdec476810c025a638573353b3e4` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/relationships.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/relationships.py | Relationship-building helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `910ca5cf5f1c0cca20b2adb0ff9d2af03b1be9e5e8eb398a0204515cb6574c93` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/schemas.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/schemas.py | Schema definitions for v4 outputs. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `f310ca9c86efe6a564acf73fa3ee7e5fcc1503f6b8117682665b548d097c9643` | NO |
| research/btc_macro_nautilus/structure_research/v4/structure_research_v4/source_discovery.py | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/structure_research_v4/source_discovery.py | Source discovery/provenance helpers for v4. | structure_research_v4 | working | NO | NO | Package exists, but the overall v4 pipeline is still not accepted as authoritative. | Imported by build/test/render v4 scripts in the same directory. | `25b6a33385db0f296dc093f7b3b1318026ebc46545fd9fb1e1b0ad57916fa943` | NO |
| research/btc_macro_nautilus/structure_research/v4/run_20260726/structure_research_qa_v4.json | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/outputs/structure_research_dataset_v4_20260726/structure_research_qa_v4.json | QA report for the 2026-07-26 v4 dataset run. | structure_research_v4 | diagnostic | NO | NO | QA belongs to an untrusted v4 dataset lineage. | Depends on the 2026-07-26 v4 dataset output. | `4ea45e22cfcf27d188d0ed2961c5f468e83ce47bd9721f23f4a52995aca5da8f` | NO |
| research/btc_macro_nautilus/structure_research/v4/run_20260726/failure_report.json | /Users/yeshevika/Documents/Codex/2026-07-26/files-mentioned-by-the-user-codex/outputs/structure_research_dataset_v4_20260726/failure_report.json | Failure report for the 2026-07-26 v4 dataset run. | structure_research_v4 | diagnostic | NO | NO | Failure report documents unresolved pipeline issues rather than a clean final run. | Depends on the 2026-07-26 v4 dataset output. | `93344c1299ce6759596d75eddcfb587736f35739e2cc6ac6dd73cd148533ea65` | NO |

## Continuation rules

1. Never silently regenerate or modify approved macro legs.
2. Verify the approved macro source by SHA-256 before use.
3. Keep spot/futures provenance explicit, especially around late 2019.
4. Do not treat Structure Research v4 outputs or status strings as proof of correctness.
5. Preserve checkpoint discipline: any future long-running collection/archive task must write results at least every 20 minutes.
