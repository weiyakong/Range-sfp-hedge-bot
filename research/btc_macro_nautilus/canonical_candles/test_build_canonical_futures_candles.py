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
        self.assertEqual(MODULE.utc_iso(MODULE.KNOWN_GAP_MS), "2019-09-08T19:00:00Z")
        timestamp = MODULE.parse_utc("2024-01-01T19:23:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 3)), "2024-01-01T19:21:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 5)), "2024-01-01T19:20:00Z")
        self.assertEqual(MODULE.utc_iso(MODULE.bucket_start_ms(timestamp, 15)), "2024-01-01T19:15:00Z")
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
        for resolution, expected in (("3m", 3), ("5m", 5), ("15m", 15)):
            start = MODULE.bucket_start_ms(MODULE.KNOWN_GAP_MS, expected)
            accumulator = MODULE.CandleAccumulator(resolution, expected, start, {MODULE.KNOWN_GAP_MS}, [])
            for index in range(expected):
                timestamp = start + index * MODULE.MINUTE_MS
                if timestamp != MODULE.KNOWN_GAP_MS:
                    accumulator.add(source_row(timestamp))
            accumulator.flush()
            row = accumulator.rows[0]
            self.assertFalse(row["complete"])
            self.assertEqual(row["constituent_count"], expected - 1)
            self.assertEqual(row["incomplete_reason"], "known_gap:2019-09-08T19:00:00Z")

    def test_incomplete_first_calendar_bar(self):
        source_start = MODULE.parse_utc("2019-09-08T17:57:00Z")
        for resolution, expected, bucket in (("3m", 3, source_start), ("5m", 5, source_start - 2 * MODULE.MINUTE_MS),
                                              ("15m", 15, source_start - 12 * MODULE.MINUTE_MS)):
            accumulator = MODULE.CandleAccumulator(resolution, expected, source_start, set(), [])
            for timestamp in range(source_start, bucket + expected * MODULE.MINUTE_MS, MODULE.MINUTE_MS):
                accumulator.add(source_row(timestamp))
            accumulator.flush()
            row = accumulator.rows[0]
            self.assertEqual(row["start_time_ms"], bucket)
            self.assertEqual(row["complete"], resolution == "3m")
            if resolution != "3m":
                self.assertEqual(row["incomplete_reason"], "dataset_start")

    def test_lower_timeframe_ohlc_and_all_additives(self):
        start = MODULE.parse_utc("2024-01-01T00:00:00Z")
        for resolution, expected in (("3m", 3), ("5m", 5), ("15m", 15)):
            accumulator = MODULE.CandleAccumulator(resolution, expected, start, set(), [])
            for index in range(expected):
                accumulator.add(source_row(start + index * MODULE.MINUTE_MS, 100 - index, index + 1))
            accumulator.flush()
            row = accumulator.rows[0]
            self.assertTrue(row["complete"])
            self.assertEqual(row["open"], 100)
            self.assertEqual(row["high"], 101)
            self.assertEqual(row["low"], 100 - expected)
            self.assertEqual(row["close"], 100 - (expected - 1) + 0.5)
            total = expected * (expected + 1) / 2
            self.assertEqual(row["volume"], total)
            self.assertEqual(row["quote_volume"], sum((index + 1) * (100 - index) for index in range(expected)))
            self.assertEqual(row["trade_count"], 2 * expected)
            self.assertEqual(row["taker_buy_base_volume"], total / 2)
            self.assertEqual(row["taker_buy_quote_volume"], row["quote_volume"] / 2)

    def test_cross_tf_15m_matches_complete_3m_and_5m_children(self):
        start = MODULE.parse_utc("2024-01-01T00:00:00Z")
        accumulators = {
            resolution: MODULE.CandleAccumulator(resolution, expected, start, set(), [])
            for resolution, expected in (("3m", 3), ("5m", 5), ("15m", 15))
        }
        for index in range(15):
            row = source_row(start + index * MODULE.MINUTE_MS, 100 + index, index + 1)
            for accumulator in accumulators.values():
                accumulator.add(row)
        for accumulator in accumulators.values():
            accumulator.flush()
        derived = {resolution: accumulator.rows for resolution, accumulator in accumulators.items()}
        result = MODULE.cross_timeframe_qa(derived, (("3m", "15m"), ("5m", "15m")))
        self.assertEqual(result["3m_to_15m"]["status"], "PASS")
        self.assertEqual(result["5m_to_15m"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
