# Evidence index

All line references describe the audited checkout at commit `889e193` before these documentation changes. Git-history evidence is addressed by commit SHA because older line numbers are not stable.

## Mandatory Pine sources

| Source | Key evidence |
|---|---|
| `tradingview/structure_anchor_test.pine` | inputs 17–24; stored state 61–79; pivot origin/edge 155–168; classification 170–231; Watch→Anchor 233–275 |
| `tradingview/structure_anchor_cluster_test.pine` | cluster contract 4–8; active-near lookup 113–123; replacement logic from 160 |
| `tradingview/structure_anchor_cluster_fixed_test.pine` | corrected lookup/replacement and indexed extrema update 75–120 |
| `tradingview/structure_anchor_phase_test.pine` | one-Internal-per-phase contract 4–8; phase state/classification in main pivot block |
| `tradingview/structure_anchor_phase_lock_test.pine` | lock contract 4–8; state 74–82; reset/unlock 161–164; locked classification 189–264 |
| `tradingview/structure_anchor_phase_1000_test.pine` | variant statement 4–6; threshold/configuration near input block |
| `tradingview/realtime_structure_sfp_anchor_v01.pine` | no-pivot contract 4–8; current-extrema construction 91–150; SFP 153–168; Watch→Anchor 169–208 |
| `tradingview/structure_sfp_test.pine` | structure/SFP scope 4–7; pivot classification 187–250; lifecycle 252–294 |
| `tradingview/sfp_levels_only.pine` | duplicate/store 81–112; HTF pivots 137–192; DWM bodies 194–226; lifecycle 236–280 |
| `tradingview/sfp_levels_only_fixed.pine` | same method; fixed implementation/alerts verified by Git diff |
| `tradingview/sfp_levels_only_fixed_v2.pine` | same method; Pine v6/type corrections verified by Git diff |
| `tradingview/sfp_levels_promoted.pine` | move-away gate and promoted admission in source-specific add blocks |
| `tradingview/sfp_levels_promoted_v03.pine` | split thresholds 17–20; `requirePromotion` behavior 54–75; DWM bypass in add blocks |
| `tradingview/sfp_htf_levels_15m_ready_1m_entry.pine` | HTF/DWM levels 47–63; 15m pivots/equal levels 65–77; S/R and entry logic below |
| `tradingview/range_sfp_visual_v01.pine` | inputs 35–62; storage 120–154; candidate/relevant arrays 170–242; HTF pivots 255–322; DWM bodies 324–360; context wick levels 362–374; local candidates 376–394; touch 396–408; range/body clusters 410–432; promotion 434–452; relevant lifecycle 454–501 |

## Additional version-defining Pine sources

| Source | Relevance |
|---|---|
| `tradingview/structure_filter_test.pine` | base current structure taxonomy; inputs 10–14; pivot/edge 117–125; classification 127–179 |
| `tradingview/structure_middle_filter_test.pine` | adds major-range/outer-zone eligibility |
| `tradingview/structure_middle_clean_test.pine` | cleaned middle-filter implementation |
| `tradingview/structure_entry_realtime_anchor_v01.pine` | transitional variant that still uses pivots around 89–100 |
| `tradingview/sfp_candidate_debug.pine` | raw→candidate contract 4–8; promotion 192–210; candidate lifecycle below |
| `tradingview/sfp_levels_visible_test.pine` | early levels-only defaults 4–14; HTF pivots 87–120; DWM bodies 122–140; lifecycle 150–184 |
| `tradingview/structure_ema_filter_test.pine` | EMA regime 19–42; same structure state 46–147; Watch-only EMA gate 146–186 |
| `tradingview/realtime_persistent_sfp_anchor_v01.pine` | persistence contract 4–7; current-bar detector 95–153; SFP/invalidation 155–195; Anchor 197–236 |
| `pinescript/dwm_body_levels_v01.pine` | closed-period/delete-on-touch contract 4–8; previous DWM values 31–40 |
| `pinescript/dwm_levels_origin_projection_v01.pine` | storage/dedup 55–108; cross-through lifecycle 131–143; closed DWM inputs and body-junction price 145–168 |
| `pinescript/global_local_fib_levels_v01.pine` | retained v0.2 global/local pivot impulse rules 18–217 |
| `pinescript/global_local_fib_levels_v04_test.pine` | global/local pivot impulses and Fib derivation 34–144 |
| `pinescript/global_local_fib_levels_v05_test.pine` | thresholds 10–25; score/replacement 36–140; Fib outputs 162–192 |
| `pinescript/major_swing_candidates_debug_v01.pine` | thresholds 4–13; alternation/extreme replacement 53–110; retrospective global/break selection 158–242; last-bar rebuild 244–296 |

## Python sources

| Source | Key evidence |
|---|---|
| `research/btc_macro_nautilus/structure_research/v2/build_structure_research_dataset_v2.py` | canonical/static leg features; no persistent structural price-level exporter found |
| `research/btc_macro_nautilus/structure_research/v3/build_structure_research_dataset_v3.py` | 4H range methods/config 2788–2829; A/B/C construction 2832–2965; availability assignment around 2918 |
| `research/btc_macro_nautilus/structure_research/v4/build_structure_research_dataset_v4.py` | upstream load 71–78; written output set 204–224; no `structural_levels.csv` |
| `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/causal_features.py` | history exclusion and availability 42–112 |
| `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/dynamic_ranges.py` | methods A/B/C 19–149 |
| `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/events.py` | retrospective event flag and construction 6–42 |
| `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/canonical.py` | upstream macro-leg/segment canonicalization 16–71 |
| `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/relationships.py` | containment/previous relationships 26–86 |
| `freqtrade/user_data/strategies/SFPCandidateDebugStrategy.py` | centered/shifted pivot recognition 117–128; 15m resampling 148–193; later exposure 195–207 |
| `research/btc_macro_nautilus/structure_research_v4/` | incomplete archived builder/test shell; not equivalent to full package |

## Git evidence

Key commits and methodological boundaries are catalogued in [version_lineage.md](version_lineage.md). Content searches included:

- exact old category strings;
- `structural_levels.csv` and `overlay_levels.csv`;
- builder/output references;
- Git `-S` searches across all refs available locally;
- filenames under the project and related research-data root.

No authoritative old file/exporter match was found.

## External local evidence

Prior task contract:

`/Users/yeshevika/.codex/attachments/15828b9c-e09f-4a4c-a9c4-ad8f43b0d580/pasted-text.txt`, especially lines 36–164.

It specifies intended overlay outputs and an N=3 fallback, but it is not source code or execution proof.

## Coverage checklist

- [x] all 15 mandatory Pine files inspected
- [x] Python v2/v3/v4 and duplicate archived v4 inspected
- [x] candidate, confirmation, price representation recorded
- [x] clustering/merge representative recorded
- [x] rebound/promotion logic recorded
- [x] lifecycle and hierarchy recorded
- [x] event/confirmation/availability separated
- [x] old category mapping confidence recorded
- [x] missing provenance explicitly reported
- [x] no research dataset or new level calculation created
