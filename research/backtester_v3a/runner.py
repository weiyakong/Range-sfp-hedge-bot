"""Atomic single-symbol production runner owned by Backtester V3-A."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Protocol, Sequence, cast

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import (
    BacktestConfig,
    BacktestResult,
    Bar,
    MaintenanceTier,
    OrderIntent,
    StrategyState,
)

from .branch_policy import require_v3a_production_branch
from .contracts import (
    ExecutionAttestationV3A,
    InstrumentMetadata,
    ResultMetadataV3A,
    RunReceiptV3A,
    StrategySpecV2,
    canonical_json_bytes,
    canonical_sha256,
    parse_execution_attestation,
    parse_result_metadata,
    parse_run_receipt,
    parse_strategy_spec_v2,
    revalidate_identity_chain,
)
from .data import (
    InputContractLocators,
    ResolvedExecutionInputs,
    resolve_execution_inputs,
    sha256_file,
)
from .precision import normalize_order_intent
from .state import (
    V3A_STATE_RELATIVE_PATH,
    RunStateIdentity,
    initialize_state,
    insert_run_identity,
    load_run_identity,
    update_run_status,
)


OUTPUT_MANIFEST_SCHEMA = "BACKTESTER_V3A_OUTPUT_MANIFEST_V1"


class RunnerError(ValueError):
    """Raised when V3-A cannot produce or independently validate a run."""


class StrategyLike(Protocol):
    def on_bar(self, bar: Bar, state: StrategyState) -> List[OrderIntent]:
        ...


@dataclass(frozen=True)
class ProductionRunRequestV3A:
    repo_root: Path
    spec_path: Path
    config_path: Path
    inputs: InputContractLocators
    required_start_ms: int
    required_end_ms: int
    output_dir: Path
    state_path: Optional[Path] = None


@dataclass(frozen=True)
class ProductionRunOutcomeV3A:
    run_id: str
    execution_id: str
    output_dir: Path
    receipt_path: Path
    receipt_sha256: str


class NormalizingStrategy:
    """Apply the V3-A precision boundary to raw strategy output."""

    def __init__(self, strategy: StrategyLike, metadata: InstrumentMetadata):
        self._strategy = strategy
        self._metadata = metadata
        self.raw_intents: List[OrderIntent] = []
        self.normalized_intents: List[OrderIntent] = []

    def on_bar(self, bar: Bar, state: StrategyState) -> List[OrderIntent]:
        raw = self._strategy.on_bar(bar, state)
        normalized = [
            normalize_order_intent(item, self._metadata, reference_price=bar.close)
            for item in raw
        ]
        self.raw_intents.extend(raw)
        self.normalized_intents.extend(normalized)
        return normalized


def _json_object(path: Path, label: str) -> Mapping[str, object]:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise RunnerError(f"{label} must be a regular file: {resolved}")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"cannot read {label}: {resolved}: {exc}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"{label} must contain one JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(canonical_json_bytes(value) + b"\n")
    os.replace(temporary, path)


def _config_payload(config: BacktestConfig) -> Dict[str, object]:
    payload = asdict(config)
    payload["funding_rate_by_time"] = {
        str(key): value for key, value in config.funding_rate_by_time.items()
    }
    payload["funding_price_by_time"] = {
        str(key): value for key, value in config.funding_price_by_time.items()
    }
    return payload


def canonical_config_sha256(config: BacktestConfig) -> str:
    return canonical_sha256(_config_payload(config))


def load_backtest_config(path: Path) -> BacktestConfig:
    payload = _json_object(path, "V3-A execution config")
    expected = {item.name for item in fields(BacktestConfig)}
    if set(payload) != expected:
        raise RunnerError(
            "V3-A execution config fields mismatch; "
            f"missing={sorted(expected - set(payload))}, "
            f"unexpected={sorted(set(payload) - expected)}",
        )
    values = dict(payload)
    rate_payload = values["funding_rate_by_time"]
    price_payload = values["funding_price_by_time"]
    tiers_payload = values["maintenance_tiers"]
    if not isinstance(rate_payload, dict) or not isinstance(price_payload, dict):
        raise RunnerError("funding maps must be JSON objects")
    if not isinstance(tiers_payload, list):
        raise RunnerError("maintenance_tiers must be a JSON array")
    values["funding_rate_by_time"] = {
        int(key): float(value) for key, value in rate_payload.items()
    }
    values["funding_price_by_time"] = {
        int(key): float(value) for key, value in price_payload.items()
    }
    tiers = tuple(
        MaintenanceTier(**item)
        for item in tiers_payload
        if isinstance(item, dict)
    )
    if len(tiers) != len(tiers_payload):
        raise RunnerError("maintenance_tiers entries must be objects")
    values["maintenance_tiers"] = tiers
    try:
        return BacktestConfig(**values)
    except (TypeError, ValueError) as exc:
        raise RunnerError(f"invalid V3-A execution config: {exc}") from exc


def _execution_config(
    config: BacktestConfig,
    resolved: ResolvedExecutionInputs,
) -> BacktestConfig:
    funding_required = resolved.bound.funding is not None
    mark_required = resolved.bound.mark_price is not None
    if not funding_required and (
        config.funding_rate_by_time or config.funding_price_by_time
    ):
        raise RunnerError("funding data is explicitly not used but config supplies funding")
    return replace(
        config,
        funding_rate_by_time=dict(resolved.funding_rate_by_time),
        funding_price_by_time=dict(resolved.funding_price_by_time),
        funding_data_verified=funding_required,
        mark_price_data_verified=mark_required,
    )


def _load_strategy(spec: StrategySpecV2) -> StrategyLike:
    module_name, separator, attribute_path = spec.strategy_entrypoint.rpartition(".")
    if not separator:
        raise RunnerError("strategy_entrypoint must include a module and callable")
    try:
        target: object = importlib.import_module(module_name)
    except ImportError as exc:
        raise RunnerError(f"cannot import frozen strategy module {module_name}: {exc}") from exc
    for part in attribute_path.split("."):
        if part.startswith("_") or not hasattr(target, part):
            raise RunnerError(
                f"frozen strategy entrypoint does not exist: {spec.strategy_entrypoint}",
            )
        target = getattr(target, part)
    if not callable(target):
        raise RunnerError("frozen strategy entrypoint must be callable")
    try:
        strategy = target(**spec.parameters)
    except TypeError as exc:
        raise RunnerError(f"strategy constructor rejected frozen parameters: {exc}") from exc
    if not callable(getattr(strategy, "on_bar", None)):
        raise RunnerError("strategy instance must provide on_bar")
    return cast(StrategyLike, strategy)


def _code_identity(repo_root: Path) -> str:
    relative_paths = (
        "research/backtester_v2/engine.py",
        "research/backtester_v2/models.py",
        "research/backtester_v3a/branch_policy.py",
        "research/backtester_v3a/contracts.py",
        "research/backtester_v3a/data.py",
        "research/backtester_v3a/precision.py",
        "research/backtester_v3a/runner.py",
        "research/backtester_v3a/state.py",
    )
    identities: Dict[str, str] = {}
    for relative in relative_paths:
        path = (repo_root / relative).resolve()
        if not path.is_file():
            raise RunnerError(f"execution-critical code is missing: {relative}")
        identities[relative] = sha256_file(path)
    return canonical_sha256(identities)


def _claims(
    run_id: str,
    spec: StrategySpecV2,
    resolved: ResolvedExecutionInputs,
) -> Dict[str, object]:
    return {
        "run_id": run_id,
        "execution_identity": spec.execution_identity.to_payload(),
        "strategy_spec_sha256": canonical_sha256(spec.to_payload()),
        "strategy_entrypoint": spec.strategy_entrypoint,
        "strategy_parameters_sha256": spec.parameters_sha256,
        **resolved.bound.contract_hash_payload(),
    }


def _result_payload(
    run_id: str,
    result: BacktestResult,
    strategy: NormalizingStrategy,
) -> Dict[str, object]:
    return {
        "schema_version": "BACKTESTER_V3A_RESULT_V1",
        "run_id": run_id,
        "result": asdict(result),
        "raw_strategy_intents": [asdict(item) for item in strategy.raw_intents],
        "normalized_order_intents": [
            asdict(item) for item in strategy.normalized_intents
        ],
    }


def run_production_v3a(
    request: ProductionRunRequestV3A,
) -> ProductionRunOutcomeV3A:
    """Resolve, normalize, execute, attest, persist, and revalidate one symbol."""
    repo_root = request.repo_root.resolve()
    require_v3a_production_branch(repo_root)
    output_dir = request.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"V3-A production output must not pre-exist: {output_dir}")
    spec = parse_strategy_spec_v2(_json_object(request.spec_path, "strategy spec"))
    resolved = resolve_execution_inputs(
        spec,
        request.inputs,
        request.required_start_ms,
        request.required_end_ms,
    )
    config = _execution_config(load_backtest_config(request.config_path), resolved)
    if canonical_config_sha256(config) != spec.execution_config_sha256:
        raise RunnerError("actual V3-A BacktestConfig differs from frozen strategy spec")
    strategy = NormalizingStrategy(_load_strategy(spec), resolved.metadata)
    result = BacktestEngine(config).run(resolved.bars, strategy)
    if result.qa_status != "VERIFIED":
        raise RunnerError(f"execution engine QA failed: {result.qa_issues}")

    run_id = str(uuid.uuid4())
    persisted_result = _result_payload(run_id, result, strategy)
    execution_id = canonical_sha256(persisted_result)
    code_identity = _code_identity(repo_root)
    claims = _claims(run_id, spec, resolved)
    result_metadata = parse_result_metadata({
        "schema_version": "BACKTESTER_V3A_RESULT_METADATA_V1",
        **claims,
    })
    result_metadata_hash = canonical_sha256(result_metadata.to_payload())
    attestation = parse_execution_attestation({
        "schema_version": "BACKTESTER_V3A_EXECUTION_ATTESTATION_V1",
        **claims,
        "execution_id": execution_id,
        "result_metadata_sha256": result_metadata_hash,
        "code_identity_sha256": code_identity,
    })
    attestation_hash = canonical_sha256(attestation.to_payload())
    receipt = parse_run_receipt({
        "schema_version": "BACKTESTER_V3A_RUN_RECEIPT_V1",
        "authority": "ATOMIC_PRODUCTION_RUNNER_V3A",
        **claims,
        "execution_id": execution_id,
        "result_metadata_sha256": result_metadata_hash,
        "execution_attestation_sha256": attestation_hash,
        "code_identity_sha256": code_identity,
    })

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(
        prefix=f".{output_dir.name}.v3a-",
        dir=output_dir.parent,
    ))
    staged = work / output_dir.name
    staged.mkdir()
    state_path = (
        request.state_path.resolve()
        if request.state_path is not None
        else (repo_root / V3A_STATE_RELATIVE_PATH).resolve()
    )
    state_status: Optional[str] = None
    try:
        _write_json(staged / "result.json", persisted_result)
        _write_json(staged / "result_metadata.json", result_metadata.to_payload())
        _write_json(staged / "execution_attestation.json", attestation.to_payload())
        _write_json(staged / "run_receipt_v3a.json", receipt.to_payload())
        checksums = {
            item.name: sha256_file(item)
            for item in sorted(staged.iterdir())
        }
        _write_json(staged / "output_manifest.json", {
            "schema_version": OUTPUT_MANIFEST_SCHEMA,
            "status": "COMPLETE",
            "run_id": run_id,
            "required_start_ms": request.required_start_ms,
            "required_end_ms": request.required_end_ms,
            "checksums": checksums,
        })
        initialize_state(state_path)
        state_record = replace(
            RunStateIdentity.from_receipt(receipt),
            status="RESERVED",
        )
        insert_run_identity(state_path, state_record)
        state_status = "RESERVED"
        update_run_status(
            state_path,
            run_id,
            expected_status="RESERVED",
            new_status="COMPLETE",
        )
        state_status = "COMPLETE"
        persisted_state = load_run_identity(state_path, run_id)
        revalidate_identity_chain(
            spec,
            resolved.bound,
            result_metadata,
            attestation,
            receipt,
            persisted_state,
        )
        validate_v3a_run(
            repo_root=repo_root,
            output_dir=staged,
            spec_path=request.spec_path,
            inputs=request.inputs,
            state_path=state_path,
        )
        os.replace(staged, output_dir)
        state_status = None
    except Exception:
        if state_status is not None:
            update_run_status(
                state_path,
                run_id,
                expected_status=state_status,
                new_status="FAILED",
            )
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
    receipt_path = output_dir / "run_receipt_v3a.json"
    return ProductionRunOutcomeV3A(
        run_id=run_id,
        execution_id=execution_id,
        output_dir=output_dir,
        receipt_path=receipt_path,
        receipt_sha256=sha256_file(receipt_path),
    )


def _require_checksum_manifest(output_dir: Path, run_id: str) -> tuple[int, int]:
    payload = _json_object(output_dir / "output_manifest.json", "output manifest")
    expected = {
        "schema_version", "status", "run_id", "required_start_ms",
        "required_end_ms", "checksums",
    }
    if set(payload) != expected:
        raise RunnerError("output manifest fields mismatch")
    if payload["schema_version"] != OUTPUT_MANIFEST_SCHEMA:
        raise RunnerError("output manifest schema mismatch")
    if payload["status"] != "COMPLETE" or payload["run_id"] != run_id:
        raise RunnerError("output manifest run identity or status mismatch")
    required_start = payload["required_start_ms"]
    required_end = payload["required_end_ms"]
    if (
        not isinstance(required_start, int)
        or isinstance(required_start, bool)
        or not isinstance(required_end, int)
        or isinstance(required_end, bool)
        or required_start > required_end
    ):
        raise RunnerError("output manifest execution coverage is invalid")
    checksums = payload["checksums"]
    if not isinstance(checksums, dict):
        raise RunnerError("output manifest checksums must be an object")
    actual_names = {
        item.name for item in output_dir.iterdir()
        if item.name != "output_manifest.json"
    }
    if set(checksums) != actual_names:
        raise RunnerError("output manifest artifact set mismatch")
    for name, digest in checksums.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise RunnerError("output manifest checksum entry is invalid")
        if sha256_file(output_dir / name) != digest:
            raise RunnerError(f"output artifact checksum mismatch: {name}")
    return required_start, required_end


def validate_v3a_run(
    *,
    repo_root: Path,
    output_dir: Path,
    spec_path: Path,
    inputs: InputContractLocators,
    state_path: Path,
) -> None:
    """Independently revalidate persisted V3-A artifacts and canonical state."""
    require_v3a_production_branch(repo_root.resolve())
    resolved_output = output_dir.resolve()
    if not resolved_output.is_dir() or resolved_output.is_symlink():
        raise RunnerError("V3-A output must be a regular directory")
    spec = parse_strategy_spec_v2(_json_object(spec_path, "strategy spec"))
    result_metadata = parse_result_metadata(
        _json_object(resolved_output / "result_metadata.json", "result metadata"),
    )
    attestation = parse_execution_attestation(
        _json_object(
            resolved_output / "execution_attestation.json",
            "execution attestation",
        ),
    )
    receipt = parse_run_receipt(
        _json_object(resolved_output / "run_receipt_v3a.json", "run receipt"),
    )
    persisted_result = _json_object(resolved_output / "result.json", "result")
    if canonical_sha256(persisted_result) != receipt.execution_id:
        raise RunnerError("result content differs from content-addressed execution_id")
    required_start, required_end = _require_checksum_manifest(
        resolved_output, receipt.run_id,
    )
    resolved = resolve_execution_inputs(
        spec,
        inputs,
        required_start_ms=required_start,
        required_end_ms=required_end,
    )
    state = load_run_identity(state_path, receipt.run_id)
    revalidate_identity_chain(
        spec,
        resolved.bound,
        result_metadata,
        attestation,
        receipt,
        state,
    )


__all__ = [
    "OUTPUT_MANIFEST_SCHEMA",
    "NormalizingStrategy",
    "ProductionRunOutcomeV3A",
    "ProductionRunRequestV3A",
    "RunnerError",
    "canonical_config_sha256",
    "load_backtest_config",
    "run_production_v3a",
    "validate_v3a_run",
]
