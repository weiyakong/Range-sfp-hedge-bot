from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


HASH_LENGTH = 64
PLACEHOLDERS = {"", "-", "n/a", "na", "unknown", "tbd", "todo", "unset"}
SPEC_STATUSES = {"DRAFT", "BLOCKED", "FROZEN", "TESTED"}
CANDIDATE_STATUSES = {
    "IDENTIFIED", "SOURCE_REVIEW", "SPEC_DRAFT", "BLOCKED_SOURCE",
    "BLOCKED_DATA", "BLOCKED_ENGINE", "FROZEN", "BACKTESTED", "REJECTED",
    "ADVANCES_TO_ADAPTATION", "ABANDONED",
}
VARIANT_STATUSES = {
    "IDENTIFIED", "SPEC_DRAFT", "BLOCKED_SOURCE", "BLOCKED_DATA",
    "BLOCKED_ENGINE", "FROZEN", "BACKTESTED", "REJECTED", "ABANDONED",
}
PARAMETER_ORIGINS = {
    "SOURCE_EXACT", "SOURCE_RANGE", "DETERMINISTIC_MARKET_TRANSLATION",
    "RESEARCH_ASSUMPTION", "POST_RESULT_ADAPTATION",
}
COMPARABILITY_CLASSES = {
    "DIRECTLY_COMPARABLE",
    "COMPARABLE_WITH_DECLARED_EXECUTION_EXCEPTION",
    "NOT_DIRECTLY_COMPARABLE",
}
REQUIRED_METRICS = {
    "total_return", "expectancy_per_trade", "profit_factor", "win_rate",
    "close_to_close_max_drawdown", "intrabar_worst_max_drawdown",
    "return_to_intrabar_drawdown", "time_exposure", "turnover",
    "average_holding_time", "ambiguity_rate", "yearly_return", "sharpe",
    "sortino", "recovery_factor", "time_underwater",
}
EXECUTION_ASSUMPTIONS = {
    "maker_fee", "taker_fee", "slippage", "passive_limit_policy",
    "marketable_limit_policy", "funding_treatment", "liquidation_model",
    "end_of_data_policy",
}
EXECUTION_ORIGINS = {
    "SOURCE", "EXCHANGE", "COMMON_RESEARCH_PROTOCOL",
    "STRATEGY_SPECIFIC_ASSUMPTION",
}


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warning(self, path: str, message: str) -> None:
        self.warnings.append(f"{path}: {message}")

    def merge(self, prefix: str, other: "ValidationReport") -> None:
        self.errors.extend(f"{prefix}.{item}" for item in other.errors)
        self.warnings.extend(f"{prefix}.{item}" for item in other.warnings)

    def render(self) -> str:
        lines = ["PASS" if self.ok else "FAIL"]
        lines.extend(f"ERROR {item}" for item in self.errors)
        lines.extend(f"WARNING {item}" for item in self.warnings)
        return "\n".join(lines)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"top-level JSON value must be an object: {path}")
    return value


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite immutable receipt: {path}")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.incomplete-", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == HASH_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def _require_text(
    obj: Mapping[str, object], key: str, path: str, report: ValidationReport,
) -> Optional[str]:
    value = obj.get(key)
    if not _is_text(value):
        report.error(f"{path}.{key}", "required non-placeholder text is missing")
        return None
    return str(value)


def _require_bool(
    obj: Mapping[str, object], key: str, path: str, report: ValidationReport,
) -> Optional[bool]:
    value = obj.get(key)
    if not isinstance(value, bool):
        report.error(f"{path}.{key}", "boolean is required")
        return None
    return value


def _require_enum(
    obj: Mapping[str, object], key: str, allowed: Set[str], path: str,
    report: ValidationReport,
) -> Optional[str]:
    value = obj.get(key)
    if value not in allowed:
        report.error(f"{path}.{key}", f"must be one of {sorted(allowed)}")
        return None
    return str(value)


def _require_hash(
    obj: Mapping[str, object], key: str, path: str, report: ValidationReport,
    allow_null: bool = False,
) -> Optional[str]:
    value = obj.get(key)
    if allow_null and value is None:
        return None
    if not _is_hash(value):
        report.error(f"{path}.{key}", "lowercase SHA-256 is required")
        return None
    return str(value)


def _parse_utc(value: object, path: str, report: ValidationReport) -> Optional[datetime]:
    if not _is_text(value):
        report.error(path, "UTC timestamp is required")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        report.error(path, "invalid ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        report.error(path, "timestamp must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _objects(value: object, path: str, report: ValidationReport) -> List[Mapping[str, object]]:
    if not isinstance(value, list):
        report.error(path, "array is required")
        return []
    objects: List[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            report.error(f"{path}[{index}]", "object is required")
        else:
            objects.append(item)
    return objects


def _unique_texts(value: object, path: str, report: ValidationReport) -> List[str]:
    if not isinstance(value, list) or not value:
        report.error(path, "non-empty array is required")
        return []
    result: List[str] = []
    for index, item in enumerate(value):
        if not _is_text(item):
            report.error(f"{path}[{index}]", "non-placeholder text is required")
            continue
        result.append(str(item))
    if len(result) != len(set(result)):
        report.error(path, "values must be unique")
    return result


def compute_fidelity_summary(spec: Mapping[str, object]) -> str:
    fidelity = spec.get("fidelity")
    if not isinstance(fidelity, dict):
        return "ADAPTED"
    parameters = spec.get("parameters")
    origins = {
        item.get("origin")
        for item in parameters
        if isinstance(item, dict)
    } if isinstance(parameters, list) else set()
    proxy = spec.get("proxy")
    proxy_used = isinstance(proxy, dict) and proxy.get("used") is True
    if (
        fidelity.get("rule") == "ADAPTED"
        or fidelity.get("execution") in {"PROXY", "ADAPTED"}
        or fidelity.get("sizing") == "ADAPTED"
        or "POST_RESULT_ADAPTATION" in origins
        or proxy_used
    ):
        return "ADAPTED"
    if (
        fidelity.get("market") == "TARGET_MARKET_TRANSFER"
        or fidelity.get("timeframe") == "TIMEFRAME_TRANSFER"
        or fidelity.get("session") == "SESSION_TRANSFER"
        or fidelity.get("product") == "PRODUCT_TRANSFER"
        or fidelity.get("execution") in {"TARGET_VENUE_MAPPING", "RESEARCH_ASSUMPTION"}
        or fidelity.get("sizing") in {"STANDARDIZED_RESEARCH_OVERLAY", "ASSUMED"}
        or bool(origins & {"DETERMINISTIC_MARKET_TRANSLATION", "RESEARCH_ASSUMPTION"})
    ):
        return "TRANSFER_REPLICATION"
    return "PURE_REPLICATION"


def validate_strategy_spec(
    spec: Mapping[str, object],
    capability: Optional[Mapping[str, object]] = None,
) -> ValidationReport:
    report = ValidationReport()
    if spec.get("schema_version") != "STRATEGY_SPEC_V1":
        report.error("schema_version", "must equal STRATEGY_SPEC_V1")
    for key in ("strategy_id", "strategy_version", "candidate_id", "variant_id"):
        _require_text(spec, key, "spec", report)
    _require_enum(spec, "status", SPEC_STATUSES, "spec", report)
    _parse_utc(spec.get("created_at_utc"), "spec.created_at_utc", report)

    fidelity = spec.get("fidelity")
    if not isinstance(fidelity, dict):
        report.error("spec.fidelity", "object is required")
        fidelity = {}
    _require_enum(fidelity, "rule", {"VERBATIM", "FORMALIZED_INTERPRETATION", "ADAPTED"}, "spec.fidelity", report)
    _require_enum(fidelity, "market", {"SAME_MARKET", "TARGET_MARKET_TRANSFER"}, "spec.fidelity", report)
    _require_enum(fidelity, "timeframe", {"SAME_TIMEFRAME", "TIMEFRAME_TRANSFER"}, "spec.fidelity", report)
    _require_enum(fidelity, "session", {"SAME_SESSION", "SESSION_TRANSFER"}, "spec.fidelity", report)
    _require_enum(fidelity, "product", {"SAME_PRODUCT_TYPE", "PRODUCT_TRANSFER"}, "spec.fidelity", report)
    _require_enum(fidelity, "execution", {"SOURCE_SPECIFIED", "TARGET_VENUE_MAPPING", "RESEARCH_ASSUMPTION", "PROXY", "ADAPTED"}, "spec.fidelity", report)
    _require_enum(fidelity, "sizing", {"SOURCE_DEFINED", "STANDARDIZED_RESEARCH_OVERLAY", "ASSUMED", "ADAPTED"}, "spec.fidelity", report)
    declared = _require_enum(fidelity, "declared_summary", {"PURE_REPLICATION", "TRANSFER_REPLICATION", "ADAPTED"}, "spec.fidelity", report)
    computed = compute_fidelity_summary(spec)
    if declared is not None and declared != computed:
        report.error("spec.fidelity.declared_summary", f"declared {declared}, computed {computed}")

    parameters = _objects(spec.get("parameters"), "spec.parameters", report)
    parameter_ids: List[str] = []
    for index, parameter in enumerate(parameters):
        path = f"spec.parameters[{index}]"
        parameter_id = _require_text(parameter, "parameter_id", path, report)
        if parameter_id:
            parameter_ids.append(parameter_id)
        _require_text(parameter, "units", path, report)
        origin = _require_enum(parameter, "origin", PARAMETER_ORIGINS, path, report)
        if "value" not in parameter:
            report.error(f"{path}.value", "selected value is required")
        if origin == "SOURCE_RANGE":
            source_range = parameter.get("source_range")
            selection = parameter.get("selection")
            if not isinstance(source_range, dict):
                report.error(f"{path}.source_range", "object is required for SOURCE_RANGE")
            else:
                if "minimum" not in source_range or "maximum" not in source_range:
                    report.error(f"{path}.source_range", "minimum and maximum are required")
            if not isinstance(selection, dict):
                report.error(f"{path}.selection", "selection contract is required for SOURCE_RANGE")
            else:
                _require_text(selection, "method", f"{path}.selection", report)
                _require_text(selection, "rationale", f"{path}.selection", report)
                _parse_utc(selection.get("selected_at_utc"), f"{path}.selection.selected_at_utc", report)
                if selection.get("selected_before_historical_results") is not True:
                    report.error(f"{path}.selection.selected_before_historical_results", "must be true")
    if len(parameter_ids) != len(set(parameter_ids)):
        report.error("spec.parameters", "parameter_id values must be unique")

    proxy = spec.get("proxy")
    if not isinstance(proxy, dict):
        report.error("spec.proxy", "object is required")
        proxy = {}
    proxy_used = _require_bool(proxy, "used", "spec.proxy", report)
    if proxy_used:
        for key in ("original_behavior", "replacement_behavior", "rationale", "impact", "classification_consequence"):
            _require_text(proxy, key, "spec.proxy", report)
        if computed == "PURE_REPLICATION":
            report.error("spec.proxy", "a proxy can never be PURE_REPLICATION")

    data_manifest = spec.get("data_manifest")
    if not isinstance(data_manifest, dict):
        report.error("spec.data_manifest", "object is required")
    else:
        _require_text(data_manifest, "manifest_id", "spec.data_manifest", report)
        _require_hash(data_manifest, "sha256", "spec.data_manifest", report)

    data_inputs = _objects(spec.get("data_inputs"), "spec.data_inputs", report)
    input_by_id: Dict[str, Mapping[str, object]] = {}
    for index, data_input in enumerate(data_inputs):
        path = f"spec.data_inputs[{index}]"
        field_id = _require_text(data_input, "field_id", path, report)
        requirement = _require_enum(data_input, "requirement", {"REQUIRED", "OPTIONAL", "FORBIDDEN", "NOT_USED"}, path, report)
        availability = _require_enum(data_input, "availability", {"AVAILABLE", "NOT_AVAILABLE"}, path, report)
        for key in ("dataset_id", "source_id", "frequency", "timestamp_semantics", "units", "available_at_semantics"):
            _require_text(data_input, key, path, report)
        manifest_hash = data_input.get("manifest_sha256")
        if manifest_hash is not None and not _is_hash(manifest_hash):
            report.error(f"{path}.manifest_sha256", "must be null or a lowercase SHA-256")
        if requirement == "REQUIRED" and availability == "NOT_AVAILABLE":
            report.error(path, "REQUIRED + NOT_AVAILABLE blocks freeze")
        if field_id:
            if field_id in input_by_id:
                report.error(f"{path}.field_id", "duplicate field_id")
            input_by_id[field_id] = data_input

    implementation = spec.get("implementation")
    if not isinstance(implementation, dict):
        report.error("spec.implementation", "object is required")
        implementation = {}
    implementation_inputs = _unique_texts(implementation.get("input_ids"), "spec.implementation.input_ids", report)
    for field_id in implementation_inputs:
        declaration = input_by_id.get(field_id)
        if declaration is None:
            report.error("spec.implementation.input_ids", f"undeclared input {field_id}")
        elif declaration.get("requirement") in {"FORBIDDEN", "NOT_USED"}:
            report.error("spec.implementation.input_ids", f"input {field_id} is {declaration.get('requirement')}")
    required_ids = {
        field_id for field_id, declaration in input_by_id.items()
        if declaration.get("requirement") == "REQUIRED"
    }
    missing_required = required_ids - set(implementation_inputs)
    if missing_required:
        report.error("spec.implementation.input_ids", f"required inputs not declared by implementation: {sorted(missing_required)}")

    required_capabilities = _unique_texts(spec.get("required_capabilities"), "spec.required_capabilities", report)
    if capability is not None:
        capabilities = capability.get("capabilities")
        if not isinstance(capabilities, dict):
            report.error("capability.capabilities", "object is required")
        else:
            for capability_id in required_capabilities:
                definition = capabilities.get(capability_id)
                if not isinstance(definition, dict):
                    report.error("spec.required_capabilities", f"unknown capability {capability_id}")
                elif definition.get("supported") is not True:
                    report.error("spec.required_capabilities", f"BLOCKED_UNSUPPORTED_ENGINE_CAPABILITY: {capability_id}")

    ambiguities = _objects(spec.get("ambiguities"), "spec.ambiguities", report)
    for index, ambiguity in enumerate(ambiguities):
        path = f"spec.ambiguities[{index}]"
        _require_text(ambiguity, "ambiguity_id", path, report)
        material = _require_bool(ambiguity, "material", path, report)
        resolution = _require_enum(ambiguity, "resolution", {"UNRESOLVED", "SOURCE_CLARIFIED", "PREDECLARED_INTERPRETATION", "NOT_REQUIRED"}, path, report)
        _require_text(ambiguity, "materiality_rationale", path, report)
        if material and resolution == "UNRESOLVED":
            report.error(path, "material ambiguity is unresolved")

    state_model = spec.get("state_model")
    if not isinstance(state_model, dict):
        report.error("spec.state_model", "object is required")
    else:
        states = set(_unique_texts(state_model.get("reachable_states"), "spec.state_model.reachable_states", report))
        signals = set(_unique_texts(state_model.get("signals_events"), "spec.state_model.signals_events", report))
        pairs = _objects(state_model.get("reachable_pairs"), "spec.state_model.reachable_pairs", report)
        decisions = _objects(state_model.get("decisions"), "spec.state_model.decisions", report)
        required_pairs: Set[Tuple[str, str]] = set()
        for index, pair in enumerate(pairs):
            state = _require_text(pair, "state", f"spec.state_model.reachable_pairs[{index}]", report)
            signal = _require_text(pair, "signal", f"spec.state_model.reachable_pairs[{index}]", report)
            if state and state not in states:
                report.error(f"spec.state_model.reachable_pairs[{index}].state", "state is not declared reachable")
            if signal and signal not in signals:
                report.error(f"spec.state_model.reachable_pairs[{index}].signal", "signal/event is not declared")
            if state and signal:
                required_pairs.add((state, signal))
        mapped_pairs: Set[Tuple[str, str]] = set()
        for index, decision in enumerate(decisions):
            state = _require_text(decision, "state", f"spec.state_model.decisions[{index}]", report)
            signal = _require_text(decision, "signal", f"spec.state_model.decisions[{index}]", report)
            _require_text(decision, "action", f"spec.state_model.decisions[{index}]", report)
            if state and signal:
                mapped_pairs.add((state, signal))
        missing_pairs = required_pairs - mapped_pairs
        if missing_pairs:
            report.error("spec.state_model.decisions", f"missing reachable state/signal decisions: {sorted(missing_pairs)}")
        extra_pairs = mapped_pairs - required_pairs
        if extra_pairs:
            report.error("spec.state_model.decisions", f"decisions not declared reachable: {sorted(extra_pairs)}")

    _unique_texts(spec.get("exit_precedence"), "spec.exit_precedence", report)
    tests = spec.get("tests")
    if not isinstance(tests, dict):
        report.error("spec.tests", "object is required")
    else:
        synthetic = tests.get("synthetic")
        if not isinstance(synthetic, dict):
            report.error("spec.tests.synthetic", "object is required")
        else:
            for test_type in ("positive", "negative", "boundary", "causality"):
                if synthetic.get(test_type) != "PASS":
                    report.error(f"spec.tests.synthetic.{test_type}", "must equal PASS")
        _require_enum(tests, "golden_examples", {"PASS", "NOT_APPLICABLE_NO_SOURCE_EXAMPLES"}, "spec.tests", report)
        _unique_texts(tests.get("test_ids"), "spec.tests.test_ids", report)

    traceability = _objects(spec.get("traceability"), "spec.traceability", report)
    if not traceability:
        report.error("spec.traceability", "at least one rule trace is required")
    for index, trace in enumerate(traceability):
        path = f"spec.traceability[{index}]"
        for key in ("rule_id", "source_evidence", "interpretation", "executable_rule", "test_id", "code_path", "code_symbol", "implementation_version"):
            _require_text(trace, key, path, report)
        implementation_hash = trace.get("implementation_sha256")
        if implementation_hash is not None and not _is_hash(implementation_hash):
            report.error(f"{path}.implementation_sha256", "must be null or a lowercase SHA-256")

    source = spec.get("source_evidence")
    if not isinstance(source, dict):
        report.error("spec.source_evidence", "object is required")
    else:
        for key in ("primary_source_id", "reference", "edition_version", "exact_locator", "knowledge_cutoff_date"):
            _require_text(source, key, "spec.source_evidence", report)
        _require_hash(source, "evidence_sha256", "spec.source_evidence", report)

    comparability = _require_enum(spec, "comparability_class", COMPARABILITY_CLASSES, "spec", report)
    exceptions = _objects(spec.get("protocol_exceptions"), "spec.protocol_exceptions", report)
    for index, exception in enumerate(exceptions):
        path = f"spec.protocol_exceptions[{index}]"
        exception_type = _require_enum(exception, "type", {"HISTORICAL_WINDOW", "EXECUTION", "OTHER"}, path, report)
        for key in ("exception_id", "rationale", "source_evidence", "comparability_consequence"):
            _require_text(exception, key, path, report)
        if exception_type == "EXECUTION" and comparability == "DIRECTLY_COMPARABLE":
            report.error(path, "execution exception requires a comparability downgrade")
    if spec.get("outcome_bearing_historical_run_seen") is not False:
        report.error("spec.outcome_bearing_historical_run_seen", "must be false at freeze")
    return report


def validate_candidate_registry(registry: Mapping[str, object]) -> ValidationReport:
    report = ValidationReport()
    if registry.get("schema_version") != "CANDIDATE_REGISTRY_V1":
        report.error("schema_version", "must equal CANDIDATE_REGISTRY_V1")
    _require_text(registry, "registry_version", "registry", report)
    _require_enum(registry, "status", {"DRAFT", "FROZEN"}, "registry", report)
    _require_text(registry, "universe_definition", "registry", report)
    if registry.get("intake_required_before_substantive_review") is not True:
        report.error("registry.intake_required_before_substantive_review", "must be true")
    candidates = _objects(registry.get("candidates"), "registry.candidates", report)
    candidate_ids: Set[str] = set()
    candidate_intake: Dict[str, datetime] = {}
    for index, candidate in enumerate(candidates):
        path = f"registry.candidates[{index}]"
        candidate_id = _require_text(candidate, "candidate_id", path, report)
        for key in ("strategy_name", "primary_source_id", "primary_source_reference", "inclusion_reason"):
            _require_text(candidate, key, path, report)
        current_status = _require_enum(candidate, "current_status", CANDIDATE_STATUSES, path, report)
        intake = _parse_utc(candidate.get("intake_timestamp_utc"), f"{path}.intake_timestamp_utc", report)
        history = _objects(candidate.get("status_history"), f"{path}.status_history", report)
        if not history:
            report.error(f"{path}.status_history", "non-empty status history is required")
        else:
            history_statuses: List[str] = []
            history_times: List[datetime] = []
            for history_index, event in enumerate(history):
                event_path = f"{path}.status_history[{history_index}]"
                status = _require_enum(event, "status", CANDIDATE_STATUSES, event_path, report)
                timestamp = _parse_utc(event.get("timestamp_utc"), f"{event_path}.timestamp_utc", report)
                _require_text(event, "reason", event_path, report)
                if status:
                    history_statuses.append(status)
                if timestamp:
                    history_times.append(timestamp)
            if history_statuses and history_statuses[0] != "IDENTIFIED":
                report.error(f"{path}.status_history", "first status must be IDENTIFIED")
            if history_statuses and current_status and history_statuses[-1] != current_status:
                report.error(f"{path}.status_history", "last status must equal current_status")
            if history_times != sorted(history_times):
                report.error(f"{path}.status_history", "timestamps must be chronological")
            if intake and history_times and intake != history_times[0]:
                report.error(f"{path}.intake_timestamp_utc", "must equal first IDENTIFIED timestamp")
        exclusion = candidate.get("exclusion_reason")
        if current_status in {"REJECTED", "ABANDONED", "BLOCKED_SOURCE", "BLOCKED_DATA", "BLOCKED_ENGINE"} and not _is_text(exclusion):
            report.error(f"{path}.exclusion_reason", "required for rejected/blocked/abandoned candidate")
        if candidate_id:
            if candidate_id in candidate_ids:
                report.error(f"{path}.candidate_id", "duplicate candidate_id")
            candidate_ids.add(candidate_id)
            if intake:
                candidate_intake[candidate_id] = intake

    variants = _objects(registry.get("variants"), "registry.variants", report)
    variant_ids: Set[str] = set()
    valid_parents = set(candidate_ids)
    for index, variant in enumerate(variants):
        path = f"registry.variants[{index}]"
        variant_id = _require_text(variant, "variant_id", path, report)
        candidate_id = _require_text(variant, "candidate_id", path, report)
        parent_id = _require_text(variant, "parent_id", path, report)
        created = _parse_utc(variant.get("created_at_utc"), f"{path}.created_at_utc", report)
        _require_enum(variant, "type", {"PURE_REPLICATION", "TRANSFER_REPLICATION", "ADAPTED"}, path, report)
        _require_enum(variant, "status", VARIANT_STATUSES, path, report)
        _require_text(variant, "exact_change", path, report)
        if not isinstance(variant.get("parameter_changes"), list):
            report.error(f"{path}.parameter_changes", "array is required")
        if not isinstance(variant.get("search_space"), dict):
            report.error(f"{path}.search_space", "object is required")
        if not isinstance(variant.get("historical_results_observed_before_creation"), list):
            report.error(f"{path}.historical_results_observed_before_creation", "array is required")
        spec_hash = variant.get("spec_sha256")
        if spec_hash is not None and not _is_hash(spec_hash):
            report.error(f"{path}.spec_sha256", "must be null or a lowercase SHA-256")
        if candidate_id and candidate_id not in candidate_ids:
            report.error(f"{path}.candidate_id", "candidate is absent from registry")
        if parent_id and parent_id not in valid_parents:
            report.error(f"{path}.parent_id", "parent must be an existing candidate or earlier variant")
        if candidate_id and created and candidate_id in candidate_intake and created < candidate_intake[candidate_id]:
            report.error(f"{path}.created_at_utc", "variant predates candidate intake")
        if variant_id:
            if variant_id in variant_ids:
                report.error(f"{path}.variant_id", "duplicate variant_id")
            variant_ids.add(variant_id)
            valid_parents.add(variant_id)
    return report


def derived_registry_counts(registry: Mapping[str, object]) -> Dict[str, int]:
    candidates = [item for item in registry.get("candidates", []) if isinstance(item, dict)] if isinstance(registry.get("candidates"), list) else []
    variants = [item for item in registry.get("variants", []) if isinstance(item, dict)] if isinstance(registry.get("variants"), list) else []
    return {
        "candidates_identified": len(candidates),
        "candidates_backtested": sum(item.get("current_status") == "BACKTESTED" for item in candidates),
        "candidates_blocked": sum(str(item.get("current_status", "")).startswith("BLOCKED_") for item in candidates),
        "candidates_rejected": sum(item.get("current_status") == "REJECTED" for item in candidates),
        "variants_total": len(variants),
        "variants_backtested": sum(item.get("status") == "BACKTESTED" for item in variants),
        "adaptations": sum(item.get("type") == "ADAPTED" for item in variants),
    }


def validate_evaluation_protocol(protocol: Mapping[str, object]) -> ValidationReport:
    report = ValidationReport()
    if protocol.get("schema_version") != "EVALUATION_PROTOCOL_V1":
        report.error("schema_version", "must equal EVALUATION_PROTOCOL_V1")
    _require_text(protocol, "protocol_version", "protocol", report)
    _require_enum(protocol, "status", {"DRAFT", "FROZEN"}, "protocol", report)
    universe = protocol.get("candidate_universe")
    if not isinstance(universe, dict):
        report.error("protocol.candidate_universe", "object is required")
    else:
        _require_text(universe, "registry_version", "protocol.candidate_universe", report)
        if universe.get("frozen_before_candidate_results") is not True:
            report.error("protocol.candidate_universe.frozen_before_candidate_results", "must be true")
    window = protocol.get("historical_window")
    if not isinstance(window, dict):
        report.error("protocol.historical_window", "object is required")
    else:
        start = _parse_utc(window.get("start_utc"), "protocol.historical_window.start_utc", report)
        end = _parse_utc(window.get("end_utc"), "protocol.historical_window.end_utc", report)
        if start and end and start >= end:
            report.error("protocol.historical_window", "start must precede end")
        if window.get("frozen_before_any_outcome_bearing_run") is not True:
            report.error("protocol.historical_window.frozen_before_any_outcome_bearing_run", "must be true")
        _require_text(window, "timezone", "protocol.historical_window", report)
        _require_text(window, "role", "protocol.historical_window", report)
    assumptions = protocol.get("execution_assumptions")
    if not isinstance(assumptions, dict):
        report.error("protocol.execution_assumptions", "object is required")
    else:
        missing = EXECUTION_ASSUMPTIONS - set(assumptions)
        extra = set(assumptions) - EXECUTION_ASSUMPTIONS
        if missing:
            report.error("protocol.execution_assumptions", f"missing assumptions: {sorted(missing)}")
        if extra:
            report.error("protocol.execution_assumptions", f"unknown assumptions: {sorted(extra)}")
        for name, assumption in assumptions.items():
            if not isinstance(assumption, dict):
                report.error(f"protocol.execution_assumptions.{name}", "object is required")
                continue
            if "value" not in assumption:
                report.error(f"protocol.execution_assumptions.{name}.value", "value is required")
            _require_enum(assumption, "origin", EXECUTION_ORIGINS, f"protocol.execution_assumptions.{name}", report)
    eligibility = protocol.get("eligibility")
    required_gates = {
        "candidate_registered", "protocol_frozen", "spec_valid", "spec_frozen",
        "no_material_ambiguity", "required_data_available", "engine_compatible",
        "synthetic_causality_tests_pass", "lineage_complete", "historical_window_frozen",
    }
    if not isinstance(eligibility, dict):
        report.error("protocol.eligibility", "object is required")
    else:
        for gate in required_gates:
            if eligibility.get(gate) is not True:
                report.error(f"protocol.eligibility.{gate}", "must be true")
        statuses = eligibility.get("allowed_v2_qa_statuses")
        if statuses != ["VERIFIED"]:
            report.error("protocol.eligibility.allowed_v2_qa_statuses", "production research permits only ['VERIFIED']")
    ranking = protocol.get("ranking")
    if not isinstance(ranking, dict):
        report.error("protocol.ranking", "object is required")
    else:
        method = _require_enum(ranking, "method", {"UNSET", "ORDERED", "WEIGHTED", "NO_SCALAR"}, "protocol.ranking", report)
        if method == "UNSET":
            report.error("protocol.ranking.method", "UNSET blocks protocol freeze")
        elif method == "ORDERED":
            _unique_texts(ranking.get("ordered_metrics"), "protocol.ranking.ordered_metrics", report)
            _require_text(ranking, "tie_break_rule", "protocol.ranking", report)
        elif method == "WEIGHTED":
            weights = ranking.get("weights")
            if not isinstance(weights, dict) or not weights:
                report.error("protocol.ranking.weights", "non-empty object is required")
            elif abs(sum(value for value in weights.values() if isinstance(value, (int, float))) - 1.0) > 1e-12 or any(not isinstance(value, (int, float)) for value in weights.values()):
                report.error("protocol.ranking.weights", "numeric weights must sum to 1")
        elif method == "NO_SCALAR":
            _require_text(ranking, "advancement_rule", "protocol.ranking", report)
    metrics = _objects(protocol.get("metrics"), "protocol.metrics", report)
    metric_names: Set[str] = set()
    for index, metric in enumerate(metrics):
        path = f"protocol.metrics[{index}]"
        name = _require_text(metric, "name", path, report)
        for key in ("formula", "units", "denominator", "source_artifact", "applicability"):
            _require_text(metric, key, path, report)
        if name:
            metric_names.add(name)
        if name in {"sharpe", "sortino"}:
            _require_text(metric, "return_series_methodology", path, report)
    missing_metrics = REQUIRED_METRICS - metric_names
    if missing_metrics:
        report.error("protocol.metrics", f"missing required metric definitions: {sorted(missing_metrics)}")
    if protocol.get("time_exposure_definition") != "ANY_POSITION_ACTIVE_DURING_BAR_FRACTION":
        report.error("protocol.time_exposure_definition", "must explicitly select ANY_POSITION_ACTIVE_DURING_BAR_FRACTION")
    protected = protocol.get("protected_validation")
    if not isinstance(protected, dict):
        report.error("protocol.protected_validation", "object is required")
    else:
        if protected.get("policy_frozen_before_first_selection_result") is not True:
            report.error("protocol.protected_validation.policy_frozen_before_first_selection_result", "must be true")
        if protected.get("data_excluded_from_initial_selection_and_formalization") is not True:
            report.error("protocol.protected_validation.data_excluded_from_initial_selection_and_formalization", "must be true")
        _require_text(protected, "finalist_evaluation_rule", "protocol.protected_validation", report)
    multiple = protocol.get("multiple_testing")
    if not isinstance(multiple, dict):
        report.error("protocol.multiple_testing", "object is required")
    else:
        for key in ("disclose_candidate_count", "disclose_variant_count", "retain_failures", "protected_finalist_stage"):
            if multiple.get(key) is not True:
                report.error(f"protocol.multiple_testing.{key}", "must be true")
        _require_text(multiple, "selection_bias_disclosure_rule", "protocol.multiple_testing", report)
    return report


def validate_capability_manifest(
    capability: Mapping[str, object], repo_root: Path,
) -> ValidationReport:
    report = ValidationReport()
    if capability.get("schema_version") != "BACKTESTER_CAPABILITIES_V1":
        report.error("schema_version", "must equal BACKTESTER_CAPABILITIES_V1")
    _require_text(capability, "manifest_version", "capability", report)
    _require_text(capability, "audited_base_commit", "capability", report)
    engine_path_value = _require_text(capability, "execution_engine_path", "capability", report)
    engine_hash = _require_hash(capability, "execution_engine_sha256", "capability", report)
    if engine_path_value and engine_hash:
        engine_path = repo_root / engine_path_value
        if not engine_path.is_file():
            report.error("capability.execution_engine_path", "engine file does not exist")
        elif sha256_file(engine_path) != engine_hash:
            report.error("capability.execution_engine_sha256", "actual engine hash does not match capability manifest")
    capabilities = capability.get("capabilities")
    if not isinstance(capabilities, dict):
        report.error("capability.capabilities", "object is required")
    else:
        expected_unsupported = {
            "stop_entry", "same_side_pyramiding", "partial_exits",
            "multiple_take_profit", "trailing_stop",
            "multiple_same_side_pending_orders", "dynamic_order_amendment",
            "same_bar_strategy_callback_reentry", "native_limit_exit",
            "exact_queue_partial_fill_microstructure",
        }
        for capability_id in expected_unsupported:
            definition = capabilities.get(capability_id)
            if not isinstance(definition, dict) or definition.get("supported") is not False:
                report.error(f"capability.capabilities.{capability_id}", "must be explicitly unsupported")
    return report


def _find_candidate(registry: Mapping[str, object], candidate_id: object) -> Optional[Mapping[str, object]]:
    candidates = registry.get("candidates")
    if not isinstance(candidates, list):
        return None
    return next((item for item in candidates if isinstance(item, dict) and item.get("candidate_id") == candidate_id), None)


def _find_variant(registry: Mapping[str, object], variant_id: object) -> Optional[Mapping[str, object]]:
    variants = registry.get("variants")
    if not isinstance(variants, list):
        return None
    return next((item for item in variants if isinstance(item, dict) and item.get("variant_id") == variant_id), None)


def validate_freeze_inputs(
    spec: Mapping[str, object], registry: Mapping[str, object],
    protocol: Mapping[str, object], capability: Mapping[str, object],
    repo_root: Path, spec_sha256: Optional[str] = None,
) -> ValidationReport:
    report = ValidationReport()
    report.merge("spec", validate_strategy_spec(spec, capability))
    report.merge("registry", validate_candidate_registry(registry))
    report.merge("protocol", validate_evaluation_protocol(protocol))
    report.merge("capability", validate_capability_manifest(capability, repo_root))
    if spec.get("status") != "FROZEN":
        report.error("spec.status", "must be FROZEN before a freeze receipt can be issued")
    if registry.get("status") != "FROZEN":
        report.error("registry.status", "must be FROZEN")
    if protocol.get("status") != "FROZEN":
        report.error("protocol.status", "must be FROZEN")
    candidate = _find_candidate(registry, spec.get("candidate_id"))
    if candidate is None:
        report.error("registry.candidates", "candidate is absent from registry")
    elif candidate.get("current_status") != "FROZEN":
        report.error("registry.candidate.current_status", "candidate must be FROZEN")
    variant = _find_variant(registry, spec.get("variant_id"))
    if variant is None:
        report.error("registry.variants", "variant is absent from registry")
    else:
        if variant.get("candidate_id") != spec.get("candidate_id"):
            report.error("registry.variant.candidate_id", "does not match strategy spec")
        if variant.get("status") != "FROZEN":
            report.error("registry.variant.status", "variant must be FROZEN")
        if spec_sha256 is not None and variant.get("spec_sha256") != spec_sha256:
            report.error("registry.variant.spec_sha256", "does not match strategy spec bytes")
    universe = protocol.get("candidate_universe")
    if isinstance(universe, dict) and universe.get("registry_version") != registry.get("registry_version"):
        report.error("protocol.candidate_universe.registry_version", "does not match registry")
    return report


def _git_commit(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True,
        capture_output=True, text=True,
    )
    return completed.stdout.strip()


def create_freeze_receipt(
    *, spec_path: Path, registry_path: Path, protocol_path: Path,
    capability_path: Path, data_manifest_path: Path, repo_root: Path,
    receipt_path: Path, strategy_code_path: Optional[Path] = None,
) -> Tuple[ValidationReport, Optional[Dict[str, object]]]:
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    capability = load_json(capability_path)
    spec_hash = sha256_file(spec_path)
    report = validate_freeze_inputs(
        spec, registry, protocol, capability, repo_root, spec_hash,
    )
    data_manifest_hash = sha256_file(data_manifest_path)
    declared_manifest = spec.get("data_manifest")
    if not isinstance(declared_manifest, dict) or declared_manifest.get("sha256") != data_manifest_hash:
        report.error("spec.data_manifest.sha256", "does not match supplied data manifest")
    strategy_code_hash = sha256_file(strategy_code_path) if strategy_code_path else None
    if not report.ok:
        return report, None
    now = datetime.now(timezone.utc).isoformat()
    git_commit = _git_commit(repo_root)
    receipt: Dict[str, object] = {
        "schema_version": "FREEZE_RECEIPT_V1",
        "strategy_id": spec["strategy_id"],
        "strategy_version": spec["strategy_version"],
        "candidate_id": spec["candidate_id"],
        "variant_id": spec["variant_id"],
        "frozen_at_utc": now,
        "git_commit": git_commit,
        "strategy_spec_sha256": spec_hash,
        "candidate_registry": {
            "version": registry["registry_version"],
            "sha256": sha256_file(registry_path),
        },
        "evaluation_protocol": {
            "version": protocol["protocol_version"],
            "sha256": sha256_file(protocol_path),
        },
        "engine_capability_manifest_sha256": sha256_file(capability_path),
        "backtester_commit": git_commit,
        "data_manifest_sha256": data_manifest_hash,
        "strategy_code_sha256": strategy_code_hash,
        "computed_fidelity_classification": compute_fidelity_summary(spec),
        "validation": {"status": "PASS", "errors": []},
        "unresolved_counts": {"material_ambiguities": 0, "unsupported_capabilities": 0},
    }
    atomic_write_json(receipt_path, receipt)
    return report, receipt


def validate_freeze_receipt(
    receipt: Mapping[str, object], *, spec_path: Path, registry_path: Path,
    protocol_path: Path, capability_path: Path, data_manifest_path: Path,
) -> ValidationReport:
    report = ValidationReport()
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    if receipt.get("schema_version") != "FREEZE_RECEIPT_V1":
        report.error("receipt.schema_version", "must equal FREEZE_RECEIPT_V1")
    expected_hashes = {
        "strategy_spec_sha256": sha256_file(spec_path),
        "engine_capability_manifest_sha256": sha256_file(capability_path),
        "data_manifest_sha256": sha256_file(data_manifest_path),
    }
    for key, expected in expected_hashes.items():
        if receipt.get(key) != expected:
            report.error(f"receipt.{key}", "frozen artifact was modified or hash is invalid")
    for key in ("strategy_id", "strategy_version", "candidate_id", "variant_id"):
        if receipt.get(key) != spec.get(key):
            report.error(f"receipt.{key}", "does not match frozen strategy spec")
    nested = (
        ("candidate_registry", registry_path),
        ("evaluation_protocol", protocol_path),
    )
    for key, path in nested:
        identity = receipt.get(key)
        if not isinstance(identity, dict) or identity.get("sha256") != sha256_file(path):
            report.error(f"receipt.{key}.sha256", "artifact hash mismatch")
    registry_identity = receipt.get("candidate_registry")
    if isinstance(registry_identity, dict) and registry_identity.get("version") != registry.get("registry_version"):
        report.error("receipt.candidate_registry.version", "registry version mismatch")
    protocol_identity = receipt.get("evaluation_protocol")
    if isinstance(protocol_identity, dict) and protocol_identity.get("version") != protocol.get("protocol_version"):
        report.error("receipt.evaluation_protocol.version", "protocol version mismatch")
    if receipt.get("computed_fidelity_classification") != compute_fidelity_summary(spec):
        report.error("receipt.computed_fidelity_classification", "fidelity mismatch")
    code_hash = receipt.get("strategy_code_sha256")
    if code_hash is not None and not _is_hash(code_hash):
        report.error("receipt.strategy_code_sha256", "must be null or lowercase SHA-256")
    validation = receipt.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "PASS":
        report.error("receipt.validation.status", "must equal PASS")
    unresolved = receipt.get("unresolved_counts")
    if not isinstance(unresolved, dict) or any(value != 0 for value in unresolved.values()):
        report.error("receipt.unresolved_counts", "all unresolved counts must be zero")
    return report


def validate_production_preflight(
    *, receipt_path: Path, spec_path: Path, registry_path: Path,
    protocol_path: Path, capability_path: Path, data_manifest_path: Path,
    strategy_code_path: Path, repo_root: Path,
) -> ValidationReport:
    report = ValidationReport()
    if not receipt_path.is_file():
        report.error("freeze_receipt", "valid freeze receipt is required; declared FROZEN is insufficient")
        return report
    receipt = load_json(receipt_path)
    report.merge("receipt", validate_freeze_receipt(
        receipt, spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path,
    ))
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    capability = load_json(capability_path)
    report.merge("freeze_inputs", validate_freeze_inputs(
        spec, registry, protocol, capability, repo_root, sha256_file(spec_path),
    ))
    if not strategy_code_path.is_file():
        report.error("strategy_code", "exact strategy implementation is required for production")
    else:
        code_hash = sha256_file(strategy_code_path)
        frozen_code_hash = receipt.get("strategy_code_sha256")
        if frozen_code_hash is not None and frozen_code_hash != code_hash:
            report.error("strategy_code", "strategy code differs from freeze receipt")
    return report


def _verify_output_manifest(output_dir: Path, manifest: Mapping[str, object]) -> ValidationReport:
    report = ValidationReport()
    if manifest.get("status") != "COMPLETE":
        report.error("output_manifest.status", "must equal COMPLETE")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict):
        report.error("output_manifest.checksums", "object is required")
        return report
    for name, expected in checksums.items():
        path = output_dir / str(name)
        if not path.is_file():
            report.error(f"output_manifest.checksums.{name}", "artifact is missing")
        elif not _is_hash(expected) or sha256_file(path) != expected:
            report.error(f"output_manifest.checksums.{name}", "artifact checksum mismatch")
    return report


def validate_run_lineage(
    *, output_dir: Path, freeze_receipt_path: Path, spec_path: Path,
    registry_path: Path, protocol_path: Path, capability_path: Path,
    data_manifest_path: Path, strategy_code_path: Path,
) -> ValidationReport:
    report = ValidationReport()
    receipt = load_json(freeze_receipt_path)
    report.merge("freeze_receipt", validate_freeze_receipt(
        receipt, spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path,
    ))
    manifest_path = output_dir / "manifest.json"
    metadata_path = output_dir / "run_metadata.json"
    config_path = output_dir / "config.json"
    for path in (manifest_path, metadata_path, config_path, strategy_code_path):
        if not path.is_file():
            report.error(str(path), "required lineage artifact is missing")
    if not manifest_path.is_file() or not metadata_path.is_file():
        return report
    manifest = load_json(manifest_path)
    metadata = load_json(metadata_path)
    report.merge("output", _verify_output_manifest(output_dir, manifest))
    if manifest.get("run_id") != metadata.get("run_id"):
        report.error("run_id", "output manifest and metadata disagree")
    lineage = metadata.get("replication_lineage")
    if not isinstance(lineage, dict):
        report.error("run_metadata.replication_lineage", "production lineage is required")
        return report
    expected = {
        "candidate_id": receipt.get("candidate_id"),
        "variant_id": receipt.get("variant_id"),
        "registry_sha256": receipt.get("candidate_registry", {}).get("sha256") if isinstance(receipt.get("candidate_registry"), dict) else None,
        "protocol_sha256": receipt.get("evaluation_protocol", {}).get("sha256") if isinstance(receipt.get("evaluation_protocol"), dict) else None,
        "strategy_spec_sha256": sha256_file(spec_path),
        "strategy_code_sha256": sha256_file(strategy_code_path),
        "capability_manifest_sha256": sha256_file(capability_path),
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "freeze_receipt_sha256": sha256_file(freeze_receipt_path),
        "registry_version": receipt.get("candidate_registry", {}).get("version") if isinstance(receipt.get("candidate_registry"), dict) else None,
        "protocol_version": receipt.get("evaluation_protocol", {}).get("version") if isinstance(receipt.get("evaluation_protocol"), dict) else None,
        "fidelity_classification": compute_fidelity_summary(load_json(spec_path)),
        "comparability_class": load_json(spec_path).get("comparability_class"),
    }
    for key, value in expected.items():
        if lineage.get(key) != value:
            report.error(f"run_metadata.replication_lineage.{key}", "lineage mismatch")
    protocol = load_json(protocol_path)
    eligibility = protocol.get("eligibility")
    allowed_statuses = eligibility.get("allowed_v2_qa_statuses", []) if isinstance(eligibility, dict) else []
    if metadata.get("qa_status") not in allowed_statuses:
        report.error("run_metadata.qa_status", f"unacceptable V2 QA status: {metadata.get('qa_status')}")
    code = metadata.get("code")
    if not isinstance(code, dict) or lineage.get("backtester_commit") != code.get("git_commit"):
        report.error("run_metadata.replication_lineage.backtester_commit", "does not match executed-code commit")
    if config_path.is_file() and lineage.get("config_sha256") != sha256_file(config_path):
        report.error("run_metadata.replication_lineage.config_sha256", "config hash mismatch")
    return report


def create_run_receipt(
    *, output_dir: Path, freeze_receipt_path: Path, spec_path: Path,
    registry_path: Path, protocol_path: Path, capability_path: Path,
    data_manifest_path: Path, strategy_code_path: Path, receipt_path: Path,
) -> Tuple[ValidationReport, Optional[Dict[str, object]]]:
    report = validate_run_lineage(
        output_dir=output_dir, freeze_receipt_path=freeze_receipt_path,
        spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, strategy_code_path=strategy_code_path,
    )
    if not report.ok:
        return report, None
    metadata = load_json(output_dir / "run_metadata.json")
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    lineage = metadata["replication_lineage"]
    assert isinstance(lineage, dict)
    receipt: Dict[str, object] = {
        "schema_version": "RUN_RECEIPT_V1",
        "run_id": metadata["run_id"],
        "candidate_id": spec["candidate_id"],
        "variant_id": spec["variant_id"],
        "spec_sha256": sha256_file(spec_path),
        "registry": {"version": registry["registry_version"], "sha256": sha256_file(registry_path)},
        "protocol": {"version": protocol["protocol_version"], "sha256": sha256_file(protocol_path)},
        "strategy_code_sha256": sha256_file(strategy_code_path),
        "backtester_commit": lineage["backtester_commit"],
        "capability_manifest_sha256": sha256_file(capability_path),
        "config_sha256": sha256_file(output_dir / "config.json"),
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "output_manifest_sha256": sha256_file(output_dir / "manifest.json"),
        "tested_start": metadata["data"]["tested_start"],
        "tested_end": metadata["data"]["tested_end"],
        "run_qa_status": metadata["qa_status"],
        "fidelity_classification": compute_fidelity_summary(spec),
        "comparability_class": spec["comparability_class"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(receipt_path, receipt)
    return report, receipt
