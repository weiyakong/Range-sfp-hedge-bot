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
from .models import BacktestConfig, BacktestResult, SourceType, Trade


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
) -> Dict[str, object]:
    if source_type not in {"external_replication", "external_adaptation", "internal"}:
        raise ValueError(f"unsupported strategy source_type: {source_type}")
    if source_type != "internal" and not source_reference:
        raise ValueError("external strategies require source_reference")
    if row_count < 0 or tested_end < tested_start:
        raise ValueError("invalid tested interval or row_count")
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
    return {
        "run_id": str(uuid.uuid4()),
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "qa_status": "PENDING_ENGINE_RESULT",
        "qa_issues": [],
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
            "dirty": bool(_git_value(repo_root, "status", "--porcelain")),
            "file_sha256": checksums,
        },
    }


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
) -> None:
    """Write a complete run to a sibling directory, then atomically promote it."""
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
        run_metadata["qa_status"] = result.qa_status
        run_metadata["qa_issues"] = list(result.qa_issues)
        _write_json(temporary / "run_metadata.json", run_metadata)
        artifact_names = sorted(path.name for path in temporary.iterdir())
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
