#!/usr/bin/env python3
"""Collect official Binance USD-M inputs for symbol-bound V3-A onboarding.

The collector is deliberately independent of the legacy BTC bootstrap.  It
reads only the BTC authority's canonical end, writes every official response
before transforming it, and checkpoints after every archive or API page.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from calendar import monthrange
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from research.backtester_v3a.contracts import (
    DATASET_IDENTITY_SCHEMA,
    parse_dataset_identity,
    parse_instrument_metadata,
)
from research.backtester_v3a.data import DATA_MANIFEST_SCHEMA

from .binance_usdm import (
    ArchiveItem,
    FundingRecord,
    OnboardingError,
    OnboardingPaths,
    PriceQAReport,
    PriceRow,
    archive_timestamp_ms,
    atomic_checkpoint,
    canonical_project_end,
    extract_instrument_metadata,
    parse_official_checksum,
    plan_price_archives,
    qa_funding_records,
)


COLLECTOR_SCHEMA = "BACKTESTER_V3A_BINANCE_USDM_ONBOARDING_V1"
COLLECTION_MANIFEST_SCHEMA = "BACKTESTER_V3A_COLLECTION_MANIFEST_V1"
COLLECTOR_VERSION = "1.0.0"
API_ROOT = "https://fapi.binance.com"
EXCHANGE_INFO_ENDPOINT = f"{API_ROOT}/fapi/v1/exchangeInfo"
FUNDING_ENDPOINT = f"{API_ROOT}/fapi/v1/fundingRate"
PRICE_ENDPOINTS = {
    "klines": f"{API_ROOT}/fapi/v1/klines",
    "markPriceKlines": f"{API_ROOT}/fapi/v1/markPriceKlines",
}
ROLE_DETAILS = {
    "trade_price": ("klines", ("open_time", "open", "high", "low", "close", "volume")),
    "mark_price": ("markPriceKlines", ("open_time", "open", "high", "low", "close")),
}


@dataclass(frozen=True)
class RawIdentity:
    kind: str
    source: str
    path: str
    sha256: str
    bytes: int
    row_count: Optional[int]
    first_timestamp_ms: Optional[int]
    last_timestamp_ms: Optional[int]


@dataclass(frozen=True)
class PriceSource:
    kind: str
    path: Path
    source: str


@dataclass(frozen=True)
class StreamingPriceQA:
    report: PriceQAReport
    symbol_mismatch_count: int
    archive_microsecond_timestamp_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z",
    )


def utc_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(
        timespec="milliseconds",
    ).replace("+00:00", "Z")


def utc_ms(value: datetime) -> int:
    if value.tzinfo != timezone.utc:
        raise OnboardingError("timestamp must be UTC")
    return int(value.timestamp() * 1000)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n").encode("utf-8"),
    )


def json_value(payload: bytes, label: str) -> object:
    try:
        return json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OnboardingError(f"invalid JSON from {label}") from exc


def json_object(payload: bytes, label: str) -> Mapping[str, object]:
    value = json_value(payload, label)
    if not isinstance(value, dict):
        raise OnboardingError(f"{label} must contain one object")
    return value


def json_array(payload: bytes, label: str) -> List[object]:
    value = json_value(payload, label)
    if not isinstance(value, list):
        raise OnboardingError(f"{label} must contain one array")
    return value


def fetch_bytes(url: str, *, allow_404: bool = False) -> Optional[bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, application/octet-stream, text/plain",
            "User-Agent": "Range-sfp-hedge-bot/backtester-v3a-onboarding-v1",
        },
        method="GET",
    )
    last_error: Optional[BaseException] = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code == 404 and allow_404:
                return None
            last_error = OnboardingError(
                f"HTTP {exc.code} for {url}: {body[:500]!r}",
            )
            if (exc.code == 429 or 500 <= exc.code < 600) and attempt < 5:
                time.sleep(float(min(attempt * 2, 10)))
                continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 5:
                time.sleep(float(min(attempt * 2, 10)))
                continue
    raise OnboardingError(f"request failed after retries: {url}: {last_error}")


def download_file(url: str, path: Path, *, allow_404: bool = False) -> bool:
    """Download atomically; return False only for an explicitly allowed 404."""
    if path.is_file():
        return True
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Range-sfp-hedge-bot/backtester-v3a-onboarding-v1"},
        method="GET",
    )
    last_error: Optional[BaseException] = None
    for attempt in range(1, 6):
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(request, timeout=120) as response:
                with temporary.open("wb") as handle:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
                    handle.flush()
                    os.fsync(handle.fileno())
            os.replace(temporary, path)
            return True
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code == 404 and allow_404:
                return False
            last_error = OnboardingError(
                f"HTTP {exc.code} for {url}: {body[:500]!r}",
            )
            if (exc.code == 429 or 500 <= exc.code < 600) and attempt < 5:
                time.sleep(float(min(attempt * 2, 10)))
                continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < 5:
                time.sleep(float(min(attempt * 2, 10)))
                continue
        finally:
            if temporary.exists():
                temporary.unlink()
    raise OnboardingError(f"download failed after retries: {url}: {last_error}")


def api_url(endpoint: str, parameters: Mapping[str, object]) -> str:
    query = urllib.parse.urlencode({key: str(value) for key, value in parameters.items()})
    return f"{endpoint}?{query}"


def git_identity(repo_root: Path) -> Dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "status_short": status}


def raw_identity(
    path: Path,
    *,
    kind: str,
    source: str,
    rows: Optional[Sequence[object]] = None,
) -> RawIdentity:
    timestamps: List[int] = []
    if rows is not None:
        for raw in rows:
            if isinstance(raw, list) and raw and isinstance(raw[0], int):
                timestamps.append(raw[0])
            elif isinstance(raw, dict):
                timestamp = raw.get("fundingTime")
                if isinstance(timestamp, int) and not isinstance(timestamp, bool):
                    timestamps.append(timestamp)
    return RawIdentity(
        kind=kind,
        source=source,
        path=str(path.resolve()),
        sha256=sha256_file(path),
        bytes=path.stat().st_size,
        row_count=len(rows) if rows is not None else None,
        first_timestamp_ms=min(timestamps) if timestamps else None,
        last_timestamp_ms=max(timestamps) if timestamps else None,
    )


def role_directories(paths: OnboardingPaths, role: str) -> Tuple[Path, Path, Path]:
    if role == "trade_price":
        return paths.trade_raw, paths.trade_normalized, paths.trade_manifest
    if role == "mark_price":
        return paths.mark_raw, paths.mark_normalized, paths.mark_manifest
    if role == "funding":
        return paths.funding_raw, paths.funding_normalized, paths.funding_manifest
    raise OnboardingError(f"unsupported dataset role: {role}")


def collect_metadata(
    *,
    paths: OnboardingPaths,
    repo_root: Path,
    canonical_authority: Path,
) -> Tuple[Mapping[str, object], int]:
    raw_path = paths.metadata_raw / "exchangeInfo.json"
    manifest_dir = paths.metadata_manifest
    checkpoint_path = manifest_dir / "checkpoint.json"
    if raw_path.is_file():
        payload = raw_path.read_bytes()
    else:
        fetched = fetch_bytes(EXCHANGE_INFO_ENDPOINT)
        if fetched is None:
            raise OnboardingError("exchangeInfo unexpectedly returned no payload")
        atomic_write_bytes(raw_path, fetched)
        payload = fetched
    existing_contract_path = manifest_dir / "instrument_metadata_v2.json"
    collected_at = utc_now()
    if existing_contract_path.is_file():
        existing_contract = json_object(
            existing_contract_path.read_bytes(), str(existing_contract_path),
        )
        existing_time = existing_contract.get("collected_at_utc")
        if not isinstance(existing_time, str):
            raise OnboardingError("existing metadata contract has no collection time")
        collected_at = existing_time
    exchange_info = json_object(payload, "exchangeInfo")
    symbols = exchange_info.get("symbols")
    if not isinstance(symbols, list):
        raise OnboardingError("exchangeInfo.symbols must be an array")
    instrument: Optional[Mapping[str, object]] = None
    for candidate in symbols:
        if isinstance(candidate, dict) and candidate.get("symbol") == paths.symbol:
            instrument = candidate
            break
    if instrument is None:
        raise OnboardingError(f"exchangeInfo does not contain {paths.symbol}")
    onboard_date = instrument.get("onboardDate")
    if isinstance(onboard_date, bool) or not isinstance(onboard_date, int):
        raise OnboardingError(f"{paths.symbol} has no valid onboardDate")
    source_hash = sha256_file(raw_path)
    contract = extract_instrument_metadata(
        exchange_info,
        symbol=paths.symbol,
        collected_at_utc=collected_at,
        source_path=raw_path.resolve(),
        source_sha256=source_hash,
    )
    parse_instrument_metadata(contract)
    tick_size = contract.get("tick_size")
    step_size = contract.get("step_size")
    price_precision = contract.get("price_precision")
    quantity_precision = contract.get("quantity_precision")
    if (
        not isinstance(tick_size, str)
        or not isinstance(step_size, str)
        or isinstance(price_precision, bool)
        or not isinstance(price_precision, int)
        or isinstance(quantity_precision, bool)
        or not isinstance(quantity_precision, int)
    ):
        raise OnboardingError("extracted metadata precision fields are invalid")
    precision_consistent = (
        decimal_grid_places(tick_size) <= price_precision
        and decimal_grid_places(step_size) <= quantity_precision
    )
    metadata_critical = [] if precision_consistent else [
        "exchangeInfo precision fields are inconsistent with tick/step grids",
    ]
    contract_path = existing_contract_path
    atomic_write_json(contract_path, contract)
    checkpoint = {
        "schema_version": COLLECTOR_SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "symbol": paths.symbol,
        "role": "instrument_metadata",
        "complete": True,
        "updated_at_utc": utc_now(),
        "raw_path": str(raw_path.resolve()),
        "raw_sha256": source_hash,
        "contract_path": str(contract_path.resolve()),
        "contract_sha256": sha256_file(contract_path),
    }
    atomic_checkpoint(checkpoint_path, checkpoint)
    collection_manifest = {
        "schema_version": COLLECTION_MANIFEST_SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "qa_status": "PASS" if not metadata_critical else "FAIL",
        "critical_issues": metadata_critical,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": paths.symbol,
        "role": "instrument_metadata",
        "source": {"endpoint": EXCHANGE_INFO_ENDPOINT, "official": True},
        "collection_timestamp_utc": collected_at,
        "requested_range": None,
        "actual_range": None,
        "row_count": 1,
        "gaps": [],
        "duplicates": 0,
        "ordering_violations": 0,
        "schema": "BACKTESTER_V3A_INSTRUMENT_METADATA_V2",
        "timestamp_semantics": "current exchangeInfo snapshot collection time UTC",
        "raw_source_identities": [asdict(raw_identity(
            raw_path, kind="api_snapshot", source=EXCHANGE_INFO_ENDPOINT,
        ))],
        "normalized_identity": {
            "path": str(contract_path.resolve()),
            "sha256": sha256_file(contract_path),
        },
        "collector": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "git": git_identity(repo_root),
            "checkpoint_policy": "raw response and checkpoint written atomically in the same collection step",
        },
        "canonical_end_authority": {
            "path": str(canonical_authority.resolve()),
            "sha256": sha256_file(canonical_authority),
        },
        "qa": {
            "symbol_exact_match": True,
            "numeric_validity": True,
            "positive_tick_size": True,
            "positive_step_size": True,
            "nonnegative_min_qty": True,
            "nonnegative_min_notional": True,
            "precision_consistency_checked": True,
            "precision_consistent": precision_consistent,
        },
        "fidelity_limitations": [
            "Binance exchangeInfo exposes current filters, not a historical filter timeline.",
            "The contract is STATIC_CURRENT_PROXY and makes no historical-effective-time claim.",
        ],
    }
    collection_path = manifest_dir / "collection_manifest.json"
    atomic_write_json(collection_path, collection_manifest)
    write_checksums(manifest_dir, (
        collection_path, contract_path, checkpoint_path,
    ))
    return instrument, onboard_date


def discover_price_start(
    *,
    paths: OnboardingPaths,
    category: str,
    requested_start_ms: int,
) -> int:
    role = "trade_price" if category == "klines" else "mark_price"
    raw_dir, _, _ = role_directories(paths, role)
    discovery_path = raw_dir / "api" / f"discovery-start-{requested_start_ms}.json"
    endpoint = PRICE_ENDPOINTS[category]
    url = api_url(endpoint, {
        "symbol": paths.symbol,
        "interval": "1m",
        "startTime": requested_start_ms,
        "limit": 1,
    })
    if not discovery_path.is_file():
        payload = fetch_bytes(url)
        if payload is None:
            raise OnboardingError("price discovery unexpectedly returned no payload")
        rows = json_array(payload, f"{category} discovery")
        atomic_write_bytes(discovery_path, payload)
    else:
        rows = json_array(discovery_path.read_bytes(), str(discovery_path))
    if not rows or not isinstance(rows[0], list) or not rows[0]:
        raise OnboardingError(f"no official {category} history for {paths.symbol}")
    timestamp = rows[0][0]
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise OnboardingError(f"invalid {category} discovery timestamp")
    return archive_timestamp_ms(str(timestamp))


def archive_window(item: ArchiveItem) -> Tuple[int, int]:
    suffix = item.name.removesuffix(".zip").rsplit("-", 3)
    if item.period == "monthly":
        year_text, month_text = suffix[-2:]
        year, month = int(year_text), int(month_text)
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(
            year, month, monthrange(year, month)[1], 23, 59,
            tzinfo=timezone.utc,
        )
    else:
        year_text, month_text, day_text = suffix[-3:]
        year, month, day = int(year_text), int(month_text), int(day_text)
        start = datetime(year, month, day, tzinfo=timezone.utc)
        end = start + timedelta(days=1) - timedelta(minutes=1)
    return utc_ms(start), utc_ms(end)


def _checkpoint_base(
    *,
    symbol: str,
    role: str,
    requested_start_ms: int,
    actual_start_ms: int,
    requested_end_ms: int,
) -> Dict[str, object]:
    return {
        "schema_version": COLLECTOR_SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "symbol": symbol,
        "role": role,
        "requested_start_ms": requested_start_ms,
        "actual_start_ms": actual_start_ms,
        "requested_end_ms": requested_end_ms,
        "updated_at_utc": utc_now(),
        "complete": False,
        "stage": "collecting_raw",
        "completed_sources": [],
    }


def _save_checkpoint_source(
    checkpoint_path: Path,
    checkpoint: Dict[str, object],
    identity: RawIdentity,
) -> None:
    completed = checkpoint.get("completed_sources")
    if not isinstance(completed, list):
        raise OnboardingError("checkpoint completed_sources is invalid")
    if not any(
        isinstance(item, dict) and item.get("path") == identity.path
        for item in completed
    ):
        completed.append(asdict(identity))
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)


def collect_archive(
    *,
    item: ArchiveItem,
    raw_dir: Path,
    checkpoint_path: Path,
    checkpoint: Dict[str, object],
) -> Optional[PriceSource]:
    destination = raw_dir / "archives" / item.period / item.name
    checksum_path = destination.with_name(f"{destination.name}.CHECKSUM")
    missing_path = destination.with_name(f"{destination.name}.missing.json")
    if missing_path.is_file():
        return None
    if not checksum_path.is_file():
        checksum_payload = fetch_bytes(item.checksum_url, allow_404=True)
        if checksum_payload is None:
            atomic_write_json(missing_path, {
                "url": item.url,
                "checksum_url": item.checksum_url,
                "http_status": 404,
                "observed_at_utc": utc_now(),
                "meaning": "official archive not published; API fallback required",
            })
            identity = raw_identity(
                missing_path, kind="official_archive_missing",
                source=item.checksum_url,
            )
            _save_checkpoint_source(checkpoint_path, checkpoint, identity)
            return None
        atomic_write_bytes(checksum_path, checksum_payload)
    expected = parse_official_checksum(checksum_path.read_bytes(), item.name)
    checksum_identity = raw_identity(
        checksum_path,
        kind="data_vision_official_checksum",
        source=item.checksum_url,
    )
    _save_checkpoint_source(checkpoint_path, checkpoint, checksum_identity)
    if not download_file(item.url, destination, allow_404=True):
        atomic_write_json(missing_path, {
            "url": item.url,
            "checksum_url": item.checksum_url,
            "http_status": 404,
            "observed_at_utc": utc_now(),
            "meaning": "checksum existed but official archive was unavailable; API fallback required",
        })
        identity = raw_identity(
            missing_path, kind="official_archive_missing", source=item.url,
        )
        _save_checkpoint_source(checkpoint_path, checkpoint, identity)
        return None
    actual = sha256_file(destination)
    if actual != expected:
        raise OnboardingError(f"official checksum mismatch: {destination}")
    identity = raw_identity(
        destination, kind=f"data_vision_{item.period}_archive", source=item.url,
    )
    _save_checkpoint_source(checkpoint_path, checkpoint, identity)
    return PriceSource(identity.kind, destination, item.url)


def collect_price_api_window(
    *,
    paths: OnboardingPaths,
    role: str,
    category: str,
    label: str,
    start_ms: int,
    end_ms: int,
    checkpoint_path: Path,
    checkpoint: Dict[str, object],
) -> List[PriceSource]:
    raw_dir, _, _ = role_directories(paths, role)
    page_dir = raw_dir / "api" / label
    endpoint = PRICE_ENDPOINTS[category]
    sources: List[PriceSource] = []
    cursor = start_ms
    page_number = 1
    while cursor <= end_ms:
        page_path = page_dir / (
            f"page-{page_number:06d}-start-{cursor}-end-{end_ms}.json"
        )
        url = api_url(endpoint, {
            "symbol": paths.symbol,
            "interval": "1m",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1500,
        })
        if page_path.is_file():
            payload = page_path.read_bytes()
        else:
            fetched = fetch_bytes(url)
            if fetched is None:
                raise OnboardingError("price API unexpectedly returned no payload")
            json_array(fetched, url)
            atomic_write_bytes(page_path, fetched)
            payload = fetched
        rows = json_array(payload, str(page_path))
        identity = raw_identity(
            page_path, kind="official_rest_api_page", source=url, rows=rows,
        )
        _save_checkpoint_source(checkpoint_path, checkpoint, identity)
        sources.append(PriceSource(identity.kind, page_path, url))
        if not rows:
            break
        last = rows[-1]
        if not isinstance(last, list) or not last:
            raise OnboardingError(f"invalid price API row in {page_path}")
        last_timestamp = last[0]
        if isinstance(last_timestamp, bool) or not isinstance(last_timestamp, int):
            raise OnboardingError(f"invalid price API timestamp in {page_path}")
        normalized_last = archive_timestamp_ms(str(last_timestamp))
        if normalized_last < cursor:
            raise OnboardingError("price API pagination did not advance")
        if normalized_last >= end_ms or len(rows) < 1500:
            break
        cursor = normalized_last + 60_000
        page_number += 1
    return sources


def collect_price_sources(
    *,
    paths: OnboardingPaths,
    role: str,
    category: str,
    requested_start_ms: int,
    actual_start_ms: int,
    project_end_ms: int,
) -> Tuple[List[PriceSource], Dict[str, object]]:
    raw_dir, _, manifest_dir = role_directories(paths, role)
    checkpoint_path = manifest_dir / "checkpoint.json"
    checkpoint = _checkpoint_base(
        symbol=paths.symbol,
        role=role,
        requested_start_ms=requested_start_ms,
        actual_start_ms=actual_start_ms,
        requested_end_ms=project_end_ms,
    )
    plan = plan_price_archives(
        symbol=paths.symbol,
        category=category,
        actual_start=datetime.fromtimestamp(actual_start_ms / 1000, timezone.utc),
        project_end=datetime.fromtimestamp(project_end_ms / 1000, timezone.utc),
    )
    sources: List[PriceSource] = []
    for item in (*plan.monthly, *plan.daily):
        archive = collect_archive(
            item=item,
            raw_dir=raw_dir,
            checkpoint_path=checkpoint_path,
            checkpoint=checkpoint,
        )
        if archive is not None:
            sources.append(archive)
            continue
        window_start, window_end = archive_window(item)
        sources.extend(collect_price_api_window(
            paths=paths,
            role=role,
            category=category,
            label=f"fallback-{item.period}-{item.name.removesuffix('.zip')}",
            start_ms=max(actual_start_ms, window_start),
            end_ms=min(project_end_ms, window_end),
            checkpoint_path=checkpoint_path,
            checkpoint=checkpoint,
        ))
    sources.extend(collect_price_api_window(
        paths=paths,
        role=role,
        category=category,
        label="canonical-end-tail",
        start_ms=max(actual_start_ms, plan.api_start_ms),
        end_ms=plan.api_end_ms,
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
    ))
    checkpoint["complete"] = True
    checkpoint["stage"] = "raw_complete"
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)
    return sources, checkpoint


def _price_row_from_sequence(
    row: Sequence[object], *, role: str,
) -> Tuple[PriceRow, bool]:
    required = 6 if role == "trade_price" else 5
    if len(row) < required:
        raise OnboardingError(f"{role} raw row has fewer than {required} fields")
    timestamp_text = str(row[0])
    timestamp = archive_timestamp_ms(timestamp_text)
    microseconds = int(timestamp_text) >= 10**15
    values = [str(item) for item in row[1:required]]
    volume = values[4] if role == "trade_price" else "0"
    return PriceRow(
        open_time_ms=timestamp,
        open=values[0],
        high=values[1],
        low=values[2],
        close=values[3],
        volume=volume,
    ), microseconds


def iter_price_source(source: PriceSource, *, role: str) -> Iterator[Tuple[PriceRow, bool]]:
    if source.path.suffix == ".zip":
        try:
            archive = zipfile.ZipFile(source.path)
        except zipfile.BadZipFile as exc:
            raise OnboardingError(f"invalid official zip archive: {source.path}") from exc
        with archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1:
                raise OnboardingError(
                    f"official archive must contain one CSV: {source.path}",
                )
            with archive.open(members[0], "r") as binary:
                text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
                reader = csv.reader(text)
                for index, csv_row in enumerate(reader):
                    if not csv_row:
                        continue
                    try:
                        yield _price_row_from_sequence(csv_row, role=role)
                    except OnboardingError:
                        if index == 0 and not csv_row[0].isdigit():
                            continue
                        raise
        return
    rows = json_array(source.path.read_bytes(), str(source.path))
    for api_row in rows:
        if not isinstance(api_row, list):
            raise OnboardingError(f"price API row is not an array: {source.path}")
        yield _price_row_from_sequence(api_row, role=role)


def decimal_value(value: str) -> Optional[Decimal]:
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def decimal_grid_places(value: str) -> int:
    parsed = decimal_value(value)
    if parsed is None or parsed <= 0:
        raise OnboardingError("metadata grid value must be finite and positive")
    exponent = parsed.normalize().as_tuple().exponent
    return max(0, -int(exponent))


def normalize_price(
    *,
    paths: OnboardingPaths,
    role: str,
    sources: Sequence[PriceSource],
    requested_start_ms: int,
    requested_end_ms: int,
) -> StreamingPriceQA:
    _, normalized_dir, manifest_dir = role_directories(paths, role)
    columns = ROLE_DETAILS[role][1]
    normalized_path = normalized_dir / f"{paths.symbol}-{role}-1m.csv"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = normalized_path.with_name(
        f".{normalized_path.name}.{uuid.uuid4().hex}.tmp",
    )
    first: Optional[int] = None
    last: Optional[int] = None
    row_count = 0
    duplicates = 0
    ordering = 0
    off_grid = 0
    bad_ohlc = 0
    negative_volume = 0
    non_numeric = 0
    outside = 0
    microseconds = 0
    missing: List[Tuple[int, int, int]] = []
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)
            for source in sources:
                for row, was_microseconds in iter_price_source(source, role=role):
                    if was_microseconds:
                        microseconds += 1
                    timestamp = row.open_time_ms
                    if timestamp < requested_start_ms or timestamp > requested_end_ms:
                        outside += 1
                        continue
                    if timestamp % 60_000:
                        off_grid += 1
                    if last is not None:
                        if timestamp == last:
                            duplicates += 1
                        elif timestamp < last:
                            ordering += 1
                        elif timestamp > last + 60_000:
                            gap_count = (timestamp - last) // 60_000 - 1
                            missing.append((last + 60_000, timestamp - 60_000, gap_count))
                    prices = tuple(decimal_value(value) for value in (
                        row.open, row.high, row.low, row.close,
                    ))
                    volume = decimal_value(row.volume)
                    if any(value is None for value in prices) or volume is None:
                        non_numeric += 1
                    else:
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
                    output: List[object] = [
                        timestamp, row.open, row.high, row.low, row.close,
                    ]
                    if role == "trade_price":
                        output.append(row.volume)
                    writer.writerow(output)
                    first = timestamp if first is None else min(first, timestamp)
                    last = timestamp
                    row_count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, normalized_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    expected_grid = 0
    if first is not None and last is not None:
        expected_grid = (requested_end_ms - requested_start_ms) // 60_000 + 1
        if first > requested_start_ms:
            count = (first - requested_start_ms) // 60_000
            missing.insert(0, (requested_start_ms, first - 60_000, count))
        if last < requested_end_ms:
            count = (requested_end_ms - last) // 60_000
            missing.append((last + 60_000, requested_end_ms, count))
    report = PriceQAReport(
        first_timestamp_ms=first,
        last_timestamp_ms=last,
        row_count=row_count,
        expected_grid_count=expected_grid,
        missing_ranges=tuple(missing),
        duplicate_count=duplicates,
        ordering_violation_count=ordering,
        off_grid_count=off_grid,
        bad_ohlc_count=bad_ohlc,
        negative_volume_count=negative_volume,
        non_numeric_count=non_numeric,
        out_of_window_count=outside,
    )
    checkpoint_path = manifest_dir / "checkpoint.json"
    checkpoint = dict(json.loads(checkpoint_path.read_text(encoding="utf-8")))
    checkpoint["stage"] = "normalized"
    checkpoint["normalized_path"] = str(normalized_path.resolve())
    checkpoint["normalized_sha256"] = sha256_file(normalized_path)
    checkpoint["normalized_rows"] = row_count
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)
    return StreamingPriceQA(
        report=report,
        symbol_mismatch_count=0,
        archive_microsecond_timestamp_count=microseconds,
    )


def collect_funding_pages(
    *,
    paths: OnboardingPaths,
    requested_start_ms: int,
    requested_end_ms: int,
) -> Tuple[List[RawIdentity], List[FundingRecord], Dict[str, object]]:
    _, _, manifest_dir = role_directories(paths, "funding")
    checkpoint_path = manifest_dir / "checkpoint.json"
    checkpoint = _checkpoint_base(
        symbol=paths.symbol,
        role="funding",
        requested_start_ms=requested_start_ms,
        actual_start_ms=requested_start_ms,
        requested_end_ms=requested_end_ms,
    )
    raw_dir = paths.funding_raw / "api" / "pages"
    identities: List[RawIdentity] = []
    records: List[FundingRecord] = []
    cursor = requested_start_ms
    page_number = 1
    while cursor <= requested_end_ms:
        page_path = raw_dir / (
            f"page-{page_number:06d}-start-{cursor}-end-{requested_end_ms}.json"
        )
        url = api_url(FUNDING_ENDPOINT, {
            "symbol": paths.symbol,
            "startTime": cursor,
            "endTime": requested_end_ms,
            "limit": 1000,
        })
        if page_path.is_file():
            payload = page_path.read_bytes()
        else:
            fetched = fetch_bytes(url)
            if fetched is None:
                raise OnboardingError("funding API unexpectedly returned no payload")
            json_array(fetched, url)
            atomic_write_bytes(page_path, fetched)
            payload = fetched
        rows = json_array(payload, str(page_path))
        identity = raw_identity(
            page_path, kind="official_rest_api_page", source=url, rows=rows,
        )
        identities.append(identity)
        _save_checkpoint_source(checkpoint_path, checkpoint, identity)
        page_records: List[FundingRecord] = []
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                raise OnboardingError(f"funding row {index} is not an object")
            timestamp = raw.get("fundingTime")
            symbol = raw.get("symbol")
            rate = raw.get("fundingRate")
            price = raw.get("markPrice")
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise OnboardingError(f"funding row {index} has invalid fundingTime")
            if not isinstance(symbol, str) or not isinstance(rate, str):
                raise OnboardingError(f"funding row {index} has invalid identity/rate")
            if price is not None and not isinstance(price, str):
                raise OnboardingError(f"funding row {index} has invalid markPrice")
            page_records.append(FundingRecord(symbol, timestamp, rate, price))
        records.extend(page_records)
        if not page_records:
            break
        last = page_records[-1].funding_time_ms
        if last < cursor:
            raise OnboardingError("funding API pagination did not advance")
        if last >= requested_end_ms or len(page_records) < 1000:
            break
        cursor = last + 1
        page_number += 1
    checkpoint["complete"] = True
    checkpoint["stage"] = "raw_complete"
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)
    return identities, records, checkpoint


def normalize_funding(
    *, paths: OnboardingPaths, records: Sequence[FundingRecord],
) -> Path:
    normalized_path = (
        paths.funding_normalized / f"{paths.symbol}-funding-rate.csv"
    )
    lines = io.StringIO(newline="")
    writer = csv.writer(lines, lineterminator="\n")
    writer.writerow(("open_time", "rate", "price"))
    for record in records:
        writer.writerow((
            record.funding_time_ms,
            record.funding_rate,
            record.mark_price if record.mark_price is not None else "",
        ))
    atomic_write_bytes(normalized_path, lines.getvalue().encode("utf-8"))
    checkpoint_path = paths.funding_manifest / "checkpoint.json"
    checkpoint = dict(json.loads(checkpoint_path.read_text(encoding="utf-8")))
    checkpoint["stage"] = "normalized"
    checkpoint["normalized_path"] = str(normalized_path.resolve())
    checkpoint["normalized_sha256"] = sha256_file(normalized_path)
    checkpoint["normalized_rows"] = len(records)
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)
    return normalized_path


def price_critical_issues(report: PriceQAReport) -> List[str]:
    issues: List[str] = []
    for field, value in (
        ("duplicate timestamps", report.duplicate_count),
        ("ordering violations", report.ordering_violation_count),
        ("off-grid timestamps", report.off_grid_count),
        ("invalid OHLC rows", report.bad_ohlc_count),
        ("negative volume rows", report.negative_volume_count),
        ("non-numeric rows", report.non_numeric_count),
    ):
        if value:
            issues.append(f"{field}: {value}")
    return issues


def build_dataset_artifacts(
    *,
    paths: OnboardingPaths,
    repo_root: Path,
    canonical_authority: Path,
    role: str,
    requested_start_ms: int,
    requested_end_ms: int,
    actual_start_ms: int,
    actual_end_ms: int,
    row_count: int,
    columns: Sequence[str],
    raw_identities: Sequence[RawIdentity],
    qa: Mapping[str, object],
    gaps: Sequence[object],
    critical_issues: Sequence[str],
    fidelity_limitations: Sequence[str],
) -> Tuple[Path, Path, Path]:
    _, normalized_dir, manifest_dir = role_directories(paths, role)
    normalized_name = (
        f"{paths.symbol}-funding-rate.csv"
        if role == "funding"
        else f"{paths.symbol}-{role}-1m.csv"
    )
    normalized_path = normalized_dir / normalized_name
    data_manifest_path = manifest_dir / "data_manifest_v1.json"
    identity_path = manifest_dir / "dataset_identity_v1.json"
    collection_path = manifest_dir / "collection_manifest.json"
    data_hash = sha256_file(normalized_path)
    data_manifest = {
        "schema_version": DATA_MANIFEST_SCHEMA,
        "role": role,
        "format": "csv",
        "data_path": str(normalized_path.resolve()),
        "data_sha256": data_hash,
        "columns": list(columns),
        "row_count": row_count,
    }
    atomic_write_json(data_manifest_path, data_manifest)
    data_timeframe = "event" if role == "funding" else "1m"
    timestamp_semantics = (
        "funding event UTC" if role == "funding" else "bar open UTC"
    )
    identity = {
        "schema_version": DATASET_IDENTITY_SCHEMA,
        "role": role,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": paths.symbol,
        "data_timeframe": data_timeframe,
        "timezone": "UTC",
        "timestamp_semantics": timestamp_semantics,
        "dataset_id": f"BINANCE-USDM-{paths.symbol}-{role}-{data_hash[:16]}",
        "dataset_sha256": data_hash,
        "manifest_path": str(data_manifest_path.resolve()),
        "manifest_id": f"BINANCE-USDM-{paths.symbol}-{role}-MANIFEST-V1",
        "manifest_sha256": sha256_file(data_manifest_path),
        "coverage_start_ms": actual_start_ms,
        "coverage_end_ms": actual_end_ms,
    }
    parse_dataset_identity(identity)
    atomic_write_json(identity_path, identity)
    source_description: Dict[str, object]
    if role == "funding":
        source_description = {"endpoint": FUNDING_ENDPOINT, "official": True}
    else:
        category = ROLE_DETAILS[role][0]
        source_description = {
            "data_vision_root": "https://data.binance.vision/data/futures/um",
            "rest_fallback_endpoint": PRICE_ENDPOINTS[category],
            "category": category,
            "official": True,
        }
    collection_manifest = {
        "schema_version": COLLECTION_MANIFEST_SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "qa_status": "PASS" if not critical_issues else "FAIL",
        "critical_issues": list(critical_issues),
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": paths.symbol,
        "role": role,
        "source": source_description,
        "collection_timestamp_utc": utc_now(),
        "requested_range": {
            "start_ms": requested_start_ms,
            "start_utc": utc_from_ms(requested_start_ms),
            "end_ms": requested_end_ms,
            "end_utc": utc_from_ms(requested_end_ms),
        },
        "actual_range": {
            "start_ms": actual_start_ms,
            "start_utc": utc_from_ms(actual_start_ms),
            "end_ms": actual_end_ms,
            "end_utc": utc_from_ms(actual_end_ms),
        },
        "row_count": row_count,
        "gaps": list(gaps),
        "duplicates": qa.get("duplicate_count", 0),
        "ordering_violations": qa.get("ordering_violation_count", 0),
        "schema": DATA_MANIFEST_SCHEMA,
        "timestamp_semantics": timestamp_semantics,
        "raw_source_identities": [asdict(item) for item in raw_identities],
        "normalized_identity": {
            "path": str(normalized_path.resolve()),
            "sha256": data_hash,
            "manifest_path": str(data_manifest_path.resolve()),
            "manifest_sha256": sha256_file(data_manifest_path),
            "dataset_identity_path": str(identity_path.resolve()),
            "dataset_identity_sha256": sha256_file(identity_path),
        },
        "collector": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "git": git_identity(repo_root),
            "checkpoint_path": str((manifest_dir / "checkpoint.json").resolve()),
            "checkpoint_policy": "raw artifact/API page and checkpoint are atomically saved after every source step",
        },
        "canonical_end_authority": {
            "path": str(canonical_authority.resolve()),
            "sha256": sha256_file(canonical_authority),
        },
        "qa": dict(qa),
        "fidelity_limitations": list(fidelity_limitations),
    }
    atomic_write_json(collection_path, collection_manifest)
    checkpoint_path = manifest_dir / "checkpoint.json"
    checkpoint = dict(json.loads(checkpoint_path.read_text(encoding="utf-8")))
    checkpoint["complete"] = True
    checkpoint["stage"] = "finalized"
    checkpoint["collection_manifest_sha256"] = sha256_file(collection_path)
    checkpoint["data_manifest_sha256"] = sha256_file(data_manifest_path)
    checkpoint["dataset_identity_sha256"] = sha256_file(identity_path)
    checkpoint["updated_at_utc"] = utc_now()
    atomic_checkpoint(checkpoint_path, checkpoint)
    write_checksums(manifest_dir, (
        collection_path, data_manifest_path, identity_path, checkpoint_path,
        normalized_path,
    ))
    return collection_path, data_manifest_path, identity_path


def write_checksums(manifest_dir: Path, paths: Sequence[Path]) -> None:
    lines: List[str] = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(manifest_dir.resolve())
            label = str(relative)
        except ValueError:
            label = str(path.resolve())
        lines.append(f"{sha256_file(path)}  {label}")
    atomic_write_bytes(
        manifest_dir / "SHA256SUMS",
        ("\n".join(lines) + "\n").encode("utf-8"),
    )


def price_raw_identities(
    checkpoint: Mapping[str, object], discovery_path: Path,
) -> List[RawIdentity]:
    identities = [raw_identity(
        discovery_path,
        kind="official_rest_api_discovery",
        source="earliest available official bar discovery",
        rows=json_array(discovery_path.read_bytes(), str(discovery_path)),
    )]
    completed = checkpoint.get("completed_sources")
    if not isinstance(completed, list):
        raise OnboardingError("price checkpoint completed_sources is invalid")
    for item in completed:
        if not isinstance(item, dict):
            raise OnboardingError("price checkpoint source identity is invalid")
        values = {
            "kind": item.get("kind"),
            "source": item.get("source"),
            "path": item.get("path"),
            "sha256": item.get("sha256"),
            "bytes": item.get("bytes"),
            "row_count": item.get("row_count"),
            "first_timestamp_ms": item.get("first_timestamp_ms"),
            "last_timestamp_ms": item.get("last_timestamp_ms"),
        }
        if (
            not isinstance(values["kind"], str)
            or not isinstance(values["source"], str)
            or not isinstance(values["path"], str)
            or not isinstance(values["sha256"], str)
            or isinstance(values["bytes"], bool)
            or not isinstance(values["bytes"], int)
        ):
            raise OnboardingError("price checkpoint source identity fields are invalid")
        row_count = values["row_count"]
        first_timestamp = values["first_timestamp_ms"]
        last_timestamp = values["last_timestamp_ms"]
        if row_count is not None and (
            isinstance(row_count, bool) or not isinstance(row_count, int)
        ):
            raise OnboardingError("price checkpoint row_count is invalid")
        for timestamp in (first_timestamp, last_timestamp):
            if timestamp is not None and (
                isinstance(timestamp, bool) or not isinstance(timestamp, int)
            ):
                raise OnboardingError("price checkpoint timestamp is invalid")
        identities.append(RawIdentity(
            kind=values["kind"],
            source=values["source"],
            path=values["path"],
            sha256=values["sha256"],
            bytes=values["bytes"],
            row_count=row_count,
            first_timestamp_ms=first_timestamp,
            last_timestamp_ms=last_timestamp,
        ))
    return identities


def gap_payload(gaps: Sequence[Tuple[int, int, int]]) -> List[Dict[str, object]]:
    return [
        {
            "start_ms": start,
            "start_utc": utc_from_ms(start),
            "end_ms": end,
            "end_utc": utc_from_ms(end),
            "missing_bar_count": count,
        }
        for start, end, count in gaps
    ]


def price_qa_payload(qa: StreamingPriceQA) -> Dict[str, object]:
    report = qa.report
    return {
        "first_timestamp_ms": report.first_timestamp_ms,
        "last_timestamp_ms": report.last_timestamp_ms,
        "row_count": report.row_count,
        "expected_grid_count": report.expected_grid_count,
        "missing_bar_count": sum(item[2] for item in report.missing_ranges),
        "duplicate_count": report.duplicate_count,
        "ordering_violation_count": report.ordering_violation_count,
        "off_grid_count": report.off_grid_count,
        "bad_ohlc_count": report.bad_ohlc_count,
        "negative_volume_count": report.negative_volume_count,
        "non_numeric_count": report.non_numeric_count,
        "source_rows_outside_requested_window": report.out_of_window_count,
        "normalized_rows_outside_requested_window": 0,
        "symbol_mismatch_count": qa.symbol_mismatch_count,
        "archive_microsecond_timestamp_count": (
            qa.archive_microsecond_timestamp_count
        ),
        "archive_timestamp_normalization": (
            "16-digit microsecond values are accepted only when exactly divisible "
            "by 1000 and are then converted to milliseconds"
        ),
    }


def funding_qa_payload(
    records: Sequence[FundingRecord],
    *,
    symbol: str,
    requested_start_ms: int,
    requested_end_ms: int,
) -> Tuple[Dict[str, object], List[str]]:
    report = qa_funding_records(
        records,
        symbol=symbol,
        requested_start_ms=requested_start_ms,
        requested_end_ms=requested_end_ms,
    )
    interval_counts = Counter(
        right.funding_time_ms - left.funding_time_ms
        for left, right in zip(records, records[1:])
    )
    modal_interval = (
        max(interval_counts, key=lambda value: (interval_counts[value], -value))
        if interval_counts else None
    )
    suspicious: List[Dict[str, object]] = []
    if modal_interval is not None:
        for left, right in zip(records, records[1:]):
            interval = right.funding_time_ms - left.funding_time_ms
            if abs(interval - modal_interval) >= 60_000:
                suspicious.append({
                    "previous_time_ms": left.funding_time_ms,
                    "previous_time_utc": utc_from_ms(left.funding_time_ms),
                    "current_time_ms": right.funding_time_ms,
                    "current_time_utc": utc_from_ms(right.funding_time_ms),
                    "interval_ms": interval,
                    "review_note": "review flag only; not automatically classified as a gap",
                })
    payload: Dict[str, object] = {
        "first_funding_time_ms": report.first_funding_time_ms,
        "last_funding_time_ms": report.last_funding_time_ms,
        "row_count": report.row_count,
        "duplicate_count": report.duplicate_count,
        "ordering_violation_count": report.ordering_violation_count,
        "symbol_mismatch_count": report.symbol_mismatch_count,
        "missing_rate_count": report.missing_rate_count,
        "non_numeric_rate_count": report.non_numeric_rate_count,
        "zero_rate_count": report.zero_rate_count,
        "missing_mark_price_count": report.missing_mark_price_count,
        "out_of_window_count": report.out_of_window_count,
        "interval_distribution_ms": {
            str(key): value for key, value in report.interval_distribution_ms.items()
        },
        "modal_interval_ms": modal_interval,
        "suspicious_interval_definition": (
            "absolute deviation from exact modal observed interval >= 60000 ms; "
            "review flag only, not an automatic missing-event assertion"
        ),
        "suspicious_intervals": suspicious,
        "offset_distribution_ms": {
            str(key): value for key, value in report.offset_distribution_ms.items()
        },
    }
    critical: List[str] = []
    for label, value in (
        ("duplicate funding events", report.duplicate_count),
        ("ordering violations", report.ordering_violation_count),
        ("symbol mismatches", report.symbol_mismatch_count),
        ("missing rates", report.missing_rate_count),
        ("non-numeric rates", report.non_numeric_rate_count),
        ("missing event markPrice", report.missing_mark_price_count),
        ("events outside requested window", report.out_of_window_count),
    ):
        if value:
            critical.append(f"{label}: {value}")
    return payload, critical


def funding_mark_mapping(
    *,
    funding: Sequence[FundingRecord],
    mark_path: Path,
) -> Dict[str, object]:
    requested_minutes = {item.funding_time_ms // 60_000 * 60_000 for item in funding}
    available: set[int] = set()
    with mark_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                timestamp = int(row["open_time"])
            except (KeyError, ValueError) as exc:
                raise OnboardingError("invalid normalized Mark Price timestamp") from exc
            if timestamp in requested_minutes:
                available.add(timestamp)
    exact = 0
    floor_available = 0
    missing_floor: List[Dict[str, object]] = []
    representative: List[Dict[str, object]] = []
    indexes = {0, len(funding) // 2, max(0, len(funding) - 1)} if funding else set()
    for index, item in enumerate(funding):
        floor_time = item.funding_time_ms // 60_000 * 60_000
        exact_available = item.funding_time_ms in available
        floor_exists = floor_time in available
        if exact_available:
            exact += 1
        if floor_exists:
            floor_available += 1
        else:
            missing_floor.append({
                "funding_time_ms": item.funding_time_ms,
                "funding_time_utc": utc_from_ms(item.funding_time_ms),
                "minute_floor_ms": floor_time,
                "minute_floor_utc": utc_from_ms(floor_time),
            })
        if index in indexes:
            representative.append({
                "funding_time_ms": item.funding_time_ms,
                "funding_time_utc": utc_from_ms(item.funding_time_ms),
                "offset_ms": item.funding_time_ms % 60_000,
                "exact_mark_open_time_match": exact_available,
                "minute_floor_ms": floor_time,
                "minute_floor_mark_available": floor_exists,
            })
    return {
        "funding_event_count": len(funding),
        "exact_timestamp_match_count": exact,
        "minute_floor_diagnostic_coverage_count": floor_available,
        "minute_floor_missing_count": len(missing_floor),
        "minute_floor_missing_events": missing_floor,
        "representative_events": representative,
        "engine_mapping_applied": False,
        "limitation": (
            "Minute-floor availability is diagnostic only. Funding timestamps are "
            "preserved exactly and no mapping/rounding rule is applied by onboarding."
        ),
    }


def compare_trade_mark_timestamps(
    *, trade_path: Path, mark_path: Path,
) -> Dict[str, object]:
    mismatch_count = 0
    examples: List[Dict[str, Optional[int]]] = []
    trade_rows = 0
    mark_rows = 0
    with trade_path.open("r", encoding="utf-8", newline="") as trade_handle:
        with mark_path.open("r", encoding="utf-8", newline="") as mark_handle:
            trade_reader = csv.DictReader(trade_handle)
            mark_reader = csv.DictReader(mark_handle)
            for trade_row, mark_row in zip_longest(trade_reader, mark_reader):
                trade_time: Optional[int] = None
                mark_time: Optional[int] = None
                if trade_row is not None:
                    trade_rows += 1
                    try:
                        trade_time = int(trade_row["open_time"])
                    except (KeyError, ValueError) as exc:
                        raise OnboardingError("invalid normalized trade timestamp") from exc
                if mark_row is not None:
                    mark_rows += 1
                    try:
                        mark_time = int(mark_row["open_time"])
                    except (KeyError, ValueError) as exc:
                        raise OnboardingError("invalid normalized mark timestamp") from exc
                if trade_time != mark_time:
                    mismatch_count += 1
                    if len(examples) < 20:
                        examples.append({
                            "trade_open_time_ms": trade_time,
                            "mark_open_time_ms": mark_time,
                        })
    return {
        "trade_row_count": trade_rows,
        "mark_row_count": mark_rows,
        "timestamp_mismatch_count": mismatch_count,
        "first_mismatch_examples": examples,
        "one_to_one_alignment": mismatch_count == 0,
    }


def collect_symbol(
    *,
    symbol: str,
    data_root: Path,
    repo_root: Path,
    canonical_authority: Path,
) -> Dict[str, object]:
    paths = OnboardingPaths(data_root, symbol)
    project_end = canonical_project_end(canonical_authority)
    project_end_ms = utc_ms(project_end)
    _, onboard_date = collect_metadata(
        paths=paths,
        repo_root=repo_root,
        canonical_authority=canonical_authority,
    )
    price_results: Dict[str, Tuple[StreamingPriceQA, List[RawIdentity]]] = {}
    for role in ("trade_price", "mark_price"):
        category = ROLE_DETAILS[role][0]
        actual_start = discover_price_start(
            paths=paths,
            category=category,
            requested_start_ms=0,
        )
        sources, checkpoint = collect_price_sources(
            paths=paths,
            role=role,
            category=category,
            requested_start_ms=onboard_date,
            actual_start_ms=actual_start,
            project_end_ms=project_end_ms,
        )
        qa = normalize_price(
            paths=paths,
            role=role,
            sources=sources,
            requested_start_ms=actual_start,
            requested_end_ms=project_end_ms,
        )
        raw_dir, _, _ = role_directories(paths, role)
        discovery_path = raw_dir / "api" / "discovery-start-0.json"
        price_results[role] = (
            qa,
            price_raw_identities(checkpoint, discovery_path),
        )
    funding_identities, funding_records, _ = collect_funding_pages(
        paths=paths,
        requested_start_ms=onboard_date,
        requested_end_ms=project_end_ms,
    )
    funding_path = normalize_funding(paths=paths, records=funding_records)
    if not funding_records:
        raise OnboardingError(f"no official funding history for {symbol}")
    mapping = funding_mark_mapping(
        funding=funding_records,
        mark_path=paths.mark_normalized / f"{symbol}-mark_price-1m.csv",
    )
    trade_mark_alignment = compare_trade_mark_timestamps(
        trade_path=paths.trade_normalized / f"{symbol}-trade_price-1m.csv",
        mark_path=paths.mark_normalized / f"{symbol}-mark_price-1m.csv",
    )
    artifact_paths: Dict[str, List[str]] = {}
    for role in ("trade_price", "mark_price"):
        qa, raw_identities = price_results[role]
        report = qa.report
        if report.first_timestamp_ms is None or report.last_timestamp_ms is None:
            raise OnboardingError(f"normalized {role} dataset is empty")
        qa_payload = price_qa_payload(qa)
        qa_payload["trade_mark_timestamp_alignment"] = trade_mark_alignment
        if role == "mark_price":
            qa_payload["funding_time_mapping"] = mapping
            trade_report = price_results["trade_price"][0].report
            qa_payload["coverage_vs_trade"] = {
                "trade_start_ms": trade_report.first_timestamp_ms,
                "trade_end_ms": trade_report.last_timestamp_ms,
                "same_start": report.first_timestamp_ms == trade_report.first_timestamp_ms,
                "same_end": report.last_timestamp_ms == trade_report.last_timestamp_ms,
            }
        limitations: List[str] = []
        if report.missing_ranges:
            limitations.append(
                "Official source coverage contains missing 1m bars; no bars were synthesized.",
            )
        if role == "mark_price" and mapping["exact_timestamp_match_count"] != len(funding_records):
            limitations.append(
                "Exact fundingTime-to-mark-open mapping is not complete; no rounding rule was applied.",
            )
        critical = price_critical_issues(report)
        if not bool(trade_mark_alignment["one_to_one_alignment"]):
            critical.append("trade/mark timestamps are not aligned one-to-one")
        artifacts = build_dataset_artifacts(
            paths=paths,
            repo_root=repo_root,
            canonical_authority=canonical_authority,
            role=role,
            requested_start_ms=onboard_date,
            requested_end_ms=project_end_ms,
            actual_start_ms=report.first_timestamp_ms,
            actual_end_ms=report.last_timestamp_ms,
            row_count=report.row_count,
            columns=ROLE_DETAILS[role][1],
            raw_identities=raw_identities,
            qa=qa_payload,
            gaps=gap_payload(report.missing_ranges),
            critical_issues=critical,
            fidelity_limitations=limitations,
        )
        artifact_paths[role] = [str(item.resolve()) for item in artifacts]
    funding_qa, funding_critical = funding_qa_payload(
        funding_records,
        symbol=symbol,
        requested_start_ms=onboard_date,
        requested_end_ms=project_end_ms,
    )
    funding_qa["funding_time_mapping"] = mapping
    funding_artifacts = build_dataset_artifacts(
        paths=paths,
        repo_root=repo_root,
        canonical_authority=canonical_authority,
        role="funding",
        requested_start_ms=onboard_date,
        requested_end_ms=project_end_ms,
        actual_start_ms=funding_records[0].funding_time_ms,
        actual_end_ms=funding_records[-1].funding_time_ms,
        row_count=len(funding_records),
        columns=("open_time", "rate", "price"),
        raw_identities=funding_identities,
        qa=funding_qa,
        gaps=(),
        critical_issues=funding_critical,
        fidelity_limitations=(
            "Funding events are event data; unusual intervals are review flags, not automatically classified as gaps.",
            "Exact millisecond fundingTime values are preserved; no minute mapping rule is applied.",
        ),
    )
    artifact_paths["funding"] = [str(item.resolve()) for item in funding_artifacts]
    return {
        "symbol": symbol,
        "onboard_date_ms": onboard_date,
        "onboard_date_utc": utc_from_ms(onboard_date),
        "canonical_end_ms": project_end_ms,
        "canonical_end_utc": utc_from_ms(project_end_ms),
        "trade_price": price_qa_payload(price_results["trade_price"][0]),
        "mark_price": price_qa_payload(price_results["mark_price"][0]),
        "funding": funding_qa,
        "funding_mark_mapping": mapping,
        "trade_mark_timestamp_alignment": trade_mark_alignment,
        "normalized_funding_path": str(funding_path.resolve()),
        "artifacts": artifact_paths,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--canonical-authority", type=Path, required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    results: List[Dict[str, object]] = []
    for symbol in args.symbols:
        print(f"[{utc_now()}] START {symbol}", flush=True)
        result = collect_symbol(
            symbol=symbol,
            data_root=args.data_root.resolve(),
            repo_root=args.repo_root.resolve(),
            canonical_authority=args.canonical_authority.resolve(),
        )
        results.append(result)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        print(f"[{utc_now()}] COMPLETE {symbol}", flush=True)
    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
