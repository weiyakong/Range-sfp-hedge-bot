from __future__ import annotations

import math

import numpy as np
import pandas as pd


def build_excursions(frame: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    by_time = {row["candidate_available_at"]: chunk for row, chunk in []}
    for open_time, chunk in candidates.groupby("candidate_available_at"):
        by_time[open_time] = chunk
    indexed = frame.set_index("open_datetime")
    for open_time, chunk in by_time.items():
        if open_time not in indexed.index:
            continue
        bar = indexed.loc[open_time]
        for candidate in chunk.to_dict(orient="records"):
            upper = candidate["upper_projected_current"]
            lower = candidate["lower_projected_current"]
            wick_outside = bool(bar["high"] > upper or bar["low"] < lower)
            close_outside = bool(bar["close"] > upper or bar["close"] < lower)
            if not (wick_outside or close_outside):
                continue
            width = upper - lower
            atr = np.nan
            side = "upper" if bar["high"] > upper else "lower"
            row = {
                "range_candidate_id": candidate["range_candidate_id"],
                "observation_time": open_time,
                "observation_available_at": bar["close_datetime"],
                "side": side,
                "wick_distance_beyond_abs": max(bar["high"] - upper, lower - bar["low"], 0.0),
                "close_distance_beyond_abs": max(bar["close"] - upper, lower - bar["close"], 0.0),
                "wick_outside": wick_outside,
                "close_outside": close_outside,
                "two_sided_range_sweep": bool(bar["high"] > upper and bar["low"] < lower),
                "wick_only_break": bool(wick_outside and not close_outside),
            }
            for prefix in ["wick", "close"]:
                abs_value = row[f"{prefix}_distance_beyond_abs"]
                row[f"{prefix}_distance_beyond_pct"] = abs_value / bar["close"] if bar["close"] else math.nan
                row[f"{prefix}_distance_beyond_atr"] = math.nan if pd.isna(atr) else abs_value / atr
                row[f"{prefix}_distance_beyond_width"] = abs_value / width if width else math.nan
            future = _future_horizons(frame, open_time, candidate)
            row.update(future)
            rows.append(row)
    return pd.DataFrame(rows)


def _future_horizons(frame: pd.DataFrame, open_time: pd.Timestamp, candidate: dict) -> dict:
    result: dict = {}
    start_index = frame.index[frame["open_datetime"] == open_time]
    if len(start_index) == 0:
        return result
    index = int(start_index[0])
    for step in [1, 3, 6]:
        future = frame.iloc[index + 1 : index + 1 + step]
        result[f"h{step}_bars_available"] = len(future)
        complete = len(future) == step
        result[f"h{step}_horizon_complete"] = complete
        if not complete:
            result[f"h{step}_mfe_abs"] = np.nan
            result[f"h{step}_mae_abs"] = np.nan
            result[f"h{step}_return_inside_outcome"] = ""
            continue
        upper = candidate["upper_projected_current"] + candidate["upper_slope_price_per_bar"] * step
        lower = candidate["lower_projected_current"] + candidate["lower_slope_price_per_bar"] * step
        result[f"h{step}_mfe_abs"] = float(max((future["high"] - upper).max(), (lower - future["low"]).max(), 0.0))
        result[f"h{step}_mae_abs"] = float(max((upper - future["low"]).max(), (future["high"] - lower).max(), 0.0))
        last_close = future["close"].iloc[-1]
        result[f"h{step}_return_inside_outcome"] = "inside" if lower <= last_close <= upper else "outside"
    return result
