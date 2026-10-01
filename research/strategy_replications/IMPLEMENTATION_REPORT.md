# Strategy Replication Enforcement Layer V1 — Implementation Report

## Phase 1 design check

Starting point: branch `backtester-v2`, commit
`2b096ebf52928248ad2e608be685bef37a7d6887`, clean worktree, 73 existing
Backtester V2 tests passing.

The implementation is intentionally small:

1. JSON Schema files define the portable structured contracts.
2. Standard-library Python validators enforce the research-specific invariants
   that JSON Schema alone cannot express.
3. A capability manifest is bound to the audited V2 execution engine by the
   SHA-256 of `engine.py` and the audited base commit.
4. A freeze receipt is written only after all spec, registry, protocol, data,
   capability, test, fidelity, and hash checks pass.
5. A production preflight requires that receipt and the exact strategy code.
6. A post-run validator binds the output manifest and V2 metadata into a
   separate immutable run receipt.
7. Backtester changes are limited to lineage metadata plus audit-only slippage
   and bar-participation exposure bookkeeping. Execution ordering and prices
   remain unchanged.

No Markdown parsing is part of enforcement. Markdown remains explanatory; JSON
sidecars and receipts are authoritative for machine checks.

## Validation summary

- Enforcement suite: 22/22 PASS, including all 14 required freeze attacks.
- Backtester V2 suite: 76/76 PASS (73 pre-existing tests plus 3 audit tests).
- Python AST, JSON parsing, validator CLI import/help, and `git diff --check`:
  PASS.
- Canonical-data smoke run: PASS with V2 QA status `VERIFIED`.
- No market data was downloaded or modified.

## Adversarial-audit remediation

Starting remediation baseline: `d12c22d1fba8f412ba8fbdecfe6f5edc538940cb`
on `backtester-v2`, equal to `origin/backtester-v2`, with a clean worktree.

The remediation closes the confirmed production bypasses without changing V2
execution semantics:

1. production metadata construction and atomic output publication both require
   an authentic `VerifiedPreflightContext`; run purpose/stage are explicit;
2. frozen protocol values are converted into one expected effective config and
   compared semantically with actual `BacktestConfig`, while actual timestamps
   must equal the frozen stage-specific window;
3. production accepts only the canonical capability manifest from the real
   expected Git repository and verifies the controlled module set;
4. lineage requires the exact writer-derived output set, rejects empty/incomplete
   or unexpected manifests, and recomputes Git, code, strategy, data, config,
   metric, and output identities;
5. registry predecessor continuity, parameter/spec identity, receipt indexes,
   research-use history, and one-use protected validation are enforced;
6. SOURCE_RANGE, proxy, state graph, cross-document chronology/source/fidelity,
   ranking, fees, test manifests, and trace path/symbol/hash contracts are strict;
7. QA is split into engine integrity, data fidelity, methodology preflight,
   execution fidelity, and causality assurance;
8. Python validators are the sole authoritative structural contract; inactive
   JSON Schema sketches were removed.

The technical boundary remains deliberately honest: executed tests and code
identity do not formally prove semantic equivalence or absence of look-ahead in
arbitrary Python. Those require source/code/causality review.
