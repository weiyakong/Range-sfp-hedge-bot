# Strategy Replication Enforcement V2 remediation plan

Status: implemented; code/test QA passed.

The authoritative production path will be a single atomic runner. It will bind
the actual bars, strategy implementation, configuration, engine code and
result into an execution attestation, validate the persisted artifacts, and
register the run in one project-level transactional state store before issuing
a V2 run receipt.

## Acceptance checkpoints

1. Existing Backtester V2 execution semantics remain unchanged.
2. Production code cannot accept a caller-supplied `BacktestResult`.
3. Actual bars/config/strategy are recorded in an immutable execution attestation.
4. Test evidence is created by an executed subprocess, not a hand-written PASS manifest.
5. Run IDs, freeze identities and protected uses are unique in the canonical store.
6. Persisted output files are parsed and cross-checked before receipt issuance.
7. Stage and QA values are derived from frozen inputs and execution evidence.
8. Legacy V1 receipts are not authoritative execution-attested receipts.
9. All prior regressions and the independent provenance attacks are covered by tests.
