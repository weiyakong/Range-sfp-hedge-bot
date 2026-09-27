export type DatasetName =
  | "open_interest"
  | "liquidations"
  | "funding_rate"
  | "predicted_funding_rate";

export type TargetExchange = "Binance" | "Bybit" | "OKX";

export interface Env {
  DB: D1Database;
  COINALYZE_API_KEY?: string;
  ENVIRONMENT?: string;
}

export interface RawMarket {
  symbol: string;
  exchange: string;
  symbol_on_exchange: string;
  base_asset: string;
  quote_asset: string;
  is_perpetual: boolean;
  margined: string;
  expire_at: number;
  oi_lq_vol_denominated_in: string;
  [key: string]: unknown;
}

export interface ExchangeCatalogEntry {
  name: string;
  code: string;
}

export interface DiscoveredMarket {
  coinalyze_symbol: string;
  exchange: string;
  exchange_code: string;
  symbol_on_exchange: string;
  base_asset: string;
  quote_asset: string;
  margined: string;
  is_perpetual: boolean;
  expire_at: number;
  oi_lq_vol_denominated_in: string;
  availability_flags: Record<string, boolean>;
  selected: boolean;
  selection_policy: string;
  selection_reason: string;
  updated_at_utc?: string;
}

export interface NormalizedDerivativeRow {
  timestamp_utc: number; // Unix epoch seconds
  exchange: string;
  coinalyze_symbol: string;
  symbol_on_exchange: string;
  interval: string;
  source: string;
  dataset: DatasetName;
  oi_usd: number | null;
  long_liquidations_usd: number | null;
  short_liquidations_usd: number | null;
  funding_rate: number | null;
  predicted_funding_rate: number | null;
  availability_state: "available" | "source_null";
  raw_request_id: string;
  collected_at_utc: string; // ISO 8601
}

export interface SyncCheckpoint {
  checkpoint_key: string; // `${dataset}:${coinalyze_symbol}:${interval}`
  dataset: DatasetName;
  coinalyze_symbol: string;
  interval: string;
  covered_through_utc: number;
  last_observation_timestamp_utc: number | null;
  updated_at_utc: string;
}

export interface RawEnvelope {
  request_id: string;
  endpoint: string;
  params_json: string;
  status_code: number;
  payload_json: string;
  created_at_utc: string;
}

export interface CollectionRun {
  run_id: string;
  trigger_type: "scheduled";
  status: "in_progress" | "success" | "partial" | "failed";
  started_at_utc: string;
  completed_at_utc: string | null;
  rows_inserted: number;
  error_message: string | null;
}
