import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.backtester_v2.data import iter_canonical_1m_bars
from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.metrics import summarize
from research.backtester_v2.models import Bar, BacktestConfig
from research.backtester_v2.output import build_run_metadata, write_results

MANIFEST = Path(
    "/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/"
    "manifests/strict_futures_1m_manifest.json"
)


class NoopStrategy:
    def on_bar(self, bar, state):
        return []


def utc_ms(year, month, day, hour, minute):
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


class LoaderTests(unittest.TestCase):
    def test_one_sided_start_filter(self):
        start = utc_ms(2019, 9, 8, 17, 59)
        first = next(iter_canonical_1m_bars(MANIFEST, start_ms=start))
        self.assertGreaterEqual(first.open_time, start)
    def test_one_sided_end_filter(self):
        end = utc_ms(2019, 9, 8, 18, 0)
        first = next(iter_canonical_1m_bars(MANIFEST, end_ms=end))
        self.assertLessEqual(first.open_time, end)

    def test_reversed_window_rejected(self):
        start = utc_ms(2020, 1, 2, 0, 0)
        end = utc_ms(2020, 1, 1, 0, 0)
        with self.assertRaises(ValueError):
            next(iter_canonical_1m_bars(MANIFEST, start_ms=start, end_ms=end))

    def test_known_exchange_gap_is_not_synthesized(self):
        start = utc_ms(2019, 9, 8, 18, 59)
        end = utc_ms(2019, 9, 8, 19, 1)
        rows = list(iter_canonical_1m_bars(MANIFEST, start_ms=start, end_ms=end))
        self.assertEqual(
            [row.open_time for row in rows],
            [utc_ms(2019, 9, 8, 18, 59), utc_ms(2019, 9, 8, 19, 1)],
        )


class OutputTests(unittest.TestCase):
    @staticmethod
    def metadata():
        return build_run_metadata(
            repo_root=Path(__file__).resolve().parents[3],
            strategy_name="output_fixture",
            strategy_version="1",
            source_type="internal",
            strategy_parameters={},
            source_reference=None,
            manifest_path=None,
            symbol="BTCUSDT",
            market="USDT-M perpetual futures",
            timeframe="1m",
            tested_start=0,
            tested_end=0,
            row_count=1,
        )

    def test_zero_trade_metrics_use_null_not_infinity(self):
        cfg = BacktestConfig(initial_cash=1000.0)
        result = BacktestEngine(cfg).run([Bar(0,100,100,100,100,1)], NoopStrategy())
        metrics = summarize(result, cfg.initial_cash)
        self.assertIsNone(metrics["profit_factor"])
        self.assertIsNone(metrics["expectancy_closed_trade"])
    def test_output_is_strict_json_and_preserves_funding_config(self):
        cfg = BacktestConfig(
            initial_cash=1000.0,
            funding_rate_by_time={120_000: 0.001},
            funding_price_by_time={120_000: 99.5},
        )
        result = BacktestEngine(cfg).run([Bar(0,100,100,100,100,1)], NoopStrategy())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_results(out, result, cfg, self.metadata())
            with (out / "metrics.json").open("r", encoding="utf-8") as handle:
                metrics = json.load(handle)
            with (out / "config.json").open("r", encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertIsNone(metrics["profit_factor"])
            self.assertEqual(saved["funding_rate_by_time"]["120000"], 0.001)
            self.assertEqual(saved["funding_price_by_time"]["120000"], 99.5)


if __name__ == "__main__":
    unittest.main()
