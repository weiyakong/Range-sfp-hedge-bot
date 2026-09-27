import {
  ALTERNATIVE_SELECTION_REASON,
  DISCOVERY_CACHE_SECONDS,
  PRIMARY_USDT_SELECTION_REASON,
  SELECTION_POLICY,
  TARGET_EXCHANGES,
} from "./constants";
import {
  DiscoveredMarket,
  ExchangeCatalogEntry,
  RawMarket,
} from "./types";

export function resolveExchangeName(
  rawExchange: string,
  catalog?: ExchangeCatalogEntry[]
): { exchange: string; exchange_code: string } {
  if (!catalog || catalog.length === 0) {
    return { exchange: rawExchange, exchange_code: rawExchange };
  }
  const match = catalog.find(
    (c) =>
      c.code.toLowerCase() === rawExchange.toLowerCase() ||
      c.name.toLowerCase() === rawExchange.toLowerCase()
  );
  if (match) {
    return { exchange: match.name, exchange_code: match.code };
  }
  return { exchange: rawExchange, exchange_code: rawExchange };
}

export function isTargetExchange(exchangeName: string): boolean {
  return TARGET_EXCHANGES.some(
    (target) => target.toLowerCase() === exchangeName.toLowerCase()
  );
}

export function isEligiblePrimaryUsdtMarket(market: {
  base_asset: string;
  quote_asset: string;
  is_perpetual: boolean;
  exchange: string;
}): boolean {
  return (
    typeof market.base_asset === "string" &&
    market.base_asset.trim().toUpperCase() === "BTC" &&
    typeof market.quote_asset === "string" &&
    market.quote_asset.trim().toUpperCase() === "USDT" &&
    market.is_perpetual === true &&
    isTargetExchange(market.exchange)
  );
}

export function isNonEmptyString(val: unknown): val is string {
  return typeof val === "string" && val.trim().length > 0;
}

export function validateRawMarkets(payload: unknown): RawMarket[] {
  if (!Array.isArray(payload)) {
    throw new Error("Invalid future-markets discovery response: expected JSON array");
  }

  const rawMarkets: RawMarket[] = [];

  for (let i = 0; i < payload.length; i++) {
    const item = payload[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Invalid raw market element at index ${i}: expected non-null object`);
    }

    const obj = item as Record<string, unknown>;

    if (!isNonEmptyString(obj.symbol)) {
      throw new Error(`Invalid raw market element at index ${i}: 'symbol' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.exchange)) {
      throw new Error(`Invalid raw market element at index ${i}: 'exchange' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.symbol_on_exchange)) {
      throw new Error(`Invalid raw market element at index ${i}: 'symbol_on_exchange' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.base_asset)) {
      throw new Error(`Invalid raw market element at index ${i}: 'base_asset' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.quote_asset)) {
      throw new Error(`Invalid raw market element at index ${i}: 'quote_asset' must be a non-empty string`);
    }
    if (typeof obj.is_perpetual !== "boolean") {
      throw new Error(`Invalid raw market element at index ${i}: 'is_perpetual' must be a boolean`);
    }

    rawMarkets.push({
      ...obj,
      symbol: obj.symbol.trim(),
      exchange: obj.exchange.trim(),
      symbol_on_exchange: obj.symbol_on_exchange.trim(),
      base_asset: obj.base_asset.trim(),
      quote_asset: obj.quote_asset.trim(),
      is_perpetual: obj.is_perpetual,
      margined: typeof obj.margined === "string" ? obj.margined.trim() : "UNKNOWN",
      expire_at: typeof obj.expire_at === "number" ? obj.expire_at : 0,
      oi_lq_vol_denominated_in:
        typeof obj.oi_lq_vol_denominated_in === "string" ? obj.oi_lq_vol_denominated_in.trim() : "",
    });
  }

  return rawMarkets;
}

export function validateExchangeCatalog(payload: unknown): ExchangeCatalogEntry[] {
  if (!Array.isArray(payload)) {
    throw new Error("Invalid exchanges discovery response: expected JSON array");
  }

  const catalog: ExchangeCatalogEntry[] = [];

  for (let i = 0; i < payload.length; i++) {
    const item = payload[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Invalid exchange catalog element at index ${i}: expected non-null object`);
    }

    const obj = item as Record<string, unknown>;

    if (!isNonEmptyString(obj.name)) {
      throw new Error(`Invalid exchange catalog element at index ${i}: 'name' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.code)) {
      throw new Error(`Invalid exchange catalog element at index ${i}: 'code' must be a non-empty string`);
    }

    catalog.push({
      name: obj.name.trim(),
      code: obj.code.trim(),
    });
  }

  return catalog;
}

export function validateDiscoveredMarketsSnapshot(markets: unknown): DiscoveredMarket[] {
  if (!Array.isArray(markets)) {
    throw new Error("Invalid discovered markets snapshot: expected an array");
  }

  const validated: DiscoveredMarket[] = [];
  const seenSymbols = new Set<string>();

  for (let i = 0; i < markets.length; i++) {
    const item = markets[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Invalid discovered market at index ${i}: expected non-null object`);
    }

    const obj = item as Record<string, unknown>;

    if (!isNonEmptyString(obj.coinalyze_symbol)) {
      throw new Error(`Invalid discovered market at index ${i}: 'coinalyze_symbol' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.exchange)) {
      throw new Error(`Invalid discovered market at index ${i}: 'exchange' must be a non-empty string`);
    }
    if (!isTargetExchange(obj.exchange)) {
      throw new Error(`Invalid discovered market at index ${i}: 'exchange' '${obj.exchange}' is not a target exchange`);
    }
    if (!isNonEmptyString(obj.exchange_code)) {
      throw new Error(`Invalid discovered market at index ${i}: 'exchange_code' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.symbol_on_exchange)) {
      throw new Error(`Invalid discovered market at index ${i}: 'symbol_on_exchange' must be a non-empty string`);
    }
    if (!isNonEmptyString(obj.base_asset)) {
      throw new Error(`Invalid discovered market at index ${i}: 'base_asset' must be a non-empty string`);
    }
    if (obj.base_asset.trim().toUpperCase() !== "BTC") {
      throw new Error(`Invalid discovered market at index ${i}: 'base_asset' must be 'BTC'`);
    }
    if (!isNonEmptyString(obj.quote_asset)) {
      throw new Error(`Invalid discovered market at index ${i}: 'quote_asset' must be a non-empty string`);
    }
    if (obj.is_perpetual !== true) {
      throw new Error(`Invalid discovered market at index ${i}: 'is_perpetual' must be true`);
    }
    if (typeof obj.selected !== "boolean") {
      throw new Error(`Invalid discovered market at index ${i}: 'selected' must be a boolean`);
    }

    // Exact canonical selection policy check: strictly SELECTION_POLICY ("primary_usdt_v1")
    if (!isNonEmptyString(obj.selection_policy) || obj.selection_policy.trim() !== SELECTION_POLICY) {
      throw new Error(
        `Invalid discovered market at index ${i}: 'selection_policy' must strictly be '${SELECTION_POLICY}', found '${obj.selection_policy}'`
      );
    }

    if (!isNonEmptyString(obj.selection_reason)) {
      throw new Error(`Invalid discovered market at index ${i}: 'selection_reason' must be a non-empty string`);
    }

    const trimmedReason = obj.selection_reason.trim();
    if (obj.selected) {
      if (obj.quote_asset.trim().toUpperCase() !== "USDT") {
        throw new Error(
          `Invalid discovered market '${obj.coinalyze_symbol}': selected market must have quote_asset 'USDT', found '${obj.quote_asset}'`
        );
      }
      if (trimmedReason !== PRIMARY_USDT_SELECTION_REASON) {
        throw new Error(
          `Invalid discovered market '${obj.coinalyze_symbol}': selected market must have selection_reason '${PRIMARY_USDT_SELECTION_REASON}', found '${trimmedReason}'`
        );
      }
    } else {
      if (trimmedReason !== ALTERNATIVE_SELECTION_REASON && trimmedReason !== "candidate") {
        throw new Error(
          `Invalid discovered market '${obj.coinalyze_symbol}': non-selected market has invalid selection_reason '${trimmedReason}'`
        );
      }
    }

    if (obj.updated_at_utc !== undefined && !isNonEmptyString(obj.updated_at_utc)) {
      throw new Error(`Invalid discovered market at index ${i}: 'updated_at_utc' must be a non-empty string when provided`);
    }

    const symbolUpper = obj.coinalyze_symbol.trim().toUpperCase();
    if (seenSymbols.has(symbolUpper)) {
      throw new Error(`Invalid discovered markets snapshot: duplicate symbol '${obj.coinalyze_symbol}'`);
    }
    seenSymbols.add(symbolUpper);

    let availability_flags: Record<string, boolean> = {};
    if (obj.availability_flags && typeof obj.availability_flags === "object" && !Array.isArray(obj.availability_flags)) {
      for (const [k, v] of Object.entries(obj.availability_flags as Record<string, unknown>)) {
        if (typeof v === "boolean") {
          availability_flags[k] = v;
        }
      }
    }

    validated.push({
      coinalyze_symbol: obj.coinalyze_symbol.trim(),
      exchange: obj.exchange.trim(),
      exchange_code: obj.exchange_code.trim(),
      symbol_on_exchange: obj.symbol_on_exchange.trim(),
      base_asset: obj.base_asset.trim().toUpperCase(),
      quote_asset: obj.quote_asset.trim().toUpperCase(),
      margined: typeof obj.margined === "string" ? obj.margined.trim() : "UNKNOWN",
      is_perpetual: true,
      expire_at: typeof obj.expire_at === "number" ? obj.expire_at : 0,
      oi_lq_vol_denominated_in:
        typeof obj.oi_lq_vol_denominated_in === "string" ? obj.oi_lq_vol_denominated_in.trim() : "",
      availability_flags,
      selected: obj.selected,
      selection_policy: SELECTION_POLICY,
      selection_reason: trimmedReason,
      ...(obj.updated_at_utc ? { updated_at_utc: (obj.updated_at_utc as string).trim() } : {}),
    });
  }

  // Exact Selection Invariant Validation per target exchange represented in the snapshot:
  // eligible exists -> exactly 1 selected
  // eligible absent -> exactly 0 selected
  const byExchange = new Map<string, DiscoveredMarket[]>();
  for (const m of validated) {
    const exKey = m.exchange.toLowerCase();
    if (!byExchange.has(exKey)) {
      byExchange.set(exKey, []);
    }
    byExchange.get(exKey)!.push(m);
  }

  for (const [, exchangeMarkets] of byExchange.entries()) {
    const exchangeName = exchangeMarkets[0].exchange;
    const eligibleUsdtCandidates = exchangeMarkets.filter(isEligiblePrimaryUsdtMarket);
    const selectedMarkets = exchangeMarkets.filter((m) => m.selected);

    if (eligibleUsdtCandidates.length > 0) {
      if (selectedMarkets.length === 0) {
        throw new Error(
          `Exchange '${exchangeName}' has ${eligibleUsdtCandidates.length} eligible BTC/USDT perpetual candidates, but 0 selected markets`
        );
      }
      if (selectedMarkets.length > 1) {
        throw new Error(
          `Exchange '${exchangeName}' has more than one selected market (${selectedMarkets.length})`
        );
      }

      // Verify that the single selected market matches deterministic tie-break winner
      const sortedEligible = [...eligibleUsdtCandidates].sort((a, b) => {
        const [mA, sA] = usdtCandidateRank(a);
        const [mB, sB] = usdtCandidateRank(b);
        if (mA !== mB) return mA - mB;
        return sA.localeCompare(sB);
      });

      const winningCandidate = sortedEligible[0];
      if (selectedMarkets[0].coinalyze_symbol !== winningCandidate.coinalyze_symbol) {
        throw new Error(
          `Exchange '${exchangeName}' selected '${selectedMarkets[0].coinalyze_symbol}', but deterministic tie-break winner is '${winningCandidate.coinalyze_symbol}'`
        );
      }
    } else {
      // eligibleUsdtCandidates.length === 0: exactly 0 selected
      if (selectedMarkets.length > 0) {
        throw new Error(
          `Exchange '${exchangeName}' has 0 eligible BTC/USDT perpetual candidates, but has ${selectedMarkets.length} selected market(s)`
        );
      }
    }
  }

  return validated;
}

function usdtCandidateRank(market: DiscoveredMarket): [number, string] {
  const marginScore = market.margined.toUpperCase() === "STABLE" ? 0 : 1;
  return [marginScore, market.coinalyze_symbol];
}

export function discoverBtcPerpetuals(
  rawMarkets: RawMarket[],
  exchangeCatalog?: ExchangeCatalogEntry[]
): DiscoveredMarket[] {
  const candidates: DiscoveredMarket[] = [];

  for (const item of rawMarkets) {
    if (item.base_asset !== "BTC" || !item.is_perpetual) {
      continue;
    }

    const { exchange, exchange_code } = resolveExchangeName(
      item.exchange,
      exchangeCatalog
    );

    if (!isTargetExchange(exchange)) {
      continue;
    }

    // Extract all has_* flags
    const availability_flags: Record<string, boolean> = {};
    for (const [key, value] of Object.entries(item)) {
      if (key.startsWith("has_") && typeof value === "boolean") {
        availability_flags[key] = value;
      }
    }

    candidates.push({
      coinalyze_symbol: item.symbol,
      exchange,
      exchange_code,
      symbol_on_exchange: item.symbol_on_exchange,
      base_asset: item.base_asset,
      quote_asset: item.quote_asset,
      margined: item.margined || "UNKNOWN",
      is_perpetual: Boolean(item.is_perpetual),
      expire_at: Number(item.expire_at || 0),
      oi_lq_vol_denominated_in: String(item.oi_lq_vol_denominated_in || ""),
      availability_flags,
      selected: false,
      selection_policy: SELECTION_POLICY,
      selection_reason: ALTERNATIVE_SELECTION_REASON,
    });
  }

  // Group by exchange and select 1 primary USDT perpetual per exchange where available
  const byExchange = new Map<string, DiscoveredMarket[]>();
  for (const cand of candidates) {
    const ex = cand.exchange.toLowerCase();
    if (!byExchange.has(ex)) {
      byExchange.set(ex, []);
    }
    byExchange.get(ex)!.push(cand);
  }

  for (const [, exchangeMarkets] of byExchange.entries()) {
    const eligibleUsdtMarkets = exchangeMarkets.filter(isEligiblePrimaryUsdtMarket);

    if (eligibleUsdtMarkets.length > 0) {
      eligibleUsdtMarkets.sort((a, b) => {
        const [mA, sA] = usdtCandidateRank(a);
        const [mB, sB] = usdtCandidateRank(b);
        if (mA !== mB) return mA - mB;
        return sA.localeCompare(sB);
      });

      const chosen = eligibleUsdtMarkets[0];
      chosen.selected = true;
      chosen.selection_reason = PRIMARY_USDT_SELECTION_REASON;
    }

    // All other markets remain selected = false with selection_reason = ALTERNATIVE_SELECTION_REASON
  }

  return candidates;
}

export function isDiscoveryExpired(lastDiscoveredUtc: string, nowUtc: string): boolean {
  const lastTime = new Date(lastDiscoveredUtc).getTime();
  const nowTime = new Date(nowUtc).getTime();
  if (isNaN(lastTime) || isNaN(nowTime)) return true;
  return nowTime - lastTime > DISCOVERY_CACHE_SECONDS * 1000;
}
