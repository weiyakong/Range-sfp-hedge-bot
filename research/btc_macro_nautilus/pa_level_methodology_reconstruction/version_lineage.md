# Version lineage

This chronology is based on repository Git history. Commit subjects are evidence of intended change; behavior claims were cross-checked against source/diffs where noted.

## Range SFP visual

| Commit | Version/change | Forensic meaning |
|---|---|---|
| `06d4125` | v0.1 | previous D/W/M wick levels + chart pivots |
| `8d878ed`, `e1eb485` | v0.2 | expands/cleans visual context while preserving direct sources |
| `f28339a` | v0.3 | context→zone→SFP→room setup qualifier |
| `4c22f48` | v0.3.1 | earlier reclaim-level entry timing |
| `0f764ef` | v0.3.2 | freezes setup at original reclaim/trigger |
| `b99703d` | v0.3.3 | untapped D/W/M levels; Swing/Local trigger selection |
| `6a481c7` | v0.3.4 | event-based current-bar sweep/reclaim |
| `b90e7cf` | v0.3.5 | D/W/M context-only by default; current structure prioritized |
| `01a87b6` | v0.3.6 | lifecycle state, body-aligned D/W/M, live structure |
| `1b20c24` | v0.3.7 | frozen/validated triggers and final-status gating |
| `0985747` | v0.3.8 | removes trade plans; structure/retest/SFP visualizer |
| `139f14d` | v0.4.0 | primary levels move to HTF pivots/body levels; LTF becomes reaction context; direct levels consumed on touch |
| `1aaca8c` | v0.4.1 | introduces candidate→Relevant after strong reaction |
| `48cc495` | v0.4.2 | explicit broken lifecycle, buffered break, relevant-zone merging |
| `3268140` | v0.4.3 | SFP/reclaim takes priority; close-through break |
| `5b761f6` | v0.4.4 | only pre-existing active relevant levels produce SFP events |
| `15c6735` | v0.4.5 | source diagnostics; current mandatory file |

The first methodological boundary is v0.3.x → v0.4.0: primary discovery moves from chart structure toward HTF pivots/body levels. The second is v0.4.0 → v0.4.1: a separate candidate/promotion/relevant lifecycle is added. v0.4.5 still carries both arrays, with different lifecycles.

## Levels-only and promotion

| Commit | File/version | Change |
|---|---|---|
| `e67c32a` | `sfp_levels_only.pine` v0.1 | base multi-TF pivot + DWM body family |
| `e69bc7b` | fixed | implementation/alert corrections |
| `353290e` | fixed v0.2 | Pine typing/version corrections |
| `23f4aa3` | promoted v0.2 | move-away admission gate |
| `f1f5f1b` | promoted update | DWM handling/default refinement |
| `1ebfb0c` | promoted v0.3 | source-specific gate; DWM bypass |

The fixes do not establish a distinct price methodology. Promotion does.

## Structure taxonomy

| Commit(s) | Change |
|---|---|
| `4d4be8f` | base structure filter |
| `134d446` | internal structure support |
| `c48a747`, `0410f56`, `156afe3`, `9d285d4`, `d1a8f68`, `d4a05db` | duplicate, retest, Watch/Entry semantics evolve |
| `598a1a9` | structure SFP lifecycle |
| `3b5d5e5`, `0a4d3ad`, `d175b7e`, `4328d8f` | major-range middle filtering and cleanup |
| `f757b73` | Watch→Anchor |
| `f528fc5` | impulse phase constraint |
| `aa59629` | 1000 threshold variant |
| `694e199` | phase lock |
| `d8196ec` | clustering |
| `81047c3` | cluster replacement fix |
| `634f735` | transitional “realtime entry + anchor” |
| `36b04dd` | true realtime structure/SFP/anchor family |

Method evolution:

`confirmed pivot → minimum move → Entry/Internal/Watch`

then independently:

- major-range position filters middle swings;
- phase restricts Internal frequency;
- lock prevents repeated same-side structure until reset;
- clustering chooses the more extreme nearby representative;
- Anchor upgrades a Watch only after subsequent move-away;
- realtime version replaces future-confirmed pivots with backward-only current-bar extrema.

## Rebound candidate/debug

| Commit | Change |
|---|---|
| `09a03fd` | initial candidate debug Pine |
| `8341c41` | compile fixes |
| `7089e97` | labels moved back to original raw swing bar; availability does not move back |
| `66c208a` | impulse mode blocks counter-trend candidates |
| `e7f14ea` | stops collecting new counter-trend raw swings during impulse |
| `99816cd` | suppresses counter-trend candidate sweep labels during impulse |
| `5e645c7`, `7f6a5c2` | Freqtrade mirror evolves to 15m levels + 1m triggers |

Across the retained current version, the core temporal contract remains raw delayed pivot followed by later move-away promotion. These display/impulse-state changes must not be mistaken for a new event timestamp.

## Other standalone families

| Commit | Source | Meaning |
|---|---|---|
| `030292b` | `sfp_htf_levels_15m_ready_1m_entry.pine` | HTF levels + 15m readiness + 1m trigger |
| `8f4b7ec` | `dwm_body_levels_v01.pine` | closed D/W/M body family |
| `32548c2`, `a91742a`, `ba0afcf` | same | subsequent fixes |
| `e07b786` | `dwm_levels_origin_projection_v01.pine` | opposite-body junction level with origin projection |

## Additional structural variants

| Commit(s) | Source/change |
|---|---|
| `ee92446` | visible levels-only prototype |
| `ff28d29`, `24e8a05` | EMA-filtered structure; final fix gates Watch only |
| `7c6267e` | persistent realtime Entry/Watch/SFP/Anchor lifecycle |

## Global/local impulse and major-swing lineage

| Commit(s) | Change |
|---|---|
| `81b0d9b`, `c593ed1` | simplified global/local Fib indicator, retained source identifies itself as v0.2 |
| `c3beb08` | v0.4 pivot local impulse and time-based Fib starts |
| `0dfa759` | v0.5 scored local impulse selection |
| `130f41c` | major-swing candidates debug |
| `337eb53` | global candidate layer |
| `e016e5a` | break levels from swings leading to extremes |

The major-swing break layer is retrospective by construction: later extremes determine which earlier pivot becomes the displayed break source.

## Python structure research

| Commit | Change |
|---|---|
| `afc54df` | archives a broken v4 builder shell under `research/` |
| `b0fc00e` | adds tests around that archived shell |
| `bef4b2f` | archives the complete v2/v3/v4 research implementations under `research/btc_macro_nautilus/structure_research/` |

No earlier Git lineage for v2/v3 was found in this repository. Version numbering alone is not proof of an earlier committed builder.

Python lineage is methodologically split:

- v2: canonical/static leg tables and rolling features, not a persistent price-level builder;
- v3: adds causal 4H dynamic range methods A/B/C;
- v4: modularizes causal features/dynamic ranges and explicitly marks retrospective event construction separately.

## Missing lineage

`structural_levels.csv`, an exporter for it, and exact category strings were not found by filename/content search or Git `-S` history. Therefore no commit can be named as the authoritative generation point.
