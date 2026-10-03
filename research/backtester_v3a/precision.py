"""Instrument precision boundary before unchanged V2 execution semantics."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from math import isfinite

from research.backtester_v2.models import OrderIntent

from .contracts import InstrumentMetadata


class IntentNormalizationError(ValueError):
    """Raised when a raw strategy intent cannot form a valid instrument order."""


def _decimal(value: float, path: str) -> Decimal:
    if not isfinite(value):
        raise IntentNormalizationError(f"{path} must be finite")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise IntentNormalizationError(f"{path} is not a decimal value") from exc


def _grid_round(value: Decimal, step: Decimal, *, quantity: bool) -> Decimal:
    rounding = ROUND_FLOOR if quantity else ROUND_HALF_UP
    units = (value / step).quantize(Decimal("1"), rounding=rounding)
    return units * step


def _normalized_price(value: float, tick: Decimal, path: str) -> float:
    rounded = _grid_round(_decimal(value, path), tick, quantity=False)
    if rounded <= 0:
        raise IntentNormalizationError(f"{path} rounds to a non-positive price")
    return float(rounded)


def normalize_order_intent(
    intent: OrderIntent,
    metadata: InstrumentMetadata,
    *,
    reference_price: float,
) -> OrderIntent:
    """Normalize one raw intent without changing the execution engine."""
    if intent.action != "enter":
        return intent
    if intent.side not in {"long", "short"}:
        raise IntentNormalizationError("entry intent requires long or short side")
    reference = _decimal(reference_price, "reference_price")
    if reference <= 0:
        raise IntentNormalizationError("reference_price must be positive")
    step = Decimal(metadata.step_size)
    tick = Decimal(metadata.tick_size)
    quantity = _grid_round(_decimal(intent.qty, "qty"), step, quantity=True)
    if quantity <= 0:
        raise IntentNormalizationError("qty becomes zero after step rounding")
    if quantity < Decimal(metadata.min_qty):
        raise IntentNormalizationError("normalized qty is below min_qty")

    limit_price = (
        _normalized_price(intent.limit_price, tick, "limit_price")
        if intent.limit_price is not None else None
    )
    stop_loss = (
        _normalized_price(intent.stop_loss, tick, "stop_loss")
        if intent.stop_loss is not None else None
    )
    take_profit = (
        _normalized_price(intent.take_profit, tick, "take_profit")
        if intent.take_profit is not None else None
    )
    entry_reference = Decimal(str(limit_price)) if limit_price is not None else reference
    if quantity * entry_reference < Decimal(metadata.min_notional):
        raise IntentNormalizationError("normalized order is below min_notional")

    if intent.side == "long":
        if stop_loss is not None and Decimal(str(stop_loss)) >= entry_reference:
            raise IntentNormalizationError("rounded long stop_loss must be below entry")
        if take_profit is not None and Decimal(str(take_profit)) <= entry_reference:
            raise IntentNormalizationError("rounded long take_profit must be above entry")
    else:
        if stop_loss is not None and Decimal(str(stop_loss)) <= entry_reference:
            raise IntentNormalizationError("rounded short stop_loss must be above entry")
        if take_profit is not None and Decimal(str(take_profit)) >= entry_reference:
            raise IntentNormalizationError("rounded short take_profit must be below entry")

    return replace(
        intent,
        qty=float(quantity),
        limit_price=limit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


def classify_marketable_limit(intent: OrderIntent, *, bar_open: float) -> bool:
    """Classify a normalized limit using the unchanged V2 open-price rule."""
    if intent.order_type != "limit" or intent.limit_price is None:
        raise IntentNormalizationError("marketability classification requires a limit")
    limit_price = float(intent.limit_price)
    if intent.side == "long":
        return bar_open <= limit_price
    if intent.side == "short":
        return bar_open >= limit_price
    raise IntentNormalizationError("limit intent requires long or short side")


__all__ = [
    "IntentNormalizationError",
    "classify_marketable_limit",
    "normalize_order_intent",
]
