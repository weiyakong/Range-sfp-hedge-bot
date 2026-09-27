# Stage 2I-B1 requirement traceability

| Requirement | Implementation | Output | Verification |
|---|---|---|---|
| Frozen Stage A population | `_load_pivots`, `validate_source_identity` | diagnostics identity columns | unit identity test; independent 4,450-row/ID-order QA |
| Canonical 4H source only | `_load_candles` with manifest SHA256 verification | manifest provenance | source checksum gate; production QA |
| Design A two-sided prominence | `design_a_metrics`, `_path_geometry` | `reference__design_a_*` | unit determinism; distribution/report checks |
| Design A formula sensitivity | minimum/geometric/harmonic fields | diagnostics Parquet | formulation correlations in report |
| Design B hierarchy | `hierarchical_simplification` | removal iteration/scale/reason; long snapshots | monotone/deterministic unit test; independent long-table QA |
| Same-type neighbour handling | `prepare_sequence`, `_more_extreme` | prepass removal reason | concrete fixture test |
| Design C retracement sweep | `_support(..., retracement_ratio)`, `threshold_sweep` | long sweep + survival fraction | exact outgoing/incoming fixture; optimized/direct equivalence test |
| Design C log sweep | `threshold_sweep` | long sweep + survival fraction | exact reproduction test; full rerun |
| Design C volatility sensitivity | `local_volatility_scales`, `threshold_sweep` | local scale/regime/survival | production distributions; independent serialization QA |
| Dual treatment | `prepare_sequence`, `unordered_dual_design_a_metrics` | deferred primary + unordered diagnostics | unit no-order test; zero fabricated transitions in independent QA |
| Cross-design stability | `empirical_rank`, `_metric_comparison` | diagnostics + comparison CSV/Parquet | row/count/correlation checks |
| Time/regime stability | year and volatility summaries | `b1_summary.json` | production report reconciliation |
| 2026 calibration | fixed non-label queries/charts | summary + calibration SVG | count reconciliation; visual QA |
| Six representative charts | `_chart_windows`, `_svg_chart` | six deterministic SVGs | independent SVG validation; local PNG render/visual inspection |
| Reference/postevent namespace | `assert_reference_namespace` | all derived fields | unit rejection test; zero causal fields in independent QA |
| No final binary label / no B2 | output contract and schema | diagnostics/schema/README | independent forbidden-column QA |
| No legacy structural data | source discovery is fixed to Stage A/canonical 4H | manifest | source-string regression test |
| Boundary handling | hierarchy survivor flags | left/right boundary columns | unit edge test; independent unique-boundary QA |
| Deterministic artifacts | deterministic sorting/writers and stable manifest | Parquet/CSV/JSON/SVG/checksums | byte-identical production rerun |
| Atomic writes / progress | `atomic_text`, `.incomplete` promotion, progress stages | `progress.json` | completed checkpoint and checksum gates |
