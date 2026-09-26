# Stage 2F slowdown outcome

This stage compares validated slowdown subsegments (`delta_speed_movement_rate_mean < 0`) before the next-subsegment direction is known. The observation contains only the current subsegment and its inbound transition; the next subsegment contributes only the canonical direction used to define `CONTINUATION` or `REVERSAL`.

The primary population uses strong inbound boundaries. Weak boundaries are written separately as sensitivity evidence. Univariate outputs include Stage 2E raw deltas, validated ratios, and standardized magnitudes. The one multivariate diagnostic is fixed ridge logistic regression with leave-one-macro-leg-out validation; its model matrix uses complete current measures and raw deltas only.

Generated artifacts are written outside Git under the supplied data root:

```text
research/macro_slowdown_outcome_stage2f/
```

Run tests and build:

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 -m unittest research/btc_macro_nautilus/macro_slowdown_outcome_stage2f/test_build_stage2f.py
PYTHONPYCACHEPREFIX=/tmp/codex-pycache python3 research/btc_macro_nautilus/macro_slowdown_outcome_stage2f/build_stage2f.py --data-root /path/to/data --repo-root /path/to/repo
```

After committing the pipeline, update only the manifest commit stamp and checksum index with `--stamp-git-commit COMMIT_SHA`; this does not recompute research results.
