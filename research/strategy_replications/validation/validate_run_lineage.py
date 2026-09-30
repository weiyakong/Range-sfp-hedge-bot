from __future__ import annotations

import argparse
from pathlib import Path

from .cli import finish
from .core import ValidationReport, create_run_receipt, validate_run_lineage


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production run lineage and optionally issue a run receipt")
    for name in ("output-dir", "freeze-receipt", "spec", "registry", "protocol", "capability", "data-manifest", "strategy-code"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args()
    try:
        kwargs = {
            "output_dir": args.output_dir,
            "freeze_receipt_path": args.freeze_receipt,
            "spec_path": args.spec,
            "registry_path": args.registry,
            "protocol_path": args.protocol,
            "capability_path": args.capability,
            "data_manifest_path": args.data_manifest,
            "strategy_code_path": args.strategy_code,
        }
        if args.receipt_out:
            report, _ = create_run_receipt(receipt_path=args.receipt_out, **kwargs)
        else:
            report = validate_run_lineage(**kwargs)
        return finish(report)
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
