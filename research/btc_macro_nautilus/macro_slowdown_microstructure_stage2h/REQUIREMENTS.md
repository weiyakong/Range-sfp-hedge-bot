# Stage 2H requirement traceability

| Requirement | Implementation | Artifact | Verification |
|---|---|---|---|
| Frozen Stage 2F population/outcome | `load_population`, population joins | `slowdown_ltf_population.parquet` | population/outcome/boundary QA |
| Exact half-open causal windows | `assign_rows_to_windows`, `select_half_open` | per-TF Parquet | unit test plus representative cross-TF QA |
| Complete-only 15m/5m/3m/1m | sequential TF extraction | population and per-TF Parquet | expected/actual counts and common-sample QA |
| Directional/path/volatility/participation/rate features | `microstructure_features` | per-TF Parquet, feature contract | semantic unit tests and path identities |
| Robust internal trajectories | `robust_slope` Huber M-estimator | per-TF Parquet | deterministic outlier unit test |
| Stage 2F baseline reproduction | `grouped_model` with frozen H0 features | model comparison, QA | exact AUC/balanced-accuracy assertion |
| Fair incremental TF comparison | common strong rows and shared LOGO groups | comparison/bootstrap CSV | common IDs/folds and disjointness QA |
| Redundancy/rank diagnostics | `effective_features`, matrix diagnostics | redundancy report | exact-duplicate/zero-variance audit |
| Interpretation and robustness | grouped univariate bootstrap, families, contexts | interpretation/sensitivity CSV files | checksums and schema audit |
| No leakage/side experiment | predictor allowlists, bounded reads | feature contract, QA | future/side-experiment critical gates |
| Resource safety/current-run identity | union-window reads, TF checkpoints, lease | manifest/checkpoint | resume and concurrent-lease unit tests |
