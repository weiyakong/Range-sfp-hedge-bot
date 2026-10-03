# Backtester V3-A Phase 2 report

## Status

Phase 2 implements the versioned identity and mismatch-gate contracts for one
symbol per run. It does not implement a V3-A production runner, precision
normalization, generic data loading, or real ETH/SOL execution.

- Branch: `backtester-v3a`
- Base HEAD: `e418da367cee5dcda9c0a99255642c065ca0cb0b`
- V2 production files changed: `NO`
- V2 worktree changed: `NO`
- Remote changes/push: `NO`

## Schema design

| Contract | Version | Purpose |
|---|---|---|
| Frozen Strategy Spec | `STRATEGY_SPEC_V2` | Sole authority for execution identity, strategy entrypoint, parameters, config hash, and required input-contract hashes |
| Dataset identity | `BACKTESTER_V3A_DATASET_IDENTITY_V1` | Instrument-bound trade-price, funding, or Mark Price identity with locator, manifest hash, dataset hash, and coverage |
| Instrument metadata | `BACKTESTER_V3A_INSTRUMENT_METADATA_V1` | Tick/step/minimum rules, optional precisions, provenance, effective time, and fidelity classification |
| Result metadata | `BACKTESTER_V3A_RESULT_METADATA_V1` | Direct persisted execution identity and all upstream contract hashes |
| Execution attestation | `BACKTESTER_V3A_EXECUTION_ATTESTATION_V1` | Result, code, spec, parameters, and input identities for one execution |
| Run receipt | `BACKTESTER_V3A_RUN_RECEIPT_V1` | Authoritative immutable identity chain for a completed V3-A run |
| Canonical state | `BACKTESTER_V3A_STATE_V1` | Directly revalidatable symbol and input identities in isolated SQLite state |

The execution identity has exactly these fields:

```text
exchange
market
symbol
execution_timeframe
timezone
timestamp_semantics
```

The strategy implementation uses `strategy_entrypoint`. V3-A schemas do not
use `strategy_symbol`.

## Authoritative symbol chain

```text
frozen STRATEGY_SPEC_V2.execution_identity.symbol
  -> trade-price contract
  -> funding contract or frozen EXPLICITLY_NOT_USED
  -> Mark Price contract or frozen EXPLICITLY_NOT_USED
  -> instrument-metadata contract
  -> result metadata
  -> execution attestation
  -> run receipt
  -> isolated V3-A SQLite state
  -> independent revalidation
```

The binder checks exchange, market, and symbol for every supplied input. Trade
and Mark Price timeframes must match `execution_timeframe`; the trade dataset
must also match execution timezone and timestamp semantics. Frozen contract
hashes are checked after semantic identity checks.

No case normalization or silent fallback is performed. A required missing
contract fails. Supplying a contract declared `EXPLICITLY_NOT_USED` also fails.

## SQLite isolation

V3-A state is defined at:

```text
.strategy-replication/v3a/enforcement-v1.sqlite3
```

V2 state remains at:

```text
.strategy-replication/enforcement-v2.sqlite3
```

The V3-A `runs` row directly stores exchange, market, symbol,
`execution_timeframe`, timezone, timestamp semantics, spec/parameter hashes,
all four input-contract hashes, result/attestation/receipt hashes, code identity,
and status.

## Requirement traceability

| Requirement | Implementation | Tests | Status |
|---|---|---|---|
| Frozen spec is sole symbol authority | `ExecutionIdentity`, `StrategySpecV2`, `bind_execution_contracts` | BTC/ETH/SOL pass; wrong-symbol inputs fail | PASS |
| Use `execution_timeframe`, not generic `timeframe` | Strict parser and Strategy Spec schema | Generic `timeframe` rejected | PASS |
| Separate traded symbol from Python entrypoint | `execution_identity.symbol`, `implementation.strategy_entrypoint` | Entry point and symbol asserted independently | PASS |
| Trade-price identity | `DatasetIdentity(role=trade_price)` | Wrong symbol, exchange, market, timeframe, hash, coverage, and missing input tests | PASS |
| Funding identity | `DatasetIdentity(role=funding)` | SOL spec + ETH funding fails; required missing fails; frozen NOT_USED enforced | PASS |
| Mark Price identity | `DatasetIdentity(role=mark_price)` | BTC spec + SOL Mark Price fails; required missing fails; frozen NOT_USED enforced | PASS |
| Instrument metadata identity | `InstrumentMetadata` | Wrong symbol, missing metadata, provenance/effective-time, and positive-value tests | PASS |
| Fidelity taxonomy | `MetadataProvenance` | Historical effective time and static proxy tests | PASS |
| Result/attestation/receipt identity | Strict artifact parsers and `revalidate_identity_chain` | Result, attestation, receipt symbol mutations fail | PASS |
| Frozen spec mutation detection | Spec hash plus independent identity comparison | Frozen-spec symbol mutation fails | PASS |
| SQLite symbol mutation detection | Isolated schema plus state revalidation | Direct SQLite symbol mutation fails | PASS |
| Strategy/config downstream mismatch | `require_downstream_symbol` | Strategy override and config mismatch fail | PASS |
| V2 state/artifact isolation | Separate package, schemas, and SQLite path | Physical-state-separation test | PASS |

## Files

New audit/documentation:

- `docs/backtester-v3a-btc-specific-dependency-audit.md`
- `docs/backtester-v3a-phase2-report.md`
- `research/backtester_v3a/README.md`

New implementation:

- `research/backtester_v3a/__init__.py`
- `research/backtester_v3a/contracts.py`
- `research/backtester_v3a/state.py`

New checked-in schemas:

- `research/backtester_v3a/schemas/strategy_spec_v2.schema.json`
- `research/backtester_v3a/schemas/dataset_identity_v1.schema.json`
- `research/backtester_v3a/schemas/instrument_metadata_v1.schema.json`
- `research/backtester_v3a/schemas/result_metadata_v1.schema.json`
- `research/backtester_v3a/schemas/execution_attestation_v1.schema.json`
- `research/backtester_v3a/schemas/run_receipt_v1.schema.json`
- `research/backtester_v3a/schemas/sqlite_state_v1.sql`

New tests:

- `research/backtester_v3a/tests/__init__.py`
- `research/backtester_v3a/tests/test_phase2_contracts.py`

Changed production V2 files: none. Deleted files: none.

## Validation

| Gate | Result |
|---|---|
| V3-A Phase 2 contract/mutation suite | `36/36 PASS` |
| Backtester V2 engine suite | `76/76 PASS` |
| Binance funding suite | `6/6 PASS` |
| Strategy-replication V2 suite in untouched `backtester-v2` worktree | `78/78 PASS` |
| Strategy-replication V2 suite from `backtester-v3a` | `59 PASS`, `19 expected branch-policy rejections` |
| Python compile check for V3-A package | `PASS` |
| JSON parse check for all checked-in schemas | `PASS` |
| Static type checker | `NOT CONFIGURED` |

The 19 V3-worktree rejections are caused by the existing V2 production guard
`production research requires branch backtester-v2`. The same complete suite
passes `78/78` in the untouched V2 worktree. The guard was not weakened or
modified.

## Phase boundary

Phase 3 has not started. The following remain outside Phase 2:

- V3-A production CLI/runner integration;
- generic manifest resolvers/loaders;
- precision normalization of raw strategy intents;
- execution of the required V2-to-V3-A BTC differential;
- synthetic normalized BTC/ETH/SOL execution equivalence;
- real ETH/SOL data collection or strategy runs;
- V3-B portfolio or multi-symbol state.
