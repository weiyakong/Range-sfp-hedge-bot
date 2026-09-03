from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_structure_research_dataset_v3 as v3  # noqa: E402
import render_structure_research_v3_html as render_v3  # noqa: E402


def make_bar_frame(
    start: str,
    periods: int,
    freq: str,
    prices: list[tuple[float, float, float, float]],
    market_source: str = "futures",
) -> pd.DataFrame:
    pandas_freq = {"1D": "1D", "4H": "4h", "15min": "15min"}[freq]
    opens = pd.date_range(start, periods=periods, freq=pandas_freq, tz="UTC")
    delta = {"1D": v3.ONE_DAY, "4H": v3.FOUR_HOURS, "15min": v3.FIFTEEN_MINUTES}[freq]
    rows = []
    for idx, ts in enumerate(opens):
        op, hi, lo, cl = prices[idx]
        rows.append(
            {
                "open_datetime": ts,
                "close_datetime": ts + delta,
                "open": op,
                "high": hi,
                "low": lo,
                "close": cl,
                "volume": 1.0 + idx,
                "market_source": market_source,
            }
        )
    return pd.DataFrame(rows)


class StructureResearchV3Tests(unittest.TestCase):
    def test_add_source_provenance_keeps_existing_market_source(self) -> None:
        frame = pd.DataFrame(
            [
                {"open_datetime": pd.Timestamp("2026-01-01T00:00:00Z"), "close_datetime": pd.Timestamp("2026-01-01T04:00:00Z"), "market_source": "spot"},
                {"open_datetime": pd.Timestamp("2026-01-01T04:00:00Z"), "close_datetime": pd.Timestamp("2026-01-01T08:00:00Z"), "market_source": ""},
            ]
        )
        result = v3.add_source_provenance(frame, "futures", "x.parquet", "merged", "BTCUSDT", "4H")
        self.assertEqual(result["market_source"].tolist(), ["spot", "futures"])

    def test_compute_window_metrics_uses_zone_overlap_and_return_vol(self) -> None:
        bars = make_bar_frame(
            "2026-01-01",
            4,
            "4H",
            [(100, 101, 99, 100), (100, 111, 99, 110), (110, 121, 109, 120), (120, 131, 119, 130)],
        )
        prev = make_bar_frame("2025-12-31", 4, "4H", [(90, 100, 80, 95)] * 4)
        metrics = v3.compute_window_metrics(bars, prev, "up")
        self.assertAlmostEqual(metrics["path_efficiency"], 1.0, places=6)
        self.assertIn("close_in_central_zone", metrics)
        self.assertIn("realized_vol_pct_return_std", metrics)
        self.assertNotIn("false_break_count", metrics)

    def test_causal_market_features_exclude_direction_adjusted_speed(self) -> None:
        bars = make_bar_frame("2026-01-01", 10, "4H", [(100 + i, 101 + i, 99 + i, 100 + i) for i in range(10)])
        bars = v3.add_market_indicators_v3(bars, interval_hours=4.0)
        features = v3.build_causal_market_features_4h(bars)
        self.assertNotIn("speed_pct_per_day_direction_adjusted", features.columns)
        self.assertIn("range_ratio_current_to_previous", features.columns)

    def test_dynamic_excursions_skip_inside_rows_and_add_return_inside_fields(self) -> None:
        bars = make_bar_frame(
            "2026-01-01",
            7,
            "4H",
            [(100, 110, 90, 100)] * 5 + [(100, 120, 95, 115), (115, 118, 92, 104)],
        )
        bars = v3.add_market_indicators_v3(bars, interval_hours=4.0)
        candidates = v3.build_dynamic_range_candidates(bars)
        selected = candidates[candidates["candidate_available_at"] == pd.Timestamp("2026-01-01T20:00:00Z")].head(1)
        excursions = v3.build_dynamic_range_excursions(selected, bars)
        self.assertEqual(len(excursions), 1)
        self.assertNotEqual(excursions.iloc[0]["side"], "inside")
        self.assertIn("h1_any_close_inside_original_candidate", excursions.columns)

    def test_static_features_include_15m_path_metrics(self) -> None:
        canonical = pd.DataFrame(
            [
                {
                    "canonical_leg_id": "CL1",
                    "direction": "up",
                    "start_time": pd.Timestamp("2026-01-01T00:00:00Z"),
                    "end_time": pd.Timestamp("2026-01-01T16:00:00Z"),
                    "start_price": 100.0,
                    "end_price": 130.0,
                    "source_record_count": 2,
                    "source_role_count": 2,
                }
            ]
        )
        memberships = pd.DataFrame([{"canonical_leg_id": "CL1", "segment_level": "structural_impulse"}])
        leg_bars_h4 = make_bar_frame("2026-01-01", 4, "4H", [(100, 105, 99, 100), (100, 111, 99, 110), (110, 121, 109, 120), (120, 131, 119, 130)])
        leg_bars_h4.insert(0, "canonical_leg_id", "CL1")
        leg_bars_1d = make_bar_frame("2026-01-01", 1, "1D", [(100, 131, 99, 130)])
        leg_bars_1d.insert(0, "canonical_leg_id", "CL1")
        leg_bars_15m = make_bar_frame(
            "2026-01-01",
            5,
            "15min",
            [(100, 101, 99, 100), (100, 108, 99, 107), (107, 109, 103, 104), (104, 125, 104, 124), (124, 131, 123, 130)],
        )
        leg_bars_15m.insert(0, "canonical_leg_id", "CL1")
        static_features = v3.aggregate_static_features_v3(canonical, memberships, leg_bars_1d, leg_bars_h4, leg_bars_15m)
        row = static_features.iloc[0]
        self.assertIn("close_path_efficiency_15m", static_features.columns)
        self.assertTrue(0.0 <= float(row["close_path_efficiency_15m"]) <= 1.0)
        self.assertIn("extreme_anchor_close_path_efficiency_15m_approx", static_features.columns)

    def test_parent_reference_candidates_and_summary_do_not_auto_pick_ambiguous(self) -> None:
        canonical = pd.DataFrame(
            [
                {"canonical_leg_id": "CL1", "direction": "up", "start_time": pd.Timestamp("2026-01-01T00:00:00Z"), "end_time": pd.Timestamp("2026-01-01T04:00:00Z"), "start_price": 100.0, "end_price": 110.0},
                {"canonical_leg_id": "CL2", "direction": "down", "start_time": pd.Timestamp("2026-01-01T04:00:00Z"), "end_time": pd.Timestamp("2026-01-01T08:00:00Z"), "start_price": 110.0, "end_price": 100.0},
                {"canonical_leg_id": "CL3", "direction": "down", "start_time": pd.Timestamp("2026-01-01T08:00:00Z"), "end_time": pd.Timestamp("2026-01-01T12:00:00Z"), "start_price": 100.0, "end_price": 90.0},
            ]
        )
        memberships = pd.DataFrame(
            [
                {"canonical_leg_id": "CL1", "segment_id": "SEG_IMP_I1", "source_id": "I1", "segment_level": "structural_impulse", "parent_segment_id": ""},
                {"canonical_leg_id": "CL2", "segment_id": "SEG_CORR_C1", "source_id": "C1", "segment_level": "structural_correction", "parent_segment_id": "SEG_IMP_I1"},
                {"canonical_leg_id": "CL3", "segment_id": "SEG_CORR_C2", "source_id": "C2", "segment_level": "structural_correction", "parent_segment_id": "SEG_IMP_I1"},
            ]
        )
        candidates = v3.build_parent_reference_candidates_v3(canonical, memberships)
        summary = v3.build_relationship_summary_v3(canonical, candidates)
        cl2 = summary[summary["canonical_leg_id"] == "CL2"].iloc[0]
        self.assertEqual(cl2["parent_relationship_status"], "unique")
        self.assertEqual(cl2["parent_canonical_leg_id"], "CL1")

    def test_fibtime_available_at_uses_first_4h_close(self) -> None:
        impulses = pd.DataFrame([{"impulse_id": "IMP1", "fib_deadline": "2026-01-02T01:00:00Z"}])
        market_h4 = make_bar_frame("2026-01-01", 8, "4H", [(1, 2, 0, 1)] * 8)
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            pd.DataFrame(
                [
                    {"impulse_id": "IMP1", "event_type": "correction_accepted", "event_time": "2026-01-02T03:00:00Z", "reason": "ok"},
                ]
            ).to_csv(base / "fibtime_events_log20.csv", index=False)
            fib = v3.build_fibtime_events_v3(base, impulses, market_h4)
            confirmed = fib[fib["event_type"] == "fibtime_confirmed"].iloc[0]
            self.assertEqual(confirmed["available_at_time"], pd.Timestamp("2026-01-02T04:00:00Z"))

    def test_qa_catches_empty_market_source_and_bad_excursion(self) -> None:
        qa = v3.run_qa_v3(
            canonical_legs=pd.DataFrame([{"canonical_leg_id": "CL1", "start_time": pd.Timestamp("2026-01-01", tz="UTC"), "end_time": pd.Timestamp("2026-01-02", tz="UTC")}]),
            static_features=pd.DataFrame([{"canonical_leg_id": "CL1", "close_path_efficiency_15m": 0.5, "empty_market_source_count": 1}]),
            causal_4h=pd.DataFrame([{"open_datetime": pd.Timestamp("2026-01-01", tz="UTC"), "speed_pct_per_day_signed": 0.1}]),
            fibtime_events=pd.DataFrame(),
            endpoint_alignment=pd.DataFrame(),
            coverage_frame=pd.DataFrame(),
            dynamic_excursions=pd.DataFrame([{"side": "inside"}]),
            source_frames={"1D": pd.DataFrame(), "4H": pd.DataFrame(), "15M": pd.DataFrame()},
        )
        self.assertIn("empty_market_source_in_used_candles", qa["critical_failures"])
        self.assertIn("excursion_rows_without_actual_excursion", qa["critical_failures"])

    def test_render_requires_green_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            (dataset_dir / "structure_research_summary_v3.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")
            (dataset_dir / "structure_research_qa_v3.json").write_text(json.dumps({"critical_failures": ["x"]}), encoding="utf-8")
            with mock.patch.object(sys, "argv", ["render_structure_research_v3_html.py", "--dataset-dir", str(dataset_dir), "--mode", "smoke"]):
                with self.assertRaises(RuntimeError):
                    render_v3.main()

    def test_render_builds_plotly_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            bars_4h = make_bar_frame("2026-01-01", 20, "4H", [(100 + i, 102 + i, 99 + i, 101 + i) for i in range(20)])
            bars_15m = make_bar_frame("2026-01-01", 16, "15min", [(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(16)])
            legs = pd.DataFrame([{"canonical_leg_id": "CL1", "direction": "up", "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-03T00:00:00Z", "start_price": 100, "end_price": 120}])
            dynamic = pd.DataFrame([{"range_candidate_id": "RC1", "candidate_available_at": "2026-01-02T00:00:00Z", "method": "A", "window_size_bars": 18, "upper_at_history_end": 120, "upper_projected_current": 121, "lower_at_history_end": 90, "lower_projected_current": 91}])
            excursions = pd.DataFrame([{"range_candidate_id": "RC1", "observation_time": "2026-01-02T00:00:00Z", "wick_outside": True, "close_outside": False}])
            fib = pd.DataFrame([{"impulse_id": "IMP1", "deadline_version": 1, "event_type": "fibtime_confirmed", "event_time": "2026-01-02T04:00:00Z"}])
            smoke = pd.DataFrame([{"case_id": "case1", "canonical_leg_id": "CL1"}])
            causal = pd.DataFrame([{"open_datetime": "2026-01-02T00:00:00Z", "window_name": "18", "window_size_bars": 18, "speed_pct_per_day_signed": 0.1, "close_path_efficiency": 0.7}])
            static = pd.DataFrame([{"canonical_leg_id": "CL1", "close_path_efficiency_15m": 0.8}])
            decision_parent = pd.DataFrame([{"current_leg_id": "CL1", "candidate_leg_id": "CL1", "relationship_kind": "parent"}])
            coverage = pd.DataFrame([{"canonical_leg_id": "CL1", "timeframe": "4H", "coverage_status": "complete"}])
            summary = {"status": "complete_with_known_coverage_limits"}
            qa = {"critical_failures": [], "warnings": []}

            bars_4h.to_parquet(dataset_dir / "market_bars_4h.parquet", index=False)
            bars_15m.to_parquet(dataset_dir / "market_bars_15m.parquet", index=False)
            dynamic.to_parquet(dataset_dir / "dynamic_range_candidates_4h_causal.parquet", index=False)
            excursions.to_parquet(dataset_dir / "dynamic_range_excursions_4h.parquet", index=False)
            causal.to_parquet(dataset_dir / "market_features_rolling_4h_causal.parquet", index=False)
            legs.to_csv(dataset_dir / "structure_canonical_legs.csv", index=False)
            fib.to_csv(dataset_dir / "fibtime_events_v3.csv", index=False)
            smoke.to_csv(dataset_dir / "smoke_case_candidates.csv", index=False)
            coverage.to_csv(dataset_dir / "coverage_by_leg_timeframe.csv", index=False)
            static.to_csv(dataset_dir / "structure_leg_features_static.csv", index=False)
            decision_parent.to_csv(dataset_dir / "decision_parent_reference_candidates.csv", index=False)
            (dataset_dir / "structure_research_summary_v3.json").write_text(json.dumps(summary), encoding="utf-8")
            (dataset_dir / "structure_research_qa_v3.json").write_text(json.dumps(qa), encoding="utf-8")

            with mock.patch.object(sys, "argv", ["render_structure_research_v3_html.py", "--dataset-dir", str(dataset_dir), "--mode", "smoke"]):
                render_v3.main()
            html = (dataset_dir / "html" / "overview_4h.html").read_text(encoding="utf-8")
            self.assertIn("Plotly.newPlot", html)
            self.assertTrue((dataset_dir / "html" / "vendor" / "plotly-2.35.2.min.js").exists())

    def test_integration_main_smoke_writes_required_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_run = root / "base_run"
            base_run.mkdir()
            output_dir = root / "out"

            daily = make_bar_frame("2026-01-01", 5, "1D", [(100, 105, 95, 102), (102, 110, 100, 108), (108, 115, 107, 114), (114, 120, 113, 119), (119, 122, 117, 121)], market_source="")
            daily.to_parquet(root / "daily.parquet", index=False)
            (root / "merge_summary.json").write_text(json.dumps({"spot_rows_used": 0}), encoding="utf-8")

            h4_prices = [(100 + i, 102 + i, 99 + i, 101 + i) for i in range(20)]
            h4 = make_bar_frame("2026-01-01", 20, "4H", h4_prices)
            h4.to_parquet(root / "h4.parquet", index=False)

            m15_prices = [(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(40)]
            m15 = make_bar_frame("2026-01-01", 40, "15min", m15_prices)
            m15.to_parquet(root / "m15.parquet", index=False)

            pd.DataFrame(
                [
                    {"leg_id": "L1", "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-04T08:00:00Z", "start_price": 99.0, "end_price": 119.0, "direction": "up", "start_event_id": "E1", "end_event_id": "E2"},
                ]
            ).to_csv(base_run / "macro_legs_log20.csv", index=False)
            pd.DataFrame(
                [
                    {"impulse_id": "IMP1", "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-04T08:00:00Z", "available_at_time": "2026-01-04T08:00:00Z", "confirmed_at": "2026-01-04T08:00:00Z", "regime_anchor_time": "2026-01-01T00:00:00Z", "fib_deadline": "2026-01-05T00:00:00Z", "status": "accepted", "direction": "up", "start_price": 99.0, "end_price": 119.0, "start_event_id": "E1", "end_event_id": "E2", "is_open": False},
                ]
            ).to_csv(base_run / "structural_impulses_log20_fibtime.csv", index=False)
            pd.DataFrame(columns=["correction_id", "start_time", "end_time", "start_price", "end_price", "direction", "start_event_id", "end_event_id", "parent_impulse_id", "status", "is_open"]).to_csv(base_run / "corrections_log20_fibtime.csv", index=False)
            pd.DataFrame([{"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-06T00:00:00Z", "start_available_at": "2026-01-01T00:00:00Z", "end_available_at": "2026-01-06T00:00:00Z", "market": "bull"}]).to_csv(base_run / "market_state_log20_fibtime_segments.csv", index=False)
            pd.DataFrame([{"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-06T00:00:00Z", "available_at_time": "2026-01-01T00:00:00Z", "regime": "bull"}]).to_csv(base_run / "structural_regime_segments_log20_fibtime.csv", index=False)
            pd.DataFrame([{"impulse_id": "IMP1", "event_type": "correction_accepted", "event_time": "2026-01-05T00:00:00Z", "reason": "ok"}]).to_csv(base_run / "fibtime_events_log20.csv", index=False)
            pd.DataFrame([{"path": str(root / "m15.parquet"), "kind": "raw_ohlcv"}]).to_csv(root / "manifest.csv", index=False)
            pd.DataFrame([{"column_name": "open_datetime", "dtype": "datetime64[ns, UTC]"}]).to_csv(root / "schema.csv", index=False)

            argv = [
                "build_structure_research_dataset_v3.py",
                "--base-run-dir", str(base_run),
                "--daily-parquet", str(root / "daily.parquet"),
                "--daily-merge-summary", str(root / "merge_summary.json"),
                "--futures-h4-parquet", str(root / "h4.parquet"),
                "--futures-15m-parquet", str(root / "m15.parquet"),
                "--parquet-manifest", str(root / "manifest.csv"),
                "--parquet-schema", str(root / "schema.csv"),
                "--output-dir", str(output_dir),
                "--mode", "smoke",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = v3.main()
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "structure_leg_features_rolling_4h_retrospective.parquet").exists())
            self.assertTrue((output_dir / "decision_parent_reference_candidates.csv").exists())
            self.assertTrue((output_dir / "structure_research_summary_v3.json").exists())


if __name__ == "__main__":
    unittest.main()
