from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from research.backtester_v3a.contracts import (
    DATASET_IDENTITY_SCHEMA,
    INSTRUMENT_METADATA_SCHEMA,
    STRATEGY_SPEC_SCHEMA,
    canonical_sha256,
)


HASH_D = "d" * 64


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def dataset_contract(
    root: Path,
    *,
    role: str,
    symbol: str,
    rows: List[Dict[str, object]],
    columns: List[str],
    data_timeframe: str,
    timestamp_semantics: str,
    coverage_start_ms: int = 0,
    coverage_end_ms: int = 120_000,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    data_path = root / f"{symbol}-{role}.csv"
    manifest_path = root / f"{symbol}-{role}-manifest.json"
    contract_path = root / f"{symbol}-{role}-contract.json"
    write_csv(data_path, columns, rows)
    manifest = {
        "schema_version": "BACKTESTER_V3A_DATA_MANIFEST_V1",
        "role": role,
        "format": "csv",
        "data_path": str(data_path.resolve()),
        "data_sha256": sha256_file(data_path),
        "columns": columns,
        "row_count": len(rows),
    }
    write_json(manifest_path, manifest)
    contract = {
        "schema_version": DATASET_IDENTITY_SCHEMA,
        "role": role,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "data_timeframe": data_timeframe,
        "timezone": "UTC",
        "timestamp_semantics": timestamp_semantics,
        "dataset_id": f"SYNTHETIC-{symbol}-{role}",
        "dataset_sha256": sha256_file(data_path),
        "manifest_path": str(manifest_path.resolve()),
        "manifest_id": f"SYNTHETIC-{symbol}-{role}-MANIFEST",
        "manifest_sha256": sha256_file(manifest_path),
        "coverage_start_ms": coverage_start_ms,
        "coverage_end_ms": coverage_end_ms,
    }
    write_json(contract_path, contract)
    return contract_path


def metadata_contract(
    root: Path,
    *,
    symbol: str,
    tick_size: str = "0.10",
    step_size: str = "0.001",
    min_qty: str = "0.001",
    min_notional: str = "5",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source_path = root / f"{symbol}-metadata-source.json"
    contract_path = root / f"{symbol}-metadata-contract.json"
    write_json(source_path, {"source": "synthetic fixture", "symbol": symbol})
    payload = {
        "schema_version": INSTRUMENT_METADATA_SCHEMA,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "metadata_id": f"SYNTHETIC-{symbol}-METADATA",
        "tick_size": tick_size,
        "step_size": step_size,
        "min_qty": min_qty,
        "min_notional": min_notional,
        "price_precision": 2,
        "quantity_precision": 3,
        "provenance": {
            "fidelity_classification": "HISTORICAL_VERIFIED",
            "source": str(source_path.resolve()),
            "source_sha256": sha256_file(source_path),
            "effective_start_ms": 0,
            "effective_end_ms": 120_000,
        },
    }
    write_json(contract_path, payload)
    return contract_path


def base_rows(price: float = 100.0) -> List[Dict[str, object]]:
    return [
        {
            "open_time": index * 60_000,
            "open": price + index,
            "high": price + index + 2,
            "low": price + index - 2,
            "close": price + index + 1,
            "volume": 10,
        }
        for index in range(3)
    ]


def build_input_contracts(
    root: Path,
    *,
    symbol: str = "BTCUSDT",
    require_funding: bool = True,
    require_mark: bool = True,
    price: float = 100.0,
    tick_size: str = "0.10",
    step_size: str = "0.001",
    min_qty: str = "0.001",
    min_notional: str = "5",
) -> Dict[str, Optional[Path]]:
    trade_rows = base_rows(price)
    trade = dataset_contract(
        root,
        role="trade_price",
        symbol=symbol,
        rows=trade_rows,
        columns=["open_time", "open", "high", "low", "close", "volume"],
        data_timeframe="1m",
        timestamp_semantics="bar open UTC",
    )
    funding = None
    if require_funding:
        funding = dataset_contract(
            root,
            role="funding",
            symbol=symbol,
            rows=[{"open_time": 120_000, "rate": "0.001", "price": str(price + 2)}],
            columns=["open_time", "rate", "price"],
            data_timeframe="event",
            timestamp_semantics="funding event UTC",
        )
    mark = None
    if require_mark:
        mark_rows = [
            {
                "open_time": row["open_time"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
            }
            for row in trade_rows
        ]
        mark = dataset_contract(
            root,
            role="mark_price",
            symbol=symbol,
            rows=mark_rows,
            columns=["open_time", "open", "high", "low", "close"],
            data_timeframe="1m",
            timestamp_semantics="bar open UTC",
        )
    metadata = metadata_contract(
        root,
        symbol=symbol,
        tick_size=tick_size,
        step_size=step_size,
        min_qty=min_qty,
        min_notional=min_notional,
    )
    return {
        "trade_price": trade,
        "funding": funding,
        "mark_price": mark,
        "instrument_metadata": metadata,
    }


def _payload(path: Path) -> Dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def strategy_spec_payload(
    paths: Dict[str, Optional[Path]],
    *,
    symbol: str = "BTCUSDT",
    execution_config_sha256: str = HASH_D,
    parameters: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    if parameters is None:
        parameters = {"side": "long", "qty": 1.0}

    def requirement(path: Optional[Path]) -> Dict[str, object]:
        if path is None:
            return {
                "mode": "EXPLICITLY_NOT_USED",
                "contract_sha256": None,
                "absence_policy": "EXPLICITLY_NOT_USED_BY_FROZEN_SPEC",
            }
        return {
            "mode": "REQUIRED",
            "contract_sha256": canonical_sha256(_payload(path)),
            "absence_policy": None,
        }

    return {
        "schema_version": STRATEGY_SPEC_SCHEMA,
        "status": "FROZEN",
        "strategy_id": "PHASE3-SYNTHETIC",
        "strategy_version": "V3A",
        "candidate_id": "PHASE3",
        "variant_id": f"PHASE3-{symbol}",
        "execution_identity": {
            "exchange": "Binance",
            "market": "USD-M perpetual",
            "symbol": symbol,
            "execution_timeframe": "1m",
            "timezone": "UTC",
            "timestamp_semantics": "bar open UTC",
        },
        "implementation": {
            "strategy_entrypoint": (
                "research.backtester_v3a.synthetic.OneShotGeometryStrategy"
            ),
            "parameters": parameters,
            "parameters_sha256": canonical_sha256(parameters),
            "execution_config_sha256": execution_config_sha256,
        },
        "data_requirements": {
            "trade_price": requirement(paths["trade_price"]),
            "funding": requirement(paths["funding"]),
            "mark_price": requirement(paths["mark_price"]),
            "instrument_metadata": requirement(paths["instrument_metadata"]),
        },
    }
