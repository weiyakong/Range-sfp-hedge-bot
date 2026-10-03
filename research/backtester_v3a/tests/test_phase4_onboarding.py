from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from research.backtester_v3a.contracts import (
    INSTRUMENT_METADATA_SCHEMA_V2,
    ContractError,
    canonical_sha256,
    parse_instrument_metadata,
)
from research.backtester_v3a.onboarding.binance_usdm import (
    ArchivePlan,
    FundingRecord,
    OnboardingPaths,
    PriceRow,
    atomic_checkpoint,
    archive_timestamp_ms,
    canonical_project_end,
    extract_instrument_metadata,
    parse_official_checksum,
    plan_price_archives,
    qa_funding_records,
    qa_price_rows,
    read_checkpoint,
)
from research.backtester_v3a.onboarding.collect_real_symbols import (
    PriceSource,
    archive_window,
    iter_price_source,
)


class Phase4LayoutTests(unittest.TestCase):
    def test_approved_symbol_aware_layout(self) -> None:
        root = Path("/data")
        paths = OnboardingPaths(root, "ETHUSDT")
        self.assertEqual(
            paths.trade_raw,
            root / "raw/binance/usdt_m/ETHUSDT/1m",
        )
        self.assertEqual(
            paths.funding_raw,
            root / "raw/binance/usdt_m/ETHUSDT/funding_rate",
        )
        self.assertEqual(
            paths.mark_raw,
            root / "raw/binance/usdt_m/ETHUSDT/mark_price/1m",
        )
        self.assertEqual(
            paths.metadata_raw,
            root / "raw/binance/usdt_m/ETHUSDT/instrument_metadata",
        )
        self.assertEqual(
            paths.trade_manifest,
            root / "manifests/binance/usdt_m/ETHUSDT/1m",
        )
        self.assertEqual(
            paths.mark_manifest,
            root / "manifests/binance/usdt_m/ETHUSDT/mark_price/1m",
        )

    def test_canonical_end_is_read_from_btc_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps({
                "dataset": {"strict_end_utc": "2024-02-03T04:05:00Z"},
            }), encoding="utf-8")
            end = canonical_project_end(path)
        self.assertEqual(end.isoformat(), "2024-02-03T04:05:00+00:00")

    def test_archive_plan_uses_monthly_daily_and_api_tail(self) -> None:
        plan = plan_price_archives(
            symbol="SOLUSDT",
            category="klines",
            actual_start=datetime(2020, 9, 14, tzinfo=timezone.utc),
            project_end=datetime(2026, 9, 25, 23, 59, tzinfo=timezone.utc),
        )
        self.assertIsInstance(plan, ArchivePlan)
        self.assertEqual(plan.monthly[0].name, "SOLUSDT-1m-2020-09.zip")
        self.assertEqual(plan.monthly[-1].name, "SOLUSDT-1m-2026-08.zip")
        self.assertEqual(plan.daily[0].name, "SOLUSDT-1m-2026-09-01.zip")
        self.assertEqual(plan.daily[-1].name, "SOLUSDT-1m-2026-09-24.zip")
        self.assertEqual(plan.api_start_ms, 1790294400000)
        self.assertEqual(plan.api_end_ms, 1790380740000)

    def test_checkpoint_roundtrip_is_immediate_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "checkpoint.json"
            atomic_checkpoint(path, {"schema_version": "TEST", "completed": ["a"]})
            self.assertEqual(read_checkpoint(path)["completed"], ["a"])

    def test_official_checksum_is_strictly_bound_to_archive_name(self) -> None:
        digest = "a" * 64
        self.assertEqual(
            parse_official_checksum(
                f"{digest}  ETHUSDT-1m-2020-01.zip\n".encode(),
                "ETHUSDT-1m-2020-01.zip",
            ),
            digest,
        )
        with self.assertRaises(ValueError):
            parse_official_checksum(
                f"{digest}  SOLUSDT-1m-2020-01.zip\n".encode(),
                "ETHUSDT-1m-2020-01.zip",
            )

    def test_archive_timestamp_unit_is_explicitly_normalized(self) -> None:
        self.assertEqual(archive_timestamp_ms("1600000000000"), 1600000000000)
        self.assertEqual(archive_timestamp_ms("1600000000000000"), 1600000000000)
        with self.assertRaises(ValueError):
            archive_timestamp_ms("1600000000000001")

    def test_archive_window_is_exact_and_inclusive(self) -> None:
        item = plan_price_archives(
            symbol="ETHUSDT",
            category="klines",
            actual_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            project_end=datetime(2020, 2, 2, 23, 59, tzinfo=timezone.utc),
        ).monthly[0]
        self.assertEqual(archive_window(item), (1577836800000, 1580515140000))

    def test_official_archive_header_and_microseconds_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ETHUSDT-1m-2025-01.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "ETHUSDT-1m-2025-01.csv",
                    "open_time,open,high,low,close,volume\n"
                    "1735689600000000,100,101,99,100.5,12\n",
                )
            rows = list(iter_price_source(
                PriceSource("archive", path, "official"),
                role="trade_price",
            ))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0].open_time_ms, 1735689600000)
        self.assertTrue(rows[0][1])


class Phase4QATests(unittest.TestCase):
    def test_price_qa_reports_real_integrity_failures(self) -> None:
        rows = [
            PriceRow(0, "10", "11", "9", "10", "1"),
            PriceRow(120_000, "10", "8", "9", "10", "-1"),
            PriceRow(120_000, "10", "11", "9", "10", "1"),
            PriceRow(180_000, "10", "11", "9", "10", "1"),
            PriceRow(180_001, "10", "11", "9", "10", "1"),
        ]
        report = qa_price_rows(rows, requested_start_ms=0, requested_end_ms=180_000)
        self.assertEqual(report.duplicate_count, 1)
        self.assertEqual(report.off_grid_count, 1)
        self.assertEqual(report.bad_ohlc_count, 1)
        self.assertEqual(report.negative_volume_count, 1)
        self.assertEqual(report.missing_ranges, ((60_000, 60_000, 1),))
        self.assertEqual(report.out_of_window_count, 1)

    def test_funding_qa_preserves_millisecond_offsets(self) -> None:
        records = [
            FundingRecord("ETHUSDT", 28_800_002, "0.0001", "100"),
            FundingRecord("ETHUSDT", 57_600_017, "0", None),
        ]
        report = qa_funding_records(
            records,
            symbol="ETHUSDT",
            requested_start_ms=0,
            requested_end_ms=60_000_000,
        )
        self.assertEqual(report.offset_distribution_ms, {2: 1, 17: 1})
        self.assertEqual(report.zero_rate_count, 1)
        self.assertEqual(report.missing_mark_price_count, 1)
        self.assertEqual(report.duplicate_count, 0)


class MetadataV2Tests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "schema_version": INSTRUMENT_METADATA_SCHEMA_V2,
            "exchange": "Binance",
            "market": "USD-M perpetual",
            "symbol": "ETHUSDT",
            "metadata_id": "ETHUSDT-2026-10-03",
            "collected_at_utc": "2026-10-03T12:00:00Z",
            "tick_size": "0.01",
            "step_size": "0.001",
            "min_qty": "0.001",
            "min_notional": "5",
            "price_precision": 2,
            "quantity_precision": 3,
            "provenance": {
                "fidelity_classification": "STATIC_CURRENT_PROXY",
                "source": "/data/raw/exchangeInfo.json",
                "source_sha256": "a" * 64,
                "effective_start_ms": None,
                "effective_end_ms": None,
            },
        }

    def test_metadata_v2_requires_and_roundtrips_collection_time(self) -> None:
        payload = self.payload()
        metadata = parse_instrument_metadata(payload)
        self.assertEqual(metadata.collected_at_utc, "2026-10-03T12:00:00Z")
        self.assertEqual(metadata.to_payload(), payload)
        self.assertEqual(metadata.contract_sha256, canonical_sha256(payload))

    def test_metadata_v2_rejects_missing_collection_time(self) -> None:
        payload = self.payload()
        del payload["collected_at_utc"]
        with self.assertRaises(ContractError):
            parse_instrument_metadata(payload)

    def test_exchange_info_filters_become_current_proxy_not_history(self) -> None:
        payload = {
            "symbols": [{
                "symbol": "ETHUSDT",
                "contractType": "PERPETUAL",
                "onboardDate": 1598572800000,
                "pricePrecision": 2,
                "quantityPrecision": 3,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0.001",
                        "minQty": "0.001",
                    },
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            }],
        }
        contract = extract_instrument_metadata(
            payload,
            symbol="ETHUSDT",
            collected_at_utc="2026-10-03T12:00:00Z",
            source_path=Path("/data/raw/exchangeInfo.json"),
            source_sha256="b" * 64,
        )
        self.assertEqual(contract["tick_size"], "0.01")
        self.assertEqual(contract["step_size"], "0.001")
        self.assertEqual(contract["min_notional"], "5")
        self.assertEqual(
            contract["provenance"]["fidelity_classification"],
            "STATIC_CURRENT_PROXY",
        )
        self.assertIsNone(contract["provenance"]["effective_start_ms"])
