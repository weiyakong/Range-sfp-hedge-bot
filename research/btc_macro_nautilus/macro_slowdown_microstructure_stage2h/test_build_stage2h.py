import importlib.util
import sys
import unittest
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("build_stage2h.py")
SPEC = importlib.util.spec_from_file_location("stage2h", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def candle(index: int, open_: float, high: float, low: float, close: float,
           volume: float = 10.0, trades: int = 5) -> dict[str, object]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return {
        "start_time": start,
        "end_time": start + timedelta(minutes=1),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": volume, "quote_volume": volume * close, "trade_count": trades,
        "taker_buy_base_volume": volume / 2, "taker_buy_quote_volume": volume * close / 2,
        "complete": True,
    }


class Stage2HTests(unittest.TestCase):
    def test_microstructure_path_and_direction_identities(self) -> None:
        rows = [
            candle(0, 100, 102, 99, 101),
            candle(1, 101, 104, 100, 103),
            candle(2, 103, 104, 101, 102),
            candle(3, 102, 106, 101, 105),
        ]
        result = MODULE.microstructure_features(rows, direction=1, timeframe="1m")
        self.assertGreaterEqual(result["total_travelled_path"], result["abs_net_progress"])
        self.assertAlmostEqual(result["forward_move_share"] + result["counter_move_share"], 1.0)
        self.assertAlmostEqual(result["persistence"], 1 / 3)
        self.assertAlmostEqual(result["alternation"], 1.0)
        self.assertEqual(result["directional_sign_changes"], 2)
        self.assertEqual(result["maximum_same_direction_run"], 1)

    def test_bearish_direction_normalization(self) -> None:
        rows = [candle(0, 103, 104, 102, 103), candle(1, 103, 104, 100, 101), candle(2, 101, 102, 98, 99)]
        result = MODULE.microstructure_features(rows, direction=-1, timeframe="1m")
        self.assertEqual(result["persistence"], 1.0)
        self.assertEqual(result["counter_move_share"], 0.0)
        self.assertGreater(result["directional_net_progress"], 0)

    def test_overlap_matches_validated_body_formula(self) -> None:
        rows = [candle(0, 100, 104, 99, 103), candle(1, 102, 105, 101, 104)]
        result = MODULE.microstructure_features(rows, direction=1, timeframe="1m")
        self.assertEqual(result["overlap_body_overlap_mean"], 1.0)

    def test_half_open_window_excludes_future_bar(self) -> None:
        rows = [candle(i, 100 + i, 102 + i, 99 + i, 101 + i) for i in range(4)]
        start = rows[0]["start_time"]
        end = rows[2]["end_time"]
        selected = MODULE.select_half_open(rows, start, end)
        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[-1]["end_time"], end)

    def test_robust_slope_resists_single_outlier(self) -> None:
        values = np.asarray([0.0, 1.0, 2.0, 100.0, 4.0, 5.0])
        slope = MODULE.robust_slope(values)
        self.assertGreater(slope, 4.0)
        self.assertLess(slope, 7.0)

    def test_grouped_model_is_reproducible_and_disjoint(self) -> None:
        rows = []
        for leg in range(6):
            for j in range(4):
                rows.append({"parent_macro_leg_id": f"L{leg}", "outcome_binary": j % 2,
                             "x": float(leg + j), "z": float(j - leg)})
        first = MODULE.grouped_model(rows, ["x", "z"])
        second = MODULE.grouped_model(rows, ["x", "z"])
        np.testing.assert_array_equal(first.predictions, second.predictions)
        self.assertTrue(first.group_disjoint)

    def test_group_bootstrap_reproducible(self) -> None:
        y = np.asarray([0, 1, 0, 1, 0, 1])
        groups = np.asarray(["a", "a", "b", "b", "c", "c"])
        base = np.asarray([.1, .8, .2, .7, .3, .6])
        candidate = np.asarray([.05, .9, .1, .8, .2, .7])
        self.assertEqual(
            MODULE.grouped_bootstrap_delta(y, groups, base, candidate, 20, 7),
            MODULE.grouped_bootstrap_delta(y, groups, base, candidate, 20, 7),
        )

    def test_compatible_checkpoint_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "stage2h"
            checkpoint = output.parent / ".stage2h.build-test"
            checkpoint.mkdir()
            (checkpoint / "microstructure_15m.parquet").write_bytes(b"validated fixture")
            (checkpoint / "progress_checkpoint.json").write_text(json.dumps({
                "run_id": "run", "source_population_sha256": "source", "completed_timeframes": ["15m"]
            }))
            match = MODULE.compatible_checkpoint(output, "source")
            self.assertIsNotNone(match)
            assert match is not None
            self.assertEqual(match[0], checkpoint)

    def test_live_checkpoint_is_not_concurrently_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "stage2h"
            checkpoint = output.parent / ".stage2h.build-live"
            checkpoint.mkdir()
            (checkpoint / "microstructure_15m.parquet").write_bytes(b"validated fixture")
            (checkpoint / "progress_checkpoint.json").write_text(json.dumps({
                "run_id": "run", "source_population_sha256": "source", "completed_timeframes": ["15m"]
            }))
            (checkpoint / "active_lease.json").write_text(json.dumps({"pid": __import__("os").getpid()}))
            self.assertIsNone(MODULE.compatible_checkpoint(output, "source"))


if __name__ == "__main__":
    unittest.main()
