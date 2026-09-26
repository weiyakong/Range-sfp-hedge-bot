# Stage 2G terminal exhaustion

Compares each forward terminal push `T` before a direction change with the nearest earlier forward push `P` in the same `enclosing_macro_leg`. The next subsegment contributes direction only; all analytical fields are known by the end of `T`.

The primary analysis uses strong reversal boundaries and reports weak boundaries separately. Price progress and effort use Stage 2E refined components. Exact new-extreme, extension, close-retention, and rejection diagnostics use validated atomic OHLC membership. Feature-wise bull/bear and era sensitivity is reported separately. No late-window rule, adverse-wick aggregation, Elliott label, new indicator family, clustering, or continuation/flag comparison is introduced.

Generated artifacts are written outside Git under `research/macro_terminal_exhaustion_stage2g/` in the supplied data root.

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 -m unittest research/btc_macro_nautilus/macro_terminal_exhaustion_stage2g/test_build_stage2g.py
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 research/btc_macro_nautilus/macro_terminal_exhaustion_stage2g/build_stage2g.py --data-root /path/to/data --repo-root /path/to/repo
```
