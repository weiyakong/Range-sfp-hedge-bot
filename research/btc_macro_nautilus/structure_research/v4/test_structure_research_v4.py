from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from structure_research_v4.canonical import canonicalize_legs
from structure_research_v4.causal_features import add_atr_and_volatility, build_rolling_features
from structure_research_v4.dynamic_ranges import build_dynamic_range_candidates
from structure_research_v4.excursions import build_excursions
from structure_research_v4.fibtime import audit_duplicates
from structure_research_v4.relationships import build_parent_reference_tables
from structure_research_v4.source_discovery import validate_source_bars


ROOT = Path(__file__).resolve().parent


class StructureResearchV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sr_v4_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _sample_bars(self, freq: str = "4h", periods: int = 120) -> pd.DataFrame:
        start = pd.Timestamp("2026-01-01 00:00:00+00:00")
        delta = pd.Timedelta(freq)
        rows = []
        price = 100.0
        for i in range(periods):
            open_time = start + i * delta
            close_time = open_time + delta
            price += 1 if i % 2 == 0 else -0.3
            rows.append(
                {
                    "interval": freq,
                    "open_datetime": open_time,
                    "close_datetime": close_time,
                    "open": price - 0.5,
                    "high": price + 1.0,
                    "low": price - 1.0,
                    "close": price,
                    "volume": 10 + i,
                }
            )
        return pd.DataFrame(rows)

    def test_source_validation_detects_duplicate(self) -> None:
        frame = self._sample_bars(periods=4)
        frame.loc[1, "open_datetime"] = frame.loc[0, "open_datetime"]
        _, issues = validate_source_bars(frame)
        self.assertIn("duplicate_open_datetime", issues)

    def test_atr_is_nan_before_window(self) -> None:
        frame = add_atr_and_volatility(self._sample_bars(periods=20))
        self.assertTrue(frame.loc[5, "atr14_sma"] != frame.loc[5, "atr14_sma"])
        self.assertTrue(pd.notna(frame.loc[19, "atr14_sma"]))

    def test_rolling_features_exclude_current_bar(self) -> None:
        frame = self._sample_bars(periods=25)
        rolling = build_rolling_features(frame)
        row = rolling[(rolling["window_size_bars"] == 18)].iloc[20]
        self.assertEqual(row["available_at_time"], frame.iloc[20]["open_datetime"])
        self.assertEqual(row["bars_available"], 18)

    def test_canonicalization_deduplicates_exact_signature(self) -> None:
        base = pd.DataFrame(
            [
                {"leg_id": "L1", "direction": "up", "start_time": "2026-01-01", "end_time": "2026-01-02", "start_price": 1.0, "end_price": 2.0},
                {"leg_id": "L2", "direction": "up", "start_time": "2026-01-01", "end_time": "2026-01-02", "start_price": 1.0, "end_price": 2.0},
            ]
        )
        canonical, memberships = canonicalize_legs({"a": base})
        self.assertEqual(len(canonical), 1)
        self.assertEqual(len(memberships), 2)

    def test_dynamic_range_candidates_have_methods(self) -> None:
        frame = self._sample_bars(periods=100)
        rolling = build_rolling_features(frame)
        candidates = build_dynamic_range_candidates(frame, rolling)
        self.assertTrue(set(["A", "B", "C"]).issubset(set(candidates["method"].unique())))

    def test_excursions_only_create_outside_rows(self) -> None:
        frame = self._sample_bars(periods=100)
        rolling = build_rolling_features(frame)
        candidates = build_dynamic_range_candidates(frame, rolling)
        excursions = build_excursions(frame, candidates)
        if not excursions.empty:
            self.assertTrue((excursions["wick_outside"] | excursions["close_outside"]).all())

    def test_reference_is_opposite_direction(self) -> None:
        legs = pd.DataFrame(
            [
                {"canonical_leg_id": "CL1", "direction": "up", "start_time": pd.Timestamp("2026-01-01", tz="UTC"), "end_time": pd.Timestamp("2026-01-03", tz="UTC"), "start_price": 100.0, "end_price": 110.0, "primary_segment_level": "base"},
                {"canonical_leg_id": "CL2", "direction": "down", "start_time": pd.Timestamp("2026-01-03", tz="UTC"), "end_time": pd.Timestamp("2026-01-04", tz="UTC"), "start_price": 110.0, "end_price": 105.0, "primary_segment_level": "base"},
            ]
        )
        candidates, relationships = build_parent_reference_tables(legs)
        refs = candidates[candidates["relationship_kind"] == "reference"]
        self.assertTrue((refs["current_direction"] != refs["candidate_direction"]).all())

    def test_fibtime_duplicate_audit(self) -> None:
        frame = pd.DataFrame(
            [
                {"impulse_id": "I1", "event_type": "x", "event_time": "2026-01-01"},
                {"impulse_id": "I1", "event_type": "x", "event_time": "2026-01-01"},
            ]
        )
        audit = audit_duplicates(frame)
        self.assertEqual(int(audit.iloc[0]["duplicate_count"]), 2)

    def test_main_smoke_integration(self) -> None:
        upstream = self.temp_dir / "upstream"
        upstream.mkdir()
        base_legs = pd.DataFrame(
            [
                {"leg_id": "L1", "direction": "up", "start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-05T00:00:00+00:00", "start_price": 100.0, "end_price": 110.0},
                {"leg_id": "L2", "direction": "down", "start_time": "2026-01-05T00:00:00+00:00", "end_time": "2026-01-09T00:00:00+00:00", "start_price": 110.0, "end_price": 103.0},
            ]
        )
        for name in ["macro_legs_log20.csv", "movement_segments_log20_fibtime.csv"]:
            base_legs.to_csv(upstream / name, index=False)
        pd.DataFrame([{"impulse_id": "I1", "direction": "up", "start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-05T00:00:00+00:00", "start_price": 100.0, "end_price": 110.0}]).to_csv(upstream / "structural_impulses_log20_fibtime.csv", index=False)
        pd.DataFrame([{"correction_id": "C1", "direction": "down", "start_time": "2026-01-05T00:00:00+00:00", "end_time": "2026-01-09T00:00:00+00:00", "start_price": 110.0, "end_price": 103.0}]).to_csv(upstream / "corrections_log20_fibtime.csv", index=False)
        pd.DataFrame([{"fib_event_id": "F1", "impulse_id": "I1", "event_type": "fibtime_confirmed", "event_time": "2026-01-06T00:00:00+00:00", "reason": "ok"}]).to_csv(upstream / "fibtime_events_log20.csv", index=False)
        daily = self._sample_bars("1d", 40)
        h4 = self._sample_bars("4h", 150)
        m15 = self._sample_bars("15min", 500)
        daily_path = self.temp_dir / "daily.parquet"
        h4_path = self.temp_dir / "h4.parquet"
        m15_path = self.temp_dir / "m15.parquet"
        daily.to_parquet(daily_path, index=False)
        h4.to_parquet(h4_path, index=False)
        m15.to_parquet(m15_path, index=False)
        manifest = self.temp_dir / "parquet_manifest.csv"
        schema = self.temp_dir / "parquet_schema.csv"
        pd.DataFrame([{"file": str(daily_path)}, {"file": str(h4_path)}, {"file": str(m15_path)}]).to_csv(manifest, index=False)
        schema_rows = []
        for path, frame in [(daily_path, daily), (h4_path, h4), (m15_path, m15)]:
            for column, dtype in frame.dtypes.items():
                schema_rows.append({"file": str(path), "column": column, "dtype": str(dtype), "non_null": int(frame[column].notna().sum()), "null": int(frame[column].isna().sum())})
        pd.DataFrame(schema_rows).to_csv(schema, index=False)
        output_dir = self.temp_dir / "output"
        cmd = [
            "python3",
            str(ROOT / "build_structure_research_dataset_v4.py"),
            "--base-run-dir",
            str(upstream),
            "--daily-parquet",
            str(daily_path),
            "--daily-merge-summary",
            str(manifest),
            "--merged-h4-parquet",
            str(h4_path),
            "--spot-h4-parquet",
            str(h4_path),
            "--futures-h4-parquet",
            str(h4_path),
            "--merged-15m-parquet",
            str(m15_path),
            "--spot-15m-parquet",
            str(m15_path),
            "--futures-15m-parquet",
            str(m15_path),
            "--aggtrades-root",
            str(self.temp_dir),
            "--parquet-manifest",
            str(manifest),
            "--parquet-schema",
            str(schema),
            "--output-dir",
            str(output_dir),
            "--mode",
            "smoke",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        qa = json.loads((output_dir / "structure_research_qa_v4.json").read_text(encoding="utf-8"))
        self.assertEqual(qa["final_status"], "complete_with_known_coverage_limits")


if __name__ == "__main__":
    unittest.main()
