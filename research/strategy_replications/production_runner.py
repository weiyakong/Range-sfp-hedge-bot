"""Atomic, execution-attested production runner for strategy replications.

V1 validators remain useful for frozen-contract validation, but a V1 receipt is
not proof that a particular ``BacktestResult`` came from the declared inputs.
This module is the sole authoritative V2 production path: it owns strategy
loading, test execution, the exact bar/config objects passed to V2, output
creation, semantic rereading, canonical state registration, and receipt issue.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Dict, Mapping, Optional, Sequence, Tuple

from research.backtester_v2.engine import BacktestEngine, Strategy
from research.backtester_v2.metrics import summarize
from research.backtester_v2.models import (
    BacktestConfig,
    BacktestResult,
    Bar,
    IntrabarAmbiguity,
    MaintenanceTier,
    OrderIntent,
    PendingOrder,
    Position,
    RejectedOrder,
    ReplicationLineage,
    Trade,
)
from research.backtester_v2.output import build_run_metadata, write_results
from research.strategy_replications.validation.core import (
    CANONICAL_CAPABILITY_RELATIVE_PATH,
    EXECUTION_CRITICAL_PATHS,
    ValidationReport,
    compute_fidelity_summary,
    create_production_preflight_context,
    load_json,
    sha256_file,
)


RUN_RECEIPT_SCHEMA = "RUN_RECEIPT_V2"
ATTESTATION_SCHEMA = "EXECUTION_ATTESTATION_V1"
TEST_EVIDENCE_SCHEMA = "RUNNER_TEST_EXECUTION_V1"
OUTPUT_MANIFEST_SCHEMA = "PRODUCTION_OUTPUT_MANIFEST_V2"
STATE_SCHEMA = "ENFORCEMENT_STATE_V2"
STATE_RELATIVE_PATH = Path(".strategy-replication/enforcement-v2.sqlite3")
V2_ADDITIONAL_ARTIFACTS = {
    "execution_attestation.json", "test_execution.json", "result.json",
}
TEST_RESULT_SENTINEL = "__CODEX_STRATEGY_TEST_RESULT__="
TEST_RUNNER_SCRIPT = """
import json
import pathlib
import sys
import unittest

class CapturingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successful_ids = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.successful_ids.append({
            "method": getattr(test, "_testMethodName", ""),
            "identifier": test.id(),
        })

suite_dir = pathlib.Path(sys.argv[1]).resolve()
suite_name = sys.argv[2]
suite = unittest.defaultTestLoader.discover(str(suite_dir), pattern=suite_name)
result = unittest.TextTestRunner(verbosity=2, resultclass=CapturingResult).run(suite)
print("__CODEX_STRATEGY_TEST_RESULT__=" + json.dumps({
    "successful": result.successful_ids,
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(result.skipped),
}, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _load_json_snapshot(source: bytes, label: str) -> Dict[str, object]:
    try:
        payload = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse immutable {label} snapshot: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"immutable {label} snapshot must contain a JSON object")
    return payload


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _regular_file(path: Path, label: str) -> Path:
    """Resolve one immutable input while refusing file-level symlink indirection."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")
    return path.resolve()


def _execution_critical_hashes(repo_root: Path) -> Dict[str, str]:
    return {
        relative: sha256_file(_regular_file(repo_root / relative, relative))
        for relative in EXECUTION_CRITICAL_PATHS
    }


def _upstream_files(request: "ProductionRunRequest", repo_root: Path) -> Dict[str, Dict[str, str]]:
    paths = {
        "spec": request.spec_path,
        "registry": request.registry_path,
        "protocol": request.protocol_path,
        "data_manifest": request.data_manifest_path,
        "freeze_receipt": request.freeze_receipt_path,
        "strategy_code": request.strategy_code_path,
        "strategy_test_suite": request.strategy_test_suite_path,
        "capability_manifest": repo_root / CANONICAL_CAPABILITY_RELATIVE_PATH,
    }
    if request.previous_registry_path is not None:
        paths["previous_registry"] = request.previous_registry_path
    result: Dict[str, Dict[str, str]] = {}
    for name, path in paths.items():
        resolved = _regular_file(path, name)
        result[name] = {"path": str(resolved), "sha256": sha256_file(resolved)}
    return result


@dataclass(frozen=True)
class ProductionRunRequest:
    repo_root: Path
    spec_path: Path
    registry_path: Path
    protocol_path: Path
    data_manifest_path: Path
    freeze_receipt_path: Path
    strategy_code_path: Path
    strategy_test_suite_path: Path
    bars: Sequence[Bar]
    config: BacktestConfig
    run_stage: str
    output_dir: Path
    symbol: str
    market: str
    timeframe: str
    strategy_name: str
    source_reference: str
    source_type: str = "external_replication"
    previous_registry_path: Optional[Path] = None


@dataclass(frozen=True)
class ProductionRunOutcome:
    run_id: str
    execution_id: str
    output_dir: Path
    receipt_path: Path
    receipt_sha256: str


@dataclass(frozen=True)
class ExecutionAttestation:
    schema_version: str
    execution_id: str
    run_id: str
    run_stage: str
    created_at_utc: str
    bars_sha256: str
    bar_count: int
    actual_start: int
    actual_end: int
    symbol: str
    market: str
    timeframe: str
    timestamp_semantics: str
    config_sha256: str
    config_payload_sha256: str
    strategy_code_sha256: str
    strategy_symbol: str
    strategy_parameters_sha256: str
    engine_code_sha256: str
    runner_code_sha256: str
    enforcement_code_sha256: str
    git_commit: str
    data_manifest_sha256: str
    result_sha256: str
    test_execution_sha256: str
    execution_critical_sha256: Mapping[str, str]
    qa_dimensions: Mapping[str, str]


def _config_payload(config: BacktestConfig) -> Dict[str, object]:
    payload = asdict(config)
    payload["funding_rate_by_time"] = {
        str(key): value for key, value in config.funding_rate_by_time.items()
    }
    payload["funding_price_by_time"] = {
        str(key): value for key, value in config.funding_price_by_time.items()
    }
    return payload


def _config_from_payload(payload: Mapping[str, object]) -> BacktestConfig:
    values = dict(payload)
    values["funding_rate_by_time"] = {
        int(key): float(value)
        for key, value in dict(values.get("funding_rate_by_time", {})).items()
    }
    values["funding_price_by_time"] = {
        int(key): float(value)
        for key, value in dict(values.get("funding_price_by_time", {})).items()
    }
    values["maintenance_tiers"] = tuple(
        MaintenanceTier(**item) if isinstance(item, dict) else item
        for item in values.get("maintenance_tiers", ())
    )
    return BacktestConfig(**values)


def _clone_config(config: BacktestConfig) -> BacktestConfig:
    """Remove mutable-dict aliasing while preserving exact config semantics."""
    return _config_from_payload(json.loads(_canonical_bytes(_config_payload(config))))


def canonical_config_sha256(config: BacktestConfig) -> str:
    """Hash every BacktestConfig field using its canonical serialized payload."""
    return _canonical_hash(_config_payload(config))


def load_backtest_config(path: Path) -> BacktestConfig:
    """Load one strict JSON config for the atomic production runner."""
    return _config_from_payload(load_json(path))


def _bar_payload(bar: Bar) -> Dict[str, object]:
    return {item.name: getattr(bar, item.name) for item in fields(Bar)}


def canonical_bars_sha256(bars: Sequence[Bar]) -> str:
    """Hash the exact ordered Bar stream used by the engine."""
    digest = hashlib.sha256()
    for bar in bars:
        digest.update(_canonical_bytes(_bar_payload(bar)))
        digest.update(b"\n")
    return digest.hexdigest()


def _strategy_parameters(spec: Mapping[str, object]) -> Dict[str, object]:
    parameters = spec.get("parameters")
    if not isinstance(parameters, list):
        raise ValueError("strategy spec parameters must be an array")
    result: Dict[str, object] = {}
    for item in parameters:
        if not isinstance(item, dict) or not isinstance(item.get("parameter_id"), str):
            raise ValueError("strategy parameter identity is invalid")
        result[str(item["parameter_id"])] = item.get("value")
    return result


def _strategy_symbol(spec: Mapping[str, object]) -> str:
    implementation = spec.get("implementation")
    symbol = implementation.get("strategy_symbol") if isinstance(implementation, dict) else None
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("frozen strategy spec requires implementation.strategy_symbol")
    if any(not part.isidentifier() or part.startswith("_") for part in symbol.split(".")):
        raise ValueError("frozen strategy symbol must be a public dotted Python symbol")
    return symbol


def _load_strategy(
    source: bytes, source_path: Path, symbol: str,
    parameters: Mapping[str, object],
) -> Strategy:
    module_name = f"_strategy_replication_{uuid.uuid4().hex}"
    module = ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__package__ = ""
    try:
        code = compile(source, str(source_path), "exec")
        exec(code, module.__dict__)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot load locked strategy module: {source_path}: {exc}") from exc
    target: object = module
    for part in symbol.split("."):
        if part.startswith("_") or not hasattr(target, part):
            raise ValueError(f"locked strategy symbol does not exist: {symbol}")
        target = getattr(target, part)
    if not callable(target):
        raise ValueError("locked strategy symbol must be callable")
    try:
        strategy = target(**dict(parameters))
    except TypeError as exc:
        raise ValueError(f"strategy constructor does not accept frozen parameters: {exc}") from exc
    if not callable(getattr(strategy, "on_bar", None)):
        raise ValueError("strategy instance must provide on_bar")
    return strategy


def _data_contract(path: Path) -> Mapping[str, object]:
    manifest = load_json(path)
    contract = manifest.get("production_contract")
    if not isinstance(contract, dict):
        raise ValueError("V2 production data manifest requires production_contract")
    required = {
        "symbol", "market", "timeframe", "timestamp_semantics", "bars_sha256",
        "row_count", "tested_start", "tested_end",
    }
    missing = required - set(contract)
    text_fields = {"symbol", "market", "timeframe", "timestamp_semantics"}
    invalid_text = [
        key for key in text_fields
        if not isinstance(contract.get(key), str) or not str(contract[key]).strip()
    ]
    digest = contract.get("bars_sha256")
    invalid_digest = (
        not isinstance(digest, str) or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    )
    invalid_numbers = [
        key for key in ("row_count", "tested_start", "tested_end")
        if not isinstance(contract.get(key), int) or isinstance(contract.get(key), bool)
    ]
    invalid = set(missing) | set(invalid_text) | set(invalid_numbers)
    if invalid_digest:
        invalid.add("bars_sha256")
    if invalid:
        raise ValueError(f"invalid production data contract; missing/invalid: {sorted(invalid)}")
    return MappingProxyType(dict(contract))


def _run_test_suite(
    *, suite_path: Path, spec: Mapping[str, object], spec_path: Path,
    strategy_spec_sha256: str,
    strategy_code_path: Path, strategy_code_sha256: str,
    strategy_symbol: str, evidence_path: Path,
) -> Dict[str, object]:
    command = [sys.executable, "-c", TEST_RUNNER_SCRIPT, str(suite_path.parent), suite_path.name]
    completed = subprocess.run(command, capture_output=True, text=True)
    tests = spec.get("tests")
    required_ids = tests.get("test_ids", []) if isinstance(tests, dict) else []
    if not isinstance(required_ids, list) or not required_ids:
        raise ValueError("strategy spec requires non-empty test_ids")
    suite_hash = sha256_file(suite_path)
    if not isinstance(tests, dict) or tests.get("suite_sha256") != suite_hash:
        raise ValueError("executed test suite differs from frozen strategy spec")
    structured_lines = [
        line.removeprefix(TEST_RESULT_SENTINEL)
        for line in completed.stdout.splitlines()
        if line.startswith(TEST_RESULT_SENTINEL)
    ]
    structured = None
    if structured_lines:
        try:
            structured = json.loads(structured_lines[-1])
        except json.JSONDecodeError:
            structured = None
    successful = structured.get("successful", []) if isinstance(structured, dict) else []
    successful_methods = {
        item.get("method") for item in successful if isinstance(item, dict)
    }
    missing = [
        item for item in required_ids
        if not isinstance(item, str) or item not in successful_methods
    ]
    if completed.returncode != 0 or missing or not isinstance(structured, dict):
        raise ValueError(
            f"strategy tests did not produce executed PASS evidence: "
            f"exit={completed.returncode}, missing={missing}"
        )
    evidence: Dict[str, object] = {
        "schema_version": "STRATEGY_TEST_RESULTS_V1",
        "runner_evidence_schema": TEST_EVIDENCE_SCHEMA,
        "execution_id": str(uuid.uuid4()),
        "executed_at_utc": _utc_now(),
        "command": command,
        "exit_code": completed.returncode,
        "strategy_spec_sha256": strategy_spec_sha256,
        "strategy_code_sha256": strategy_code_sha256,
        "strategy_symbol": strategy_symbol,
        "test_suite_path": str(suite_path.resolve()),
        "test_suite_sha256": suite_hash,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "required_test_ids": list(required_ids),
        "executed_test_ids": successful,
        "tests_run": structured["tests_run"],
        "results": [
            {
                "test_id": item,
                "test_identifier": next(
                    entry["identifier"] for entry in successful if entry["method"] == item
                ),
                "result": "PASS",
            }
            for item in required_ids
        ],
    }
    _write_json(evidence_path, evidence)
    return evidence


def _lineage(
    spec: Mapping[str, object], registry: Mapping[str, object],
    protocol: Mapping[str, object], paths: ProductionRunRequest,
    strategy_spec_sha256: str,
) -> ReplicationLineage:
    return ReplicationLineage(
        candidate_id=str(spec["candidate_id"]), variant_id=str(spec["variant_id"]),
        registry_version=str(registry["registry_version"]),
        registry_sha256=sha256_file(paths.registry_path),
        protocol_version=str(protocol["protocol_version"]),
        protocol_sha256=sha256_file(paths.protocol_path),
        strategy_spec_sha256=strategy_spec_sha256,
        fidelity_classification=compute_fidelity_summary(spec),
        comparability_class=str(spec["comparability_class"]),
        capability_manifest_version="BACKTESTER_V2_EXECUTION_CONTRACT_4",
        freeze_receipt_sha256=sha256_file(paths.freeze_receipt_path),
    )


def _result_payload(result: BacktestResult) -> Dict[str, object]:
    return asdict(result)


def _result_from_payload(payload: Mapping[str, object]) -> BacktestResult:
    def position(value: Mapping[str, object]) -> Position:
        return Position(**dict(value))

    def pending(value: Mapping[str, object]) -> PendingOrder:
        values = dict(value)
        values["intent"] = OrderIntent(**dict(values["intent"]))
        return PendingOrder(**values)

    return BacktestResult(
        final_cash=float(payload["final_cash"]), final_equity=float(payload["final_equity"]),
        trades=[Trade(**dict(item)) for item in payload["trades"]],
        equity_curve=[tuple(item) for item in payload["equity_curve"]],
        intrabar_equity_curve=[tuple(item) for item in payload["intrabar_equity_curve"]],
        bar_exposure_curve=[tuple(item) for item in payload["bar_exposure_curve"]],
        open_positions={str(key): position(value) for key, value in dict(payload["open_positions"]).items()},
        pending_orders={str(key): pending(value) for key, value in dict(payload["pending_orders"]).items()},
        rejected_orders=[RejectedOrder(**dict(item)) for item in payload["rejected_orders"]],
        intrabar_ambiguities=[IntrabarAmbiguity(
            **{
                **dict(item),
                "open_legs_before": tuple(item["open_legs_before"]),
                "resulting_trade_indices": tuple(item["resulting_trade_indices"]),
                "resulting_legs": tuple(item["resulting_legs"]),
            }
        ) for item in payload["intrabar_ambiguities"]],
        open_position_unrealized_pnl=float(payload["open_position_unrealized_pnl"]),
        open_position_entry_fee=float(payload["open_position_entry_fee"]),
        open_position_funding=float(payload["open_position_funding"]),
        qa_status=str(payload["qa_status"]),
        qa_issues=tuple(payload["qa_issues"]),
    )


def _csv_expected_rows(result: BacktestResult) -> Dict[str, Tuple[Tuple[str, ...], list]]:
    return {
        "trades.csv": (
            tuple(item.name for item in fields(Trade)),
            [asdict(item) for item in result.trades],
        ),
        "equity.csv": (
            ("open_time", "equity"),
            [{"open_time": timestamp, "equity": value} for timestamp, value in result.equity_curve],
        ),
        "intrabar_equity.csv": (
            ("open_time", "worst_equity"),
            [{"open_time": timestamp, "worst_equity": value} for timestamp, value in result.intrabar_equity_curve],
        ),
        "bar_exposure.csv": (
            ("open_time", "any_position_active"),
            [{"open_time": timestamp, "any_position_active": value} for timestamp, value in result.bar_exposure_curve],
        ),
        "rejected_orders.csv": (
            ("bar_time", "side", "reason", "order_type", "qty", "limit_price", "attempted_fill_price", "event_type"),
            [asdict(item) for item in result.rejected_orders],
        ),
        "intrabar_ambiguities.csv": (
            ("bar_time", "open_legs_before", "competing_paths", "chosen_path", "resulting_trade_indices", "resulting_legs", "competing_events", "reason"),
            [asdict(item) for item in result.intrabar_ambiguities],
        ),
    }


def _csv_cell(value: object) -> str:
    return "" if value is None else str(value)


def _validate_semantic_outputs(output_dir: Path) -> ValidationReport:
    report = ValidationReport()
    required = {
        "trades.csv", "equity.csv", "intrabar_equity.csv", "bar_exposure.csv",
        "intrabar_ambiguities.csv", "rejected_orders.csv", "metrics.json",
        "config.json", "exposure.json", "run_metadata.json",
        *V2_ADDITIONAL_ARTIFACTS,
    }
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        report.error("manifest", "regular output manifest is required")
        return report
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError) as exc:
        report.error("manifest", f"cannot parse output manifest: {exc}")
        return report
    if manifest.get("schema_version") != OUTPUT_MANIFEST_SCHEMA or manifest.get("status") != "COMPLETE":
        report.error("manifest", "V2 COMPLETE manifest is required")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or set(checksums) != required:
        report.error("manifest.checksums", "must contain the exact V2 artifact set")
        return report
    actual_files = {
        item.name for item in output_dir.iterdir()
        if item.name not in {"manifest.json", "run_receipt_v2.json"}
    }
    if actual_files != required:
        report.error("output", "actual artifact set differs from V2 contract")
    for name in required:
        path = output_dir / name
        if path.is_symlink() or not path.is_file():
            report.error(f"output.{name}", "regular file is required; symlinks are forbidden")
        elif checksums.get(name) != sha256_file(path):
            report.error(f"output.{name}", "checksum mismatch")
    if not report.ok:
        return report
    try:
        result_payload = load_json(output_dir / "result.json")
        result = _result_from_payload(result_payload)
        config_payload = load_json(output_dir / "config.json")
        config = _config_from_payload(config_payload)
        attestation = load_json(output_dir / "execution_attestation.json")
        metadata = load_json(output_dir / "run_metadata.json")
        metrics = load_json(output_dir / "metrics.json")
        exposure = load_json(output_dir / "exposure.json")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        report.error("output", f"cannot reconstruct canonical run: {exc}")
        return report
    if attestation.get("result_sha256") != sha256_file(output_dir / "result.json"):
        report.error("attestation.result_sha256", "result identity mismatch")
    if attestation.get("config_sha256") != sha256_file(output_dir / "config.json"):
        report.error("attestation.config_sha256", "config identity mismatch")
    if attestation.get("test_execution_sha256") != sha256_file(output_dir / "test_execution.json"):
        report.error("attestation.test_execution_sha256", "test evidence identity mismatch")
    if metadata.get("run_id") != attestation.get("run_id") or manifest.get("run_id") != attestation.get("run_id"):
        report.error("run_id", "manifest, metadata and attestation disagree")
    data = metadata.get("data")
    expected_data = {
        "tested_start": attestation.get("actual_start"),
        "tested_end": attestation.get("actual_end"),
        "row_count": attestation.get("bar_count"),
        "symbol": attestation.get("symbol"),
        "market": attestation.get("market"),
        "timeframe": attestation.get("timeframe"),
    }
    if not isinstance(data, dict) or any(data.get(key) != value for key, value in expected_data.items()):
        report.error("run_metadata.data", "does not match actual execution attestation")
    if metadata.get("run_stage") != attestation.get("run_stage"):
        report.error("run_metadata.run_stage", "does not match attested stage")
    if metadata.get("qa_dimensions") != attestation.get("qa_dimensions"):
        report.error("run_metadata.qa_dimensions", "does not match runner-derived attestation")
    if metrics != summarize(result, config.initial_cash):
        report.error("metrics", "not deterministically derived from canonical result")
    expected_exposure = {
        "open_positions": {side: asdict(item) for side, item in result.open_positions.items()},
        "pending_orders": {side: asdict(item) for side, item in result.pending_orders.items()},
        "pending_long": asdict(result.pending_orders["long"]) if "long" in result.pending_orders else None,
        "pending_short": asdict(result.pending_orders["short"]) if "short" in result.pending_orders else None,
        "open_position_unrealized_pnl": result.open_position_unrealized_pnl,
        "open_position_entry_fee": result.open_position_entry_fee,
        "open_position_funding": result.open_position_funding,
        "final_cash": result.final_cash, "final_equity": result.final_equity,
    }
    if exposure != expected_exposure:
        report.error("exposure", "not derived from canonical result")
    for name, (headers, expected_rows) in _csv_expected_rows(result).items():
        try:
            with (output_dir / name).open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                actual_rows = list(reader)
                if tuple(reader.fieldnames or ()) != headers:
                    report.error(name, "header differs from canonical result schema")
                    continue
        except (OSError, UnicodeError, csv.Error) as exc:
            report.error(name, f"cannot parse canonical CSV: {exc}")
            continue
        normalized = [
            {header: _csv_cell(item.get(header)) for header in headers}
            for item in expected_rows
        ]
        if actual_rows != normalized:
            report.error(name, "rows differ from canonical result")
    return report


def _state_path(repo_root: Path) -> Path:
    return repo_root.resolve() / STATE_RELATIVE_PATH


def _connect_state(repo_root: Path) -> sqlite3.Connection:
    path = _state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', 'ENFORCEMENT_STATE_V2');
        CREATE TABLE IF NOT EXISTS freeze_identities (
            candidate_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            parameter_sha256 TEXT NOT NULL,
            spec_sha256 TEXT NOT NULL,
            PRIMARY KEY(candidate_id, variant_id, strategy_version)
        );
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL UNIQUE,
            candidate_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            run_stage TEXT NOT NULL,
            data_manifest_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            receipt_path TEXT,
            receipt_sha256 TEXT,
            created_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS protected_uses (
            candidate_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            data_manifest_sha256 TEXT NOT NULL,
            run_stage TEXT NOT NULL,
            run_id TEXT NOT NULL UNIQUE,
            PRIMARY KEY(candidate_id, variant_id, data_manifest_sha256, run_stage),
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );
        CREATE TABLE IF NOT EXISTS test_executions (
            execution_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            evidence_sha256 TEXT NOT NULL,
            suite_sha256 TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );
    """)
    schema = connection.execute(
        "SELECT value FROM metadata WHERE key='schema_version'"
    ).fetchone()
    if schema != (STATE_SCHEMA,):
        connection.close()
        raise ValueError("canonical enforcement state has incompatible schema")
    return connection


def _open_state_readonly(repo_root: Path) -> sqlite3.Connection:
    path = _state_path(repo_root)
    if path.is_symlink() or not path.is_file():
        raise ValueError("canonical enforcement state is missing or is not a regular file")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
    schema = connection.execute(
        "SELECT value FROM metadata WHERE key='schema_version'"
    ).fetchone()
    if schema != (STATE_SCHEMA,):
        connection.close()
        raise ValueError("canonical enforcement state has incompatible schema")
    return connection


def _reserve_run(
    connection: sqlite3.Connection, *, run_id: str, execution_id: str,
    spec: Mapping[str, object], stage: str, data_hash: str,
) -> None:
    parameter_hash = _canonical_hash(spec.get("parameters", []))
    spec_hash = str(spec["__file_sha256"])
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute(
            "SELECT parameter_sha256, spec_sha256 FROM freeze_identities "
            "WHERE candidate_id=? AND variant_id=? AND strategy_version=?",
            (spec["candidate_id"], spec["variant_id"], spec["strategy_version"]),
        ).fetchone()
        if existing is not None and existing != (parameter_hash, spec_hash):
            raise ValueError("canonical state rejects reused variant identity")
        connection.execute(
            "INSERT OR IGNORE INTO freeze_identities VALUES (?, ?, ?, ?, ?)",
            (spec["candidate_id"], spec["variant_id"], spec["strategy_version"], parameter_hash, spec_hash),
        )
        connection.execute(
            "INSERT INTO runs(run_id, execution_id, candidate_id, variant_id, run_stage, "
            "data_manifest_sha256, status, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, 'RESERVED', ?)",
            (run_id, execution_id, spec["candidate_id"], spec["variant_id"], stage, data_hash, _utc_now()),
        )
        if stage == "PROTECTED_VALIDATION":
            connection.execute(
                "INSERT INTO protected_uses VALUES (?, ?, ?, ?, ?)",
                (spec["candidate_id"], spec["variant_id"], data_hash, stage, run_id),
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _mark_failed(connection: sqlite3.Connection, run_id: str) -> None:
    connection.execute("UPDATE runs SET status='FAILED' WHERE run_id=?", (run_id,))


def _complete_state(
    connection: sqlite3.Connection, *, run_id: str, evidence: Mapping[str, object],
    evidence_hash: str, receipt_path: Path, receipt_hash: str,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT INTO test_executions VALUES (?, ?, ?, ?)",
            (evidence["execution_id"], run_id, evidence_hash, evidence["test_suite_sha256"]),
        )
        updated = connection.execute(
            "UPDATE runs SET status='COMPLETE', receipt_path=?, receipt_sha256=? "
            "WHERE run_id=? AND status='RESERVED'",
            (str(receipt_path.resolve()), receipt_hash, run_id),
        ).rowcount
        if updated != 1:
            raise ValueError("canonical run reservation is missing or not unique")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def run_production_research(request: ProductionRunRequest) -> ProductionRunOutcome:
    """Execute and publish one production run without accepting a result object."""
    repo_root = request.repo_root.resolve()
    output_dir = request.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"production output must not pre-exist: {output_dir}")
    if request.run_stage not in {"COMPARISON", "PROTECTED_VALIDATION", "ADAPTATION_VALIDATION"}:
        raise ValueError("invalid production run stage")
    bars = tuple(request.bars)
    if not bars:
        raise ValueError("production run requires at least one bar")
    upstream_files = _upstream_files(request, repo_root)
    spec_path = _regular_file(request.spec_path, "spec")
    spec_source = spec_path.read_bytes()
    spec_source_sha256 = hashlib.sha256(spec_source).hexdigest()
    if spec_source_sha256 != upstream_files["spec"]["sha256"]:
        raise ValueError("strategy spec changed while its immutable snapshot was captured")
    spec = _load_json_snapshot(spec_source, "strategy spec")
    strategy_path = _regular_file(request.strategy_code_path, "strategy_code")
    strategy_source = strategy_path.read_bytes()
    strategy_source_sha256 = hashlib.sha256(strategy_source).hexdigest()
    if strategy_source_sha256 != upstream_files["strategy_code"]["sha256"]:
        raise ValueError("strategy code changed while its immutable snapshot was captured")
    execution_critical_hashes = _execution_critical_hashes(repo_root)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    data_contract = _data_contract(request.data_manifest_path)
    for field in ("symbol", "market", "timeframe"):
        if getattr(request, field) != data_contract[field]:
            raise ValueError(f"actual {field} differs from production data contract")
    config = _clone_config(request.config)
    strategy_symbol = _strategy_symbol(spec)
    config_payload_hash = canonical_config_sha256(config)
    if spec.get("execution_config_sha256") != config_payload_hash:
        raise ValueError("actual BacktestConfig differs from frozen strategy spec")
    spec["__file_sha256"] = spec_source_sha256
    registry = load_json(request.registry_path)
    protocol = load_json(request.protocol_path)
    parameters = _strategy_parameters(spec)
    strategy_parameters_sha256 = _canonical_hash(parameters)
    strategy = _load_strategy(
        strategy_source, strategy_path, strategy_symbol, parameters,
    )
    actual_start, actual_end = bars[0].open_time, bars[-1].open_time
    if any(bars[index].open_time >= bars[index + 1].open_time for index in range(len(bars) - 1)):
        raise ValueError("production bars must be strictly ordered with unique open_time")
    bar_hash = canonical_bars_sha256(bars)
    expected_bar_identity = {
        "bars_sha256": bar_hash,
        "row_count": len(bars),
        "tested_start": actual_start,
        "tested_end": actual_end,
    }
    mismatches = [
        key for key, value in expected_bar_identity.items()
        if data_contract.get(key) != value
    ]
    if mismatches:
        raise ValueError(f"actual bars differ from production data contract: {mismatches}")
    run_id, execution_id = str(uuid.uuid4()), str(uuid.uuid4())
    data_hash = sha256_file(request.data_manifest_path)
    state = _connect_state(repo_root)
    reserved = False
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.production-v2-", dir=output_dir.parent))
    staged_output = work / output_dir.name
    evidence_path = work / "test_execution.json"
    try:
        evidence = _run_test_suite(
            suite_path=request.strategy_test_suite_path.resolve(), spec=spec,
            spec_path=request.spec_path, strategy_spec_sha256=spec_source_sha256,
            strategy_code_path=request.strategy_code_path,
            strategy_code_sha256=strategy_source_sha256,
            strategy_symbol=strategy_symbol,
            evidence_path=evidence_path,
        )
        preflight_report, context = create_production_preflight_context(
            receipt_path=request.freeze_receipt_path, spec_path=request.spec_path,
            registry_path=request.registry_path, protocol_path=request.protocol_path,
            capability_path=repo_root / CANONICAL_CAPABILITY_RELATIVE_PATH,
            data_manifest_path=request.data_manifest_path,
            strategy_code_path=request.strategy_code_path, repo_root=repo_root,
            actual_config=config, tested_start=actual_start, tested_end=actual_end,
            run_stage=request.run_stage, test_manifest_path=evidence_path,
            previous_registry_path=request.previous_registry_path,
        )
        if not preflight_report.ok or context is None:
            raise ValueError(preflight_report.render())
        _reserve_run(
            state, run_id=run_id, execution_id=execution_id, spec=spec,
            stage=request.run_stage, data_hash=data_hash,
        )
        reserved = True
        result = BacktestEngine(config).run(bars, strategy)
        metadata = build_run_metadata(
            repo_root=repo_root, strategy_name=request.strategy_name,
            strategy_version=str(spec["strategy_version"]),
            source_type=request.source_type, run_purpose="PRODUCTION_RESEARCH",
            run_stage=request.run_stage, strategy_parameters=parameters,
            source_reference=request.source_reference,
            manifest_path=request.data_manifest_path, symbol=request.symbol,
            market=request.market, timeframe=request.timeframe,
            tested_start=actual_start, tested_end=actual_end, row_count=len(bars),
            replication_lineage=_lineage(
                spec, registry, protocol, request, spec_source_sha256,
            ),
            strategy_code_path=request.strategy_code_path,
            capability_manifest_path=repo_root / CANONICAL_CAPABILITY_RELATIVE_PATH,
            freeze_receipt_path=request.freeze_receipt_path,
            preflight_context=context,
        )
        metadata["run_id"] = run_id
        write_results(staged_output, result, config, metadata, preflight_context=context)
        result_path = staged_output / "result.json"
        _write_json(result_path, _result_payload(result))
        shutil.copy2(evidence_path, staged_output / "test_execution.json")
        config_path = staged_output / "config.json"
        persisted_metadata = load_json(staged_output / "run_metadata.json")
        persisted_qa = persisted_metadata.get("qa_dimensions")
        if not isinstance(persisted_qa, dict):
            raise ValueError("writer did not persist independent QA dimensions")
        if _upstream_files(request, repo_root) != upstream_files:
            raise ValueError("an upstream contract changed during production execution")
        if _execution_critical_hashes(repo_root) != execution_critical_hashes:
            raise ValueError("execution-critical code changed during production execution")
        if _git(repo_root, "rev-parse", "HEAD") != git_commit:
            raise ValueError("Git commit changed during production execution")
        attestation = ExecutionAttestation(
            schema_version=ATTESTATION_SCHEMA, execution_id=execution_id,
            run_id=run_id, run_stage=request.run_stage, created_at_utc=_utc_now(),
            bars_sha256=bar_hash, bar_count=len(bars), actual_start=actual_start,
            actual_end=actual_end, symbol=request.symbol, market=request.market,
            timeframe=request.timeframe,
            timestamp_semantics=str(data_contract["timestamp_semantics"]),
            config_sha256=sha256_file(config_path),
            config_payload_sha256=config_payload_hash,
            strategy_code_sha256=sha256_file(request.strategy_code_path),
            strategy_symbol=strategy_symbol,
            strategy_parameters_sha256=strategy_parameters_sha256,
            engine_code_sha256=sha256_file(repo_root / "research/backtester_v2/engine.py"),
            runner_code_sha256=sha256_file(Path(__file__)),
            enforcement_code_sha256=sha256_file(repo_root / "research/strategy_replications/validation/core.py"),
            git_commit=git_commit,
            data_manifest_sha256=data_hash,
            result_sha256=sha256_file(result_path),
            test_execution_sha256=sha256_file(staged_output / "test_execution.json"),
            execution_critical_sha256=execution_critical_hashes,
            qa_dimensions=dict(persisted_qa),
        )
        _write_json(staged_output / "execution_attestation.json", asdict(attestation))
        manifest = {
            "schema_version": OUTPUT_MANIFEST_SCHEMA, "status": "COMPLETE",
            "run_id": run_id,
            "checksums": {
                item.name: sha256_file(item)
                for item in sorted(staged_output.iterdir())
                if item.name != "manifest.json"
            },
        }
        _write_json(staged_output / "manifest.json", manifest)
        semantic = _validate_semantic_outputs(staged_output)
        if not semantic.ok:
            raise ValueError(semantic.render())
        qa = load_json(staged_output / "run_metadata.json").get("qa_dimensions")
        receipt = {
            "schema_version": RUN_RECEIPT_SCHEMA, "run_id": run_id,
            "execution_id": execution_id, "created_at_utc": _utc_now(),
            "candidate_id": spec["candidate_id"], "variant_id": spec["variant_id"],
            "strategy_version": spec["strategy_version"], "run_stage": request.run_stage,
            "spec_sha256": spec_source_sha256,
            "registry_sha256": sha256_file(request.registry_path),
            "protocol_sha256": sha256_file(request.protocol_path),
            "freeze_receipt_sha256": sha256_file(request.freeze_receipt_path),
            "capability_manifest_sha256": sha256_file(repo_root / CANONICAL_CAPABILITY_RELATIVE_PATH),
            "data_manifest_sha256": data_hash,
            "strategy_code_sha256": sha256_file(request.strategy_code_path),
            "strategy_symbol": strategy_symbol,
            "strategy_parameters_sha256": strategy_parameters_sha256,
            "output_manifest_sha256": sha256_file(staged_output / "manifest.json"),
            "execution_attestation_sha256": sha256_file(staged_output / "execution_attestation.json"),
            "test_execution_sha256": sha256_file(staged_output / "test_execution.json"),
            "bars_sha256": bar_hash,
            "config_payload_sha256": config_payload_hash,
            "git_commit": git_commit,
            "upstream_files": upstream_files,
            "qa_dimensions": qa,
            "authority": "ATOMIC_PRODUCTION_RUNNER_V2",
        }
        _write_json(staged_output / "run_receipt_v2.json", receipt)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_output, output_dir)
        receipt_path = output_dir / "run_receipt_v2.json"
        receipt_hash = sha256_file(receipt_path)
        _complete_state(
            state, run_id=run_id, evidence=evidence,
            evidence_hash=sha256_file(output_dir / "test_execution.json"),
            receipt_path=receipt_path, receipt_hash=receipt_hash,
        )
        final_report = validate_v2_run_receipt(output_dir=output_dir, repo_root=repo_root)
        if not final_report.ok:
            raise ValueError(final_report.render())
        return ProductionRunOutcome(
            run_id=run_id, execution_id=execution_id, output_dir=output_dir,
            receipt_path=receipt_path, receipt_sha256=receipt_hash,
        )
    except Exception:
        if reserved:
            _mark_failed(state, run_id)
        raise
    finally:
        state.close()
        shutil.rmtree(work, ignore_errors=True)


def validate_v2_run_receipt(*, output_dir: Path, repo_root: Path) -> ValidationReport:
    if output_dir.is_symlink():
        report = ValidationReport()
        report.error("output_dir", "production output directory must not be a symlink")
        return report
    output_dir = output_dir.resolve()
    repo_root = repo_root.resolve()
    report = _validate_semantic_outputs(output_dir)
    receipt_path = output_dir / "run_receipt_v2.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        report.error("run_receipt_v2", "regular V2 receipt is required")
        return report
    try:
        receipt = load_json(receipt_path)
    except (OSError, ValueError) as exc:
        report.error("run_receipt_v2", f"cannot parse receipt: {exc}")
        return report
    if receipt.get("schema_version") != RUN_RECEIPT_SCHEMA or receipt.get("authority") != "ATOMIC_PRODUCTION_RUNNER_V2":
        report.error("run_receipt_v2", "authoritative V2 receipt is required")
    manifest = output_dir / "manifest.json"
    attestation = output_dir / "execution_attestation.json"
    tests = output_dir / "test_execution.json"
    for name, path in (
        ("manifest", manifest), ("execution_attestation", attestation),
        ("test_execution", tests),
    ):
        if path.is_symlink() or not path.is_file():
            report.error(name, "regular attested artifact is required")
    if any(path.is_symlink() or not path.is_file() for path in (manifest, attestation, tests)):
        return report
    expected = {
        "output_manifest_sha256": sha256_file(manifest),
        "execution_attestation_sha256": sha256_file(attestation),
        "test_execution_sha256": sha256_file(tests),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            report.error(f"run_receipt_v2.{key}", "receipt identity mismatch")
    try:
        attested = load_json(attestation)
        test_evidence = load_json(tests)
    except (OSError, ValueError) as exc:
        report.error("attested_artifacts", f"cannot parse execution evidence: {exc}")
        return report
    if receipt.get("run_id") != attested.get("run_id") or receipt.get("execution_id") != attested.get("execution_id"):
        report.error("run_receipt_v2", "receipt and execution attestation disagree")
    if receipt.get("git_commit") != attested.get("git_commit"):
        report.error("run_receipt_v2.git_commit", "receipt and execution attestation disagree")
    upstream = receipt.get("upstream_files")
    if not isinstance(upstream, dict):
        report.error("run_receipt_v2.upstream_files", "immutable upstream identities are required")
        upstream = {}
    required_upstream = {
        "spec", "registry", "protocol", "data_manifest", "freeze_receipt",
        "strategy_code", "strategy_test_suite", "capability_manifest",
    }
    if not required_upstream.issubset(upstream):
        report.error("run_receipt_v2.upstream_files", "required upstream identities are missing")
    top_level_hashes = {
        "spec": "spec_sha256", "registry": "registry_sha256",
        "protocol": "protocol_sha256", "data_manifest": "data_manifest_sha256",
        "freeze_receipt": "freeze_receipt_sha256",
        "strategy_code": "strategy_code_sha256",
        "capability_manifest": "capability_manifest_sha256",
    }
    for name, identity in upstream.items():
        if not isinstance(name, str) or not isinstance(identity, dict):
            report.error("run_receipt_v2.upstream_files", "malformed upstream identity")
            continue
        if set(identity) != {"path", "sha256"} or not isinstance(identity.get("path"), str):
            report.error(f"run_receipt_v2.upstream_files.{name}", "path and sha256 are required")
            continue
        path = Path(identity["path"])
        try:
            actual_hash = sha256_file(_regular_file(path, f"upstream {name}"))
        except (OSError, ValueError) as exc:
            report.error(f"run_receipt_v2.upstream_files.{name}", str(exc))
            continue
        if identity.get("sha256") != actual_hash:
            report.error(f"run_receipt_v2.upstream_files.{name}", "current file identity differs from execution")
        receipt_key = top_level_hashes.get(name)
        if receipt_key is not None and receipt.get(receipt_key) != identity.get("sha256"):
            report.error(f"run_receipt_v2.{receipt_key}", "does not match upstream identity")
    frozen_spec = None
    frozen_strategy_symbol = None
    frozen_parameters_sha256 = None
    frozen_parameter_identity_sha256 = None
    spec_upstream = upstream.get("spec")
    if isinstance(spec_upstream, dict) and isinstance(spec_upstream.get("path"), str):
        try:
            frozen_spec = load_json(Path(spec_upstream["path"]))
            frozen_strategy_symbol = _strategy_symbol(frozen_spec)
            frozen_parameters_sha256 = _canonical_hash(_strategy_parameters(frozen_spec))
            frozen_parameter_identity_sha256 = _canonical_hash(
                frozen_spec.get("parameters", []),
            )
        except (OSError, ValueError) as exc:
            report.error("spec.execution_identity", str(exc))
    freeze_upstream = upstream.get("freeze_receipt")
    freeze_strategy_symbol = None
    freeze_parameter_identity_sha256 = None
    if isinstance(freeze_upstream, dict) and isinstance(freeze_upstream.get("path"), str):
        try:
            frozen_receipt = load_json(Path(freeze_upstream["path"]))
            freeze_strategy_symbol = frozen_receipt.get("strategy_symbol")
            freeze_parameter_identity_sha256 = frozen_receipt.get(
                "parameter_identity_sha256",
            )
        except (OSError, ValueError) as exc:
            report.error("freeze_receipt.execution_identity", str(exc))
    symbol_identities = {
        "run_receipt_v2.strategy_symbol": receipt.get("strategy_symbol"),
        "execution_attestation.strategy_symbol": attested.get("strategy_symbol"),
        "test_execution.strategy_symbol": test_evidence.get("strategy_symbol"),
        "freeze_receipt.strategy_symbol": freeze_strategy_symbol,
    }
    for path, actual_symbol in symbol_identities.items():
        if actual_symbol != frozen_strategy_symbol:
            report.error(path, "does not match frozen strategy entrypoint")
    parameter_identities = {
        "run_receipt_v2.strategy_parameters_sha256": receipt.get(
            "strategy_parameters_sha256",
        ),
        "execution_attestation.strategy_parameters_sha256": attested.get(
            "strategy_parameters_sha256",
        ),
    }
    for path, actual_identity in parameter_identities.items():
        if actual_identity != frozen_parameters_sha256:
            report.error(path, "does not match frozen strategy parameters")
    if freeze_parameter_identity_sha256 != frozen_parameter_identity_sha256:
        report.error(
            "freeze_receipt.parameter_identity_sha256",
            "does not match frozen strategy spec",
        )
    try:
        metadata = load_json(output_dir / "run_metadata.json")
        metadata_strategy = metadata.get("strategy")
        metadata_parameters = (
            metadata_strategy.get("parameters")
            if isinstance(metadata_strategy, dict) else None
        )
        metadata_parameters_sha256 = _canonical_hash(metadata_parameters)
    except (OSError, TypeError, ValueError) as exc:
        report.error("run_metadata.strategy.parameters", str(exc))
    else:
        if metadata_parameters_sha256 != frozen_parameters_sha256:
            report.error(
                "run_metadata.strategy.parameters",
                "does not match frozen strategy parameters",
            )
    critical = attested.get("execution_critical_sha256")
    try:
        current_critical = _execution_critical_hashes(repo_root)
    except (OSError, ValueError) as exc:
        report.error("execution_critical_sha256", str(exc))
        current_critical = {}
    if critical != current_critical:
        report.error("execution_critical_sha256", "current execution code differs from attested code")
    try:
        current_commit = _git(repo_root, "rev-parse", "HEAD")
    except subprocess.CalledProcessError as exc:
        report.error("git_commit", f"cannot resolve repository commit: {exc}")
    else:
        if receipt.get("git_commit") != current_commit:
            report.error("git_commit", "current repository commit differs from attested execution")
    strategy_identity = upstream.get("strategy_code")
    suite_identity = upstream.get("strategy_test_suite")
    spec_identity = upstream.get("spec")
    data_identity = upstream.get("data_manifest")
    if isinstance(strategy_identity, dict):
        if test_evidence.get("strategy_code_sha256") != strategy_identity.get("sha256"):
            report.error("test_execution.strategy_code_sha256", "does not match attested strategy")
        if attested.get("strategy_code_sha256") != strategy_identity.get("sha256"):
            report.error("execution_attestation.strategy_code_sha256", "does not match attested strategy")
    if isinstance(suite_identity, dict) and test_evidence.get("test_suite_sha256") != suite_identity.get("sha256"):
        report.error("test_execution.test_suite_sha256", "does not match attested test suite")
    if isinstance(spec_identity, dict) and test_evidence.get("strategy_spec_sha256") != spec_identity.get("sha256"):
        report.error("test_execution.strategy_spec_sha256", "does not match attested spec")
    if receipt.get("bars_sha256") != attested.get("bars_sha256"):
        report.error("run_receipt_v2.bars_sha256", "does not match execution attestation")
    try:
        persisted_config_hash = canonical_config_sha256(
            _config_from_payload(load_json(output_dir / "config.json"))
        )
    except (OSError, TypeError, ValueError) as exc:
        report.error("config_payload_sha256", f"cannot reconstruct persisted config: {exc}")
    else:
        if receipt.get("config_payload_sha256") != persisted_config_hash:
            report.error("run_receipt_v2.config_payload_sha256", "does not match persisted config")
        if attested.get("config_payload_sha256") != persisted_config_hash:
            report.error("execution_attestation.config_payload_sha256", "does not match persisted config")
        if isinstance(spec_identity, dict) and isinstance(spec_identity.get("path"), str):
            try:
                frozen_config_hash = load_json(Path(spec_identity["path"])).get("execution_config_sha256")
            except (OSError, ValueError) as exc:
                report.error("spec.execution_config_sha256", str(exc))
            else:
                if frozen_config_hash != persisted_config_hash:
                    report.error("spec.execution_config_sha256", "does not match persisted execution config")
    if isinstance(data_identity, dict) and isinstance(data_identity.get("path"), str):
        try:
            contract = _data_contract(Path(data_identity["path"]))
        except (OSError, ValueError) as exc:
            report.error("data_manifest.production_contract", str(exc))
        else:
            attested_contract = {
                "bars_sha256": attested.get("bars_sha256"),
                "row_count": attested.get("bar_count"),
                "tested_start": attested.get("actual_start"),
                "tested_end": attested.get("actual_end"),
                "symbol": attested.get("symbol"),
                "market": attested.get("market"),
                "timeframe": attested.get("timeframe"),
                "timestamp_semantics": attested.get("timestamp_semantics"),
            }
            if any(contract.get(key) != value for key, value in attested_contract.items()):
                report.error("data_manifest.production_contract", "does not match actual execution attestation")
    try:
        state = _open_state_readonly(repo_root)
        record = state.execute(
            "SELECT execution_id, status, receipt_path, receipt_sha256 FROM runs WHERE run_id=?",
            (receipt.get("run_id"),),
        ).fetchone()
        freeze_record = None
        if isinstance(frozen_spec, dict):
            freeze_record = state.execute(
                "SELECT parameter_sha256, spec_sha256 FROM freeze_identities "
                "WHERE candidate_id=? AND variant_id=? AND strategy_version=?",
                (
                    frozen_spec.get("candidate_id"),
                    frozen_spec.get("variant_id"),
                    frozen_spec.get("strategy_version"),
                ),
            ).fetchone()
        state.close()
    except (sqlite3.Error, ValueError) as exc:
        report.error("canonical_state", str(exc))
        return report
    expected_record = (
        receipt.get("execution_id"), "COMPLETE", str(receipt_path.resolve()),
        sha256_file(receipt_path),
    )
    if record != expected_record:
        report.error("canonical_state", "receipt is absent, replaced, or discontinuous")
    if isinstance(spec_upstream, dict):
        expected_freeze_record = (
            frozen_parameter_identity_sha256,
            spec_upstream.get("sha256"),
        )
        if freeze_record != expected_freeze_record:
            report.error(
                "canonical_state.freeze_identity",
                "frozen spec and parameter identity are absent or inconsistent",
            )
    return report


__all__ = [
    "ExecutionAttestation", "ProductionRunOutcome", "ProductionRunRequest",
    "canonical_bars_sha256", "canonical_config_sha256",
    "load_backtest_config", "run_production_research", "validate_v2_run_receipt",
]
