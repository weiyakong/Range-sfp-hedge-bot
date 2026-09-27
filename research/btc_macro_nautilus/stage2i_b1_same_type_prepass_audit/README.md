# Stage 2I-B1 Same-Type Prepass Sensitivity Audit

## Purpose

This module implements the sensitivity audit for the Stage 2I-B1 same-type prepass rule.
The audit tests:
1. Whether the deterministic rule (consecutive HIGH keeps higher, consecutive LOW keeps lower) safely eliminates micro-fluctuations or prematurely destroys independent price movements.
2. The empirical distribution of realized departures for all 924 removed events.
3. The impact of excluding dual HIGH+LOW outside candles, which causes adjacent same-type candidates to collapse across the dual boundary.
4. A dual-aware alternative prepass (Variant B) where dual candles act as structural barriers/separators.
5. An alternative representation (Variant C) where same-type removals are marked as `excluded_from_alternating_sequence = True` without assigning structural scale 0.
6. The sensitivity of the Design B hierarchy across multiscale thresholds (0.5% through 25%), confirming whether the prepass impacts local/micro structure or medium/major coarse turns.

## Structure

- `build_stage2i_b1_prepass_audit.py`: Production and smoke execution script.
- `validate_stage2i_b1_prepass_audit.py`: Independent validation script verifying checksums, schema, counts, monotonicity, and invariants.
- `test_build_stage2i_b1_prepass_audit.py`: Unit test suite.
- `README.md`: This file.

## Execution

```bash
# Run unit tests
python3 test_build_stage2i_b1_prepass_audit.py

# Run audit
python3 build_stage2i_b1_prepass_audit.py --mode prod

# Validate artifacts
python3 validate_stage2i_b1_prepass_audit.py --mode prod
```

## Policy Constraints

- Does not select a canonical B1 reference contract.
- Does not change the status of same-type prepass to FIXED.
- Does not modify canonical methodology in `PA_STRUCTURE_CANONICAL.md`.
- Does not produce live/causal signals, zones, or indicators.
