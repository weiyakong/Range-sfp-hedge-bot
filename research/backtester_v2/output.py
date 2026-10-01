import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

from .metrics import summarize
from .models import (
    BacktestConfig,
    BacktestResult,
    PRODUCTION_OUTPUT_ARTIFACTS,
    ReplicationLineage,
    RunPurpose,
    RunStage,
    SourceType,
    Trade,
)
from research.strategy_replications.validation.core import (
    PRODUCTION_STAGES,
    RUN_STAGES,
    VerifiedPreflightContext,
    _actual_controlled_config,
    _material_dirty_paths,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, check=True,
        capture_output=True, text=True,
    )
    return completed.stdout.strip()


def build_run_metadata(
    repo_root: Path,
    strategy_name: str,
    strategy_version: str,
    source_type: SourceType,
    run_purpose: RunPurpose,
    run_stage: RunStage,
    strategy_parameters: Dict[str, object],
    source_reference: Optional[str],
    manifest_path: Optional[Path],
    symbol: str,
    market: str,
    timeframe: str,
    tested_start: int,
    tested_end: int,
    row_count: int,
    code_paths: Optional[Iterable[Path]] = None,
    replication_lineage: Optional[ReplicationLineage] = None,
    strategy_code_path: Optional[Path] = None,
    capability_manifest_path: Optional[Path] = None,
    freeze_receipt_path: Optional[Path] = None,
    preflight_context: Optional[VerifiedPreflightContext] = None,
) -> Dict[str, object]:
    if source_type not in {"external_replication", "external_adaptation", "internal"}:
        raise ValueError(f"unsupported strategy source_type: {source_type}")
    if source_type != "internal" and not source_reference:
        raise ValueError("external strategies require source_reference")
    if run_purpose not in {"PRODUCTION_RESEARCH", "TEST", "SMOKE", "SYNTHETIC"}:
        raise ValueError("explicit valid run_purpose is required")
    if run_stage not in RUN_STAGES:
        raise ValueError("explicit valid run_stage is required")
    if run_purpose == "PRODUCTION_RESEARCH":
        if run_stage not in PRODUCTION_STAGES:
            raise ValueError("production research requires a production run stage")
        if preflight_context is None or not preflight_context.is_authentic():
            raise ValueError("production output requires a verified preflight context")
        if preflight_context.run_stage != run_stage:
            raise ValueError("run stage differs from verified preflight")
    elif run_stage in PRODUCTION_STAGES:
        raise ValueError("production stage cannot be used for non-production purpose")
    if row_count < 0 or tested_end < tested_start:
        raise ValueError("invalid tested interval or row_count")
    if run_purpose == "PRODUCTION_RESEARCH":
        missing = [
            name for name, value in (
                ("replication_lineage", replication_lineage),
                ("strategy_code_path", strategy_code_path),
                ("capability_manifest_path", capability_manifest_path),
                ("freeze_receipt_path", freeze_receipt_path),
                ("manifest_path", manifest_path),
                ("preflight_context", preflight_context),
            ) if value is None
        ]
        if missing:
            raise ValueError(f"production external run missing lineage: {', '.join(missing)}")
    default_paths = (
        Path(__file__).with_name(name)
        for name in ("engine.py", "models.py", "metrics.py", "output.py")
    )
    selected_paths = list(code_paths) if code_paths is not None else list(default_paths)
    checksums = {
        str(path.resolve().relative_to(repo_root.resolve())): _sha256(path)
        for path in selected_paths
    }
    manifest_resolved = manifest_path.resolve() if manifest_path is not None else None
    metadata: Dict[str, object] = {
        "run_id": str(uuid.uuid4()),
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_purpose": run_purpose,
        "run_stage": run_stage,
        "qa_status": "PENDING_ENGINE_RESULT" if run_purpose == "PRODUCTION_RESEARCH" else "NON_PRODUCTION",
        "qa_issues": [],
        "qa_dimensions": (
            dict(preflight_context.qa_dimensions)
            if preflight_context is not None else {
                "engine_integrity": "PENDING",
                "data_fidelity": "VERIFIED_DECLARED" if manifest_path else "NOT_VERIFIED",
                "methodology_preflight": "NOT_APPLICABLE",
                "execution_fidelity": "NOT_VERIFIED",
                "causality_assurance": "HUMAN_REVIEW_REQUIRED",
            }
        ),
        "strategy": {
            "name": strategy_name,
            "version": strategy_version,
            "source_type": source_type,
            "parameters": strategy_parameters,
            "source_reference": source_reference,
        },
        "data": {
            "manifest_path": str(manifest_resolved) if manifest_resolved else None,
            "manifest_sha256": (
                _sha256(manifest_resolved) if manifest_resolved is not None else None
            ),
            "symbol": symbol,
            "market": market,
            "timeframe": timeframe,
            "tested_start": tested_start,
            "tested_end": tested_end,
            "row_count": row_count,
        },
        "code": {
            "git_commit": _git_value(repo_root, "rev-parse", "HEAD"),
            "dirty": bool(_material_dirty_paths(repo_root, strategy_code_path)),
            "file_sha256": checksums,
        },
    }
    if replication_lineage is not None:
        if strategy_code_path is None or capability_manifest_path is None or freeze_receipt_path is None:
            raise ValueError("replication lineage requires strategy code, capability manifest, and freeze receipt paths")
        strategy_resolved = strategy_code_path.resolve()
        capability_resolved = capability_manifest_path.resolve()
        receipt_resolved = freeze_receipt_path.resolve()
        for path in (strategy_resolved, capability_resolved, receipt_resolved):
            if not path.is_file():
                raise ValueError(f"lineage file does not exist: {path}")
        metadata["replication_lineage"] = {
            **asdict(replication_lineage),
            "strategy_code_sha256": _sha256(strategy_resolved),
            "capability_manifest_sha256": _sha256(capability_resolved),
            "freeze_receipt_sha256": _sha256(receipt_resolved),
            "data_manifest_sha256": (
                _sha256(manifest_resolved) if manifest_resolved is not None else None
            ),
            "backtester_commit": metadata["code"]["git_commit"],
            "config_sha256": None,
        }
    if preflight_context is not None:
        metadata["production_gate"] = {
            "status": "PASS",
            "git_commit": preflight_context.git_commit,
            "expected_start": preflight_context.expected_start,
            "expected_end": preflight_context.expected_end,
            "expected_config_sha256": hashlib.sha256(json.dumps(
                preflight_context.expected_config, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest(),
            "identities": dict(preflight_context.identities),
        }
    return metadata


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict]) -> None:
    names = list(fieldnames)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def write_results(
    output_dir: Path, result: BacktestResult, config: BacktestConfig,
    metadata: Dict[str, object],
    preflight_context: Optional[VerifiedPreflightContext] = None,
) -> None:
    """Write a complete run to a sibling directory, then atomically promote it."""
    purpose = metadata.get("run_purpose")
    if purpose == "PRODUCTION_RESEARCH":
        if preflight_context is None or not preflight_context.is_authentic():
            raise ValueError("production publication requires verified preflight context")
        if metadata.get("run_stage") != preflight_context.run_stage:
            raise ValueError("production run stage differs from preflight")
        data = metadata.get("data")
        if not isinstance(data, dict) or data.get("tested_start") != preflight_context.expected_start or data.get("tested_end") != preflight_context.expected_end:
            raise ValueError("production tested window differs from preflight")
        expected = dict(preflight_context.expected_config)
        actual = _actual_controlled_config(config)
        mismatches = {key: (value, actual.get(key)) for key, value in expected.items() if actual.get(key) != value}
        if mismatches:
            raise ValueError(f"production config differs from preflight: {mismatches}")
        code = metadata.get("code")
        if not isinstance(code, dict) or code.get("git_commit") != preflight_context.git_commit or code.get("dirty") is not False:
            raise ValueError("production executed-code Git identity differs from preflight")
        context_repo = Path(preflight_context.repo_root)
        context_strategy = Path(preflight_context.strategy_code_path)
        if _material_dirty_paths(context_repo, context_strategy):
            raise ValueError("production code became materially dirty after preflight")
        for identity, expected_hash in preflight_context.identities.items():
            if identity.startswith("code:"):
                actual_path = context_repo / identity.split(":", 1)[1]
            elif identity == "strategy_code_sha256":
                actual_path = context_strategy
            elif identity == "data_manifest_sha256":
                actual_path = Path(preflight_context.data_manifest_path)
            else:
                continue
            if not actual_path.is_file() or _sha256(actual_path) != expected_hash:
                raise ValueError(f"production identity changed after preflight: {identity}")
        gate = metadata.get("production_gate")
        if not isinstance(gate, dict) or gate.get("status") != "PASS" or gate.get("identities") != dict(preflight_context.identities):
            raise ValueError("production gate identity is absent or invalid")
    elif purpose not in {"TEST", "SMOKE", "SYNTHETIC"}:
        raise ValueError("explicit run_purpose is required before output")
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty run: {output_dir}")
    temporary = Path(tempfile.mkdtemp(
        prefix=f".{output_dir.name}.incomplete-", dir=output_dir.parent,
    ))
    try:
        _write_csv(
            temporary / "trades.csv", [field.name for field in fields(Trade)],
            (asdict(trade) for trade in result.trades),
        )
        _write_csv(
            temporary / "equity.csv", ("open_time", "equity"),
            ({"open_time": timestamp, "equity": equity}
             for timestamp, equity in result.equity_curve),
        )
        _write_csv(
            temporary / "intrabar_equity.csv", ("open_time", "worst_equity"),
            ({"open_time": timestamp, "worst_equity": equity}
             for timestamp, equity in result.intrabar_equity_curve),
        )
        _write_csv(
            temporary / "bar_exposure.csv", ("open_time", "any_position_active"),
            ({"open_time": timestamp, "any_position_active": exposed}
             for timestamp, exposed in result.bar_exposure_curve),
        )
        _write_csv(
            temporary / "intrabar_ambiguities.csv",
            ("bar_time", "open_legs_before", "competing_paths", "chosen_path",
             "resulting_trade_indices", "resulting_legs", "competing_events",
             "reason"),
            (asdict(item) for item in result.intrabar_ambiguities),
        )
        _write_csv(
            temporary / "rejected_orders.csv",
            ("bar_time", "side", "reason", "order_type", "qty",
             "limit_price", "attempted_fill_price", "event_type"),
            (asdict(item) for item in result.rejected_orders),
        )
        _write_json(temporary / "metrics.json", summarize(result, config.initial_cash))
        config_payload = asdict(config)
        config_payload["funding_rate_by_time"] = {
            str(key): value for key, value in config.funding_rate_by_time.items()
        }
        config_payload["funding_price_by_time"] = {
            str(key): value for key, value in config.funding_price_by_time.items()
        }
        _write_json(temporary / "config.json", config_payload)
        exposure = {
            "open_positions": {
                side: asdict(position)
                for side, position in result.open_positions.items()
            },
            "pending_orders": {
                side: asdict(order) for side, order in result.pending_orders.items()
            },
            "pending_long": (
                asdict(result.pending_orders["long"])
                if "long" in result.pending_orders else None
            ),
            "pending_short": (
                asdict(result.pending_orders["short"])
                if "short" in result.pending_orders else None
            ),
            "open_position_unrealized_pnl": result.open_position_unrealized_pnl,
            "open_position_entry_fee": result.open_position_entry_fee,
            "open_position_funding": result.open_position_funding,
            "final_cash": result.final_cash,
            "final_equity": result.final_equity,
        }
        _write_json(temporary / "exposure.json", exposure)
        run_metadata = dict(metadata)
        if "replication_lineage" in run_metadata:
            lineage = dict(run_metadata["replication_lineage"])
            lineage["config_sha256"] = _sha256(temporary / "config.json")
            run_metadata["replication_lineage"] = lineage
        dimensions = dict(run_metadata.get("qa_dimensions", {}))
        dimensions["engine_integrity"] = "PASS" if result.qa_status == "VERIFIED" else "FAIL"
        run_metadata["qa_dimensions"] = dimensions
        run_metadata["qa_status"] = (
            "PRODUCTION_VALIDATED_WITH_REVIEW_REQUIRED"
            if purpose == "PRODUCTION_RESEARCH" and dimensions["engine_integrity"] == "PASS"
            else "PRODUCTION_FAILED" if purpose == "PRODUCTION_RESEARCH"
            else "NON_PRODUCTION"
        )
        run_metadata["qa_issues"] = list(result.qa_issues)
        _write_json(temporary / "run_metadata.json", run_metadata)
        artifact_names = sorted(path.name for path in temporary.iterdir())
        if set(artifact_names) != set(PRODUCTION_OUTPUT_ARTIFACTS):
            raise RuntimeError("writer artifact set diverged from production output contract")
        manifest = {
            "status": "COMPLETE", "run_id": run_metadata["run_id"],
            "checksums": {
                name: _sha256(temporary / name) for name in artifact_names
            },
        }
        _write_json(temporary / "manifest.json", manifest)
        for name in artifact_names:
            if _sha256(temporary / name) != manifest["checksums"][name]:
                raise RuntimeError(f"artifact checksum verification failed: {name}")
        for path in temporary.glob("*.json"):
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON constant: {value}")
                ))
        if output_dir.exists():
            output_dir.rmdir()
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
