import { describe, expect, it } from "vitest";
import worker from "../src/index";
import { Env } from "../src/types";

describe("Worker Entrypoint Handlers", () => {
  it("responds with 200 JSON on /health and does not touch D1 or external services", async () => {
    let dbTouched = false;
    const mockDb: any = {
      prepare() {
        dbTouched = true;
        throw new Error("DB should not be touched on /health");
      },
    };

    const env: Env = { DB: mockDb };
    const request = new Request("https://collector.local/health");
    const ctx: any = { waitUntil: () => {} };

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/json");

    const body = (await response.json()) as any;
    expect(body.status).toBe("healthy");
    expect(body.service).toBe("btc-derivatives-collector");
    expect(typeof body.timestamp_utc).toBe("number");
    expect(dbTouched).toBe(false);
  });

  it("returns 404 for all other routes and non-GET methods (strictly GET /health only)", async () => {
    const env: Env = { DB: {} as any };
    const ctx: any = { waitUntil: () => {} };

    // GET / must be 404 (PATCH 8)
    const resRoot = await worker.fetch(new Request("https://collector.local/"), env, ctx);
    expect(resRoot.status).toBe(404);

    // POST /health must be 405 Method Not Allowed
    const resPost = await worker.fetch(
      new Request("https://collector.local/health", { method: "POST" }),
      env,
      ctx
    );
    expect(resPost.status).toBe(405);

    // PUT /health must be 405 Method Not Allowed
    const resPut = await worker.fetch(
      new Request("https://collector.local/health", { method: "PUT" }),
      env,
      ctx
    );
    expect(resPut.status).toBe(405);

    // /trigger must be 404
    const res1 = await worker.fetch(new Request("https://collector.local/trigger"), env, ctx);
    expect(res1.status).toBe(404);

    // /cdn-cgi/local/scheduled must NOT be implemented in fetch router (returns 404)
    const res2 = await worker.fetch(new Request("https://collector.local/cdn-cgi/local/scheduled"), env, ctx);
    expect(res2.status).toBe(404);

    // /__scheduled must NOT be implemented in fetch router (returns 404)
    const res3 = await worker.fetch(new Request("https://collector.local/__scheduled"), env, ctx);
    expect(res3.status).toBe(404);
  });

  it("exported scheduled handler executes collection pipeline via ctx.waitUntil", async () => {
    let waitUntilCalled = false;
    const ctx: any = {
      waitUntil(promise: Promise<any>) {
        waitUntilCalled = true;
      },
    };

    const mockDb: any = {
      prepare() {
        return {
          bind() {
            return {
              async run() { return { success: true }; },
              async all() { return { results: [] }; },
              async first() { return null; },
            };
          },
        };
      },
      async batch() { return []; },
    };

    const event: any = { scheduledTime: Date.now(), cron: "*/10 * * * *" };
    const env: Env = { DB: mockDb };

    await worker.scheduled(event, env, ctx);
    expect(waitUntilCalled).toBe(true);
  });
});
