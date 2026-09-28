# Backtester V2

Purpose: transparent strategy-agnostic historical simulation on canonical BTCUSDT USDT-M data.

V2 is a clean successor to rejected V1. V1 remains unchanged for audit comparison.

## Core causal contract

- strategy callback runs after the current bar has been fully processed;
- market signals can execute no earlier than the next bar open;
- input timestamps must be strictly increasing;
- strategy receives immutable `StrategyState` only;
- at most one intent per side is accepted per bar;
- long and short legs may coexist in hedge mode;
- repeated same-side entry (pyramiding) is rejected;
- GTC/IOC semantics are explicit for limit orders.

## Execution

- long/short;
- market and limit entries;
- marketable limits use the taker model and adverse slippage, with the limit
  price retained as a hard cap;
- passive limits use configurable `touch` or `strict_through` policy;
- GTC limits persist; IOC limits expire after one attempt;
- a passive limit fill may be followed by a same-bar take-profit when that
  TP is causally reachable after the fill on every relevant admissible OHLC
  path (`O→H→L→C` and `O→L→H→C`); when the two paths disagree about
  whether the TP is reached after the fill, V2 selects the conservative
  worst admissible outcome and records the event in `intrabar_ambiguities.csv`;
  it never assumes a favorable same-bar TP solely from the candle high/low;
- adverse same-bar stop after passive fill remains eligible;
- stop gaps execute from first available bar open plus adverse slippage.
- ordinary capacity failures are persisted as `ORDER_REJECTED` with
  `INSUFFICIENT_CROSS_MARGIN`; they do not abort the run;
- passive fills preserve `entry_bar_time`, `entry_time_exact=null`, and
  `fill_time_resolution="bar"` rather than inventing an exact fill timestamp.
## Funding

- funding rates are keyed by exact timestamp;
- default mode requires an explicit funding price for each funding event;
- `bar_open` funding price is available only as an explicitly selected approximation;
- positions opened on a funding timestamp do not pay that event;
- positions still open at that timestamp pay/receive funding before an exit at the same timestamp.

## Cross margin and liquidation

V2 supports `cross` margin only.

Liquidation uses:
- explicit leverage;
- configurable maintenance-margin tiers;
- maintenance amount/deduction per tier;
- separate Mark Price OHLC;
- configurable liquidation fee.

A leveraged liquidation run without complete Mark Price OHLC is rejected.
The engine does not silently substitute last-trade candles for Mark Price.

V2 models hedge-mode cross margin with one long leg and one short leg per symbol. Both legs share the same wallet balance, account equity, maintenance-margin test, and liquidation event. Initial margin requirement is the sum of long-side and short-side requirements. Pyramiding within a side is intentionally out of scope.

Every fill is capacity-checked after its actual modeled fill price, fee, and
immediate unrealized PnL are known. Intrabar exposure changes (fill, stop,
target, or liquidation) cause maintenance margin to be recomputed for the
remaining path. Both `O→H→L→C` and `O→L→H→C` paths are evaluated; the lower
equity admissible result is retained. Differing outcomes are logged as
`AMBIGUOUS_INTRABAR` in `intrabar_ambiguities.csv`.

Liquidation output distinguishes `liquidation_trigger_price` from
`liquidation_execution_price`. The built-in
`mark_trigger_approximation` uses the trigger as an approximate execution
price; it is not represented as a historical Binance clearing fill.

## End of data and metrics

- `mark_to_market`: preserves open exposure and reports final equity including unrealized PnL;
- `force_close`: closes at final close under the configured taker/slippage model;
- metrics include open-position entry fee and funding;
- drawdown is reported separately as
  `close_to_close_max_drawdown_pct` and
  `intrabar_worst_max_drawdown_pct`;
- undefined metrics are JSON `null`, never `Infinity`.

## Run artifacts and verification status

`write_results` writes to a sibling incomplete directory, validates strict
JSON and SHA-256 checksums, and then atomically promotes the complete run. It
refuses to overwrite an existing non-empty run directory. A complete artifact
set contains trades, close and intrabar equity, metrics, full config, exposure
and pending orders, rejected orders, intrabar ambiguities, run metadata, and a
checksum manifest.

Use `build_run_metadata` for material runs. It records strategy identity and
source type, parameters/reference, canonical manifest path and checksum, data
scope, unique run identity/time, Git commit/dirty state, and checksums of the
executed backtester files.

Synthetic engine fixtures may exercise leverage and liquidation, but a real
leveraged run is automatically `NOT VERIFIED` when it lacks the applicable
verified historical Mark Price, funding, maintenance-tier, or liquidation
execution inputs. Missing inputs are listed in `qa_issues`.
## Validation commands

Run all V2 tests:

`python3 -m unittest discover -s research/backtester_v2/tests -v`

Smoke test on canonical BTCUSDT 1m data:

`python3 -m research.backtester_v2.smoke_run`

## Known limitations

- no partial fills or queue-position model;
- one symbol only; no multi-symbol portfolio yet;
- no same-side pyramiding; maximum one long leg plus one short leg;
- no automatic historical funding/Mark Price loader yet;
- liquidation trigger is modeled from supplied Mark Price OHLC and maintenance tiers;
- liquidation clearing price beyond the trigger is not reconstructed from exchange microstructure;
- intrabar fill ordering for passive limits follows a conservative dual-path
  model: when admissible paths disagree on a same-bar protective level,
  the worst admissible outcome is chosen and flagged as `AMBIGUOUS_INTRABAR`;
- no parameter optimizer.

Any run that enables leverage/liquidation without historically appropriate maintenance tiers and Mark Price data must be labeled `NOT VERIFIED`.
