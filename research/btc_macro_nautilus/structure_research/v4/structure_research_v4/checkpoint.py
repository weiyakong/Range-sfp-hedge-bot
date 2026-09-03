from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .io import save_json, save_table


def table_fingerprint(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "row_count": None,
        "checksum": hashlib.sha256(data).hexdigest(),
        "file_size": len(data),
    }


def save_partial(frame: pd.DataFrame, path: Path) -> dict:
    save_table(frame, path)
    info = table_fingerprint(path)
    info["row_count"] = len(frame)
    info["saved_at"] = pd.Timestamp.utcnow().isoformat()
    return info


def write_checkpoint_index(entries: dict, path: Path) -> None:
    save_json(entries, path)
