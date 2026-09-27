import { describe, expect, it } from "vitest";
import { normalizeCoinalyzePayload } from "../src/normalizer";
import { DiscoveredMarket } from "../src/types";

const mockMarket: DiscoveredMarket = {
  coinalyze_symbol: "BTCUSDT_PERP.A",
  exchange: "Binance",
  exchange_code: "A",
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

describe("Normalizer", () => {
  const baseTs = 1727440020; // 60s aligned (1727440020 % 60 === 0)

  it("normalizes open interest and preserves null without zero-filling", () => {
    const payload = [
      {
        symbol: "BTCUSDT_PERP.A",
        history: [
          { t: baseTs, o: 100, h: 105, l: 99, c: 102.5 },
          { t: baseTs + 60, o: 102.5, h: 103, l: 101, c: null }, // null observation
        ],
      },
    ];

    const rows = normalizeCoinalyzePayload(
      "open_interest",
      mockMarket,
      "1min",
      "req-1",
      "2026-09-27T12:00:00Z",
      payload,
      baseTs,
      baseTs + 60
    );

    expect(rows).toHaveLength(2);
    expect(rows[0].oi_usd).toBe(102.5);
    expect(rows[0].availability_state).toBe("available");
    expect(rows[0].source).toBe("open-interest-history");
    expect(rows[0].dataset).toBe("open_interest");
    expect(rows[0].long_liquidations_usd).toBeNull();
    expect(rows[0].funding_rate).toBeNull();

    // Null must remain null, NOT zero!
    expect(rows[1].oi_usd).toBeNull();
    expect(rows[1].availability_state).toBe("source_null");
  });

  it("normalizes liquidations with separate long and short values", () => {
    const payload = [
      {
        symbol: "BTCUSDT_PERP.A",
        history: [{ t: baseTs, l: 50000, s: 12000 }],
      },
    ];

    const rows = normalizeCoinalyzePayload(
      "liquidations",
      mockMarket,
      "1min",
      "req-2",
      "2026-09-27T12:00:00Z",
      payload,
      baseTs,
      baseTs
    );

    expect(rows).toHaveLength(1);
    expect(rows[0].long_liquidations_usd).toBe(50000);
    expect(rows[0].short_liquidations_usd).toBe(12000);
    expect(rows[0].oi_usd).toBeNull();
    expect(rows[0].source).toBe("liquidation-history");
    expect(rows[0].dataset).toBe("liquidations");
  });

  it("normalizes funding rate and predicted funding rate", () => {
    const frPayload = [
      {
        symbol: "BTCUSDT_PERP.A",
        history: [{ t: baseTs, c: 0.0001 }],
      },
    ];
    const frRows = normalizeCoinalyzePayload(
      "funding_rate",
      mockMarket,
      "1min",
      "req-3",
      "2026-09-27T12:00:00Z",
      frPayload,
      baseTs,
      baseTs
    );
    expect(frRows[0].funding_rate).toBe(0.0001);
    expect(frRows[0].predicted_funding_rate).toBeNull();
    expect(frRows[0].source).toBe("funding-rate-history");

    const pfrPayload = [
      {
        symbol: "BTCUSDT_PERP.A",
        history: [{ t: baseTs, c: 0.00015 }],
      },
    ];
    const pfrRows = normalizeCoinalyzePayload(
      "predicted_funding_rate",
      mockMarket,
      "1min",
      "req-4",
      "2026-09-27T12:00:00Z",
      pfrPayload,
      baseTs,
      baseTs
    );
    expect(pfrRows[0].predicted_funding_rate).toBe(0.00015);
    expect(pfrRows[0].funding_rate).toBeNull();
    expect(pfrRows[0].source).toBe("predicted-funding-rate-history");
  });

  describe("Strict Validation (Patches 1B & 2)", () => {
    it("accepts valid empty responses: [] and [{ symbol, history: [] }]", () => {
      // Empty array []
      const emptyArrayRows = normalizeCoinalyzePayload(
        "predicted_funding_rate",
        mockMarket,
        "1min",
        "req-empty-1",
        "2026-09-27T12:00:00Z",
        [],
        baseTs,
        baseTs + 60
      );
      expect(emptyArrayRows).toEqual([]);

      // Block with empty history []
      const emptyHistoryRows = normalizeCoinalyzePayload(
        "predicted_funding_rate",
        mockMarket,
        "1min",
        "req-empty-2",
        "2026-09-27T12:00:00Z",
        [{ symbol: "BTCUSDT_PERP.A", history: [] }],
        baseTs,
        baseTs + 60
      );
      expect(emptyHistoryRows).toEqual([]);
    });

    it("throws on unexpected schema: non-array, null, or wrong container", () => {
      expect(() =>
        normalizeCoinalyzePayload(
          "open_interest",
          mockMarket,
          "1min",
          "req-err",
          "2026-09-27T12:00:00Z",
          { error: "bad request" }
        )
      ).toThrow(/Invalid schema: payload must be an array/);
    });

    it("throws on symbol mismatch (PATCH 2A)", () => {
      const payload = [
        {
          symbol: "ETHUSDT_PERP.A", // WRONG SYMBOL
          history: [{ t: baseTs, c: 100 }],
        },
      ];

      expect(() =>
        normalizeCoinalyzePayload(
          "open_interest",
          mockMarket,
          "1min",
          "req-err",
          "2026-09-27T12:00:00Z",
          payload,
          baseTs,
          baseTs
        )
      ).toThrow(/Symbol mismatch/);
    });

    it("throws on non-integer timestamp (PATCH 2B)", () => {
      const payload = [
        {
          symbol: "BTCUSDT_PERP.A",
          history: [{ t: 1727440020.5, c: 100 }],
        },
      ];

      expect(() =>
        normalizeCoinalyzePayload(
          "open_interest",
          mockMarket,
          "1min",
          "req-err",
          "2026-09-27T12:00:00Z",
          payload,
          baseTs,
          baseTs + 60
        )
      ).toThrow(/must be an integer/);
    });

    it("throws on timestamp outside requested range (PATCH 2C & 2D)", () => {
      const payload = [
        {
          symbol: "BTCUSDT_PERP.A",
          history: [{ t: baseTs + 300, c: 100 }], // 300s in the future of toTs
        },
      ];

      expect(() =>
        normalizeCoinalyzePayload(
          "open_interest",
          mockMarket,
          "1min",
          "req-err",
          "2026-09-27T12:00:00Z",
          payload,
          baseTs,
          baseTs + 60
        )
      ).toThrow(/Timestamp out of requested range/);
    });

    it("throws on non-minute-aligned timestamp for interval=1min (PATCH 2E)", () => {
      const payload = [
        {
          symbol: "BTCUSDT_PERP.A",
          history: [{ t: baseTs + 25, c: 100 }], // not aligned to 60s
        },
      ];

      expect(() =>
        normalizeCoinalyzePayload(
          "open_interest",
          mockMarket,
          "1min",
          "req-err",
          "2026-09-27T12:00:00Z",
          payload,
          baseTs,
          baseTs + 60
        )
      ).toThrow(/must be aligned to 60-second boundary/);
    });
  });
});
