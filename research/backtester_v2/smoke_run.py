from pathlib import Path

from .data import iter_canonical_1m_bars
from .engine import BacktestEngine
from .metrics import summarize
from .models import BacktestConfig, OrderIntent

MANIFEST = Path(
    "/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data/"
    "manifests/strict_futures_1m_manifest.json"
)


class SmokeStrategy:
    def __init__(self) -> None:
        self.sent = False

    def on_bar(self, bar, state):
        if not self.sent:
            self.sent = True
            return [
                OrderIntent.market("long", qty=0.01, max_hold_bars=10),
                OrderIntent.market("short", qty=0.01, max_hold_bars=10),
            ]
        return []


def main() -> None:
    start_ms = 1569165480000
    end_ms = start_ms + 60_000 * 50
    bars = list(iter_canonical_1m_bars(MANIFEST, start_ms, end_ms))
    config = BacktestConfig(
        initial_cash=10_000.0,
        maker_fee_rate=0.0002,
        taker_fee_rate=0.0005,
        slippage_rate=0.0001,
        intrabar_policy="worst_case",
        limit_fill_policy="strict_through",
        end_of_data_policy="force_close",
    )
    result = BacktestEngine(config).run(bars, SmokeStrategy())
    print(summarize(result, config.initial_cash))
    print(result.trades[0] if result.trades else "NO CLOSED TRADE")


if __name__ == "__main__":
    main()
