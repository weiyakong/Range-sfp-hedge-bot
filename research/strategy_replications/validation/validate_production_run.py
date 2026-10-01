from __future__ import annotations

import argparse
from pathlib import Path

from .cli import finish
from .core import ValidationReport, load_json, validate_production_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight an external-strategy production historical run")
    for name in ("spec", "registry", "protocol", "capability", "data-manifest", "strategy-code", "receipt", "repo-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tested-start", type=int, required=True)
    parser.add_argument("--tested-end", type=int, required=True)
    parser.add_argument("--run-stage", choices=("COMPARISON", "PROTECTED_VALIDATION", "ADAPTATION_VALIDATION"), required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--previous-registry", type=Path)
    args = parser.parse_args()
    try:
        return finish(validate_production_preflight(
            receipt_path=args.receipt, spec_path=args.spec,
            registry_path=args.registry, protocol_path=args.protocol,
            capability_path=args.capability, data_manifest_path=args.data_manifest,
            strategy_code_path=args.strategy_code, repo_root=args.repo_root,
            actual_config=load_json(args.config), tested_start=args.tested_start,
            tested_end=args.tested_end, run_stage=args.run_stage,
            test_manifest_path=args.test_manifest,
            previous_registry_path=args.previous_registry,
        ))
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
