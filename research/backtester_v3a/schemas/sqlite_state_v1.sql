PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO metadata(key, value)
VALUES ('schema_version', 'BACKTESTER_V3A_STATE_V1');

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    exchange TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL CHECK(symbol = upper(symbol)),
    execution_timeframe TEXT NOT NULL,
    timezone TEXT NOT NULL,
    timestamp_semantics TEXT NOT NULL,
    strategy_spec_sha256 TEXT NOT NULL,
    strategy_entrypoint TEXT NOT NULL,
    strategy_parameters_sha256 TEXT NOT NULL,
    trade_price_contract_sha256 TEXT NOT NULL,
    funding_contract_sha256 TEXT,
    mark_price_contract_sha256 TEXT,
    instrument_metadata_contract_sha256 TEXT NOT NULL,
    result_metadata_sha256 TEXT NOT NULL,
    execution_attestation_sha256 TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    code_identity_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('RESERVED', 'COMPLETE', 'FAILED'))
);
