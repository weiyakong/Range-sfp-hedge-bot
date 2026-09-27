# Current project state

Last updated: 2026-09-27

## Repository research state

- Current repository direction is 12H primary macro research / macro-signature research.
- Existing price-action research and prior results are preserved unless an explicit task changes them.
- Parent/child structural hierarchy is not to be presumed before evidence; current macro research precedes such hierarchy decisions.

## Derivatives-data direction

- Derivatives data is an additive research layer around price-action events, not a replacement for the PA research.
- Coinalyze API access has been configured locally through `COINALYZE_API_KEY` in `.env`.
- `.env` is intended to remain ignored by Git and secrets must never be committed or logged.
- V1 derivatives scope: BTC perpetual Open Interest, liquidations, funding rate, predicted funding rate.
- CVD is excluded from V1.
- Binance, Bybit, and OKX data must remain source-separated until a later explicitly approved aggregation study.
- Missing/unavailable data must remain missing/unavailable, never silently become zero.
- Cross-exchange funding must not be silently averaged.

## Historical derivatives sources under consideration

- Coinalyze: primary intraday research source and ongoing collection source.
- Direct exchange APIs: longer OI/funding history where available and later realtime collection.
- `ErcinDedeoglu/crypto-market-data`: third-party daily historical context only after validation against overlapping authoritative data. Its upstream provider is currently unverified and must be recorded as unknown unless proven.

## Infrastructure target

- Always-on collection should not depend on the user's Mac being online.
- Current target architecture: Cloudflare Worker scheduled collection + Cloudflare D1 storage.
- Intended scheduled cadence for Coinalyze collection: every 10 minutes with catch-up/overlap and idempotent writes, while preserving 1-minute observations where the upstream endpoint provides them.
- Cloudflare resources have not yet been created or deployed from this repository.

## Current constraints

- Current task is infrastructure/data collection only. It must not change existing PA business logic or research labels.
- External market-data API use for the current derivatives collector has been explicitly authorized; paid data/API credits have not been authorized.
- Remote GitHub state changes remain governed by `AGENTS.md`.
