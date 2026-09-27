import { describe, expect, it } from "vitest";
import { CoinalyzeClient } from "../src/coinalyze-client";
import {
  getLastClosedMinuteStart,
  runScheduledCollection,
} from "../src/collector";
import {
  BOOTSTRAP_LOOKBACK_SECONDS,
  MAX_CATCHUP_PER_RUN_SECONDS,
  NORMAL_OVERLAP_SECONDS,
} from "../src/constants";
import { DiscoveredMarket, Env, SyncCheckpoint } from "../src/types";
import { Storage } from "../src/storage";

function createMockD1(): {
  db: D1Database;
  state: {
    checkpoints: Map<string, SyncCheckpoint>;
    runs: any[];
    normalized: any[];
    rawEnvelopes: any[];
    markets: DiscoveredMarket[];
  };
} {
  const state = {
    checkpoints: new Map<string, SyncCheckpoint>(),
    runs: [] as any[],
    normalized: [] as any[],
    rawEnvelopes: [] as any[],
    markets: [] as DiscoveredMarket[],
  };

  const db: any = {
    prepare(query: string) {
      let boundParams: any[] = [];
      const stmt = {
        bind(...params: any[]) {
          boundParams = params;
          return stmt;
        },
        async all() {
          if (query.includes("FROM discovered_markets")) {
            return {
              results: state.markets.map((m) => ({
                ...m,
                availability_flags_json: JSON.stringify(m.availability_flags),
                updated_at_utc: "2026-09-27T00:00:00Z",
              })),
            };
          }
          return { results: [] };
        },
        async first() {
          if (query.includes("FROM sync_checkpoints")) {
            const key = boundParams[0];
            return state.checkpoints.get(key) || null;
          }
          return null;
        },
        async run() {
          if (query.includes("INSERT INTO collection_runs")) {
            state.runs.push({
              run_id: boundParams[0],
              trigger_type: boundParams[1],
              status: boundParams[2],
              started_at_utc: boundParams[3],
              completed_at_utc: boundParams[4],
              rows_inserted: boundParams[5],
              error_message: boundParams[6],
            });
          } else if (query.includes("UPDATE collection_runs")) {
            const run = state.runs.find((r) => r.run_id === boundParams[4]);
            if (run) {
              run.status = boundParams[0];
              run.completed_at_utc = boundParams[1];
              run.rows_inserted = boundParams[2];
              run.error_message = boundParams[3];
            }
          } else if (query.includes("INSERT INTO sync_checkpoints")) {
            state.checkpoints.set(boundParams[0], {
              checkpoint_key: boundParams[0],
              dataset: boundParams[1],
              coinalyze_symbol: boundParams[2],
              interval: boundParams[3],
              covered_through_utc: boundParams[4],
              last_observation_timestamp_utc: boundParams[5],
              updated_at_utc: boundParams[6],
            });
          } else if (query.includes("DELETE FROM discovered_markets")) {
            state.markets = [];
          } else if (query.includes("INSERT INTO raw_envelopes")) {
            state.rawEnvelopes.push({
              request_id: boundParams[0],
              endpoint: boundParams[1],
              payload_json: boundParams[4],
            });
          } else if (query.includes("INSERT INTO discovered_markets")) {
            state.markets.push({
              coinalyze_symbol: boundParams[0],
              exchange: boundParams[1],
              exchange_code: boundParams[2],
              symbol_on_exchange: boundParams[3],
              base_asset: boundParams[4],
              quote_asset: boundParams[5],
              margined: boundParams[6],
              is_perpetual: Boolean(boundParams[7]),
              expire_at: Number(boundParams[8]),
              oi_lq_vol_denominated_in: boundParams[9],
              availability_flags: JSON.parse(boundParams[10] || "{}"),
              selected: Boolean(boundParams[11]),
              selection_policy: boundParams[12],
              selection_reason: boundParams[13],
            });
          } else if (query.includes("INSERT INTO normalized_derivatives")) {
            state.normalized.push({
              timestamp_utc: boundParams[0],
              coinalyze_symbol: boundParams[2],
            });
          }
          return { success: true };
        },
      };
      return stmt;
    },
    async batch(stmts: any[]) {
      for (const stmt of stmts) {
        if (stmt.run) await stmt.run();
      }
      return [];
    },
  };

  return { db, state };
}

const mockBinanceMarket: DiscoveredMarket = {
  coinalyze_symbol: "BTCUSDT_PERP.BIN",
  exchange: "Binance",
  exchange_code: "BIN",
  symbol_on_exchange: "BTCUSDT",
  base_asset: "BTC",
  quote_asset: "USDT",
  margined: "STABLE",
  is_perpetual: true,
  expire_at: 0,
  oi_lq_vol_denominated_in: "BASE_ASSET",
  availability_flags: {},
  selected: true,
  selection_policy: "primary_usdt_v1",
  selection_reason: "primary_usdt_perpetual",
};

describe("Collector Checkpoint & Watermark Semantics", () => {
  it("A. Sparse liquidations: advances covered_through to request_to while last_obs stays at latest liquidation", async () => {
    const { db, state } = createMockD1();
    state.markets = [mockBinanceMarket];

    // Current time: 14:05:30 -> closed minute boundary: 14:04:00
    const now = new Date("2026-09-27T14:05:30Z");
    const lastClosedMinute = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));

    // Existing checkpoint 1 hour ago
    const initialCoveredThrough = lastClosedMinute - 3600;
    const initialLastObs = initialCoveredThrough - 1800; // liquidation occurred 1.5h ago
    state.checkpoints.set("liquidations:BTCUSDT_PERP.BIN:1min", {
      checkpoint_key: "liquidations:BTCUSDT_PERP.BIN:1min",
      dataset: "liquidations",
      coinalyze_symbol: "BTCUSDT_PERP.BIN",
      interval: "1min",
      covered_through_utc: initialCoveredThrough,
      last_observation_timestamp_utc: initialLastObs,
      updated_at_utc: "2026-09-27T13:05:00Z",
    });

    // Mock API returns only 1 liquidation at 40 minutes before closed minute
    const singleLiquidationTs = lastClosedMinute - 40 * 60;
    const mockFetch: typeof fetch = async (url) => {
      const u = new URL(url.toString());
      const endpoint = u.pathname.replace(/^\/v1\//, "");
      if (endpoint === "liquidation-history") {
        return new Response(
          JSON.stringify([
            {
              symbol: "BTCUSDT_PERP.BIN",
              history: [{ t: singleLiquidationTs, l: 25000, s: 0 }],
            },
          ]),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify([{ symbol: "BTCUSDT_PERP.BIN", history: [] }]), {
        status: 200,
      });
    };

    const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
    const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

    const run = await runScheduledCollection(env, { now, client });
    expect(run.status).toBe("success");

    const cp = state.checkpoints.get("liquidations:BTCUSDT_PERP.BIN:1min");
    expect(cp).toBeDefined();

    // 1. covered_through_utc MUST advance to request_to (lastClosedMinute), NOT stop at singleLiquidationTs!
    expect(cp!.covered_through_utc).toBe(lastClosedMinute);

    // 2. last_observation_timestamp_utc must be exactly singleLiquidationTs
    expect(cp!.last_observation_timestamp_utc).toBe(singleLiquidationTs);
  });

  it("B. Completely empty response: advances covered_through, keeps last_obs NULL, and next run advances from coverage", async () => {
    const { db, state } = createMockD1();
    state.markets = [mockBinanceMarket];

    const nowRun1 = new Date("2026-09-27T12:00:00Z");
    const closedMin1 = getLastClosedMinuteStart(Math.floor(nowRun1.getTime() / 1000));

    const requestedWindows: Array<{ from: number; to: number }> = [];

    // Empty response for all history endpoints
    const mockFetch: typeof fetch = async (url) => {
      const u = new URL(url.toString());
      const from = parseInt(u.searchParams.get("from") || "0", 10);
      const to = parseInt(u.searchParams.get("to") || "0", 10);
      if (u.pathname.includes("history")) {
        requestedWindows.push({ from, to });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    };

    const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
    const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

    // Run 1: initial bootstrap on empty endpoint (like OKX predicted funding rate)
    const run1 = await runScheduledCollection(env, { now: nowRun1, client });
    expect(run1.status).toBe("success");
    expect(run1.rows_inserted).toBe(0);

    const cp1 = state.checkpoints.get("predicted_funding_rate:BTCUSDT_PERP.BIN:1min");
    expect(cp1).toBeDefined();
    // covered_through_utc advanced to closedMin1
    expect(cp1!.covered_through_utc).toBe(closedMin1);
    // last_observation_timestamp_utc remains NULL
    expect(cp1!.last_observation_timestamp_utc).toBeNull();

    // Run 2: 10 minutes later
    const nowRun2 = new Date("2026-09-27T12:10:00Z");
    const closedMin2 = getLastClosedMinuteStart(Math.floor(nowRun2.getTime() / 1000));

    requestedWindows.length = 0;
    const run2 = await runScheduledCollection(env, { now: nowRun2, client });
    expect(run2.status).toBe("success");

    // The second run must start from covered_through_utc - overlap, NOT repeating initial bootstrap!
    const expectedFromRun2 = closedMin1 - NORMAL_OVERLAP_SECONDS;
    const pfrReq = requestedWindows[0];
    expect(pfrReq.from).toBe(expectedFromRun2);
    expect(pfrReq.to).toBe(closedMin2);

    const cp2 = state.checkpoints.get("predicted_funding_rate:BTCUSDT_PERP.BIN:1min");
    expect(cp2!.covered_through_utc).toBe(closedMin2);
  });

  it("C. Failed request: does NOT advance covered_through watermark", async () => {
    const { db, state } = createMockD1();
    state.markets = [mockBinanceMarket];

    const initialCovered = 1727400000;
    state.checkpoints.set("open_interest:BTCUSDT_PERP.BIN:1min", {
      checkpoint_key: "open_interest:BTCUSDT_PERP.BIN:1min",
      dataset: "open_interest",
      coinalyze_symbol: "BTCUSDT_PERP.BIN",
      interval: "1min",
      covered_through_utc: initialCovered,
      last_observation_timestamp_utc: initialCovered,
      updated_at_utc: "2026-09-27T00:00:00Z",
    });

    // Mock API returns 500 server error
    const mockFetch: typeof fetch = async (url) => {
      if (url.toString().includes("open-interest-history")) {
        return new Response("Internal Server Error", { status: 500 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    };

    const instantClock = {
      now: () => Date.now(),
      sleep: async () => {},
    };
    const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch, clock: instantClock });
    const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

    const run = await runScheduledCollection(env, {
      now: new Date("2026-09-27T12:00:00Z"),
      client,
    });

    expect(run.status).toBe("partial"); // other endpoints succeeded, OI failed

    // covered_through_utc must remain at initialCovered
    const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min");
    expect(cp!.covered_through_utc).toBe(initialCovered);
  });

  it("D. Long downtime + empty windows: successive runs advance coverage chunk-by-chunk and catch up without getting stuck", async () => {
    const { db, state } = createMockD1();
    state.markets = [mockBinanceMarket];

    const targetNow = new Date("2026-09-27T20:00:00Z");
    const targetClosedMinute = getLastClosedMinuteStart(Math.floor(targetNow.getTime() / 1000));

    // Downtime of 15 hours ago
    const initialCovered = targetClosedMinute - 15 * 3600;
    state.checkpoints.set("liquidations:BTCUSDT_PERP.BIN:1min", {
      checkpoint_key: "liquidations:BTCUSDT_PERP.BIN:1min",
      dataset: "liquidations",
      coinalyze_symbol: "BTCUSDT_PERP.BIN",
      interval: "1min",
      covered_through_utc: initialCovered,
      last_observation_timestamp_utc: null,
      updated_at_utc: "2026-09-27T05:00:00Z",
    });

    // Empty response for all history
    const mockFetch: typeof fetch = async () => new Response(JSON.stringify([]), { status: 200 });
    const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
    const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

    // Run 1: advances by 6h chunk
    await runScheduledCollection(env, { now: targetNow, client });
    let cp = state.checkpoints.get("liquidations:BTCUSDT_PERP.BIN:1min")!;
    const expectedChunk1 = initialCovered - NORMAL_OVERLAP_SECONDS + MAX_CATCHUP_PER_RUN_SECONDS;
    expect(cp.covered_through_utc).toBe(expectedChunk1);

    // Run 2: advances by another 6h chunk
    await runScheduledCollection(env, { now: targetNow, client });
    cp = state.checkpoints.get("liquidations:BTCUSDT_PERP.BIN:1min")!;
    const expectedChunk2 = expectedChunk1 - NORMAL_OVERLAP_SECONDS + MAX_CATCHUP_PER_RUN_SECONDS;
    expect(cp.covered_through_utc).toBe(expectedChunk2);

    // Run 3: finishes catch-up up to targetClosedMinute
    await runScheduledCollection(env, { now: targetNow, client });
    cp = state.checkpoints.get("liquidations:BTCUSDT_PERP.BIN:1min")!;
    expect(cp.covered_through_utc).toBe(targetClosedMinute);
  });

  it("E. Closed 1-minute boundary helper satisfies conservative causal semantics", () => {
    // now = 14:26:29 -> target = 14:25:00
    const t1 = Math.floor(new Date("2026-09-27T14:26:29Z").getTime() / 1000);
    expect(getLastClosedMinuteStart(t1)).toBe(
      Math.floor(new Date("2026-09-27T14:25:00Z").getTime() / 1000)
    );

    // now = 14:26:00 -> target = 14:25:00
    const t2 = Math.floor(new Date("2026-09-27T14:26:00Z").getTime() / 1000);
    expect(getLastClosedMinuteStart(t2)).toBe(
      Math.floor(new Date("2026-09-27T14:25:00Z").getTime() / 1000)
    );

    // now = 14:26:59 -> target = 14:25:00
    const t3 = Math.floor(new Date("2026-09-27T14:26:59Z").getTime() / 1000);
    expect(getLastClosedMinuteStart(t3)).toBe(
      Math.floor(new Date("2026-09-27T14:25:00Z").getTime() / 1000)
    );

    // now = 14:27:00 -> target = 14:26:00
    const t4 = Math.floor(new Date("2026-09-27T14:27:00Z").getTime() / 1000);
    expect(getLastClosedMinuteStart(t4)).toBe(
      Math.floor(new Date("2026-09-27T14:26:00Z").getTime() / 1000)
    );
  });

  it("F. Closed 1-minute boundary in collector: does not mark unclosed current minute as covered and preserves invariant", async () => {
    const { db, state } = createMockD1();
    state.markets = [mockBinanceMarket];

    // Unclosed minute: 14:26:29
    const now = new Date("2026-09-27T14:26:29Z");
    const expectedTarget = Math.floor(new Date("2026-09-27T14:25:00Z").getTime() / 1000);

    let requestedTo: number = 0;
    const mockFetch: typeof fetch = async (url) => {
      const u = new URL(url.toString());
      if (u.pathname.includes("history")) {
        requestedTo = parseInt(u.searchParams.get("to") || "0", 10);
      }
      return new Response(JSON.stringify([]), { status: 200 });
    };

    const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
    const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

    await runScheduledCollection(env, { now, client });

    // requestedTo must be exactly 14:25:00 (NOT 14:26:00 or 14:26:29)
    expect(requestedTo).toBe(expectedTarget);

    // Checkpoint invariant: covered_through_utc <= lastClosedMinuteStart across all checkpoints
    const lastClosedMinuteStart = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));
    expect(state.checkpoints.size).toBeGreaterThan(0);
    for (const [key, cp] of state.checkpoints.entries()) {
      expect(cp.covered_through_utc).toBeLessThanOrEqual(lastClosedMinuteStart);
    }
  });

  describe("Patch 1 & 2: Strict Validation in Collector Pipeline", () => {
    it("malformed JSON fails partition, saves raw envelope, and does NOT advance checkpoint", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const initialCovered = 1727400000;
      state.checkpoints.set("open_interest:BTCUSDT_PERP.BIN:1min", {
        checkpoint_key: "open_interest:BTCUSDT_PERP.BIN:1min",
        dataset: "open_interest",
        coinalyze_symbol: "BTCUSDT_PERP.BIN",
        interval: "1min",
        covered_through_utc: initialCovered,
        last_observation_timestamp_utc: initialCovered,
        updated_at_utc: "2026-09-27T00:00:00Z",
      });

      const mockFetch: typeof fetch = async (url) => {
        if (url.toString().includes("open-interest-history")) {
          // HTTP 200 with invalid JSON
          return new Response("<html>Gateway Timeout</html>", {
            status: 200,
            headers: { "Content-Type": "text/html" },
          });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const run = await runScheduledCollection(env, {
        now: new Date("2026-09-27T12:00:00Z"),
        client,
      });

      expect(run.status).toBe("partial"); // OI failed, other partitions succeeded
      expect(run.error_message).toContain("not valid JSON");

      // Raw envelope must be saved with the raw body text
      const rawEnv = state.rawEnvelopes.find((e) => e.endpoint.includes("open-interest"));
      expect(rawEnv).toBeDefined();
      expect(rawEnv.payload_json).toBe("<html>Gateway Timeout</html>");

      // Checkpoint must NOT advance
      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min");
      expect(cp!.covered_through_utc).toBe(initialCovered);
    });

    it("unexpected schema fails partition and does NOT advance checkpoint", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const initialCovered = 1727400000;
      state.checkpoints.set("open_interest:BTCUSDT_PERP.BIN:1min", {
        checkpoint_key: "open_interest:BTCUSDT_PERP.BIN:1min",
        dataset: "open_interest",
        coinalyze_symbol: "BTCUSDT_PERP.BIN",
        interval: "1min",
        covered_through_utc: initialCovered,
        last_observation_timestamp_utc: initialCovered,
        updated_at_utc: "2026-09-27T00:00:00Z",
      });

      const mockFetch: typeof fetch = async (url) => {
        if (url.toString().includes("open-interest-history")) {
          return new Response(JSON.stringify({ error: "Rate limit exceeded" }), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const run = await runScheduledCollection(env, {
        now: new Date("2026-09-27T12:00:00Z"),
        client,
      });

      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("payload must be an array");

      // Checkpoint must NOT advance
      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min");
      expect(cp!.covered_through_utc).toBe(initialCovered);
    });

    it("wrong symbol in response fails partition and does NOT advance checkpoint", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const initialCovered = 1727400000;
      state.checkpoints.set("open_interest:BTCUSDT_PERP.BIN:1min", {
        checkpoint_key: "open_interest:BTCUSDT_PERP.BIN:1min",
        dataset: "open_interest",
        coinalyze_symbol: "BTCUSDT_PERP.BIN",
        interval: "1min",
        covered_through_utc: initialCovered,
        last_observation_timestamp_utc: initialCovered,
        updated_at_utc: "2026-09-27T00:00:00Z",
      });

      const mockFetch: typeof fetch = async (url) => {
        if (url.toString().includes("open-interest-history")) {
          return new Response(
            JSON.stringify([{ symbol: "ETHUSDT_PERP.BIN", history: [{ t: 1727400060, c: 100 }] }]),
            { status: 200 }
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const run = await runScheduledCollection(env, {
        now: new Date("2026-09-27T12:00:00Z"),
        client,
      });

      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("Symbol mismatch");

      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min");
      expect(cp!.covered_through_utc).toBe(initialCovered);
    });

    it("out-of-range timestamp fails partition and does NOT advance checkpoint", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const now = new Date("2026-09-27T12:00:00Z");
      const lastClosed = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));

      const mockFetch: typeof fetch = async (url) => {
        if (url.toString().includes("open-interest-history")) {
          // Timestamp is beyond requested toTs
          return new Response(
            JSON.stringify([{ symbol: "BTCUSDT_PERP.BIN", history: [{ t: lastClosed + 120, c: 100 }] }]),
            { status: 200 }
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const run = await runScheduledCollection(env, { now, client });
      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("Timestamp out of requested range");

      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min");
      expect(cp).toBeUndefined(); // Bootstrap run never saved checkpoint on failure
    });
  });

  describe("Patch 3: Last Observation Watermark Semantics", () => {
    it("available row advances last observation, source_null row does not", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const now = new Date("2026-09-27T12:00:00Z");
      const lastClosed = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));
      const tAvailable = lastClosed - 60;
      const tNull = lastClosed;

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("open-interest-history")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.BIN",
                history: [
                  { t: tAvailable, c: 100.5 },
                  { t: tNull, c: null }, // source_null at later timestamp
                ],
              },
            ]),
            { status: 200 }
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      await runScheduledCollection(env, { now, client });

      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min")!;
      expect(cp.covered_through_utc).toBe(lastClosed);
      // last_observation_timestamp_utc must be tAvailable, NOT tNull!
      expect(cp.last_observation_timestamp_utc).toBe(tAvailable);
    });

    it("all-null successful response advances coverage, but observation watermark remains null", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const now = new Date("2026-09-27T12:00:00Z");
      const lastClosed = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("open-interest-history")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.BIN",
                history: [
                  { t: lastClosed - 120, c: null },
                  { t: lastClosed - 60, c: null },
                ],
              },
            ]),
            { status: 200 }
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      await runScheduledCollection(env, { now, client });

      const cp = state.checkpoints.get("open_interest:BTCUSDT_PERP.BIN:1min")!;
      expect(cp.covered_through_utc).toBe(lastClosed);
      expect(cp.last_observation_timestamp_utc).toBeNull();
    });
  });

  describe("Patch 4 & 5: Atomic Discovery Snapshot & Run Status", () => {
    it("stale discovery market disappears after successful new snapshot", async () => {
      const { db, state } = createMockD1();
      // Pre-existing stale market (Bybit)
      state.markets = [
        mockBinanceMarket,
        {
          ...mockBinanceMarket,
          coinalyze_symbol: "OLD_BTCUSDT_PERP.BYB",
          exchange: "Bybit",
          exchange_code: "BYB",
          symbol_on_exchange: "BTCUSDT",
          quote_asset: "USDT",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];

      // New discovery does NOT include OLD_BTCUSDT_PERP.BYB
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.BIN",
                exchange: "Binance",
                symbol_on_exchange: "BTCUSDT",
                base_asset: "BTC",
                quote_asset: "USDT",
                is_perpetual: true,
                margined: "STABLE",
              },
            ]),
            { status: 200 }
          );
        }
        if (u.pathname.includes("exchanges")) {
          return new Response(JSON.stringify([{ name: "Binance", code: "BIN" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      // Force discovery expiration by passing a date in future
      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });
      expect(run.status).toBe("success");

      // OLD_BTCUSDT_PERP.BYB must have disappeared from state.markets
      expect(state.markets.find((m) => m.coinalyze_symbol === "OLD_BTCUSDT_PERP.BYB")).toBeUndefined();
      expect(state.markets).toHaveLength(1);
      expect(state.markets[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("invalid new discovery does NOT destroy previous validated snapshot and marks run partial/degraded", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      // Discovery returns invalid JSON
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 }); // invalid JSON
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      // Run status must be degraded/partial due to discovery fallback
      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("Discovery refresh failed");

      // Previous validated snapshot was preserved
      expect(state.markets).toHaveLength(1);
      expect(state.markets[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("zero selected markets fails the run immediately and runs 0 partitions", async () => {
      const { db, state } = createMockD1();
      state.markets = []; // No cached discovery

      // API returns only non-target exchanges
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.DERIBIT",
                exchange: "Deribit", // Not Binance, Bybit, or OKX
                symbol_on_exchange: "BTCUSDT",
                base_asset: "BTC",
                quote_asset: "USDT",
                is_perpetual: true,
              },
            ]),
            { status: 200 }
          );
        }
        if (u.pathname.includes("exchanges")) {
          return new Response(JSON.stringify([{ name: "Deribit", code: "DRB" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const run = await runScheduledCollection(env, { client });
      expect(run.status).toBe("failed");
      expect(run.error_message).toContain("Discovery produced 0 selected markets");
      expect(state.checkpoints.size).toBe(0);
    });
  });

  describe("Patch 7: Inclusive Timing Bounds & Bucket Calculations", () => {
    it("bootstrap queries exactly 120 minute buckets inclusive", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const now = new Date("2026-09-27T14:26:29Z");
      const lastClosed = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000)); // 14:25:00

      let requestedFrom = 0;
      let requestedTo = 0;
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("history")) {
          requestedFrom = parseInt(u.searchParams.get("from") || "0", 10);
          requestedTo = parseInt(u.searchParams.get("to") || "0", 10);
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      await runScheduledCollection(env, { now, client });

      expect(requestedTo).toBe(lastClosed);
      expect(requestedFrom).toBe(lastClosed - 119 * 60);

      // Number of inclusive 1-minute buckets
      const bucketCount = Math.floor((requestedTo - requestedFrom) / 60) + 1;
      expect(bucketCount).toBe(120);
    });

    it("max catch-up queries at most 360 minute buckets inclusive", async () => {
      const { db, state } = createMockD1();
      state.markets = [mockBinanceMarket];

      const now = new Date("2026-09-27T20:00:00Z");
      const lastClosed = getLastClosedMinuteStart(Math.floor(now.getTime() / 1000));

      // 10 hours ago checkpoint
      const initialCovered = lastClosed - 10 * 3600;
      state.checkpoints.set("open_interest:BTCUSDT_PERP.BIN:1min", {
        checkpoint_key: "open_interest:BTCUSDT_PERP.BIN:1min",
        dataset: "open_interest",
        coinalyze_symbol: "BTCUSDT_PERP.BIN",
        interval: "1min",
        covered_through_utc: initialCovered,
        last_observation_timestamp_utc: null,
        updated_at_utc: "2026-09-27T10:00:00Z",
      });

      let requestedFrom = 0;
      let requestedTo = 0;
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("open-interest-history")) {
          requestedFrom = parseInt(u.searchParams.get("from") || "0", 10);
          requestedTo = parseInt(u.searchParams.get("to") || "0", 10);
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      await runScheduledCollection(env, { now, client });

      // Overlap = 20 minutes before initialCovered
      expect(requestedFrom).toBe(initialCovered - NORMAL_OVERLAP_SECONDS);
      // toTs = fromTs + 359 * 60
      expect(requestedTo).toBe(requestedFrom + 359 * 60);

      const bucketCount = Math.floor((requestedTo - requestedFrom) / 60) + 1;
      expect(bucketCount).toBe(360);
    });
  });

  describe("Strict Runtime Validation of Discovery (Second Codex Re-Review)", () => {
    it("Case A & L: non-object element in future-markets invalidates fresh discovery and leaves previous validated snapshot intact", async () => {
      const { db, state } = createMockD1();
      state.markets = [{ ...mockBinanceMarket }];

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.BIN",
                exchange: "Binance",
                symbol_on_exchange: "BTCUSDT",
                base_asset: "BTC",
                quote_asset: "USDT",
                is_perpetual: true,
              },
              "invalid-element-not-an-object",
            ]),
            { status: 200 }
          );
        }
        if (u.pathname.includes("exchanges")) {
          return new Response(JSON.stringify([{ name: "Binance", code: "BIN" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      // Force discovery expiration so it tries fresh discovery
      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      // Run status is degraded/partial because it gracefully fell back to valid cached snapshot
      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("expected non-null object");

      // Previous validated snapshot is 100% intact
      expect(state.markets).toHaveLength(1);
      expect(state.markets[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("Case H: fresh discovery invalid with valid cached snapshot uses stale fallback and marks run partial/degraded", async () => {
      const { db, state } = createMockD1();
      state.markets = [{ ...mockBinanceMarket }];

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          // Element has numeric symbol (Case B)
          return new Response(
            JSON.stringify([
              {
                symbol: 99999,
                exchange: "Binance",
                symbol_on_exchange: "BTCUSDT",
                base_asset: "BTC",
                quote_asset: "USDT",
                is_perpetual: true,
              },
            ]),
            { status: 200 }
          );
        }
        if (u.pathname.includes("exchanges")) {
          return new Response(JSON.stringify([{ name: "Binance", code: "BIN" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("used previously validated snapshot");
      // Partitions for the cached market were executed
      expect(state.checkpoints.size).toBe(4);
    });

    it("Case I: fresh discovery invalid and cached snapshot malformed forbids fallback, fails run, and runs 0 partitions", async () => {
      const { db, state } = createMockD1();
      // Corrupt/malformed cached market in D1 (e.g. invalid exchange identity)
      state.markets = [
        {
          ...mockBinanceMarket,
          exchange: "InvalidExchangeName",
        },
      ];

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response(JSON.stringify([{ symbol: "", exchange: "Binance" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      // Run must fail completely
      expect(run.status).toBe("failed");
      expect(run.error_message).toContain("must be a non-empty string");

      // ZERO partitions executed, no checkpoints created
      expect(state.checkpoints.size).toBe(0);
    });

    it("Case J: cached snapshot with malformed identity returns null from storage and is rejected", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      // Malformed: empty symbol
      state.markets = [
        {
          ...mockBinanceMarket,
          coinalyze_symbol: "",
        },
      ];

      const cached = await storage.getCachedDiscoveredMarkets();
      expect(cached).toBeNull();
    });

    it("Case K: successful valid discovery atomically replaces previous snapshot", async () => {
      const { db, state } = createMockD1();
      state.markets = [
        {
          ...mockBinanceMarket,
          coinalyze_symbol: "OLD_MARKET.BIN",
        },
      ];

      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response(
            JSON.stringify([
              {
                symbol: "BTCUSDT_PERP.BIN",
                exchange: "Binance",
                symbol_on_exchange: "BTCUSDT",
                base_asset: "BTC",
                quote_asset: "USDT",
                is_perpetual: true,
                margined: "STABLE",
              },
            ]),
            { status: 200 }
          );
        }
        if (u.pathname.includes("exchanges")) {
          return new Response(JSON.stringify([{ name: "Binance", code: "BIN" }]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("success");
      expect(state.markets).toHaveLength(1);
      expect(state.markets[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("Storage Defense: saveDiscoveredMarkets validates first and does not DELETE if snapshot is invalid", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      state.markets = [{ ...mockBinanceMarket }];

      // Attempt to save snapshot with duplicate identity
      const invalidSnapshot: DiscoveredMarket[] = [
        mockBinanceMarket,
        { ...mockBinanceMarket, selected: false, selection_reason: "alternative_perpetual" },
      ];

      await expect(storage.saveDiscoveredMarkets(invalidSnapshot, "2026-09-27T12:00:00Z")).rejects.toThrow(
        "duplicate symbol"
      );

      // Previous state.markets was NOT deleted
      expect(state.markets).toHaveLength(1);
      expect(state.markets[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("Case N: cached snapshot with selected non-USDT market is rejected and forbids fallback", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      // Malformed cached market: selected with USDC
      state.markets = [
        {
          ...mockBinanceMarket,
          coinalyze_symbol: "BTCUSDC_PERP.BIN",
          quote_asset: "USDC",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];

      // Storage rejects it
      const cached = await storage.getCachedDiscoveredMarkets();
      expect(cached).toBeNull();

      // Fresh discovery fails -> fallback forbidden -> run fails with 0 partitions
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 }); // invalid JSON fails discovery immediately
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("failed");
      expect(state.checkpoints.size).toBe(0);
    });

    it("Case O: cached snapshot with eligible USDT candidate but 0 selected is rejected and forbids fallback", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      // Malformed cached market: eligible candidate but selected = false
      state.markets = [
        {
          ...mockBinanceMarket,
          selected: false,
          selection_reason: "alternative_perpetual",
        },
      ];

      const cached = await storage.getCachedDiscoveredMarkets();
      expect(cached).toBeNull();

      // Fresh discovery fails -> fallback forbidden -> run fails
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("failed");
      expect(state.checkpoints.size).toBe(0);
    });

    it("Case P: fresh discovery invalid + semantically valid stale cache uses fallback and completes degraded", async () => {
      const { db, state } = createMockD1();
      // Semantically valid cached market
      state.markets = [{ ...mockBinanceMarket }];

      // Fresh discovery fails
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      // Run status is degraded/partial
      expect(run.status).toBe("partial");
      expect(run.error_message).toContain("used previously validated snapshot");
      // Partitions executed successfully using valid cached market
      expect(state.checkpoints.size).toBe(4);
    });

    it("Gap C1: cached snapshot with selection_policy != primary_usdt_v1 is rejected, forbids fallback, run fails, partitions = 0", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      // Cached market with wrong selection policy
      state.markets = [
        {
          ...mockBinanceMarket,
          selection_policy: "primary_usdc_v1",
        },
      ];

      const cached = await storage.getCachedDiscoveredMarkets();
      expect(cached).toBeNull();

      // Fresh discovery fails -> fallback forbidden -> run fails with 0 partitions
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("failed");
      expect(state.checkpoints.size).toBe(0);
    });

    it("Gap C2: cached selected row with misleading primary_usdc_perpetual is rejected, forbids fallback, run fails, partitions = 0", async () => {
      const { db, state } = createMockD1();
      const storage = new Storage(db);

      // Cached market with misleading reason
      state.markets = [
        {
          ...mockBinanceMarket,
          selection_reason: "primary_usdc_perpetual",
        },
      ];

      const cached = await storage.getCachedDiscoveredMarkets();
      expect(cached).toBeNull();

      // Fresh discovery fails -> fallback forbidden -> run fails with 0 partitions
      const mockFetch: typeof fetch = async (url) => {
        const u = new URL(url.toString());
        if (u.pathname.includes("future-markets")) {
          return new Response("502 Bad Gateway", { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const client = new CoinalyzeClient("test-key", { fetchFn: mockFetch });
      const env: Env = { DB: db, COINALYZE_API_KEY: "test-key" };

      const futureNow = new Date("2026-09-29T12:00:00Z");
      const run = await runScheduledCollection(env, { now: futureNow, client });

      expect(run.status).toBe("failed");
      expect(state.checkpoints.size).toBe(0);
    });
  });
});
