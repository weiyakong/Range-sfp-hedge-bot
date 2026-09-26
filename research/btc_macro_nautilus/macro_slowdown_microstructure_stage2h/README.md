# Stage 2H slowdown microstructure

This stage keeps the canonical Stage 2F slowdown population and outcome frozen, then measures only complete
canonical 15m, 5m, 3m, and 1m bars inside each half-open slowdown interval. It compares the unchanged Stage 2F
ridge/leave-one-macro-leg-out baseline with one predefined microstructure feature set per timeframe.

The feature contract, current-run QA, manifests, model comparisons, and checksums are written outside Git under
`research/macro_slowdown_microstructure_stage2h/` in the supplied data root. Reads are restricted to the union of
the 210 slowdown windows; extraction is persisted one timeframe at a time.

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 -m unittest \
  research/btc_macro_nautilus/macro_slowdown_microstructure_stage2h/test_build_stage2h.py
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 \
  research/btc_macro_nautilus/macro_slowdown_microstructure_stage2h/build_stage2h.py \
  --data-root /path/to/Range-sfp-hedge-bot-data --repo-root /path/to/repo
```
