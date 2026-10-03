# Strategy Replication Enforcement Layer V1

Markdown files in this directory explain the research standard. They are not
parsed and cannot authorize a production historical run.

Machine authority is split as follows:

- Candidate Registry JSON: candidate intake, status history, and variants.
- Evaluation Protocol JSON: common window, execution, metrics, ranking,
  protected validation, and multiple-testing rules.
- Strategy Spec JSON: source evidence, fidelity, rules, parameters, data
  allowlist, state decisions, tests, and strategy-specific exceptions.
- Capability manifest: the exact supported V2 execution contract.
- Test-result manifest: identities and results of actually executed strategy tests.
- Run config: effective values used by V2.
- Freeze/run/protected-use receipts and ledgers: immutable identities, collision
  detection, and post-run lineage.

## Authoritative production path (V2)

`run_production_research()` in `production_runner.py` is the only authoritative
production path. It does not accept a caller-supplied `BacktestResult`, strategy
object, run ID, preflight context, state database, or receipt/index path. It:

1. captures the frozen strategy-spec bytes once, parses all execution-critical
   spec values from that immutable snapshot, captures the locked strategy bytes
   once, and constructs the frozen entrypoint with those exact parameters;
   callers cannot choose an alternate class, function, or parameter payload;
2. verifies the suite hash frozen in the strategy spec, executes that unittest
   suite, and records structured process evidence;
3. derives the actual window and row count from the bars passed to V2;
4. requires the manifest's exact bar-stream hash/count/window to match those bars;
5. requires the full canonical `BacktestConfig` hash to match
   `strategy_spec.execution_config_sha256`;
6. runs `BacktestEngine` itself;
7. writes a canonical `result.json` and execution attestation;
8. rereads and cross-checks every CSV/JSON output against that result;
9. transactionally registers the run and protected use in the fixed project
   store `.strategy-replication/enforcement-v2.sqlite3`;
10. issues `RUN_RECEIPT_V2` only after all checks pass.

The CLI is `python3 -m research.strategy_replications.run_production_v2`.
Its local bars file must be JSON/JSONL and its data manifest must contain a
`production_contract` with `symbol`, `market`, `timeframe`,
`timestamp_semantics`, `bars_sha256`, `row_count`, `tested_start`, and
`tested_end`. `bars_sha256` is the SHA-256 of newline-delimited, canonical JSON
for each ordered `Bar` dataclass field. Use `canonical_bars_sha256()` to produce
it. No market data is downloaded by the runner.

The frozen strategy spec must also contain
`implementation.strategy_symbol`, `tests.suite_sha256`, and
`execution_config_sha256`. These bind the exact executable entrypoint, the
approved executable tests, and every `BacktestConfig` field, including fields
not represented by the common protocol. The entrypoint is repeated and
cross-checked in the freeze receipt, executed-test evidence, execution
attestation, and `RUN_RECEIPT_V2`. The canonical constructor-parameter payload
is likewise hashed as `strategy_parameters_sha256` in the execution attestation
and `RUN_RECEIPT_V2`, then revalidated against the authoritative frozen spec
and canonical state.

`RUN_RECEIPT_V1` issuance and validation are disabled. V1 artifacts remain
historical evidence only and are explicitly not execution-attested authority.

The standard-library Python validators in `validation/core.py` are the one
authoritative structural and semantic contract. The former non-executed JSON
Schema sketches were removed so there is no second, divergent contract. No
arbitrary Markdown parsing or third-party schema dependency is required.

## Freeze

```bash
python3 -m research.strategy_replications.validation.validate_freeze \
  --spec path/to/spec.json \
  --registry path/to/registry.json \
  --protocol path/to/protocol.json \
  --capability research/strategy_replications/capability/backtester_v2_capabilities.json \
  --data-manifest path/to/data-manifest.json \
  --repo-root . \
  --receipt-out path/to/freeze_receipt.json
```

The command reports every detected defect and writes a receipt only on PASS.
Receipt files are immutable: existing files are never overwritten.
Strategy code is mandatory at freeze. The receipt index prevents reuse of the
same candidate/variant/version/parameter identity.

## Legacy standalone preflight

```bash
python3 -m research.strategy_replications.validation.validate_production_run \
  --spec path/to/spec.json --registry path/to/registry.json \
  --protocol path/to/protocol.json \
  --capability research/strategy_replications/capability/backtester_v2_capabilities.json \
  --data-manifest path/to/data-manifest.json \
  --strategy-code path/to/strategy.py --test-manifest path/to/test-results.json \
  --config path/to/effective-config.json \
  --tested-start 1577836800000 --tested-end 1609459200000 \
  --run-stage COMPARISON \
  --receipt path/to/freeze_receipt.json --repo-root .
```

Declaring `FROZEN` without a valid receipt never passes this diagnostic gate.
The standalone preflight cannot issue an authoritative production receipt;
production authority requires the atomic V2 runner.

## Fail-closed production flow

`candidate intake → protocol → spec → freeze → runner-owned tests → preflight → runner-owned execution → semantic validation → transactional registration → V2 receipt`

- intake blocks unknown/reused identities and broken registry predecessor chains;
- freeze blocks invalid specs, missing strategy entrypoints,
  code/data/capability drift, and parameter reuse;
- preflight binds the frozen window and semantically derived effective config to
  the actual `BacktestConfig`, real Git repository, strategy code, and executed
  test manifest;
- output publication rechecks the opaque preflight context, window, config, and
  Git identity;
- post-run validation requires the exact complete output set, verifies every
  checksum and required metric, and recomputes Git/code/data/test identities;
- receipt revalidation opens canonical state read-only and rejects drift in any
  upstream file, execution-critical file, Git commit, exact bar contract, or
  strategy entrypoint identity;
- V2 receipt creation uses database uniqueness constraints for run IDs, frozen
  variant identities, and protected uses; the database path is not caller-controlled.

Every run has explicit `run_purpose` and `run_stage`. Non-production
`TEST`/`SMOKE`/`SYNTHETIC` outputs remain possible but are labeled
`NON_PRODUCTION` and cannot be mistaken for production research.

## QA dimensions

Production eligibility is based on separate fields:

- `engine_integrity`: whether V2's applicable engine checks passed;
- `data_fidelity`: canonical/declared identity verification status;
- `methodology_preflight`: whether the frozen research contract passed;
- `execution_fidelity`: source-faithful, target mapping, or proxy;
- `causality_assurance`: executed-test evidence or human review required.

The legacy aggregate `qa_status` is retained only for compatibility. It is not
evidence of canonical data, source fidelity, or absence of look-ahead.

## Hashing and immutability

Every SHA-256 is calculated over the exact bytes stored on disk. No document
contains its own hash. A freeze receipt is external to all artifacts it hashes.
The output manifest similarly excludes itself; its exact-byte SHA-256 is stored
in the external run receipt. Frozen specs are never edited with run facts or
change history.

## Technically enforced

Exact file identities, real Git HEAD/branch/origin, material dirty state,
canonical capability path and controlled IDs, window/config equality, data
manifest consistency, required test-result identities, trace path/symbol/hash
existence, complete outputs, metrics, receipt uniqueness, registry continuity,
and protected-use logging are machine checked.

## Human/code-review trust boundary

The layer does not prove semantic equivalence to prose, discover an honestly
omitted candidate, statically prove arbitrary Python causal, or prevent
malicious code from reading undeclared files. Source review, code review,
semantic causality review, and candidate-universe completeness remain human
responsibilities. `HUMAN_REVIEW_REQUIRED` states this boundary explicitly.

## Status mapping

`DRAFT` strategy specs correspond to registry `IDENTIFIED`, `SOURCE_REVIEW`, or
`SPEC_DRAFT`. `BLOCKED` corresponds to `BLOCKED_SOURCE`, `BLOCKED_DATA`, or
`BLOCKED_ENGINE`. `FROZEN` and `TESTED` correspond to registry `FROZEN` and
`BACKTESTED`. A freeze receipt is issued only for the exact `FROZEN` pair.

## Exit ordering

Engine-controlled ordering is authoritative in the capability manifest and V2
engine. A strategy spec declares only strategy-controlled simultaneous choices;
it cannot override liquidation, gap, protective-order, or callback ordering.
