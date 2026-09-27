import { describe, expect, it } from "vitest";
import {
  discoverBtcPerpetuals,
  isDiscoveryExpired,
  resolveExchangeName,
  validateDiscoveredMarketsSnapshot,
  validateExchangeCatalog,
  validateRawMarkets,
} from "../src/discovery";
import { DiscoveredMarket, RawMarket } from "../src/types";

function mockMarket(
  symbol: string,
  exchange: string,
  quote: string,
  options?: { isPerpetual?: boolean; margined?: string }
): RawMarket {
  return {
    symbol,
    exchange,
    symbol_on_exchange: symbol.split("_")[0],
    base_asset: "BTC",
    quote_asset: quote,
    is_perpetual: options?.isPerpetual ?? true,
    margined: options?.margined ?? (quote === "USDT" || quote === "USDC" ? "STABLE" : "COIN"),
    expire_at: 0,
    oi_lq_vol_denominated_in: "BASE_ASSET",
    has_ohlcv_data: true,
    has_long_short_ratio_data: true,
  };
}

describe("Market Discovery", () => {
  it("resolves exchange codes using dynamic catalog", () => {
    const catalog = [
      { name: "Binance", code: "binance-code" },
      { name: "Bybit", code: "bybit-code" },
    ];
    const resolved = resolveExchangeName("binance-code", catalog);
    expect(resolved.exchange).toBe("Binance");
    expect(resolved.exchange_code).toBe("binance-code");
  });

  it("selects exactly one primary USDT perpetual per target exchange", () => {
    const raw: RawMarket[] = [
      mockMarket("BTCUSD_PERP.BIN", "Binance", "USD"),
      mockMarket("BTCUSDT_PERP.BIN", "Binance", "USDT"),
      mockMarket("BTCUSDC_PERP.BYB", "Bybit", "USDC"),
      mockMarket("BTCUSDT_PERP.BYB", "Bybit", "USDT"),
      mockMarket("BTCUSDT_PERP.OKX", "OKX", "USDT"),
      mockMarket("ETHUSDT_PERP.OKX", "OKX", "USDT"), // not BTC
      mockMarket("BTCUSDT_EXP.OKX", "OKX", "USDT", { isPerpetual: false }), // not perp
    ];

    const discovered = discoverBtcPerpetuals(raw);
    const selected = discovered.filter((m) => m.selected);

    expect(selected.map((s) => ({ exchange: s.exchange, symbol: s.coinalyze_symbol }))).toEqual([
      { exchange: "Binance", symbol: "BTCUSDT_PERP.BIN" },
      { exchange: "Bybit", symbol: "BTCUSDT_PERP.BYB" },
      { exchange: "OKX", symbol: "BTCUSDT_PERP.OKX" },
    ]);

    // Check non-selected are preserved with reason
    const nonSelected = discovered.filter((m) => !m.selected);
    expect(nonSelected.length).toBeGreaterThan(0);
    expect(nonSelected[0].selection_reason).toBe("alternative_perpetual");
  });

  it("correctly identifies expired discovery after 24h", () => {
    const t0 = "2026-09-27T00:00:00.000Z";
    const tFresh = "2026-09-27T23:59:00.000Z";
    const tExpired = "2026-09-28T00:01:00.000Z";

    expect(isDiscoveryExpired(t0, tFresh)).toBe(false);
    expect(isDiscoveryExpired(t0, tExpired)).toBe(true);
  });
});

describe("Strict Runtime Validation of Raw Catalogs and Snapshots", () => {
  const validMarket: DiscoveredMarket = {
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

  describe("validateRawMarkets", () => {
    it("rejects non-array payloads", () => {
      expect(() => validateRawMarkets(null)).toThrow("expected JSON array");
      expect(() => validateRawMarkets({})).toThrow("expected JSON array");
      expect(() => validateRawMarkets("string")).toThrow("expected JSON array");
    });

    it("rejects elements that are not objects (Case A)", () => {
      expect(() => validateRawMarkets([null])).toThrow("expected non-null object");
      expect(() => validateRawMarkets(["not-an-object"])).toThrow("expected non-null object");
      expect(() => validateRawMarkets([123])).toThrow("expected non-null object");
    });

    it("rejects elements with numeric symbol (Case B)", () => {
      const payload = [
        {
          symbol: 12345,
          exchange: "Binance",
          symbol_on_exchange: "BTCUSDT",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(payload)).toThrow("'symbol' must be a non-empty string");
    });

    it("rejects elements with empty or whitespace symbol (Case C)", () => {
      const emptySymbol = [
        {
          symbol: "",
          exchange: "Binance",
          symbol_on_exchange: "BTCUSDT",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(emptySymbol)).toThrow("'symbol' must be a non-empty string");

      const whitespaceSymbol = [
        {
          symbol: "   ",
          exchange: "Binance",
          symbol_on_exchange: "BTCUSDT",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(whitespaceSymbol)).toThrow("'symbol' must be a non-empty string");
    });

    it("rejects elements with missing required exchange identity fields (Case D)", () => {
      const missingExchange = [
        {
          symbol: "BTCUSDT_PERP.BIN",
          symbol_on_exchange: "BTCUSDT",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(missingExchange)).toThrow("'exchange' must be a non-empty string");

      const missingSymbolOnExchange = [
        {
          symbol: "BTCUSDT_PERP.BIN",
          exchange: "Binance",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(missingSymbolOnExchange)).toThrow(
        "'symbol_on_exchange' must be a non-empty string"
      );

      const missingBase = [
        {
          symbol: "BTCUSDT_PERP.BIN",
          exchange: "Binance",
          symbol_on_exchange: "BTCUSDT",
          quote_asset: "USDT",
          is_perpetual: true,
        },
      ];
      expect(() => validateRawMarkets(missingBase)).toThrow("'base_asset' must be a non-empty string");

      const nonBooleanPerp = [
        {
          symbol: "BTCUSDT_PERP.BIN",
          exchange: "Binance",
          symbol_on_exchange: "BTCUSDT",
          base_asset: "BTC",
          quote_asset: "USDT",
          is_perpetual: "true", // string, not boolean
        },
      ];
      expect(() => validateRawMarkets(nonBooleanPerp)).toThrow("'is_perpetual' must be a boolean");
    });

    it("successfully validates and trims valid raw markets", () => {
      const payload = [
        {
          symbol: " BTCUSDT_PERP.BIN ",
          exchange: " Binance ",
          symbol_on_exchange: " BTCUSDT ",
          base_asset: " BTC ",
          quote_asset: " USDT ",
          is_perpetual: true,
          has_ohlcv_data: true,
        },
      ];
      const validated = validateRawMarkets(payload);
      expect(validated).toHaveLength(1);
      expect(validated[0].symbol).toBe("BTCUSDT_PERP.BIN");
      expect(validated[0].exchange).toBe("Binance");
      expect(validated[0].has_ohlcv_data).toBe(true);
    });
  });

  describe("validateExchangeCatalog", () => {
    it("rejects non-array payloads", () => {
      expect(() => validateExchangeCatalog(null)).toThrow("expected JSON array");
      expect(() => validateExchangeCatalog("not-array")).toThrow("expected JSON array");
    });

    it("rejects elements that are not objects", () => {
      expect(() => validateExchangeCatalog(["Binance"])).toThrow("expected non-null object");
    });

    it("rejects elements with missing, numeric, or whitespace fields (Case E)", () => {
      expect(() => validateExchangeCatalog([{ name: 123, code: "BIN" }])).toThrow(
        "'name' must be a non-empty string"
      );
      expect(() => validateExchangeCatalog([{ name: "Binance", code: 456 }])).toThrow(
        "'code' must be a non-empty string"
      );
      expect(() => validateExchangeCatalog([{ name: "  ", code: "BIN" }])).toThrow(
        "'name' must be a non-empty string"
      );
      expect(() => validateExchangeCatalog([{ name: "Binance", code: "   " }])).toThrow(
        "'code' must be a non-empty string"
      );
    });

    it("successfully validates and trims valid catalog entries", () => {
      const catalog = [
        { name: " Binance ", code: " binance-code " },
        { name: " Bybit ", code: " bybit-code " },
      ];
      const validated = validateExchangeCatalog(catalog);
      expect(validated).toEqual([
        { name: "Binance", code: "binance-code" },
        { name: "Bybit", code: "bybit-code" },
      ]);
    });
  });

  describe("validateDiscoveredMarketsSnapshot", () => {
    it("rejects non-array snapshot", () => {
      expect(() => validateDiscoveredMarketsSnapshot(null)).toThrow("expected an array");
    });

    it("accepts valid empty snapshot", () => {
      expect(validateDiscoveredMarketsSnapshot([])).toEqual([]);
    });

    it("accepts valid snapshot", () => {
      const res = validateDiscoveredMarketsSnapshot([validMarket]);
      expect(res).toHaveLength(1);
      expect(res[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
    });

    it("rejects snapshot containing duplicate identity", () => {
      const duplicate: DiscoveredMarket[] = [
        validMarket,
        {
          ...validMarket,
          selected: false,
          selection_reason: "alternative_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(duplicate)).toThrow("duplicate symbol 'BTCUSDT_PERP.BIN'");
    });

    it("rejects snapshot containing >1 selected market for one exchange (Case H)", () => {
      const multiSelected: DiscoveredMarket[] = [
        validMarket,
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDT_2_PERP.BIN",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(multiSelected)).toThrow(
        "more than one selected market (2)"
      );
    });

    it("Case A: rejects selected BTC/USDC perpetual", () => {
      const selectedUsdc: DiscoveredMarket[] = [
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDC_PERP.BIN",
          quote_asset: "USDC",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(selectedUsdc)).toThrow(
        "selected market must have quote_asset 'USDT', found 'USDC'"
      );
    });

    it("Case B: rejects selected BTC/USD perpetual", () => {
      const selectedUsd: DiscoveredMarket[] = [
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSD_PERP.BIN",
          quote_asset: "USD",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(selectedUsd)).toThrow(
        "selected market must have quote_asset 'USDT', found 'USD'"
      );
    });

    it("Case C & D: rejects wrong or arbitrary selection_policy", () => {
      const wrongPolicy: DiscoveredMarket[] = [
        {
          ...validMarket,
          selection_policy: "primary_usdc_v1",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(wrongPolicy)).toThrow(
        "'selection_policy' must strictly be 'primary_usdt_v1'"
      );

      const arbitraryPolicy: DiscoveredMarket[] = [
        {
          ...validMarket,
          selection_policy: "some_arbitrary_policy",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(arbitraryPolicy)).toThrow(
        "'selection_policy' must strictly be 'primary_usdt_v1'"
      );
    });

    it("Case E: rejects selected market with selection_reason = primary_usdc_perpetual", () => {
      const usdcReason: DiscoveredMarket[] = [
        {
          ...validMarket,
          selection_reason: "primary_usdc_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(usdcReason)).toThrow(
        "must have selection_reason 'primary_usdt_perpetual'"
      );
    });

    it("Case F: rejects selection_reason starting with primary_ but not canonical reason", () => {
      const customPrimary: DiscoveredMarket[] = [
        {
          ...validMarket,
          selection_reason: "primary_custom_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(customPrimary)).toThrow(
        "must have selection_reason 'primary_usdt_perpetual'"
      );
    });

    it("Case G: rejects exchange with eligible BTCUSDT perpetual candidate when selected count = 0", () => {
      const zeroSelected: DiscoveredMarket[] = [
        {
          ...validMarket,
          selected: false,
          selection_reason: "alternative_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(zeroSelected)).toThrow(
        "has 1 eligible BTC/USDT perpetual candidates, but 0 selected markets"
      );
    });

    it("Case I: accepts exchange with eligible BTCUSDT perpetual candidates and exactly 1 selected", () => {
      const oneSelected: DiscoveredMarket[] = [
        validMarket,
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDT_2_PERP.BIN",
          margined: "COIN", // worse rank than STABLE
          selected: false,
          selection_reason: "alternative_perpetual",
        },
      ];
      const validated = validateDiscoveredMarketsSnapshot(oneSelected);
      expect(validated).toHaveLength(2);
      expect(validated.filter((m) => m.selected)).toHaveLength(1);
    });

    it("Case J: accepts exchange represented only by non-USDT perpetual markets with selected count = 0", () => {
      const nonUsdtExchange: DiscoveredMarket[] = [
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDC_PERP.BIN",
          quote_asset: "USDC",
          selected: false,
          selection_reason: "alternative_perpetual",
        },
      ];
      const validated = validateDiscoveredMarketsSnapshot(nonUsdtExchange);
      expect(validated).toHaveLength(1);
      expect(validated[0].selected).toBe(false);
    });

    it("Case M: accepts valid snapshot containing only Binance when other exchanges are absent", () => {
      const onlyBinance: DiscoveredMarket[] = [validMarket];
      const validated = validateDiscoveredMarketsSnapshot(onlyBinance);
      expect(validated).toHaveLength(1);
      expect(validated[0].exchange).toBe("Binance");
    });

    it("rejects snapshot with non-target exchange or non-BTC asset", () => {
      const nonTarget: DiscoveredMarket[] = [
        {
          ...validMarket,
          exchange: "Kraken",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(nonTarget)).toThrow("is not a target exchange");

      const nonBtc: DiscoveredMarket[] = [
        {
          ...validMarket,
          base_asset: "ETH",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(nonBtc)).toThrow("'base_asset' must be 'BTC'");
    });

    it("rejects snapshot if is_perpetual is not true", () => {
      const nonPerp: any[] = [
        {
          ...validMarket,
          is_perpetual: false,
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(nonPerp)).toThrow("'is_perpetual' must be true");
    });
  });

  describe("Selector Canonical USDT Contract (Cases K & L)", () => {
    it("Case K: selector does NOT fallback to USDC when USDT is absent", () => {
      const raw: RawMarket[] = [
        mockMarket("BTCUSDC_PERP.BIN", "Binance", "USDC"),
        mockMarket("BTCUSD_PERP.BIN", "Binance", "USD"),
      ];

      const discovered = discoverBtcPerpetuals(raw);
      expect(discovered).toHaveLength(2);
      // Zero selected because no eligible USDT perpetual exists for Binance
      const selected = discovered.filter((m) => m.selected);
      expect(selected).toHaveLength(0);

      // Snapshot passes validation under exactly-zero-selected invariant
      const validated = validateDiscoveredMarketsSnapshot(discovered);
      expect(validated.filter((m) => m.selected)).toHaveLength(0);
    });

    it("Case L: selector with USDT + USDC selects only eligible USDT candidate deterministically", () => {
      const raw: RawMarket[] = [
        mockMarket("BTCUSDC_PERP.BIN", "Binance", "USDC"),
        mockMarket("BTCUSDT_COIN_PERP.BIN", "Binance", "USDT", { margined: "COIN" }),
        mockMarket("BTCUSDT_PERP.BIN", "Binance", "USDT", { margined: "STABLE" }),
      ];

      const discovered = discoverBtcPerpetuals(raw);
      const selected = discovered.filter((m) => m.selected);
      expect(selected).toHaveLength(1);
      expect(selected[0].coinalyze_symbol).toBe("BTCUSDT_PERP.BIN");
      expect(selected[0].quote_asset).toBe("USDT");
      expect(selected[0].selection_reason).toBe("primary_usdt_perpetual");
    });

    it("Gap A: rejects snapshot when an eligible USDT candidate is selected but is NOT the deterministic winner", () => {
      // Binance has two eligible USDT candidates:
      // 1. BTCUSDT_PERP.BIN (margined: "STABLE") -> deterministic winner
      // 2. BTCUSDT_COIN_PERP.BIN (margined: "COIN") -> worse margin rank
      // If BTCUSDT_COIN_PERP.BIN is marked selected instead of the STABLE winner:
      const wrongWinnerSnapshot: DiscoveredMarket[] = [
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDT_PERP.BIN",
          margined: "STABLE",
          selected: false,
          selection_reason: "alternative_perpetual",
        },
        {
          ...validMarket,
          coinalyze_symbol: "BTCUSDT_COIN_PERP.BIN",
          margined: "COIN",
          selected: true,
          selection_reason: "primary_usdt_perpetual",
        },
      ];

      expect(() => validateDiscoveredMarketsSnapshot(wrongWinnerSnapshot)).toThrow(
        "selected 'BTCUSDT_COIN_PERP.BIN', but deterministic tie-break winner is 'BTCUSDT_PERP.BIN'"
      );
    });

    it("Gap B: deterministic winner between equally-ranked eligible USDT candidates is chosen by alphabetical tie-break", () => {
      // Both have margined: "STABLE", quote_asset: "USDT", base_asset: "BTC", is_perpetual: true
      // "BTCUSDT_A_PERP.BIN" < "BTCUSDT_B_PERP.BIN"
      const raw: RawMarket[] = [
        mockMarket("BTCUSDT_B_PERP.BIN", "Binance", "USDT", { margined: "STABLE" }),
        mockMarket("BTCUSDT_A_PERP.BIN", "Binance", "USDT", { margined: "STABLE" }),
      ];

      const discovered = discoverBtcPerpetuals(raw);
      const selected = discovered.filter((m) => m.selected);

      expect(selected).toHaveLength(1);
      // Alphabetical winner strictly checked
      expect(selected[0].coinalyze_symbol).toBe("BTCUSDT_A_PERP.BIN");
      expect(selected[0].selection_reason).toBe("primary_usdt_perpetual");

      // Verify validator confirms BTCUSDT_A_PERP.BIN is the winner
      const validated = validateDiscoveredMarketsSnapshot(discovered);
      expect(validated.find((m) => m.selected)?.coinalyze_symbol).toBe("BTCUSDT_A_PERP.BIN");

      // And if BTCUSDT_B_PERP.BIN was marked selected instead, validator rejects
      const invertedWinner: DiscoveredMarket[] = [
        {
          ...discovered[0],
          selected: discovered[0].coinalyze_symbol === "BTCUSDT_B_PERP.BIN",
          selection_reason:
            discovered[0].coinalyze_symbol === "BTCUSDT_B_PERP.BIN"
              ? "primary_usdt_perpetual"
              : "alternative_perpetual",
        },
        {
          ...discovered[1],
          selected: discovered[1].coinalyze_symbol === "BTCUSDT_B_PERP.BIN",
          selection_reason:
            discovered[1].coinalyze_symbol === "BTCUSDT_B_PERP.BIN"
              ? "primary_usdt_perpetual"
              : "alternative_perpetual",
        },
      ];
      expect(() => validateDiscoveredMarketsSnapshot(invertedWinner)).toThrow(
        "deterministic tie-break winner is 'BTCUSDT_A_PERP.BIN'"
      );
    });
  });
});
