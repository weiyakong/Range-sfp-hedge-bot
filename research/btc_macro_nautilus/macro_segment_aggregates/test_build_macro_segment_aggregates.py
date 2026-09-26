import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_macro_segment_aggregates.py")
SPEC = importlib.util.spec_from_file_location("macro_segment_aggregates", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SegmentAggregateTests(unittest.TestCase):
    def test_conservative_unresolved_bounds(self):
        anchor = {"exact_pivot_time": "", "matching_5m_start_times": "2024-01-01T00:00:00+00:00|2024-01-01T00:10:00+00:00"}
        start, mode = MODULE.boundary_bounds(anchor, "start")
        self.assertEqual(start.isoformat(), "2024-01-01T00:15:00+00:00")
        self.assertEqual(mode, "guaranteed_after_all_candidate_windows")
        end, mode = MODULE.boundary_bounds(anchor, "end")
        self.assertEqual(end.isoformat(), "2024-01-01T00:00:00+00:00")
        self.assertEqual(mode, "guaranteed_before_all_candidate_windows")

    def test_numeric_summary_and_direction_summary(self):
        values = MODULE.numeric_summary([1.0, 2.0, 3.0], "x")
        self.assertEqual(values["x__count"], 3)
        self.assertEqual(values["x__median"], 2.0)
        self.assertEqual(values["x__p25"], 1.5)
        directions = MODULE.direction_summary(["up", "down", "flat", "up"], "local_direction")
        self.assertEqual(directions["local_direction__positive_count"], 2)
        self.assertEqual(directions["local_direction__zero_share"], 0.25)

    def test_path_metrics(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        rows = []
        for index, (open_price, close_price) in enumerate(((100, 110), (110, 105), (105, 120))):
            timestamp = start + timedelta(hours=4 * index)
            rows.append({"timestamp": timestamp, "end_time": timestamp + timedelta(hours=4), "open": open_price, "close": close_price, "source_complete": True, "pair_eligible": index > 0})
        result = MODULE.path_metrics(rows)
        self.assertTrue(result["interior_path_contiguous"])
        self.assertEqual(result["interior_net_signed_move"], 20)
        self.assertEqual(result["interior_close_path"], 30)
        self.assertAlmostEqual(result["interior_path_efficiency"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
