# Causality audit

## Timestamp contract

For every reconstructed method, three moments must be separated:

- `event_time`: price bar on which the swing/extreme visually occurred;
- `confirmation_time`: first bar at which the defining condition is confirmed;
- `available_from`: first timestamp at which a downstream model could legally consume the level.

Normally `available_from >= confirmation_time`. A Pine label or line whose x-coordinate is moved back to `event_time` does not alter this inequality.

## Audit table

| Method | event_time | confirmation_time | available_from | Future dependency | Verdict |
|---|---|---|---|---|---|
| Confirmed pivot | pivot origin | close of Nth right bar | confirmation close or next executable timestamp | N right-side bars | delayed-causal |
| Pivot + move-away | pivot origin | later of pivot confirmation and threshold hit | threshold-hit close | right bars + later price path | delayed-causal |
| Pivot + immediate promotion gate | pivot origin | bar on which pivot becomes visible and gate passes | that bar close | right bars | delayed-causal |
| Watch→Anchor | Watch origin | later anchor move threshold | anchor-confirmation close | subsequent price path | delayed-causal; commonly backdated |
| Phase reset/lock | original pivot | pivot qualification plus prior reset state | classification bar close | no future beyond availability | causal state machine after delayed pivot |
| Cluster replacement | new pivot origin | new member qualification | replacement bar close | new pivot right bars | delayed-causal; old representative changes only then |
| Closed D/W/M body | prior period | new period boundary | first bar of new period | none after period close | causal |
| Previous D/W/M wick | prior period | new period boundary | first bar of new period | none after period close | causal |
| Opposite-body D/W/M junction | previous/older closed periods | new period boundary | first bar of new period | none after period close | causal |
| Backward-only realtime extrema | current bar | current bar close for OHLC research | after close | none | causal at bar close |
| Major-swing lead-break label | earlier leading pivot | only after later retained global extreme is known | latest rebuild time | later pivot sequence/extreme | retrospective |
| Python 4H dynamic range | historical window | current 4H open | current 4H open | history excludes current bar | causal |
| 1m intrabar trigger | current 1m bar | tick-dependent | live tick/alert time | not future, but path unavailable in OHLC | not exactly reproducible from bar close |
| Completed macro-leg event fractions | historical leg interior | only once enclosing leg/end is known | after leg completion | future leg completion | retrospective |

## Pine-specific findings

### `lookahead_off` does not remove pivot delay

All `request.security(... ta.pivothigh/low(...), lookahead=barmerge.lookahead_off)` families avoid explicit HTF lookahead, but the pivot still needs right-side bars. Correct model ingestion must stamp the level at the returned/confirmation bar, not at the offset pivot origin.

Affected mandatory files include all `sfp_levels_only*`, `sfp_levels_promoted*`, `structure_*` pivot variants, `structure_anchor_*`, `sfp_candidate_debug.pine`, `range_sfp_visual_v01.pine` pivot sources and `sfp_htf_levels_15m_ready_1m_entry.pine`.

### Backdated promotion/relevance

`range_sfp_visual_v01.pine` may draw a promoted relevant line beginning at candidate origin. Its stored relevant creation bar is later and is the proper availability stamp.

`sfp_candidate_debug.pine` similarly labels the originating pivot when move-away later promotes it. The origin is descriptive, not causal availability.

### Anchor backdating

Anchor variants label the earlier Watch price/bar only after a later move threshold. Treating Anchor status as present at the Watch origin is direct leakage.

### Fibonacci and major-swing redrawing

Global/local Fibonacci endpoints are delayed pivots. v0.5 may replace the selected local impulse when a later score/size condition wins. Major-swing global/break levels are selected from the retained sequence on the last bar. Their historic line origin is not a valid availability timestamp.

### Same/next-bar SFP

When scripts allow same-bar or next-bar reclaim, historical OHLC establishes the outcome no earlier than the bar close. It does not establish whether an intrabar consumer could have acted before close unless tick ordering is retained.

## Python-specific findings

### Causal modules

In v4, `causal_features.py` slices history strictly before the current bar, and `dynamic_ranges.py` computes range boundaries from that history. This supports `available_from=current_open`.

### Retrospective modules

`events.py` explicitly marks generated structure events `is_causal=False`. `canonical.py` and `relationships.py` operate on upstream completed macro legs and containment/previous-leg relationships. These products are useful for retrospective analysis but cannot be silently converted into online structural levels.

### Archived duplicate

`research/btc_macro_nautilus/structure_research_v4/` is incomplete relative to the package under `research/btc_macro_nautilus/structure_research/v4/`. Its presence does not prove an independent historical run or a second authoritative source.

## Common leakage modes

1. Joining a pivot by its origin timestamp instead of confirmation timestamp.
2. Treating a visually backdated promoted/Anchor label as available at origin.
3. Replacing a cluster representative historically instead of only from replacement time onward.
4. Using completed macro-leg direction/end/fractions as online features.
5. Reconstructing intrabar reclaim/break ordering from OHLC when both occurred in the same candle.
6. Treating a previous-period level as known before that period closed.

## Minimum safe contract for any future reuse

Every level row would need at least:

`level_id, method_version, source_timeframe, event_time, confirmation_time, available_from, price, side, lifecycle_state, state_changed_at, supersedes_level_id, builder_commit`

This is a forensic recommendation only; no such dataset was created in this audit.
