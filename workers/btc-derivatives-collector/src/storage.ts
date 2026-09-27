import { validateDiscoveredMarketsSnapshot } from "./discovery";
import {
  CollectionRun,
  DiscoveredMarket,
  NormalizedDerivativeRow,
  RawEnvelope,
  SyncCheckpoint,
} from "./types";

export class Storage {
  private readonly db: D1Database;

  constructor(db: D1Database) {
    this.db = db;
  }

  async getCachedDiscoveredMarkets(): Promise<{
    markets: DiscoveredMarket[];
    lastUpdatedUtc: string;
  } | null> {
    const res = await this.db
      .prepare(
        `SELECT coinalyze_symbol, exchange, exchange_code, symbol_on_exchange,
                base_asset, quote_asset, margined, is_perpetual, expire_at,
                oi_lq_vol_denominated_in, availability_flags_json, selected,
                selection_policy, selection_reason, updated_at_utc
         FROM discovered_markets`
      )
      .all();

    if (!res.results || res.results.length === 0) {
      return null;
    }

    let maxUpdated = "";
    const rawMarkets: unknown[] = [];

    for (const r of res.results as Record<string, unknown>[]) {
      const updated = typeof r.updated_at_utc === "string" ? r.updated_at_utc.trim() : "";
      if (updated > maxUpdated) {
        maxUpdated = updated;
      }
      let flags: Record<string, boolean> = {};
      try {
        flags = JSON.parse(String(r.availability_flags_json || "{}"));
      } catch {
        flags = {};
      }

      rawMarkets.push({
        coinalyze_symbol: r.coinalyze_symbol,
        exchange: r.exchange,
        exchange_code: r.exchange_code,
        symbol_on_exchange: r.symbol_on_exchange,
        base_asset: r.base_asset,
        quote_asset: r.quote_asset,
        margined: r.margined,
        is_perpetual: r.is_perpetual === 1 || r.is_perpetual === true,
        expire_at: Number(r.expire_at || 0),
        oi_lq_vol_denominated_in: r.oi_lq_vol_denominated_in,
        availability_flags: flags,
        selected: r.selected === 1 || r.selected === true,
        selection_policy: r.selection_policy,
        selection_reason: r.selection_reason,
        updated_at_utc: updated,
      });
    }

    try {
      const validatedMarkets = validateDiscoveredMarketsSnapshot(rawMarkets);
      return { markets: validatedMarkets, lastUpdatedUtc: maxUpdated };
    } catch {
      // Cached snapshot failed runtime validation (e.g. malformed rows, duplicate symbols, etc.)
      return null;
    }
  }

  async saveDiscoveredMarkets(markets: DiscoveredMarket[], updatedAtUtc: string): Promise<void> {
    if (markets.length === 0) return;
    if (!updatedAtUtc || typeof updatedAtUtc !== "string" || updatedAtUtc.trim().length === 0) {
      throw new Error("Invalid updatedAtUtc: must be a non-empty string");
    }

    // Defensive validation before preparing batch statements:
    // Guarantees DELETE is NEVER executed if validation fails!
    const validated = validateDiscoveredMarketsSnapshot(markets);

    // Atomic snapshot replacement: clear previous snapshot and insert newly validated snapshot in a single batch transaction.
    // If any insert fails, D1 rolls back the entire batch, preserving the previous state.
    const stmts: D1PreparedStatement[] = [];
    stmts.push(this.db.prepare(`DELETE FROM discovered_markets`));

    for (const m of validated) {
      stmts.push(
        this.db.prepare(
          `INSERT INTO discovered_markets (
            coinalyze_symbol, exchange, exchange_code, symbol_on_exchange,
            base_asset, quote_asset, margined, is_perpetual, expire_at,
            oi_lq_vol_denominated_in, availability_flags_json, selected,
            selection_policy, selection_reason, updated_at_utc
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          m.coinalyze_symbol,
          m.exchange,
          m.exchange_code,
          m.symbol_on_exchange,
          m.base_asset,
          m.quote_asset,
          m.margined,
          m.is_perpetual ? 1 : 0,
          m.expire_at,
          m.oi_lq_vol_denominated_in,
          JSON.stringify(m.availability_flags),
          m.selected ? 1 : 0,
          m.selection_policy,
          m.selection_reason,
          updatedAtUtc.trim()
        )
      );
    }

    await this.db.batch(stmts);
  }

  async saveRawEnvelope(envelope: RawEnvelope): Promise<void> {
    await this.db
      .prepare(
        `INSERT INTO raw_envelopes (
          request_id, endpoint, params_json, status_code, payload_json, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (request_id) DO NOTHING`
      )
      .bind(
        envelope.request_id,
        envelope.endpoint,
        envelope.params_json,
        envelope.status_code,
        envelope.payload_json,
        envelope.created_at_utc
      )
      .run();
  }

  async saveNormalizedRows(rows: NormalizedDerivativeRow[]): Promise<number> {
    if (rows.length === 0) return 0;

    const stmts: D1PreparedStatement[] = [];
    for (const r of rows) {
      stmts.push(
        this.db.prepare(
          `INSERT INTO normalized_derivatives (
            timestamp_utc, exchange, coinalyze_symbol, symbol_on_exchange,
            interval, source, dataset, oi_usd, long_liquidations_usd,
            short_liquidations_usd, funding_rate, predicted_funding_rate,
            availability_state, raw_request_id, collected_at_utc
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT (timestamp_utc, exchange, coinalyze_symbol, interval, dataset, source)
          DO UPDATE SET
            symbol_on_exchange     = excluded.symbol_on_exchange,
            source                 = excluded.source,
            oi_usd                 = excluded.oi_usd,
            long_liquidations_usd  = excluded.long_liquidations_usd,
            short_liquidations_usd = excluded.short_liquidations_usd,
            funding_rate           = excluded.funding_rate,
            predicted_funding_rate = excluded.predicted_funding_rate,
            availability_state     = excluded.availability_state,
            raw_request_id         = excluded.raw_request_id,
            collected_at_utc       = excluded.collected_at_utc`
        ).bind(
          r.timestamp_utc,
          r.exchange,
          r.coinalyze_symbol,
          r.symbol_on_exchange,
          r.interval,
          r.source,
          r.dataset,
          r.oi_usd,
          r.long_liquidations_usd,
          r.short_liquidations_usd,
          r.funding_rate,
          r.predicted_funding_rate,
          r.availability_state,
          r.raw_request_id,
          r.collected_at_utc
        )
      );
    }

    const CHUNK_SIZE = 50;
    for (let i = 0; i < stmts.length; i += CHUNK_SIZE) {
      await this.db.batch(stmts.slice(i, i + CHUNK_SIZE));
    }

    return rows.length;
  }

  async getCheckpoint(key: string): Promise<SyncCheckpoint | null> {
    const res = await this.db
      .prepare(
        `SELECT checkpoint_key, dataset, coinalyze_symbol, interval,
                covered_through_utc, last_observation_timestamp_utc, updated_at_utc
         FROM sync_checkpoints
         WHERE checkpoint_key = ?`
      )
      .bind(key)
      .first<SyncCheckpoint>();

    return res || null;
  }

  async saveCheckpoint(checkpoint: SyncCheckpoint): Promise<void> {
    await this.db
      .prepare(
        `INSERT INTO sync_checkpoints (
          checkpoint_key, dataset, coinalyze_symbol, interval,
          covered_through_utc, last_observation_timestamp_utc, updated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (checkpoint_key) DO UPDATE SET
          covered_through_utc            = excluded.covered_through_utc,
          last_observation_timestamp_utc = excluded.last_observation_timestamp_utc,
          updated_at_utc                 = excluded.updated_at_utc`
      )
      .bind(
        checkpoint.checkpoint_key,
        checkpoint.dataset,
        checkpoint.coinalyze_symbol,
        checkpoint.interval,
        checkpoint.covered_through_utc,
        checkpoint.last_observation_timestamp_utc,
        checkpoint.updated_at_utc
      )
      .run();
  }

  async recordCollectionRunStart(run: CollectionRun): Promise<void> {
    await this.db
      .prepare(
        `INSERT INTO collection_runs (
          run_id, trigger_type, status, started_at_utc, completed_at_utc,
          rows_inserted, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
      .bind(
        run.run_id,
        run.trigger_type,
        run.status,
        run.started_at_utc,
        run.completed_at_utc,
        run.rows_inserted,
        run.error_message
      )
      .run();
  }

  async recordCollectionRunFinish(
    runId: string,
    status: CollectionRun["status"],
    rowsInserted: number,
    errorMessage?: string | null
  ): Promise<void> {
    const completedAtUtc = new Date().toISOString();
    await this.db
      .prepare(
        `UPDATE collection_runs
         SET status = ?, completed_at_utc = ?, rows_inserted = ?, error_message = ?
         WHERE run_id = ?`
      )
      .bind(status, completedAtUtc, rowsInserted, errorMessage || null, runId)
      .run();
  }
}
