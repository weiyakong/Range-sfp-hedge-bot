"""Resumable official Binance USD-M onboarding primitives.

This module contains no strategy logic and no symbol-specific production
branches. Paths, collection plans, checkpoints, and QA are parameterized by the
authoritative exchange symbol.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from research.backtester_v3a.contracts import (
    INSTRUMENT_METADATA_SCHEMA_V2,
    parse_instrument_metadata,
)


DATA_VISION_ROOT = "https://data.binance.vision/data/futures/um"
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class OnboardingError(ValueError):
    """Raised when an onboarding contract or official-data input is invalid."""


@dataclass(frozen=True)
class OnboardingPaths:
    data_root: Path
    symbol: str

    def __post_init__(self) -> None:
        if self.symbol != self.symbol.upper() or _SYMBOL_RE.fullmatch(self.symbol) is None:
            raise OnboardingError("symbol must be an uppercase exchange symbol")

    @property
    def trade_raw(self) -> Path:
        return self.data_root / "raw/binance/usdt_m" / self.symbol / "1m"

    @property
    def funding_raw(self) -> Path:
        return self.data_root / "raw/binance/usdt_m" / self.symbol / "funding_rate"

    @property
    def mark_raw(self) -> Path:
        return self.data_root / "raw/binance/usdt_m" / self.symbol / "mark_price/1m"

    @property
    def metadata_raw(self) -> Path:
        return self.data_root / "raw/binance/usdt_m" / self.symbol / "instrument_metadata"

    @property
    def trade_normalized(self) -> Path:
        return self.data_root / "normalized/binance/usdt_m" / self.symbol / "1m"

    @property
    def funding_normalized(self) -> Path:
        return self.data_root / "normalized/binance/usdt_m" / self.symbol / "funding_rate"

    @property
    def mark_normalized(self) -> Path:
        return self.data_root / "normalized/binance/usdt_m" / self.symbol / "mark_price/1m"

    @property
    def trade_manifest(self) -> Path:
        return self.data_root / "manifests/binance/usdt_m" / self.symbol / "1m"

    @property
    def funding_manifest(self) -> Path:
        return self.data_root / "manifests/binance/usdt_m" / self.symbol / "funding_rate"

    @property
    def mark_manifest(self) -> Path:
        return self.data_root / "manifests/binance/usdt_m" / self.symbol / "mark_price/1m"

    @property
    def metadata_manifest(self) -> Path:
        return self.data_root / "manifests/binance/usdt_m" / self.symbol / "instrument_metadata"


@dataclass(frozen=True)
class ArchiveItem:
    period: str
    name: str
    url: str
    checksum_url: str


@dataclass(frozen=True)
class ArchivePlan:
    symbol: str
    category: str
    monthly: Tuple[ArchiveItem, ...]
    daily: Tuple[ArchiveItem, ...]
    api_start_ms: int
    api_end_ms: int


@dataclass(frozen=True)
class PriceRow:
    open_time_ms: int
    open: str
    high: str
    low: str
    close: str
    volume: str


@dataclass(frozen=True)
class PriceQAReport:
    first_timestamp_ms: Optional[int]
    last_timestamp_ms: Optional[int]
    row_count: int
    expected_grid_count: int
    missing_ranges: Tuple[Tuple[int, int, int], ...]
    duplicate_count: int
    ordering_violation_count: int
    off_grid_count: int
    bad_ohlc_count: int
    negative_volume_count: int
    non_numeric_count: int
    out_of_window_count: int


@dataclass(frozen=True)
class FundingRecord:
    symbol: str
    funding_time_ms: int
    funding_rate: str
    mark_price: Optional[str]


@dataclass(frozen=True)
class FundingQAReport:
    first_funding_time_ms: Optional[int]
    last_funding_time_ms: Optional[int]
    row_count: int
    duplicate_count: int
    ordering_violation_count: int
    symbol_mismatch_count: int
    missing_rate_count: int
    non_numeric_rate_count: int
    zero_rate_count: int
    missing_mark_price_count: int
    out_of_window_count: int
    interval_distribution_ms: Mapping[int, int]
    offset_distribution_ms: Mapping[int, int]


def parse_official_checksum(payload: bytes, archive_name: str) -> str:
    """Parse one Data Vision checksum without accepting a different filename."""
    try:
        text = payload.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise OnboardingError("official checksum is not ASCII") from exc
    fields = text.split()
    if len(fields) != 2 or fields[1].lstrip("*") != archive_name:
        raise OnboardingError("official checksum is not bound to the archive name")
    digest = fields[0].lower()
    if _SHA256_RE.fullmatch(digest) is None:
        raise OnboardingError("official checksum is not a SHA-256 digest")
    return digest


def archive_timestamp_ms(value: str) -> int:
    """Normalize an explicit Binance archive millisecond/microsecond timestamp."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OnboardingError("archive timestamp is not an integer") from exc
    if parsed < 0:
        raise OnboardingError("archive timestamp must be non-negative")
    if parsed < 10**15:
        return parsed
    if parsed < 10**18 and parsed % 1000 == 0:
        return parsed // 1000
    raise OnboardingError("archive timestamp unit is unsupported or loses precision")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise OnboardingError(f"{label} must be an object")
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OnboardingError(f"{label} must be a non-empty string")
    return value


def extract_instrument_metadata(
    payload: Mapping[str, object],
    *,
    symbol: str,
    collected_at_utc: str,
    source_path: Path,
    source_sha256: str,
) -> Dict[str, object]:
    """Extract current exchangeInfo filters as an honest static proxy contract."""
    OnboardingPaths(Path("/"), symbol)
    if not source_path.is_absolute():
        raise OnboardingError("metadata source path must be absolute")
    if _SHA256_RE.fullmatch(source_sha256) is None:
        raise OnboardingError("metadata source SHA-256 is invalid")
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        raise OnboardingError("exchangeInfo.symbols must be an array")
    matches = [
        _mapping(item, "exchangeInfo symbol")
        for item in symbols
        if isinstance(item, dict) and item.get("symbol") == symbol
    ]
    if len(matches) != 1:
        raise OnboardingError(f"exchangeInfo must contain exactly one {symbol}")
    instrument = matches[0]
    if instrument.get("contractType") != "PERPETUAL":
        raise OnboardingError(f"{symbol} is not a PERPETUAL contract")
    filters_value = instrument.get("filters")
    if not isinstance(filters_value, list):
        raise OnboardingError("exchangeInfo filters must be an array")
    filters: Dict[str, Mapping[str, object]] = {}
    for raw_filter in filters_value:
        item = _mapping(raw_filter, "exchangeInfo filter")
        filter_type = _required_text(item.get("filterType"), "filterType")
        filters[filter_type] = item
    try:
        price_filter = filters["PRICE_FILTER"]
        lot_filter = filters["LOT_SIZE"]
    except KeyError as exc:
        raise OnboardingError("required PRICE_FILTER/LOT_SIZE is absent") from exc
    notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL")
    if notional_filter is None:
        raise OnboardingError("required notional filter is absent")
    notional = notional_filter.get("notional")
    if notional is None:
        notional = notional_filter.get("minNotional")
    contract: Dict[str, object] = {
        "schema_version": INSTRUMENT_METADATA_SCHEMA_V2,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "metadata_id": f"BINANCE-USDM-{symbol}-{source_sha256[:16]}",
        "collected_at_utc": collected_at_utc,
        "tick_size": _required_text(price_filter.get("tickSize"), "tickSize"),
        "step_size": _required_text(lot_filter.get("stepSize"), "stepSize"),
        "min_qty": _required_text(lot_filter.get("minQty"), "minQty"),
        "min_notional": _required_text(notional, "minNotional"),
        "price_precision": instrument.get("pricePrecision"),
        "quantity_precision": instrument.get("quantityPrecision"),
        "provenance": {
            "fidelity_classification": "STATIC_CURRENT_PROXY",
            "source": str(source_path),
            "source_sha256": source_sha256,
            "effective_start_ms": None,
            "effective_end_ms": None,
        },
    }
    parse_instrument_metadata(contract)
    return contract


def canonical_project_end(authority_path: Path) -> datetime:
    """Read, never infer or hardcode, the current BTC canonical end."""
    try:
        payload = json.loads(authority_path.read_text(encoding="utf-8"))
        dataset = payload["dataset"]
        raw = dataset["strict_end_utc"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OnboardingError("BTC canonical authority has no valid strict_end_utc") from exc
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise OnboardingError("BTC canonical strict_end_utc must use UTC Z notation")
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise OnboardingError("BTC canonical strict_end_utc is invalid") from exc
    if parsed.tzinfo != timezone.utc:
        raise OnboardingError("BTC canonical strict_end_utc must be UTC")
    return parsed


def _next_month(year: int, month: int) -> Tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _archive_item(
    symbol: str,
    category: str,
    period: str,
    suffix: str,
) -> ArchiveItem:
    name = f"{symbol}-1m-{suffix}.zip"
    url = f"{DATA_VISION_ROOT}/{period}/{category}/{symbol}/1m/{name}"
    return ArchiveItem(period, name, url, f"{url}.CHECKSUM")


def _utc_ms(value: datetime) -> int:
    if value.tzinfo != timezone.utc:
        raise OnboardingError("collection datetimes must be UTC")
    return int(value.timestamp() * 1000)


def plan_price_archives(
    *,
    symbol: str,
    category: str,
    actual_start: datetime,
    project_end: datetime,
) -> ArchivePlan:
    """Plan immutable archives plus an API tail for the final project day."""
    OnboardingPaths(Path("/"), symbol)
    if category not in {"klines", "markPriceKlines"}:
        raise OnboardingError("unsupported official Binance price category")
    if actual_start.tzinfo != timezone.utc or project_end.tzinfo != timezone.utc:
        raise OnboardingError("archive plan timestamps must be UTC")
    if actual_start > project_end:
        raise OnboardingError("actual start must not exceed project end")

    monthly: List[ArchiveItem] = []
    year, month = actual_start.year, actual_start.month
    while (year, month) < (project_end.year, project_end.month):
        monthly.append(_archive_item(
            symbol, category, "monthly", f"{year:04d}-{month:02d}",
        ))
        year, month = _next_month(year, month)

    daily: List[ArchiveItem] = []
    first_day = 1
    if (actual_start.year, actual_start.month) == (project_end.year, project_end.month):
        first_day = actual_start.day
    for day in range(first_day, project_end.day):
        daily.append(_archive_item(
            symbol,
            category,
            "daily",
            f"{project_end.year:04d}-{project_end.month:02d}-{day:02d}",
        ))
    api_start = datetime(
        project_end.year,
        project_end.month,
        project_end.day,
        tzinfo=timezone.utc,
    )
    return ArchivePlan(
        symbol=symbol,
        category=category,
        monthly=tuple(monthly),
        daily=tuple(daily),
        api_start_ms=_utc_ms(api_start),
        api_end_ms=_utc_ms(project_end),
    )


def atomic_checkpoint(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_checkpoint(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OnboardingError(f"cannot read checkpoint: {path}") from exc
    if not isinstance(payload, dict):
        raise OnboardingError("checkpoint must contain one JSON object")
    return payload


def _decimal(value: str) -> Optional[Decimal]:
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _missing_ranges(
    timestamps: Sequence[int],
    requested_start_ms: int,
    requested_end_ms: int,
) -> Tuple[Tuple[int, int, int], ...]:
    valid = sorted({
        value for value in timestamps
        if requested_start_ms <= value <= requested_end_ms
        and value % 60_000 == 0
    })
    missing: List[Tuple[int, int, int]] = []
    cursor = requested_start_ms
    for value in valid:
        if value > cursor:
            count = (value - cursor) // 60_000
            missing.append((cursor, value - 60_000, count))
        cursor = max(cursor, value + 60_000)
    if cursor <= requested_end_ms:
        count = (requested_end_ms - cursor) // 60_000 + 1
        missing.append((cursor, requested_end_ms, count))
    return tuple(item for item in missing if item[2] > 0)


def qa_price_rows(
    rows: Sequence[PriceRow],
    *,
    requested_start_ms: int,
    requested_end_ms: int,
) -> PriceQAReport:
    if requested_start_ms > requested_end_ms:
        raise OnboardingError("requested price window is invalid")
    timestamps = [row.open_time_ms for row in rows]
    duplicates = len(timestamps) - len(set(timestamps))
    ordering = sum(
        1 for left, right in zip(timestamps, timestamps[1:]) if right <= left
    )
    off_grid = sum(1 for value in timestamps if value % 60_000 != 0)
    outside = sum(
        1 for value in timestamps
        if value < requested_start_ms or value > requested_end_ms
    )
    bad_ohlc = 0
    negative_volume = 0
    non_numeric = 0
    for row in rows:
        prices = tuple(_decimal(value) for value in (
            row.open, row.high, row.low, row.close,
        ))
        volume = _decimal(row.volume)
        if any(value is None for value in prices) or volume is None:
            non_numeric += 1
            continue
        open_price, high, low, close = prices
        assert open_price is not None and high is not None
        assert low is not None and close is not None and volume is not None
        if (
            min(open_price, high, low, close) <= 0
            or high < max(open_price, close, low)
            or low > min(open_price, close, high)
        ):
            bad_ohlc += 1
        if volume < 0:
            negative_volume += 1
    grid = (requested_end_ms - requested_start_ms) // 60_000 + 1
    return PriceQAReport(
        first_timestamp_ms=min(timestamps) if timestamps else None,
        last_timestamp_ms=max(timestamps) if timestamps else None,
        row_count=len(rows),
        expected_grid_count=grid,
        missing_ranges=_missing_ranges(
            timestamps, requested_start_ms, requested_end_ms,
        ),
        duplicate_count=duplicates,
        ordering_violation_count=ordering,
        off_grid_count=off_grid,
        bad_ohlc_count=bad_ohlc,
        negative_volume_count=negative_volume,
        non_numeric_count=non_numeric,
        out_of_window_count=outside,
    )


def qa_funding_records(
    records: Sequence[FundingRecord],
    *,
    symbol: str,
    requested_start_ms: int,
    requested_end_ms: int,
) -> FundingQAReport:
    timestamps = [item.funding_time_ms for item in records]
    interval_distribution: Dict[int, int] = {}
    for left, right in zip(timestamps, timestamps[1:]):
        interval = right - left
        interval_distribution[interval] = interval_distribution.get(interval, 0) + 1
    offsets: Dict[int, int] = {}
    for value in timestamps:
        offset = value % 60_000
        offsets[offset] = offsets.get(offset, 0) + 1
    missing_rate = 0
    non_numeric = 0
    zero = 0
    missing_mark = 0
    for item in records:
        if item.funding_rate == "":
            missing_rate += 1
        else:
            rate = _decimal(item.funding_rate)
            if rate is None:
                non_numeric += 1
            elif rate == 0:
                zero += 1
        if item.mark_price in {None, ""}:
            missing_mark += 1
    return FundingQAReport(
        first_funding_time_ms=min(timestamps) if timestamps else None,
        last_funding_time_ms=max(timestamps) if timestamps else None,
        row_count=len(records),
        duplicate_count=len(timestamps) - len(set(timestamps)),
        ordering_violation_count=sum(
            1 for left, right in zip(timestamps, timestamps[1:]) if right <= left
        ),
        symbol_mismatch_count=sum(1 for item in records if item.symbol != symbol),
        missing_rate_count=missing_rate,
        non_numeric_rate_count=non_numeric,
        zero_rate_count=zero,
        missing_mark_price_count=missing_mark,
        out_of_window_count=sum(
            1 for value in timestamps
            if value < requested_start_ms or value > requested_end_ms
        ),
        interval_distribution_ms=dict(sorted(interval_distribution.items())),
        offset_distribution_ms=dict(sorted(offsets.items())),
    )


__all__ = [
    "ArchiveItem",
    "ArchivePlan",
    "FundingQAReport",
    "FundingRecord",
    "OnboardingError",
    "OnboardingPaths",
    "PriceQAReport",
    "PriceRow",
    "atomic_checkpoint",
    "archive_timestamp_ms",
    "canonical_project_end",
    "extract_instrument_metadata",
    "parse_official_checksum",
    "plan_price_archives",
    "qa_funding_records",
    "qa_price_rows",
    "read_checkpoint",
]
