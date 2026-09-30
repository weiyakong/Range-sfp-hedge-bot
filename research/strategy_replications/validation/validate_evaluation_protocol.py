from __future__ import annotations

import argparse
from pathlib import Path

from .cli import finish
from .core import ValidationReport, load_json, validate_evaluation_protocol


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a structured evaluation protocol")
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    try:
        return finish(validate_evaluation_protocol(load_json(args.protocol)))
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
