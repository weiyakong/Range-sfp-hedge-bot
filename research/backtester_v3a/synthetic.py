"""Deterministic synthetic instrument profiles and a geometry test strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from research.backtester_v2.models import Bar, OrderIntent, StrategyState

from .contracts import InstrumentMetadata, parse_instrument_metadata


_SOURCE_HASH = "f" * 64


class OneShotGeometryStrategy:
    """Emit one grid-valid market intent for differential and synthetic tests."""

    def __init__(self, side: str, qty: float):
        if side not in {"long", "short"}:
            raise ValueError("side must equal long or short")
        self.side = side
        self.qty = qty
        self._emitted = False
        self.emitted_intents: List[OrderIntent] = []

    def on_bar(self, bar: Bar, state: StrategyState) -> List[OrderIntent]:
        del bar, state
        if self._emitted:
            return []
        self._emitted = True
        intent = OrderIntent.market(self.side, self.qty)
        self.emitted_intents.append(intent)
        return [intent]


@dataclass(frozen=True)
class SyntheticInstrumentProfile:
    name: str
    base_price: float
    grid_valid_qty: float
    metadata: InstrumentMetadata
    price_step: float

    def bars(self) -> List[Bar]:
        result: List[Bar] = []
        for index in range(3):
            open_price = self.base_price + index * self.price_step
            result.append(Bar(
                open_time=index * 60_000,
                open=open_price,
                high=open_price + 2 * self.price_step,
                low=open_price - 2 * self.price_step,
                close=open_price + self.price_step,
                volume=100.0,
            ))
        return result


def _metadata(
    symbol: str,
    *,
    tick_size: str,
    step_size: str,
    min_qty: str,
    min_notional: str,
    price_precision: int,
    quantity_precision: int,
) -> InstrumentMetadata:
    return parse_instrument_metadata({
        "schema_version": "BACKTESTER_V3A_INSTRUMENT_METADATA_V1",
        "exchange": "SYNTHETIC",
        "market": "PERPETUAL",
        "symbol": symbol,
        "metadata_id": f"{symbol}-PROFILE-V1",
        "tick_size": tick_size,
        "step_size": step_size,
        "min_qty": min_qty,
        "min_notional": min_notional,
        "price_precision": price_precision,
        "quantity_precision": quantity_precision,
        "provenance": {
            "fidelity_classification": "RESEARCH_ASSUMPTION",
            "source": "checked-in synthetic profile",
            "source_sha256": _SOURCE_HASH,
            "effective_start_ms": None,
            "effective_end_ms": None,
        },
    })


def synthetic_profiles() -> Dict[str, SyntheticInstrumentProfile]:
    return {
        "BTC-like": SyntheticInstrumentProfile(
            name="BTC-like",
            base_price=30_000.0,
            grid_valid_qty=0.01,
            price_step=30.0,
            metadata=_metadata(
                "BTCUSDT", tick_size="0.10", step_size="0.001",
                min_qty="0.001", min_notional="5",
                price_precision=2, quantity_precision=3,
            ),
        ),
        "ETH-like": SyntheticInstrumentProfile(
            name="ETH-like",
            base_price=2_000.0,
            grid_valid_qty=0.1,
            price_step=2.0,
            metadata=_metadata(
                "ETHUSDT", tick_size="0.01", step_size="0.01",
                min_qty="0.01", min_notional="10",
                price_precision=2, quantity_precision=2,
            ),
        ),
        "SOL/alt-like": SyntheticInstrumentProfile(
            name="SOL/alt-like",
            base_price=50.0,
            grid_valid_qty=5.0,
            price_step=0.05,
            metadata=_metadata(
                "SOLUSDT", tick_size="0.001", step_size="0.1",
                min_qty="0.1", min_notional="20",
                price_precision=3, quantity_precision=1,
            ),
        ),
    }


__all__ = [
    "OneShotGeometryStrategy",
    "SyntheticInstrumentProfile",
    "synthetic_profiles",
]
