from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from research.backtester_v2.models import PRODUCTION_OUTPUT_ARTIFACTS


HASH_LENGTH = 64
GIT_SHA_LENGTH = 40
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
    "end_of_data_policy", "margin_mode", "leverage", "liquidation_enabled",
    "liquidation_fee", "intrabar_policy",
}
EXECUTION_ORIGINS = {
    "SOURCE", "EXCHANGE", "COMMON_RESEARCH_PROTOCOL",
    "STRATEGY_SPECIFIC_ASSUMPTION",
}
RUN_STAGES = {
    "DEVELOPMENT", "COMPARISON", "PROTECTED_VALIDATION",
    "ADAPTATION_VALIDATION", "SYNTHETIC", "SMOKE",
}
PRODUCTION_STAGES = {
    "COMPARISON", "PROTECTED_VALIDATION", "ADAPTATION_VALIDATION",
}
CANONICAL_CAPABILITY_RELATIVE_PATH = Path(
    "research/strategy_replications/capability/backtester_v2_capabilities.json"
)
CANONICAL_REPOSITORY_NAME = "Range-sfp-hedge-bot"
EXPECTED_CAPABILITY_VERSION = "BACKTESTER_V2_EXECUTION_CONTRACT_2"
AUDITED_BASE_COMMIT = "2b096ebf52928248ad2e608be685bef37a7d6887"
CONTROLLED_CAPABILITIES = {
    "market_entry", "next_bar_market_execution", "passive_limit_entry",
    "marketable_limit_entry", "limit_fill_touch", "limit_fill_strict_through",
    "gtc", "ioc", "cancel_pending_per_side", "maximum_one_pending_order_per_side",
    "simultaneous_long_short", "cross_margin", "one_static_stop_loss_per_position",
    "one_static_take_profit_per_position", "conservative_dual_ohlc_path",
    "supplied_funding_input", "mark_price_liquidation_with_supplied_data",
    "stop_entry", "same_side_pyramiding", "partial_exits", "multiple_take_profit",
    "trailing_stop", "multiple_same_side_pending_orders", "dynamic_order_amendment",
    "same_bar_strategy_callback_reentry", "native_limit_exit",
    "exact_queue_partial_fill_microstructure",
}
EXECUTION_CRITICAL_PATHS = (
    "research/backtester_v2/models.py",
    "research/backtester_v2/engine.py",
    "research/backtester_v2/metrics.py",
)
MANDATORY_OUTPUT_ARTIFACTS = set(PRODUCTION_OUTPUT_ARTIFACTS)
METRIC_OUTPUT_KEYS = {
    "total_return": "total_return",
    "expectancy_per_trade": "expectancy_per_trade",
    "profit_factor": "profit_factor",
    "win_rate": "win_rate",
    "close_to_close_max_drawdown": "close_to_close_max_drawdown",
    "intrabar_worst_max_drawdown": "intrabar_worst_max_drawdown",
    "return_to_intrabar_drawdown": "return_to_intrabar_drawdown",
    "time_exposure": "time_exposure",
    "turnover": "turnover",
    "average_holding_time": "average_holding_time",
    "ambiguity_rate": "ambiguity_rate",
    "yearly_return": "yearly_return",
    "sharpe": "sharpe",
    "sortino": "sortino",
    "recovery_factor": "recovery_factor",
    "time_underwater": "time_underwater",
}


_PREFLIGHT_SEAL = object()


@dataclass(frozen=True)
class VerifiedPreflightContext:
    """Opaque in-process proof that production inputs were validated together."""

    run_stage: str
    repo_root: str
    strategy_code_path: str
    data_manifest_path: str
    git_commit: str
    expected_start: int
    expected_end: int
    expected_config: Mapping[str, object]
    identities: Mapping[str, str]
    qa_dimensions: Mapping[str, str]
    _seal: object = field(repr=False, compare=False, default=None)

    def is_authentic(self) -> bool:
        return self._seal is _PREFLIGHT_SEAL


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
        value = json.load(
            handle,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {token}: {path}")
            ),
        )
    if not isinstance(value, dict):
        raise ValueError(f"top-level JSON value must be an object: {path}")
    return value


def _reject_unexpected(
    obj: Mapping[str, object], allowed: Set[str], path: str,
    report: ValidationReport,
) -> None:
    unexpected = set(obj) - allowed
    if unexpected:
        report.error(path, f"unexpected properties: {sorted(unexpected)}")


def _is_git_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == GIT_SHA_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _timestamp_ms(value: object, path: str, report: ValidationReport) -> Optional[int]:
    parsed = _parse_utc(value, path, report)
    return int(parsed.timestamp() * 1000) if parsed is not None else None


def _canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    _reject_unexpected(spec, {
        "schema_version", "strategy_id", "strategy_version", "candidate_id",
        "variant_id", "status", "created_at_utc", "fidelity", "parameters",
        "proxy", "data_manifest", "data_inputs", "implementation",
        "required_capabilities", "ambiguities", "state_model", "exit_precedence",
        "tests", "traceability", "source_evidence", "protocol_exceptions",
        "comparability_class", "outcome_bearing_historical_run_seen",
    }, "spec", report)
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
                minimum = source_range.get("minimum")
                maximum = source_range.get("maximum")
                if (
                    not isinstance(minimum, (int, float)) or isinstance(minimum, bool)
                    or not isinstance(maximum, (int, float)) or isinstance(maximum, bool)
                    or not math.isfinite(float(minimum)) or not math.isfinite(float(maximum))
                ):
                    report.error(f"{path}.source_range", "finite numeric minimum and maximum are required")
                elif minimum > maximum:
                    report.error(f"{path}.source_range", "minimum must be <= maximum")
                selected = parameter.get("value")
                if (
                    not isinstance(selected, (int, float)) or isinstance(selected, bool)
                    or not math.isfinite(float(selected))
                ):
                    report.error(f"{path}.value", "SOURCE_RANGE selection must be finite numeric")
                elif isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and not (minimum <= selected <= maximum):
                    report.error(f"{path}.value", "selected value is outside source range")
            if not isinstance(selection, dict):
                report.error(f"{path}.selection", "selection contract is required for SOURCE_RANGE")
            else:
                _require_text(selection, "method", f"{path}.selection", report)
                _require_text(selection, "rationale", f"{path}.selection", report)
                _parse_utc(selection.get("selected_at_utc"), f"{path}.selection.selected_at_utc", report)
                if selection.get("selected_before_historical_results") is not True:
                    report.error(f"{path}.selection.selected_before_historical_results", "must be true")
                selected_at = _parse_utc(selection.get("selected_at_utc"), f"{path}.selection.selected_at_utc", report)
                spec_created = _parse_utc(spec.get("created_at_utc"), "spec.created_at_utc", ValidationReport())
                if selected_at and spec_created and selected_at > spec_created:
                    report.error(f"{path}.selection.selected_at_utc", "selection must exist no later than spec freeze input creation")
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
        if fidelity.get("execution") != "PROXY":
            report.error("spec.proxy.used", "true requires fidelity.execution=PROXY")
        if proxy.get("classification_consequence") != "ADAPTED":
            report.error("spec.proxy.classification_consequence", "must equal ADAPTED")
    elif fidelity.get("execution") == "PROXY":
        report.error("spec.fidelity.execution", "PROXY requires proxy.used=true")

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
        metadata_keys = ("dataset_id", "source_id", "frequency", "timestamp_semantics", "units", "available_at_semantics")
        if requirement == "NOT_USED":
            for key in metadata_keys:
                if key in data_input and data_input.get(key) is not None:
                    report.error(f"{path}.{key}", "NOT_USED metadata must be omitted or null")
        else:
            for key in metadata_keys:
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
        if states and signals and not pairs:
            report.error("spec.state_model.reachable_pairs", "non-empty declared state/event graph is required")
        if pairs and not decisions:
            report.error("spec.state_model.decisions", "non-empty decision mapping is required")
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

    exit_precedence = _unique_texts(spec.get("exit_precedence"), "spec.exit_precedence", report)
    precedence_positions = {name: index for index, name in enumerate(exit_precedence)}
    for earlier, later in (
        ("LIQUIDATION_ENGINE_CONTROLLED", "STRATEGY_EXIT_NEXT_OPEN"),
        ("STOP_LOSS_ENGINE_CONTROLLED", "TAKE_PROFIT_ENGINE_CONTROLLED"),
    ):
        if earlier in precedence_positions and later in precedence_positions and precedence_positions[earlier] > precedence_positions[later]:
            report.error("spec.exit_precedence", f"{earlier} must precede {later}")
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
    rule_ids: List[str] = []
    for index, trace in enumerate(traceability):
        path = f"spec.traceability[{index}]"
        for key in ("rule_id", "source_evidence", "interpretation", "executable_rule", "test_id", "code_path", "code_symbol", "implementation_version"):
            _require_text(trace, key, path, report)
        implementation_hash = trace.get("implementation_sha256")
        if implementation_hash is not None and not _is_hash(implementation_hash):
            report.error(f"{path}.implementation_sha256", "must be null or a lowercase SHA-256")
        if _is_text(trace.get("rule_id")):
            rule_ids.append(str(trace["rule_id"]))
    if len(rule_ids) != len(set(rule_ids)):
        report.error("spec.traceability", "rule_id values must be unique")

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
        if exception_type in {"EXECUTION", "HISTORICAL_WINDOW"} and exception.get("approved") is not True:
            report.error(f"{path}.approved", "controlled exception must be explicitly approved before freeze")
        if exception_type == "EXECUTION":
            controlled = _require_enum(exception, "controlled_field", EXECUTION_ASSUMPTIONS, path, report)
            if controlled and "effective_value" not in exception:
                report.error(f"{path}.effective_value", "approved effective value is required")
        if exception_type == "HISTORICAL_WINDOW":
            effective_window = exception.get("effective_window")
            if not isinstance(effective_window, dict):
                report.error(f"{path}.effective_window", "approved effective window is required")
            else:
                start = _parse_utc(effective_window.get("start_utc"), f"{path}.effective_window.start_utc", report)
                end = _parse_utc(effective_window.get("end_utc"), f"{path}.effective_window.end_utc", report)
                if start and end and start >= end:
                    report.error(f"{path}.effective_window", "start must precede end")
    if spec.get("outcome_bearing_historical_run_seen") is not False:
        report.error("spec.outcome_bearing_historical_run_seen", "must be false at freeze")
    return report


def validate_candidate_registry(
    registry: Mapping[str, object],
    predecessor: Optional[Mapping[str, object]] = None,
) -> ValidationReport:
    report = ValidationReport()
    _reject_unexpected(registry, {
        "schema_version", "registry_version", "status", "created_at_utc",
        "predecessor", "universe_definition", "intake_required_before_substantive_review",
        "candidates", "variants",
    }, "registry", report)
    if registry.get("schema_version") != "CANDIDATE_REGISTRY_V1":
        report.error("schema_version", "must equal CANDIDATE_REGISTRY_V1")
    _require_text(registry, "registry_version", "registry", report)
    created_at = _parse_utc(registry.get("created_at_utc"), "registry.created_at_utc", report)
    predecessor_identity = registry.get("predecessor")
    if predecessor_identity is not None:
        if not isinstance(predecessor_identity, dict):
            report.error("registry.predecessor", "must be null or an identity object")
        else:
            _reject_unexpected(predecessor_identity, {"version", "sha256"}, "registry.predecessor", report)
            _require_text(predecessor_identity, "version", "registry.predecessor", report)
            _require_hash(predecessor_identity, "sha256", "registry.predecessor", report)
            if predecessor is None:
                report.error("registry.predecessor", "predecessor document is required to validate continuity")
            else:
                if predecessor_identity.get("version") != predecessor.get("registry_version"):
                    report.error("registry.predecessor.version", "does not match predecessor registry")
                predecessor_created = _parse_utc(predecessor.get("created_at_utc"), "predecessor.created_at_utc", report)
                if created_at and predecessor_created and created_at <= predecessor_created:
                    report.error("registry.created_at_utc", "must be later than predecessor")
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
        _require_hash(variant, "parameter_identity_sha256", path, report)
        _require_enum(
            variant, "fidelity_classification",
            {"PURE_REPLICATION", "TRANSFER_REPLICATION", "ADAPTED"}, path, report,
        )
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
    if predecessor is not None:
        old_candidates = {
            item.get("candidate_id") for item in predecessor.get("candidates", [])
            if isinstance(item, dict)
        }
        old_variants = {
            item.get("variant_id") for item in predecessor.get("variants", [])
            if isinstance(item, dict)
        }
        missing_candidates = old_candidates - candidate_ids
        missing_variants = old_variants - variant_ids
        if missing_candidates:
            report.error("registry.candidates", f"predecessor candidates removed: {sorted(missing_candidates)}")
        if missing_variants:
            report.error("registry.variants", f"predecessor variants removed: {sorted(missing_variants)}")
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
    _reject_unexpected(protocol, {
        "schema_version", "protocol_version", "status", "created_at_utc",
        "candidate_universe", "historical_window", "execution_assumptions",
        "eligibility", "ranking", "metrics", "time_exposure_definition",
        "protected_validation", "multiple_testing",
    }, "protocol", report)
    if protocol.get("schema_version") != "EVALUATION_PROTOCOL_V1":
        report.error("schema_version", "must equal EVALUATION_PROTOCOL_V1")
    _require_text(protocol, "protocol_version", "protocol", report)
    protocol_created = _parse_utc(protocol.get("created_at_utc"), "protocol.created_at_utc", report)
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
            value = assumption.get("value")
            if name in {"maker_fee", "taker_fee", "slippage", "liquidation_fee"}:
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or not 0 <= value < 1:
                    report.error(f"protocol.execution_assumptions.{name}.value", "must be finite numeric in [0, 1)")
            elif name == "leverage":
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or value < 1:
                    report.error(f"protocol.execution_assumptions.{name}.value", "must be finite numeric >= 1")
            elif name == "liquidation_enabled" and not isinstance(value, bool):
                report.error(f"protocol.execution_assumptions.{name}.value", "must be boolean")
    eligibility = protocol.get("eligibility")
    required_gates = {
        "candidate_registered", "protocol_frozen", "spec_valid", "spec_frozen",
        "no_material_ambiguity", "required_data_available", "engine_compatible",
        "synthetic_causality_tests_pass", "lineage_complete", "historical_window_frozen",
    }
    if not isinstance(eligibility, dict):
        report.error("protocol.eligibility", "object is required")
    else:
        _reject_unexpected(
            eligibility, required_gates | {"allowed_engine_integrity_statuses"},
            "protocol.eligibility", report,
        )
        for gate in required_gates:
            if eligibility.get(gate) is not True:
                report.error(f"protocol.eligibility.{gate}", "must be true")
        statuses = eligibility.get("allowed_engine_integrity_statuses")
        if statuses != ["PASS"]:
            report.error("protocol.eligibility.allowed_engine_integrity_statuses", "production research requires engine integrity PASS")
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
            elif (
                any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or value < 0 for value in weights.values())
                or abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-12
            ):
                report.error("protocol.ranking.weights", "finite non-negative numeric weights must sum to 1")
        elif method == "NO_SCALAR":
            _require_text(ranking, "advancement_rule", "protocol.ranking", report)
    metrics = _objects(protocol.get("metrics"), "protocol.metrics", report)
    metric_names: Set[str] = set()
    for index, metric in enumerate(metrics):
        path = f"protocol.metrics[{index}]"
        name = _require_text(metric, "name", path, report)
        for key in ("formula", "formula_version", "units", "denominator", "source_artifact", "applicability"):
            _require_text(metric, key, path, report)
        if name:
            if name in metric_names:
                report.error(f"{path}.name", "duplicate metric ID")
            if name not in REQUIRED_METRICS:
                report.error(f"{path}.name", "unknown metric ID")
            elif metric.get("formula_version") != f"BACKTESTER_V2_METRICS_2:{name}":
                report.error(f"{path}.formula_version", "does not match the canonical evaluator version")
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
        for key in ("dataset_manifest_sha256", "finalist_set_sha256", "selection_protocol_sha256"):
            _require_hash(protected, key, "protocol.protected_validation", report)
        protected_window = protected.get("window")
        if not isinstance(protected_window, dict):
            report.error("protocol.protected_validation.window", "object is required")
        else:
            protected_start = _parse_utc(protected_window.get("start_utc"), "protocol.protected_validation.window.start_utc", report)
            protected_end = _parse_utc(protected_window.get("end_utc"), "protocol.protected_validation.window.end_utc", report)
            if protected_start and protected_end and protected_start >= protected_end:
                report.error("protocol.protected_validation.window", "start must precede end")
        finalists = _unique_texts(protected.get("finalist_variant_ids"), "protocol.protected_validation.finalist_variant_ids", report)
        if finalists and _canonical_json_hash(sorted(finalists)) != protected.get("finalist_set_sha256"):
            report.error("protocol.protected_validation.finalist_set_sha256", "does not match finalist IDs")
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
    capability_path: Optional[Path] = None,
) -> ValidationReport:
    report = ValidationReport()
    repo_root = repo_root.resolve()
    try:
        if _git(repo_root, "rev-parse", "--is-inside-work-tree") != "true":
            raise ValueError("not inside work tree")
        remote = _git(repo_root, "remote", "get-url", "origin")
        if "weiyakong/Range-sfp-hedge-bot" not in remote:
            report.error("repo.origin", "unexpected repository identity")
    except (OSError, subprocess.CalledProcessError, ValueError):
        report.error("repo_root", "must be the real Git repository with expected origin")
        return report
    canonical_path = (repo_root / CANONICAL_CAPABILITY_RELATIVE_PATH).resolve()
    if capability_path is not None and capability_path.resolve() != canonical_path:
        report.error("capability.path", "production requires the canonical repo-relative manifest")
    if not canonical_path.is_file() or not _is_within(canonical_path, repo_root):
        report.error("capability.path", "canonical capability manifest is missing or outside repo")
        return report
    try:
        canonical = load_json(canonical_path)
    except (OSError, ValueError) as exc:
        report.error("capability.path", str(exc))
        return report
    if dict(capability) != canonical:
        report.error("capability", "content differs from canonical capability manifest")
    if capability.get("schema_version") != "BACKTESTER_CAPABILITIES_V1":
        report.error("schema_version", "must equal BACKTESTER_CAPABILITIES_V1")
    if capability.get("manifest_version") != EXPECTED_CAPABILITY_VERSION:
        report.error("capability.manifest_version", f"must equal {EXPECTED_CAPABILITY_VERSION}")
    if capability.get("audited_base_commit") != AUDITED_BASE_COMMIT:
        report.error("capability.audited_base_commit", "must equal the controlled audited base commit")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", AUDITED_BASE_COMMIT, "HEAD"],
            cwd=repo_root, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        report.error("capability.audited_base_commit", "is not an ancestor of current HEAD")
    engine_path_value = _require_text(capability, "execution_engine_path", "capability", report)
    engine_hash = _require_hash(capability, "execution_engine_sha256", "capability", report)
    if engine_path_value and engine_hash:
        engine_path = (repo_root / engine_path_value).resolve()
        if engine_path != (repo_root / "research/backtester_v2/engine.py").resolve() or not _is_within(engine_path, repo_root):
            report.error("capability.execution_engine_path", "must be the canonical repo-relative engine path")
        if not engine_path.is_file():
            report.error("capability.execution_engine_path", "engine file does not exist")
        elif sha256_file(engine_path) != engine_hash:
            report.error("capability.execution_engine_sha256", "actual engine hash does not match capability manifest")
    module_hashes = capability.get("execution_critical_sha256")
    if not isinstance(module_hashes, dict) or set(module_hashes) != set(EXECUTION_CRITICAL_PATHS):
        report.error("capability.execution_critical_sha256", "must contain the exact controlled module set")
    else:
        for relative_path in EXECUTION_CRITICAL_PATHS:
            actual_path = (repo_root / relative_path).resolve()
            if not _is_within(actual_path, repo_root) or not actual_path.is_file():
                report.error(f"capability.execution_critical_sha256.{relative_path}", "module missing or outside repo")
            elif module_hashes.get(relative_path) != sha256_file(actual_path):
                report.error(f"capability.execution_critical_sha256.{relative_path}", "actual module hash mismatch")
    capabilities = capability.get("capabilities")
    if not isinstance(capabilities, dict):
        report.error("capability.capabilities", "object is required")
    else:
        unknown = set(capabilities) - CONTROLLED_CAPABILITIES
        missing_controlled = CONTROLLED_CAPABILITIES - set(capabilities)
        if unknown:
            report.error("capability.capabilities", f"unknown capability IDs: {sorted(unknown)}")
        if missing_controlled:
            report.error("capability.capabilities", f"missing controlled capability IDs: {sorted(missing_controlled)}")
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
    predecessor_registry: Optional[Mapping[str, object]] = None,
) -> ValidationReport:
    report = ValidationReport()
    report.merge("spec", validate_strategy_spec(spec, capability))
    report.merge("registry", validate_candidate_registry(registry, predecessor_registry))
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
    else:
        spec_created = _parse_utc(spec.get("created_at_utc"), "spec.created_at_utc", report)
        intake = _parse_utc(candidate.get("intake_timestamp_utc"), "registry.candidate.intake_timestamp_utc", report)
        if spec_created and intake and intake > spec_created:
            report.error("registry.candidate.intake_timestamp_utc", "must be no later than spec creation")
        source = spec.get("source_evidence")
        if isinstance(source, dict):
            if candidate.get("primary_source_id") != source.get("primary_source_id"):
                report.error("registry.candidate.primary_source_id", "does not match strategy spec source")
            if candidate.get("primary_source_reference") != source.get("reference"):
                report.error("registry.candidate.primary_source_reference", "does not match strategy spec source")
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
        computed_fidelity = compute_fidelity_summary(spec)
        if variant.get("type") != computed_fidelity or variant.get("fidelity_classification") != computed_fidelity:
            report.error("registry.variant.fidelity_classification", "does not match computed spec fidelity")
        parameters = spec.get("parameters")
        parameter_identity = _canonical_json_hash(parameters if isinstance(parameters, list) else [])
        if variant.get("parameter_identity_sha256") != parameter_identity:
            report.error("registry.variant.parameter_identity_sha256", "does not match strategy parameters")
    universe = protocol.get("candidate_universe")
    if isinstance(universe, dict) and universe.get("registry_version") != registry.get("registry_version"):
        report.error("protocol.candidate_universe.registry_version", "does not match registry")
    declared_manifest = spec.get("data_manifest")
    declared_hash = declared_manifest.get("sha256") if isinstance(declared_manifest, dict) else None
    for index, data_input in enumerate(spec.get("data_inputs", []) if isinstance(spec.get("data_inputs"), list) else []):
        if not isinstance(data_input, dict) or data_input.get("requirement") == "NOT_USED":
            continue
        if data_input.get("manifest_sha256") != declared_hash:
            report.error(f"spec.data_inputs[{index}].manifest_sha256", "must match authoritative data manifest")
    return report


def _git_commit(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD")


def _material_dirty_paths(repo_root: Path, strategy_code_path: Optional[Path]) -> List[str]:
    material_prefixes = (
        "research/backtester_v2/", "research/strategy_replications/",
    )
    strategy_relative: Optional[str] = None
    if strategy_code_path is not None and _is_within(strategy_code_path, repo_root):
        strategy_relative = str(strategy_code_path.resolve().relative_to(repo_root.resolve()))
    dirty: List[str] = []
    for line in _git(repo_root, "status", "--porcelain").splitlines():
        candidate = line[3:].split(" -> ")[-1]
        if candidate.startswith(material_prefixes) or candidate == strategy_relative:
            dirty.append(candidate)
    return dirty


def _register_receipt_identity(
    index_path: Path, *, kind: str, identity: str, artifact_path: Path,
    artifact_sha256: str,
) -> ValidationReport:
    report = ValidationReport()
    payload: Dict[str, object] = {
        "schema_version": "RECEIPT_INDEX_V1", "records": [],
    }
    if index_path.exists():
        payload = load_json(index_path)
        if payload.get("schema_version") != "RECEIPT_INDEX_V1" or not isinstance(payload.get("records"), list):
            report.error("receipt_index", "invalid canonical receipt index")
            return report
    records = payload["records"]
    assert isinstance(records, list)
    for record in records:
        if isinstance(record, dict) and record.get("kind") == kind and record.get("identity") == identity:
            report.error("receipt_index", f"duplicate/collision for {kind} identity {identity}")
            return report
    records.append({
        "kind": kind, "identity": identity,
        "artifact_path": str(artifact_path.resolve()),
        "artifact_sha256": artifact_sha256,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    index_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{index_path.name}.", dir=index_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary_name, index_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return report


def _config_payload(config: object) -> Dict[str, object]:
    if isinstance(config, Mapping):
        payload = dict(config)
    else:
        try:
            payload = asdict(config)
        except TypeError as exc:
            raise ValueError("actual BacktestConfig or mapping is required") from exc
    return payload


def derive_expected_effective_config(
    protocol: Mapping[str, object], spec: Mapping[str, object],
) -> Dict[str, object]:
    assumptions = protocol.get("execution_assumptions")
    if not isinstance(assumptions, dict):
        return {}
    field_map = {
        "maker_fee": "maker_fee_rate",
        "taker_fee": "taker_fee_rate",
        "slippage": "slippage_rate",
        "passive_limit_policy": "limit_fill_policy",
        "marketable_limit_policy": "marketable_limit_policy",
        "funding_treatment": "funding_price_source",
        "liquidation_model": "liquidation_execution_model",
        "end_of_data_policy": "end_of_data_policy",
        "margin_mode": "margin_mode",
        "leverage": "leverage",
        "liquidation_enabled": "liquidation_enabled",
        "liquidation_fee": "liquidation_fee_rate",
        "intrabar_policy": "intrabar_policy",
    }
    expected = {
        field_map[name]: value.get("value")
        for name, value in assumptions.items()
        if name in field_map and isinstance(value, dict)
    }
    for exception in spec.get("protocol_exceptions", []) if isinstance(spec.get("protocol_exceptions"), list) else []:
        if not isinstance(exception, dict) or exception.get("approved") is not True:
            continue
        controlled = exception.get("controlled_field")
        if controlled in field_map and "effective_value" in exception:
            expected[field_map[str(controlled)]] = exception["effective_value"]
    return expected


def derive_expected_window(
    protocol: Mapping[str, object], spec: Mapping[str, object], run_stage: str,
    report: Optional[ValidationReport] = None,
) -> Dict[str, Optional[int]]:
    local_report = report or ValidationReport()
    window = protocol.get("historical_window")
    if run_stage == "PROTECTED_VALIDATION":
        protected = protocol.get("protected_validation")
        window = protected.get("window") if isinstance(protected, dict) else None
    for exception in spec.get("protocol_exceptions", []) if isinstance(spec.get("protocol_exceptions"), list) else []:
        if (
            isinstance(exception, dict)
            and exception.get("type") == "HISTORICAL_WINDOW"
            and exception.get("approved") is True
            and isinstance(exception.get("effective_window"), dict)
        ):
            window = exception["effective_window"]
    if not isinstance(window, dict):
        local_report.error("effective_window", "frozen effective window is missing")
        return {"start": None, "end": None}
    return {
        "start": _timestamp_ms(window.get("start_utc"), "effective_window.start_utc", local_report),
        "end": _timestamp_ms(window.get("end_utc"), "effective_window.end_utc", local_report),
    }


def _actual_controlled_config(config: object) -> Dict[str, object]:
    payload = _config_payload(config)
    controlled = {
        key: payload.get(key) for key in {
            "maker_fee_rate", "taker_fee_rate", "slippage_rate", "limit_fill_policy",
            "funding_price_source", "liquidation_execution_model", "end_of_data_policy",
            "margin_mode", "leverage", "liquidation_enabled", "liquidation_fee_rate",
            "intrabar_policy",
        }
    }
    controlled["marketable_limit_policy"] = "OPEN_TAKER_WITH_LIMIT_CAP"
    return controlled


def _validate_effective_config(
    expected: Mapping[str, object], actual_config: object,
) -> ValidationReport:
    report = ValidationReport()
    actual = _actual_controlled_config(actual_config)
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            report.error(f"actual_config.{key}", f"expected {expected_value!r}, got {actual.get(key)!r}")
    return report


def _symbol_exists(tree: ast.AST, qualified_name: str) -> bool:
    parts = qualified_name.split(".")
    nodes: List[ast.AST] = [tree]
    for part in parts:
        next_nodes: List[ast.AST] = []
        for node in nodes:
            body = getattr(node, "body", [])
            next_nodes.extend(
                child for child in body
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == part
            )
        if not next_nodes:
            return False
        nodes = next_nodes
    return True


def validate_test_manifest_and_traceability(
    *, spec: Mapping[str, object], spec_path: Path, strategy_code_path: Path,
    test_manifest_path: Path,
) -> ValidationReport:
    report = ValidationReport()
    if not test_manifest_path.is_file():
        report.error("test_manifest", "executed strategy test-result manifest is required")
        return report
    manifest = load_json(test_manifest_path)
    if manifest.get("schema_version") != "STRATEGY_TEST_RESULTS_V1":
        report.error("test_manifest.schema_version", "must equal STRATEGY_TEST_RESULTS_V1")
    executed = _parse_utc(manifest.get("executed_at_utc"), "test_manifest.executed_at_utc", report)
    if executed and executed > datetime.now(timezone.utc):
        report.error("test_manifest.executed_at_utc", "cannot be in the future")
    identities = {
        "strategy_spec_sha256": sha256_file(spec_path),
        "strategy_code_sha256": sha256_file(strategy_code_path),
    }
    for key, expected in identities.items():
        if manifest.get(key) != expected:
            report.error(f"test_manifest.{key}", "identity mismatch")
    suite_value = manifest.get("test_suite_path")
    suite_path = (
        Path(str(suite_value)) if isinstance(suite_value, str) and Path(suite_value).is_absolute()
        else test_manifest_path.parent / str(suite_value)
    ) if _is_text(suite_value) else None
    if suite_path is None or not suite_path.resolve().is_file():
        report.error("test_manifest.test_suite_path", "executed suite file does not exist")
    elif manifest.get("test_suite_sha256") != sha256_file(suite_path.resolve()):
        report.error("test_manifest.test_suite_sha256", "suite hash mismatch")
    result_objects = _objects(manifest.get("results"), "test_manifest.results", report)
    results: Dict[str, Mapping[str, object]] = {}
    for index, item in enumerate(result_objects):
        path = f"test_manifest.results[{index}]"
        test_id = _require_text(item, "test_id", path, report)
        _require_text(item, "test_identifier", path, report)
        if item.get("result") != "PASS":
            report.error(f"{path}.result", "required test must have executed PASS result")
        if test_id:
            if test_id in results:
                report.error(f"{path}.test_id", "duplicate test result ID")
            results[test_id] = item
    declared_tests = spec.get("tests")
    required_ids = set(declared_tests.get("test_ids", [])) if isinstance(declared_tests, dict) and isinstance(declared_tests.get("test_ids"), list) else set()
    missing = required_ids - set(results)
    if missing:
        report.error("test_manifest.results", f"required executed tests missing: {sorted(missing)}")
    for index, trace in enumerate(spec.get("traceability", []) if isinstance(spec.get("traceability"), list) else []):
        if not isinstance(trace, dict):
            continue
        path = f"spec.traceability[{index}]"
        if trace.get("test_id") not in results:
            report.error(f"{path}.test_id", "does not reference an executed PASS test")
        code_value = trace.get("code_path")
        code_path = (
            Path(str(code_value)) if isinstance(code_value, str) and Path(code_value).is_absolute()
            else spec_path.parent / str(code_value)
        ) if _is_text(code_value) else None
        if code_path is None or not code_path.resolve().is_file():
            report.error(f"{path}.code_path", "code file does not exist")
            continue
        code_path = code_path.resolve()
        if code_path != strategy_code_path.resolve():
            report.error(f"{path}.code_path", "must resolve to the locked strategy implementation")
        if trace.get("implementation_sha256") != sha256_file(code_path):
            report.error(f"{path}.implementation_sha256", "implementation hash mismatch")
        try:
            tree = ast.parse(code_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            report.error(f"{path}.code_path", f"cannot parse implementation: {exc}")
            continue
        symbol = trace.get("code_symbol")
        if isinstance(symbol, str) and not _symbol_exists(tree, symbol):
            report.error(f"{path}.code_symbol", "declared symbol does not exist")
    return report


def create_freeze_receipt(
    *, spec_path: Path, registry_path: Path, protocol_path: Path,
    capability_path: Path, data_manifest_path: Path, repo_root: Path,
    receipt_path: Path, strategy_code_path: Optional[Path] = None,
    receipt_index_path: Optional[Path] = None,
    previous_registry_path: Optional[Path] = None,
) -> Tuple[ValidationReport, Optional[Dict[str, object]]]:
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    capability = load_json(capability_path)
    spec_hash = sha256_file(spec_path)
    predecessor = load_json(previous_registry_path) if previous_registry_path is not None else None
    report = validate_freeze_inputs(
        spec, registry, protocol, capability, repo_root, spec_hash, predecessor,
    )
    if previous_registry_path is not None:
        predecessor_identity = registry.get("predecessor")
        if not isinstance(predecessor_identity, dict) or predecessor_identity.get("sha256") != sha256_file(previous_registry_path):
            report.error("registry.predecessor.sha256", "does not match predecessor bytes")
    report.merge("capability_path", validate_capability_manifest(
        capability, repo_root, capability_path,
    ))
    data_manifest_hash = sha256_file(data_manifest_path)
    declared_manifest = spec.get("data_manifest")
    if not isinstance(declared_manifest, dict) or declared_manifest.get("sha256") != data_manifest_hash:
        report.error("spec.data_manifest.sha256", "does not match supplied data manifest")
    if strategy_code_path is None or not strategy_code_path.is_file():
        report.error("strategy_code", "exact strategy implementation must be locked at freeze")
        strategy_code_hash = None
    else:
        strategy_code_hash = sha256_file(strategy_code_path)
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
        "engine_capability_manifest_version": capability["manifest_version"],
        "execution_critical_sha256": {
            relative: sha256_file(repo_root / relative)
            for relative in EXECUTION_CRITICAL_PATHS
        },
        "backtester_commit": git_commit,
        "data_manifest_sha256": data_manifest_hash,
        "strategy_code_sha256": strategy_code_hash,
        "computed_fidelity_classification": compute_fidelity_summary(spec),
        "parameter_identity_sha256": _canonical_json_hash(spec.get("parameters", [])),
        "expected_effective_config": derive_expected_effective_config(protocol, spec),
        "expected_window": {
            **derive_expected_window(protocol, spec, "COMPARISON"),
        },
        "validation": {"status": "PASS", "errors": []},
        "unresolved_counts": {"material_ambiguities": 0, "unsupported_capabilities": 0},
    }
    identity = "|".join(str(receipt[key]) for key in (
        "candidate_id", "variant_id", "strategy_version",
    ))
    index_path = receipt_index_path or receipt_path.parent / "receipt_index.json"
    if index_path.exists():
        existing = load_json(index_path)
        for record in existing.get("records", []) if isinstance(existing.get("records"), list) else []:
            if isinstance(record, dict) and record.get("kind") == "freeze" and record.get("identity") == identity:
                report.error("receipt_index", f"duplicate/collision for freeze identity {identity}")
                return report, None
    atomic_write_json(receipt_path, receipt)
    indexed = _register_receipt_identity(
        index_path, kind="freeze", identity=identity,
        artifact_path=receipt_path, artifact_sha256=sha256_file(receipt_path),
    )
    if not indexed.ok:
        receipt_path.unlink(missing_ok=True)
        report.merge("receipt_index", indexed)
        return report, None
    return report, receipt


def validate_freeze_receipt(
    receipt: Mapping[str, object], *, spec_path: Path, registry_path: Path,
    protocol_path: Path, capability_path: Path, data_manifest_path: Path,
    repo_root: Optional[Path] = None, strategy_code_path: Optional[Path] = None,
) -> ValidationReport:
    report = ValidationReport()
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    _reject_unexpected(receipt, {
        "schema_version", "strategy_id", "strategy_version", "candidate_id",
        "variant_id", "frozen_at_utc", "git_commit", "strategy_spec_sha256",
        "candidate_registry", "evaluation_protocol",
        "engine_capability_manifest_sha256", "engine_capability_manifest_version",
        "execution_critical_sha256", "backtester_commit", "data_manifest_sha256",
        "strategy_code_sha256", "computed_fidelity_classification",
        "parameter_identity_sha256", "expected_effective_config", "expected_window",
        "validation", "unresolved_counts",
    }, "receipt", report)
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
    if not _is_hash(code_hash):
        report.error("receipt.strategy_code_sha256", "locked lowercase SHA-256 is required")
    if strategy_code_path is not None and strategy_code_path.is_file() and code_hash != sha256_file(strategy_code_path):
        report.error("receipt.strategy_code_sha256", "strategy implementation changed")
    frozen_at = _parse_utc(receipt.get("frozen_at_utc"), "receipt.frozen_at_utc", report)
    if frozen_at and frozen_at > datetime.now(timezone.utc):
        report.error("receipt.frozen_at_utc", "cannot be in the future")
    for index, parameter in enumerate(spec.get("parameters", []) if isinstance(spec.get("parameters"), list) else []):
        if not isinstance(parameter, dict) or parameter.get("origin") != "SOURCE_RANGE":
            continue
        selection = parameter.get("selection")
        selected_at = _parse_utc(selection.get("selected_at_utc"), f"spec.parameters[{index}].selection.selected_at_utc", report) if isinstance(selection, dict) else None
        if selected_at and frozen_at and selected_at > frozen_at:
            report.error(f"spec.parameters[{index}].selection.selected_at_utc", "selection occurred after freeze")
    if receipt.get("parameter_identity_sha256") != _canonical_json_hash(spec.get("parameters", [])):
        report.error("receipt.parameter_identity_sha256", "parameter identity mismatch")
    if receipt.get("engine_capability_manifest_version") != EXPECTED_CAPABILITY_VERSION:
        report.error("receipt.engine_capability_manifest_version", "capability version mismatch")
    if receipt.get("expected_effective_config") != derive_expected_effective_config(protocol, spec):
        report.error("receipt.expected_effective_config", "effective config derivation mismatch")
    validation = receipt.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "PASS" or validation.get("errors") != []:
        report.error("receipt.validation.status", "must equal PASS")
    unresolved = receipt.get("unresolved_counts")
    if not isinstance(unresolved, dict) or set(unresolved) != {"material_ambiguities", "unsupported_capabilities"} or any(type(value) is not int or value != 0 for value in unresolved.values()):
        report.error("receipt.unresolved_counts", "all unresolved counts must be zero")
    if repo_root is not None:
        try:
            actual_head = _git_commit(repo_root)
        except (OSError, subprocess.CalledProcessError):
            report.error("repo_root", "real Git repository required")
        else:
            for key in ("git_commit", "backtester_commit"):
                if not _is_git_sha(receipt.get(key)) or receipt.get(key) != actual_head:
                    report.error(f"receipt.{key}", "must match actual Git HEAD")
            critical = receipt.get("execution_critical_sha256")
            if not isinstance(critical, dict):
                report.error("receipt.execution_critical_sha256", "critical code identity is required")
            else:
                for relative in EXECUTION_CRITICAL_PATHS:
                    if critical.get(relative) != sha256_file(repo_root / relative):
                        report.error(f"receipt.execution_critical_sha256.{relative}", "actual code hash mismatch")
    return report


def validate_production_preflight(
    *, receipt_path: Path, spec_path: Path, registry_path: Path,
    protocol_path: Path, capability_path: Path, data_manifest_path: Path,
    strategy_code_path: Path, repo_root: Path,
    actual_config: Optional[object] = None,
    tested_start: Optional[int] = None,
    tested_end: Optional[int] = None,
    run_stage: Optional[str] = None,
    test_manifest_path: Optional[Path] = None,
    previous_registry_path: Optional[Path] = None,
) -> ValidationReport:
    report = ValidationReport()
    if not receipt_path.is_file():
        report.error("freeze_receipt", "valid freeze receipt is required; declared FROZEN is insufficient")
        return report
    receipt = load_json(receipt_path)
    report.merge("receipt", validate_freeze_receipt(
        receipt, spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, repo_root=repo_root,
        strategy_code_path=strategy_code_path,
    ))
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    capability = load_json(capability_path)
    predecessor = load_json(previous_registry_path) if previous_registry_path is not None else None
    report.merge("registry", validate_candidate_registry(registry, predecessor))
    if previous_registry_path is not None:
        predecessor_identity = registry.get("predecessor")
        if not isinstance(predecessor_identity, dict) or predecessor_identity.get("sha256") != sha256_file(previous_registry_path):
            report.error("registry.predecessor.sha256", "does not match predecessor bytes")
    report.merge("freeze_inputs", validate_freeze_inputs(
        spec, registry, protocol, capability, repo_root, sha256_file(spec_path), predecessor,
    ))
    report.merge("capability", validate_capability_manifest(capability, repo_root, capability_path))
    if not strategy_code_path.is_file():
        report.error("strategy_code", "exact strategy implementation is required for production")
    else:
        code_hash = sha256_file(strategy_code_path)
        frozen_code_hash = receipt.get("strategy_code_sha256")
        if frozen_code_hash is not None and frozen_code_hash != code_hash:
            report.error("strategy_code", "strategy code differs from freeze receipt")
    try:
        branch = _git(repo_root, "branch", "--show-current")
        if branch != "backtester-v2":
            report.error("repo.branch", "production research requires branch backtester-v2")
        dirty = _material_dirty_paths(repo_root, strategy_code_path)
        if dirty:
            report.error("repo.dirty", f"material production code is dirty: {dirty}")
    except (OSError, subprocess.CalledProcessError):
        report.error("repo_root", "real Git repository state could not be verified")
    if run_stage not in PRODUCTION_STAGES:
        report.error("run_stage", f"production stage must be one of {sorted(PRODUCTION_STAGES)}")
    expected_window = derive_expected_window(protocol, spec, str(run_stage), report)
    if not isinstance(tested_start, int) or not isinstance(tested_end, int):
        report.error("actual_window", "integer tested_start/tested_end are required")
    elif not isinstance(expected_window, dict) or tested_start != expected_window.get("start") or tested_end != expected_window.get("end"):
        report.error("actual_window", "actual tested window does not match frozen effective window")
    if actual_config is None:
        report.error("actual_config", "actual BacktestConfig is required before production execution")
    else:
        expected_config = receipt.get("expected_effective_config")
        if not isinstance(expected_config, dict):
            report.error("receipt.expected_effective_config", "is missing")
        else:
            report.merge("effective_config", _validate_effective_config(expected_config, actual_config))
    if test_manifest_path is None:
        report.error("test_manifest", "actual executed strategy test manifest is required")
    elif strategy_code_path.is_file():
        report.merge("test_evidence", validate_test_manifest_and_traceability(
            spec=spec, spec_path=spec_path, strategy_code_path=strategy_code_path,
            test_manifest_path=test_manifest_path,
        ))
    metadata_manifest_hash = spec.get("data_manifest", {}).get("sha256") if isinstance(spec.get("data_manifest"), dict) else None
    if metadata_manifest_hash != sha256_file(data_manifest_path):
        report.error("data_manifest", "actual data manifest identity mismatch")
    if run_stage == "PROTECTED_VALIDATION":
        protected = protocol.get("protected_validation")
        if not isinstance(protected, dict):
            report.error("protocol.protected_validation", "frozen protected identity is required")
        else:
            if spec.get("variant_id") not in protected.get("finalist_variant_ids", []):
                report.error("protocol.protected_validation.finalist_variant_ids", "variant is not a frozen finalist")
            if protected.get("dataset_manifest_sha256") != sha256_file(data_manifest_path):
                report.error("protocol.protected_validation.dataset_manifest_sha256", "protected data identity mismatch")
    ledger_path = receipt_path.parent / "research_use_ledger.json"
    if ledger_path.exists():
        ledger = load_json(ledger_path)
        records = ledger.get("records")
        if ledger.get("schema_version") != "RESEARCH_USE_LEDGER_V1" or not isinstance(records, list):
            report.error("research_use_ledger", "invalid canonical ledger")
        else:
            parameter_identity = _canonical_json_hash(spec.get("parameters", []))
            for item in records:
                if not isinstance(item, dict):
                    report.error("research_use_ledger.records", "record must be an object")
                    continue
                if item.get("variant_id") == spec.get("variant_id") and item.get("parameter_identity_sha256") != parameter_identity:
                    report.error("research_use_ledger", "variant ID was previously used with different parameters")
            variant = _find_variant(registry, spec.get("variant_id"))
            if isinstance(variant, dict):
                created = _parse_utc(variant.get("created_at_utc"), "registry.variant.created_at_utc", report)
                declared_prior = set(variant.get("historical_results_observed_before_creation", [])) if isinstance(variant.get("historical_results_observed_before_creation"), list) else set()
                actual_prior = set()
                for item in records:
                    if not isinstance(item, dict) or item.get("candidate_id") != spec.get("candidate_id"):
                        continue
                    timestamp = _parse_utc(item.get("timestamp_utc"), "research_use_ledger.record.timestamp_utc", report)
                    if created and timestamp and timestamp < created and _is_text(item.get("run_id")):
                        actual_prior.add(str(item["run_id"]))
                if not actual_prior.issubset(declared_prior):
                    report.error("registry.variant.historical_results_observed_before_creation", f"omits prior run IDs: {sorted(actual_prior - declared_prior)}")
    return report


def create_production_preflight_context(
    *, receipt_path: Path, spec_path: Path, registry_path: Path,
    protocol_path: Path, capability_path: Path, data_manifest_path: Path,
    strategy_code_path: Path, repo_root: Path, actual_config: object,
    tested_start: int, tested_end: int, run_stage: str,
    test_manifest_path: Path, previous_registry_path: Optional[Path] = None,
) -> Tuple[ValidationReport, Optional[VerifiedPreflightContext]]:
    report = validate_production_preflight(
        receipt_path=receipt_path, spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, strategy_code_path=strategy_code_path,
        repo_root=repo_root, actual_config=actual_config,
        tested_start=tested_start, tested_end=tested_end, run_stage=run_stage,
        test_manifest_path=test_manifest_path,
        previous_registry_path=previous_registry_path,
    )
    if not report.ok:
        return report, None
    receipt = load_json(receipt_path)
    protocol = load_json(protocol_path)
    spec = load_json(spec_path)
    expected_config = receipt["expected_effective_config"]
    assert isinstance(expected_config, dict)
    identities = {
        "freeze_receipt_sha256": sha256_file(receipt_path),
        "strategy_spec_sha256": sha256_file(spec_path),
        "registry_sha256": sha256_file(registry_path),
        "protocol_sha256": sha256_file(protocol_path),
        "capability_manifest_sha256": sha256_file(capability_path),
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "strategy_code_sha256": sha256_file(strategy_code_path),
        "test_manifest_sha256": sha256_file(test_manifest_path),
        **{
            f"code:{relative}": sha256_file(repo_root / relative)
            for relative in EXECUTION_CRITICAL_PATHS
        },
    }
    execution_fidelity = spec.get("fidelity", {}).get("execution") if isinstance(spec.get("fidelity"), dict) else None
    qa_dimensions = {
        "engine_integrity": "PENDING",
        "data_fidelity": "VERIFIED_DECLARED",
        "methodology_preflight": "PASS",
        "execution_fidelity": (
            "PROXY" if execution_fidelity == "PROXY" else
            "SOURCE_FAITHFUL" if compute_fidelity_summary(spec) == "PURE_REPLICATION" else
            "TARGET_MAPPING"
        ),
        "causality_assurance": "HUMAN_REVIEW_REQUIRED",
    }
    return report, VerifiedPreflightContext(
        run_stage=run_stage, repo_root=str(repo_root.resolve()),
        strategy_code_path=str(strategy_code_path.resolve()),
        data_manifest_path=str(data_manifest_path.resolve()),
        git_commit=_git_commit(repo_root), expected_start=int(derive_expected_window(protocol, spec, run_stage)["start"]),
        expected_end=int(derive_expected_window(protocol, spec, run_stage)["end"]), expected_config=expected_config,
        identities=identities, qa_dimensions=qa_dimensions, _seal=_PREFLIGHT_SEAL,
    )


def _verify_output_manifest(output_dir: Path, manifest: Mapping[str, object]) -> ValidationReport:
    report = ValidationReport()
    if manifest.get("status") != "COMPLETE":
        report.error("output_manifest.status", "must equal COMPLETE")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or not checksums:
        report.error("output_manifest.checksums", "non-empty object is required")
        return report
    listed = set(str(name) for name in checksums)
    missing = MANDATORY_OUTPUT_ARTIFACTS - listed
    extra_listed = listed - MANDATORY_OUTPUT_ARTIFACTS
    actual = {path.name for path in output_dir.iterdir() if path.is_file()}
    unexpected = actual - MANDATORY_OUTPUT_ARTIFACTS - {"manifest.json"}
    if missing:
        report.error("output_manifest.checksums", f"mandatory artifacts missing: {sorted(missing)}")
    if extra_listed:
        report.error("output_manifest.checksums", f"unexpected listed artifacts: {sorted(extra_listed)}")
    if unexpected:
        report.error("output_manifest", f"unexpected unlisted material artifacts: {sorted(unexpected)}")
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
    repo_root: Optional[Path] = None,
) -> ValidationReport:
    report = ValidationReport()
    repo_root = repo_root.resolve() if repo_root is not None else capability_path.resolve().parents[3]
    receipt = load_json(freeze_receipt_path)
    report.merge("freeze_receipt", validate_freeze_receipt(
        receipt, spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, repo_root=repo_root,
        strategy_code_path=strategy_code_path,
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
        "capability_manifest_version": EXPECTED_CAPABILITY_VERSION,
    }
    for key, value in expected.items():
        if lineage.get(key) != value:
            report.error(f"run_metadata.replication_lineage.{key}", "lineage mismatch")
    protocol = load_json(protocol_path)
    if metadata.get("run_purpose") != "PRODUCTION_RESEARCH" or metadata.get("run_stage") not in PRODUCTION_STAGES:
        report.error("run_metadata.run_purpose", "valid production purpose/stage are required")
    qa = metadata.get("qa_dimensions")
    if not isinstance(qa, dict):
        report.error("run_metadata.qa_dimensions", "independent QA dimensions are required")
    else:
        required_qa = {
            "engine_integrity": "PASS", "methodology_preflight": "PASS",
        }
        for key, value in required_qa.items():
            if qa.get(key) != value:
                report.error(f"run_metadata.qa_dimensions.{key}", f"must equal {value}")
        if qa.get("data_fidelity") not in {"VERIFIED_CANONICAL", "VERIFIED_DECLARED"}:
            report.error("run_metadata.qa_dimensions.data_fidelity", "verified data identity is required")
        if qa.get("execution_fidelity") not in {"SOURCE_FAITHFUL", "TARGET_MAPPING", "PROXY"}:
            report.error("run_metadata.qa_dimensions.execution_fidelity", "controlled execution fidelity is required")
        if qa.get("causality_assurance") not in {"TESTED", "HUMAN_REVIEW_REQUIRED"}:
            report.error("run_metadata.qa_dimensions.causality_assurance", "controlled causality assurance is required")
    code = metadata.get("code")
    if not isinstance(code, dict) or lineage.get("backtester_commit") != code.get("git_commit"):
        report.error("run_metadata.replication_lineage.backtester_commit", "does not match executed-code commit")
    try:
        actual_head = _git_commit(repo_root)
        if not isinstance(code, dict) or code.get("git_commit") != actual_head or lineage.get("backtester_commit") != actual_head:
            report.error("run_metadata.code.git_commit", "does not match actual Git HEAD")
        dirty = _material_dirty_paths(repo_root, strategy_code_path)
        if dirty or (isinstance(code, dict) and code.get("dirty") is not False):
            report.error("run_metadata.code.dirty", f"material production code must be clean: {dirty}")
        file_hashes = code.get("file_sha256") if isinstance(code, dict) else None
        if not isinstance(file_hashes, dict):
            report.error("run_metadata.code.file_sha256", "executed code hashes are required")
        else:
            for relative in EXECUTION_CRITICAL_PATHS:
                if file_hashes.get(relative) != sha256_file(repo_root / relative):
                    report.error(f"run_metadata.code.file_sha256.{relative}", "actual executed-code hash mismatch")
    except (OSError, subprocess.CalledProcessError):
        report.error("repo_root", "actual Git state could not be verified")
    if config_path.is_file() and lineage.get("config_sha256") != sha256_file(config_path):
        report.error("run_metadata.replication_lineage.config_sha256", "config hash mismatch")
    if config_path.is_file():
        actual_config = load_json(config_path)
        expected_config = receipt.get("expected_effective_config")
        if isinstance(expected_config, dict):
            report.merge("effective_config", _validate_effective_config(expected_config, actual_config))
    expected_window = derive_expected_window(protocol, load_json(spec_path), str(metadata.get("run_stage")), report)
    data = metadata.get("data")
    if not isinstance(data, dict):
        report.error("run_metadata.data", "object is required")
    else:
        if not isinstance(expected_window, dict) or data.get("tested_start") != expected_window.get("start") or data.get("tested_end") != expected_window.get("end"):
            report.error("run_metadata.data", "actual run window differs from frozen window")
        if data.get("manifest_sha256") != sha256_file(data_manifest_path):
            report.error("run_metadata.data.manifest_sha256", "actual data identity mismatch")
    gate = metadata.get("production_gate")
    if not isinstance(gate, dict) or gate.get("status") != "PASS":
        report.error("run_metadata.production_gate", "verified preflight identity is required")
    metrics_path = output_dir / "metrics.json"
    if metrics_path.is_file():
        metrics = load_json(metrics_path)
        if metrics.get("metric_contract_version") != "BACKTESTER_V2_METRICS_2":
            report.error("metrics.metric_contract_version", "unknown formula/version")
        definitions = protocol.get("metrics", [])
        for item in definitions if isinstance(definitions, list) else []:
            if isinstance(item, dict) and item.get("name") in REQUIRED_METRICS:
                metric_id = str(item["name"])
                output_key = METRIC_OUTPUT_KEYS[metric_id]
                if output_key not in metrics:
                    report.error(f"metrics.{metric_id}", "required applicable metric is absent")
                if item.get("formula_version") != f"BACKTESTER_V2_METRICS_2:{metric_id}":
                    report.error(f"metrics.{metric_id}", "protocol formula version is not canonical")
    return report


def create_run_receipt(
    *, output_dir: Path, freeze_receipt_path: Path, spec_path: Path,
    registry_path: Path, protocol_path: Path, capability_path: Path,
    data_manifest_path: Path, strategy_code_path: Path, receipt_path: Path,
    repo_root: Optional[Path] = None,
    receipt_index_path: Optional[Path] = None,
    research_use_ledger_path: Optional[Path] = None,
) -> Tuple[ValidationReport, Optional[Dict[str, object]]]:
    repo_root = repo_root.resolve() if repo_root is not None else capability_path.resolve().parents[3]
    report = validate_run_lineage(
        output_dir=output_dir, freeze_receipt_path=freeze_receipt_path,
        spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, strategy_code_path=strategy_code_path,
        repo_root=repo_root,
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
        "run_metadata_sha256": sha256_file(output_dir / "run_metadata.json"),
        "tested_start": metadata["data"]["tested_start"],
        "tested_end": metadata["data"]["tested_end"],
        "run_qa_status": metadata["qa_status"],
        "qa_dimensions": metadata["qa_dimensions"],
        "run_purpose": metadata["run_purpose"],
        "run_stage": metadata["run_stage"],
        "executed_code_sha256": {
            relative: sha256_file(repo_root / relative)
            for relative in EXECUTION_CRITICAL_PATHS
        },
        "fidelity_classification": compute_fidelity_summary(spec),
        "comparability_class": spec["comparability_class"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    index_path = receipt_index_path or receipt_path.parent / "receipt_index.json"
    if index_path.exists():
        existing_index = load_json(index_path)
        for record in existing_index.get("records", []) if isinstance(existing_index.get("records"), list) else []:
            if isinstance(record, dict) and record.get("kind") == "run" and record.get("identity") == str(metadata["run_id"]):
                report.error("receipt_index", f"run ID collision: {metadata['run_id']}")
                return report, None
    ledger_path = research_use_ledger_path or receipt_path.parent / "research_use_ledger.json"
    ledger: Dict[str, object] = {"schema_version": "RESEARCH_USE_LEDGER_V1", "records": []}
    if ledger_path.exists():
        ledger = load_json(ledger_path)
        if ledger.get("schema_version") != "RESEARCH_USE_LEDGER_V1" or not isinstance(ledger.get("records"), list):
            report.error("research_use_ledger", "invalid append-only ledger")
            return report, None
    records = ledger["records"]
    assert isinstance(records, list)
    if metadata.get("run_stage") == "PROTECTED_VALIDATION":
        repeated = any(
            isinstance(item, dict)
            and item.get("candidate_id") == spec.get("candidate_id")
            and item.get("variant_id") == spec.get("variant_id")
            and item.get("run_stage") == "PROTECTED_VALIDATION"
            for item in records
        )
        if repeated:
            report.error("research_use_ledger", "repeated protected use prevents a clean valid receipt")
            return report, None
    atomic_write_json(receipt_path, receipt)
    indexed = _register_receipt_identity(
        index_path, kind="run", identity=str(metadata["run_id"]),
        artifact_path=receipt_path, artifact_sha256=sha256_file(receipt_path),
    )
    if not indexed.ok:
        receipt_path.unlink(missing_ok=True)
        report.merge("receipt_index", indexed)
        return report, None
    records.append({
        "run_id": metadata["run_id"], "candidate_id": spec["candidate_id"],
        "variant_id": spec["variant_id"], "parameter_identity_sha256": _canonical_json_hash(spec.get("parameters", [])),
        "run_stage": metadata["run_stage"], "timestamp_utc": receipt["created_at_utc"],
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "tested_start": receipt["tested_start"], "tested_end": receipt["tested_end"],
        "receipt_sha256": sha256_file(receipt_path),
    })
    fd, temporary_name = tempfile.mkstemp(prefix=f".{ledger_path.name}.", dir=ledger_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary_name, ledger_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return report, receipt


def validate_run_receipt(
    receipt_path: Path, *, output_dir: Path, freeze_receipt_path: Path,
    spec_path: Path, registry_path: Path, protocol_path: Path,
    capability_path: Path, data_manifest_path: Path, strategy_code_path: Path,
    repo_root: Optional[Path] = None,
) -> ValidationReport:
    report = validate_run_lineage(
        output_dir=output_dir, freeze_receipt_path=freeze_receipt_path,
        spec_path=spec_path, registry_path=registry_path,
        protocol_path=protocol_path, capability_path=capability_path,
        data_manifest_path=data_manifest_path, strategy_code_path=strategy_code_path,
        repo_root=repo_root,
    )
    if not receipt_path.is_file():
        report.error("run_receipt", "receipt is missing")
        return report
    receipt = load_json(receipt_path)
    _reject_unexpected(receipt, {
        "schema_version", "run_id", "candidate_id", "variant_id", "spec_sha256",
        "registry", "protocol", "strategy_code_sha256", "backtester_commit",
        "capability_manifest_sha256", "config_sha256", "data_manifest_sha256",
        "output_manifest_sha256", "run_metadata_sha256", "tested_start",
        "tested_end", "run_qa_status", "qa_dimensions", "run_purpose", "run_stage",
        "executed_code_sha256", "fidelity_classification", "comparability_class",
        "created_at_utc",
    }, "run_receipt", report)
    metadata = load_json(output_dir / "run_metadata.json")
    spec = load_json(spec_path)
    registry = load_json(registry_path)
    protocol = load_json(protocol_path)
    actual_repo = repo_root.resolve() if repo_root is not None else capability_path.resolve().parents[3]
    expected: Dict[str, object] = {
        "schema_version": "RUN_RECEIPT_V1",
        "run_id": metadata.get("run_id"),
        "candidate_id": spec.get("candidate_id"),
        "variant_id": spec.get("variant_id"),
        "spec_sha256": sha256_file(spec_path),
        "registry": {"version": registry.get("registry_version"), "sha256": sha256_file(registry_path)},
        "protocol": {"version": protocol.get("protocol_version"), "sha256": sha256_file(protocol_path)},
        "strategy_code_sha256": sha256_file(strategy_code_path),
        "backtester_commit": _git_commit(actual_repo),
        "capability_manifest_sha256": sha256_file(capability_path),
        "config_sha256": sha256_file(output_dir / "config.json"),
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "output_manifest_sha256": sha256_file(output_dir / "manifest.json"),
        "run_metadata_sha256": sha256_file(output_dir / "run_metadata.json"),
        "tested_start": metadata.get("data", {}).get("tested_start") if isinstance(metadata.get("data"), dict) else None,
        "tested_end": metadata.get("data", {}).get("tested_end") if isinstance(metadata.get("data"), dict) else None,
        "run_qa_status": metadata.get("qa_status"),
        "qa_dimensions": metadata.get("qa_dimensions"),
        "run_purpose": metadata.get("run_purpose"),
        "run_stage": metadata.get("run_stage"),
        "executed_code_sha256": {relative: sha256_file(actual_repo / relative) for relative in EXECUTION_CRITICAL_PATHS},
        "fidelity_classification": compute_fidelity_summary(spec),
        "comparability_class": spec.get("comparability_class"),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            report.error(f"run_receipt.{key}", "receipt no longer matches actual upstream/output identity")
    created = _parse_utc(receipt.get("created_at_utc"), "run_receipt.created_at_utc", report)
    if created and created > datetime.now(timezone.utc):
        report.error("run_receipt.created_at_utc", "cannot be in the future")
    return report
