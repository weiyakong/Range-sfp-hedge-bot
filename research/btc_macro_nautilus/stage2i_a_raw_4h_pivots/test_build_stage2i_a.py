from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_stage2i_a.py")
SPEC = importlib.util.spec_from_file_location("stage2i_a", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def candle(
    index: int,
    high: float,
    low: float,
    *,
    complete: bool = True,
    open_: float | None = None,
    close: float | None = None,
) -> dict[str, object]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index)
    open_value = low + (high - low) * 0.4 if open_ is None else open_
    close_value = low + (high - low) * 0.6 if close is None else close
    return {
        "source_row_index": index,
        "start_time": start,
        "end_time": start + timedelta(hours=4),
        "open": open_value,
        "high": high,
        "low": low,
        "close": close_value,
        "volume": 100.0 + index,
        "quote_volume": (100.0 + index) * close_value,
        "trade_count": 1000 + index,
        "taker_buy_base_volume": 50.0,
        "taker_buy_quote_volume": 50.0 * close_value,
        "constituent_count": 240 if complete else 200,
        "expected_constituent_count": 240,
        "complete": complete,
        "incomplete_reason": None if complete else "fixture_incomplete",
        "market": "binance_usdt_m_futures",
        "instrument": "BTCUSDT",
        "resolution": "4h",
    }


class Stage2IARawPivotTests(unittest.TestCase):
    def test_strict_pivot_high(self) -> None:
        rows = [candle(i, high, 5.0) for i, high in enumerate([7, 8, 12, 9, 6])]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        self.assertEqual([(event["pivot_bar_index"], event["pivot_type"]) for event in events], [(2, "HIGH")])
        self.assertEqual(events[0]["pivot_price"], 12.0)

    def test_strict_pivot_low(self) -> None:
        rows = [candle(i, 20.0, low) for i, low in enumerate([12, 10, 5, 9, 11])]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        self.assertEqual([(event["pivot_bar_index"], event["pivot_type"]) for event in events], [(2, "LOW")])
        self.assertEqual(events[0]["pivot_price"], 5.0)

    def test_equality_does_not_pass(self) -> None:
        high_rows = [candle(i, high, 5.0) for i, high in enumerate([7, 12, 12, 9, 6])]
        low_rows = [candle(i, 20.0, low) for i, low in enumerate([12, 5, 5, 9, 11])]
        self.assertEqual(MODULE.build_raw_pivot_rows(MODULE.complete_population(high_rows), "manifest"), [])
        self.assertEqual(MODULE.build_raw_pivot_rows(MODULE.complete_population(low_rows), "manifest"), [])

    def test_first_and_last_two_bars_never_pivot(self) -> None:
        rows = [candle(i, high, low) for i, (high, low) in enumerate([(20, 1), (19, 2), (18, 3), (19, 2), (20, 1)])]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        self.assertEqual(events, [])

    def test_available_from_is_second_right_candle_close(self) -> None:
        rows = [candle(i, high, 5.0) for i, high in enumerate([7, 8, 12, 9, 6])]
        complete = MODULE.complete_population(rows)
        event = MODULE.build_raw_pivot_rows(complete, "manifest")[0]
        self.assertEqual(event["confirmation_timestamp"], complete[4].end_time)
        self.assertEqual(event["available_from"], complete[4].end_time)

    def test_incomplete_candles_do_not_participate(self) -> None:
        rows = [candle(i, high, 5.0, complete=(i != 2)) for i, high in enumerate([4, 5, 100, 7, 8, 12, 9, 6])]
        complete = MODULE.complete_population(rows)
        self.assertEqual(len(complete), 7)
        events = MODULE.build_raw_pivot_rows(complete, "manifest")
        self.assertEqual([(event["source_row_index"], event["pivot_type"]) for event in events], [(5, "HIGH")])
        self.assertNotIn(2, {event["source_row_index"] for event in events})

    def test_dual_high_low_candle_creates_two_events(self) -> None:
        rows = [
            candle(0, 8, 4), candle(1, 9, 3), candle(2, 12, 1), candle(3, 9, 3), candle(4, 8, 4)
        ]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        self.assertEqual([event["pivot_type"] for event in events], ["HIGH", "LOW"])
        self.assertTrue(all(event["causal__dual_high_low_same_candle"] for event in events))

    def test_output_is_ordered_unique_and_leakage_named(self) -> None:
        rows = [candle(i, high, low) for i, (high, low) in enumerate([
            (8, 4), (9, 3), (12, 2), (9, 4), (8, 3), (10, 1), (8, 4), (11, 3), (8, 4)
        ])]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        keys = [(event["pivot_bar_index"], event["pivot_type"]) for event in events]
        self.assertEqual(keys, sorted(keys, key=lambda item: (item[0], 0 if item[1] == "HIGH" else 1)))
        self.assertEqual(len(keys), len(set(keys)))
        columns = set().union(*(event.keys() for event in events))
        self.assertTrue(all(name.startswith("postevent__") for name in columns if "next_" in name or "horizon_" in name))

    def test_excursions_are_non_negative(self) -> None:
        rows = [candle(i, high, 5.0) for i, high in enumerate([7, 8, 12, 9, 6, 7])]
        event = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")[0]
        self.assertEqual(event["postevent__horizon_1__max_upward_excursion"], 0.0)
        self.assertGreaterEqual(event["postevent__horizon_1__max_downward_excursion"], 0.0)

    def test_parquet_write_is_deterministic(self) -> None:
        rows = [candle(i, high, 5.0) for i, high in enumerate([7, 8, 12, 9, 6])]
        events = MODULE.build_raw_pivot_rows(MODULE.complete_population(rows), "manifest")
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.parquet"
            second = Path(directory) / "second.parquet"
            MODULE.write_pivot_parquet(first, events)
            MODULE.write_pivot_parquet(second, events)
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), hashlib.sha256(second.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
