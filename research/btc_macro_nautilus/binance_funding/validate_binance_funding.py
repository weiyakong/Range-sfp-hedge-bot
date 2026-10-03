#!/usr/bin/env python3
"""Independently validate saved Binance funding artifacts against raw pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


EXPECTED_ENDPOINT = "https://fapi.binance.com/fapi/v1/fundingRate"
EXPECTED_SYMBOL = "BTCUSDT"
EXPECTED_COLUMNS = ("symbol", "funding_time_ms", "funding_time_utc", "funding_rate", "mark_price")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def is_numeric_decimal(value: str) -> bool:
    if value == "":
        return False
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return False
    return parsed.is_finite()


def validate_artifacts(data_root: Path) -> Dict[str, object]:
    manifest_dir = data_root / "manifests/binance/usdt_m/BTCUSDT/funding_rate"
    manifest_path = manifest_dir / "funding_manifest.json"
    checksums_path = manifest_dir / "SHA256SUMS"
    errors: List[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    source = manifest.get("source", {})
    if not isinstance(source, dict) or source.get("endpoint") != EXPECTED_ENDPOINT:
        errors.append("manifest source endpoint is not the approved Binance endpoint")
    if not isinstance(source, dict) or source.get("symbol") != EXPECTED_SYMBOL:
        errors.append("manifest source symbol is not BTCUSDT")

    expected_checksum_line = f"{sha256_file(manifest_path)}  {manifest_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected_checksum_line:
        errors.append("SHA256SUMS does not match funding_manifest.json")

    raw_records: List[Mapping[str, object]] = []
    raw_files = manifest.get("raw_files")
    if not isinstance(raw_files, list) or not raw_files:
        errors.append("manifest raw_files is empty or invalid")
        raw_files = []
    for expected_page_number, identity in enumerate(raw_files, start=1):
        if not isinstance(identity, dict):
            errors.append(f"raw identity {expected_page_number} is not an object")
            continue
        path = Path(str(identity.get("path", "")))
        if not path.is_file():
            errors.append(f"raw file is missing: {path}")
            continue
        if identity.get("page_number") != expected_page_number:
            errors.append(f"raw page sequence mismatch at {path}")
        actual_hash = sha256_file(path)
        if identity.get("sha256") != actual_hash:
            errors.append(f"raw SHA-256 mismatch: {path}")
        try:
            rows = json.loads(path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"raw JSON parse failure at {path}: {exc}")
            continue
        if not isinstance(rows, list):
            errors.append(f"raw page is not a JSON list: {path}")
            continue
        if identity.get("row_count") != len(rows):
            errors.append(f"raw row count mismatch: {path}")
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"raw row is not an object: {path}")
                continue
            raw_records.append(row)

    requested = manifest.get("requested_window", {})
    if not isinstance(requested, dict):
        errors.append("requested_window is invalid")
        requested = {}
    start_ms = requested.get("start_ms")
    end_ms = requested.get("end_ms")
    if not isinstance(start_ms, int) or not isinstance(end_ms, int):
        errors.append("requested window bounds are not integer milliseconds")
        start_ms, end_ms = 0, -1

    seen: set[int] = set()
    expected_rows: List[Tuple[str, str, str, str, str]] = []
    duplicate_count = 0
    ordering_violations = 0
    prior_time: Optional[int] = None
    for row in raw_records:
        timestamp = row.get("fundingTime")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            errors.append(f"invalid raw fundingTime: {timestamp!r}")
            continue
        if prior_time is not None and timestamp < prior_time:
            ordering_violations += 1
        prior_time = timestamp
        if timestamp in seen:
            duplicate_count += 1
            continue
        seen.add(timestamp)
        if not start_ms <= timestamp <= end_ms or row.get("symbol") != EXPECTED_SYMBOL:
            continue
        rate = row.get("fundingRate")
        mark_price = row.get("markPrice")
        expected_rows.append(
            (
                str(row.get("symbol", "")),
                str(timestamp),
                utc_from_ms(timestamp),
                rate if isinstance(rate, str) else "",
                mark_price if isinstance(mark_price, str) else "",
            )
        )
    expected_rows.sort(key=lambda row: int(row[1]))

    normalized_file = manifest.get("normalized_file", {})
    if not isinstance(normalized_file, dict):
        errors.append("normalized_file is invalid")
        normalized_file = {}
    csv_path = Path(str(normalized_file.get("path", "")))
    if not csv_path.is_file():
        errors.append(f"normalized CSV is missing: {csv_path}")
        csv_rows: List[Tuple[str, str, str, str, str]] = []
    else:
        if normalized_file.get("sha256") != sha256_file(csv_path):
            errors.append("normalized CSV SHA-256 does not match manifest")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            all_rows = list(reader)
        if not all_rows or tuple(all_rows[0]) != EXPECTED_COLUMNS:
            errors.append("normalized CSV header does not match contract")
            csv_rows = []
        else:
            csv_rows = [tuple(row) for row in all_rows[1:] if len(row) == len(EXPECTED_COLUMNS)]
            if len(csv_rows) != len(all_rows) - 1:
                errors.append("normalized CSV contains a malformed row")
    if csv_rows != expected_rows:
        errors.append("normalized CSV rows do not exactly match deduplicated in-window raw values")

    timestamps = [int(row[1]) for row in csv_rows]
    intervals = [current - previous for previous, current in zip(timestamps, timestamps[1:])]
    interval_distribution = {str(key): value for key, value in sorted(Counter(intervals).items())}
    validation = manifest.get("validation", {})
    if not isinstance(validation, dict):
        errors.append("validation object is invalid")
        validation = {}
    if validation.get("duplicate_count") != duplicate_count:
        errors.append("manifest duplicate count does not match raw data")
    if validation.get("ordering_violations") != ordering_violations:
        errors.append("manifest ordering violation count does not match raw data")
    if validation.get("interval_distribution_ms") != interval_distribution:
        errors.append("manifest interval distribution does not match normalized CSV")

    missing_rate_count = sum(1 for row in csv_rows if row[3] == "")
    non_numeric_rate_count = sum(1 for row in csv_rows if row[3] != "" and not is_numeric_decimal(row[3]))
    zero_rate_count = sum(1 for row in csv_rows if is_numeric_decimal(row[3]) and Decimal(row[3]) == 0)
    missing_mark_price_count = sum(1 for row in csv_rows if row[4] == "")
    checks = {
        "missing_funding_rate_count": missing_rate_count,
        "non_numeric_funding_rate_count": non_numeric_rate_count,
        "zero_rate_count": zero_rate_count,
        "missing_mark_price_count": missing_mark_price_count,
    }
    for field, actual in checks.items():
        if validation.get(field) != actual:
            errors.append(f"manifest {field} does not match normalized CSV")

    coverage = manifest.get("actual_coverage", {})
    if not isinstance(coverage, dict):
        errors.append("actual_coverage is invalid")
        coverage = {}
    expected_first = timestamps[0] if timestamps else None
    expected_last = timestamps[-1] if timestamps else None
    if coverage.get("row_count") != len(csv_rows):
        errors.append("manifest row count does not match normalized CSV")
    if coverage.get("first_funding_time_ms") != expected_first:
        errors.append("manifest first funding time does not match normalized CSV")
    if coverage.get("last_funding_time_ms") != expected_last:
        errors.append("manifest last funding time does not match normalized CSV")

    proof = coverage.get("end_coverage_proof")
    if not isinstance(proof, dict) or proof.get("method") != "empty_official_api_response":
        errors.append("end coverage is not proven by an empty bounded API response")
    else:
        proof_path = Path(str(proof.get("raw_path", "")))
        if not proof_path.is_file() or json.loads(proof_path.read_bytes()) != []:
            errors.append("terminal coverage proof is not an empty raw API page")
        if proof.get("request_end_ms") != end_ms:
            errors.append("terminal coverage proof does not reach requested end")
        if expected_last is not None and proof.get("request_start_ms") != expected_last + 1:
            errors.append("terminal coverage proof does not begin after the last actual event")

    return {
        "qa_status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "raw_file_count": len(raw_files),
        "raw_record_count": len(raw_records),
        "normalized_row_count": len(csv_rows),
        "normalized_sha256": sha256_file(csv_path) if csv_path.is_file() else None,
        "first_funding_time_ms": expected_first,
        "first_funding_time_utc": utc_from_ms(expected_first) if expected_first is not None else None,
        "last_funding_time_ms": expected_last,
        "last_funding_time_utc": utc_from_ms(expected_last) if expected_last is not None else None,
        "duplicate_count": duplicate_count,
        "ordering_violations": ordering_violations,
        **checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_artifacts(args.data_root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["qa_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
