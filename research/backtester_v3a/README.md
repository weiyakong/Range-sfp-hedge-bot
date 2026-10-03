# Backtester V3-A single-instrument infrastructure

This package owns the contracts, input resolution, precision boundary,
production branch policy, atomic runner, differential harness, and canonical
state for one run of one instrument. It does not modify Backtester V2
execution, accounting, funding timing, liquidation, fill, hedge, leverage, or
drawdown semantics.

## Sole symbol authority

The authoritative chain begins at the frozen `STRATEGY_SPEC_V2`:

```text
STRATEGY_SPEC_V2.execution_identity.symbol
  -> trade-price identity
  -> funding identity or explicit frozen NOT_USED policy
  -> Mark Price identity or explicit frozen NOT_USED policy
  -> instrument-metadata identity
  -> result metadata
  -> execution attestation
  -> run receipt
  -> isolated V3-A SQLite state
```

Every duplicated identity is checked for exact equality. Values are not
case-normalized. A mismatch fails before execution or fails independent
revalidation.

`execution_identity` contains:

- `exchange`
- `market`
- `symbol`
- `execution_timeframe`
- `timezone`
- `timestamp_semantics`

`execution_timeframe` is deliberately distinct from signal, feature, or
derived-data timeframes.

## Strategy entrypoint

V3-A uses `implementation.strategy_entrypoint` for the locked Python callable.
It never uses `strategy_symbol`; `symbol` exclusively means the traded
instrument.

## Input contracts

The frozen spec hash-binds exactly four requirements:

- trade price (always required);
- funding (`REQUIRED` or `EXPLICITLY_NOT_USED`);
- Mark Price (`REQUIRED` or `EXPLICITLY_NOT_USED`);
- instrument metadata (always required).

Dataset paths are locators. Dataset and manifest hashes are immutable identity.
Supplying an input declared `EXPLICITLY_NOT_USED` is rejected, preventing a
caller from silently introducing a proxy after the spec was frozen.

## Instrument metadata

The metadata contract records decimal-string tick/step/minimum rules, optional
precision values, provenance hash, effective-time information, and one explicit
fidelity class:

- `HISTORICAL_VERIFIED`
- `STATIC_CURRENT_PROXY`
- `RESEARCH_ASSUMPTION`

The precision boundary floors quantity to `step_size`, rounds order prices to
the nearest `tick_size`, enforces minimum quantity and notional, and validates
rounded protective levels before the intent reaches the unchanged V2 engine.

## Explicit data resolution

The caller supplies contract locators, never a symbol. Each dataset contract
contains an absolute manifest locator plus the manifest SHA-256. The manifest
contains the explicit data locator and payload SHA-256. Runtime resolution
checks both hashes, strict CSV columns, row counts, time ordering, OHLC
integrity, declared coverage, and the complete identity against the frozen
spec.

Funding is never defaulted to zero when required. Mark Price is never replaced
with trade-price candles when required. Metadata provenance content is hashed,
and its fidelity classification remains explicit.

## Independent branch policy

V3-A production execution and validation use
`BACKTESTER_V3A_BRANCH_POLICY_V1`, whose sole production branch is
`backtester-v3a`. This policy does not import the V2 enforcement layer. The V2
production branch remains `backtester-v2`.

## Production runner

`python3 -m research.backtester_v3a.run_production_v3a` executes the complete
authority chain. Its CLI has no symbol option. It writes into a private staging
directory, records a RESERVED-to-COMPLETE SQLite transition, independently
revalidates the identity chain and artifact checksums, and only then atomically
promotes the output directory. Failed reservations become FAILED.

The result envelope is content-bound: its canonical SHA-256 is the execution
identifier stored in the attestation, receipt, and SQLite state.

## Artifact and state schemas

Checked-in JSON Schemas document the strict V3-A Strategy Spec, datasets,
metadata, result metadata, attestation, and receipt. Runtime parsing is also
strict and rejects missing or unexpected fields.

V3-A state uses:

```text
.strategy-replication/v3a/enforcement-v1.sqlite3
```

It is physically separate from V2 state at
`.strategy-replication/enforcement-v2.sqlite3`. Every run row stores symbol,
exchange, market, execution timeframe, dataset-contract hashes, metadata hash,
spec hash, result/attestation/receipt hashes, and code identity.

## Phase boundary

Phase 3 includes only generic single-symbol infrastructure and synthetic
verification. It does not collect full ETH/SOL histories, run TSMOM research,
optimize strategies, or implement a multi-symbol/V3-B portfolio.
