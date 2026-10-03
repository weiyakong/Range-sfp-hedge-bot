"""Generic, manifest-bound single-symbol input resolution for V3-A."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from research.backtester_v2.models import Bar

from .contracts import (
    BoundExecutionContracts,
    ContractError,
    DatasetIdentity,
    InstrumentMetadata,
    StrategySpecV2,
    bind_execution_contracts,
    parse_dataset_identity,
    parse_instrument_metadata,
    require_dataset_coverage,
)


DATA_MANIFEST_SCHEMA = "BACKTESTER_V3A_DATA_MANIFEST_V1"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMEFRAME_RE = re.compile(r"^(\d+)([mhd])$")


class ResolutionError(ValueError):
    """Raised when a locator, manifest, or payload fails reproducibility checks."""


@dataclass(frozen=True)
class InputContractLocators:
    trade_price: Optional[Path]
    funding: Optional[Path]
    mark_price: Optional[Path]
    instrument_metadata: Optional[Path]


@dataclass(frozen=True)
class DataManifest:
    role: str
    data_path: Path
    data_sha256: str
    columns: Tuple[str, ...]
    row_count: int


@dataclass(frozen=True)
class ResolvedExecutionInputs:
    bound: BoundExecutionContracts
    bars: Tuple[Bar, ...]
    funding_rate_by_time: Mapping[int, float]
    funding_price_by_time: Mapping[int, float]
    metadata: InstrumentMetadata


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_object(path: Path, label: str) -> Mapping[str, object]:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ResolutionError(f"{label} must be a regular file: {resolved}")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"cannot read {label}: {resolved}: {exc}") from exc
    if not isinstance(value, dict):
        raise ResolutionError(f"{label} must contain one JSON object")
    return value


def _exact_keys(value: Mapping[str, object], expected: Sequence[str], label: str) -> None:
    missing = sorted(set(expected) - set(value))
    extra = sorted(set(value) - set(expected))
    if missing or extra:
        raise ResolutionError(
            f"{label} fields mismatch; missing={missing}, unexpected={extra}",
        )


def _load_dataset_contract(path: Optional[Path]) -> Optional[DatasetIdentity]:
    if path is None:
        return None
    return parse_dataset_identity(_json_object(path, "dataset contract"))


def _load_metadata_contract(path: Optional[Path]) -> Optional[InstrumentMetadata]:
    if path is None:
        return None
    metadata = parse_instrument_metadata(_json_object(path, "metadata contract"))
    source_path = Path(metadata.provenance.source)
    if not source_path.is_absolute():
        raise ResolutionError("metadata provenance source must be an absolute locator")
    if not source_path.is_file() or source_path.is_symlink():
        raise ResolutionError("metadata provenance source must be a regular file")
    if sha256_file(source_path) != metadata.provenance.source_sha256:
        raise ResolutionError("metadata provenance SHA-256 mismatch")
    return metadata


def _load_manifest(identity: DatasetIdentity) -> DataManifest:
    manifest_path = Path(identity.manifest_path).resolve()
    if sha256_file(manifest_path) != identity.manifest_sha256:
        raise ResolutionError(f"{identity.role} manifest SHA-256 mismatch")
    payload = _json_object(manifest_path, f"{identity.role} manifest")
    _exact_keys(payload, (
        "schema_version", "role", "format", "data_path", "data_sha256",
        "columns", "row_count",
    ), f"{identity.role} manifest")
    if payload["schema_version"] != DATA_MANIFEST_SCHEMA:
        raise ResolutionError(f"{identity.role} manifest schema mismatch")
    if payload["role"] != identity.role:
        raise ResolutionError(f"{identity.role} manifest role mismatch")
    if payload["format"] != "csv":
        raise ResolutionError(f"{identity.role} manifest format must equal csv")
    data_path_value = payload["data_path"]
    if not isinstance(data_path_value, str) or not Path(data_path_value).is_absolute():
        raise ResolutionError(f"{identity.role} data_path must be absolute")
    data_path = Path(data_path_value).resolve()
    if not data_path.is_file() or data_path.is_symlink():
        raise ResolutionError(f"{identity.role} data_path must be a regular file")
    data_hash = payload["data_sha256"]
    if not isinstance(data_hash, str) or _HASH_RE.fullmatch(data_hash) is None:
        raise ResolutionError(f"{identity.role} data_sha256 is invalid")
    actual_hash = sha256_file(data_path)
    if actual_hash != data_hash or actual_hash != identity.dataset_sha256:
        raise ResolutionError(f"{identity.role} data SHA-256 mismatch")
    columns_value = payload["columns"]
    if (
        not isinstance(columns_value, list)
        or not columns_value
        or any(not isinstance(item, str) or not item for item in columns_value)
    ):
        raise ResolutionError(f"{identity.role} manifest columns are invalid")
    row_count = payload["row_count"]
    if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count < 0:
        raise ResolutionError(f"{identity.role} manifest row_count is invalid")
    return DataManifest(
        role=identity.role,
        data_path=data_path,
        data_sha256=data_hash,
        columns=tuple(columns_value),
        row_count=row_count,
    )


def _csv_rows(manifest: DataManifest, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
    if manifest.columns != tuple(expected_columns):
        raise ResolutionError(f"{manifest.role} manifest columns mismatch")
    with manifest.data_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != manifest.columns:
            raise ResolutionError(f"{manifest.role} CSV header differs from manifest")
        rows = [dict(row) for row in reader]
    if len(rows) != manifest.row_count:
        raise ResolutionError(f"{manifest.role} row_count differs from manifest")
    return rows


def _number(value: str, path: str, *, positive: bool = True) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ResolutionError(f"{path} must be numeric") from exc
    if not isfinite(result) or (positive and result <= 0):
        qualifier = "positive and finite" if positive else "finite"
        raise ResolutionError(f"{path} must be {qualifier}")
    return result


def _timestamp(value: str, path: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ResolutionError(f"{path} must be an integer timestamp") from exc
    if result < 0:
        raise ResolutionError(f"{path} must be non-negative")
    return result


def _timeframe_ms(value: str) -> int:
    match = _TIMEFRAME_RE.fullmatch(value)
    if match is None:
        raise ResolutionError(f"unsupported execution timeframe: {value}")
    multiplier = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}[match.group(2)]
    return int(match.group(1)) * multiplier


def _load_trade(identity: DatasetIdentity) -> Tuple[Bar, ...]:
    rows = _csv_rows(
        _load_manifest(identity),
        ("open_time", "open", "high", "low", "close", "volume"),
    )
    bars: List[Bar] = []
    for index, row in enumerate(rows):
        timestamp = _timestamp(row["open_time"], f"trade_price[{index}].open_time")
        open_price = _number(row["open"], f"trade_price[{index}].open")
        high = _number(row["high"], f"trade_price[{index}].high")
        low = _number(row["low"], f"trade_price[{index}].low")
        close = _number(row["close"], f"trade_price[{index}].close")
        volume = _number(row["volume"], f"trade_price[{index}].volume", positive=False)
        if volume < 0:
            raise ResolutionError(f"trade_price[{index}].volume must be non-negative")
        if high < max(open_price, low, close) or low > min(open_price, high, close):
            raise ResolutionError(f"trade_price[{index}] has invalid OHLC")
        bars.append(Bar(timestamp, open_price, high, low, close, volume))
    if not bars:
        raise ResolutionError("trade_price dataset must not be empty")
    interval = _timeframe_ms(identity.data_timeframe)
    for previous, current in zip(bars, bars[1:]):
        if current.open_time - previous.open_time != interval:
            raise ResolutionError("trade_price timestamps must be unique, ordered, and gap-free")
    if bars[0].open_time < identity.coverage_start_ms:
        raise ResolutionError("trade_price begins before declared coverage")
    if bars[-1].open_time > identity.coverage_end_ms:
        raise ResolutionError("trade_price ends after declared coverage")
    return tuple(bars)


def _load_funding(identity: DatasetIdentity) -> Tuple[Dict[int, float], Dict[int, float]]:
    rows = _csv_rows(
        _load_manifest(identity),
        ("open_time", "rate", "price"),
    )
    rates: Dict[int, float] = {}
    prices: Dict[int, float] = {}
    last: Optional[int] = None
    for index, row in enumerate(rows):
        timestamp = _timestamp(row["open_time"], f"funding[{index}].open_time")
        if last is not None and timestamp <= last:
            raise ResolutionError("funding timestamps must be strictly ordered and unique")
        if timestamp < identity.coverage_start_ms or timestamp > identity.coverage_end_ms:
            raise ResolutionError("funding event lies outside declared coverage")
        rates[timestamp] = _number(
            row["rate"], f"funding[{index}].rate", positive=False,
        )
        prices[timestamp] = _number(row["price"], f"funding[{index}].price")
        last = timestamp
    return rates, prices


def _attach_mark(
    trade: Tuple[Bar, ...], identity: DatasetIdentity,
) -> Tuple[Bar, ...]:
    rows = _csv_rows(
        _load_manifest(identity),
        ("open_time", "open", "high", "low", "close"),
    )
    if len(rows) != len(trade):
        raise ResolutionError("mark_price rows must align one-to-one with trade bars")
    combined: List[Bar] = []
    for index, (bar, row) in enumerate(zip(trade, rows)):
        timestamp = _timestamp(row["open_time"], f"mark_price[{index}].open_time")
        if timestamp != bar.open_time:
            raise ResolutionError("mark_price timestamp differs from trade-price timestamp")
        mark_open = _number(row["open"], f"mark_price[{index}].open")
        mark_high = _number(row["high"], f"mark_price[{index}].high")
        mark_low = _number(row["low"], f"mark_price[{index}].low")
        mark_close = _number(row["close"], f"mark_price[{index}].close")
        if (
            mark_high < max(mark_open, mark_low, mark_close)
            or mark_low > min(mark_open, mark_high, mark_close)
        ):
            raise ResolutionError(f"mark_price[{index}] has invalid OHLC")
        combined.append(Bar(
            open_time=bar.open_time,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            mark_open=mark_open,
            mark_high=mark_high,
            mark_low=mark_low,
            mark_close=mark_close,
        ))
    return tuple(combined)


def resolve_execution_inputs(
    spec: StrategySpecV2,
    locators: InputContractLocators,
    required_start_ms: int,
    required_end_ms: int,
) -> ResolvedExecutionInputs:
    """Resolve all inputs from frozen spec authority; no symbol argument exists."""
    trade = _load_dataset_contract(locators.trade_price)
    funding = _load_dataset_contract(locators.funding)
    mark = _load_dataset_contract(locators.mark_price)
    metadata = _load_metadata_contract(locators.instrument_metadata)
    bound = bind_execution_contracts(
        spec,
        trade_price=trade,
        funding=funding,
        mark_price=mark,
        instrument_metadata=metadata,
    )
    for role, dataset in (
        ("trade_price", bound.trade_price),
        ("funding", bound.funding),
        ("mark_price", bound.mark_price),
    ):
        if dataset is not None:
            require_dataset_coverage(
                dataset,
                required_start_ms=required_start_ms,
                required_end_ms=required_end_ms,
                path=role,
            )
    provenance = bound.instrument_metadata.provenance
    if provenance.fidelity_classification == "HISTORICAL_VERIFIED":
        if (
            provenance.effective_start_ms is None
            or provenance.effective_end_ms is None
            or provenance.effective_start_ms > required_start_ms
            or provenance.effective_end_ms < required_end_ms
        ):
            raise ContractError("instrument metadata does not cover execution window")
    bars = _load_trade(bound.trade_price)
    rates: Dict[int, float] = {}
    prices: Dict[int, float] = {}
    if bound.funding is not None:
        rates, prices = _load_funding(bound.funding)
    if bound.mark_price is not None:
        bars = _attach_mark(bars, bound.mark_price)
    return ResolvedExecutionInputs(
        bound=bound,
        bars=bars,
        funding_rate_by_time=rates,
        funding_price_by_time=prices,
        metadata=bound.instrument_metadata,
    )


__all__ = [
    "DATA_MANIFEST_SCHEMA",
    "DataManifest",
    "InputContractLocators",
    "ResolutionError",
    "ResolvedExecutionInputs",
    "resolve_execution_inputs",
    "sha256_file",
]
