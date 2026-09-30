from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Dict, Mapping

from .core import ValidationReport, load_json


def add_common_document(parser: argparse.ArgumentParser, flag: str) -> None:
    parser.add_argument(flag, type=Path, required=True)


def finish(report: ValidationReport) -> int:
    print(report.render())
    return 0 if report.ok else 1


def validate_document(
    path: Path,
    validator: Callable[[Mapping[str, object]], ValidationReport],
) -> int:
    try:
        payload: Dict[str, object] = load_json(path)
        return finish(validator(payload))
    except (OSError, ValueError) as exc:
        report = ValidationReport()
        report.error(str(path), str(exc))
        return finish(report)
