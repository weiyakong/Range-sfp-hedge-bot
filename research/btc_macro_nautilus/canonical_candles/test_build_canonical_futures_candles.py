import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_canonical_futures_candles.py")
SPEC = importlib.util.spec_from_file_location("canonical_candles", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def source_row(timestamp, price=100.0, volume=1.0):
    return (timestamp, price, price + 1, price - 1, price + 0.5, volume, volume * price, 2, volume / 2, volume * price / 2)


class CanonicalCandleTests(unittest.TestCase):
    def test_utc_bucket_alignment(self):
        timestamp = MODULE.parse_utc("2024-01-01T19:23:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 240)), "2024-01-01T16:00:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 720)), "2024-01-01T12:00:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 1440)), "2024-01-01T00:00:00Z")

    def test_complete_ohlcv_aggregation(self):
        start = MODULE.parse_utc("2024-01-01T00:00:00Z")
        accumulator = MODULE.CandleAccumulator("4h", 3, start, set(), [])
        accumulator.add(source_row(start, 100, 1))
        accumulator.add(source_row(start + MODULE.MINUTE_MS, 102, 2))
        accumulator.add(source_row(start + 2 * MODULE.MINUTE_MS, 99, 3))
        accumulator.flush()
        row = accumulator.rows[0]
        self.assertTrue(row["complete"])
        self.assertEqual(row["open"], 100)
        self.assertEqual(row["high"], 103)
        self.assertEqual(row["low"], 98)
        self.assertEqual(row["close"], 99.5)
        self.assertEqual(row["volume"], 6)
        self.assertEqual(row["trade_count"], 6)

    def test_known_gap_is_incomplete_without_fill(self):
        start = MODULE.bucket_start_ms(MODULE.KNOWN_GAP_MS, 240)
        accumulator = MODULE.CandleAccumulator("4h", 240, start, {MODULE.KNOWN_GAP_MS}, [])
        for index in range(240):
            timestamp = start + index * MODULE.MINUTE_MS
            if timestamp != MODULE.KNOWN_GAP_MS:
                accumulator.add(source_row(timestamp))
        accumulator.flush()
        row = accumulator.rows[0]
        self.assertFalse(row["complete"])
        self.assertEqual(row["constituent_count"], 239)
        self.assertEqual(row["incomplete_reason"], "known_gap:2019-09-08T19:00:00Z")


if __name__ == "__main__":
    unittest.main()
