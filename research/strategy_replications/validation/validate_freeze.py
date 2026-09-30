from __future__ import annotations

import argparse
from pathlib import Path

from .cli import finish
from .core import ValidationReport, create_freeze_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and issue an immutable strategy freeze receipt")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--capability", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--strategy-code", type=Path)
    args = parser.parse_args()
    try:
        report, _ = create_freeze_receipt(
            spec_path=args.spec, registry_path=args.registry,
            protocol_path=args.protocol, capability_path=args.capability,
            data_manifest_path=args.data_manifest, repo_root=args.repo_root,
            receipt_path=args.receipt_out, strategy_code_path=args.strategy_code,
        )
        return finish(report)
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
