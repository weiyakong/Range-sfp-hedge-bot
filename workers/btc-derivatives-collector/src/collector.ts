import { CoinalyzeClient } from "./coinalyze-client";
import {
  BOOTSTRAP_INCLUSIVE_SPAN_SECONDS,
  DATASET_ENDPOINTS,
  DEFAULT_INTERVAL,
  MAX_CATCHUP_INCLUSIVE_SPAN_SECONDS,
  NORMAL_OVERLAP_SECONDS,
  USD_DATASETS,
} from "./constants";
import {
  discoverBtcPerpetuals,
  isDiscoveryExpired,
  validateDiscoveredMarketsSnapshot,
  validateExchangeCatalog,
  validateRawMarkets,
} from "./discovery";
import { normalizeCoinalyzePayload } from "./normalizer";
import { Storage } from "./storage";
import {
  CollectionRun,
  DatasetName,
  DiscoveredMarket,
  Env,
  ExchangeCatalogEntry,
  RawMarket,
} from "./types";

export interface CollectorOptions {
  now?: Date;
  client?: CoinalyzeClient;
}

/**
 * Calculates the start timestamp (in UTC seconds) of the last fully closed 1-minute bucket.
 *
 * For conservative causal research data pipelines, an ongoing minute bucket is NOT closed.
 * Example:
 *   - At 14:26:29 -> current minute bucket [14:26:00, 14:27:00) is open.
 *                    The last fully closed 1-minute bucket is [14:25:00, 14:26:00), whose start is 14:25:00.
 *   - At 14:26:00 -> current minute bucket [14:26:00, 14:27:00) has just started.
 *                    The last fully closed bucket start is 14:25:00.
 *   - At 14:26:59 -> still inside minute 14:26. Last fully closed bucket start is 14:25:00.
 *   - At 14:27:00 -> minute 14:26 has closed. The last fully closed bucket start is 14:26:00.
 */
export function getLastClosedMinuteStart(nowSeconds: number): number {
  const currentMinuteStart = Math.floor(nowSeconds / 60) * 60;
  return currentMinuteStart - 60;
}

export async function runScheduledCollection(
  env: Env,
  options?: CollectorOptions
): Promise<CollectionRun> {
  const now = options?.now || new Date();
  const nowIso = now.toISOString();
  const nowSeconds = Math.floor(now.getTime() / 1000);
  // Last fully closed 1-minute bucket start (conservative causal boundary)
  const lastClosedMinuteStart = getLastClosedMinuteStart(nowSeconds);

  const runId = crypto.randomUUID();
  const storage = new Storage(env.DB);

  const runRecord: CollectionRun = {
    run_id: runId,
    trigger_type: "scheduled",
    status: "in_progress",
    started_at_utc: nowIso,
    completed_at_utc: null,
    rows_inserted: 0,
    error_message: null,
  };

  await storage.recordCollectionRunStart(runRecord);

  if (!env.COINALYZE_API_KEY) {
    const errorMsg = "COINALYZE_API_KEY is not configured";
    await storage.recordCollectionRunFinish(runId, "failed", 0, errorMsg);
    return {
      ...runRecord,
      status: "failed",
      completed_at_utc: new Date().toISOString(),
      error_message: errorMsg,
    };
  }

  const client =
    options?.client || new CoinalyzeClient(env.COINALYZE_API_KEY);

  let totalRowsInserted = 0;
  const errors: string[] = [];
  let successfulPartitions = 0;
  let totalPartitions = 0;

  try {
    // 1. Discovery
    let markets: DiscoveredMarket[] = [];
    let validCachedMarkets: DiscoveredMarket[] | null = null;
    let cachedLastUpdatedUtc: string | null = null;

    try {
      const cachedDiscovery = await storage.getCachedDiscoveredMarkets();
      if (cachedDiscovery && cachedDiscovery.markets.length > 0) {
        // Validate cached snapshot before fallback
        validCachedMarkets = validateDiscoveredMarketsSnapshot(cachedDiscovery.markets);
        cachedLastUpdatedUtc = cachedDiscovery.lastUpdatedUtc;
      }
    } catch {
      validCachedMarkets = null;
      cachedLastUpdatedUtc = null;
    }

    if (
      validCachedMarkets &&
      cachedLastUpdatedUtc &&
      !isDiscoveryExpired(cachedLastUpdatedUtc, nowIso)
    ) {
      markets = validCachedMarkets;
    } else {
      try {
        const marketsRes = await client.get("future-markets", {});
        const exchangesRes = await client.get("exchanges", {});

        await storage.saveRawEnvelope({
          request_id: marketsRes.requestId,
          endpoint: marketsRes.endpoint,
          params_json: JSON.stringify(marketsRes.safeParams),
          status_code: marketsRes.statusCode,
          payload_json: marketsRes.rawBodyText,
          created_at_utc: marketsRes.createdAtUtc,
        });

        await storage.saveRawEnvelope({
          request_id: exchangesRes.requestId,
          endpoint: exchangesRes.endpoint,
          params_json: JSON.stringify(exchangesRes.safeParams),
          status_code: exchangesRes.statusCode,
          payload_json: exchangesRes.rawBodyText,
          created_at_utc: exchangesRes.createdAtUtc,
        });

        if (!marketsRes.isJsonValid) {
          throw new Error("Invalid future-markets discovery response: JSON is not valid");
        }

        if (!exchangesRes.isJsonValid) {
          throw new Error("Invalid exchanges discovery response: JSON is not valid");
        }

        // Strict runtime validation of raw catalogs
        const validatedRawMarkets = validateRawMarkets(marketsRes.payload);
        const validatedExchangeCatalog = validateExchangeCatalog(exchangesRes.payload);

        const candidateMarkets = discoverBtcPerpetuals(
          validatedRawMarkets,
          validatedExchangeCatalog
        );

        // Strict runtime validation of final candidate snapshot
        const validatedSnapshot = validateDiscoveredMarketsSnapshot(candidateMarkets);

        await storage.saveDiscoveredMarkets(validatedSnapshot, nowIso);
        markets = validatedSnapshot;
      } catch (err: unknown) {
        if (validCachedMarkets && validCachedMarkets.length > 0 && cachedLastUpdatedUtc) {
          // Graceful fallback to cached discovery: mark run degraded/partial
          markets = validCachedMarkets;
          const errMsg = err instanceof Error ? err.message : String(err);
          errors.push(
            `Discovery refresh failed (${errMsg}); used previously validated snapshot from ${cachedLastUpdatedUtc}`
          );
        } else {
          throw err;
        }
      }
    }

    const selectedMarkets = markets.filter((m) => m.selected);
    if (selectedMarkets.length === 0) {
      const zeroSelectedMsg = "Discovery produced 0 selected markets";
      await storage.recordCollectionRunFinish(runId, "failed", 0, zeroSelectedMsg);
      return {
        ...runRecord,
        status: "failed",
        completed_at_utc: new Date().toISOString(),
        rows_inserted: 0,
        error_message: zeroSelectedMsg,
      };
    }

    const datasets: DatasetName[] = [
      "open_interest",
      "liquidations",
      "funding_rate",
      "predicted_funding_rate",
    ];

    // 2. Collection per market and dataset
    for (const market of selectedMarkets) {
      for (const dataset of datasets) {
        totalPartitions++;
        const interval = DEFAULT_INTERVAL;
        const checkpointKey = `${dataset}:${market.coinalyze_symbol}:${interval}`;

        try {
          const checkpoint = await storage.getCheckpoint(checkpointKey);

          let fromTs: number;
          let toTs: number;

          if (!checkpoint) {
            // Initial Bootstrap Lookback = 2 hours = 120 minute buckets inclusive:
            // from = to - (119 * 60)
            // NOTE: This is NOT historical backfill!
            fromTs = Math.max(0, lastClosedMinuteStart - BOOTSTRAP_INCLUSIVE_SPAN_SECONDS);
            toTs = lastClosedMinuteStart;
          } else {
            // Overlap = 20 minutes prior to coverage watermark (covered_through_utc)
            const desiredFrom = checkpoint.covered_through_utc - NORMAL_OVERLAP_SECONDS;
            const lag = lastClosedMinuteStart - desiredFrom;

            if (lag > MAX_CATCHUP_INCLUSIVE_SPAN_SECONDS) {
              // Bounded catch-up: process next window up to 360 minute buckets inclusive
              fromTs = desiredFrom;
              toTs = Math.min(desiredFrom + MAX_CATCHUP_INCLUSIVE_SPAN_SECONDS, lastClosedMinuteStart);
            } else {
              fromTs = desiredFrom;
              toTs = lastClosedMinuteStart;
            }
          }

          if (fromTs >= toTs) {
            successfulPartitions++;
            continue;
          }

          const endpoint = DATASET_ENDPOINTS[dataset];
          const queryParams: Record<string, string | number | boolean> = {
            symbols: market.coinalyze_symbol,
            interval,
            from: fromTs,
            to: toTs,
          };

          if (USD_DATASETS.has(dataset)) {
            queryParams.convert_to_usd = "true";
          }

          const fetchResult = await client.get(endpoint, queryParams);

          await storage.saveRawEnvelope({
            request_id: fetchResult.requestId,
            endpoint: fetchResult.endpoint,
            params_json: JSON.stringify(fetchResult.safeParams),
            status_code: fetchResult.statusCode,
            payload_json: fetchResult.rawBodyText,
            created_at_utc: fetchResult.createdAtUtc,
          });

          if (!fetchResult.isJsonValid) {
            throw new Error(
              `Response from ${endpoint} for ${market.coinalyze_symbol} is not valid JSON`
            );
          }

          const normalizedRows = normalizeCoinalyzePayload(
            dataset,
            market,
            interval,
            fetchResult.requestId,
            fetchResult.createdAtUtc,
            fetchResult.payload,
            fromTs,
            toTs
          );

          if (normalizedRows.length > 0) {
            await storage.saveNormalizedRows(normalizedRows);
            totalRowsInserted += normalizedRows.length;
          }

          // Calculate observation timestamp using ONLY available rows (PATCH 3)
          // source_null rows must NOT advance last_observation_timestamp_utc
          const availableRows = normalizedRows.filter(
            (r) => r.availability_state === "available"
          );
          let newLastObs = checkpoint?.last_observation_timestamp_utc ?? null;
          if (availableRows.length > 0) {
            const maxObsInBatch = Math.max(...availableRows.map((r) => r.timestamp_utc));
            newLastObs =
              newLastObs !== null ? Math.max(newLastObs, maxObsInBatch) : maxObsInBatch;
          }

          // Advance covered_through_utc to the successfully verified toTs watermark
          await storage.saveCheckpoint({
            checkpoint_key: checkpointKey,
            dataset,
            coinalyze_symbol: market.coinalyze_symbol,
            interval,
            covered_through_utc: toTs,
            last_observation_timestamp_utc: newLastObs,
            updated_at_utc: nowIso,
          });

          successfulPartitions++;
        } catch (partitionErr: unknown) {
          const msg =
            partitionErr instanceof Error
              ? partitionErr.message
              : String(partitionErr);
          errors.push(`[${checkpointKey}]: ${msg}`);
        }
      }
    }

    let finalStatus: CollectionRun["status"] = "success";
    if (errors.length > 0) {
      finalStatus = successfulPartitions > 0 ? "partial" : "failed";
    }

    const finalErrorMessage = errors.length > 0 ? errors.join("; ") : null;
    await storage.recordCollectionRunFinish(
      runId,
      finalStatus,
      totalRowsInserted,
      finalErrorMessage
    );

    return {
      run_id: runId,
      trigger_type: "scheduled",
      status: finalStatus,
      started_at_utc: nowIso,
      completed_at_utc: new Date().toISOString(),
      rows_inserted: totalRowsInserted,
      error_message: finalErrorMessage,
    };
  } catch (fatalErr: unknown) {
    const fatalMsg =
      fatalErr instanceof Error ? fatalErr.message : String(fatalErr);
    await storage.recordCollectionRunFinish(runId, "failed", totalRowsInserted, fatalMsg);
    return {
      run_id: runId,
      trigger_type: "scheduled",
      status: "failed",
      started_at_utc: nowIso,
      completed_at_utc: new Date().toISOString(),
      rows_inserted: totalRowsInserted,
      error_message: fatalMsg,
    };
  }
}
