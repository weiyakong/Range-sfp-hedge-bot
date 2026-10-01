# Strategy Replication Enforcement — execution provenance remediation

## Authority change

`RUN_RECEIPT_V1` is legacy and cannot be issued or validated as production
authority. `RUN_RECEIPT_V2` is issued only by the atomic production runner.

## Closed architectural gaps

- The production API cannot accept a caller-supplied result, strategy object,
  run ID, preflight context, or state/index path.
- The exact bar objects consumed by V2 are hashed and must match the data
  manifest's hash, start, end and count; symbol, market, timeframe and timestamp
  semantics are attested as the same contract.
- The same cloned config object is used for preflight, execution and output.
- The canonical hash of every config field must match the frozen strategy spec;
  the contract is not limited to fees/slippage protocol fields.
- The strategy is loaded from the locked file/symbol and instantiated with the
  frozen parameter mapping.
- The test-suite hash is frozen in the strategy spec. Tests are executed by a
  subprocess; structured successes, exit status, suite hash and output hashes
  are recorded, and every required test method must actually pass.
- `result.json` is canonical. All CSVs, metrics and exposure are reread and
  compared to its deterministic reconstruction before receipt issue.
- Output symlinks and incomplete/extra artifact sets are rejected.
- Stage and QA dimensions are copied into the execution attestation and must
  remain identical during revalidation.
- A fixed SQLite state store provides transactional uniqueness for run IDs,
  variant identities and protected-data use.
- Revalidation opens that store read-only and rehashes every upstream input,
  the test suite, all execution-critical code and the recorded Git commit.
- Registry predecessor records are immutable by identity; state decisions,
  exit precedence, ranking metric references and strategy exceptions are strict.

## Deliberate human-review boundary

The runner proves execution provenance and deterministic artifact consistency.
It does not prove that prose was interpreted correctly, that arbitrary Python
contains no look-ahead, or that the candidate universe is complete. Production
metadata therefore retains `HUMAN_REVIEW_REQUIRED` for causality unless a later
separately specified review authority is introduced.

## Requirement traceability

| Requirement | Implementation | Authoritative output | Regression coverage | Status |
|---|---|---|---|---|
| Runner owns execution | `run_production_research` | `result.json`, attestation | caller cannot supply result/strategy/run ID | PASS |
| Exact data identity | `canonical_bars_sha256`, `_data_contract` | attested bar hash/count/window | altered OHLCV/window and data-contract tests | PASS |
| Exact config identity | `canonical_config_sha256` | config and payload hashes | slippage and non-protocol config-field tests | PASS |
| Frozen strategy/tests | `_load_strategy`, `_run_test_suite` | structured test evidence | changed/failing suite and strategy-drift tests | PASS |
| Semantic output integrity | `_validate_semantic_outputs` | exact V2 manifest set | malformed CSV, stage/QA and symlink tests | PASS |
| Global run/use continuity | `_reserve_run`, `_complete_state` | canonical SQLite record | duplicate protected use and missing-state tests | PASS |
| Receipt provenance | `validate_v2_run_receipt` | `RUN_RECEIPT_V2` | receipt/upstream mutation tests | PASS |
| Strict frozen contracts | validators in `validation/core.py` | freeze/preflight reports | nested fields, states, metrics, exceptions, predecessor tests | PASS |
| V1 authority removal | disabled V1 issue/validate entrypoints | explicit validation error | legacy receipt regression tests | PASS |

## Verification

- Backtester V2: 76/76 tests PASS.
- Strategy-replication enforcement: 68/68 tests PASS.
- Differential execution reference: 15/15 execution classes match audited commit.
- Execution-critical capability hashes: 8/8 match.
- Package import, CLI startup, syntax compilation and `git diff --check`: PASS.
- Static type checker: NOT CONFIGURED in this repository; no dependency was added.
- Real-data production smoke: NOT RUN because no approved strategy/data/freeze bundle
  was supplied for this remediation, and synthetic fixtures must not be published as research.
