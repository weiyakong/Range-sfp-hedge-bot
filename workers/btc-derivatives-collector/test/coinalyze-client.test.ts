import { describe, expect, it } from "vitest";
import { CoinalyzeClient, RateLimiterClock, RollingRateLimiter, sanitizeText } from "../src/coinalyze-client";

class MockClock implements RateLimiterClock {
  currentTime = 0;
  sleeps: number[] = [];

  now(): number {
    return this.currentTime;
  }

  async sleep(ms: number): Promise<void> {
    this.sleeps.push(ms);
    this.currentTime += ms;
  }
}

describe("CoinalyzeClient & Secret Sanitization", () => {
  const FAKE_SECRET_KEY = "SUPER_SECRET_API_KEY_xyz987654";

  it("never leaks secret API key into safeParams, rawBodyText, payload, or error messages", async () => {
    // Mock fetch that intentionally echoes back headers and secret in error body
    const mockFetch: typeof fetch = async (input, init) => {
      const headers = (init?.headers || {}) as Record<string, string>;
      const echoBody = JSON.stringify({
        error: `Invalid request with key ${headers["api_key"] || "none"}`,
        echoKey: FAKE_SECRET_KEY,
      });

      return new Response(echoBody, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new CoinalyzeClient(FAKE_SECRET_KEY, {
      fetchFn: mockFetch,
    });

    const result = await client.get("open-interest-history", {
      symbols: "BTCUSDT_PERP.A",
      api_key: FAKE_SECRET_KEY, // accidentally supplied param
    });

    // 1. safeParams must NOT contain api_key
    expect(result.safeParams).not.toHaveProperty("api_key");
    expect(JSON.stringify(result.safeParams)).not.toContain(FAKE_SECRET_KEY);

    // 2. rawBodyText must NOT contain the secret
    expect(result.rawBodyText).not.toContain(FAKE_SECRET_KEY);
    expect(result.rawBodyText).toContain("[REDACTED]");

    // 3. payload object must NOT contain the secret
    const payloadStr = JSON.stringify(result.payload);
    expect(payloadStr).not.toContain(FAKE_SECRET_KEY);
    expect(payloadStr).toContain("[REDACTED]");
  });

  it("sanitizes API key from error messages on HTTP errors", async () => {
    const mockFetch: typeof fetch = async () => {
      return new Response(`Failed authentication with key ${FAKE_SECRET_KEY}`, {
        status: 401,
      });
    };

    const client = new CoinalyzeClient(FAKE_SECRET_KEY, {
      fetchFn: mockFetch,
    });

    let caughtError: Error | null = null;
    try {
      await client.get("open-interest-history", { symbols: "BTCUSDT" });
    } catch (err) {
      caughtError = err as Error;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError!.message).not.toContain(FAKE_SECRET_KEY);
    expect(caughtError!.message).toContain("[REDACTED]");
  });

  it("handles HTTP 429 and respects Retry-After header with rate limiter", async () => {
    const clock = new MockClock();
    let attempts = 0;

    const mockFetch: typeof fetch = async () => {
      attempts++;
      if (attempts === 1) {
        return new Response("Too Many Requests", {
          status: 429,
          headers: { "retry-after": "2" }, // 2 seconds
        });
      }
      return new Response(JSON.stringify([{ symbol: "BTC", history: [] }]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    const limiter = new RollingRateLimiter(40, 60_000, clock);
    const client = new CoinalyzeClient("test-key", {
      clock,
      limiter,
      fetchFn: mockFetch,
    });

    const res = await client.get("open-interest-history", { symbols: "BTC" });
    expect(res.statusCode).toBe(200);
    expect(attempts).toBe(2);
    expect(clock.sleeps).toContain(2000);
  });

  it("accounts rate-limit units per symbol in batched requests", async () => {
    const clock = new MockClock();
    // Limiter with capacity of 4 units per window
    const limiter = new RollingRateLimiter(4, 60_000, clock);

    const mockFetch: typeof fetch = async () => {
      return new Response(JSON.stringify([]), { status: 200 });
    };

    const client = new CoinalyzeClient("test-key", {
      clock,
      limiter,
      fetchFn: mockFetch,
    });

    // 1. Request with 1 symbol -> costs 1 unit (remaining 3)
    await client.get("open-interest-history", { symbols: "BTCUSDT_PERP.BIN" });
    expect(clock.sleeps).toHaveLength(0);

    // 2. Request with 3 symbols -> costs 3 units (total 4 units consumed, 0 remaining)
    await client.get("open-interest-history", {
      symbols: "BTCUSDT_PERP.BIN,BTCUSDT_PERP.BYB,BTCUSDT_PERP.OKX",
    });
    expect(clock.sleeps).toHaveLength(0);

    // 3. Next request with 1 symbol exceeds capacity of 4 -> must trigger limiter sleep
    await client.get("future-markets", {});
    expect(clock.sleeps.length).toBeGreaterThan(0);
    expect(clock.sleeps[0]).toBeGreaterThan(0);
  });
});

