# Backtest Methodology

## Status

Canonical research protocol for testing external and internally developed trading strategies in this repository.

This document extends `AGENTS.md`. If a conflict exists, the stricter causality, provenance, validation, and reproducibility rule applies unless the user explicitly approves an exception.

---

## 1. Two strategy tracks must remain separate

### Track A — External strategy replication

Use this track when testing a strategy whose rules already exist outside this project.

Before viewing results, freeze:

- exact entry rules;
- exact exit rules;
- parameters;
- timeframe;
- instrument/market;
- position sizing;
- order type assumptions;
- fee/funding/slippage assumptions;
- any author-defined filters.

A pure replication run is not a development run and does not use walk-forward optimization.

If any parameter, filter, or rule is changed after inspecting results, the result must be labeled as a new **adaptation** and must no longer be reported as pure replication.

### Track B — Internal / adapted strategy development

Use this track for strategies created from project data or materially modified from an external strategy.

These strategies require explicit development, validation, and final untouched evaluation stages.

Never mix replication results with adaptation/development results.

---

## 2. Look-ahead bias is a critical failure

A signal at time `t` may use only information that was actually available at time `t`.

Examples of prohibited behavior:

- calculating a signal on a candle close and filling the trade at that same close when that close was not yet known;
- using future bars in indicators, labels, filters, pivots, swing definitions, or regime classification;
- using retrospective structure as if it were causal;
- entering or exiting at prices that could not have been known or submitted at the decision time.

The backtest engine must make signal time and earliest legal execution time explicit.

Causality must be covered by dedicated tests.

A detected look-ahead violation invalidates the affected backtest.

---

## 3. Rule overfitting must be tracked explicitly

Changing the logic after observing historical results creates a new hypothesis.

Every material strategy revision must receive a new version identifier, for example:

- `strategy_v1`
- `strategy_v2`
- `strategy_v3`

Do not silently improve a historical strategy result by adding filters after seeing where it failed.

For each version, record:

- what changed;
- why it changed;
- which data had already been inspected when the change was made;
- which future period remains genuinely unseen.

A period that influenced rule design is no longer out-of-sample for that strategy version.

---

## 4. Multiple-testing and selection bias

Testing many strategies, parameters, filters, or variants increases the probability of selecting a false positive.

Therefore:

- record every tested strategy/variant, including failures;
- do not report only the best survivor;
- record the size of parameter grids or search spaces;
- distinguish pre-specified tests from exploratory searches;
- reserve a genuinely untouched final period for finalists when strategy selection has occurred;
- treat repeated inspection of the same validation period as additional fitting pressure.

The final test is not only a test of one strategy. It also protects against selection bias created by choosing winners from many candidates.

---

## 5. Data split for internally developed/adapted strategies

The chronological split must be fixed before strategy selection or parameter tuning on the protected periods.

Default conceptual stages:

1. **Development** — hypothesis formation and permitted tuning.
2. **Validation** — evaluation of frozen candidate versions.
3. **Final untouched test** — opened only after strategy rules and selection criteria are frozen.
4. **Paper trading** — forward observation after historical testing.

Exact date boundaries are a project decision and must be approved before use.

Do not choose boundaries retrospectively because they make a strategy look better.

---

## 6. Walk-forward testing

Walk-forward testing applies to internally developed or adapted strategies when repeated calibration is part of the intended real-world process.

The run must explicitly declare whether it uses:

- expanding windows;
- rolling windows;
- fixed parameter transfer;
- scheduled re-optimization.

For every window, record:

- training/development range;
- parameter-selection rule;
- next out-of-sample range;
- parameters transferred into that range;
- pass/fail result.

Do not change the walk-forward procedure after seeing later-window results without creating a new methodology/version.

Pure external-strategy replication does not require walk-forward optimization.

---

## 7. Execution model must be explicit

Each strategy must define the legal execution model before testing.

At minimum specify:

- market, limit, post-only/maker, or other order type;
- signal timestamp;
- order submission timestamp;
- earliest possible fill timestamp;
- fill-price rule;
- stop-loss execution rule;
- take-profit execution rule;
- time exit, if applicable;
- partial fills, if modeled;
- position sizing;
- leverage;
- simultaneous-position policy.

Do not assume that a touched limit price always fills.

Maker execution must model fill uncertainty separately from fee savings.

---

## 8. Intrabar ambiguity on OHLC data

One-minute OHLCV does not reveal the exact price path inside the candle.

If entry, stop, and/or target can all be touched within the same candle, the order of events may be unknowable from 1m OHLCV alone.

The strategy must use one of the following pre-declared approaches:

1. conservative deterministic ordering;
2. mark the trade as ambiguous and exclude it from definitive claims;
3. resolve only the ambiguous trades using finer-grained trade/tick data when available and explicitly authorized.

Never silently choose the intrabar path that improves performance.

If strategy profitability materially depends on unresolved intrabar ordering, 1m OHLCV is insufficient for a definitive conclusion.

---

## 9. Fees, funding, spread, and slippage

Trading costs must be applied at trade level, not added only as a final summary adjustment.

The model must distinguish, where applicable:

- maker fees;
- taker fees;
- spread;
- slippage;
- funding payments/receipts;
- borrow or financing costs for markets where relevant.

Do not hardcode a single fee value as universally valid.

Fee and funding assumptions must be attributable to the tested market/product/account assumptions and, where material, the relevant historical regime.

If a zero-fee or maker-rebate condition is assumed, it must be explicitly documented and tested separately from standard-cost execution.

Gross and net performance must both be reported.

---

## 10. Liquidity and fill realism

Especially on short timeframes, a theoretical signal is not sufficient evidence of executable profit.

Where relevant, evaluate:

- trade size relative to available liquidity;
- likely spread;
- slippage sensitivity;
- order type;
- missed limit orders;
- adverse selection on maker fills;
- latency assumptions if the strategy depends on fast reaction.

A strategy that survives only under unrealistic fills must not be classified as validated.

---

## 11. Metrics must be frozen before finalist selection

Do not define success after seeing the result.

Each experiment must declare its primary and secondary metrics before finalist selection.

Recommended core metrics:

- net P&L / return after all modeled costs;
- expectancy per trade;
- maximum drawdown;
- return-to-drawdown ratio;
- profit factor;
- Sharpe ratio where meaningful;
- win rate;
- average win / average loss;
- number of trades;
- exposure;
- turnover;
- average holding time;
- fee/cost share of gross profit;
- worst losing streak;
- performance by year;
- performance by market regime where regime labels are causally available;
- parameter sensitivity/stability.

No single metric is sufficient by itself.

---

## 12. Sample size and dependence

The number of candles is not the effective sample size.

Report at minimum:

- total trades;
- trades by year/period;
- trades by relevant regime/session when applicable;
- clustering/concentration of trades;
- concentration of profit in a small number of trades.

Do not use an arbitrary universal minimum trade count as proof of validity.

Where feasible, report uncertainty or confidence intervals and use methods that respect serial dependence rather than assuming independent trades.

A result based on many highly correlated trades may contain less independent evidence than a smaller but more diverse sample.

---

## 13. Strategy version and experiment record

Every material backtest must preserve:

- strategy name and version;
- source type: `external_replication`, `external_adaptation`, or `internal`;
- source/reference for external rules;
- code commit;
- input dataset fingerprint/manifest;
- market, symbol, contract type, timeframe, timezone;
- tested date range;
- data split role;
- execution assumptions;
- fee/funding/slippage assumptions;
- parameter values;
- metrics;
- trade count;
- QA status;
- known limitations;
- whether any protected period had been inspected previously.

Failed and rejected experiments must also remain in the research record.

---

## 14. Acceptance and rejection must be pre-declared

Before comparing finalists, define what qualifies a candidate to advance.

The criteria may include thresholds or relative comparison rules, but they must be frozen before viewing the protected evaluation results.

Do not move thresholds after seeing which strategy almost passed.

If criteria are changed, create a new evaluation version and treat the previously viewed data as no longer untouched.

---

## 15. First-stage workflow for external strategies

For the current research program, use this sequence:

1. collect 10–15 external strategy candidates;
2. record the original source and exact original rules;
3. classify each candidate as directly testable on existing 1m OHLCV or requiring additional data;
4. freeze the replication specification before running it;
5. run replication with realistic execution/cost assumptions;
6. retain all results, including failures;
7. only after replication, decide whether a separate adaptation experiment is justified;
8. keep replication and adaptation results separate;
9. compare finalists using pre-declared metrics;
10. move historically robust finalists to paper trading.

Do not use the later 80+ regime features for the first replication phase unless a specific external strategy requires them.

---

## 16. Critical invalidation conditions

A backtest is invalid or `NOT VERIFIED` if any material result depends on:

- look-ahead leakage;
- unknown or fabricated source data;
- unresolved provenance;
- unacknowledged spot/futures mixing;
- future-informed regime/structure labels;
- impossible execution timing;
- optimistic unresolved intrabar ordering;
- silently omitted costs that are material to the strategy;
- stale artifacts presented as current-run outputs;
- incomplete coverage presented as complete;
- post-hoc rule changes reported as if they belonged to the original frozen strategy.

Such a run must not be used as evidence that a strategy works.

---

## 17. Principle for interpretation

A profitable historical equity curve is a research observation, not proof of a durable edge.

Confidence should increase only when a strategy survives:

- correct causal implementation;
- realistic execution and costs;
- multiple market conditions;
- protected out-of-sample evaluation where applicable;
- sensitivity checks;
- and subsequent paper trading.
