# C001 / Strategy 1A — Time-Series Momentum Owner Decisions V1

Date: 2026-10-03
Status: approved owner decisions; implementation/freeze/testing still required
Backtester: V3-A, one instrument per run
First instrument: BTCUSDT Binance USD-M perpetual

## Source variant

Strategy 1A is the classic Moskowitz–Ooi–Pedersen (2012) Time-Series Momentum methodology, adapted only where necessary to execute it on BTCUSDT perpetual futures.

The goal of 1A is source-faithful replication/transfer. Do not introduce crypto-specific signal optimization into 1A.

A separate later variant, 1B, will test the Bitcoin-specific Kang–Ryu (2026) formulation. Results or settings from 1B must not be used to rewrite 1A after seeing results.

## Signal

- Signal input: price only.
- Funding must not enter the signal.
- Direction at each rebalance is the sign of the 12-month price return.
- Conceptual formula: `sign(Close_month_end_t / Close_month_end_(t-12m) - 1)`.
- Positive 12-month return => long direction.
- Negative 12-month return => short direction.
- Any exact zero-return/tie handling that is not fixed by source methodology must be made explicit before the run; do not silently choose a rule.

## Rebalance and causality

- Rebalance frequency: calendar month-end.
- The signal is determined only after the last available minute of the calendar month has closed.
- The earliest permitted execution is the first available minute of the next calendar month.
- No same-close execution and no use of future information.

## Volatility scaling

Retain the original methodology for the source-faithful 1A variant:

- volatility input: daily returns;
- estimator: EWMA;
- EWMA center of mass: 60 days;
- annualization factor: 261;
- target annualized volatility: 40%;
- exposure conceptually scales as `0.40 / sigma` using only information available at that time.

The 261 annualization factor is deliberately retained for 1A even though BTC trades every day. A 365-day adaptation would be a different variant and must not silently replace 1A.

## Leverage variants

Run three parallel variants with all other rules identical:

- **1A-BASE** — source sizing; no additional research leverage cap.
- **1A-CAP2** — same strategy with exposure capped at 2× equity.
- **1A-CAP3** — same strategy with exposure capped at 3× equity.

Do not tune these caps after observing results.

## P&L and execution costs

Actual backtest P&L must include:

- trading fees;
- slippage under the frozen execution model;
- actual funding payments/receipts from the official Binance funding history.

Funding changes realized P&L only. It does not change the 12-month momentum signal.

## BTC data authority for first run

Canonical BTCUSDT trade-price authority currently remains:

`/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/manifests/strict_futures_1m_manifest.json`

Its current canonical window is:

- start: `2019-09-08T17:57:00Z`;
- end: `2026-09-25T23:59:00Z`;
- one known real missing minute: `2019-09-08T19:00:00Z`.

Official Binance BTCUSDT funding already exists under the symbol-aware data root. Do not substitute Coinalyze or another provider into the primary funding series.

V3-A data contracts remain fail-closed. If Mark Price or instrument metadata required by the real execution path are not yet available with sufficient provenance/coverage, the production historical run must stop and report the blocker rather than use trade-price or other silent proxies.

## First-test sequence

1. Validate BTCUSDT through the full real V3-A data/execution/receipt/revalidation chain.
2. Freeze the executable 1A specification and its exact parameter identities.
3. Run BTCUSDT 1A-BASE, 1A-CAP2 and 1A-CAP3 under identical signal/execution assumptions except for the stated leverage cap.
4. Preserve complete outputs and diagnostics before interpreting performance.
5. Do not optimize or modify the strategy in response to the first BTC results.

## Not yet authorized

- No coin-specific tuning.
- No 365-day annualization substitution for 1A.
- No funding-based signal.
- No same-close execution.
- No silent Mark Price proxy.
- No silent change in fee/slippage assumptions.
- No parameter search based on observed BTC results.
