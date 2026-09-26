# Canonical Stage 2G slowdown history

Tests whether `S_(i-1)` or `S_(i-2) → S_(i-1)` history adds grouped out-of-sample information beyond the validated Stage 2F slowdown model. The next subsegment contributes outcome direction only. The separate `macro_terminal_exhaustion_stage2g` side experiment is not read or used as a label.

H0 exactly reproduces Stage 2F. H1 preserves previous-subsegment values and validated ratios/z-magnitudes, while a deterministic rank audit prevents algebraically reconstructable fields from being treated as new information. H2 adds the earlier transition and continuous delta-change trajectories. All primary H0/H1/H2 metrics use the identical H2-eligible strong sample and identical leave-one-enclosing-macro-leg-out folds.

Generated artifacts are written outside Git under `research/macro_slowdown_history_stage2g/` in the supplied data root.

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 -m unittest research/btc_macro_nautilus/macro_slowdown_history_stage2g/test_build_stage2g.py
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 research/btc_macro_nautilus/macro_slowdown_history_stage2g/build_stage2g.py --data-root /path/to/data --repo-root /path/to/repo
```
