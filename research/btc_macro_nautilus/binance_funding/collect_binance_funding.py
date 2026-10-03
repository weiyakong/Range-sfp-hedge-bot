#!/usr/bin/env python3
"""Collect and independently validate official Binance USD-M funding history."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, TypedDict


SCHEMA_VERSION = "binance-usdm-funding-v1"
COLLECTOR_VERSION = "1.0.0"
ENDPOINT = "https://fapi.binance.com/fapi/v1/fundingRate"
DEFAULT_LIMIT = 1000
PAGE_RE = re.compile(r"^page-(\d{6})-start-(\d+)-end-(\d+)\.json$")
CSV_FIELDS = ("symbol", "funding_time_ms", "funding_time_utc", "funding_rate", "mark_price")


class FundingRecord(TypedDict, total=False):
    symbol: str
    fundingTime: int
    fundingRate: Optional[str]
    markPrice: Optional[str]


class RawFileIdentity(TypedDict):
    page_number: int
    request_start_ms: int
    request_end_ms: int
    path: str
    bytes: int
    sha256: str
    row_count: int
    first_funding_time_ms: Optional[int]
    last_funding_time_ms: Optional[int]


class SurroundingEvent(TypedDict):
    symbol: object
    funding_time_ms: int
    funding_time_utc: str
    funding_rate: object
    mark_price: object


class IntervalAnomaly(TypedDict):
    previous_funding_time_ms: int
    previous_funding_time_utc: str
    current_funding_time_ms: int
    current_funding_time_utc: str
    delta_ms: int
    delta_seconds: int
    delta_hours: float
    surrounding_funding_events: List[SurroundingEvent]


PageFetcher = Callable[[Mapping[str, str]], bytes]


@dataclass(frozen=True)
class CollectorConfig:
    data_root: Path
    repo_root: Path
    symbol: str
    requested_start_ms: int
    requested_end_ms: int
    source_manifest_path: Path
    limit: int = DEFAULT_LIMIT

    @property
    def raw_pages_dir(self) -> Path:
        return self.data_root / "raw/binance/usdt_m" / self.symbol / "funding_rate/api/pages"

    @property
    def normalized_path(self) -> Path:
        return (
            self.data_root
            / "normalized/binance/usdt_m"
            / self.symbol
            / "funding_rate"
            / f"{self.symbol}-funding-rate.csv"
        )

    @property
    def manifest_dir(self) -> Path:
        return self.data_root / "manifests/binance/usdt_m" / self.symbol / "funding_rate"

    @property
    def checkpoint_path(self) -> Path:
        return self.manifest_dir / "checkpoint.json"

    @property
    def manifest_path(self) -> Path:
        return self.manifest_dir / "funding_manifest.json"

    @property
    def checksums_path(self) -> Path:
        return self.manifest_dir / "SHA256SUMS"

    @property
    def config_fingerprint(self) -> str:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "endpoint": ENDPOINT,
            "symbol": self.symbol,
            "requested_start_ms": self.requested_start_ms,
            "requested_end_ms": self.requested_end_ms,
            "limit": self.limit,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CollectionResult:
    complete: bool
    page_count: int
    raw_row_count: int
    next_start_ms: int
    last_funding_time_ms: Optional[int]
    coverage_proof: Optional[Dict[str, object]]


@dataclass(frozen=True)
class ValidationReport:
    actual_first_funding_time_ms: Optional[int]
    actual_first_funding_time_utc: Optional[str]
    actual_last_funding_time_ms: Optional[int]
    actual_last_funding_time_utc: Optional[str]
    row_count: int
    duplicate_count: int
    ordering_violations: int
    missing_funding_rate_count: int
    non_numeric_funding_rate_count: int
    zero_rate_count: int
    missing_mark_price_count: int
    symbol_mismatch_count: int
    out_of_window_count: int
    interval_distribution_ms: Dict[int, int]
    modal_interval_ms: Optional[int]
    unusual_intervals: List[IntervalAnomaly]
    normalized_sha256: str
    normalized_bytes: int
    normalized_reproducible: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def ms_from_utc(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp is not timezone-aware: {value}")
    return int(parsed.timestamp() * 1000)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, encoded)


def parse_page(payload: bytes, path_label: str) -> List[FundingRecord]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid JSON in {path_label}: {exc}") from exc
    if not isinstance(decoded, list):
        raise RuntimeError(f"Binance response is not a list in {path_label}: {decoded!r}")
    rows: List[FundingRecord] = []
    for index, raw in enumerate(decoded):
        if not isinstance(raw, dict):
            raise RuntimeError(f"row {index} is not an object in {path_label}")
        funding_time = raw.get("fundingTime")
        if isinstance(funding_time, bool) or not isinstance(funding_time, int):
            raise RuntimeError(f"row {index} has invalid fundingTime in {path_label}: {funding_time!r}")
        rows.append(raw)  # type: ignore[arg-type]
    return rows


def raw_identity(path: Path) -> RawFileIdentity:
    match = PAGE_RE.match(path.name)
    if match is None:
        raise RuntimeError(f"unexpected raw page filename: {path}")
    rows = parse_page(path.read_bytes(), str(path))
    times = [row["fundingTime"] for row in rows]
    return {
        "page_number": int(match.group(1)),
        "request_start_ms": int(match.group(2)),
        "request_end_ms": int(match.group(3)),
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "row_count": len(rows),
        "first_funding_time_ms": times[0] if times else None,
        "last_funding_time_ms": times[-1] if times else None,
    }


def list_raw_identities(config: CollectorConfig) -> List[RawFileIdentity]:
    if not config.raw_pages_dir.exists():
        return []
    identities = [raw_identity(path) for path in sorted(config.raw_pages_dir.glob("*.json"))]
    for expected, identity in enumerate(identities, start=1):
        if identity["page_number"] != expected:
            raise RuntimeError(
                f"raw page sequence is not contiguous: expected {expected}, got {identity['page_number']}"
            )
        if identity["request_end_ms"] != config.requested_end_ms:
            raise RuntimeError(f"raw page end is incompatible with current request: {identity['path']}")
        if expected == 1 and identity["request_start_ms"] != config.requested_start_ms:
            raise RuntimeError(f"raw page start is incompatible with current request: {identity['path']}")
        if expected > 1:
            previous = identities[expected - 2]
            previous_last = previous["last_funding_time_ms"]
            if previous_last is None:
                raise RuntimeError("an empty raw page must be terminal")
            if identity["request_start_ms"] != previous_last + 1:
                raise RuntimeError(f"raw request sequence is discontinuous at {identity['path']}")
    return identities


def load_raw_records(config: CollectorConfig) -> List[FundingRecord]:
    records: List[FundingRecord] = []
    for identity in list_raw_identities(config):
        records.extend(parse_page(Path(identity["path"]).read_bytes(), identity["path"]))
    return records


def default_fetcher(params: Mapping[str, str]) -> bytes:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Range-sfp-hedge-bot/binance-funding-v1"},
        method="GET",
    )
    last_error: Optional[BaseException] = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            last_error = RuntimeError(f"HTTP {exc.code} from Binance: {body[:1000]!r}")
            if exc.code == 429 and attempt < 5:
                retry_after = exc.headers.get("Retry-After", "5")
                try:
                    delay = max(1.0, float(retry_after))
                except ValueError:
                    delay = 5.0
                time.sleep(delay)
                continue
            if 500 <= exc.code < 600 and attempt < 5:
                time.sleep(float(attempt))
                continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(float(attempt))
    raise RuntimeError(f"Binance request failed after retries: {last_error}")


def _checkpoint_payload(
    config: CollectorConfig,
    identities: Sequence[RawFileIdentity],
    complete: bool,
    coverage_proof: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    last_times = [item["last_funding_time_ms"] for item in identities if item["last_funding_time_ms"] is not None]
    last_time = last_times[-1] if last_times else None
    next_start = int(last_time) + 1 if last_time is not None else config.requested_start_ms
    return {
        "schema_version": SCHEMA_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "config_fingerprint": config.config_fingerprint,
        "endpoint": ENDPOINT,
        "symbol": config.symbol,
        "requested_start_ms": config.requested_start_ms,
        "requested_start_utc": utc_from_ms(config.requested_start_ms),
        "requested_end_ms": config.requested_end_ms,
        "requested_end_utc": utc_from_ms(config.requested_end_ms),
        "limit": config.limit,
        "updated_at_utc": utc_now(),
        "complete": complete,
        "page_count": len(identities),
        "raw_row_count": sum(item["row_count"] for item in identities),
        "last_funding_time_ms": last_time,
        "next_start_ms": next_start,
        "coverage_proof": dict(coverage_proof) if coverage_proof is not None else None,
        "raw_files": list(identities),
    }


def _recover_state(config: CollectorConfig) -> Tuple[List[RawFileIdentity], bool, Optional[Dict[str, object]]]:
    identities = list_raw_identities(config)
    complete = False
    proof: Optional[Dict[str, object]] = None
    if identities and identities[-1]["row_count"] == 0:
        terminal = identities[-1]
        complete = True
        proof = {
            "method": "empty_official_api_response",
            "request_start_ms": terminal["request_start_ms"],
            "request_start_utc": utc_from_ms(terminal["request_start_ms"]),
            "request_end_ms": terminal["request_end_ms"],
            "request_end_utc": utc_from_ms(terminal["request_end_ms"]),
            "raw_path": terminal["path"],
            "raw_sha256": terminal["sha256"],
        }
    elif identities:
        last = identities[-1]["last_funding_time_ms"]
        if last is not None and last >= config.requested_end_ms:
            complete = True
            proof = {
                "method": "last_event_reached_requested_end",
                "last_funding_time_ms": last,
                "last_funding_time_utc": utc_from_ms(last),
            }
    if config.checkpoint_path.exists():
        checkpoint = json.loads(config.checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("config_fingerprint") != config.config_fingerprint:
            raise RuntimeError("checkpoint is incompatible with current collector configuration")
        recorded = checkpoint.get("raw_files")
        if not isinstance(recorded, list):
            raise RuntimeError("checkpoint raw_files is invalid")
        recorded_hashes = [item.get("sha256") for item in recorded if isinstance(item, dict)]
        current_hashes = [item["sha256"] for item in identities]
        if recorded_hashes != current_hashes[: len(recorded_hashes)]:
            raise RuntimeError("checkpoint raw-file hashes do not match current raw artifacts")
    return identities, complete, proof


def collect_funding(
    config: CollectorConfig,
    *,
    fetcher: PageFetcher = default_fetcher,
    max_new_pages: Optional[int] = None,
) -> CollectionResult:
    if config.requested_end_ms < config.requested_start_ms:
        raise ValueError("requested end precedes requested start")
    if not 1 <= config.limit <= 1000:
        raise ValueError("Binance funding limit must be between 1 and 1000")
    config.raw_pages_dir.mkdir(parents=True, exist_ok=True)
    config.manifest_dir.mkdir(parents=True, exist_ok=True)
    identities, complete, proof = _recover_state(config)
    if complete:
        atomic_write_json(config.checkpoint_path, _checkpoint_payload(config, identities, True, proof))
        return _collection_result(config, identities, True, proof)

    new_pages = 0
    while not complete:
        last_time = identities[-1]["last_funding_time_ms"] if identities else None
        next_start = int(last_time) + 1 if last_time is not None else config.requested_start_ms
        page_number = len(identities) + 1
        page_path = config.raw_pages_dir / (
            f"page-{page_number:06d}-start-{next_start}-end-{config.requested_end_ms}.json"
        )
        if page_path.exists():
            payload = page_path.read_bytes()
        else:
            params = {
                "symbol": config.symbol,
                "startTime": str(next_start),
                "endTime": str(config.requested_end_ms),
                "limit": str(config.limit),
            }
            payload = fetcher(params)
            parse_page(payload, f"HTTP page {page_number}")
            atomic_write_bytes(page_path, payload)

        identity = raw_identity(page_path)
        if identity["request_start_ms"] != next_start:
            raise RuntimeError(f"raw page request start mismatch: {page_path}")
        rows = parse_page(payload, str(page_path))
        if rows:
            page_times = [row["fundingTime"] for row in rows]
            if any(current < previous for previous, current in zip(page_times, page_times[1:])):
                raise RuntimeError(f"Binance page is not chronologically ordered: {page_path}")
            if page_times[-1] < next_start:
                raise RuntimeError(
                    f"Binance pagination did not advance: requested {next_start}, last event {page_times[-1]}"
                )
        identities.append(identity)
        new_pages += 1

        if not rows:
            complete = True
            proof = {
                "method": "empty_official_api_response",
                "request_start_ms": next_start,
                "request_start_utc": utc_from_ms(next_start),
                "request_end_ms": config.requested_end_ms,
                "request_end_utc": utc_from_ms(config.requested_end_ms),
                "raw_path": str(page_path.resolve()),
                "raw_sha256": identity["sha256"],
            }
        elif rows[-1]["fundingTime"] >= config.requested_end_ms:
            complete = True
            proof = {
                "method": "last_event_reached_requested_end",
                "last_funding_time_ms": rows[-1]["fundingTime"],
                "last_funding_time_utc": utc_from_ms(rows[-1]["fundingTime"]),
            }

        atomic_write_json(config.checkpoint_path, _checkpoint_payload(config, identities, complete, proof))
        if max_new_pages is not None and new_pages >= max_new_pages and not complete:
            break

    return _collection_result(config, identities, complete, proof)


def _collection_result(
    config: CollectorConfig,
    identities: Sequence[RawFileIdentity],
    complete: bool,
    proof: Optional[Dict[str, object]],
) -> CollectionResult:
    last_times = [item["last_funding_time_ms"] for item in identities if item["last_funding_time_ms"] is not None]
    last_time = last_times[-1] if last_times else None
    return CollectionResult(
        complete=complete,
        page_count=len(identities),
        raw_row_count=sum(item["row_count"] for item in identities),
        next_start_ms=int(last_time) + 1 if last_time is not None else config.requested_start_ms,
        last_funding_time_ms=last_time,
        coverage_proof=proof,
    )


def _decimal_is_numeric(value: object) -> bool:
    if not isinstance(value, str) or value == "":
        return False
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return False
    return parsed.is_finite()


def _csv_bytes(records: Sequence[FundingRecord]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for record in records:
        funding_time = record["fundingTime"]
        rate = record.get("fundingRate")
        mark_price = record.get("markPrice")
        writer.writerow(
            (
                record.get("symbol", ""),
                str(funding_time),
                utc_from_ms(funding_time),
                rate if isinstance(rate, str) else "",
                mark_price if isinstance(mark_price, str) else "",
            )
        )
    return stream.getvalue().encode("utf-8")


def _surrounding_event(record: FundingRecord) -> SurroundingEvent:
    funding_time = record["fundingTime"]
    return {
        "symbol": record.get("symbol"),
        "funding_time_ms": funding_time,
        "funding_time_utc": utc_from_ms(funding_time),
        "funding_rate": record.get("fundingRate"),
        "mark_price": record.get("markPrice"),
    }


def normalize_and_validate(config: CollectorConfig) -> ValidationReport:
    source_records = load_raw_records(config)
    duplicate_count = 0
    seen: set[int] = set()
    unique: List[FundingRecord] = []
    for record in source_records:
        timestamp = record["fundingTime"]
        if timestamp in seen:
            duplicate_count += 1
            continue
        seen.add(timestamp)
        unique.append(record)

    ordering_violations = sum(
        1
        for previous, current in zip(source_records, source_records[1:])
        if current["fundingTime"] < previous["fundingTime"]
    )
    symbol_mismatch_count = sum(1 for row in source_records if row.get("symbol") != config.symbol)
    out_of_window_count = sum(
        1
        for row in source_records
        if row["fundingTime"] < config.requested_start_ms or row["fundingTime"] > config.requested_end_ms
    )
    normalized = sorted(
        (
            row
            for row in unique
            if config.requested_start_ms <= row["fundingTime"] <= config.requested_end_ms
            and row.get("symbol") == config.symbol
        ),
        key=lambda row: row["fundingTime"],
    )
    missing_rate = sum(1 for row in normalized if row.get("fundingRate") is None or row.get("fundingRate") == "")
    non_numeric_rate = sum(
        1
        for row in normalized
        if row.get("fundingRate") not in (None, "") and not _decimal_is_numeric(row.get("fundingRate"))
    )
    zero_rate = 0
    for row in normalized:
        value = row.get("fundingRate")
        if _decimal_is_numeric(value) and Decimal(str(value)) == 0:
            zero_rate += 1
    missing_mark_price = sum(1 for row in normalized if row.get("markPrice") is None or row.get("markPrice") == "")

    deltas = [
        current["fundingTime"] - previous["fundingTime"]
        for previous, current in zip(normalized, normalized[1:])
    ]
    counts = Counter(deltas)
    interval_distribution = dict(sorted(counts.items()))
    modal_interval = max(counts, key=lambda delta: (counts[delta], -delta)) if counts else None
    unusual: List[IntervalAnomaly] = []
    if modal_interval is not None:
        for index in range(1, len(normalized)):
            previous = normalized[index - 1]
            current = normalized[index]
            delta = current["fundingTime"] - previous["fundingTime"]
            if delta == modal_interval:
                continue
            context = normalized[max(0, index - 2) : min(len(normalized), index + 3)]
            unusual.append(
                {
                    "previous_funding_time_ms": previous["fundingTime"],
                    "previous_funding_time_utc": utc_from_ms(previous["fundingTime"]),
                    "current_funding_time_ms": current["fundingTime"],
                    "current_funding_time_utc": utc_from_ms(current["fundingTime"]),
                    "delta_ms": delta,
                    "delta_seconds": delta // 1000,
                    "delta_hours": delta / 3_600_000,
                    "surrounding_funding_events": [_surrounding_event(row) for row in context],
                }
            )

    first_build = _csv_bytes(normalized)
    second_build = _csv_bytes(normalized)
    reproducible = first_build == second_build and sha256_bytes(first_build) == sha256_bytes(second_build)
    if not reproducible:
        raise RuntimeError("normalized CSV is not reproducible within the same run")
    atomic_write_bytes(config.normalized_path, first_build)
    return ValidationReport(
        actual_first_funding_time_ms=normalized[0]["fundingTime"] if normalized else None,
        actual_first_funding_time_utc=utc_from_ms(normalized[0]["fundingTime"]) if normalized else None,
        actual_last_funding_time_ms=normalized[-1]["fundingTime"] if normalized else None,
        actual_last_funding_time_utc=utc_from_ms(normalized[-1]["fundingTime"]) if normalized else None,
        row_count=len(normalized),
        duplicate_count=duplicate_count,
        ordering_violations=ordering_violations,
        missing_funding_rate_count=missing_rate,
        non_numeric_funding_rate_count=non_numeric_rate,
        zero_rate_count=zero_rate,
        missing_mark_price_count=missing_mark_price,
        symbol_mismatch_count=symbol_mismatch_count,
        out_of_window_count=out_of_window_count,
        interval_distribution_ms=interval_distribution,
        modal_interval_ms=modal_interval,
        unusual_intervals=unusual,
        normalized_sha256=sha256_bytes(first_build),
        normalized_bytes=len(first_build),
        normalized_reproducible=reproducible,
    )


def git_metadata(repo_root: Path) -> Dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, text=True, capture_output=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=repo_root, check=True, text=True, capture_output=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "status_short": status}


def finalize(config: CollectorConfig, collection: CollectionResult) -> Dict[str, object]:
    if not collection.complete or collection.coverage_proof is None:
        raise RuntimeError("cannot finalize an incomplete collection")
    report = normalize_and_validate(config)
    raw_files = list_raw_identities(config)
    critical_issues: List[str] = []
    if report.duplicate_count:
        critical_issues.append("duplicate fundingTime values were present in raw responses")
    if report.ordering_violations:
        critical_issues.append("raw funding events were not chronologically ordered")
    if report.missing_funding_rate_count:
        critical_issues.append("missing fundingRate values were present")
    if report.non_numeric_funding_rate_count:
        critical_issues.append("non-numeric fundingRate values were present")
    if report.symbol_mismatch_count:
        critical_issues.append("records with a symbol other than BTCUSDT were present")
    if report.out_of_window_count:
        critical_issues.append("records outside the requested window were present")
    if not report.normalized_reproducible:
        critical_issues.append("normalized output was not reproducible")

    manifest: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "qa_status": "PASS" if not critical_issues else "FAIL",
        "critical_issues": critical_issues,
        "source": {
            "endpoint": ENDPOINT,
            "exchange": "Binance",
            "market": "USD-M perpetual futures",
            "symbol": config.symbol,
            "timezone": "UTC",
            "source_values": ["fundingTime", "fundingRate", "markPrice"],
        },
        "collection_timestamp_utc": utc_now(),
        "requested_window": {
            "start_ms": config.requested_start_ms,
            "start_utc": utc_from_ms(config.requested_start_ms),
            "end_ms": config.requested_end_ms,
            "end_utc": utc_from_ms(config.requested_end_ms),
            "source_manifest_path": str(config.source_manifest_path.resolve()),
            "source_manifest_sha256": sha256_file(config.source_manifest_path),
        },
        "actual_coverage": {
            "first_funding_time_ms": report.actual_first_funding_time_ms,
            "first_funding_time_utc": report.actual_first_funding_time_utc,
            "last_funding_time_ms": report.actual_last_funding_time_ms,
            "last_funding_time_utc": report.actual_last_funding_time_utc,
            "row_count": report.row_count,
            "end_coverage_proof": collection.coverage_proof,
        },
        "validation": {
            "duplicate_count": report.duplicate_count,
            "ordering_violations": report.ordering_violations,
            "missing_funding_rate_count": report.missing_funding_rate_count,
            "non_numeric_funding_rate_count": report.non_numeric_funding_rate_count,
            "zero_rate_count": report.zero_rate_count,
            "missing_mark_price_count": report.missing_mark_price_count,
            "symbol_mismatch_count": report.symbol_mismatch_count,
            "out_of_window_count": report.out_of_window_count,
            "normalized_reproducible": report.normalized_reproducible,
            "unusual_interval_definition": "delta_ms differs from the modal observed interval; this is a review flag, not an assertion of missing data",
            "modal_interval_ms": report.modal_interval_ms,
            "interval_distribution_ms": {str(key): value for key, value in report.interval_distribution_ms.items()},
            "unusual_intervals": report.unusual_intervals,
        },
        "raw_files": raw_files,
        "normalized_file": {
            "path": str(config.normalized_path.resolve()),
            "format": "CSV",
            "bytes": report.normalized_bytes,
            "rows": report.row_count,
            "sha256": report.normalized_sha256,
            "columns": list(CSV_FIELDS),
            "decimal_storage": "funding_rate and mark_price retain the exact Binance JSON string spelling",
        },
        "collector": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "git": git_metadata(config.repo_root),
            "config_fingerprint": config.config_fingerprint,
            "checkpoint_path": str(config.checkpoint_path.resolve()),
            "checkpoint_sha256": sha256_file(config.checkpoint_path),
            "checkpoint_policy": "raw response and checkpoint are atomically written after every API page",
        },
    }
    atomic_write_json(config.manifest_path, manifest)
    manifest_sha = sha256_file(config.manifest_path)
    atomic_write_bytes(config.checksums_path, f"{manifest_sha}  {config.manifest_path.name}\n".encode("utf-8"))
    return manifest


def config_from_manifest(data_root: Path, repo_root: Path, symbol: str, limit: int) -> CollectorConfig:
    manifest_path = data_root / "manifests/strict_futures_1m_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset = payload.get("dataset")
    if not isinstance(dataset, dict):
        raise RuntimeError("strict futures manifest has no dataset object")
    if dataset.get("exchange") != "Binance" or dataset.get("symbol") != symbol:
        raise RuntimeError("strict futures manifest does not describe Binance BTCUSDT")
    start = dataset.get("strict_start_utc")
    end = dataset.get("strict_end_utc")
    if not isinstance(start, str) or not isinstance(end, str):
        raise RuntimeError("strict futures manifest lacks strict UTC bounds")
    return CollectorConfig(
        data_root=data_root,
        repo_root=repo_root,
        symbol=symbol,
        requested_start_ms=ms_from_utc(start),
        requested_end_ms=ms_from_utc(end),
        source_manifest_path=manifest_path,
        limit=limit,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--mode", choices=("smoke", "collect", "validate"), default="collect")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_manifest(args.data_root.resolve(), args.repo_root.resolve(), args.symbol, args.limit)
    if args.mode == "smoke":
        collection = collect_funding(config, max_new_pages=1)
        print(json.dumps(asdict(collection), indent=2, sort_keys=True))
        return 0
    if args.mode == "collect":
        collection = collect_funding(config)
        manifest = finalize(config, collection)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0 if manifest["qa_status"] == "PASS" else 1
    identities, complete, proof = _recover_state(config)
    collection = _collection_result(config, identities, complete, proof)
    manifest = finalize(config, collection)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["qa_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
