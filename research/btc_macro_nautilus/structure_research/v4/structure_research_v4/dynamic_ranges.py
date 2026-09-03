from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .causal_features import WINDOWS


def _ols_line(values: pd.Series) -> tuple[float, float]:
    x = np.arange(len(values), dtype=float)
    if len(values) == 0:
        return math.nan, math.nan
    slope, intercept = np.polyfit(x, values.to_numpy(dtype=float), 1)
    return float(intercept), float(slope)


def build_dynamic_range_candidates(frame: pd.DataFrame, rolling_features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    candidate_id = 0
    for index in range(len(frame)):
        current = frame.iloc[index]
        for window in WINDOWS:
            history = frame.iloc[max(0, index - window) : index]
            if len(history) < 2:
                continue
            atr = rolling_features[
                (rolling_features["available_at_time"] == current["open_datetime"])
                & (rolling_features["window_size_bars"] == window)
            ]["atr14_wilder"]
            atr_value = float(atr.iloc[0]) if not atr.empty and pd.notna(atr.iloc[0]) else math.nan
            candidate_available_at = current["open_datetime"]
            methods = {
                "A": _method_a(history),
                "B": _method_b(history),
                "C": _method_c(history),
            }
            for method, values in methods.items():
                candidate_id += 1
                width_start = values["upper_at_history_start"] - values["lower_at_history_start"]
                width_end = values["upper_at_history_end"] - values["lower_at_history_end"]
                width_current = values["upper_projected_current"] - values["lower_projected_current"]
                closes = history["close"].to_numpy(dtype=float)
                path = np.abs(np.diff(closes)).sum()
                direct = abs(closes[-1] - closes[0])
                close_inside = ((history["close"] <= values["upper_at_history_end"]) & (history["close"] >= values["lower_at_history_end"])).mean()
                candidate = {
                    "range_candidate_id": f"RC{candidate_id:07d}",
                    "method": method,
                    "window_size_bars": window,
                    "history_start_time": history["open_datetime"].iloc[0],
                    "history_end_time": history["close_datetime"].iloc[-1],
                    "candidate_available_at": candidate_available_at,
                    **values,
                    "upper_slope_pct_per_bar": values["upper_slope_price_per_bar"] / history["close"].iloc[-1],
                    "lower_slope_pct_per_bar": values["lower_slope_price_per_bar"] / history["close"].iloc[-1],
                    "mid_slope_pct_per_bar": values["mid_slope_price_per_bar"] / history["close"].iloc[-1],
                    "upper_slope_atr_per_bar": values["upper_slope_price_per_bar"] / atr_value if atr_value and not math.isnan(atr_value) else math.nan,
                    "lower_slope_atr_per_bar": values["lower_slope_price_per_bar"] / atr_value if atr_value and not math.isnan(atr_value) else math.nan,
                    "width_start": width_start,
                    "width_end": width_end,
                    "width_projected_current": width_current,
                    "width_change_abs": width_end - width_start,
                    "width_change_ratio": width_end / width_start if width_start else math.nan,
                    "parallelism_atr_normalized": abs(values["upper_slope_price_per_bar"] - values["lower_slope_price_per_bar"]) / atr_value if atr_value and not math.isnan(atr_value) else math.nan,
                    "close_inside_share": float(close_inside),
                    "full_candle_inside_share": float(((history["high"] <= values["upper_at_history_end"]) & (history["low"] >= values["lower_at_history_end"])).mean()),
                    "wick_inside_share": float(((history["high"] <= values["upper_at_history_end"]) | (history["low"] >= values["lower_at_history_end"])).mean()),
                    "mid_cross_count": int(np.sum(np.diff(np.sign(history["close"] - ((values["upper_at_history_end"] + values["lower_at_history_end"]) / 2.0))) != 0)),
                    "mid_cross_rate_per_bar": math.nan,
                    "directional_progress_abs": history["close"].iloc[-1] - history["close"].iloc[0],
                    "directional_progress_to_width": (history["close"].iloc[-1] - history["close"].iloc[0]) / width_end if width_end else math.nan,
                    "close_path_efficiency": direct / path if path else math.nan,
                }
                candidate["mid_cross_rate_per_bar"] = candidate["mid_cross_count"] / max(len(history) - 1, 1)
                for prefix in ["upper", "lower"]:
                    touches = history["high"] if prefix == "upper" else history["low"]
                    boundary = values["upper_at_history_end"] if prefix == "upper" else values["lower_at_history_end"]
                    comparator = np.abs(touches - boundary)
                    for multiple, label in [(0.05, "005"), (0.10, "010"), (0.20, "020"), (0.30, "030")]:
                        key = f"{prefix}_touch_count_{label}atr"
                        candidate[key] = int((comparator <= atr_value * multiple).sum()) if atr_value and not math.isnan(atr_value) else 0
                candidate["alternating_touch_count"] = min(candidate["upper_touch_count_010atr"], candidate["lower_touch_count_010atr"])
                candidate["same_side_repeat_count"] = max(candidate["upper_touch_count_010atr"], candidate["lower_touch_count_010atr"])
                rows.append(candidate)
    return pd.DataFrame(rows)


def _method_a(history: pd.DataFrame) -> dict:
    upper = float(history["high"].max())
    lower = float(history["low"].min())
    return _pack_values(upper, upper, upper, lower, lower, lower)


def _method_b(history: pd.DataFrame) -> dict:
    intercept, slope = _ols_line(history["close"])
    x = np.arange(len(history), dtype=float)
    central = intercept + slope * x
    residuals = history["close"].to_numpy(dtype=float) - central
    upper = central + residuals.max()
    lower = central + residuals.min()
    return _pack_values(upper[0], upper[-1], upper[-1] + slope, lower[0], lower[-1], lower[-1] + slope, slope, slope)


def _method_c(history: pd.DataFrame) -> dict:
    upper_intercept, upper_slope = _ols_line(history["high"])
    lower_intercept, lower_slope = _ols_line(history["low"])
    x_end = len(history) - 1
    return _pack_values(
        upper_intercept,
        upper_intercept + upper_slope * x_end,
        upper_intercept + upper_slope * (x_end + 1),
        lower_intercept,
        lower_intercept + lower_slope * x_end,
        lower_intercept + lower_slope * (x_end + 1),
        upper_slope,
        lower_slope,
    )


def _pack_values(
    upper_start: float,
    upper_end: float,
    upper_current: float,
    lower_start: float,
    lower_end: float,
    lower_current: float,
    upper_slope: float = 0.0,
    lower_slope: float = 0.0,
) -> dict:
    mid_start = (upper_start + lower_start) / 2.0
    mid_end = (upper_end + lower_end) / 2.0
    mid_current = (upper_current + lower_current) / 2.0
    mid_slope = (upper_slope + lower_slope) / 2.0
    return {
        "upper_at_history_start": upper_start,
        "upper_at_history_end": upper_end,
        "upper_projected_current": upper_current,
        "lower_at_history_start": lower_start,
        "lower_at_history_end": lower_end,
        "lower_projected_current": lower_current,
        "mid_at_history_start": mid_start,
        "mid_at_history_end": mid_end,
        "mid_projected_current": mid_current,
        "upper_slope_price_per_bar": upper_slope,
        "lower_slope_price_per_bar": lower_slope,
        "mid_slope_price_per_bar": mid_slope,
    }
