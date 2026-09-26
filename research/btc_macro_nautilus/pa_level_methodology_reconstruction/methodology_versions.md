# Methodology versions

Обозначения: **VERIFIED** — следует непосредственно из кода/history; **INFERRED** — интерпретация поведения; **UNRESOLVED** — доказательств недостаточно.

## Сводная таблица

| ID | Versioned source | Candidate / confirmation | Price representation | Lifecycle / hierarchy | Causality |
|---|---|---|---|---|---|
| M1 | `range_sfp_visual_v01.pine` v0.1–v0.3.x in Git | previous D/W/M values; chart pivots/fresh swings | wick extrema / swing price | direct active level, SFP/break handling | closed HTF: causal; pivots: delayed-causal |
| M2 | same file v0.4.0–v0.4.5 | v0.4.0 direct HTF hierarchy; from v0.4.1 raw candidate then reaction gate | original level/candidate price | direct level consumed on touch; relevant survives SFP and retires on clean break | delayed-causal; line may be backdated |
| M3 | `sfp_levels_only*.pine` | HTF pivot(3), optional chart pivot(5), closed D/W/M body | pivot wick; body=max/min(open,close) | active; one-bar reclaim pending; clean break retires | delayed-causal / causal closed-period mix |
| M4 | `sfp_levels_promoted*.pine` | pivot accepted only if move-away gate is already met at appearance; D/W/M bypass in v0.3 | pivot wick / DWM body | active → SFP or broken | delayed-causal |
| M5 | `sfp_candidate_debug.pine`, Python mirror | raw pivot then first move-away ≥ threshold | pivot wick | raw → candidate → SFP/broken retirement | delayed-causal; label backdated |
| M6 | structure/anchor/phase/cluster scripts | confirmed pivot, first minMove, edge/major-zone, reset/phase/cluster rules | pivot wick; cluster representative is same-side extreme | Entry/Internal/Watch/Anchor and rejects | delayed-causal; anchors additionally delayed |
| M7 | `structure_entry_realtime_anchor_v01.pine`; `realtime_structure_sfp_anchor_v01.pine` | transitional pivot+impulse-into; later true current-bar breakout+impulse-into | pivot wick or current high/low | Entry/Watch; SFP; Watch→Anchor | transitional delayed; true realtime causal at close |
| M8 | `sfp_htf_levels_15m_ready_1m_entry.pine` | HTF pivots(20), prior D/W/M wick, 15m readiness pivots/equal levels | extrema; equal pair averaged | HTF break flips S/R; 1m confluence trigger | levels delayed/closed-period; trigger intrabar |
| M9 | `pinescript/dwm_body_levels_v01.pine` | previous closed D/W/M candle | body high/low | delete after later touch | causal from new period open |
| M10 | `pinescript/dwm_levels_origin_projection_v01.pine` | two consecutive closed D/W/M bodies of opposite direction | midpoint of prior open and older close | active until full candle-range cross-through | causal from new period open |
| M11 | `global_local_fib_levels_v01/v04/v05` | opposite confirmed pivot endpoints passing %/ATR/structure gates | impulse endpoints and Fibonacci interpolation | latest/selected global and local impulse | delayed-causal; selection can change later |
| M12 | `major_swing_candidates_debug_v01.pine` | pivot sequence, same-side extreme replacement, ≥18% opposite move | pivot wick; break level from swing leading to later extreme | rebuilt over retained history; global best ≥35% | retrospective for global/break selection |
| M13 | Python v3/v4 dynamic ranges | history before current 4H open | rolling extrema or regression-channel boundaries | recomputed boundary snapshot; no persistent level lifecycle | causal at current bar open |

## M1 — Legacy Range SFP direct levels

**VERIFIED.** Git versions v0.1–v0.3.x precede the candidate/relevance rewrite. The family combines completed higher-timeframe levels with local swing evidence. The retained evolution is:

- v0.1: previous D/W/M wick high/low plus chart pivot levels;
- v0.2: expands display/context filtering while retaining those sources;
- v0.3: setup-qualification flow around previous D/W/M wicks and fresh chart pivots;
- v0.3.1–v0.3.2: entry/reclaim timing and trigger anchoring change, not the base pivot price;
- v0.3.3: explicit untapped D/W/M lifecycle and Swing/Local trigger selection;
- v0.3.4: current-bar event-based sweep/reclaim;
- v0.3.5: D/W/M become context-only by default while current structure is prioritized;
- v0.3.6: explicit level lifecycle, live structure and body-aligned D/W/M context;
- v0.3.7: frozen/validated structure triggers and final-status gating;
- v0.3.8: removes trade-plan generation and remains a structure/body-level/retest/SFP-candidate visualizer.

- HTF closed-period values are knowable only after the period closes.
- A pivot is knowable only after its right-side bars.
- This family is a plausible ancestor of old daily/weekly categories, but no row-level provenance links it to the missing CSV (**UNRESOLVED**).

## M2 — Range SFP relevant reaction levels, v0.4.x

**VERIFIED.** `tradingview/range_sfp_visual_v01.pine` has two distinct v0.4 phases:

- v0.4.0 moves primary discovery to 1H/4H/8H/12H/1D pivots and D/W/M body levels; LTF becomes a reaction/context layer. These direct stored levels are consumed on their first wick touch/cross.
- v0.4.1 adds a separate candidate → Relevant Reaction Level path. v0.4.2 adds explicit broken state, USD/ATR break buffer and 100-USD relevant-zone merge. v0.4.3 gives SFP/reclaim priority over break and simplifies break to close-through. v0.4.4 requires a relevant level to pre-exist the event bar and suppresses non-SFP “relevant” events. v0.4.5 adds source recording and per-source SFP allow flags.

Current v0.4.5 behavior:

- Inputs: HTF pivots from 1H/4H/8H/12H/1D; previous closed D/W/M body extremes; optional local pivots; range/body-cluster candidates.
- Candidate promotion: within a 24-bar reaction window, any of USD move, ATR multiple, percentage move or local-break condition.
- Stored representative: the original candidate price. Duplicate relevant evidence augments naming/context; it does not replace price with a mean/median.
- Lifecycle: candidate expires or becomes relevant; relevant level stays active through SFP events and is retired only by a clean close break. SFP is evaluated only for levels born before the current bar.
- In parallel, the direct HTF/body/LTF display-level array still marks a level past on any touch. It is distinct from the Relevant array.
- Display lines can begin at candidate origin although relevance becomes known later. Backdated drawing is not historical availability.
- Previous ordinary D/W/M wick highs/lows in current v0.4.5 are optional context, not automatically relevant levels.

## M3 — Levels-only HTF pivots + D/W/M bodies

**VERIFIED.** Files:

- `tradingview/sfp_levels_only.pine`
- `tradingview/sfp_levels_only_fixed.pine`
- `tradingview/sfp_levels_only_fixed_v2.pine`
- `tradingview/sfp_levels_visible_test.pine` (earlier visible prototype)

Construction:

- 1H/4H/8H/12H/1D `ta.pivothigh`/`ta.pivotlow`, default pivot length 3;
- optional chart-timeframe pivots, default length 5;
- previous completed D/W/M body high/low, using `max(open, close)` and `min(open, close)`;
- same-side levels inside the merge tolerance are discarded; the earlier stored price remains representative.

Lifecycle:

- same-bar or next-bar close reclaim can mark an SFP;
- a clean close beyond the versioned break buffer retires the level;
- SFP itself does not retire the source level in this family;
- arrays are capped for display/runtime control.

`fixed` and `fixed_v2` are implementation/typing/alert corrections; no evidence of a new construction method was found.

The visible prototype already has the core 1H/4H/8H/12H/1D pivot + closed D/W/M body design, same/next-bar reclaim and clean-break retirement. Its notable defaults are a tighter USD merge tolerance (50) and fixed clean-break buffer (120). It is a versioned precursor, not a separate construction family.

## M4 — Promoted levels-only

**VERIFIED.** Files:

- `tradingview/sfp_levels_promoted.pine`
- `tradingview/sfp_levels_promoted_v03.pine`

v0.2 admits a newly exposed pivot only when move-away is already at least the configured USD/ATR threshold. The check occurs when the pivot value appears; there is no persistent raw candidate waiting indefinitely. v0.3 splits thresholds by source class (1H versus other HTF) and lets D/W/M body levels bypass pivot promotion. Same-side duplicates retain the previously stored representative.

## M5 — Rebound candidate engine

**VERIFIED.** `tradingview/sfp_candidate_debug.pine` stores raw chart/HTF pivots and promotes a raw swing on the first later bar whose move-away reaches the threshold. Candidate/SFP labels may be placed at the pivot origin, but `available_from` is the promotion bar. A promoted candidate retires on a qualifying same/next-bar reclaim or clean break; there is no separate time-expiry rule in the retained version. The script also carries an impulse-state filter; this affects admissibility, not timestamp truth.

`freqtrade/user_data/strategies/SFPCandidateDebugStrategy.py` mirrors the core delayed-pivot construction for resampled 15m data: centered swing recognition is shifted by the right-side window, and exposure occurs at the later 15m timestamp.

## M6 — Structure Entry/Internal/Watch/Anchor family

### Base structure lineage

**VERIFIED.** `tradingview/structure_filter_test.pine` classifies a confirmed pivot after minimum move-away:

- **Entry:** edge swing satisfying the version's eligibility rules;
- **Internal:** a non-duplicate structural reset after sufficient opposite move;
- **Watch:** structurally notable duplicate/edge case that is not immediately Entry;
- rejected/middle/duplicate markers are diagnostic rather than promoted structural levels.

`structure_middle_filter_test.pine` and `structure_middle_clean_test.pine` add a major-range outer-zone filter: pivots in the middle of the larger lookback are rejected/diagnostic.

### Anchor

**VERIFIED.** `tradingview/structure_anchor_test.pine` starts from pivot origin, waits for minimum move, then applies edge/major-zone/reset logic. A latest active same-side Watch can become Anchor only after the configured additional move. The Anchor label is placed at the Watch origin; its causal availability is the later threshold-crossing bar.

### Phase, 1000 and lock

**VERIFIED.** Files:

- `tradingview/structure_anchor_phase_test.pine`
- `tradingview/structure_anchor_phase_1000_test.pine`
- `tradingview/structure_anchor_phase_lock_test.pine`

Phase variants allow at most one Internal per impulse phase, re-armed by a sufficiently large reset from the latest Entry. `_1000` changes the minimum qualifying move from 700 to 1000. `_lock` additionally blocks same-side Entry/Internal until reset unlocks the phase.

### Cluster and cluster fixed

**VERIFIED.** Files:

- `tradingview/structure_anchor_cluster_test.pine`
- `tradingview/structure_anchor_cluster_fixed_test.pine`

Within the cluster tolerance, high-side evidence keeps the highest price and low-side evidence keeps the lowest price. This is an **extreme representative**, not an average or median. Replacement also transfers the current role/type and deletes the superseded label. The fixed version supplies the missing array index in the replacement update and centralizes nearest-cluster lookup; it should be treated as the executable cluster version.

### Structure SFP lifecycle

**VERIFIED.** `tradingview/structure_sfp_test.pine` applies SFP logic only to Entry/Internal. A same-bar or next-bar reclaim and a clean close break are terminal for that active structural instance. Watch/reject diagnostics are not SFP sources.

### EMA-filtered Watch variant

**VERIFIED.** `tradingview/structure_ema_filter_test.pine` keeps the same confirmed-pivot, minimum-move, edge/reset taxonomy. EMA compression/crossing and ordered EMA expansion gate only duplicate-ready **Watch** creation in v0.2; Entry/Internal rules remain ungated. Commit `24e8a05` explicitly corrected the filter to this narrower role. It is a structure-family variant, not a new base level definition.

## M7 — Realtime extrema / impulse-into

`tradingview/structure_entry_realtime_anchor_v01.pine` is a transitional version: despite its name, it still uses confirmed pivots and therefore remains delayed-causal. It adds impulse-into and multi-lookback edge conditions, nearby-level handling and Watch→Anchor behavior.

`tradingview/realtime_structure_sfp_anchor_v01.pine` is the verified no-pivot version:

- candidate originates on the current bar when it makes a new high/low over a backward-only window;
- move into the extreme must satisfy the prior-window impulse threshold;
- near an existing same-side level, a more extreme price upgrades/replaces it; otherwise the new evidence is Watch;
- close reclaim can mark SFP; a Watch can later become Anchor after move-away.

At historical OHLC resolution, creation/SFP is safely treated as known at bar close. Any intrabar alert timing is not reconstructed from OHLC alone.

`tradingview/realtime_persistent_sfp_anchor_v01.pine` is a lifecycle variant of the same causal detector. Entry/Watch persist until explicit close invalidation beyond 600 USD, SFP consumption, or Watch→Anchor conversion. SFP consumes Entry; Anchor never consumes or mutates Entry arrays. This persistence rule materially differs from relying only on new current-bar candidates.

## M8 — HTF confluence/readiness strategy

**VERIFIED.** `tradingview/sfp_htf_levels_15m_ready_1m_entry.pine` combines:

- 1H/4H pivots with large confirmation windows;
- prior D/W/M wick high/low;
- 15m readiness from pivots and equal-high/equal-low pairs, represented by their average;
- HTF close breaks that change support/resistance role;
- 1m sweep/confluence entry logic.

The HTF level set is delayed-causal or closed-period causal. The live 1m trigger is intrabar and cannot be reproduced exactly from bar-close OHLC without tick/alert records.

## M9 — Standalone D/W/M body levels

**VERIFIED.** `pinescript/dwm_body_levels_v01.pine` creates prior completed daily/weekly/monthly body extremes on the first bar of the new period. Duplicate checks are per timeframe and use a 10-tick tolerance. A level is removed on a later touch; the creation bar is excluded from touch deletion. This is the clearest strictly closed-period causal family.

## M10 — Opposite-body D/W/M junction levels

**VERIFIED.** `pinescript/dwm_levels_origin_projection_v01.pine` inspects the two preceding closed periods on D/W/M. If their candle bodies have opposite directions, it creates a level at `(previous_open + older_close) / 2`, stamped to the previous period's time. On lower-timeframe charts the display origin is a moving projection window, but the stored origin timestamp is retained.

Deduplication requires same timeframe, same origin time and price within two ticks; it does not merge different origins. A level is deleted only when a later candle fully straddles it (`low < level < high`), not on equality or close-through. This is closed-period causal at the new-period boundary.

## M11 — Global/local impulse and Fibonacci levels

**VERIFIED.** Files:

- `pinescript/global_local_fib_levels_v01.pine` (indicator identifies the retained code as v0.2);
- `pinescript/global_local_fib_levels_v04_test.pine`;
- `pinescript/global_local_fib_levels_v05_test.pine`.

All use confirmed pivot wick endpoints, so impulse endpoints are delayed-causal. Global defaults use 1D pivot length 5 and a 15% or 5-ATR minimum; local defaults use 4H pivot length 4 and a 1.2% or 2-ATR minimum. The retained v0.2 code additionally requires a new global extreme and constrains the endpoint's position within a 244-day macro range. v0.4 simplifies selection to the latest qualifying opposite-pivot impulse and removes those explicit new-extreme/macro-position gates. v0.5 introduces a local score combining percentage size, ATR size and recency: same-direction replacement needs a 1.15× score; counter-direction replacement needs either 0.60× size or 1.25× score; the local active window defaults to 60 bars. Fibonacci prices are deterministic interpolation/extrapolation from the selected impulse endpoints. Their drawn start time can be the delayed endpoint origin, not availability.

## M12 — Major swing and break-from-lead levels

**VERIFIED.** `pinescript/major_swing_candidates_debug_v01.pine` starts with chart-timeframe pivots (default N=4). Consecutive same-side pivots collapse to the more extreme wick. An opposite pivot becomes a major swing only after at least an 18% move. The global layer searches all retained major pairs and displays the largest bullish/bearish candidate if at least 35%.

The horizontal “break” price is the prior opposite major swing that led to the lowest retained major low or highest retained major high. Individual pivot/major-swing recognition is delayed-causal, but because the global best and lead extreme are rebuilt on `barstate.islast` using later retained pivots, the resulting global/break labels are retrospective. They cannot be assigned to their origin bars as causal levels.

## M13 — Python causal 4H dynamic ranges

**VERIFIED.** `research/btc_macro_nautilus/structure_research/v3/build_structure_research_dataset_v3.py` and the v4 modules implement three rolling 4H boundaries using only history before the current bar open:

- A: rolling high/low extrema;
- B: OLS channel around close with a residual envelope;
- C: separate OLS lines for highs and lows.

In v4, the key implementation is in:

- `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/causal_features.py`
- `research/btc_macro_nautilus/structure_research/v4/structure_research_v4/dynamic_ranges.py`

`candidate_available_at` is the current 4H open after the input history. These are recomputed range boundaries, not persistent structural levels with SFP/break lifecycle.

The duplicate path `research/btc_macro_nautilus/structure_research_v4/` contains a broken builder/test shell, not a second complete implementation.

## Non-executable prior fallback contract

A prior task attachment specifies `minimal_confirmed_1H_4H_N3`: local highs/lows confirmed after three right-side closed bars, available at the close of the third right bar. No matching builder, committed output or manifest was found. This is **VERIFIED as a written contract** and **UNRESOLVED as an executed methodology**.
