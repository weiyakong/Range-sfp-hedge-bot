from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from research.backtester_v2.models import BacktestConfig, Bar
from research.strategy_replications.production_runner import (
    ProductionRunRequest,
    _load_strategy,
    canonical_bars_sha256,
    run_production_research,
    validate_v2_run_receipt,
)
from research.strategy_replications.tests.test_enforcement import (
    CAPABILITY_PATH,
    REPO_ROOT,
    fixture_files,
    valid_registry,
    write_json,
)
from research.strategy_replications.validation.core import (
    create_freeze_receipt,
    load_json,
    sha256_file,
)


START = 1_577_836_800_000
END = 1_609_459_200_000
PSTART = 1_640_995_200_000
PEND = 1_672_531_200_000


def _fixture(root: Path, *, protected: bool = False, suite_source: Optional[str] = None):
    spec, registry, protocol, data, strategy, freeze_receipt = fixture_files(root)
    start, end = (PSTART, PEND) if protected else (START, END)
    bars = (Bar(start, 100, 100, 100, 100, 1), Bar(end, 100, 100, 100, 100, 1))
    write_json(data, {
        "dataset": "fixture",
        "production_contract": {
            "symbol": "BTCUSDT", "market": "perpetual", "timeframe": "1m",
            "timestamp_semantics": "bar open UTC",
            "bars_sha256": canonical_bars_sha256(bars), "row_count": len(bars),
            "tested_start": start, "tested_end": end,
        },
    })
    strategy.write_text(
        "class MaCrossStrategy:\n"
        "    def __init__(self, fast_length, slow_length):\n"
        "        self.fast_length = fast_length\n"
        "        self.slow_length = slow_length\n"
        "    def on_bar(self, bar, state):\n"
        "        return []\n",
        encoding="utf-8",
    )
    spec_payload = load_json(spec)
    spec_payload["data_manifest"]["sha256"] = sha256_file(data)
    spec_payload["data_inputs"][0]["manifest_sha256"] = sha256_file(data)
    spec_payload["traceability"][0]["implementation_sha256"] = sha256_file(strategy)
    write_json(spec, spec_payload)
    write_json(registry, valid_registry(sha256_file(spec)))
    protocol_payload = load_json(protocol)
    if protected:
        protocol_payload["protected_validation"]["dataset_manifest_sha256"] = sha256_file(data)
    write_json(protocol, protocol_payload)
    suite = root / "test_strategy.py"
    suite.write_text(suite_source or (
        "import unittest\n\n"
        "class StrategyContractTests(unittest.TestCase):\n"
        "    def test_ma_positive(self): self.assertTrue(True)\n"
        "    def test_ma_negative(self): self.assertTrue(True)\n"
        "    def test_ma_boundary(self): self.assertTrue(True)\n"
        "    def test_ma_causality(self): self.assertTrue(True)\n\n"
        "if __name__ == '__main__': unittest.main()\n"
    ),
        encoding="utf-8",
    )
    spec_payload = load_json(spec)
    spec_payload["tests"]["suite_sha256"] = sha256_file(suite)
    write_json(spec, spec_payload)
    write_json(registry, valid_registry(sha256_file(spec)))
    freeze, created = create_freeze_receipt(
        spec_path=spec, registry_path=registry, protocol_path=protocol,
        capability_path=CAPABILITY_PATH, data_manifest_path=data,
        repo_root=REPO_ROOT, receipt_path=freeze_receipt,
        strategy_code_path=strategy,
    )
    if not freeze.ok or created is None:
        raise AssertionError(freeze.render())
    return spec, registry, protocol, data, strategy, freeze_receipt, suite


def _request(root: Path, paths, *, protected: bool = False, output_name: str = "run"):
    spec, registry, protocol, data, strategy, freeze_receipt, suite = paths
    start, end = (PSTART, PEND) if protected else (START, END)
    return ProductionRunRequest(
        repo_root=REPO_ROOT, spec_path=spec, registry_path=registry,
        protocol_path=protocol, data_manifest_path=data,
        freeze_receipt_path=freeze_receipt, strategy_code_path=strategy,
        strategy_test_suite_path=suite,
        bars=(Bar(start, 100, 100, 100, 100, 1), Bar(end, 100, 100, 100, 100, 1)),
        config=BacktestConfig(),
        run_stage="PROTECTED_VALIDATION" if protected else "COMPARISON",
        output_dir=root / output_name, symbol="BTCUSDT", market="perpetual",
        timeframe="1m", strategy_name="fixture", source_reference="Fixture source",
    )


class AtomicProductionRunnerTests(unittest.TestCase):
    def _patches(self, state_path: Path):
        return (
            patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]),
            patch("research.backtester_v2.output._material_dirty_paths", return_value=[]),
            patch("research.strategy_replications.production_runner._state_path", return_value=state_path),
        )

    def _run(self, request, state_path):
        p1, p2, p3 = self._patches(state_path)
        with p1, p2, p3:
            return run_production_research(request)

    def _validate(self, output, state_path):
        with patch("research.strategy_replications.production_runner._state_path", return_value=state_path):
            return validate_v2_run_receipt(output_dir=output, repo_root=REPO_ROOT)

    def test_atomic_runner_produces_revalidatable_v2_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            self.assertTrue(outcome.receipt_path.is_file())
            self.assertEqual(outcome.receipt_sha256, sha256_file(outcome.receipt_path))
            report = self._validate(outcome.output_dir, state)
            self.assertTrue(report.ok, report.render())
            attestation = load_json(outcome.output_dir / "execution_attestation.json")
            self.assertEqual(attestation["bar_count"], 2)
            self.assertEqual(attestation["actual_start"], START)
            self.assertEqual(attestation["actual_end"], END)

    def test_actual_bar_window_not_declared_window_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            request = _request(root, paths)
            request = ProductionRunRequest(**{
                **request.__dict__,
                "bars": (Bar(0,100,100,100,100,1), Bar(60_000,100,100,100,100,1)),
            })
            with self.assertRaises(ValueError):
                self._run(request, state)
            self.assertFalse(request.output_dir.exists())

    def test_actual_config_mismatch_is_rejected_before_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            request = _request(root, paths)
            request = ProductionRunRequest(**{
                **request.__dict__, "config": BacktestConfig(slippage_rate=.01),
            })
            with self.assertRaises(ValueError):
                self._run(request, state)

    def test_non_protocol_config_field_is_also_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            request = _request(root, paths)
            request = ProductionRunRequest(**{
                **request.__dict__, "config": BacktestConfig(initial_cash=123_456.0),
            })
            with self.assertRaisesRegex(ValueError, "differs from frozen strategy spec"):
                self._run(request, state)
            self.assertFalse(request.output_dir.exists())

    def test_actual_ohlcv_values_must_match_data_manifest_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            request = _request(root, paths)
            request = ProductionRunRequest(**{
                **request.__dict__,
                "bars": (
                    Bar(START, 100, 100, 100, 100, 1),
                    Bar(END, 101, 101, 101, 101, 1),
                ),
            })
            with self.assertRaisesRegex(ValueError, "actual bars differ"):
                self._run(request, state)
            self.assertFalse(request.output_dir.exists())

    def test_data_contract_symbol_and_timeframe_are_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            for field, value in (("symbol", "ETHUSDT"), ("timeframe", "17m")):
                with self.subTest(field=field):
                    request = _request(root, paths, output_name=f"run-{field}")
                    request = ProductionRunRequest(**{**request.__dict__, field: value})
                    with self.assertRaises(ValueError):
                        self._run(request, state)

    def test_test_suite_must_match_frozen_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            paths[-1].write_text(
                "import unittest\n"
                "class Broken(unittest.TestCase):\n"
                "    def test_ma_positive(self): self.fail('real failure')\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                self._run(_request(root, paths), state)

    def test_frozen_suite_must_really_execute_required_test_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / "state.sqlite3"
            paths = _fixture(root, suite_source=(
                "import unittest\n\n"
                "class StrategyContractTests(unittest.TestCase):\n"
                "    def test_ma_positive(self): self.fail('real failure')\n"
                "    def test_ma_negative(self): self.assertTrue(True)\n"
                "    def test_ma_boundary(self): self.assertTrue(True)\n"
                "    def test_ma_causality(self): self.assertTrue(True)\n"
            ))
            with self.assertRaisesRegex(ValueError, "executed PASS evidence"):
                self._run(_request(root, paths), state)

    def test_semantic_output_mutation_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            trades = outcome.output_dir / "trades.csv"
            trades.write_text("not,a,trade\nFAKE\n", encoding="utf-8")
            manifest = load_json(outcome.output_dir / "manifest.json")
            manifest["checksums"]["trades.csv"] = sha256_file(trades)
            write_json(outcome.output_dir / "manifest.json", manifest)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("trades.csv" in item for item in report.errors))

    def test_malformed_json_returns_fail_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            attestation = outcome.output_dir / "execution_attestation.json"
            attestation.write_text("{broken", encoding="utf-8")
            manifest = load_json(outcome.output_dir / "manifest.json")
            manifest["checksums"]["execution_attestation.json"] = sha256_file(attestation)
            write_json(outcome.output_dir / "manifest.json", manifest)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("cannot parse" in item for item in report.errors))

    def test_stage_and_qa_posthoc_upgrade_invalidate_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            metadata_path = outcome.output_dir / "run_metadata.json"
            metadata = load_json(metadata_path)
            metadata["run_stage"] = "ADAPTATION_VALIDATION"
            metadata["qa_dimensions"]["causality_assurance"] = "TESTED"
            write_json(metadata_path, metadata)
            manifest = load_json(outcome.output_dir / "manifest.json")
            manifest["checksums"]["run_metadata.json"] = sha256_file(metadata_path)
            write_json(outcome.output_dir / "manifest.json", manifest)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            joined = "\n".join(report.errors)
            self.assertIn("run_stage", joined)
            self.assertIn("qa_dimensions", joined)

    def test_symlinked_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            trades = outcome.output_dir / "trades.csv"
            external = root / "external.csv"; external.write_bytes(trades.read_bytes())
            trades.unlink(); trades.symlink_to(external)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("symlink" in item for item in report.errors))

    def test_canonical_state_is_required_for_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            state.unlink()
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("canonical_state" in item for item in report.errors))
            self.assertFalse(state.exists(), "validation must not recreate missing authority state")

    def test_upstream_strategy_change_invalidates_historical_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            strategy = paths[4]
            strategy.write_text(strategy.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("upstream_files.strategy_code" in item for item in report.errors))

    def test_receipt_mutation_is_rejected_by_canonical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            receipt = load_json(outcome.receipt_path)
            receipt["created_at_utc"] = "2099-01-01T00:00:00+00:00"
            write_json(outcome.receipt_path, receipt)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any("canonical_state" in item for item in report.errors))

    def test_protected_use_is_unique_across_output_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root, protected=True); state = root / "state.sqlite3"
            first = self._run(_request(root, paths, protected=True, output_name="first"), state)
            self.assertTrue(self._validate(first.output_dir, state).ok)
            with self.assertRaises(Exception):
                self._run(_request(root, paths, protected=True, output_name="second"), state)
            self.assertFalse((root / "second").exists())

    def test_caller_cannot_supply_result_strategy_or_run_id(self):
        fields = set(ProductionRunRequest.__dataclass_fields__)
        self.assertNotIn("result", fields)
        self.assertNotIn("strategy", fields)
        self.assertNotIn("strategy_symbol", fields)
        self.assertNotIn("run_id", fields)
        self.assertNotIn("state_path", fields)

    def test_frozen_symbol_not_alternate_class_in_same_file_is_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            strategy = paths[4]
            freeze_receipt = paths[5]
            freeze_receipt.unlink()
            (root / "receipt_index.json").unlink()
            strategy.write_text(
                strategy.read_text(encoding="utf-8")
                + "\nclass AlternateStrategy:\n"
                + "    def __init__(self, fast_length, slow_length): pass\n"
                + "    def on_bar(self, bar, state):\n"
                + "        from research.backtester_v2.models import OrderIntent\n"
                + "        return [OrderIntent.market('long', 1.0)]\n",
                encoding="utf-8",
            )
            spec = load_json(paths[0])
            spec["traceability"][0]["implementation_sha256"] = sha256_file(strategy)
            write_json(paths[0], spec)
            write_json(paths[1], valid_registry(sha256_file(paths[0])))
            report, created = create_freeze_receipt(
                spec_path=paths[0], registry_path=paths[1], protocol_path=paths[2],
                capability_path=CAPABILITY_PATH, data_manifest_path=paths[3],
                repo_root=REPO_ROOT, receipt_path=freeze_receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(report.ok, report.render())
            self.assertIsNotNone(created)
            outcome = self._run(_request(root, paths), state)
            result = load_json(outcome.output_dir / "result.json")
            attestation = load_json(outcome.output_dir / "execution_attestation.json")
            self.assertEqual(attestation["strategy_symbol"], "MaCrossStrategy")
            self.assertEqual(result["open_positions"], {})

    def test_strategy_loader_executes_captured_bytes_not_reread_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strategy.py"
            path.write_text(
                "class Locked:\n"
                "    def __init__(self, value): self.value = value\n"
                "    def on_bar(self, bar, state): return ['locked']\n",
                encoding="utf-8",
            )
            captured = path.read_bytes()
            path.write_text(
                "class Locked:\n"
                "    def __init__(self, value): self.value = value\n"
                "    def on_bar(self, bar, state): return ['replaced']\n",
                encoding="utf-8",
            )
            loaded = _load_strategy(captured, path, "Locked", {"value": 1})
            self.assertEqual(loaded.on_bar(None, None), ["locked"])

    def test_attested_strategy_symbol_mutation_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); paths = _fixture(root); state = root / "state.sqlite3"
            outcome = self._run(_request(root, paths), state)
            attestation_path = outcome.output_dir / "execution_attestation.json"
            attestation = load_json(attestation_path)
            attestation["strategy_symbol"] = "AlternateStrategy"
            write_json(attestation_path, attestation)
            manifest_path = outcome.output_dir / "manifest.json"
            manifest = load_json(manifest_path)
            manifest["checksums"]["execution_attestation.json"] = sha256_file(attestation_path)
            write_json(manifest_path, manifest)
            report = self._validate(outcome.output_dir, state)
            self.assertFalse(report.ok)
            self.assertTrue(any(
                "execution_attestation.strategy_symbol" in item
                for item in report.errors
            ))


if __name__ == "__main__":
    unittest.main()
