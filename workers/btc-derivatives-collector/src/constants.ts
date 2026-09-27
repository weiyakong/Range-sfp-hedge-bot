import { DatasetName, TargetExchange } from "./types";

export const BASE_URL = "https://api.coinalyze.net/v1";
export const SCHEMA_VERSION = "coinalyze-btc-derivatives-v1";
export const COLLECTOR_VERSION = "btc-derivatives-collector-v1";
export const SELECTION_POLICY = "primary_usdt_v1";
export const PRIMARY_USDT_SELECTION_REASON = "primary_usdt_perpetual";
export const ALTERNATIVE_SELECTION_REASON = "alternative_perpetual";

export const TARGET_EXCHANGES: readonly TargetExchange[] = ["Binance", "Bybit", "OKX"];

export const DEFAULT_INTERVAL = "1min";
export const DISCOVERY_CACHE_SECONDS = 24 * 60 * 60; // 24 hours

// Timing bounds (V1 continuous cloud collector)
// NOTE: Initial Bootstrap Lookback = 2 hours applies ONLY to continuous cloud collector
// catch-up when starting fresh. It is NOT a substitute for historical backfill!
// Coinalyze from/to are inclusive. For interval=1min:
// 2 hours = 120 buckets -> span = (120 - 1) * 60 = 119 * 60 = 7140 seconds
export const BOOTSTRAP_INCLUSIVE_SPAN_SECONDS = (120 - 1) * 60;
export const BOOTSTRAP_LOOKBACK_SECONDS = BOOTSTRAP_INCLUSIVE_SPAN_SECONDS;

export const NORMAL_OVERLAP_SECONDS = 20 * 60; // 20 minutes

// 6 hours = 360 buckets -> span = (360 - 1) * 60 = 359 * 60 = 21540 seconds
export const MAX_CATCHUP_INCLUSIVE_SPAN_SECONDS = (360 - 1) * 60;
export const MAX_CATCHUP_PER_RUN_SECONDS = MAX_CATCHUP_INCLUSIVE_SPAN_SECONDS;

export const DATASET_ENDPOINTS: Record<DatasetName, string> = {
  open_interest: "open-interest-history",
  liquidations: "liquidation-history",
  funding_rate: "funding-rate-history",
  predicted_funding_rate: "predicted-funding-rate-history",
};

export const USD_DATASETS: ReadonlySet<DatasetName> = new Set([
  "open_interest",
  "liquidations",
]);
