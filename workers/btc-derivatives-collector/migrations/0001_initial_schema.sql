-- 0001_initial_schema.sql
-- Migration 0001: Initial schema for BTC derivatives collection from Coinalyze

-- 1. Discovered markets catalog / cache
CREATE TABLE IF NOT EXISTS discovered_markets (
  coinalyze_symbol TEXT PRIMARY KEY,
  exchange TEXT NOT NULL,
  exchange_code TEXT NOT NULL,
  symbol_on_exchange TEXT NOT NULL,
  base_asset TEXT NOT NULL,
  quote_asset TEXT NOT NULL,
  margined TEXT NOT NULL,
  is_perpetual INTEGER NOT NULL,
  expire_at INTEGER NOT NULL,
  oi_lq_vol_denominated_in TEXT NOT NULL,
  availability_flags_json TEXT NOT NULL,
  selected INTEGER NOT NULL,
  selection_policy TEXT NOT NULL,
  selection_reason TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL
);

-- 2. Raw response audit envelopes (Strictly no secrets)
CREATE TABLE IF NOT EXISTS raw_envelopes (
  request_id TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status_code INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL
);

-- 3. Normalized derivative observations
CREATE TABLE IF NOT EXISTS normalized_derivatives (
  timestamp_utc INTEGER NOT NULL,
  exchange TEXT NOT NULL,
  coinalyze_symbol TEXT NOT NULL,
  symbol_on_exchange TEXT NOT NULL,
  interval TEXT NOT NULL,
  source TEXT NOT NULL,
  dataset TEXT NOT NULL,
  oi_usd REAL,
  long_liquidations_usd REAL,
  short_liquidations_usd REAL,
  funding_rate REAL,
  predicted_funding_rate REAL,
  availability_state TEXT NOT NULL,
  raw_request_id TEXT NOT NULL,
  collected_at_utc TEXT NOT NULL,
  PRIMARY KEY (
    timestamp_utc,
    exchange,
    coinalyze_symbol,
    interval,
    dataset,
    source
  )
);

CREATE INDEX IF NOT EXISTS idx_normalized_lookup
ON normalized_derivatives (coinalyze_symbol, dataset, interval, timestamp_utc);

-- 4. Sync checkpoints for idempotent incremental catch-up
-- Separates coverage watermark (covered_through_utc) from actual observation timestamp
CREATE TABLE IF NOT EXISTS sync_checkpoints (
  checkpoint_key TEXT PRIMARY KEY,
  dataset TEXT NOT NULL,
  coinalyze_symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  covered_through_utc INTEGER NOT NULL,
  last_observation_timestamp_utc INTEGER,
  updated_at_utc TEXT NOT NULL
);

-- 5. Collection runs audit log (V1 creates scheduled runs only)
CREATE TABLE IF NOT EXISTS collection_runs (
  run_id TEXT PRIMARY KEY,
  trigger_type TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at_utc TEXT NOT NULL,
  completed_at_utc TEXT,
  rows_inserted INTEGER NOT NULL DEFAULT 0,
  error_message TEXT
);
