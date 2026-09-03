from __future__ import annotations

import math

import numpy as np
import pandas as pd


WINDOWS = [18, 42, 84]


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def add_atr_and_volatility(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    tr = true_range(result)
    result["atr14_sma"] = tr.shift(1).rolling(14).mean()
    result["atr14_wilder"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift(1)
    pct_returns = result["close"].pct_change()
    log_returns = np.log(result["close"]).diff()
    result["realized_vol_pct_return_std"] = pct_returns.shift(1).rolling(14).std()
    result["realized_vol_log_return_std"] = log_returns.shift(1).rolling(14).std()
    return result


def compute_speed(last_close: float, first_close: float, duration_days: float) -> float:
    if duration_days <= 0 or pd.isna(last_close) or pd.isna(first_close):
        return math.nan
    return ((last_close / first_close) - 1.0) / duration_days


def build_rolling_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = add_atr_and_volatility(frame)
    rows: list[dict] = []
    closes = result["close"].astype(float)
    for index in range(len(result)):
        current = result.iloc[index]
        for window in WINDOWS:
            history = result.iloc[max(0, index - window) : index]
            previous = result.iloc[max(0, index - 2 * window) : max(0, index - window)]
            row = {
                "open_datetime": current["open_datetime"],
                "close_datetime": current["close_datetime"],
                "window_size_bars": window,
                "bars_available": len(history),
                "window_is_full": len(history) == window,
                "actual_window_hours": float(
                    (history["close_datetime"].max() - history["open_datetime"].min()).total_seconds() / 3600.0
                )
                if len(history) > 0
                else math.nan,
                "gap_count": int((history["open_datetime"].diff().dropna().dt.total_seconds() / 3600.0 > 6.0).sum())
                if len(history) > 1
                else 0,
                "window_start_time": history["open_datetime"].min() if len(history) else pd.NaT,
                "window_end_time": history["close_datetime"].max() if len(history) else pd.NaT,
                "available_at_time": current["open_datetime"],
                "range_abs": float(history["high"].max() - history["low"].min()) if len(history) else math.nan,
                "range_ratio_current_to_previous": float(
                    (history["high"].max() - history["low"].min()) / (previous["high"].max() - previous["low"].min())
                )
                if len(history) and len(previous) and float(previous["high"].max() - previous["low"].min()) != 0.0
                else math.nan,
                "speed_pct_per_day_signed": compute_speed(
                    history["close"].iloc[-1] if len(history) else math.nan,
                    history["close"].iloc[0] if len(history) else math.nan,
                    len(history) * 4.0 / 24.0,
                ),
                "speed_pct_per_day_abs": math.nan,
                "recent_speed_24h_signed": compute_speed(
                    closes.iloc[index - 1] if index >= 1 else math.nan,
                    closes.iloc[max(0, index - 6)] if index >= 6 else math.nan,
                    1.0,
                ),
                "recent_speed_24h_abs": math.nan,
                "recent_speed_3d_signed": compute_speed(
                    closes.iloc[index - 1] if index >= 1 else math.nan,
                    closes.iloc[max(0, index - 18)] if index >= 18 else math.nan,
                    3.0,
                ),
                "recent_speed_3d_abs": math.nan,
                "recent_speed_7d_signed": compute_speed(
                    closes.iloc[index - 1] if index >= 1 else math.nan,
                    closes.iloc[max(0, index - 42)] if index >= 42 else math.nan,
                    7.0,
                ),
                "recent_speed_7d_abs": math.nan,
                "atr14_sma": current["atr14_sma"],
                "atr14_wilder": current["atr14_wilder"],
                "realized_vol_pct_return_std": current["realized_vol_pct_return_std"],
                "realized_vol_log_return_std": current["realized_vol_log_return_std"],
            }
            for field in [
                "speed_pct_per_day_signed",
                "recent_speed_24h_signed",
                "recent_speed_3d_signed",
                "recent_speed_7d_signed",
            ]:
                abs_field = field.replace("_signed", "_abs")
                row[abs_field] = abs(row[field]) if pd.notna(row[field]) else math.nan
            rows.append(row)
    return pd.DataFrame(rows)


def compute_path_features(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    records: list[dict] = []
    for window in WINDOWS:
        for index in range(len(frame)):
            history = frame.iloc[max(0, index - window) : index]
            if len(history) < 2:
                continue
            path = history["close"].diff().abs().sum()
            direct = abs(history["close"].iloc[-1] - history["close"].iloc[0])
            efficiency = direct / path if path else np.nan
            records.append(
                {
                    "available_at_time": frame.iloc[index]["open_datetime"],
                    "window_size_bars": window,
                    f"close_path_length_{label}": float(path),
                    f"close_path_efficiency_{label}": float(efficiency),
                    f"close_path_tortuosity_{label}": float(path / direct) if direct else np.nan,
                }
            )
    return pd.DataFrame(records)
