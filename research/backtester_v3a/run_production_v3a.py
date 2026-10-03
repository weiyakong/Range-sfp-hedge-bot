"""Command-line entrypoint for one authoritative-symbol V3-A production run."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .data import InputContractLocators
from .runner import ProductionRunRequestV3A, run_production_v3a


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute one manifest-bound Backtester V3-A run",
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--trade-contract", required=True, type=Path)
    parser.add_argument("--funding-contract", type=Path)
    parser.add_argument("--mark-contract", type=Path)
    parser.add_argument("--metadata-contract", required=True, type=Path)
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--state-path", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_production_v3a(ProductionRunRequestV3A(
        repo_root=args.repo_root,
        spec_path=args.spec,
        config_path=args.config,
        inputs=InputContractLocators(
            trade_price=args.trade_contract,
            funding=args.funding_contract,
            mark_price=args.mark_contract,
            instrument_metadata=args.metadata_contract,
        ),
        required_start_ms=args.start_ms,
        required_end_ms=args.end_ms,
        output_dir=args.output_dir,
        state_path=args.state_path,
    ))
    print(outcome.receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
