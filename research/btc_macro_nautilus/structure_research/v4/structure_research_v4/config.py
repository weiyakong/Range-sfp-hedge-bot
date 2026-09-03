from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path


KNOWN_COVERAGE_END = "2026-07-05 23:59:59+00:00"


@dataclass(frozen=True)
class BuildConfig:
    base_run_dir: Path
    daily_parquet: Path
    daily_merge_summary: Path
    merged_h4_parquet: Path
    spot_h4_parquet: Path
    futures_h4_parquet: Path
    merged_15m_parquet: Path
    spot_15m_parquet: Path
    futures_15m_parquet: Path
    aggtrades_root: Path
    parquet_manifest: Path
    parquet_schema: Path
    output_dir: Path
    mode: str
    resume: bool

    def config_hash(self) -> str:
        payload = {key: str(value) for key, value in asdict(self).items()}
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
