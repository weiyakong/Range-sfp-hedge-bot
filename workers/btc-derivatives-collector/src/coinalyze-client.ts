import { BASE_URL } from "./constants";

export interface RateLimiterClock {
  now(): number;
  sleep(ms: number): Promise<void>;
}

export class SystemRateLimiterClock implements RateLimiterClock {
  now(): number {
    return Date.now();
  }
  sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
  }
}

export class HttpError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "HttpError";
  }
}

export class RollingRateLimiter {
  private timestamps: number[] = [];
  private readonly maxUnits: number;
  private readonly windowMs: number;
  private readonly clock: RateLimiterClock;

  constructor(
    maxUnits = 40,
    windowMs = 60_000,
    clock: RateLimiterClock = new SystemRateLimiterClock()
  ) {
    this.maxUnits = maxUnits;
    this.windowMs = windowMs;
    this.clock = clock;
  }

  async acquire(units = 1): Promise<void> {
    while (true) {
      const now = this.clock.now();
      const cutoff = now - this.windowMs;
      this.timestamps = this.timestamps.filter((ts) => ts > cutoff);

      if (this.timestamps.length + units <= this.maxUnits) {
        for (let i = 0; i < units; i++) {
          this.timestamps.push(now);
        }
        return;
      }

      const oldest = this.timestamps[0];
      const waitMs = oldest + this.windowMs - now + 50;
      await this.clock.sleep(waitMs);
    }
  }
}

export interface ClientResult {
  requestId: string;
  endpoint: string;
  safeParams: Record<string, string>;
  statusCode: number;
  payload: unknown;
  rawBodyText: string;
  isJsonValid: boolean;
  createdAtUtc: string;
}

export function sanitizeText(text: string, secret?: string): string {
  if (!secret || secret.trim().length === 0) {
    return text;
  }
  return text.replaceAll(secret, "[REDACTED]");
}

export function sanitizeObject<T>(obj: T, secret?: string): T {
  if (!secret) return obj;
  const str = JSON.stringify(obj);
  const sanitized = sanitizeText(str, secret);
  return JSON.parse(sanitized) as T;
}

export class CoinalyzeClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly limiter: RollingRateLimiter;
  private readonly clock: RateLimiterClock;
  private readonly fetchFn: typeof fetch;

  constructor(
    apiKey: string,
    options?: {
      baseUrl?: string;
      limiter?: RollingRateLimiter;
      clock?: RateLimiterClock;
      fetchFn?: typeof fetch;
    }
  ) {
    if (!apiKey || apiKey.trim().length === 0) {
      throw new Error("COINALYZE_API_KEY must not be empty");
    }
    this.apiKey = apiKey.trim();
    this.baseUrl = options?.baseUrl || BASE_URL;
    this.clock = options?.clock || new SystemRateLimiterClock();
    this.limiter = options?.limiter || new RollingRateLimiter(40, 60_000, this.clock);
    this.fetchFn = options?.fetchFn || fetch.bind(globalThis);
  }

  async get(
    endpoint: string,
    params: Record<string, string | number | boolean>,
    options?: { unitsCost?: number; maxRetries?: number }
  ): Promise<ClientResult> {
    const requestId = crypto.randomUUID();
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint.slice(1) : endpoint;
    const maxRetries = options?.maxRetries ?? 3;

    // Calculate API-call cost: Coinalyze charges 1 unit per symbol in batched requests
    let unitsCost = options?.unitsCost;
    if (unitsCost === undefined) {
      if (params.symbols !== undefined && params.symbols !== null) {
        const symbolsStr = String(params.symbols).trim();
        const symbolList = symbolsStr
          .split(",")
          .map((s) => s.trim())
          .filter((s) => s.length > 0);
        unitsCost = Math.max(1, symbolList.length);
      } else {
        unitsCost = 1;
      }
    }

    // Filter out any secret params if ever mistakenly provided
    const safeParams: Record<string, string> = {};
    for (const [k, v] of Object.entries(params)) {
      if (k.toLowerCase() === "api_key" || k.toLowerCase() === "key") {
        continue;
      }
      safeParams[k] = String(v);
    }

    const query = new URLSearchParams(safeParams).toString();
    const url = `${this.baseUrl}/${cleanEndpoint}${query ? `?${query}` : ""}`;

    let attempt = 0;
    while (true) {
      await this.limiter.acquire(unitsCost);
      attempt++;

      const createdAtUtc = new Date().toISOString();

      try {
        const response = await this.fetchFn(url, {
          method: "GET",
          headers: {
            api_key: this.apiKey,
            Accept: "application/json",
          },
        });

        const rawBodyText = await response.text();

        if (response.status === 429) {
          if (attempt > maxRetries) {
            throw new Error(`Coinalyze 429 Rate Limited after ${attempt} attempts`);
          }
          const retryAfterHeader = response.headers.get("retry-after");
          let delayMs = 5000;
          if (retryAfterHeader) {
            const parsed = parseInt(retryAfterHeader, 10);
            if (!isNaN(parsed) && parsed > 0) {
              delayMs = parsed * 1000;
            }
          }
          await this.clock.sleep(delayMs);
          continue;
        }

        if (!response.ok) {
          const safeBody = sanitizeText(rawBodyText, this.apiKey);
          const statusError = new HttpError(
            response.status,
            `Coinalyze HTTP ${response.status} on /${cleanEndpoint}: ${safeBody}`
          );
          // 4xx errors (except 429 handled above) are permanent client errors; do not retry
          if (response.status >= 400 && response.status < 500) {
            throw statusError;
          }
          if (attempt > maxRetries) {
            throw statusError;
          }
          await this.clock.sleep(1000 * attempt);
          continue;
        }

        let payload: unknown = null;
        let isJsonValid = false;
        try {
          payload = JSON.parse(rawBodyText);
          isJsonValid = true;
        } catch {
          payload = null;
          isJsonValid = false;
        }

        // Guarantee that the raw envelope and returned data have zero secret occurrences
        const sanitizedBody = sanitizeText(rawBodyText, this.apiKey);
        const sanitizedPayload = isJsonValid ? sanitizeObject(payload, this.apiKey) : null;

        return {
          requestId,
          endpoint: cleanEndpoint,
          safeParams,
          statusCode: response.status,
          payload: sanitizedPayload,
          rawBodyText: sanitizedBody,
          isJsonValid,
          createdAtUtc,
        };
      } catch (err: unknown) {
        if (err instanceof HttpError && err.status >= 400 && err.status < 500) {
          throw err;
        }
        if (attempt > maxRetries || (err instanceof Error && err.message.includes("429 Rate Limited"))) {
          const rawMessage = err instanceof Error ? err.message : String(err);
          const safeMessage = sanitizeText(rawMessage, this.apiKey);
          throw new Error(`Request failed for /${cleanEndpoint}: ${safeMessage}`);
        }
        // Wait and retry for transient network failure
        await this.clock.sleep(1000 * attempt);
      }
    }
  }
}
