from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Mapping


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from collect_binance_funding import (  # noqa: E402
    CollectorConfig,
    collect_funding,
    finalize,
    load_raw_records,
    normalize_and_validate,
    sha256_file,
)


class FakeFetcher:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = list(responses)
        self.calls: list[Mapping[str, str]] = []

    def __call__(self, params: Mapping[str, str]) -> bytes:
        self.calls.append(dict(params))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def response(*rows: dict[str, object]) -> bytes:
    return json.dumps(rows, separators=(",", ":")).encode("utf-8")


class BinanceFundingCollectorTests(unittest.TestCase):
    def config(self, root: Path, *, start_ms: int = 1_000, end_ms: int = 5_000) -> CollectorConfig:
        return CollectorConfig(
            data_root=root,
            repo_root=Path(__file__).resolve().parents[3],
            symbol="BTCUSDT",
            requested_start_ms=start_ms,
            requested_end_ms=end_ms,
            source_manifest_path=root / "manifests" / "strict_futures_1m_manifest.json",
            limit=2,
        )

    def test_paginates_after_last_actual_timestamp_and_proves_tail_with_empty_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fetcher = FakeFetcher(
                [
                    response(
                        {"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.00010000", "markPrice": "10.50000000"},
                        {"symbol": "BTCUSDT", "fundingTime": 3_000, "fundingRate": "-0.00020000", "markPrice": "11.00000000"},
                    ),
                    response(
                        {"symbol": "BTCUSDT", "fundingTime": 4_000, "fundingRate": "0.00000000", "markPrice": "12.00000000"}
                    ),
                    response(),
                ]
            )

            result = collect_funding(self.config(root), fetcher=fetcher)

            self.assertTrue(result.complete)
            self.assertEqual([c["startTime"] for c in fetcher.calls], ["1000", "3001", "4001"])
            pages = sorted((root / "raw/binance/usdt_m/BTCUSDT/funding_rate/api/pages").glob("*.json"))
            self.assertEqual([p.read_bytes() for p in pages], [
                response(
                    {"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.00010000", "markPrice": "10.50000000"},
                    {"symbol": "BTCUSDT", "fundingTime": 3_000, "fundingRate": "-0.00020000", "markPrice": "11.00000000"},
                ),
                response(
                    {"symbol": "BTCUSDT", "fundingTime": 4_000, "fundingRate": "0.00000000", "markPrice": "12.00000000"}
                ),
                response(),
            ])

    def test_completed_checkpoint_makes_rerun_network_free_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = FakeFetcher(
                [
                    response({"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.1", "markPrice": "9.25"}),
                    response(),
                ]
            )
            config = self.config(root)
            collect_funding(config, fetcher=first)

            second = FakeFetcher([])
            rerun = collect_funding(config, fetcher=second)
            records = load_raw_records(config)

            self.assertTrue(rerun.complete)
            self.assertEqual(second.calls, [])
            self.assertEqual(len(records), 1)

    def test_normalized_csv_preserves_decimal_text_and_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(root)
            fetcher = FakeFetcher(
                [
                    response(
                        {"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.00010000", "markPrice": "10.50000000"},
                        {"symbol": "BTCUSDT", "fundingTime": 3_000, "fundingRate": "0.00000000", "markPrice": "10.00000001"},
                    ),
                    response(),
                ]
            )
            collect_funding(config, fetcher=fetcher)

            report1 = normalize_and_validate(config)
            first_bytes = config.normalized_path.read_bytes()
            report2 = normalize_and_validate(config)
            second_bytes = config.normalized_path.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(report1.normalized_sha256, report2.normalized_sha256)
            self.assertEqual(hashlib.sha256(first_bytes).hexdigest(), report1.normalized_sha256)
            text = first_bytes.decode("utf-8")
            self.assertIn(",0.00010000,10.50000000\n", text)
            self.assertIn(",0.00000000,10.00000001\n", text)
            self.assertEqual(report1.zero_rate_count, 1)

    def test_validation_reports_duplicates_ordering_and_non_modal_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(root, start_ms=0, end_ms=3_600_000)
            page_dir = config.raw_pages_dir
            page_dir.mkdir(parents=True)
            raw = response(
                {"symbol": "BTCUSDT", "fundingTime": 600_000, "fundingRate": "0.1", "markPrice": "1"},
                {"symbol": "BTCUSDT", "fundingTime": 1_800_000, "fundingRate": "0.3", "markPrice": "3"},
                {"symbol": "BTCUSDT", "fundingTime": 1_200_000, "fundingRate": "0.2", "markPrice": "2"},
                {"symbol": "BTCUSDT", "fundingTime": 1_200_000, "fundingRate": "0.2", "markPrice": "2"},
                {"symbol": "BTCUSDT", "fundingTime": 3_000_000, "fundingRate": "0.4", "markPrice": "4"},
            )
            (page_dir / "page-000001-start-0-end-3600000.json").write_bytes(raw)

            report = normalize_and_validate(config)

            self.assertEqual(report.duplicate_count, 1)
            self.assertEqual(report.ordering_violations, 1)
            self.assertEqual(report.interval_distribution_ms, {600_000: 2, 1_200_000: 1})
            self.assertEqual(len(report.unusual_intervals), 1)
            self.assertEqual(report.unusual_intervals[0]["delta_ms"], 1_200_000)

    def test_repeated_page_is_rejected_instead_of_looping_forever(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repeated = response(
                {"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.1", "markPrice": "1"},
            )
            with self.assertRaisesRegex(RuntimeError, "did not advance"):
                collect_funding(self.config(root), fetcher=FakeFetcher([repeated, repeated]))

    def test_manifest_hashes_raw_normalized_and_checksum_hashes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.config(root)
            config.source_manifest_path.parent.mkdir(parents=True)
            config.source_manifest_path.write_text("{}\n", encoding="utf-8")
            collection = collect_funding(
                config,
                fetcher=FakeFetcher(
                    [
                        response(
                            {"symbol": "BTCUSDT", "fundingTime": 2_000, "fundingRate": "0.00010000", "markPrice": "10.50000000"}
                        ),
                        response(),
                    ]
                ),
            )

            manifest = finalize(config, collection)

            self.assertEqual(manifest["qa_status"], "PASS")
            raw_files = manifest["raw_files"]
            self.assertEqual(len(raw_files), 2)
            self.assertTrue(all(item["sha256"] for item in raw_files))
            self.assertEqual(manifest["normalized_file"]["sha256"], sha256_file(config.normalized_path))
            expected = f"{sha256_file(config.manifest_path)}  funding_manifest.json\n"
            self.assertEqual(config.checksums_path.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
