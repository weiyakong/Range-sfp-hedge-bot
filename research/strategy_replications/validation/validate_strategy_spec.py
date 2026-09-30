from __future__ import annotations

import argparse
from pathlib import Path

from .cli import finish
from .core import ValidationReport, load_json, validate_strategy_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a structured strategy spec")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--capability", type=Path)
    args = parser.parse_args()
    try:
        capability = load_json(args.capability) if args.capability else None
        return finish(validate_strategy_spec(load_json(args.spec), capability))
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
