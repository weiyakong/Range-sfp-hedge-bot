# BTC Derivatives Collector (Cloudflare Worker + D1)

Isolated Cloudflare Worker for scheduled collection of BTC perpetual derivatives data (Open Interest, Liquidations, Funding Rate, Predicted Funding Rate) from Coinalyze into Cloudflare D1.

## Architecture & Semantics

- **Runtime**: Cloudflare Worker (TypeScript).
- **Persistent Storage**: Cloudflare D1 (`btc-derivatives`, binding `DB`).
- **Trigger**: Cloudflare Cron Trigger scheduled every 10 minutes (`*/10 * * * *`).
- **Auth**: `COINALYZE_API_KEY` provided as Cloudflare Secret. Never logged, never persisted in envelopes or error messages.
- **Dynamic Discovery**: Targets Binance, Bybit, OKX (`where available`). Dynamic discovery via `/v1/future-markets` + `/v1/exchanges`. Selects 1 primary BTC/USDT perpetual per available target exchange (`selection_policy = "primary_usdt_v1"`, `selection_reason = "primary_usdt_perpetual"`, strictly no non-USDT fallback). Cached in D1 for 24 hours.
- **V1 Ingestion**: 1-minute interval observations across 4 datasets:
  - `open_interest` (`/open-interest-history`, converted to USD)
  - `liquidations` (`/liquidation-history`, separated long/short in USD)
  - `funding_rate` (`/funding-rate-history`)
  - `predicted_funding_rate` (`/predicted-funding-rate-history`)

### Initial Bootstrap vs Historical Backfill (CRITICAL)

- **Initial Bootstrap Lookback = 2 hours (120 minute buckets inclusive)**:
  When a checkpoint for a given dataset/symbol does not yet exist in D1, the collector fetches a bounded window of the last 120 minute buckets (`to - 119 * 60` to `to`, where `to = lastClosedMinuteStart`).
- **This is NOT a historical backfill**:
  The Worker is strictly designed for continuous, low-latency forward collection. It will NEVER attempt to download multi-month or multi-year historical data during initial startup or normal runs.
- **Historical backfill is a separate task/pipeline**:
  Deep historical research data is populated via dedicated backfill tools (e.g., local Parquet pipelines).
- **Missing values are NOT zeros**:
  The absence of historical data prior to the bootstrap window in D1 must NEVER be interpreted as zero values. All missing metrics remain `NULL` (`availability_state = 'source_null'`).

### Incremental Catch-up & Dual Watermark Semantics

- **Coverage Watermark (`covered_through_utc`)**: Tracks the exact timestamp up to which the API request window has been successfully checked and saved. This advances even when history is empty (e.g., OKX predicted funding rate returns `[]` or `[{ symbol, history: [] }]`), preventing infinite re-query loops.
- **Last Observation (`last_observation_timestamp_utc`)**: Tracks the timestamp of the latest real *available* market observation (`availability_state = 'available'`). Rows with `source_null` do NOT advance this watermark. Remains `NULL` if no observations were ever returned.
- **Strict Response & Schema Validation**:
  - Malformed JSON responses fail the partition without advancing coverage; raw sanitized response is saved for audit.
  - Expected schema: `[{ symbol: string, history: Array<{ t: number, ... }> }]` or valid empty responses: `[]` or `[{ symbol: string, history: [] }]`.
  - Upstream `symbol` must strictly match the requested symbol; timestamps `t` must be finite integers aligned to 60s and within the requested `[from, to]` window.
- **Closed 1-Minute Boundary (Conservative Causal Lag)**:
  For causal quantitative research pipelines, no ongoing, unclosed 1-minute candle may be marked as complete. The collector enforces an intentional lag of at least one closed minute boundary using a centralized helper `getLastClosedMinuteStart(nowSeconds)`:
  ```ts
  currentMinuteStart = Math.floor(nowSeconds / 60) * 60;
  lastClosedMinuteStart = currentMinuteStart - 60;
  ```
  - At `14:26:29 UTC`, the current minute bucket `[14:26:00, 14:27:00)` is active and unclosed. Target coverage boundary is strictly `14:25:00 UTC`.
  - At `14:26:00 UTC`, target coverage is strictly `14:25:00 UTC`.
  - At `14:26:59 UTC`, target coverage is strictly `14:25:00 UTC`.
  - At `14:27:00 UTC`, the 14:26 candle has closed, and target coverage advances to `14:26:00 UTC`.
  - Invariant: `covered_through_utc <= lastClosedMinuteStart` is guaranteed across all checkpoints.
- **Normal Overlap**: 20 minutes lookback prior to coverage watermark (`covered_through_utc - 1200s`) to ensure revised liquidations and late funding prints are captured.
- **Max Catch-up per Run**: Capped at 360 minute buckets inclusive (`from + 359 * 60`), strictly bounded by `lastClosedMinuteStart`. If collection was interrupted for > 6 hours, each 10-minute cron run catches up by advancing one 6-hour chunk of coverage without skipping failures.
- **Atomic Discovery Snapshot**:
  - Validates discovery catalog before updating D1. Replaces active discovery state via an atomic transaction (`DELETE FROM discovered_markets` + `INSERT`). Stale markets not in the new snapshot disappear automatically.
  - If discovery refresh fails but cached snapshot exists, uses cached snapshot and flags run as degraded/partial.
  - Zero selected markets fails the run immediately.
- **Error Preservation**: If a request or write fails, `covered_through_utc` is NOT advanced for that partition.

### Run Telemetry & Endpoints

- **V1 Scheduled Runs**: All collection runs are logged to table `collection_runs` with `trigger_type = 'scheduled'`.
- **Public Endpoint**: Strictly `GET /health` only (returns 200 JSON). All other paths (including `/`) return 404; non-GET requests to `/health` return 405. Does not touch DB or external APIs.

---

## Local Development & Testing

### 1. Install Dependencies
```bash
npm install
```

### 2. Type Check
```bash
npm run build
```

### 3. Run Unit Tests
```bash
npm test
```

### 4. Apply Local D1 Migrations
```bash
npm run migrate:local
```

### 5. Local Dev Server & Smoke Test
```bash
# Start local dev server with scheduled test route enabled
npx wrangler dev --port 8787 --test-scheduled

# Health check (should return 200 OK with status: healthy)
curl http://localhost:8787/health

# Trigger scheduled collection handler locally via wrangler dev test route
# (Do NOT use 'npx wrangler scheduled', which is deprecated/unsupported for local testing)
curl http://localhost:8787/__scheduled
# or:
curl http://localhost:8787/cdn-cgi/local/scheduled
```

---

## First Remote Deployment Instructions

Existing Cloudflare resources:
- Worker: `btc-derivatives-collector`
- D1: `btc-derivatives`
- Binding: `DB`
- Secret: `COINALYZE_API_KEY`

When authorized to perform remote deployment:
1. Obtain the real database ID for existing D1 `btc-derivatives`:
   ```bash
   npx wrangler d1 list
   ```
2. Replace `DEPLOY_TIME_D1_DATABASE_ID` in `wrangler.toml` with the actual database ID.
3. Apply migrations to the remote D1 database:
   ```bash
   npx wrangler d1 migrations apply DB --remote
   ```
4. Deploy the Worker:
   ```bash
   npx wrangler deploy
   ```
