from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli import finish
from .core import (
    ValidationReport,
    derived_registry_counts,
    load_json,
    validate_candidate_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the candidate and variant registry")
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    try:
        registry = load_json(args.registry)
        report = validate_candidate_registry(registry)
        if report.ok:
            print(json.dumps(derived_registry_counts(registry), sort_keys=True))
        return finish(report)
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error("input", str(exc))
        return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
