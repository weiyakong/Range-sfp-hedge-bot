import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_atomic_features.py")
SPEC = importlib.util.spec_from_file_location("atomic_features", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def candle(index, *, open_price=100.0, high=110.0, low=90.0, close=105.0, complete=True):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index)
    return {
        "start_time": start,
        "end_time": start + timedelta(hours=4),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": 10.0,
        "quote_volume": 1000.0,
        "trade_count": 5,
        "taker_buy_base_volume": 4.0,
        "taker_buy_quote_volume": 400.0,
        "constituent_count": 240 if complete else 239,
        "expected_constituent_count": 240,
        "complete": complete,
        "market": "binance_usdt_m_futures",
        "instrument": "BTCUSDT",
        "resolution": "4h",
    }


class AtomicFeatureTests(unittest.TestCase):
    def test_geometry_and_zero_range(self):
        result = MODULE.geometry(candle(0))
        self.assertEqual(result["full_range"], 20)
        self.assertEqual(result["body_size"], 5)
        self.assertEqual(result["body_share"], 0.25)
        flat = MODULE.geometry(candle(0, open_price=100, high=100, low=100, close=100))
        self.assertIsNone(flat["body_share"])
        self.assertIsNone(flat["upper_wick_share"])

    def test_pair_overlap_and_penetration(self):
        previous = candle(0, open_price=95, high=110, low=90, close=105)
        current = candle(1, open_price=105, high=120, low=100, close=115)
        result = MODULE.pair_features(previous, current, None)
        self.assertEqual(result["range_overlap_abs"], 10)
        self.assertEqual(result["overlap_share_prev"], 0.5)
        self.assertEqual(result["overlap_share_curr"], 0.5)
        self.assertAlmostEqual(result["overlap_jaccard"], 1 / 3)
        self.assertEqual(result["upper_extension_abs"], 10)
        self.assertEqual(result["extreme_penetration_from_top_abs"], 10)

    def test_incomplete_boundary_resets_pair_and_atr(self):
        candles = [candle(0, complete=False)] + [candle(index, close=100 + index) for index in range(1, 17)]
        rows = MODULE.compute_features(candles)
        self.assertFalse(rows[0]["pair_eligible"])
        self.assertFalse(rows[1]["pair_eligible"])
        self.assertIsNone(rows[1]["true_range"])
        self.assertIsNone(rows[14]["atr14_sma"])
        self.assertIsNotNone(rows[15]["atr14_sma"])
        self.assertIsNotNone(rows[15]["atr14_wilder"])

    def test_alternation_skips_zero_steps(self):
        candles = [
            candle(0, close=100),
            candle(1, close=101),
            candle(2, close=101),
            candle(3, close=99),
        ]
        rows = MODULE.compute_features(candles)
        self.assertIsNone(rows[1]["alternation_indicator"])
        self.assertIsNone(rows[2]["alternation_indicator"])
        self.assertTrue(rows[3]["alternation_indicator"])


if __name__ == "__main__":
    unittest.main()
