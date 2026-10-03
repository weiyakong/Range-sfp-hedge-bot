# Research Strategy Universe and Owner Decisions V1

Date: 2026-10-03
Branch: `backtester-v3a`
Repository: `https://github.com/weiyakong/Range-sfp-hedge-bot`
Methodology: `https://github.com/weiyakong/Range-sfp-hedge-bot/blob/backtester-v2/docs/backtest-methodology.md`

## Purpose

This document records the strategy universe selected for the research program and the owner decisions that must not be silently changed during implementation or testing.

The strategies are external/known strategies selected for replication and testing. They are separate from the project's earlier SFP/VAH/VAL/POC/CVD ideas.

## Selected strategy universe

1. Time-Series Momentum / Trend Following
2. Moving-Average / Channel Breakout
3. Cross-Sectional Momentum
4. Residual Momentum
5. 52-Week-High Momentum
6. Short-Term Reversal / Liquidity Provision
7. Pairs / Statistical Arbitrage
8. Crypto Funding / Basis Arbitrage
9. Intraday Momentum
10. Post-Earnings-Announcement Drift (PEAD)
11. Volatility-Managed Momentum / Trend
12. False-Break / Breakout-Failure
13. Opening-Range Breakout (ORB) — retained as a negative control

## Program decisions

- Do not remove a candidate because it performs poorly or is difficult to implement.
- Test strategies under frozen rules before using results to decide which candidates advance.
- Development backtests are followed by validation; surviving finalists later receive untouched final validation and paper/forward testing.
- Finalist evaluation considers net P&L after costs, drawdown, trade count, stability by month/regime, parameter robustness, and maker/taker execution sensitivity.
- Strategy-specific exceptions must be explicit and frozen before the corresponding historical run.

## V3-A instrument policy

- V3-A is a symbol-agnostic single-instrument backtester.
- One run tests one symbol.
- The engine is not limited to BTC, ETH, SOL, XRP, HYPE, or any fixed coin list.
- A new compatible Binance USD-M perpetual should be onboarded through data, manifests, metadata, QA and smoke validation without symbol-specific engine logic.
- `symbol` is execution identity from the frozen strategy spec; production runs do not accept a caller-selected symbol override.
- BTCUSDT is the first real instrument used to validate V3-A and to test Strategy 1.
- Additional instruments can be onboarded sequentially after BTC; ETHUSDT, SOLUSDT, XRPUSDT and HYPEUSDT are currently named future examples, not an exhaustive or frozen universe.

## Strategy 1 order

Strategy 1 is Time-Series Momentum / Trend Following.

The first implementation/test is **1A: classic Moskowitz–Ooi–Pedersen (2012) Time-Series Momentum adapted to BTC/crypto execution**.

The planned second variant is **1B: Kang–Ryu (2026) Bitcoin-specific Time-Series Momentum**. It is not to replace or retroactively alter 1A.

Detailed approved owner decisions for 1A are recorded in `strategies/C001_TSMOM_1A_OWNER_DECISIONS_V1.md`.
