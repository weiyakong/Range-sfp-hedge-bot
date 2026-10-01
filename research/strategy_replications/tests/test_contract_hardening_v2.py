from __future__ import annotations

import copy
import unittest

from research.strategy_replications.tests.test_enforcement import (
    CAPABILITY_PATH,
    HASH_A,
    REPO_ROOT,
    valid_protocol,
    valid_registry,
    valid_spec,
)
from research.strategy_replications.validation.core import (
    load_json,
    validate_candidate_registry,
    validate_evaluation_protocol,
    validate_freeze_inputs,
    validate_strategy_spec,
)


class ContractHardeningV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capability = load_json(CAPABILITY_PATH)

    def test_nested_extra_properties_are_rejected(self):
        spec = valid_spec(HASH_A)
        spec["fidelity"]["bypass"] = True
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("unexpected properties" in item for item in report.errors))

    def test_duplicate_conflicting_state_decision_is_rejected(self):
        spec = valid_spec(HASH_A)
        spec["state_model"]["decisions"].append({
            "state": "FLAT", "signal": "LONG_SIGNAL", "action": "DO_NOTHING",
        })
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("exactly one decision" in item for item in report.errors))

    def test_unknown_exit_precedence_is_rejected(self):
        spec = valid_spec(HASH_A)
        spec["exit_precedence"] = ["IMPOSSIBLE_ENGINE_ORDERING"]
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("unknown precedence" in item for item in report.errors))

    def test_ranking_must_reference_canonical_metrics(self):
        for ranking in (
            {"method": "WEIGHTED", "weights": {"invented_metric": 1.0}},
            {"method": "ORDERED", "ordered_metrics": ["invented_metric"], "tie_break_rule": "fixed"},
        ):
            with self.subTest(ranking=ranking["method"]):
                protocol = valid_protocol(); protocol["ranking"] = ranking
                report = validate_evaluation_protocol(protocol)
                self.assertFalse(report.ok)
                self.assertTrue(any("unknown metric" in item for item in report.errors))

    def test_metric_source_artifact_must_be_real_contract_artifact(self):
        protocol = valid_protocol()
        protocol["metrics"][0]["source_artifact"] = "missing.bin"
        report = validate_evaluation_protocol(protocol)
        self.assertFalse(report.ok)
        self.assertTrue(any("canonical output artifact" in item for item in report.errors))

    def test_predecessor_candidate_and_variant_identity_are_immutable(self):
        predecessor = valid_registry(HASH_A)
        current = copy.deepcopy(predecessor)
        current["registry_version"] = "REG-2"
        current["created_at_utc"] = "2026-02-01T00:00:00Z"
        current["predecessor"] = {"version": "REG-1", "sha256": HASH_A}
        current["candidates"][0]["primary_source_id"] = "REWRITTEN"
        current["variants"][0]["parameter_identity_sha256"] = "b" * 64
        report = validate_candidate_registry(current, predecessor)
        self.assertFalse(report.ok)
        joined = "\n".join(report.errors)
        self.assertIn("immutable predecessor fields", joined)

    def test_conflicting_execution_exceptions_are_rejected(self):
        spec = valid_spec(HASH_A)
        spec["comparability_class"] = "COMPARABLE_WITH_DECLARED_EXECUTION_EXCEPTION"
        base = {
            "type": "EXECUTION", "rationale": "source-specific fee",
            "source_evidence": "SRC1:p12", "comparability_consequence": "downgrade",
            "approved": True, "controlled_field": "taker_fee",
        }
        spec["protocol_exceptions"] = [
            {**base, "exception_id": "E1", "effective_value": .001},
            {**base, "exception_id": "E2", "effective_value": .002},
        ]
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("conflicting exceptions" in item for item in report.errors))

    def test_historical_window_exception_requires_non_direct_comparability(self):
        spec = valid_spec(HASH_A)
        spec["protocol_exceptions"] = [{
            "exception_id": "H1", "type": "HISTORICAL_WINDOW",
            "rationale": "source period", "source_evidence": "SRC1:p12",
            "comparability_consequence": "not direct", "approved": True,
            "effective_window": {
                "start_utc": "2018-01-01T00:00:00Z",
                "end_utc": "2019-01-01T00:00:00Z",
            },
        }]
        report = validate_strategy_spec(spec, self.capability)
        self.assertFalse(report.ok)
        self.assertTrue(any("NOT_DIRECTLY_COMPARABLE" in item for item in report.errors))

    def test_exception_requires_protocol_authorization(self):
        spec = valid_spec(HASH_A)
        spec["comparability_class"] = "COMPARABLE_WITH_DECLARED_EXECUTION_EXCEPTION"
        spec["protocol_exceptions"] = [{
            "exception_id": "E1", "type": "EXECUTION",
            "rationale": "source-specific fee", "source_evidence": "SRC1:p12",
            "comparability_consequence": "downgrade", "approved": True,
            "controlled_field": "taker_fee", "effective_value": .001,
        }]
        registry = valid_registry(HASH_A)
        report = validate_freeze_inputs(
            spec, registry, valid_protocol(), self.capability, REPO_ROOT, HASH_A,
        )
        self.assertFalse(report.ok)
        self.assertTrue(any("explicit policy" in item for item in report.errors))

    def test_authorized_unique_exception_is_valid(self):
        spec = valid_spec(HASH_A)
        spec["comparability_class"] = "COMPARABLE_WITH_DECLARED_EXECUTION_EXCEPTION"
        spec["protocol_exceptions"] = [{
            "exception_id": "E1", "type": "EXECUTION",
            "rationale": "source-specific fee", "source_evidence": "SRC1:p12",
            "comparability_consequence": "downgrade", "approved": True,
            "controlled_field": "taker_fee", "effective_value": .001,
        }]
        protocol = valid_protocol()
        protocol["strategy_exception_policy"] = {
            "allowed_types": ["EXECUTION"],
            "allowed_execution_fields": ["taker_fee"],
            "historical_window_allowed": False,
        }
        report = validate_freeze_inputs(
            spec, valid_registry(HASH_A), protocol, self.capability, REPO_ROOT, HASH_A,
        )
        self.assertTrue(report.ok, report.render())


if __name__ == "__main__":
    unittest.main()
