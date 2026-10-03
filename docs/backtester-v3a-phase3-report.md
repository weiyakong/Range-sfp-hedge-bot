# Backtester V3-A Phase 3 report

## Status and boundary

Phase 3 implements generic one-run/one-symbol input resolution, precision
normalization, an independent V3-A branch policy, an atomic V3-A runner, a BTC
differential harness, and three synthetic instrument profiles.

- Branch: `backtester-v3a`
- Base HEAD: `e418da367cee5dcda9c0a99255642c065ca0cb0b`
- V2 production files changed: `NO`
- V2 branch policy changed: `NO`
- Real TSMOM, ETH, or SOL research runs: `NO`
- New market data collected: `NO`
- Remote changes/push: `NO`
- Phase 4 started: `NO`

## Architecture

```text
frozen STRATEGY_SPEC_V2
  -> immutable execution identity and authoritative symbol
  -> explicit trade/funding/mark/metadata contract locators
  -> manifest SHA-256 and data SHA-256 verification
  -> strict single-symbol dataset loading and coverage checks
  -> frozen strategy_entrypoint
  -> raw strategy intent
  -> instrument precision normalization and validation
  -> unchanged Backtester V2 execution engine
  -> content-addressed V3-A result
  -> V3-A result metadata
  -> V3-A execution attestation
  -> V3-A run receipt
  -> isolated V3-A SQLite RESERVED -> COMPLETE state
  -> immediate independent revalidation
  -> atomic output-directory promotion
```

The public resolver and runner request contain no independently supplied
symbol. The symbol is read only from
`STRATEGY_SPEC_V2.execution_identity.symbol`.

## V3-A branch policy

The independent policy is:

```text
schema/version: BACKTESTER_V3A_BRANCH_POLICY_V1
production branch: backtester-v3a
```

Both execution and independent validation invoke this policy. The module does
not import V2 validation or branch enforcement. The existing V2 guard remains
unchanged and continues to require `backtester-v2`.

## Generic data resolution

`InputContractLocators` contains only four paths:

- trade-price contract;
- funding contract or explicit absence;
- Mark Price contract or explicit absence;
- instrument-metadata contract.

For datasets, the contract binds the authoritative exchange, market, symbol,
timeframe/semantics, coverage, manifest path, manifest hash, and dataset hash.
The manifest is a locator document; its hash and the data payload hash are the
reproducibility authority. Runtime validation checks strict CSV schemas, row
counts, timestamps, gaps, duplicates, OHLC invariants, funding values, Mark
Price alignment, and metadata provenance content.

Required funding or Mark Price cannot be absent. Funding is not silently set to
zero, and required Mark Price is not replaced by trade-price candles.

## Precision boundary

```text
raw strategy intent
  -> quantity floor to step_size
  -> price rounding to nearest tick_size
  -> zero/min_qty/min_notional checks
  -> rounded SL/TP geometry validation
  -> normalized limit marketability classification
  -> unchanged V2 engine
```

Grid-valid values remain unchanged. Exit and cancel intents pass through
without entry-size checks.

## BTC differential

The locked testcase uses BTC-like grid-valid values:

- prices around `30000`;
- quantity `0.01`;
- tick `0.10`;
- step `0.001`;
- non-zero taker fees, slippage, and funding;
- forced close at the final bar.

The raw and normalized intents are identical. Exact comparison of intents,
submissions, fills, timestamps, prices, quantity, fees, slippage, funding,
realized/unrealized PnL, liquidation fields, trade log, final cash/equity,
equity curves, drawdown, and ambiguity labels passes with no tolerance or
unexplained numeric difference.

Observed result:

| Field | Value |
|---|---:|
| Entry price | `30013.001` |
| Exit price | `30036.996` |
| Fees | `0.24019998800000003` |
| Slippage cost | `0.06005000000001019` |
| Funding | `0.3003` |
| Net PnL | `-0.3005499880000102` |
| Final cash/equity | `9999.699450011998` |
| Maximum drawdown | `3.504862337440155e-05` |
| QA | `VERIFIED` |
| Differential | `PASS` |

## Synthetic instruments

Three checked-in synthetic profiles have different absolute prices and
microstructure:

| Profile | Base price | Tick | Step | Min qty | Min notional |
|---|---:|---:|---:|---:|---:|
| BTC-like | 30000 | 0.10 | 0.001 | 0.001 | 5 |
| ETH-like | 2000 | 0.01 | 0.01 | 0.01 | 10 |
| SOL/alt-like | 50 | 0.001 | 0.1 | 0.1 | 20 |

Equivalent normalized one-shot geometry produces the same trade count, side,
entry timestamp, exit reason, and QA classification for all three profiles.

## Requirement traceability

| Requirement | Module | Tests | Status |
|---|---|---|---|
| Independent V3-A branch guard | `branch_policy.py` | correct/wrong branch, no V2 import | PASS |
| No caller symbol override | `data.py`, `run_production_v3a.py` | locator and CLI field inspection | PASS |
| Manifest and content authority | `data.py` | manifest/data hash corruption | PASS |
| Trade integrity and coverage | `data.py` | load, symbol, coverage, schema/time checks | PASS |
| Funding hard requirements | `data.py` | missing and wrong-symbol funding | PASS |
| Mark Price hard requirements | `data.py` | missing and wrong-symbol mark | PASS |
| Metadata identity/provenance | `data.py`, `contracts.py` | symbol and source-hash mismatch | PASS |
| Precision normalization | `precision.py` | tick, step, zero, minima, SL/TP, marketability | PASS |
| Atomic production runner | `runner.py`, `state.py` | end-to-end persist/revalidate/mutation | PASS |
| BTC exact differential | `differential.py` | exact PASS and injected numeric failure | PASS |
| Synthetic instruments | `synthetic.py` | three profiles and logical equivalence | PASS |
| Static type safety | `mypy.ini`, `requirements-dev.txt` | strict mypy | PASS |

## Files added in Phase 3

- `requirements-dev.txt`
- `mypy.ini`
- `research/backtester_v3a/branch_policy.py`
- `research/backtester_v3a/data.py`
- `research/backtester_v3a/precision.py`
- `research/backtester_v3a/runner.py`
- `research/backtester_v3a/run_production_v3a.py`
- `research/backtester_v3a/differential.py`
- `research/backtester_v3a/synthetic.py`
- `research/backtester_v3a/schemas/data_manifest_v1.schema.json`
- `research/backtester_v3a/schemas/output_manifest_v1.schema.json`
- `research/backtester_v3a/schemas/result_v1.schema.json`
- `research/backtester_v3a/tests/phase3_support.py`
- `research/backtester_v3a/tests/test_phase3_branch_policy.py`
- `research/backtester_v3a/tests/test_phase3_data.py`
- `research/backtester_v3a/tests/test_phase3_precision.py`
- `research/backtester_v3a/tests/test_phase3_runner_differential.py`

Phase 3 also extends the already-new V3-A `contracts.py`, `state.py`, and
package README. No V2 source or test file is changed.

## Validation

| Gate | Result |
|---|---:|
| Phase 2 V3-A contracts | `36/36 PASS` |
| Phase 3 V3-A | `33/33 PASS` |
| Total V3-A | `69/69 PASS` |
| Backtester V2 in V2 worktree | `76/76 PASS` |
| Strategy replications in V2 worktree | `78/78 PASS` |
| Binance funding in V2 worktree | `6/6 PASS` |
| V2 baseline total | `160/160 PASS` |
| Strict mypy | `PASS` |
| Compile/import/CLI startup | `PASS` |
| Checked-in JSON parse | `PASS` |
| Git diff/whitespace check | `PASS` |

## Stop gate

Phase 4 has not started. No push has been performed.
