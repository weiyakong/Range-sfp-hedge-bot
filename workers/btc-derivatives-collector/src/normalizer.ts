import { DATASET_ENDPOINTS } from "./constants";
import { DatasetName, DiscoveredMarket, NormalizedDerivativeRow } from "./types";

export interface CoinalyzeHistoryItem {
  t: number;
  c?: number | null;
  l?: number | null;
  s?: number | null;
  [key: string]: unknown;
}

export interface CoinalyzeResponseItem {
  symbol: string;
  history: CoinalyzeHistoryItem[];
}

export function normalizeCoinalyzePayload(
  dataset: DatasetName,
  market: DiscoveredMarket,
  interval: string,
  rawRequestId: string,
  collectedAtUtc: string,
  payload: unknown,
  fromTs?: number,
  toTs?: number
): NormalizedDerivativeRow[] {
  if (!Array.isArray(payload)) {
    throw new Error(`Invalid schema: payload must be an array, got ${typeof payload}`);
  }

  // Valid empty series (e.g. OKX predicted funding rate returns [])
  if (payload.length === 0) {
    return [];
  }

  // We queried for a single symbol; receiving multiple symbol blocks is an invalid schema
  if (payload.length > 1) {
    throw new Error(`Unexpected schema: expected 1 symbol block for ${market.coinalyze_symbol}, got ${payload.length}`);
  }

  const block = payload[0] as CoinalyzeResponseItem;
  if (!block || typeof block !== "object") {
    throw new Error(`Invalid schema: response block must be an object`);
  }

  // 1. Symbol validation: must strictly match requested symbol
  if (typeof block.symbol !== "string" || block.symbol !== market.coinalyze_symbol) {
    throw new Error(`Symbol mismatch: expected ${market.coinalyze_symbol}, got ${block.symbol}`);
  }

  // 2. History array validation
  if (!Array.isArray(block.history)) {
    throw new Error(`Invalid schema: block.history must be an array for ${market.coinalyze_symbol}`);
  }

  // Valid empty series with explicit symbol block (e.g. [{ symbol: "...", history: [] }])
  if (block.history.length === 0) {
    return [];
  }

  const endpoint = DATASET_ENDPOINTS[dataset];
  const rows: NormalizedDerivativeRow[] = [];

  for (const item of block.history) {
    if (!item || typeof item !== "object") {
      throw new Error(`Invalid history observation: item must be an object`);
    }

    // 3. Timestamp validation
    if (typeof item.t !== "number" || !Number.isFinite(item.t)) {
      throw new Error(`Invalid timestamp in observation: 't' must be a finite number, got ${item.t}`);
    }

    if (!Number.isInteger(item.t)) {
      throw new Error(`Invalid timestamp in observation: 't' must be an integer, got ${item.t}`);
    }

    if (interval === "1min" && item.t % 60 !== 0) {
      throw new Error(`Invalid timestamp alignment: 't'=${item.t} must be aligned to 60-second boundary`);
    }

    if (fromTs !== undefined && toTs !== undefined) {
      if (item.t < fromTs || item.t > toTs) {
        throw new Error(
          `Timestamp out of requested range: 't'=${item.t} not in [${fromTs}, ${toTs}] for ${market.coinalyze_symbol}`
        );
      }
    }

    let oi_usd: number | null = null;
    let long_liquidations_usd: number | null = null;
    let short_liquidations_usd: number | null = null;
    let funding_rate: number | null = null;
    let predicted_funding_rate: number | null = null;

    let hasMetric = false;

    if (dataset === "open_interest") {
      if (typeof item.c === "number" && !isNaN(item.c)) {
        oi_usd = item.c;
        hasMetric = true;
      }
    } else if (dataset === "liquidations") {
      if (typeof item.l === "number" && !isNaN(item.l)) {
        long_liquidations_usd = item.l;
        hasMetric = true;
      }
      if (typeof item.s === "number" && !isNaN(item.s)) {
        short_liquidations_usd = item.s;
        hasMetric = true;
      }
    } else if (dataset === "funding_rate") {
      if (typeof item.c === "number" && !isNaN(item.c)) {
        funding_rate = item.c;
        hasMetric = true;
      }
    } else if (dataset === "predicted_funding_rate") {
      if (typeof item.c === "number" && !isNaN(item.c)) {
        predicted_funding_rate = item.c;
        hasMetric = true;
      }
    }

    const availability_state = hasMetric ? "available" : "source_null";

    rows.push({
      timestamp_utc: item.t,
      exchange: market.exchange,
      coinalyze_symbol: market.coinalyze_symbol,
      symbol_on_exchange: market.symbol_on_exchange,
      interval,
      source: endpoint,
      dataset,
      oi_usd,
      long_liquidations_usd,
      short_liquidations_usd,
      funding_rate,
      predicted_funding_rate,
      availability_state,
      raw_request_id: rawRequestId,
      collected_at_utc: collectedAtUtc,
    });
  }

  return rows;
}
