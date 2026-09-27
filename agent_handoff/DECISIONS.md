# Decisions

Only explicit decisions for this project/task belong here. Do not generalize these decisions to unrelated tasks.

## 2026-09-27 — derivatives collector architecture

- Derivatives data will be added as a separate research/context layer around existing price-action events.
- Existing PA research remains intact unless a future task explicitly changes it.
- V1 metrics: Open Interest, long/short liquidations, funding rate, predicted funding rate.
- CVD is excluded from V1.
- Binance, Bybit, and OKX remain source-separated initially.
- Missing/unavailable values are not zeros.
- Cross-exchange funding is not to be silently averaged.
- Coinalyze is the current primary intraday source for the first collector implementation.
- Collection must not depend on the user's Mac being online.
- Current cloud target: Cloudflare Worker + Cloudflare D1.
- Scheduled collection target: every 10 minutes with overlap/catch-up and idempotent writes.
- Cloudflare secret name: `COINALYZE_API_KEY`.
- Local `.env` contains the API key and must remain ignored by Git.
- Standard Cloudflare/Create Cloudflare/Wrangler tooling is approved for this isolated Worker subproject; other new dependencies still require explicit approval.

## 2026-09-27 — historical third-party dataset

- `ErcinDedeoglu/crypto-market-data` may be evaluated as a coarse daily historical context layer.
- It must not be treated as authoritative until validated against overlapping data from a better-provenanced source.
- Its upstream provider is currently unverified; provenance must say `unknown` unless evidence establishes otherwise.
- Its embedded `trading_signal` metadata is not accepted as project trading logic.
- Current incomplete daily buckets must not be treated as completed daily observations.

## 2026-09-27 — multi-agent workflow

- Codex and Antigravity may alternate on the same project through repository handoff files.
- One implementation owner at a time per task/file scope.
- Prefer one agent implementing and the other independently reviewing.
- Do not let two agents concurrently edit the same active task scope without explicit approval.
- Critical task state must live in the repository handoff files rather than only in an agent chat.
