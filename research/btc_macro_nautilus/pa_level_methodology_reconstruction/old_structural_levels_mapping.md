# Old `structural_levels.csv` mapping audit

## Availability result

**No authoritative copy of `structural_levels.csv` was found.** No manifest, checksum, row sample or committed builder links a historical row to a versioned source. Exact category-string search and Git history search also produced no authoritative match.

This document therefore maps only semantic candidates. It does **not** recreate rows or labels.

## Category mapping

| Old category | Candidate source/method | Mapping basis | Confidence | Status |
|---|---|---|---|---|
| `internal_support_resistance` | M6 Structure Internal/Entry; alternatively M8 broken S/R | semantic role only | low | **UNRESOLVED**: exact string/export absent; methods are materially different |
| `daily_high_low` | M8 prior daily wick; legacy M1 prior D/W/M wick; prior task contract `overlay_levels.csv` | matching timeframe and high/low semantics | medium-low | **INFERRED**: category concept exists, row provenance absent |
| `weekly_high_low` | M8 prior weekly wick; legacy M1; prior task contract | matching timeframe and high/low semantics | medium-low | **INFERRED** |
| `monthly_high_low` | M8 prior monthly wick; legacy M1 | matching timeframe and high/low semantics | low | **UNRESOLVED**: exact string not found; prior overlay contract mentioned only daily/weekly outputs |
| `old_macro_impulse_low` | M11 global/local impulse endpoint; M12 major-swing low/break lineage; completed macro-leg lows in Python canonical research | semantic resemblance only | very low | **UNRESOLVED**: no exact field, exporter or row link |

## Important distinctions

### High/low versus body high/low

Several scripts use previous wick extrema, while `sfp_levels_only*`, promoted v0.3 DWM sources and `dwm_body_levels_v01.pine` use candle-body extrema. A category named `daily_high_low` cannot safely be assumed to mean body high/low. This ambiguity alone can materially change price and touch history.

### Internal structure versus flipped S/R

M6 “Internal” is a classified swing after reset/phase rules. M8 support/resistance can arise from an HTF level after a break. Both could be described informally as internal S/R, but their event definitions, availability and lifecycle are not interchangeable.

### Macro impulse endpoint versus approved macro segment

The Fibonacci scripts define pivot-based impulses with percentage/ATR gates. Major-swing debug constructs percentage-filtered swings and later global extremes. Python canonical research ingests completed macro legs from upstream data. None exposes `old_macro_impulse_low`, so none is a justified automatic mapping.

## Prior contract evidence

A prior local task attachment requested two outputs:

- `overlay_levels.csv` with daily/weekly body and high/low levels from closed periods;
- `structural_levels.csv`, falling back to confirmed 1H/4H local highs/lows with N=3 right bars if no old builder existed.

This is evidence of an intended contract, not evidence that the fallback ran or that any currently discussed old CSV came from it. No generated output, code implementation or manifest was located. The fallback must therefore remain **UNRESOLVED**.

## Conditions that would resolve provenance

Any one of the following could materially improve the mapping:

- the original `structural_levels.csv` plus checksum/manifest;
- a builder path and Git commit SHA;
- several rows including category, price, event timestamp and availability timestamp;
- a run log naming the Pine/Python version and parameters;
- an external archived branch containing the exporter.

Until then, the old categories should not be used as authoritative labels or features.
