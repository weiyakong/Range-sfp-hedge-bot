"""Strict immutable identity contracts for Backtester V3-A Phase 2.

These contracts deliberately do not alter Backtester V2 execution semantics.
They establish the one-run/one-symbol authority chain that must be validated
before bars, funding, Mark Price, metadata, or strategy intents reach execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Mapping, Optional, Protocol, Sequence, Tuple


STRATEGY_SPEC_SCHEMA = "STRATEGY_SPEC_V2"
DATASET_IDENTITY_SCHEMA = "BACKTESTER_V3A_DATASET_IDENTITY_V1"
INSTRUMENT_METADATA_SCHEMA = "BACKTESTER_V3A_INSTRUMENT_METADATA_V1"
INSTRUMENT_METADATA_SCHEMA_V2 = "BACKTESTER_V3A_INSTRUMENT_METADATA_V2"
RESULT_METADATA_SCHEMA = "BACKTESTER_V3A_RESULT_METADATA_V1"
ATTESTATION_SCHEMA = "BACKTESTER_V3A_EXECUTION_ATTESTATION_V1"
RECEIPT_SCHEMA = "BACKTESTER_V3A_RUN_RECEIPT_V1"

DATASET_ROLES = frozenset({"trade_price", "funding", "mark_price"})
REQUIREMENT_ROLES = (
    "trade_price",
    "funding",
    "mark_price",
    "instrument_metadata",
)
REQUIREMENT_MODES = frozenset({"REQUIRED", "EXPLICITLY_NOT_USED"})
ABSENCE_POLICY = "EXPLICITLY_NOT_USED_BY_FROZEN_SPEC"
METADATA_FIDELITY = frozenset({
    "HISTORICAL_VERIFIED",
    "STATIC_CURRENT_PROXY",
    "RESEARCH_ASSUMPTION",
})

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,40}$")


class ContractError(ValueError):
    """Raised when an immutable V3-A identity contract is invalid."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the deterministic JSON representation used for contract hashes."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical JSON: {exc}") from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ContractError(f"{path} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: Sequence[str], path: str,
) -> None:
    expected_set = set(expected)
    missing = sorted(expected_set - set(value))
    extra = sorted(set(value) - expected_set)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {missing}")
        if extra:
            details.append(f"unexpected {extra}")
        raise ContractError(f"{path} has invalid fields: {', '.join(details)}")


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError(f"{path} must be a non-empty exact string")
    return value


def _hash(value: object, path: str) -> str:
    text = _text(value, path)
    if _HASH_RE.fullmatch(text) is None:
        raise ContractError(f"{path} must be a lowercase SHA-256")
    return text


def _optional_hash(value: object, path: str) -> Optional[str]:
    if value is None:
        return None
    return _hash(value, path)


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractError(f"{path} must be an integer")
    return value


def _optional_integer(value: object, path: str) -> Optional[int]:
    if value is None:
        return None
    return _integer(value, path)


def _positive_decimal_text(value: object, path: str) -> str:
    text = _text(value, path)
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ContractError(f"{path} must be a decimal string") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ContractError(f"{path} must be finite and positive")
    return text


def _entrypoint(value: object, path: str) -> str:
    text = _text(value, path)
    if any(not part.isidentifier() or part.startswith("_") for part in text.split(".")):
        raise ContractError(f"{path} must be a public dotted Python entrypoint")
    return text


def _utc_timestamp(value: object, path: str) -> str:
    text = _text(value, path)
    if not text.endswith("Z"):
        raise ContractError(f"{path} must use canonical UTC Z notation")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ContractError(f"{path} must be UTC")
    return text


@dataclass(frozen=True)
class ExecutionIdentity:
    exchange: str
    market: str
    symbol: str
    execution_timeframe: str
    timezone: str
    timestamp_semantics: str

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object], path: str = "execution_identity",
    ) -> "ExecutionIdentity":
        _exact_keys(payload, (
            "exchange", "market", "symbol", "execution_timeframe", "timezone",
            "timestamp_semantics",
        ), path)
        symbol = _text(payload["symbol"], f"{path}.symbol")
        if symbol != symbol.upper() or _SYMBOL_RE.fullmatch(symbol) is None:
            raise ContractError(
                f"{path}.symbol must be an uppercase exchange symbol",
            )
        return cls(
            exchange=_text(payload["exchange"], f"{path}.exchange"),
            market=_text(payload["market"], f"{path}.market"),
            symbol=symbol,
            execution_timeframe=_text(
                payload["execution_timeframe"], f"{path}.execution_timeframe",
            ),
            timezone=_text(payload["timezone"], f"{path}.timezone"),
            timestamp_semantics=_text(
                payload["timestamp_semantics"], f"{path}.timestamp_semantics",
            ),
        )

    def to_payload(self) -> Dict[str, object]:
        return {
            "exchange": self.exchange,
            "market": self.market,
            "symbol": self.symbol,
            "execution_timeframe": self.execution_timeframe,
            "timezone": self.timezone,
            "timestamp_semantics": self.timestamp_semantics,
        }


@dataclass(frozen=True)
class InputRequirement:
    role: str
    mode: str
    contract_sha256: Optional[str]
    absence_policy: Optional[str]

    @classmethod
    def from_payload(
        cls, role: str, payload: Mapping[str, object], path: str,
    ) -> "InputRequirement":
        _exact_keys(
            payload, ("mode", "contract_sha256", "absence_policy"), path,
        )
        mode = _text(payload["mode"], f"{path}.mode")
        if mode not in REQUIREMENT_MODES:
            raise ContractError(f"{path}.mode is unsupported: {mode}")
        contract_hash = _optional_hash(
            payload["contract_sha256"], f"{path}.contract_sha256",
        )
        absence = payload["absence_policy"]
        if mode == "REQUIRED":
            if contract_hash is None:
                raise ContractError(f"{path}.contract_sha256 is required")
            if absence is not None:
                raise ContractError(f"{path}.absence_policy must be null")
            absence_text = None
        else:
            if contract_hash is not None:
                raise ContractError(
                    f"{path}.contract_sha256 must be null when explicitly not used",
                )
            if absence != ABSENCE_POLICY:
                raise ContractError(
                    f"{path}.absence_policy must equal {ABSENCE_POLICY}",
                )
            absence_text = ABSENCE_POLICY
        return cls(role, mode, contract_hash, absence_text)

    def to_payload(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "contract_sha256": self.contract_sha256,
            "absence_policy": self.absence_policy,
        }


@dataclass(frozen=True)
class StrategySpecV2:
    status: str
    strategy_id: str
    strategy_version: str
    candidate_id: str
    variant_id: str
    execution_identity: ExecutionIdentity
    strategy_entrypoint: str
    parameters_canonical_json: str
    parameters_sha256: str
    execution_config_sha256: str
    data_requirements: Tuple[InputRequirement, ...]

    @property
    def parameters(self) -> Dict[str, object]:
        value = json.loads(self.parameters_canonical_json)
        if not isinstance(value, dict):
            raise ContractError("implementation.parameters is not an object")
        return value

    def requirement(self, role: str) -> InputRequirement:
        for requirement in self.data_requirements:
            if requirement.role == role:
                return requirement
        raise ContractError(f"data_requirements is missing {role}")

    def to_payload(self) -> Dict[str, object]:
        return {
            "schema_version": STRATEGY_SPEC_SCHEMA,
            "status": self.status,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "candidate_id": self.candidate_id,
            "variant_id": self.variant_id,
            "execution_identity": self.execution_identity.to_payload(),
            "implementation": {
                "strategy_entrypoint": self.strategy_entrypoint,
                "parameters": self.parameters,
                "parameters_sha256": self.parameters_sha256,
                "execution_config_sha256": self.execution_config_sha256,
            },
            "data_requirements": {
                requirement.role: requirement.to_payload()
                for requirement in self.data_requirements
            },
        }


def parse_strategy_spec_v2(payload: Mapping[str, object]) -> StrategySpecV2:
    root = _object(payload, "spec")
    _exact_keys(root, (
        "schema_version", "status", "strategy_id", "strategy_version",
        "candidate_id", "variant_id", "execution_identity", "implementation",
        "data_requirements",
    ), "spec")
    if root["schema_version"] != STRATEGY_SPEC_SCHEMA:
        raise ContractError(f"spec.schema_version must equal {STRATEGY_SPEC_SCHEMA}")
    if root["status"] != "FROZEN":
        raise ContractError("spec.status must equal FROZEN for execution authority")
    identity = ExecutionIdentity.from_payload(
        _object(root["execution_identity"], "spec.execution_identity"),
        "spec.execution_identity",
    )
    implementation = _object(root["implementation"], "spec.implementation")
    _exact_keys(implementation, (
        "strategy_entrypoint", "parameters", "parameters_sha256",
        "execution_config_sha256",
    ), "spec.implementation")
    parameters = _object(
        implementation["parameters"], "spec.implementation.parameters",
    )
    parameters_hash = _hash(
        implementation["parameters_sha256"],
        "spec.implementation.parameters_sha256",
    )
    if canonical_sha256(parameters) != parameters_hash:
        raise ContractError(
            "spec.implementation.parameters_sha256 does not match parameters",
        )
    requirements_payload = _object(
        root["data_requirements"], "spec.data_requirements",
    )
    _exact_keys(requirements_payload, REQUIREMENT_ROLES, "spec.data_requirements")
    requirements = tuple(
        InputRequirement.from_payload(
            role,
            _object(
                requirements_payload[role], f"spec.data_requirements.{role}",
            ),
            f"spec.data_requirements.{role}",
        )
        for role in REQUIREMENT_ROLES
    )
    for required_role in ("trade_price", "instrument_metadata"):
        requirement = next(item for item in requirements if item.role == required_role)
        if requirement.mode != "REQUIRED":
            raise ContractError(
                f"spec.data_requirements.{required_role} must be REQUIRED",
            )
    return StrategySpecV2(
        status="FROZEN",
        strategy_id=_text(root["strategy_id"], "spec.strategy_id"),
        strategy_version=_text(root["strategy_version"], "spec.strategy_version"),
        candidate_id=_text(root["candidate_id"], "spec.candidate_id"),
        variant_id=_text(root["variant_id"], "spec.variant_id"),
        execution_identity=identity,
        strategy_entrypoint=_entrypoint(
            implementation["strategy_entrypoint"],
            "spec.implementation.strategy_entrypoint",
        ),
        parameters_canonical_json=canonical_json_bytes(parameters).decode("utf-8"),
        parameters_sha256=parameters_hash,
        execution_config_sha256=_hash(
            implementation["execution_config_sha256"],
            "spec.implementation.execution_config_sha256",
        ),
        data_requirements=requirements,
    )


@dataclass(frozen=True)
class DatasetIdentity:
    role: str
    exchange: str
    market: str
    symbol: str
    data_timeframe: str
    timezone: str
    timestamp_semantics: str
    dataset_id: str
    dataset_sha256: str
    manifest_path: str
    manifest_id: str
    manifest_sha256: str
    coverage_start_ms: int
    coverage_end_ms: int

    @property
    def contract_sha256(self) -> str:
        return canonical_sha256(self.to_payload())

    def to_payload(self) -> Dict[str, object]:
        return {
            "schema_version": DATASET_IDENTITY_SCHEMA,
            "role": self.role,
            "exchange": self.exchange,
            "market": self.market,
            "symbol": self.symbol,
            "data_timeframe": self.data_timeframe,
            "timezone": self.timezone,
            "timestamp_semantics": self.timestamp_semantics,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "manifest_path": self.manifest_path,
            "manifest_id": self.manifest_id,
            "manifest_sha256": self.manifest_sha256,
            "coverage_start_ms": self.coverage_start_ms,
            "coverage_end_ms": self.coverage_end_ms,
        }


def parse_dataset_identity(payload: Mapping[str, object]) -> DatasetIdentity:
    root = _object(payload, "dataset_identity")
    _exact_keys(root, (
        "schema_version", "role", "exchange", "market", "symbol",
        "data_timeframe", "timezone", "timestamp_semantics", "dataset_id",
        "dataset_sha256", "manifest_path", "manifest_id", "manifest_sha256",
        "coverage_start_ms", "coverage_end_ms",
    ), "dataset_identity")
    if root["schema_version"] != DATASET_IDENTITY_SCHEMA:
        raise ContractError(
            f"dataset_identity.schema_version must equal {DATASET_IDENTITY_SCHEMA}",
        )
    role = _text(root["role"], "dataset_identity.role")
    if role not in DATASET_ROLES:
        raise ContractError(f"dataset_identity.role is unsupported: {role}")
    symbol = _text(root["symbol"], "dataset_identity.symbol")
    if symbol != symbol.upper() or _SYMBOL_RE.fullmatch(symbol) is None:
        raise ContractError("dataset_identity.symbol must be an uppercase exchange symbol")
    start = _integer(root["coverage_start_ms"], "dataset_identity.coverage_start_ms")
    end = _integer(root["coverage_end_ms"], "dataset_identity.coverage_end_ms")
    if start > end:
        raise ContractError("dataset_identity coverage start must not exceed end")
    manifest_path = _text(root["manifest_path"], "dataset_identity.manifest_path")
    if not Path(manifest_path).is_absolute():
        raise ContractError("dataset_identity.manifest_path must be an absolute frozen locator")
    return DatasetIdentity(
        role=role,
        exchange=_text(root["exchange"], "dataset_identity.exchange"),
        market=_text(root["market"], "dataset_identity.market"),
        symbol=symbol,
        data_timeframe=_text(root["data_timeframe"], "dataset_identity.data_timeframe"),
        timezone=_text(root["timezone"], "dataset_identity.timezone"),
        timestamp_semantics=_text(
            root["timestamp_semantics"], "dataset_identity.timestamp_semantics",
        ),
        dataset_id=_text(root["dataset_id"], "dataset_identity.dataset_id"),
        dataset_sha256=_hash(
            root["dataset_sha256"], "dataset_identity.dataset_sha256",
        ),
        manifest_path=manifest_path,
        manifest_id=_text(root["manifest_id"], "dataset_identity.manifest_id"),
        manifest_sha256=_hash(
            root["manifest_sha256"], "dataset_identity.manifest_sha256",
        ),
        coverage_start_ms=start,
        coverage_end_ms=end,
    )


@dataclass(frozen=True)
class MetadataProvenance:
    fidelity_classification: str
    source: str
    source_sha256: str
    effective_start_ms: Optional[int]
    effective_end_ms: Optional[int]

    def to_payload(self) -> Dict[str, object]:
        return {
            "fidelity_classification": self.fidelity_classification,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "effective_start_ms": self.effective_start_ms,
            "effective_end_ms": self.effective_end_ms,
        }


@dataclass(frozen=True)
class InstrumentMetadata:
    schema_version: str
    exchange: str
    market: str
    symbol: str
    metadata_id: str
    collected_at_utc: Optional[str]
    tick_size: str
    step_size: str
    min_qty: str
    min_notional: str
    price_precision: Optional[int]
    quantity_precision: Optional[int]
    provenance: MetadataProvenance

    @property
    def contract_sha256(self) -> str:
        return canonical_sha256(self.to_payload())

    def to_payload(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "schema_version": self.schema_version,
            "exchange": self.exchange,
            "market": self.market,
            "symbol": self.symbol,
            "metadata_id": self.metadata_id,
            "tick_size": self.tick_size,
            "step_size": self.step_size,
            "min_qty": self.min_qty,
            "min_notional": self.min_notional,
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "provenance": self.provenance.to_payload(),
        }
        if self.schema_version == INSTRUMENT_METADATA_SCHEMA_V2:
            payload["collected_at_utc"] = self.collected_at_utc
            ordered = (
                "schema_version", "exchange", "market", "symbol",
                "metadata_id", "collected_at_utc", "tick_size", "step_size",
                "min_qty", "min_notional", "price_precision",
                "quantity_precision", "provenance",
            )
            return {key: payload[key] for key in ordered}
        return payload


def parse_instrument_metadata(payload: Mapping[str, object]) -> InstrumentMetadata:
    root = _object(payload, "instrument_metadata")
    schema_version = root.get("schema_version")
    base_fields = (
        "schema_version", "exchange", "market", "symbol", "metadata_id",
        "tick_size", "step_size", "min_qty", "min_notional",
        "price_precision", "quantity_precision", "provenance",
    )
    if schema_version == INSTRUMENT_METADATA_SCHEMA:
        _exact_keys(root, base_fields, "instrument_metadata")
        collected_at_utc = None
    elif schema_version == INSTRUMENT_METADATA_SCHEMA_V2:
        _exact_keys(
            root,
            (*base_fields[:5], "collected_at_utc", *base_fields[5:]),
            "instrument_metadata",
        )
        collected_at_utc = _utc_timestamp(
            root["collected_at_utc"],
            "instrument_metadata.collected_at_utc",
        )
    else:
        raise ContractError(
            "instrument_metadata.schema_version is unsupported",
        )
    symbol = _text(root["symbol"], "instrument_metadata.symbol")
    if symbol != symbol.upper() or _SYMBOL_RE.fullmatch(symbol) is None:
        raise ContractError("instrument_metadata.symbol must be an uppercase exchange symbol")
    price_precision = _optional_integer(
        root["price_precision"], "instrument_metadata.price_precision",
    )
    quantity_precision = _optional_integer(
        root["quantity_precision"], "instrument_metadata.quantity_precision",
    )
    for name, value in (
        ("price_precision", price_precision),
        ("quantity_precision", quantity_precision),
    ):
        if value is not None and value < 0:
            raise ContractError(f"instrument_metadata.{name} must be non-negative")
    provenance_payload = _object(
        root["provenance"], "instrument_metadata.provenance",
    )
    _exact_keys(provenance_payload, (
        "fidelity_classification", "source", "source_sha256",
        "effective_start_ms", "effective_end_ms",
    ), "instrument_metadata.provenance")
    fidelity = _text(
        provenance_payload["fidelity_classification"],
        "instrument_metadata.provenance.fidelity_classification",
    )
    if fidelity not in METADATA_FIDELITY:
        raise ContractError(
            "instrument_metadata.provenance.fidelity_classification is unsupported",
        )
    effective_start = _optional_integer(
        provenance_payload["effective_start_ms"],
        "instrument_metadata.provenance.effective_start_ms",
    )
    effective_end = _optional_integer(
        provenance_payload["effective_end_ms"],
        "instrument_metadata.provenance.effective_end_ms",
    )
    if fidelity == "HISTORICAL_VERIFIED":
        if effective_start is None or effective_end is None:
            raise ContractError(
                "historically verified metadata requires effective start and end",
            )
        if effective_start > effective_end:
            raise ContractError("instrument metadata effective start must not exceed end")
    elif effective_start is not None or effective_end is not None:
        if effective_start is None or effective_end is None or effective_start > effective_end:
            raise ContractError("instrument metadata effective range must be complete and ordered")
    provenance = MetadataProvenance(
        fidelity_classification=fidelity,
        source=_text(
            provenance_payload["source"], "instrument_metadata.provenance.source",
        ),
        source_sha256=_hash(
            provenance_payload["source_sha256"],
            "instrument_metadata.provenance.source_sha256",
        ),
        effective_start_ms=effective_start,
        effective_end_ms=effective_end,
    )
    return InstrumentMetadata(
        schema_version=str(schema_version),
        exchange=_text(root["exchange"], "instrument_metadata.exchange"),
        market=_text(root["market"], "instrument_metadata.market"),
        symbol=symbol,
        metadata_id=_text(root["metadata_id"], "instrument_metadata.metadata_id"),
        collected_at_utc=collected_at_utc,
        tick_size=_positive_decimal_text(
            root["tick_size"], "instrument_metadata.tick_size",
        ),
        step_size=_positive_decimal_text(
            root["step_size"], "instrument_metadata.step_size",
        ),
        min_qty=_positive_decimal_text(
            root["min_qty"], "instrument_metadata.min_qty",
        ),
        min_notional=_positive_decimal_text(
            root["min_notional"], "instrument_metadata.min_notional",
        ),
        price_precision=price_precision,
        quantity_precision=quantity_precision,
        provenance=provenance,
    )


def require_downstream_symbol(
    authoritative_symbol: str, downstream_symbol: str, path: str,
) -> None:
    """Reject any downstream attempt to select or mutate the run symbol."""
    if downstream_symbol != authoritative_symbol:
        raise ContractError(
            f"{path} differs from authoritative symbol {authoritative_symbol}",
        )


def _require_identity_match(
    authoritative: ExecutionIdentity,
    *,
    exchange: str,
    market: str,
    symbol: str,
    path: str,
) -> None:
    for field, actual in (
        ("exchange", exchange), ("market", market), ("symbol", symbol),
    ):
        expected = getattr(authoritative, field)
        if actual != expected:
            raise ContractError(
                f"{path}.{field} differs from authoritative execution identity",
            )


def _require_requirement(
    requirement: InputRequirement,
    contract: Optional[object],
    path: str,
) -> None:
    if requirement.mode == "REQUIRED" and contract is None:
        raise ContractError(f"{path} is required by frozen strategy spec")
    if requirement.mode == "EXPLICITLY_NOT_USED" and contract is not None:
        raise ContractError(f"{path} is explicitly not used by frozen strategy spec")


@dataclass(frozen=True)
class BoundExecutionContracts:
    execution_identity: ExecutionIdentity
    trade_price: DatasetIdentity
    funding: Optional[DatasetIdentity]
    mark_price: Optional[DatasetIdentity]
    instrument_metadata: InstrumentMetadata

    def contract_hash_payload(self) -> Dict[str, object]:
        return {
            "trade_price_contract_sha256": self.trade_price.contract_sha256,
            "funding_contract_sha256": (
                self.funding.contract_sha256 if self.funding is not None else None
            ),
            "mark_price_contract_sha256": (
                self.mark_price.contract_sha256
                if self.mark_price is not None else None
            ),
            "instrument_metadata_contract_sha256": (
                self.instrument_metadata.contract_sha256
            ),
        }


def bind_execution_contracts(
    spec: StrategySpecV2,
    *,
    trade_price: Optional[DatasetIdentity],
    funding: Optional[DatasetIdentity],
    mark_price: Optional[DatasetIdentity],
    instrument_metadata: Optional[InstrumentMetadata],
) -> BoundExecutionContracts:
    """Bind all inputs to the sole symbol authority before execution."""
    identity = spec.execution_identity
    supplied = {
        "trade_price": trade_price,
        "funding": funding,
        "mark_price": mark_price,
        "instrument_metadata": instrument_metadata,
    }
    for role in REQUIREMENT_ROLES:
        _require_requirement(spec.requirement(role), supplied[role], role)

    if trade_price is None:
        raise ContractError("trade_price is required by frozen strategy spec")
    if instrument_metadata is None:
        raise ContractError(
            "instrument_metadata is required by frozen strategy spec",
        )

    datasets = (
        ("trade_price", trade_price),
        ("funding", funding),
        ("mark_price", mark_price),
    )
    for role, dataset in datasets:
        if dataset is None:
            continue
        if dataset.role != role:
            raise ContractError(f"{role}.role must equal {role}")
        _require_identity_match(
            identity,
            exchange=dataset.exchange,
            market=dataset.market,
            symbol=dataset.symbol,
            path=role,
        )
        if role in {"trade_price", "mark_price"} and (
            dataset.data_timeframe != identity.execution_timeframe
        ):
            raise ContractError(
                f"{role}.data_timeframe differs from execution_timeframe",
            )
        if role == "trade_price":
            if dataset.timezone != identity.timezone:
                raise ContractError("trade_price.timezone differs from execution identity")
            if dataset.timestamp_semantics != identity.timestamp_semantics:
                raise ContractError(
                    "trade_price.timestamp_semantics differs from execution identity",
                )
        expected_hash = spec.requirement(role).contract_sha256
        if dataset.contract_sha256 != expected_hash:
            raise ContractError(f"{role}.contract_sha256 differs from frozen spec")

    _require_identity_match(
        identity,
        exchange=instrument_metadata.exchange,
        market=instrument_metadata.market,
        symbol=instrument_metadata.symbol,
        path="instrument_metadata",
    )
    metadata_hash = spec.requirement("instrument_metadata").contract_sha256
    if instrument_metadata.contract_sha256 != metadata_hash:
        raise ContractError(
            "instrument_metadata.contract_sha256 differs from frozen spec",
        )
    return BoundExecutionContracts(
        execution_identity=identity,
        trade_price=trade_price,
        funding=funding,
        mark_price=mark_price,
        instrument_metadata=instrument_metadata,
    )


def require_dataset_coverage(
    dataset: DatasetIdentity,
    *,
    required_start_ms: int,
    required_end_ms: int,
    path: str,
) -> None:
    """Require one frozen dataset to contain the complete execution window."""
    if required_start_ms > required_end_ms:
        raise ContractError("required execution coverage start must not exceed end")
    if (
        dataset.coverage_start_ms > required_start_ms
        or dataset.coverage_end_ms < required_end_ms
    ):
        raise ContractError(
            f"{path}.coverage does not contain required execution window",
        )


_CLAIM_KEYS = (
    "run_id", "execution_identity", "strategy_spec_sha256",
    "strategy_entrypoint", "strategy_parameters_sha256",
    "trade_price_contract_sha256", "funding_contract_sha256",
    "mark_price_contract_sha256", "instrument_metadata_contract_sha256",
)


@dataclass(frozen=True)
class _IdentityClaims:
    run_id: str
    execution_identity: ExecutionIdentity
    strategy_spec_sha256: str
    strategy_entrypoint: str
    strategy_parameters_sha256: str
    trade_price_contract_sha256: str
    funding_contract_sha256: Optional[str]
    mark_price_contract_sha256: Optional[str]
    instrument_metadata_contract_sha256: str

    def claim_payload(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "execution_identity": self.execution_identity.to_payload(),
            "strategy_spec_sha256": self.strategy_spec_sha256,
            "strategy_entrypoint": self.strategy_entrypoint,
            "strategy_parameters_sha256": self.strategy_parameters_sha256,
            "trade_price_contract_sha256": self.trade_price_contract_sha256,
            "funding_contract_sha256": self.funding_contract_sha256,
            "mark_price_contract_sha256": self.mark_price_contract_sha256,
            "instrument_metadata_contract_sha256": (
                self.instrument_metadata_contract_sha256
            ),
        }


def _parse_claims(payload: Mapping[str, object], path: str) -> _IdentityClaims:
    return _IdentityClaims(
        run_id=_text(payload["run_id"], f"{path}.run_id"),
        execution_identity=ExecutionIdentity.from_payload(
            _object(payload["execution_identity"], f"{path}.execution_identity"),
            f"{path}.execution_identity",
        ),
        strategy_spec_sha256=_hash(
            payload["strategy_spec_sha256"], f"{path}.strategy_spec_sha256",
        ),
        strategy_entrypoint=_entrypoint(
            payload["strategy_entrypoint"], f"{path}.strategy_entrypoint",
        ),
        strategy_parameters_sha256=_hash(
            payload["strategy_parameters_sha256"],
            f"{path}.strategy_parameters_sha256",
        ),
        trade_price_contract_sha256=_hash(
            payload["trade_price_contract_sha256"],
            f"{path}.trade_price_contract_sha256",
        ),
        funding_contract_sha256=_optional_hash(
            payload["funding_contract_sha256"],
            f"{path}.funding_contract_sha256",
        ),
        mark_price_contract_sha256=_optional_hash(
            payload["mark_price_contract_sha256"],
            f"{path}.mark_price_contract_sha256",
        ),
        instrument_metadata_contract_sha256=_hash(
            payload["instrument_metadata_contract_sha256"],
            f"{path}.instrument_metadata_contract_sha256",
        ),
    )


@dataclass(frozen=True)
class ResultMetadataV3A(_IdentityClaims):
    def to_payload(self) -> Dict[str, object]:
        return {"schema_version": RESULT_METADATA_SCHEMA, **self.claim_payload()}


def parse_result_metadata(payload: Mapping[str, object]) -> ResultMetadataV3A:
    root = _object(payload, "result")
    _exact_keys(root, ("schema_version", *_CLAIM_KEYS), "result")
    if root["schema_version"] != RESULT_METADATA_SCHEMA:
        raise ContractError(f"result.schema_version must equal {RESULT_METADATA_SCHEMA}")
    return ResultMetadataV3A(**_parse_claims(root, "result").__dict__)


@dataclass(frozen=True)
class ExecutionAttestationV3A(_IdentityClaims):
    execution_id: str
    result_metadata_sha256: str
    code_identity_sha256: str

    def to_payload(self) -> Dict[str, object]:
        return {
            "schema_version": ATTESTATION_SCHEMA,
            **self.claim_payload(),
            "execution_id": self.execution_id,
            "result_metadata_sha256": self.result_metadata_sha256,
            "code_identity_sha256": self.code_identity_sha256,
        }


def parse_execution_attestation(
    payload: Mapping[str, object],
) -> ExecutionAttestationV3A:
    root = _object(payload, "attestation")
    _exact_keys(root, (
        "schema_version", *_CLAIM_KEYS, "execution_id",
        "result_metadata_sha256", "code_identity_sha256",
    ), "attestation")
    if root["schema_version"] != ATTESTATION_SCHEMA:
        raise ContractError(
            f"attestation.schema_version must equal {ATTESTATION_SCHEMA}",
        )
    claims = _parse_claims(root, "attestation")
    return ExecutionAttestationV3A(
        **claims.__dict__,
        execution_id=_text(root["execution_id"], "attestation.execution_id"),
        result_metadata_sha256=_hash(
            root["result_metadata_sha256"],
            "attestation.result_metadata_sha256",
        ),
        code_identity_sha256=_hash(
            root["code_identity_sha256"], "attestation.code_identity_sha256",
        ),
    )


@dataclass(frozen=True)
class RunReceiptV3A(_IdentityClaims):
    authority: str
    execution_id: str
    result_metadata_sha256: str
    execution_attestation_sha256: str
    code_identity_sha256: str

    def to_payload(self) -> Dict[str, object]:
        return {
            "schema_version": RECEIPT_SCHEMA,
            "authority": self.authority,
            **self.claim_payload(),
            "execution_id": self.execution_id,
            "result_metadata_sha256": self.result_metadata_sha256,
            "execution_attestation_sha256": self.execution_attestation_sha256,
            "code_identity_sha256": self.code_identity_sha256,
        }


def parse_run_receipt(payload: Mapping[str, object]) -> RunReceiptV3A:
    root = _object(payload, "receipt")
    _exact_keys(root, (
        "schema_version", "authority", *_CLAIM_KEYS, "execution_id",
        "result_metadata_sha256", "execution_attestation_sha256",
        "code_identity_sha256",
    ), "receipt")
    if root["schema_version"] != RECEIPT_SCHEMA:
        raise ContractError(f"receipt.schema_version must equal {RECEIPT_SCHEMA}")
    if root["authority"] != "ATOMIC_PRODUCTION_RUNNER_V3A":
        raise ContractError("receipt.authority must equal ATOMIC_PRODUCTION_RUNNER_V3A")
    claims = _parse_claims(root, "receipt")
    return RunReceiptV3A(
        **claims.__dict__,
        authority="ATOMIC_PRODUCTION_RUNNER_V3A",
        execution_id=_text(root["execution_id"], "receipt.execution_id"),
        result_metadata_sha256=_hash(
            root["result_metadata_sha256"], "receipt.result_metadata_sha256",
        ),
        execution_attestation_sha256=_hash(
            root["execution_attestation_sha256"],
            "receipt.execution_attestation_sha256",
        ),
        code_identity_sha256=_hash(
            root["code_identity_sha256"], "receipt.code_identity_sha256",
        ),
    )


class StateIdentityLike(Protocol):
    @property
    def run_id(self) -> str: ...
    @property
    def execution_id(self) -> str: ...
    @property
    def execution_identity(self) -> ExecutionIdentity: ...
    @property
    def strategy_spec_sha256(self) -> str: ...
    @property
    def strategy_entrypoint(self) -> str: ...
    @property
    def strategy_parameters_sha256(self) -> str: ...
    @property
    def trade_price_contract_sha256(self) -> str: ...
    @property
    def funding_contract_sha256(self) -> Optional[str]: ...
    @property
    def mark_price_contract_sha256(self) -> Optional[str]: ...
    @property
    def instrument_metadata_contract_sha256(self) -> str: ...
    @property
    def result_metadata_sha256(self) -> str: ...
    @property
    def execution_attestation_sha256(self) -> str: ...
    @property
    def receipt_sha256(self) -> str: ...
    @property
    def code_identity_sha256(self) -> str: ...


def _expected_claims(
    spec: StrategySpecV2, bound: BoundExecutionContracts,
) -> Dict[str, object]:
    return {
        "execution_identity": spec.execution_identity,
        "strategy_spec_sha256": canonical_sha256(spec.to_payload()),
        "strategy_entrypoint": spec.strategy_entrypoint,
        "strategy_parameters_sha256": spec.parameters_sha256,
        **bound.contract_hash_payload(),
    }


def _validate_claim_object(
    expected: Mapping[str, object], actual: object, path: str,
) -> None:
    for field, expected_value in expected.items():
        if getattr(actual, field) != expected_value:
            raise ContractError(f"{path}.{field} differs from frozen identity chain")


def revalidate_identity_chain(
    spec: StrategySpecV2,
    bound: BoundExecutionContracts,
    result: ResultMetadataV3A,
    attestation: ExecutionAttestationV3A,
    receipt: RunReceiptV3A,
    state: StateIdentityLike,
) -> None:
    """Independently revalidate every persisted symbol and input identity."""
    if bound.execution_identity != spec.execution_identity:
        raise ContractError(
            "contracts.execution_identity differs from frozen strategy spec",
        )
    expected = _expected_claims(spec, bound)
    _validate_claim_object(expected, result, "result")
    _validate_claim_object(expected, attestation, "attestation")
    _validate_claim_object(expected, receipt, "receipt")
    _validate_claim_object(expected, state, "state")
    if not (
        result.run_id == attestation.run_id == receipt.run_id == state.run_id
    ):
        raise ContractError("run_id differs across V3-A identity chain")
    if not (
        attestation.execution_id == receipt.execution_id == state.execution_id
    ):
        raise ContractError("execution_id differs across V3-A identity chain")
    result_hash = canonical_sha256(result.to_payload())
    if attestation.result_metadata_sha256 != result_hash:
        raise ContractError("attestation.result_metadata_sha256 mismatch")
    if receipt.result_metadata_sha256 != result_hash:
        raise ContractError("receipt.result_metadata_sha256 mismatch")
    attestation_hash = canonical_sha256(attestation.to_payload())
    if receipt.execution_attestation_sha256 != attestation_hash:
        raise ContractError("receipt.execution_attestation_sha256 mismatch")
    if state.result_metadata_sha256 != result_hash:
        raise ContractError("state.result_metadata_sha256 mismatch")
    if state.execution_attestation_sha256 != attestation_hash:
        raise ContractError("state.execution_attestation_sha256 mismatch")
    receipt_hash = canonical_sha256(receipt.to_payload())
    if state.receipt_sha256 != receipt_hash:
        raise ContractError("state.receipt_sha256 mismatch")
    if not (
        attestation.code_identity_sha256
        == receipt.code_identity_sha256
        == state.code_identity_sha256
    ):
        raise ContractError("code identity differs across V3-A identity chain")
    if getattr(state, "status", None) != "COMPLETE":
        raise ContractError("state.status must equal COMPLETE")


__all__ = [
    "ABSENCE_POLICY",
    "ATTESTATION_SCHEMA",
    "DATASET_IDENTITY_SCHEMA",
    "INSTRUMENT_METADATA_SCHEMA",
    "INSTRUMENT_METADATA_SCHEMA_V2",
    "RECEIPT_SCHEMA",
    "RESULT_METADATA_SCHEMA",
    "STRATEGY_SPEC_SCHEMA",
    "BoundExecutionContracts",
    "ContractError",
    "DatasetIdentity",
    "ExecutionAttestationV3A",
    "ExecutionIdentity",
    "InputRequirement",
    "InstrumentMetadata",
    "MetadataProvenance",
    "ResultMetadataV3A",
    "RunReceiptV3A",
    "StrategySpecV2",
    "bind_execution_contracts",
    "canonical_json_bytes",
    "canonical_sha256",
    "parse_dataset_identity",
    "parse_execution_attestation",
    "parse_instrument_metadata",
    "parse_result_metadata",
    "parse_run_receipt",
    "parse_strategy_spec_v2",
    "require_downstream_symbol",
    "require_dataset_coverage",
    "revalidate_identity_chain",
]
