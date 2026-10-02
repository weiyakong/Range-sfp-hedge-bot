from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Tuple
from unittest.mock import patch

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import (
    BacktestConfig,
    Bar,
    ReplicationLineage,
)
from research.backtester_v2.output import build_run_metadata, write_results
from research.strategy_replications.validation.core import (
    compute_fidelity_summary,
    create_freeze_receipt,
    create_production_preflight_context,
    create_run_receipt,
    derived_registry_counts,
    load_json,
    sha256_file,
    validate_candidate_registry,
    validate_capability_manifest,
    validate_evaluation_protocol,
    validate_freeze_inputs,
    validate_freeze_receipt,
    validate_production_preflight,
    validate_run_lineage,
    validate_run_receipt,
    validate_strategy_spec,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CAPABILITY_PATH = (
    REPO_ROOT
    / "research/strategy_replications/capability/backtester_v2_capabilities.json"
)
HASH_A = "a" * 64
DEFAULT_CONFIG_SHA256 = hashlib.sha256(json.dumps(
    asdict(BacktestConfig()), sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode("utf-8")).hexdigest()


class NoopStrategy:
    def on_bar(self, bar: Bar, state: object) -> list:
        return []


def metric(name: str) -> Dict[str, object]:
    item: Dict[str, object] = {
        "name": name,
        "formula": f"frozen formula for {name}",
        "formula_version": f"BACKTESTER_V2_METRICS_2:{name}",
        "units": "ratio",
        "denominator": "frozen denominator",
        "source_artifact": "metrics.json or equity.csv",
        "applicability": "all mathematically defined runs",
    }
    if name in {"sharpe", "sortino"}:
        item["return_series_methodology"] = "one simple return per canonical bar; no interpolation"
    return item


def valid_protocol() -> Dict[str, object]:
    metric_names = [
        "total_return", "expectancy_per_trade", "profit_factor", "win_rate",
        "close_to_close_max_drawdown", "intrabar_worst_max_drawdown",
        "return_to_intrabar_drawdown", "time_exposure", "turnover",
        "average_holding_time", "ambiguity_rate", "yearly_return", "sharpe",
        "sortino", "recovery_factor", "time_underwater",
    ]
    values = {
        "maker_fee": 0.0, "taker_fee": 0.0, "slippage": 0.0,
        "passive_limit_policy": "strict_through",
        "marketable_limit_policy": "OPEN_TAKER_WITH_LIMIT_CAP",
        "funding_treatment": "provided",
        "liquidation_model": "mark_trigger_approximation",
        "end_of_data_policy": "mark_to_market", "margin_mode": "cross",
        "leverage": 1.0, "liquidation_enabled": False,
        "liquidation_fee": 0.0, "intrabar_policy": "worst_case",
    }
    assumptions = {
        name: {"value": value, "origin": "COMMON_RESEARCH_PROTOCOL"}
        for name, value in values.items()
    }
    finalist_hash = hashlib.sha256(
        json.dumps(["C001-V1"], separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {
        "schema_version": "EVALUATION_PROTOCOL_V1",
        "protocol_version": "EP-1",
        "status": "FROZEN",
        "created_at_utc": "2019-12-30T00:00:00Z",
        "candidate_universe": {
            "registry_version": "REG-1",
            "frozen_before_candidate_results": True,
        },
        "historical_window": {
            "start_utc": "2020-01-01T00:00:00Z",
            "end_utc": "2021-01-01T00:00:00Z",
            "timezone": "UTC",
            "role": "INITIAL_COMPARISON_EXCLUDING_PROTECTED_FINAL",
            "frozen_before_any_outcome_bearing_run": True,
        },
        "execution_assumptions": assumptions,
        "eligibility": {
            "candidate_registered": True,
            "protocol_frozen": True,
            "spec_valid": True,
            "spec_frozen": True,
            "no_material_ambiguity": True,
            "required_data_available": True,
            "engine_compatible": True,
            "synthetic_causality_tests_pass": True,
            "lineage_complete": True,
            "historical_window_frozen": True,
            "allowed_engine_integrity_statuses": ["PASS"],
        },
        "ranking": {
            "method": "NO_SCALAR",
            "advancement_rule": "Advance every eligible candidate to separately protected finalist validation",
        },
        "metrics": [metric(name) for name in metric_names],
        "time_exposure_definition": "ANY_POSITION_ACTIVE_DURING_BAR_FRACTION",
        "protected_validation": {
            "policy_frozen_before_first_selection_result": True,
            "data_excluded_from_initial_selection_and_formalization": True,
            "finalist_evaluation_rule": "Evaluate all predeclared finalists once on the protected partition",
            "dataset_manifest_sha256": HASH_A,
            "finalist_set_sha256": finalist_hash,
            "selection_protocol_sha256": HASH_A,
            "finalist_variant_ids": ["C001-V1"],
            "window": {"start_utc": "2022-01-01T00:00:00Z", "end_utc": "2023-01-01T00:00:00Z"},
        },
        "multiple_testing": {
            "disclose_candidate_count": True,
            "disclose_variant_count": True,
            "retain_failures": True,
            "protected_finalist_stage": True,
            "selection_bias_disclosure_rule": "Report every candidate and variant count with finalist results",
        },
    }


def valid_spec(data_manifest_hash: str) -> Dict[str, object]:
    return {
        "schema_version": "STRATEGY_SPEC_V1",
        "strategy_id": "MA-CROSS",
        "strategy_version": "V1",
        "candidate_id": "C001",
        "variant_id": "C001-V1",
        "status": "FROZEN",
        "created_at_utc": "2026-01-02T00:00:00Z",
        "fidelity": {
            "rule": "VERBATIM",
            "market": "SAME_MARKET",
            "timeframe": "SAME_TIMEFRAME",
            "session": "SAME_SESSION",
            "product": "SAME_PRODUCT_TYPE",
            "execution": "SOURCE_SPECIFIED",
            "sizing": "SOURCE_DEFINED",
            "declared_summary": "PURE_REPLICATION",
        },
        "parameters": [
            {"parameter_id": "fast_length", "value": 10, "units": "bars", "origin": "SOURCE_EXACT"},
            {"parameter_id": "slow_length", "value": 20, "units": "bars", "origin": "SOURCE_EXACT"},
        ],
        "proxy": {"used": False},
        "data_manifest": {"manifest_id": "FIXTURE-DATA", "sha256": data_manifest_hash},
        "data_inputs": [
            {
                "field_id": "ohlc", "requirement": "REQUIRED",
                "availability": "AVAILABLE", "dataset_id": "fixture-bars",
                "source_id": "fixture", "frequency": "1m",
                "timestamp_semantics": "bar open UTC",
                "units": "quote currency", "available_at_semantics": "after bar close",
                "manifest_sha256": data_manifest_hash,
            }
        ],
        "implementation": {
            "input_ids": ["ohlc"],
            "strategy_symbol": "MaCrossStrategy",
        },
        "required_capabilities": ["market_entry", "next_bar_market_execution"],
        "ambiguities": [],
        "state_model": {
            "reachable_states": ["FLAT", "LONG", "SHORT"],
            "signals_events": ["LONG_SIGNAL", "SHORT_SIGNAL", "EXIT_SIGNAL"],
            "reachable_pairs": [
                {"state": "FLAT", "signal": "LONG_SIGNAL"},
                {"state": "FLAT", "signal": "SHORT_SIGNAL"},
                {"state": "LONG", "signal": "EXIT_SIGNAL"},
                {"state": "SHORT", "signal": "EXIT_SIGNAL"},
            ],
            "decisions": [
                {"state": "FLAT", "signal": "LONG_SIGNAL", "action": "ENTER_LONG_NEXT_OPEN"},
                {"state": "FLAT", "signal": "SHORT_SIGNAL", "action": "ENTER_SHORT_NEXT_OPEN"},
                {"state": "LONG", "signal": "EXIT_SIGNAL", "action": "EXIT_LONG_NEXT_OPEN"},
                {"state": "SHORT", "signal": "EXIT_SIGNAL", "action": "EXIT_SHORT_NEXT_OPEN"},
            ],
        },
        "exit_precedence": ["LIQUIDATION_ENGINE_CONTROLLED", "STRATEGY_EXIT_NEXT_OPEN"],
        "tests": {
            "synthetic": {"positive": "PASS", "negative": "PASS", "boundary": "PASS", "causality": "PASS"},
            "golden_examples": "NOT_APPLICABLE_NO_SOURCE_EXAMPLES",
            "test_ids": ["test_ma_positive", "test_ma_negative", "test_ma_boundary", "test_ma_causality"],
            "suite_sha256": HASH_A,
        },
        "traceability": [
            {
                "rule_id": "R1", "source_evidence": "SRC1:p10",
                "interpretation": "Fast SMA crosses above slow SMA after close",
                "executable_rule": "fast_prev <= slow_prev and fast_now > slow_now",
                "test_id": "test_ma_positive", "code_path": "strategy.py",
                "code_symbol": "MaCrossStrategy.on_bar", "implementation_version": "V1",
                "implementation_sha256": None,
            }
        ],
        "source_evidence": {
            "primary_source_id": "SRC1", "reference": "Fixture source",
            "edition_version": "1", "exact_locator": "page 10",
            "knowledge_cutoff_date": "2019-12-01",
            "evidence_sha256": HASH_A,
        },
        "protocol_exceptions": [],
        "comparability_class": "DIRECTLY_COMPARABLE",
        "outcome_bearing_historical_run_seen": False,
        "execution_config_sha256": DEFAULT_CONFIG_SHA256,
    }


def valid_registry(spec_hash: str) -> Dict[str, object]:
    parameter_hash = hashlib.sha256(json.dumps(
        valid_spec(HASH_A)["parameters"], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema_version": "CANDIDATE_REGISTRY_V1",
        "registry_version": "REG-1",
        "status": "FROZEN",
        "created_at_utc": "2026-01-04T00:00:00Z",
        "predecessor": None,
        "universe_definition": "All candidates identified by the frozen search protocol",
        "intake_required_before_substantive_review": True,
        "candidates": [
            {
                "candidate_id": "C001", "strategy_name": "MA crossover",
                "primary_source_id": "SRC1", "primary_source_reference": "Fixture source",
                "intake_timestamp_utc": "2026-01-01T00:00:00Z",
                "current_status": "FROZEN", "inclusion_reason": "Meets frozen inclusion rule",
                "exclusion_reason": None,
                "status_history": [
                    {"status": "IDENTIFIED", "timestamp_utc": "2026-01-01T00:00:00Z", "reason": "Intake before review"},
                    {"status": "FROZEN", "timestamp_utc": "2026-01-03T00:00:00Z", "reason": "Validated spec"},
                ],
            }
        ],
        "variants": [
            {
                "variant_id": "C001-V1", "candidate_id": "C001", "parent_id": "C001",
                "created_at_utc": "2026-01-02T00:00:00Z", "type": "PURE_REPLICATION",
                "exact_change": "Initial source-faithful formalization", "parameter_changes": [],
                "search_space": {}, "spec_sha256": spec_hash,
                "parameter_identity_sha256": parameter_hash,
                "fidelity_classification": "PURE_REPLICATION",
                "historical_results_observed_before_creation": [], "status": "FROZEN",
            }
        ],
    }


def write_json(path: Path, value: Dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_files(root: Path) -> Tuple[Path, Path, Path, Path, Path, Path]:
    data = root / "data_manifest.json"
    data.write_text('{"dataset":"fixture"}\n', encoding="utf-8")
    strategy = root / "strategy.py"
    strategy.write_text("class MaCrossStrategy:\n    def on_bar(self, bar, state):\n        return []\n", encoding="utf-8")
    suite = root / "strategy_tests.py"
    suite.write_text("# executed fixture suite\n", encoding="utf-8")
    spec_path = root / "spec.json"
    spec_payload = valid_spec(sha256_file(data))
    spec_payload["tests"]["suite_sha256"] = sha256_file(suite)
    spec_payload["traceability"][0]["code_path"] = "strategy.py"
    spec_payload["traceability"][0]["implementation_sha256"] = sha256_file(strategy)
    write_json(spec_path, spec_payload)
    registry_path = root / "registry.json"
    write_json(registry_path, valid_registry(sha256_file(spec_path)))
    protocol_path = root / "protocol.json"
    write_json(protocol_path, valid_protocol())
    receipt_path = root / "freeze_receipt.json"
    write_json(root / "test_manifest.json", {
        "schema_version": "STRATEGY_TEST_RESULTS_V1",
        "executed_at_utc": "2026-01-03T00:00:00Z",
        "strategy_spec_sha256": sha256_file(spec_path),
        "strategy_code_sha256": sha256_file(strategy),
        "strategy_symbol": "MaCrossStrategy",
        "test_suite_path": "strategy_tests.py",
        "test_suite_sha256": sha256_file(suite),
        "results": [
            {"test_id": test_id, "test_identifier": f"fixture.{test_id}", "result": "PASS"}
            for test_id in spec_payload["tests"]["test_ids"]
        ],
    })
    return spec_path, registry_path, protocol_path, data, strategy, receipt_path


class FreezeAttackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = load_json(CAPABILITY_PATH)

    def test_01_manual_frozen_without_receipt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec, registry, protocol, data, strategy, _ = fixture_files(Path(tmp))
            report = validate_production_preflight(
                receipt_path=Path(tmp) / "missing.json", spec_path=spec,
                registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                strategy_code_path=strategy, repo_root=REPO_ROOT,
            )
            self.assertFalse(report.ok)

    def test_02_invalid_enum_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["fidelity"]["rule"] = "MOSTLY_VERBATIM"
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_03_required_placeholders_fail(self) -> None:
        for value in ("", "-", "N/A", "unknown"):
            spec = valid_spec(HASH_A)
            spec["strategy_id"] = value
            with self.subTest(value=value):
                self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_04_hidden_unsupported_stop_entry_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["required_capabilities"].append("stop_entry")
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_05_proxy_plus_pure_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["proxy"] = {
            "used": True, "original_behavior": "stop entry",
            "replacement_behavior": "next-open market", "rationale": "engine gap",
            "impact": "different fill", "classification_consequence": "ADAPTED",
        }
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_06_forbidden_input_use_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["data_inputs"].append({
            "field_id": "future_label", "requirement": "FORBIDDEN",
            "availability": "AVAILABLE", "dataset_id": "labels",
            "source_id": "fixture", "frequency": "1m",
            "timestamp_semantics": "future outcome", "units": "class",
            "available_at_semantics": "after outcome", "manifest_sha256": HASH_A,
        })
        spec["implementation"]["input_ids"].append("future_label")
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_07_material_unresolved_ambiguity_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["ambiguities"] = [{
            "ambiguity_id": "U1", "material": True, "resolution": "UNRESOLVED",
            "materiality_rationale": "Changes entry timing",
        }]
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_08_incomplete_reachable_state_mapping_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["state_model"]["decisions"].pop()
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_09_source_range_without_selection_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["parameters"][0] = {
            "parameter_id": "fast_length", "value": 10, "units": "bars",
            "origin": "SOURCE_RANGE", "source_range": {"minimum": 5, "maximum": 20},
        }
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_10_candidate_absent_from_registry_fails(self) -> None:
        spec = valid_spec(HASH_A)
        registry = valid_registry(HASH_A)
        registry["candidates"] = []
        report = validate_freeze_inputs(
            spec, registry, valid_protocol(), self.capability, REPO_ROOT, HASH_A,
        )
        self.assertFalse(report.ok)

    def test_11_invalid_hash_fails(self) -> None:
        spec = valid_spec(HASH_A)
        spec["data_manifest"]["sha256"] = "invalid"
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_frozen_strategy_symbol_is_required(self) -> None:
        spec = valid_spec(HASH_A)
        del spec["implementation"]["strategy_symbol"]
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("strategy_symbol" in item for item in report.errors))

    def test_freeze_rejects_strategy_symbol_missing_from_locked_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, receipt = fixture_files(root)
            payload = load_json(spec)
            payload["implementation"]["strategy_symbol"] = "MissingStrategy"
            payload["traceability"][0]["code_symbol"] = "MissingStrategy.on_bar"
            write_json(spec, payload)
            write_json(registry, valid_registry(sha256_file(spec)))
            report, created = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt,
                strategy_code_path=strategy,
            )
            self.assertFalse(report.ok)
            self.assertIsNone(created)
            self.assertTrue(any("entrypoint" in item for item in report.errors))

    def test_12_frozen_spec_mutation_invalidates_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = fixture_files(Path(tmp))
            spec, registry, protocol, data, strategy, receipt = paths
            report, _ = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(report.ok, report.render())
            spec.write_text(spec.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            checked = validate_freeze_receipt(
                load_json(receipt), spec_path=spec, registry_path=registry,
                protocol_path=protocol, capability_path=CAPABILITY_PATH,
                data_manifest_path=data,
            )
            self.assertFalse(checked.ok)

    def test_13_favorable_execution_exception_requires_downgrade(self) -> None:
        spec = valid_spec(HASH_A)
        spec["protocol_exceptions"] = [{
            "exception_id": "E1", "type": "EXECUTION",
            "rationale": "Lower source-specific fees", "source_evidence": "SRC1:p12",
            "comparability_consequence": "Requires declared exception",
        }]
        self.assertFalse(validate_strategy_spec(spec, self.capability).ok)

    def test_14_unacceptable_qa_or_missing_lineage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, receipt = fixture_files(root)
            report, _ = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(report.ok, report.render())
            output = root / "run"
            output.mkdir()
            write_json(output / "manifest.json", {"status": "COMPLETE", "run_id": "R1", "checksums": {}})
            write_json(output / "run_metadata.json", {
                "run_id": "R1", "qa_status": "NOT VERIFIED", "data": {"tested_start": 0, "tested_end": 1}
            })
            write_json(output / "config.json", {})
            checked = validate_run_lineage(
                output_dir=output, freeze_receipt_path=receipt, spec_path=spec,
                registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                strategy_code_path=strategy,
            )
            self.assertFalse(checked.ok)


class PositiveEnforcementTests(unittest.TestCase):
    def test_valid_ma_replication_passes_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec, registry, protocol, data, strategy, receipt = fixture_files(Path(tmp))
            report, frozen = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(report.ok, report.render())
            self.assertIsNotNone(frozen)

    def test_target_market_transfer_is_computed(self) -> None:
        spec = valid_spec(HASH_A)
        spec["fidelity"]["market"] = "TARGET_MARKET_TRANSFER"
        spec["fidelity"]["declared_summary"] = "TRANSFER_REPLICATION"
        self.assertEqual(compute_fidelity_summary(spec), "TRANSFER_REPLICATION")
        self.assertTrue(validate_strategy_spec(spec, load_json(CAPABILITY_PATH)).ok)

    def test_unsupported_stop_entry_is_blocked(self) -> None:
        spec = valid_spec(HASH_A)
        spec["required_capabilities"] = ["stop_entry"]
        report = validate_strategy_spec(spec, load_json(CAPABILITY_PATH))
        self.assertTrue(any("BLOCKED_UNSUPPORTED_ENGINE_CAPABILITY" in item for item in report.errors))

    def test_no_source_golden_examples_can_pass(self) -> None:
        spec = valid_spec(HASH_A)
        self.assertEqual(spec["tests"]["golden_examples"], "NOT_APPLICABLE_NO_SOURCE_EXAMPLES")
        self.assertTrue(validate_strategy_spec(spec, load_json(CAPABILITY_PATH)).ok)

    def test_registry_counts_are_derived(self) -> None:
        counts = derived_registry_counts(valid_registry(HASH_A))
        self.assertEqual(counts["candidates_identified"], 1)
        self.assertEqual(counts["variants_total"], 1)
        self.assertEqual(counts["variants_backtested"], 0)

    def test_capability_manifest_matches_execution_engine(self) -> None:
        report = validate_capability_manifest(load_json(CAPABILITY_PATH), REPO_ROOT)
        self.assertTrue(report.ok, report.render())

    def test_protocol_is_valid_and_ranking_not_unset(self) -> None:
        self.assertTrue(validate_evaluation_protocol(valid_protocol()).ok)
        invalid = valid_protocol()
        invalid["ranking"] = {"method": "UNSET"}
        self.assertFalse(validate_evaluation_protocol(invalid).ok)

    def test_full_run_receipt_and_lineage_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, registry, protocol, data, strategy, freeze_receipt = fixture_files(root)
            freeze_report, _ = create_freeze_receipt(
                spec_path=spec, registry_path=registry, protocol_path=protocol,
                capability_path=CAPABILITY_PATH, data_manifest_path=data,
                repo_root=REPO_ROOT, receipt_path=freeze_receipt,
                strategy_code_path=strategy,
            )
            self.assertTrue(freeze_report.ok, freeze_report.render())
            spec_payload = load_json(spec)
            registry_payload = load_json(registry)
            protocol_payload = load_json(protocol)
            lineage = ReplicationLineage(
                candidate_id="C001", variant_id="C001-V1",
                registry_version="REG-1", registry_sha256=sha256_file(registry),
                protocol_version="EP-1", protocol_sha256=sha256_file(protocol),
                strategy_spec_sha256=sha256_file(spec),
                fidelity_classification=compute_fidelity_summary(spec_payload),
                comparability_class="DIRECTLY_COMPARABLE",
                capability_manifest_version="BACKTESTER_V2_EXECUTION_CONTRACT_4",
                freeze_receipt_sha256=sha256_file(freeze_receipt),
            )
            start = 1_577_836_800_000
            end = 1_609_459_200_000
            config = BacktestConfig()
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]), patch("research.backtester_v2.output._material_dirty_paths", return_value=[]):
                preflight_report, context = create_production_preflight_context(
                    receipt_path=freeze_receipt, spec_path=spec,
                    registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                    actual_config=config, tested_start=start, tested_end=end,
                    run_stage="COMPARISON", test_manifest_path=root / "test_manifest.json",
                )
                self.assertTrue(preflight_report.ok, preflight_report.render())
                self.assertIsNotNone(context)
                metadata = build_run_metadata(
                    repo_root=REPO_ROOT, strategy_name="MA crossover",
                    strategy_version="V1", source_type="external_replication",
                    run_purpose="PRODUCTION_RESEARCH", run_stage="COMPARISON",
                    strategy_parameters={"fast": 10, "slow": 20},
                    source_reference="Fixture source", manifest_path=data,
                    symbol="BTCUSDT", market="USDT-M perpetual futures",
                    timeframe="1m", tested_start=start, tested_end=end,
                    row_count=2, replication_lineage=lineage,
                    strategy_code_path=strategy,
                    capability_manifest_path=CAPABILITY_PATH,
                    freeze_receipt_path=freeze_receipt,
                    preflight_context=context,
                )
                result = BacktestEngine(config).run(
                    [Bar(start, 100, 100, 100, 100, 1), Bar(end, 100, 100, 100, 100, 1)],
                    NoopStrategy(),
                )
                output = root / "run"
                write_results(output, result, config, metadata, preflight_context=context)
            run_receipt = root / "run_receipt.json"
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                run_report, created = create_run_receipt(
                    output_dir=output, freeze_receipt_path=freeze_receipt,
                    spec_path=spec, registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, receipt_path=run_receipt,
                    repo_root=REPO_ROOT,
                )
            self.assertFalse(run_report.ok)
            self.assertIsNone(created)
            self.assertTrue(any("RUN_RECEIPT_V1 issuance is disabled" in item for item in run_report.errors))
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                revalidated = validate_run_receipt(
                    run_receipt, output_dir=output,
                    freeze_receipt_path=freeze_receipt, spec_path=spec,
                    registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                )
                duplicate_report, duplicate = create_run_receipt(
                    output_dir=output, freeze_receipt_path=freeze_receipt,
                    spec_path=spec, registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, receipt_path=root / "duplicate_run_receipt.json",
                    repo_root=REPO_ROOT,
                )
            self.assertFalse(revalidated.ok)
            self.assertTrue(any("not execution-attested" in item for item in revalidated.errors))
            self.assertFalse(duplicate_report.ok)
            self.assertIsNone(duplicate)

            metadata_path = output / "run_metadata.json"
            metadata_payload = load_json(metadata_path)
            metadata_payload["replication_lineage"]["candidate_id"] = "WRONG"
            write_json(metadata_path, metadata_payload)
            with patch("research.strategy_replications.validation.core._material_dirty_paths", return_value=[]):
                mismatch = validate_run_lineage(
                    output_dir=output, freeze_receipt_path=freeze_receipt,
                    spec_path=spec, registry_path=registry, protocol_path=protocol,
                    capability_path=CAPABILITY_PATH, data_manifest_path=data,
                    strategy_code_path=strategy, repo_root=REPO_ROOT,
                )
            self.assertFalse(mismatch.ok)


if __name__ == "__main__":
    unittest.main()
