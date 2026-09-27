# Stage 2I-B1 — retrospective structural reference research

This package compares three transparent offline representations of the frozen Stage 2I-A raw 4H pivot sequence:

1. two-sided realized prominence with minimum, geometric-mean and harmonic formulations;
2. a deterministic alternating-sequence removal hierarchy with complete removal scale/depth;
3. reversal-scale sweeps using relative retracement, log-price movement and a trailing 42-bar median-true-range sensitivity normalization.

The primary sequence defers all dual HIGH+LOW candles. A separate unordered diagnostic preserves both extrema and measures their two-sided support only against strictly earlier/later opposite non-dual pivots. No same-bar temporal order is invented.

All realized-path values are explicitly `reference__*` or `postevent__*`. They are offline research diagnostics, not causal Stage 2I-B2 features. The implementation does not create a MICRO/INDEPENDENT label or choose a final B1 reference contract.

Generated datasets and charts are written outside Git to:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/research/stage2i_b1_retrospective_reference/`

Run unit tests, smoke, production and independent QA with the commands recorded in the research report.
