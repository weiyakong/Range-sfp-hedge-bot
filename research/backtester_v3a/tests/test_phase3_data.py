from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.backtester_v3a.contracts import ContractError, parse_strategy_spec_v2
from research.backtester_v3a.data import (
    InputContractLocators,
    ResolutionError,
    resolve_execution_inputs,
)
from research.backtester_v3a.tests.phase3_support import (
    build_input_contracts,
    strategy_spec_payload,
    write_json,
)


class GenericInputResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def resolve(self, paths=None, *, symbol: str = "BTCUSDT"):
        if paths is None:
            paths = build_input_contracts(self.root, symbol=symbol)
        spec = parse_strategy_spec_v2(strategy_spec_payload(paths, symbol=symbol))
        locators = InputContractLocators(
            trade_price=paths["trade_price"],
            funding=paths["funding"],
            mark_price=paths["mark_price"],
            instrument_metadata=paths["instrument_metadata"],
        )
        return resolve_execution_inputs(
            spec,
            locators,
            required_start_ms=0,
            required_end_ms=120_000,
        )

    def test_resolves_trade_funding_mark_and_metadata(self) -> None:
        resolved = self.resolve()
        self.assertEqual(resolved.bound.execution_identity.symbol, "BTCUSDT")
        self.assertEqual(len(resolved.bars), 3)
        self.assertEqual(resolved.funding_rate_by_time, {120_000: 0.001})
        self.assertEqual(resolved.funding_price_by_time, {120_000: 102.0})
        self.assertEqual(resolved.bars[0].mark_open, 100.0)
        self.assertEqual(resolved.metadata.symbol, "BTCUSDT")

    def test_phase3_versioned_schemas_are_checked_in(self) -> None:
        schema_root = Path("research/backtester_v3a/schemas")
        self.assertTrue((schema_root / "data_manifest_v1.schema.json").is_file())
        self.assertTrue((schema_root / "output_manifest_v1.schema.json").is_file())
        self.assertTrue((schema_root / "result_v1.schema.json").is_file())

    def test_locator_interface_has_no_symbol_override(self) -> None:
        self.assertNotIn("symbol", InputContractLocators.__dataclass_fields__)

    def test_trade_symbol_mismatch_is_hard_failure(self) -> None:
        paths = build_input_contracts(self.root, symbol="ETHUSDT")
        with self.assertRaisesRegex(ContractError, "symbol"):
            self.resolve(paths, symbol="BTCUSDT")

    def test_funding_symbol_mismatch_is_hard_failure(self) -> None:
        btc = build_input_contracts(self.root / "btc", symbol="BTCUSDT")
        eth = build_input_contracts(self.root / "eth", symbol="ETHUSDT")
        btc["funding"] = eth["funding"]
        spec_paths = dict(btc)
        spec = parse_strategy_spec_v2(strategy_spec_payload(spec_paths))
        locators = InputContractLocators(
            trade_price=btc["trade_price"], funding=btc["funding"],
            mark_price=btc["mark_price"],
            instrument_metadata=btc["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "funding.symbol"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_mark_symbol_mismatch_is_hard_failure(self) -> None:
        btc = build_input_contracts(self.root / "btc", symbol="BTCUSDT")
        sol = build_input_contracts(self.root / "sol", symbol="SOLUSDT")
        btc["mark_price"] = sol["mark_price"]
        spec = parse_strategy_spec_v2(strategy_spec_payload(btc))
        locators = InputContractLocators(
            trade_price=btc["trade_price"], funding=btc["funding"],
            mark_price=btc["mark_price"],
            instrument_metadata=btc["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "mark_price.symbol"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_metadata_symbol_mismatch_is_hard_failure(self) -> None:
        btc = build_input_contracts(self.root / "btc", symbol="BTCUSDT")
        eth = build_input_contracts(self.root / "eth", symbol="ETHUSDT")
        btc["instrument_metadata"] = eth["instrument_metadata"]
        spec = parse_strategy_spec_v2(strategy_spec_payload(btc))
        locators = InputContractLocators(
            trade_price=btc["trade_price"], funding=btc["funding"],
            mark_price=btc["mark_price"],
            instrument_metadata=btc["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "instrument_metadata.symbol"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_required_funding_missing_is_hard_failure(self) -> None:
        paths = build_input_contracts(self.root)
        spec = parse_strategy_spec_v2(strategy_spec_payload(paths))
        locators = InputContractLocators(
            trade_price=paths["trade_price"], funding=None,
            mark_price=paths["mark_price"],
            instrument_metadata=paths["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "funding.*required"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_required_mark_missing_is_not_replaced_by_trade_price(self) -> None:
        paths = build_input_contracts(self.root)
        spec = parse_strategy_spec_v2(strategy_spec_payload(paths))
        locators = InputContractLocators(
            trade_price=paths["trade_price"], funding=paths["funding"],
            mark_price=None,
            instrument_metadata=paths["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "mark_price.*required"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_manifest_hash_mismatch_fails(self) -> None:
        paths = build_input_contracts(self.root)
        contract = json.loads(paths["trade_price"].read_text(encoding="utf-8"))
        manifest = Path(contract["manifest_path"])
        manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(ResolutionError, "manifest SHA-256"):
            self.resolve(paths)

    def test_dataset_hash_mismatch_fails(self) -> None:
        paths = build_input_contracts(self.root)
        contract = json.loads(paths["trade_price"].read_text(encoding="utf-8"))
        manifest = json.loads(Path(contract["manifest_path"]).read_text(encoding="utf-8"))
        Path(manifest["data_path"]).write_text("corrupt\n", encoding="utf-8")
        with self.assertRaisesRegex(ResolutionError, "data SHA-256"):
            self.resolve(paths)

    def test_coverage_mismatch_fails(self) -> None:
        paths = build_input_contracts(self.root)
        contract_path = paths["trade_price"]
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        payload["coverage_end_ms"] = 60_000
        write_json(contract_path, payload)
        spec = parse_strategy_spec_v2(strategy_spec_payload(paths))
        locators = InputContractLocators(
            trade_price=paths["trade_price"], funding=paths["funding"],
            mark_price=paths["mark_price"],
            instrument_metadata=paths["instrument_metadata"],
        )
        with self.assertRaisesRegex(ContractError, "coverage"):
            resolve_execution_inputs(spec, locators, 0, 120_000)

    def test_metadata_provenance_hash_mismatch_fails(self) -> None:
        paths = build_input_contracts(self.root)
        metadata = json.loads(paths["instrument_metadata"].read_text(encoding="utf-8"))
        source = Path(metadata["provenance"]["source"])
        source.write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ResolutionError, "metadata provenance"):
            self.resolve(paths)
