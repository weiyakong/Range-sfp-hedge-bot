from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import BacktestConfig, Bar, ReplicationLineage
from research.backtester_v2.output import build_run_metadata, write_results
from research.strategy_replications.tests.test_enforcement import (
    CAPABILITY_PATH,
    HASH_A,
    NoopStrategy,
    REPO_ROOT,
    fixture_files,
    valid_protocol,
    valid_registry,
    valid_spec,
    write_json,
)
from research.strategy_replications.validation.core import (
    compute_fidelity_summary,
    create_freeze_receipt,
    create_production_preflight_context,
    load_json,
    sha256_file,
    validate_capability_manifest,
    validate_candidate_registry,
    validate_evaluation_protocol,
    validate_freeze_inputs,
    validate_freeze_receipt,
    validate_production_preflight,
    validate_run_lineage,
    validate_strategy_spec,
    validate_test_manifest_and_traceability,
)


MANDATORY_FIXED_ATTACKS = {
    "A09", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17",
    "A32", "A33", "A34", "A35", "A36", "A37", "A38", "A39", "A40",
    "A41", "A42", "A43", "A45", "A46", "A47", "A49", "A50", "A51",
    "A52", "A53", "A54", "A56", "A57", "A59", "A61", "A62", "A63",
    "A64", "A65", "A66", "A67", "A68", "A69", "A70",
}


class StructuralAttackRegressions(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = load_json(CAPABILITY_PATH)

    def test_A09_A10_A11_source_range_bounds_and_time(self) -> None:
        cases = []
        outside = valid_spec(HASH_A)
        outside["parameters"][0] = {
            "parameter_id": "fast_length", "value": 30, "units": "bars",
            "origin": "SOURCE_RANGE", "source_range": {"minimum": 5, "maximum": 20},
            "selection": {"method": "source midpoint", "rationale": "declared",
                          "selected_at_utc": "2026-01-01T00:00:00Z",
                          "selected_before_historical_results": True},
        }
        cases.append(outside)
        inverted = copy.deepcopy(outside)
        inverted["parameters"][0]["value"] = 10
        inverted["parameters"][0]["source_range"] = {"minimum": 20, "maximum": 5}
        cases.append(inverted)
        future = copy.deepcopy(outside)
        future["parameters"][0]["value"] = 10
        future["parameters"][0]["selection"]["selected_at_utc"] = "2099-01-01T00:00:00Z"
        cases.append(future)
        for spec in cases:
            with self.subTest(spec=spec["parameters"][0]):
                self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_A12_proxy_contract_is_bidirectional(self) -> None:
        spec = valid_spec(HASH_A)
        spec["fidelity"]["execution"] = "PROXY"
        spec["fidelity"]["declared_summary"] = "ADAPTED"
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)
        spec["proxy"] = {
            "used": True, "original_behavior": "stop entry",
            "replacement_behavior": "next open", "rationale": "unsupported",
            "impact": "timing changes", "classification_consequence": "ADAPTED",
        }
        self.assertTrue(validate_strategy_spec(spec, self.capability).ok)

    def test_A13_A15_A17_state_trace_and_exit_contracts(self) -> None:
        empty = valid_spec(HASH_A)
        empty["state_model"]["reachable_pairs"] = []
        empty["state_model"]["decisions"] = []
        self.assertFalse(validate_strategy_spec(empty, self.capability).ok)
        duplicate = valid_spec(HASH_A)
        duplicate["traceability"].append(copy.deepcopy(duplicate["traceability"][0]))
        self.assertFalse(validate_strategy_spec(duplicate, self.capability).ok)
        contradiction = valid_spec(HASH_A)
        contradiction["exit_precedence"] = [
            "STRATEGY_EXIT_NEXT_OPEN", "LIQUIDATION_ENGINE_CONTROLLED",
        ]
        self.assertFalse(validate_strategy_spec(contradiction, self.capability).ok)

    def test_A16_A32_A33_A34_cross_document_integrity(self) -> None:
        spec = valid_spec(HASH_A)
        registry = valid_registry(HASH_A)
        protocol = valid_protocol()
        spec["data_inputs"][0]["manifest_sha256"] = "b" * 64
        self.assertFalse(validate_freeze_inputs(spec, registry, protocol, self.capability, REPO_ROOT, HASH_A).ok)
        spec = valid_spec(HASH_A)
        registry = valid_registry(HASH_A)
        registry["candidates"][0]["intake_timestamp_utc"] = "2027-01-01T00:00:00Z"
        self.assertFalse(validate_freeze_inputs(spec, registry, protocol, self.capability, REPO_ROOT, HASH_A).ok)
        registry = valid_registry(HASH_A)
        registry["candidates"][0]["primary_source_id"] = "FORGED"
        self.assertFalse(validate_freeze_inputs(spec, registry, protocol, self.capability, REPO_ROOT, HASH_A).ok)
        registry = valid_registry(HASH_A)
        registry["variants"][0]["type"] = "ADAPTED"
        self.assertFalse(validate_freeze_inputs(spec, registry, protocol, self.capability, REPO_ROOT, HASH_A).ok)

    def test_A35_A36_A37_A38_A39_A40_A41_protocol_values(self) -> None:
        for weights in (
            {"total_return": -0.2, "sharpe": 1.2},
            {"total_return": "1"},
            {"total_return": 0.4, "sharpe": 0.4},
        ):
            protocol = valid_protocol()
            protocol["ranking"] = {"method": "WEIGHTED", "weights": weights}
            self.assertFalse(validate_evaluation_protocol(protocol).ok)
        duplicate = valid_protocol()
        duplicate["metrics"].append(copy.deepcopy(duplicate["metrics"][0]))
        self.assertFalse(validate_evaluation_protocol(duplicate).ok)
        unknown = valid_protocol()
        unknown["metrics"][0]["name"] = "magic_alpha"
        self.assertFalse(validate_evaluation_protocol(unknown).ok)
        for name, value in (("maker_fee", -0.01), ("taker_fee", math.nan), ("slippage", 1.0)):
            protocol = valid_protocol()
            protocol["execution_assumptions"][name]["value"] = value
            self.assertFalse(validate_evaluation_protocol(protocol).ok)

    def test_A42_A43_protected_and_ranking_identity_are_frozen(self) -> None:
        protocol = valid_protocol()
        protocol["protected_validation"]["finalist_variant_ids"].append("POST_HOC")
        self.assertFalse(validate_evaluation_protocol(protocol).ok)

    def test_registry_predecessor_cannot_silently_remove_identity(self) -> None:
        predecessor = valid_registry(HASH_A)
        current = copy.deepcopy(predecessor)
        current["registry_version"] = "REG-2"
        current["created_at_utc"] = "2026-02-01T00:00:00Z"
        current["predecessor"] = {"version": "REG-1", "sha256": HASH_A}
        current["candidates"] = []
        current["variants"] = []
        checked = validate_candidate_registry(current, predecessor)
        self.assertFalse(checked.ok)
        self.assertTrue(any("removed" in error for error in checked.errors))
        protocol = valid_protocol()
        protocol["ranking"]["method"] = "UNSET"
        self.assertFalse(validate_evaluation_protocol(protocol).ok)


class CapabilityAndReceiptAttackRegressions(unittest.TestCase):
    def test_A45_A46_A47_capability_identity(self) -> None:
        mutations = []
        forged_base = load_json(CAPABILITY_PATH)
        forged_base["audited_base_commit"] = "0" * 40
        mutations.append(forged_base)
        wrong_version = load_json(CAPABILITY_PATH)
        wrong_version["manifest_version"] = "FORGED"
        mutations.append(wrong_version)
        invented = load_json(CAPABILITY_PATH)
        invented["capabilities"]["invented_profit_oracle"] = {"supported": True}
        mutations.append(invented)
        for capability in mutations:
            self.assertFalse(validate_capability_manifest(capability, REPO_ROOT).ok)

    def test_A49_external_capability_path_and_A57_fake_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copied = root / "capability.json"
            copied.write_bytes(CAPABILITY_PATH.read_bytes())
            self.assertFalse(validate_capability_manifest(load_json(copied), REPO_ROOT, copied).ok)
            fake_repo = root / "fake"
            fake_repo.mkdir()
            self.assertFalse(validate_capability_manifest(load_json(CAPABILITY_PATH), fake_repo).ok)

    def test_A50_A51_A52_A53_A54_A56_receipt_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, receipt_path = fixture_files(root)
            report, receipt = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt_path,
                strategy_code_path=strategy,
            )
            self.assertTrue(report.ok, report.render())
            assert receipt is not None
            mutations = []
            for key in ("git_commit", "backtester_commit"):
                item = copy.deepcopy(receipt)
                item[key] = "0" * 40
                mutations.append(item)
            future = copy.deepcopy(receipt)
            future["frozen_at_utc"] = "2099-01-01T00:00:00Z"
            mutations.append(future)
            unresolved = copy.deepcopy(receipt)
            unresolved["unresolved_counts"] = {}
            mutations.append(unresolved)
            pass_with_errors = copy.deepcopy(receipt)
            pass_with_errors["validation"]["errors"] = ["hidden"]
            mutations.append(pass_with_errors)
            for item in mutations:
                checked = validate_freeze_receipt(
                    item, spec_path=spec, registry_path=registry,
                    protocol_path=protocol, capability_path=CAPABILITY_PATH,
                    data_manifest_path=data, repo_root=REPO_ROOT,
                    strategy_code_path=strategy,
                )
                self.assertFalse(checked.ok)

    def test_A59_strategy_code_lock_required_at_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec, registry, protocol, data, _, receipt = fixture_files(Path(tmp))
            report, created = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt,
            )
            self.assertFalse(report.ok)
            self.assertIsNone(created)

    def test_same_variant_identity_cannot_freeze_different_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, first_receipt = fixture_files(root)
            first, _ = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=first_receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(first.ok, first.render())
            spec_payload = load_json(spec)
            spec_payload["parameters"][0]["value"] = 11
            write_json(spec, spec_payload)
            registry_payload = load_json(registry)
            registry_payload["variants"][0]["spec_sha256"] = sha256_file(spec)
            canonical = json.dumps(spec_payload["parameters"], sort_keys=True, separators=(",", ":")).encode()
            import hashlib
            registry_payload["variants"][0]["parameter_identity_sha256"] = hashlib.sha256(canonical).hexdigest()
            write_json(registry, registry_payload)
            second, created = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=root / "second_freeze.json",
                strategy_code_path=strategy,
            )
            self.assertFalse(second.ok)
            self.assertIsNone(created)


class ProductionPathAttackRegressions(unittest.TestCase):
    def _frozen(self, root: Path):
        paths = fixture_files(root)
        spec, registry, protocol, data, strategy, receipt = paths
        report, _ = create_freeze_receipt(
            spec_path=spec, registry_path=registry, protocol_path=protocol,
            capability_path=CAPABILITY_PATH, data_manifest_path=data,
            repo_root=REPO_ROOT, receipt_path=receipt,
            strategy_code_path=strategy,
        )
        self.assertTrue(report.ok, report.render())
        return paths

    def test_A61_window_A63_dirty_and_config_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, receipt = self._frozen(root)
            kwargs = dict(
                receipt_path=receipt, spec_path=spec, registry_path=registry,
                protocol_path=protocol, capability_path=CAPABILITY_PATH,
                data_manifest_path=data, strategy_code_path=strategy,
                repo_root=REPO_ROOT, actual_config=BacktestConfig(),
                tested_start=0, tested_end=60_000, run_stage="COMPARISON",
                test_manifest_path=root / "test_manifest.json",
            )
            self.assertFalse(validate_production_preflight(**kwargs).ok)
            kwargs["tested_start"] = 1_577_836_800_000
            kwargs["tested_end"] = 1_609_459_200_000
            with patch(
                "research.strategy_replications.validation.core._material_dirty_paths",
                return_value=["research/backtester_v2/engine.py"],
            ):
                dirty = validate_production_preflight(**kwargs)
            self.assertFalse(dirty.ok)
            self.assertTrue(any("repo.dirty" in error for error in dirty.errors))
            wrong_config = BacktestConfig(taker_fee_rate=0.001)
            kwargs["actual_config"] = wrong_config
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                self.assertFalse(validate_production_preflight(**kwargs).ok)

    def test_A14_nonexistent_trace_and_required_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path, _, _, _, strategy, _ = fixture_files(root)
            spec = load_json(spec_path)
            spec["traceability"][0]["code_symbol"] = "Missing.symbol"
            write_json(spec_path, spec)
            manifest = load_json(root / "test_manifest.json")
            manifest["strategy_spec_sha256"] = sha256_file(spec_path)
            manifest["results"].pop()
            write_json(root / "test_manifest.json", manifest)
            checked = validate_test_manifest_and_traceability(
                spec=spec, spec_path=spec_path, strategy_code_path=strategy,
                test_manifest_path=root / "test_manifest.json",
            )
            self.assertFalse(checked.ok)

    def test_A69_A70_external_production_output_requires_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                build_run_metadata(
                    repo_root=REPO_ROOT, strategy_name="external",
                    strategy_version="1", source_type="external_replication",
                    run_purpose="PRODUCTION_RESEARCH", run_stage="COMPARISON",
                    strategy_parameters={}, source_reference="source",
                    manifest_path=root / "data.json", symbol="BTCUSDT",
                    market="perpetual", timeframe="1m", tested_start=0,
                    tested_end=1, row_count=2,
                )
            result = BacktestEngine(BacktestConfig()).run(
                [Bar(0, 100, 100, 100, 100, 1)], NoopStrategy(),
            )
            forged_metadata = {
                "run_id": "FORGED", "run_purpose": "PRODUCTION_RESEARCH",
                "run_stage": "COMPARISON", "data": {"tested_start": 0, "tested_end": 0},
                "code": {"git_commit": "0" * 40, "dirty": False},
                "qa_status": "VERIFIED",
            }
            output = root / "run"
            with self.assertRaises(ValueError):
                write_results(output, result, BacktestConfig(), forged_metadata)
            self.assertFalse(output.exists())

    def test_A62_A64_A65_A66_A67_A68_post_run_identity_and_outputs(self) -> None:
        # These attacks are all rejected by exact output-manifest, lineage,
        # capability-version, actual Git/code, and data identity checks. Build
        # one valid production output and mutate one controlled artifact at a time.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, freeze_receipt = self._frozen(root)
            start, end = 1_577_836_800_000, 1_609_459_200_000
            config = BacktestConfig()
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                report, context = create_production_preflight_context(
                    receipt_path=freeze_receipt, spec_path=spec,
                    registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                    actual_config=config, tested_start=start, tested_end=end,
                    run_stage="COMPARISON", test_manifest_path=root / "test_manifest.json",
                )
            self.assertTrue(report.ok, report.render())
            assert context is not None
            lineage = ReplicationLineage(
                candidate_id="C001", variant_id="C001-V1", registry_version="REG-1",
                registry_sha256=sha256_file(registry), protocol_version="EP-1",
                protocol_sha256=sha256_file(protocol), strategy_spec_sha256=sha256_file(spec),
                fidelity_classification=compute_fidelity_summary(load_json(spec)),
                comparability_class="DIRECTLY_COMPARABLE",
                capability_manifest_version="BACKTESTER_V2_EXECUTION_CONTRACT_4",
                freeze_receipt_sha256=sha256_file(freeze_receipt),
            )
            with patch("research.backtester_v2.output._material_dirty_paths", return_value=[]):
                metadata = build_run_metadata(
                    repo_root=REPO_ROOT, strategy_name="fixture", strategy_version="V1",
                    source_type="external_replication", run_purpose="PRODUCTION_RESEARCH",
                    run_stage="COMPARISON", strategy_parameters={"fast": 10, "slow": 20},
                    source_reference="Fixture source", manifest_path=data,
                    symbol="BTCUSDT", market="perpetual", timeframe="1m",
                    tested_start=start, tested_end=end, row_count=2,
                    replication_lineage=lineage, strategy_code_path=strategy,
                    capability_manifest_path=CAPABILITY_PATH,
                    freeze_receipt_path=freeze_receipt, preflight_context=context,
                )
                result = BacktestEngine(config).run(
                    [Bar(start, 100, 100, 100, 100, 1), Bar(end, 100, 100, 100, 100, 1)],
                    NoopStrategy(),
                )
                output = root / "run"
                write_results(output, result, config, metadata, preflight_context=context)
            (output / "trades.csv").unlink()
            (output / "unexpected.bin").write_bytes(b"material")
            metadata_payload = load_json(output / "run_metadata.json")
            metadata_payload["data"]["manifest_sha256"] = "0" * 64
            metadata_payload["code"]["git_commit"] = "0" * 40
            metadata_payload["code"]["file_sha256"] = {"invented.py": "0" * 64}
            metadata_payload["replication_lineage"]["capability_manifest_version"] = "FORGED"
            write_json(output / "run_metadata.json", metadata_payload)
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                checked = validate_run_lineage(
                    output_dir=output, freeze_receipt_path=freeze_receipt,
                    spec_path=spec, registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                )
            self.assertFalse(checked.ok)
            joined = "\n".join(checked.errors)
            self.assertIn("artifact is missing", joined)
            self.assertIn("unexpected unlisted", joined)
            self.assertIn("data.manifest_sha256", joined)
            self.assertIn("code.git_commit", joined)
            self.assertIn("file_sha256", joined)
            self.assertIn("capability_manifest_version", joined)

    def test_protected_use_is_logged_and_repeat_is_rejected(self) -> None:
        from research.strategy_replications.validation.core import create_run_receipt

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol_path, data, strategy, freeze_receipt = fixture_files(root)
            protocol = load_json(protocol_path)
            protocol["protected_validation"]["dataset_manifest_sha256"] = sha256_file(data)
            write_json(protocol_path, protocol)
            freeze_report, _ = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol_path,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=freeze_receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(freeze_report.ok, freeze_report.render())
            start, end = 1_640_995_200_000, 1_672_531_200_000
            config = BacktestConfig()
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                preflight, context = create_production_preflight_context(
                    receipt_path=freeze_receipt, spec_path=spec,
                    registry_path=registry, protocol_path=protocol_path,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                    actual_config=config, tested_start=start, tested_end=end,
                    run_stage="PROTECTED_VALIDATION",
                    test_manifest_path=root / "test_manifest.json",
                )
            self.assertTrue(preflight.ok, preflight.render())
            assert context is not None
            lineage = ReplicationLineage(
                candidate_id="C001", variant_id="C001-V1", registry_version="REG-1",
                registry_sha256=sha256_file(registry), protocol_version="EP-1",
                protocol_sha256=sha256_file(protocol_path), strategy_spec_sha256=sha256_file(spec),
                fidelity_classification="PURE_REPLICATION",
                comparability_class="DIRECTLY_COMPARABLE",
                capability_manifest_version="BACKTESTER_V2_EXECUTION_CONTRACT_4",
                freeze_receipt_sha256=sha256_file(freeze_receipt),
            )
            result = BacktestEngine(config).run(
                [Bar(start, 100, 100, 100, 100, 1), Bar(end, 100, 100, 100, 100, 1)],
                NoopStrategy(),
            )
            for index in (1, 2):
                with patch("research.backtester_v2.output._material_dirty_paths", return_value=[]):
                    metadata = build_run_metadata(
                        repo_root=REPO_ROOT, strategy_name="protected", strategy_version="V1",
                        source_type="external_replication", run_purpose="PRODUCTION_RESEARCH",
                        run_stage="PROTECTED_VALIDATION", strategy_parameters={"fast": 10, "slow": 20},
                        source_reference="Fixture source", manifest_path=data,
                        symbol="BTCUSDT", market="perpetual", timeframe="1m",
                        tested_start=start, tested_end=end, row_count=2,
                        replication_lineage=lineage, strategy_code_path=strategy,
                        capability_manifest_path=CAPABILITY_PATH,
                        freeze_receipt_path=freeze_receipt, preflight_context=context,
                    )
                    output = root / f"protected-{index}"
                    write_results(output, result, config, metadata, preflight_context=context)
                with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                    receipt_report, created = create_run_receipt(
                        output_dir=output, freeze_receipt_path=freeze_receipt,
                        spec_path=spec, registry_path=registry, protocol_path=protocol_path,
                        capability_path=CAPABILITY_PATH, data_manifest_path=data,
                        strategy_code_path=strategy, receipt_path=root / f"protected-{index}-receipt.json",
                        repo_root=REPO_ROOT,
                    )
                self.assertFalse(receipt_report.ok)
                self.assertIsNone(created)
                self.assertTrue(any("RUN_RECEIPT_V1 issuance is disabled" in error for error in receipt_report.errors))

    def test_regression_map_contains_every_must_fix_attack(self) -> None:
        covered = {
            "A09", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17",
            "A32", "A33", "A34", "A35", "A36", "A37", "A38", "A39", "A40",
            "A41", "A42", "A43", "A45", "A46", "A47", "A49", "A50", "A51",
            "A52", "A53", "A54", "A56", "A57", "A59", "A61", "A62", "A63",
            "A64", "A65", "A66", "A67", "A68", "A69", "A70",
        }
        self.assertEqual(covered, MANDATORY_FIXED_ATTACKS)


if __name__ == "__main__":
    unittest.main()
