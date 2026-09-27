# Current task

Task ID: `DERIV-COLLECTOR-001`

Status: `PLANNED`

Active implementation owner: unassigned

Independent reviewer: unassigned

Last updated: 2026-09-27

## Goal

Prepare an isolated Cloudflare Worker + D1 collector for BTC derivatives context from Coinalyze so collection can continue without the user's Mac being online.

This task is additive infrastructure. Do not change existing price-action research logic, labels, historical conclusions, or unrelated repository behavior.

## Approved data scope

Discover BTC perpetual markets dynamically through the official Coinalyze market-discovery endpoint. Do not guess or hardcode Coinalyze symbol IDs before discovery.

Target exchanges where available in Coinalyze:

- Binance
- Bybit
- OKX

Collect:

- Open Interest history with USD conversion where supported;
- liquidation history with long and short values separated and USD conversion where supported;
- funding-rate history;
- predicted-funding-rate history.

Explicitly out of scope for V1:

- CVD;
- long/short ratio;
- order book;
- TradingView;
- cross-exchange aggregation into a single metric;
- trading/execution actions.

## Intended runtime architecture

- Cloudflare Worker written in TypeScript.
- Cloudflare D1 as persistent storage.
- Scheduled trigger every 10 minutes.
- API key supplied only as Cloudflare secret `COINALYZE_API_KEY` in deployed runtime.
- Local development may read the existing local `.env`, but must never print, copy, commit, or persist the key elsewhere.
- Collector preserves 1-minute upstream observations where available.
- Each run performs catch-up from the last persisted timestamp with a bounded overlap so a missed scheduled run can be repaired while remaining idempotent.

## Storage requirements

Keep source-level provenance. Do not silently mix exchanges.

Provide two logical layers:

1. Raw ingest/audit layer retaining source response/provenance sufficiently to audit normalization.
2. Normalized observations with explicit source, exchange, symbol, metric, interval, UTC timestamp, units, availability/missing state, and ingestion metadata.

Use primary/unique keys that make retries and overlap idempotent.

Do not convert missing/unavailable data to `0`.

All market/event timestamps are UTC.

## Rate-limit/error requirements

- Respect Coinalyze's documented API limits for the account in use.
- Treat batched-symbol accounting according to official documentation, not assumption.
- Handle HTTP 429 explicitly, including `Retry-After` when provided.
- Do not hide upstream failures behind empty successful output.
- Preserve coverage/gap information.

## Implementation sequence

1. Read `AGENTS.md` and all current handoff files.
2. Inspect repository dependency/configuration conventions and choose an isolated subproject location.
3. Before implementation, report intended files, plan, and dependencies.
4. Define D1 schema/contracts and acceptance criteria.
5. Write tests for specified behavior before production implementation where testable.
6. Implement locally.
7. Run unit/integration tests without exposing secrets.
8. Run only a minimal authorized real-data smoke test before any broader backfill.
9. Stop before creating remote Cloudflare resources or deploying unless the user explicitly authorizes that separate action.

## Minimum required tests

- market discovery;
- normalization;
- UTC timestamp handling;
- source/exchange provenance preservation;
- missing values remain missing;
- deduplication/idempotent overlap;
- resume/catch-up from last successful timestamp;
- HTTP 429 / `Retry-After` handling;
- API key is not logged or written to artifacts;
- incomplete coverage cannot be reported as complete.

## Dependency rule

Use existing repository dependencies where possible. Standard Cloudflare/Create Cloudflare/Wrangler tooling for this isolated Worker subproject is approved for this task. Any other new runtime or development dependency requires explicit approval under `AGENTS.md` before addition.

## Stop point / deliverable for first implementation pass

Local implementation only. Before deployment, provide:

- exact files created/changed;
- D1 schema/migrations;
- tests and actual results;
- discovered BTC perpetual symbols from the minimal smoke test if performed;
- unresolved limitations;
- exact proposed commands/actions for Cloudflare login, D1 creation, secret creation, migrations, and first deploy.

Do not create Cloudflare resources, deploy, commit secrets, or change unrelated research in this task pass without separate explicit approval.

## Handoff rule

Whichever agent implements this task must append an implementation entry to `TASK_LOG.md` and set status to `REVIEW_NEEDED` after implementation/tests. The other agent should then perform independent review before further changes.
