# Strategy Replication Enforcement V1 — Remediation QA

> Historical V1 remediation record. A later independent review found that V1
> did not bind caller-supplied results to actual execution. See
> `REMEDIATION_V2_REPORT.md`; V1 receipts are no longer authoritative.

Baseline: `d12c22d1fba8f412ba8fbdecfe6f5edc538940cb` on `backtester-v2`.

## Finding closure

| Finding | Fixed | Enforcement / regression evidence |
|---|---:|---|
| CR-01 opt-in production gate | Yes | Opaque preflight context required by metadata builder and output writer; A69/A70 |
| CR-02 protocol not bound to run | Yes | Stage-specific window plus semantic effective-config equality before publication and after run; A61 |
| CR-03 replaceable capability | Yes | Canonical path/content, real Git repo/origin/base ancestor, controlled module hashes and IDs; A45–A49 |
| CR-04 empty/forged lineage | Yes | Writer-owned exact output set, checksums, Git/code/data/config/metric revalidation; A62–A68 |
| CR-05 testing/protected bypass | Yes | Registry predecessor, identity index, research-use ledger, frozen finalists/data/window, repeat rejection |
| CR-06 SOURCE_RANGE/proxy bypass | Yes | Numeric range/time checks and bidirectional controlled proxy contract; A09–A12 |
| CR-07 self-attested tests/traces | Yes | Executed test-result identity, PASS IDs, suite hash, code path/symbol/hash checks; A14/A15 |
| CR-08 overloaded VERIFIED | Yes | Five independent QA dimensions; non-production aggregate is `NON_PRODUCTION` |
| MJ-01 inactive schema contract | Yes | Python validator is sole authority; inactive JSON Schema sketches removed |
| MJ-02 NOT_USED false positive | Yes | Metadata is conditionally omitted/null; fake placeholders are rejected |
| MJ-03 cross-document integrity | Yes | Intake/source/fidelity/spec/parameter/predecessor continuity checks |
| MJ-04 vacuous state graph | Yes | Non-empty declared pairs and complete decisions required |
| MJ-05 data-contract binding | Yes | Authoritative/per-input/output manifest identities cross-checked |
| MJ-06 metrics/receipt integrity | Yes | Canonical metric IDs/formula versions plus revalidatable run receipt |

## Attack matrix

`retained` means the independent audit found the control already behaved
correctly; remediation regression suites keep it green. `rejected` means a
previously accepted invalid case is now blocked.

| Attack | Before | After | Regression test |
|---|---|---|---|
| A01 | retained | retained | `FreezeAttackTests.test_01_*` |
| A02 | retained | retained | `FreezeAttackTests.test_02_*` |
| A03 | retained | retained | `FreezeAttackTests.test_03_*` |
| A04 | retained | retained | `FreezeAttackTests.test_04_*` |
| A05 | retained | retained | `FreezeAttackTests.test_05_*` |
| A06 | retained | retained | `FreezeAttackTests.test_06_*` |
| A07 | retained | retained | `FreezeAttackTests.test_07_*` |
| A08 | retained | retained | `FreezeAttackTests.test_08_*` |
| A09 | accepted invalid range | rejected | `test_A09_A10_A11_source_range_bounds_and_time` |
| A10 | accepted inverted range | rejected | `test_A09_A10_A11_source_range_bounds_and_time` |
| A11 | accepted future selection | rejected | `test_A09_A10_A11_source_range_bounds_and_time` |
| A12 | accepted proxy mismatch | rejected | `test_A12_proxy_contract_is_bidirectional` |
| A13 | accepted empty state map | rejected | `test_A13_A15_A17_state_trace_and_exit_contracts` |
| A14 | accepted nonexistent trace/test | rejected | `test_A14_nonexistent_trace_and_required_test` |
| A15 | accepted duplicate Rule ID | rejected | `test_A13_A15_A17_state_trace_and_exit_contracts` |
| A16 | accepted data hash mismatch | rejected | `test_A16_A32_A33_A34_cross_document_integrity` |
| A17 | accepted enforceable exit contradiction | rejected | `test_A13_A15_A17_state_trace_and_exit_contracts` |
| A18 | retained fidelity control | retained | `test_target_market_transfer_is_computed` |
| A19 | retained fidelity control | retained | `test_unsupported_stop_entry_is_blocked` |
| A20 | retained fidelity control | retained | `test_05_proxy_plus_pure_fails` |
| A21 | retained parameter control | retained | `test_same_variant_identity_cannot_freeze_different_parameters` |
| A22 | retained candidate control | retained | `test_10_candidate_absent_from_registry_fails` |
| A23 | retained duplicate-ID control | retained | enforcement suite registry validation |
| A24 | retained missing-parent control | retained | enforcement suite registry validation |
| A25 | retained chronology control | retained | enforcement suite registry validation |
| A26 | retained status-history control | retained | enforcement suite registry validation |
| A27 | retained frozen-hash control | retained | `test_12_frozen_spec_mutation_invalidates_receipt` |
| A28 | retained exact-byte control | retained | `test_12_frozen_spec_mutation_invalidates_receipt` |
| A29 | retained fidelity downgrade | retained | `test_13_favorable_execution_exception_requires_downgrade` |
| A30 | retained data allowlist | retained | `test_06_forbidden_input_use_fails` |
| A31 | retained ambiguity block | retained | `test_07_material_unresolved_ambiguity_fails` |
| A32 | accepted intake/spec inversion | rejected | `test_A16_A32_A33_A34_cross_document_integrity` |
| A33 | accepted source mismatch | rejected | `test_A16_A32_A33_A34_cross_document_integrity` |
| A34 | accepted variant/fidelity mismatch | rejected | `test_A16_A32_A33_A34_cross_document_integrity` |
| A35 | accepted negative weights | rejected | `test_A35_A36_A37_A38_A39_A40_A41_protocol_values` |
| A36 | accepted nonnumeric weights | rejected | same |
| A37 | accepted non-unit weights | rejected | same |
| A38 | accepted duplicate metric | rejected | same |
| A39 | accepted unknown metric | rejected | same |
| A40 | accepted invalid fee | rejected | same |
| A41 | accepted non-finite/out-of-domain cost | rejected | same |
| A42 | accepted post-hoc protected identity | rejected | `test_A42_A43_protected_and_ranking_identity_are_frozen` |
| A43 | accepted post-hoc ranking | rejected | same |
| A44 | retained canonical capability content | retained | `test_capability_manifest_matches_execution_engine` |
| A45 | accepted forged base commit | rejected | `test_A45_A46_A47_capability_identity` |
| A46 | accepted forged manifest version | rejected | same |
| A47 | accepted invented capability | rejected | same |
| A48 | retained unsupported-capability block | retained | `test_unsupported_stop_entry_is_blocked` |
| A49 | accepted external engine/manifest path | rejected | `test_A49_external_capability_path_and_A57_fake_repo` |
| A50 | accepted forged freeze Git identity | rejected | `test_A50_A51_A52_A53_A54_A56_receipt_claims` |
| A51 | accepted forged backtester identity | rejected | same |
| A52 | accepted future receipt timestamp | rejected | same |
| A53 | accepted malformed unresolved counts | rejected | same |
| A54 | accepted PASS receipt with errors | rejected | same |
| A55 | retained byte-mutation detection | retained | `test_12_frozen_spec_mutation_invalidates_receipt` |
| A56 | accepted forged preflight commit | rejected | `test_A50_A51_A52_A53_A54_A56_receipt_claims` |
| A57 | accepted fake repo | rejected | `test_A49_external_capability_path_and_A57_fake_repo` |
| A58 | retained strategy requirement control | retained | freeze/enforcement suite |
| A59 | accepted missing code lock | rejected | `test_A59_strategy_code_lock_required_at_freeze` |
| A60 | engine status overstated causality | explicit human-review boundary | QA-dimension assertions in production integration |
| A61 | accepted wrong run window | rejected | `test_A61_window_A63_dirty_and_config_binding` |
| A62 | accepted metadata/data mismatch | rejected | `test_A62_A64_A65_A66_A67_A68_post_run_identity_and_outputs` |
| A63 | accepted dirty material code | rejected | `test_A61_window_A63_dirty_and_config_binding` |
| A64 | accepted forged commits | rejected | `test_A62_A64_A65_A66_A67_A68_post_run_identity_and_outputs` |
| A65 | accepted invented code hashes | rejected | same |
| A66 | accepted capability-version mismatch | rejected | same |
| A67 | accepted missing outputs | rejected | same |
| A68 | ignored unexpected output | rejected | same |
| A69 | external output bypassed preflight | rejected before write | `test_A69_A70_external_production_output_requires_gate` |
| A70 | ungated output claimed VERIFIED | no output; non-production is explicit | same |

## QA and trust boundary

Production metadata records `engine_integrity`, `data_fidelity`,
`methodology_preflight`, `execution_fidelity`, and `causality_assurance`.
Production may proceed with `HUMAN_REVIEW_REQUIRED`, but this state is never
presented as formal proof of no look-ahead. Arbitrary Python semantic causality,
source interpretation, and candidate-universe completeness remain human review.

## Verification commands

- V2: `python3 -m unittest discover -s research/backtester_v2/tests -v`
- Enforcement/adversarial/differential:
  `python3 -m unittest discover -s research/strategy_replications/tests -v`

The differential test loads the pre-enforcement reference directly from Git and
compares 15 execution classes. Engine execution semantics are unchanged.
