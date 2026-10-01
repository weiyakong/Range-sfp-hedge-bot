"""CLI for the sole authoritative Strategy Replication production path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from research.backtester_v2.models import Bar
from research.strategy_replications.production_runner import (
    ProductionRunRequest,
    load_backtest_config,
    run_production_research,
)


def _load_bars(path: Path) -> List[Bar]:
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            rows = [json.loads(line) for line in handle if line.strip()]
        else:
            rows = json.load(handle)
    if not isinstance(rows, list) or not rows:
        raise ValueError("bars file must contain a non-empty JSON array/JSONL stream")
    bars: List[Bar] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"bars[{index}] must be an object")
        bars.append(Bar(**row))
    return bars


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute, attest, validate and register one production research run",
    )
    for name in (
        "repo-root", "spec", "registry", "protocol", "data-manifest",
        "freeze-receipt", "strategy-code", "strategy-test-suite", "config",
        "bars", "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--previous-registry", type=Path)
    parser.add_argument("--strategy-symbol", required=True)
    parser.add_argument("--strategy-name", required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument(
        "--source-type", default="external_replication",
        choices=("external_replication", "external_adaptation", "internal"),
    )
    parser.add_argument(
        "--run-stage", required=True,
        choices=("COMPARISON", "PROTECTED_VALIDATION", "ADAPTATION_VALIDATION"),
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--timeframe", required=True)
    args = parser.parse_args()
    try:
        outcome = run_production_research(ProductionRunRequest(
            repo_root=args.repo_root, spec_path=args.spec,
            registry_path=args.registry, protocol_path=args.protocol,
            data_manifest_path=args.data_manifest,
            freeze_receipt_path=args.freeze_receipt,
            strategy_code_path=args.strategy_code,
            strategy_symbol=args.strategy_symbol,
            strategy_test_suite_path=args.strategy_test_suite,
            bars=tuple(_load_bars(args.bars)), config=load_backtest_config(args.config),
            run_stage=args.run_stage, output_dir=args.output_dir,
            symbol=args.symbol, market=args.market, timeframe=args.timeframe,
            strategy_name=args.strategy_name,
            source_reference=args.source_reference, source_type=args.source_type,
            previous_registry_path=args.previous_registry,
        ))
    except (OSError, ValueError, TypeError) as exc:
        print(f"FAIL\nERROR {exc}")
        return 1
    print(json.dumps({
        "status": "PASS", "run_id": outcome.run_id,
        "execution_id": outcome.execution_id,
        "output_dir": str(outcome.output_dir),
        "receipt_path": str(outcome.receipt_path),
        "receipt_sha256": outcome.receipt_sha256,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
