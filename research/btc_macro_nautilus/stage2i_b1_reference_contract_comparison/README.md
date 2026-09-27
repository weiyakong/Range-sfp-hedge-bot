# Stage 2I-B1 — Reference Contract Comparison

Research code and test suite for Stage 2I-B1 retrospective structural reference representations under the fixed B+C candidate-preservation contract.

## Methodological Guardrails
- **Fixed Contract**: Stage 2I-A raw 4H pivots, causal availability semantics, B1/B2 dual-layer separation, B+C candidate-preservation policy.
- **Segment-Aware Architecture**: Dual candles act as structural barriers/separators. Hierarchy does not bridge across dual boundaries.
- **Candidate Preservation**: Technical same-type exclusions from the alternating sequence are preserved with provenance and assigned `scale = None` (no semantic scale 0 or micro label).
- **Hard Separation**: No retrospective structural reference fields leak into live or causal predictors.
- **No Canonical Selection**: Canonical B1 contract remains OPEN. `PA_STRUCTURE_CANONICAL.md` is strictly unmodified.

## Components
- `build_stage2i_b1_comparison.py`: Main deterministic pipeline producing master reference, sequence reference, continuous/ordinal/confidence representations, contract comparison, parameter sensitivity, temporal stability, volatility sensitivity, ambiguity diagnostics, 2026 calibration, schemas, manifest, checksums, and representative SVG charts.
- `validate_stage2i_b1_comparison.py`: Strict validation script checking population invariants, special states, manifest checksums, and schema consistency.
- `test_stage2i_b1_comparison.py`: Unit test suite covering all 13 required test specifications.

## Execution
```bash
# Smoke run
python3 build_stage2i_b1_comparison.py --mode smoke

# Production build
python3 build_stage2i_b1_comparison.py --mode production

# Validation
python3 validate_stage2i_b1_comparison.py --artifact-dir /path/to/artifacts

# Tests
python3 test_stage2i_b1_comparison.py -v
```
