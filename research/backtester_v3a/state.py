"""Physically isolated canonical SQLite identity state for Backtester V3-A."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .contracts import (
    ContractError,
    ExecutionIdentity,
    RunReceiptV3A,
    canonical_sha256,
)


STATE_SCHEMA = "BACKTESTER_V3A_STATE_V1"
V3A_STATE_RELATIVE_PATH = Path(".strategy-replication/v3a/enforcement-v1.sqlite3")
_SCHEMA_PATH = Path(__file__).with_name("schemas") / "sqlite_state_v1.sql"


@dataclass(frozen=True)
class RunStateIdentity:
    run_id: str
    execution_id: str
    execution_identity: ExecutionIdentity
    strategy_spec_sha256: str
    strategy_entrypoint: str
    strategy_parameters_sha256: str
    trade_price_contract_sha256: str
    funding_contract_sha256: Optional[str]
    mark_price_contract_sha256: Optional[str]
    instrument_metadata_contract_sha256: str
    result_metadata_sha256: str
    execution_attestation_sha256: str
    receipt_sha256: str
    code_identity_sha256: str
    status: str

    @classmethod
    def from_receipt(cls, receipt: RunReceiptV3A) -> "RunStateIdentity":
        return cls(
            run_id=receipt.run_id,
            execution_id=receipt.execution_id,
            execution_identity=receipt.execution_identity,
            strategy_spec_sha256=receipt.strategy_spec_sha256,
            strategy_entrypoint=receipt.strategy_entrypoint,
            strategy_parameters_sha256=receipt.strategy_parameters_sha256,
            trade_price_contract_sha256=receipt.trade_price_contract_sha256,
            funding_contract_sha256=receipt.funding_contract_sha256,
            mark_price_contract_sha256=receipt.mark_price_contract_sha256,
            instrument_metadata_contract_sha256=(
                receipt.instrument_metadata_contract_sha256
            ),
            result_metadata_sha256=receipt.result_metadata_sha256,
            execution_attestation_sha256=receipt.execution_attestation_sha256,
            receipt_sha256=canonical_sha256(receipt.to_payload()),
            code_identity_sha256=receipt.code_identity_sha256,
            status="COMPLETE",
        )


def initialize_state(path: Path) -> None:
    """Create an isolated V3-A state database from the checked-in schema."""
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    connection = sqlite3.connect(resolved)
    try:
        connection.executescript(schema)
        row = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'",
        ).fetchone()
        if row != (STATE_SCHEMA,):
            raise ContractError("V3-A canonical state schema identity mismatch")
        connection.commit()
    finally:
        connection.close()


def insert_run_identity(path: Path, record: RunStateIdentity) -> None:
    connection = sqlite3.connect(path.resolve())
    try:
        connection.execute(
            """
            INSERT INTO runs(
                run_id, execution_id, exchange, market, symbol,
                execution_timeframe, timezone, timestamp_semantics,
                strategy_spec_sha256, strategy_entrypoint,
                strategy_parameters_sha256, trade_price_contract_sha256,
                funding_contract_sha256, mark_price_contract_sha256,
                instrument_metadata_contract_sha256, result_metadata_sha256,
                execution_attestation_sha256, receipt_sha256,
                code_identity_sha256, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.execution_id,
                record.execution_identity.exchange,
                record.execution_identity.market,
                record.execution_identity.symbol,
                record.execution_identity.execution_timeframe,
                record.execution_identity.timezone,
                record.execution_identity.timestamp_semantics,
                record.strategy_spec_sha256,
                record.strategy_entrypoint,
                record.strategy_parameters_sha256,
                record.trade_price_contract_sha256,
                record.funding_contract_sha256,
                record.mark_price_contract_sha256,
                record.instrument_metadata_contract_sha256,
                record.result_metadata_sha256,
                record.execution_attestation_sha256,
                record.receipt_sha256,
                record.code_identity_sha256,
                record.status,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def update_run_status(
    path: Path,
    run_id: str,
    *,
    expected_status: str,
    new_status: str,
) -> None:
    """Perform one guarded state transition for an existing V3-A run."""
    allowed = {
        ("RESERVED", "COMPLETE"),
        ("RESERVED", "FAILED"),
        ("COMPLETE", "FAILED"),
    }
    if (expected_status, new_status) not in allowed:
        raise ContractError("invalid V3-A canonical state transition")
    connection = sqlite3.connect(path.resolve())
    try:
        updated = connection.execute(
            "UPDATE runs SET status=? WHERE run_id=? AND status=?",
            (new_status, run_id, expected_status),
        ).rowcount
        if updated != 1:
            raise ContractError("V3-A canonical state transition target mismatch")
        connection.commit()
    finally:
        connection.close()


def load_run_identity(path: Path, run_id: str) -> RunStateIdentity:
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro", uri=True,
    )
    try:
        schema = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'",
        ).fetchone()
        if schema != (STATE_SCHEMA,):
            raise ContractError("V3-A canonical state schema identity mismatch")
        row = connection.execute(
            """
            SELECT
                run_id, execution_id, exchange, market, symbol,
                execution_timeframe, timezone, timestamp_semantics,
                strategy_spec_sha256, strategy_entrypoint,
                strategy_parameters_sha256, trade_price_contract_sha256,
                funding_contract_sha256, mark_price_contract_sha256,
                instrument_metadata_contract_sha256, result_metadata_sha256,
                execution_attestation_sha256, receipt_sha256,
                code_identity_sha256, status
            FROM runs WHERE run_id=?
            """,
            (run_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ContractError(f"V3-A canonical state has no run {run_id}")
    return RunStateIdentity(
        run_id=row[0],
        execution_id=row[1],
        execution_identity=ExecutionIdentity(
            exchange=row[2],
            market=row[3],
            symbol=row[4],
            execution_timeframe=row[5],
            timezone=row[6],
            timestamp_semantics=row[7],
        ),
        strategy_spec_sha256=row[8],
        strategy_entrypoint=row[9],
        strategy_parameters_sha256=row[10],
        trade_price_contract_sha256=row[11],
        funding_contract_sha256=row[12],
        mark_price_contract_sha256=row[13],
        instrument_metadata_contract_sha256=row[14],
        result_metadata_sha256=row[15],
        execution_attestation_sha256=row[16],
        receipt_sha256=row[17],
        code_identity_sha256=row[18],
        status=row[19],
    )


__all__ = [
    "STATE_SCHEMA",
    "V3A_STATE_RELATIVE_PATH",
    "RunStateIdentity",
    "initialize_state",
    "insert_run_identity",
    "load_run_identity",
    "update_run_status",
]
