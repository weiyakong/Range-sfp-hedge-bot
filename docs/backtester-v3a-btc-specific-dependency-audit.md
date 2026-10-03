# Backtester V3-A: BTC-specific dependency audit

## 1. Audit identity

- Audit date: `2026-10-03`
- Repository worktree: `/Users/yeshevika/Documents/Codex/2026-10-03/range-sfp-backtester-v3a`
- Branch: `backtester-v3a`
- Audited base HEAD: `e418da367cee5dcda9c0a99255642c065ca0cb0b`
- V2 baseline at audit start: `160/160 PASS`
  - Backtester V2: `76/76 PASS`
  - Strategy replications: `78/78 PASS`
  - Binance funding: `6/6 PASS`
- Production code changed during this phase: `NO`
- External data collected: `NO`
- Remote state changed: `NO`

The audit covers literal BTC references and non-literal symbol coupling in the
single-instrument engine, loaders, contracts, Strategy Spec validation,
production runner, receipts, attestations, canonical SQLite state, tests, and
the local data-root layout.

Literal inventory command:

```text
git grep -I -n -i -E 'BTCUSDT|(^|[^[:alnum:]_])BTC([^[:alnum:]_]|$)|btc[_/-]'
```

Result: `358` literal occurrences in `48` tracked files. Literal matching alone
is insufficient: several of the most important dependencies are symbol-blind
rather than explicitly BTC-named.

## 2. Executive findings

### 2.1 Current authority chain

The present production authority chain is:

```text
Frozen Strategy Spec
  -> implementation.strategy_symbol (Python class/entrypoint, not instrument)

Caller CLI --symbol/--market/--timeframe
  -> ProductionRunRequest.symbol/market/timeframe
  -> equality check against data_manifest.production_contract
  -> run metadata + execution attestation
  -> engine (symbol-blind)
```

This does not meet the V3-A contract. The frozen Strategy Spec does not contain
an authoritative execution instrument symbol. The caller currently supplies
the market symbol independently. `strategy_symbol` is an overloaded name for a
Python entrypoint such as `MaCrossStrategy`; it is not `BTCUSDT`.

### 2.2 Critical gaps

1. **Frozen Strategy Spec has no instrument identity.** Its strict top-level
   schema rejects unknown fields, so V3-A requires an explicit versioned schema
   extension or a new schema version.
2. **Caller is currently authoritative for symbol.** The data manifest only
   checks equality with the caller value, not with the frozen spec.
3. **Engine-domain objects are symbol-blind.** `Bar`, `BacktestConfig`,
   `BacktestResult`, positions, orders, and strategy state carry no instrument
   identity.
4. **Funding is an untyped pair of timestamp maps.** It has no exchange,
   market, symbol, dataset identity, coverage, manifest hash, or absence policy.
   An empty map silently means no funding events.
5. **Mark Price is embedded as optional fields on each `Bar`.** There is no
   separate mark dataset contract or symbol identity.
6. **Instrument metadata and precision rules do not exist.** There is no tick
   size, step size, minimum quantity, minimum notional, precision provenance,
   rounding policy, or order rejection based on those rules.
7. **The authoritative receipt lacks instrument symbol.** The receipt contains
   `strategy_symbol` (Python entrypoint), but not market `symbol`, `exchange`,
   or `market` as direct immutable fields.
8. **Canonical SQLite state lacks symbol.** A run row is bound to a data
   manifest hash but has no directly revalidatable symbol column.
9. **Result payload lacks symbol.** Symbol is present in `run_metadata.json` and
   `execution_attestation.json`, but not in the engine result identity.
10. **The legacy canonical candle builder is explicitly BTC-only.** It hardcodes
    `BTCUSDT`, BTC coverage, the known BTC gap, and `derived/BTCUSDT` paths.
11. **The funding collector is partly generic but its production bootstrap and
    independent validator remain BTC-only.** Its diagnostic text and default
    CLI symbol also assume BTC.
12. **There is no local ETHUSDT or SOLUSDT data.** This is acceptable for the
    requested synthetic/infrastructure stage but blocks real ETH/SOL research.

## 3. Production and contract dependency table

| FILE | LOCATION | CURRENT BTC-SPECIFIC OR SYMBOL-COUPLED BEHAVIOR | V3-A REQUIRED BEHAVIOR | CHANGE REQUIRED? |
|---|---:|---|---|---|
| `research/strategy_replications/validation/core.py` | 395-403 | `STRATEGY_SPEC_V1` strict field list has no execution instrument identity and rejects extra fields. | Frozen spec must authoritatively contain exchange, market, and instrument symbol. | YES |
| `research/strategy_replications/validation/core.py` | 512-528 | Data declarations carry hashes and field metadata, but no common authoritative instrument identity. | Validate every declared execution dataset against the frozen spec instrument. | YES |
| `research/strategy_replications/validation/core.py` | 550-568 | `implementation.strategy_symbol` means a public dotted Python entrypoint. The name is easily confused with a market symbol. | Preserve entrypoint locking but distinguish it from `instrument_symbol`; do not reinterpret the existing field silently. | YES |
| `research/strategy_replications/validation/core.py` | 1620-1790 | Freeze receipt binds the Python strategy entrypoint and parameter identity, not the market symbol. | Freeze receipt must bind the authoritative execution instrument identity. | YES |
| `research/strategy_replications/run_production_v2.py` | 38-69 | CLI requires caller-controlled `--symbol`, `--market`, and `--timeframe`. | V3-A runner derives identity from the frozen spec; any optional duplicated caller assertion must match exactly or hard-fail. | YES |
| `research/strategy_replications/production_runner.py` | 167-187 | `ProductionRunRequest` independently accepts `symbol`, `market`, and `timeframe`. | Request cannot introduce an independent execution symbol. | YES |
| `research/strategy_replications/production_runner.py` | 298-305 | `_strategy_symbol()` reads a Python class/entrypoint, not the traded instrument. | Retain as entrypoint identity; add a separate frozen instrument identity parser. | YES |
| `research/strategy_replications/production_runner.py` | 337-365 | Data contract requires symbol, market, timeframe, timestamps, bar hash, row count, and tested bounds. It omits exchange, timezone, dataset ID/hash, coverage identity, and manifest identity/version. | Implement the full symbol-specific data identity from the V3-A contract. | YES |
| `research/strategy_replications/production_runner.py` | 773-830 | Runner only compares request identity to data contract. It never compares data to a spec-owned instrument identity. | Spec identity must be read first and every downstream contract must equal it before execution. | YES |
| `research/strategy_replications/production_runner.py` | 840-920 | Engine receives bars/config with no symbol. Attestation receives caller symbol after execution. | Validate all input identities before engine creation; attest the frozen authoritative symbol. | YES |
| `research/strategy_replications/production_runner.py` | 936-960 | `run_receipt_v2.json` omits traded symbol, exchange, market, funding identity, mark identity, and metadata identity. It contains `strategy_symbol`, which is only the Python entrypoint. | V3-A receipt must carry all required instrument and input identities directly and immutably. | YES |
| `research/strategy_replications/production_runner.py` | 986-1203 | Revalidation checks Python entrypoint identity and indirectly checks data symbol through attestation/data contract. It cannot validate receipt-symbol mutation because receipt has no instrument symbol. | Cross-check spec, result, receipt, attestation, data, funding, mark, metadata, and SQLite symbol identities. | YES |
| `research/strategy_replications/production_runner.py` | 640-708 | SQLite `runs` table has no symbol, exchange, or market column. | Version the state schema and persist immutable instrument identity. | YES |
| `research/strategy_replications/production_runner.py` | 711-769, 1207-1230 | Reservation/completion/revalidation keys do not independently bind a run to symbol. | Bind and revalidate the run's frozen instrument identity; symbol mutation must fail. | YES |
| `research/backtester_v2/models.py` | 27-38 | `Bar` contains trade OHLC and optional Mark Price OHLC but no dataset or symbol identity. | V3-A boundary must pair bar streams with an immutable symbol-specific contract; per-row duplication is not required if the enclosing contract is immutable. | YES, in V3-A boundary |
| `research/backtester_v2/models.py` | 49-87 | Orders use unconstrained floating-point price/quantity values. | Apply instrument-specific rounding and rejection before execution without changing V2 semantics. | YES, in V3-A layer |
| `research/backtester_v2/models.py` | 89-110 | Funding values and maintenance tiers are embedded in config without dataset or instrument identity. | Bind funding, mark, and metadata contracts to the authoritative symbol and record fidelity classifications. | YES |
| `research/backtester_v2/models.py` | 248-264 | `BacktestResult` carries no symbol or input identities. | V3-A result identity must unambiguously include the frozen symbol and linked inputs. | YES |
| `research/backtester_v2/engine.py` | 39-95 | Engine executes one implicit instrument; it has no symbol field. | Preserve one-run/one-symbol accounting while making the surrounding execution identity explicit and immutable. | YES, without multi-symbol state |
| `research/backtester_v2/engine.py` | 748-766 | Funding is applied from raw timestamp maps; no symbol, market, coverage, causality-manifest, or dataset identity is checked here. | Only accept prevalidated symbol-matched funding input; preserve V2 payment timing/sign semantics. | YES |
| `research/backtester_v2/engine.py` | 367-370, 687-748, 836-843 | Liquidation uses optional mark fields; identity is not known. Non-liquidation equity can fall back to trade price under existing V2 behavior. | Bind Mark Price contract to symbol and preserve the documented V2 fidelity limitation and fallback semantics. | YES |
| `research/backtester_v2/engine.py` | 880-956 | Config validation covers fees, leverage, funding numbers, and tiers but not instrument metadata provenance. | Validate a versioned instrument profile before orders reach existing V2 execution. | YES |
| `research/backtester_v2/engine.py` | 993-1022 | Quantity and prices are only checked for finite/positive and protective-level direction. No tick/step/minimum rules exist. | Add deterministic symbol-specific rounding and rejections with explicit precision tests. | YES |
| `research/backtester_v2/data.py` | 7-9 | Generic-looking loader imports from the BTC-specific `btc_macro_nautilus` builder. | V3-A loader/resolver must not depend on a BTC-specific module as authority. | YES |
| `research/backtester_v2/data.py` | 22-48 | Loader reads coverage but does not validate exchange, market, symbol, timeframe, timezone, or manifest identity before yielding bars. | Hard-validate the full data contract before yielding any bars. | YES |
| `research/backtester_v2/output.py` | 50-150 | `build_run_metadata()` accepts symbol/market/timeframe from its caller. | Accept one immutable execution identity derived from the frozen spec. | YES |
| `research/backtester_v2/output.py` | 207-360 | Output writer binds checksums, but symbol exists only inside caller-produced run metadata; result/trade artifacts have no independent instrument field. | Write and revalidate symbol across all relevant V3-A artifacts while retaining V2 artifact compatibility. | YES |
| `research/backtester_v2/smoke_run.py` | 8-11 | Hardcoded user-specific singleton BTC manifest path. | V3-A smoke uses deterministic symbol-aware discovery or an explicit frozen manifest contract. | YES for V3-A; keep V2 smoke reproducible |
| `research/backtester_v2/smoke_run.py` | 21-24 | Fixed `0.01` quantity implicitly assumes BTC-like viability and ignores step/min-notional metadata. | Use an instrument-profile-valid synthetic/smoke quantity. | YES for V3-A |
| `research/strategy_replications/capability/backtester_v2_capabilities.json` | 1-58 | Declares supplied funding and supplied mark support, but no symbol identity or precision-metadata capability. | Version V3-A capabilities and bind the new contract/test surface. | YES; do not overwrite V2 capability identity |

## 4. Legacy BTC data builders and collectors

These files are BTC-specific by design and are part of the preserved V2/research
baseline. V3-A must not silently rewrite their historical contract. Reuse is
allowed only behind a new symbol-aware adapter whose identity checks occur
before execution.

| FILE | LOCATION | CURRENT BTC-SPECIFIC BEHAVIOR | V3-A REQUIRED BEHAVIOR | CHANGE REQUIRED? |
|---|---:|---|---|---|
| `research/btc_macro_nautilus/canonical_candles/build_canonical_futures_candles.py` | 2, 29-68 | Module description, `INSTRUMENT`, `SOURCE_CONTRACT`, exact coverage, and known gap are BTCUSDT-specific. | Preserve as V2/BTC historical builder; V3-A must consume a generic manifest contract rather than these constants. | NO in legacy file; YES new V3-A resolver/contract |
| same | 923-1004 | Writes and stamps `derived/BTCUSDT`; report filenames are singleton/global. | Symbol-aware output discovery must resolve by authoritative symbol without changing legacy artifacts. | NO in legacy file; YES new V3-A path |
| `research/btc_macro_nautilus/binance_funding/collect_binance_funding.py` | 82-125 | `CollectorConfig` paths are already parameterized by `symbol`. | This path shape can support V3-A inputs after identity validation. | NO for path construction |
| same | 546-700 | Record validation compares rows to `config.symbol`, but one error message says BTCUSDT regardless of configured symbol. | Diagnostic and contract identity must use the authoritative symbol. | YES if promoted for V3-A use |
| same | 735-762 | Bootstrap reads singleton `strict_futures_1m_manifest.json`, emits a BTC-specific error, and defaults CLI symbol to BTCUSDT. | V3-A must not silently default to BTC or derive other symbols from the BTC singleton manifest. | YES if promoted for V3-A use |
| `research/btc_macro_nautilus/binance_funding/validate_binance_funding.py` | 19, 48, 57-58, 125 | Validator hardcodes expected BTCUSDT and the BTC manifest directory. | V3-A validation must receive/freeze the authoritative symbol and market. | NO in preserved BTC validator; YES new generic validator |
| `research/btc_macro_nautilus/binance_funding/CONTRACTS.md` | 1, 6 | Explicit BTCUSDT collection contract. | Keep as historical BTC contract. | NO |
| `research/btc_macro_nautilus/binance_funding/README.md` | 1, 6, 9, 16, 19 | Documents BTC-only workflow. | Keep accurate for legacy collector; document V3-A separately. | NO |
| `research/btc_macro_nautilus/coinalyze_derivatives/*` | listed in Appendix A | BTC derivatives research/collector contracts, not the Backtester V3-A production input path. | Remain out of scope unless explicitly adopted as a V3-A dataset. | NO |
| `workers/btc-derivatives-collector/**` | listed in Appendix A | Separate BTC-only worker, discovery policy, fixtures, package/config names. | V3-A must not couple to this worker. | NO |

## 5. Strategy interface and symbol authority

| FILE | LOCATION | CURRENT BEHAVIOR | V3-A REQUIRED BEHAVIOR | CHANGE REQUIRED? |
|---|---:|---|---|---|
| `research/backtester_v2/engine.py` | 24-26 | Strategy protocol receives only `Bar` and `StrategyState`. | One locked strategy version must execute under the run's immutable symbol without being able to override it. | YES, V3-A construction/context boundary |
| `research/strategy_replications/production_runner.py` | 308-334 | Strategy constructor receives only frozen parameter values. | Preserve parameter authority; symbol should be immutable execution context, not a caller- or strategy-controlled parameter. | YES |
| `research/strategy_replications/STRATEGY_SPEC_TEMPLATE.md` | 192-224 | Human template has “Target instrument”, but the validated structured sidecar has no corresponding machine field. | Machine-readable frozen symbol must be authoritative; Markdown alone is insufficient. | YES |
| `research/strategy_replications/STRATEGY_SPEC_TEMPLATE.md` | 122 | BTCUSDT appears only as an explanatory example. | Generic wording is preferable but not execution-critical. | OPTIONAL |

No production strategy implementation in the audited V2 tree contains a
literal `BTCUSDT`. The main risk is absent symbol context, not a strategy-level
BTC constant.

## 6. Funding, Mark Price, and metadata identity

### Funding

- V2 engine semantics are explicit and tested: exact-timestamp funding,
  funding before same-timestamp exit, and no funding for a position opened on
  that timestamp.
- Production runner does not load or validate a funding manifest. It receives
  timestamp maps through `BacktestConfig`.
- No dataset hash, source market, symbol, timezone, coverage, or causal
  availability contract accompanies those maps.
- `funding_rate_by_time={}` is accepted and produces no funding. V3-A needs a
  frozen, explicit absence policy; missing data cannot silently become zero.

### Mark Price

- Mark OHLC is optional per `Bar`.
- Leveraged liquidation requires mark values at runtime, which protects against
  last-trade substitution for liquidation.
- There is no Mark Price loader, manifest, symbol identity, or local Mark Price
  OHLC dataset.
- The funding CSV contains a `mark_price` at funding events; that is not a
  replacement for a causal Mark Price OHLC series used for liquidation.

### Exchange metadata and precision

- No versioned instrument metadata input exists in source or local data.
- No matching local files named as exchange info, instrument metadata,
  precision, or filters were found.
- V2 uses binary floating-point values and does not round to a tick/step.
- V2 has no min-quantity or min-notional rejection.
- Any V3-A precision behavior must be introduced as explicit instrument-specific
  behavior and must not retroactively alter the V2 differential baseline.

## 7. Test and fixture dependency table

| FILE | LOCATION | CURRENT BTC-SPECIFIC BEHAVIOR | V3-A REQUIRED BEHAVIOR | CHANGE REQUIRED? |
|---|---:|---|---|---|
| `research/backtester_v2/tests/test_audit_regressions.py` | 63 | BTCUSDT fixture metadata for V2 output tests. | Preserve V2 fixture and add separate V3-A symbol-matrix tests. | NO in V2; YES new tests |
| `research/backtester_v2/tests/test_data_output.py` | 67 | BTCUSDT passed to metadata builder. | Preserve baseline; V3-A output tests derive symbol from frozen identity. | NO in V2; YES new tests |
| `research/strategy_replications/tests/test_enforcement.py` | 576 | BTCUSDT fixture passed directly when building metadata. | Add machine-frozen instrument identity coverage. | YES/additive |
| `research/strategy_replications/tests/test_production_runner_v2.py` | 46, 109 | Manifest and request independently repeat BTCUSDT. | Preserve V2 baseline; V3-A fixture must put symbol in spec and prove every mismatch hard-fails. | YES/additive |
| same | 192-200 | Existing test proves caller symbol/timeframe must equal data contract. It does not prove spec authority. | Add spec-to-data, spec-to-config, and strategy-override rejection tests. | YES |
| same | 384-402 | “strategy symbol mutation” test mutates Python entrypoint, not instrument symbol. | Keep entrypoint test and add distinct instrument-symbol mutation tests. | YES/additive |
| `research/strategy_replications/tests/test_remediation_adversarial.py` | 330, 383, 469 | BTCUSDT fixture values in existing adversarial tests. | Preserve baseline; extend V3-A mutation surface. | YES/additive |
| `research/btc_macro_nautilus/binance_funding/test_collect_binance_funding.py` | 48-178 | BTC-specific collector baseline fixtures and paths. | Keep as BTC collector regression; add generic identity tests outside this baseline. | NO in existing test; YES new tests |
| `research/strategy_replications/tests/test_differential_reference.py` | 14-130 | Existing 15-scenario differential compares the current V2 engine to commit `2b096eb`; it is not a V2-to-V3-A BTC differential. | Add an explicit V2-at-approved-base versus V3-A BTCUSDT semantic differential covering required outputs. | YES/additive |

Missing tests required by V3-A include receipt instrument mutation, attestation
instrument mutation, frozen-spec instrument mutation, SQLite instrument
mutation, wrong-symbol bars/funding/mark/metadata, case mismatch, unsupported
symbol, missing metadata/data, precision profiles, and normalized synthetic
BTC/ETH/SOL equivalence.

## 8. Local data-root audit

Data root inspected read-only:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data`

### 8.1 Existing symbol-aware layout

The existing layout already uses a deterministic `{SYMBOL}` directory in
several relevant families:

```text
raw/binance/usdt_m/{SYMBOL}/...
normalized/binance/usdt_m/{SYMBOL}/...
manifests/binance/usdt_m/{SYMBOL}/...
derived/{SYMBOL}/{TIMEFRAME}/...
features/{SYMBOL}/...
```

Therefore V3-A does not need to invent a new general layout for these families.
Only `BTCUSDT` currently exists.

### 8.2 Singleton legacy manifest ambiguity

The authoritative strict 1m candle manifest currently lives at:

```text
manifests/strict_futures_1m_manifest.json
```

It contains `dataset.symbol=BTCUSDT`, but the path itself is not symbol-scoped.
There are multiple reasonable migration choices for additional symbols:

1. keep a per-run explicit manifest path and rely solely on validated manifest
   identity;
2. add `manifests/binance/usdt_m/{SYMBOL}/candles/1m/...`;
3. add a generic manifest catalog/index pointing to symbol manifests.

The V3-A specification requires this choice to be approved before Phase 3; the
audit does not select one.

### 8.3 Verified local identities

- Strict BTCUSDT 1m manifest SHA-256:
  `09d8af8e7f1bc0db13ff9bcaa8124e44dca95e2aa80a6d61c64884fd1b824e6f`
- BTCUSDT funding manifest SHA-256:
  `84930ecbcc6ce69786ce85f8a561e3fb8b208eb9afccc806ddca48b5d60170f0`
- ETH-like files/directories found: `0`
- SOL-like files/directories found: `0`
- Mark Price-named files found: `0`
- Exchange-metadata/precision/filter-named files found: `0`

## 9. Required V3-A change boundary

To preserve V2, the recommended boundary is additive:

- keep `research/backtester_v2` as the executable baseline;
- introduce versioned V3-A identity/contracts around the single-instrument
  execution semantics;
- do not add `positions[symbol]` or a multi-symbol event loop;
- derive exactly one immutable symbol from the frozen spec;
- bind bars, funding, Mark Price, instrument metadata, engine result, receipts,
  attestation, and state to that identity;
- apply precision at a documented V3-A order-normalization boundary;
- prove BTC execution/accounting equivalence against untouched V2.

This boundary is an audit recommendation, not an implementation decision.

## 10. Approved Phase 1 review decisions

The Phase 1 review approved the following architecture for Phase 2:

1. Introduce a separate versioned `STRATEGY_SPEC_V2` rather than extending the
   strict V1 schema in place.
2. Define immutable `execution_identity` with `exchange`, `market`, `symbol`,
   `execution_timeframe`, `timezone`, and `timestamp_semantics`. The generic
   field name `timeframe` is not used in execution identity because strategy
   signal and derived-data timeframes are separate concerns.
3. Rename the V3-A Python implementation identity to `strategy_entrypoint`.
   V2 `strategy_symbol` retains its historical meaning and is not reinterpreted.
4. Create separate versioned V3-A attestation, receipt, canonical SQLite state,
   and validation/revalidation contracts. V3-A state is physically separate
   from `.strategy-replication/enforcement-v2.sqlite3`.
5. Remove authoritative `--symbol` from the future V3-A production CLI. The
   sole symbol authority is `STRATEGY_SPEC_V2.execution_identity.symbol`.
6. Normalize and validate instrument precision at a V3-A boundary before the
   existing execution logic. The V2 engine core remains symbol-agnostic and its
   semantics are not changed for precision.
7. Use an explicit frozen manifest locator plus immutable hash/content identity.
   Do not introduce a new multi-symbol filesystem hierarchy during Phase 2.
8. Define separate instrument-bound identities for trade price, funding, Mark
   Price, and exchange metadata. Missing required inputs and any symbol mismatch
   hard-fail before execution; silent funding zero and silent trade-price Mark
   Price substitution are forbidden.
9. The BTC differential uses already grid-valid prices and quantities, so the
   V3-A precision boundary is a no-op in that equivalence test. Precision changes
   are tested independently.

The following later-phase choices remain explicit stop points if encountered:

- a new canonical ETH/SOL candle-manifest hierarchy;
- selection of real historical metadata versus a frozen static proxy or research
  assumption for an actual production run;
- any requested funding or Mark Price proxy fidelity contract;
- real ETH/SOL data collection or strategy execution.

## Appendix A: complete tracked literal BTC occurrence inventory

This appendix accounts for all 48 tracked files returned by the literal scan.
Line lists are grouped per file. “No” means the reference belongs to historical
documentation, a separate BTC research pipeline, or the preserved V2 baseline;
it does not mean V3-A may depend on it.

| FILE | LOCATION(S) | CLASSIFICATION | V3-A CHANGE? |
|---|---|---|---|
| `agent_handoff/CURRENT_STATE.md` | 16 | Historical BTC collector state | NO |
| `agent_handoff/CURRENT_TASK.md` | 15,16,23,30,36,129 | Historical BTC collector task | NO |
| `agent_handoff/TASK_LOG.md` | 28-48,59,71-82,100-102,137-148,164,169-174,190,197,201-206,221-223,231 | Historical task log | NO |
| `docs/next-steps.md` | 9 | Project-level BTC research note | NO |
| `docs/strategy-overview.md` | 5 | Existing BTC strategy documentation | NO |
| `freqtrade/README.md` | 12,52,55,82,96,105,132 | Separate Freqtrade BTC workflow | NO |
| `freqtrade/user_data/config-btc-sfp-backtest.json` | 3,28 | Separate BTC Freqtrade config/filename | NO |
| `freqtrade/user_data/config.json` | 41 | Separate Freqtrade pair config | NO |
| `freqtrade/user_data/config_nfi.json` | 41,64 | Separate Freqtrade pair config | NO |
| `freqtrade/user_data/strategies/verify.py` | 22 | Separate strategy verification fixture | NO |
| `openspec/changes/structure-research-v5-foundation/design.md` | 16 | BTC macro-research scope | NO |
| `openspec/changes/structure-research-v5-foundation/proposal.md` | 4,22 | BTC macro-research scope | NO |
| `openspec/changes/structure-research-v5-foundation/specs/atomic-market-data-and-macro-leg-analysis/spec.md` | 9-11 | BTC macro-research contract | NO |
| `openspec/changes/structure-research-v5-foundation/specs/bounded-source-access/spec.md` | 9 | BTC macro-research contract | NO |
| `openspec/changes/structure-research-v5-foundation/specs/macro-trade-boundary-refinement/spec.md` | 31 | BTC macro-research contract | NO |
| `openspec/changes/structure-research-v5-foundation/specs/research-objective/spec.md` | 5,41,43,47,53,56 | BTC macro-research objective | NO |
| `openspec/changes/structure-research-v5-foundation/specs/source-contract/spec.md` | 1,5,13,15,16,22,123,124,151-155,159-162 | BTC source contract/filenames | NO |
| `openspec/changes/structure-research-v5-foundation/tasks.md` | 35 | BTC macro-research task | NO |
| `research/backtester_v2/README.md` | 3,126 | V2 BTC baseline documentation/smoke | NO in V2; V3 docs YES |
| `research/backtester_v2/data.py` | 7 | Import from BTC-named pipeline | YES |
| `research/backtester_v2/tests/test_audit_regressions.py` | 63 | V2 BTC fixture | NO in V2; additive V3 tests |
| `research/backtester_v2/tests/test_data_output.py` | 67 | V2 BTC fixture | NO in V2; additive V3 tests |
| `research/btc_macro_nautilus/binance_funding/CONTRACTS.md` | 1,6 | BTC funding contract | NO |
| `research/btc_macro_nautilus/binance_funding/README.md` | 1,6,9,16,19 | BTC funding instructions | NO |
| `research/btc_macro_nautilus/binance_funding/collect_binance_funding.py` | 657,742,762 | BTC diagnostic/bootstrap/default | Conditional YES |
| `research/btc_macro_nautilus/binance_funding/test_collect_binance_funding.py` | 48,61,62,65,75,78,79,82,92,114,115,142-146,162,178 | BTC collector fixtures | NO in baseline; additive V3 tests |
| `research/btc_macro_nautilus/binance_funding/validate_binance_funding.py` | 19,48,58 | BTC-only validator/path | New generic V3 validator YES |
| `research/btc_macro_nautilus/canonical_candles/build_canonical_futures_candles.py` | 2,32,62,940,1001 | BTC constants/output paths | Preserve legacy; new V3 resolver YES |
| `research/btc_macro_nautilus/coinalyze_derivatives/CONTRACTS.md` | 1,3,13,24,32,39,55,57,64,69 | Separate BTC derivatives contract | NO |
| `research/btc_macro_nautilus/coinalyze_derivatives/README.md` | 1,4,20,28,40 | Separate BTC derivatives instructions | NO |
| `research/strategy_replications/STRATEGY_SPEC_TEMPLATE.md` | 122 | Explanatory BTC example | OPTIONAL |
| `research/strategy_replications/tests/test_enforcement.py` | 576 | BTC fixture | Additive V3 tests |
| `research/strategy_replications/tests/test_production_runner_v2.py` | 46,109 | BTC data/request fixture | Additive V3 tests |
| `research/strategy_replications/tests/test_remediation_adversarial.py` | 330,383,469 | BTC fixture | Additive V3 tests |
| `step_2/post_macro_analysis_plan.md` | 119,223 | BTC macro-analysis plan | NO |
| `workers/btc-derivatives-collector/README.md` | 1,3,8,11,105,106,111 | Separate BTC collector | NO |
| `workers/btc-derivatives-collector/migrations/0001_initial_schema.sql` | 2 | Separate worker schema name | NO |
| `workers/btc-derivatives-collector/package-lock.json` | 2,8 | Package identity | NO |
| `workers/btc-derivatives-collector/package.json` | 2,4 | Package identity | NO |
| `workers/btc-derivatives-collector/src/constants.ts` | 4,5 | BTC discovery scope/exchanges | NO |
| `workers/btc-derivatives-collector/src/discovery.ts` | 46,175,176,278,305,326 | BTC base-asset selection | NO |
| `workers/btc-derivatives-collector/src/index.ts` | 19 | BTC worker service name | NO |
| `workers/btc-derivatives-collector/test/coinalyze-client.test.ts` | 41,72,94,107,129,134 | BTC worker fixtures | NO |
| `workers/btc-derivatives-collector/test/collector.test.ts` | 137,140,141,165,166,168,184,191,202,240,261,270,271,273,303,316,317,319,333,339,345,414,415,417,452,461,462,464,490,499,500,502,530,545,559,580,598,617,635,649,652,659,666,668,669,692,693,695,723,737,739,740,805,806,808,852,854,855,883,899,900,989,991,992,1015,1036 | BTC worker fixtures | NO |
| `workers/btc-derivatives-collector/test/discovery.test.ts` | 22,47,49-52,59-61,82,85,86,116,117,130,131,142,143,154-156,165,167,178,180,189,191,192,203,205,206,214,270,282,290,300,315,376,385,389,394,427,442,477,478,484,491-493,497,504,512,517,518,520,521,529,532,534,536,540,542,548,550,556 | BTC discovery fixtures | NO |
| `workers/btc-derivatives-collector/test/health.test.ts` | 25 | BTC worker fixture | NO |
| `workers/btc-derivatives-collector/test/normalizer.test.ts` | 6,9,10,28,63,90,110,151,196,218,240 | BTC worker fixtures | NO |
| `workers/btc-derivatives-collector/wrangler.toml` | 1,10 | BTC worker deployment identity | NO |

## Appendix B: explicit negative findings

- No literal `BTCUSDT` occurs in `research/backtester_v2/engine.py`.
- No production strategy implementation in this checkout hardcodes BTCUSDT.
- No symbol-aware Mark Price loader exists.
- No instrument metadata/precision loader exists.
- No receipt field represents the traded instrument symbol.
- No SQLite run-state column represents the traded instrument symbol.
- No ETHUSDT or SOLUSDT local production dataset was found.
- No V3-A branch/worktree existed before the approved creation in this task.
