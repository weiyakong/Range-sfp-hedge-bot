#!/usr/bin/env python3
"""Build contract-defined reusable atomic features for canonical futures candles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA_VERSION = "btc-futures-atomic-features-v1"
FEATURE_VERSION = "structure-research-v5-contract-v1"
RESOLUTIONS = ("4h", "12h", "1d")
BASE_COLUMNS = (
    "timestamp",
    "end_time",
    "resolution",
    "market",
    "instrument",
    "source_complete",
    "source_constituent_count",
    "source_expected_constituent_count",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "previous_timestamp",
    "pair_eligible",
    "pair_ineligibility_reason",
)
GEOMETRY_FIELDS = (
    "full_range",
    "body_size",
    "body_high",
    "body_low",
    "upper_wick",
    "lower_wick",
    "body_share",
    "upper_wick_share",
    "lower_wick_share",
    "log_full_range",
    "log_body_size",
    "log_upper_wick",
    "log_lower_wick",
    "complete_volume",
    "complete_quote_volume",
    "complete_trade_count",
    "complete_taker_buy_base_volume",
    "complete_taker_buy_quote_volume",
    "volume_body_up",
    "volume_body_down",
    "volume_body_flat",
)
MOVEMENT_FIELDS = (
    "signed_price_change",
    "absolute_price_change",
    "signed_close_return",
    "absolute_close_return",
    "signed_return_pct",
    "absolute_return_pct",
    "signed_log_move",
    "absolute_log_move",
    "local_direction",
    "duration_hours",
    "raw_signed_speed_pct_per_hour",
    "signed_log_speed_per_hour",
    "absolute_log_speed_per_hour",
    "close_step_sign",
    "alternation_indicator",
    "volume_close_step_up",
    "volume_close_step_down",
    "volume_close_step_flat",
    "true_range",
    "atr14_sma",
    "atr14_wilder",
)
RANGE_OVERLAP_FIELDS = (
    "range_overlap_low",
    "range_overlap_high",
    "range_overlap_abs",
    "range_union_abs",
    "overlap_share_prev",
    "overlap_share_curr",
    "overlap_jaccard",
    "overlap_mid",
    "overlap_low_pos_prev",
    "overlap_high_pos_prev",
    "overlap_mid_pos_prev",
    "overlap_low_pos_curr",
    "overlap_high_pos_curr",
    "overlap_mid_pos_curr",
)
BODY_OVERLAP_FIELDS = (
    "body_overlap_low",
    "body_overlap_high",
    "body_overlap_abs",
    "body_union_abs",
    "body_overlap_share_prev",
    "body_overlap_share_curr",
    "body_overlap_jaccard",
)
EXTENSION_FIELDS = (
    "upper_extension_abs",
    "lower_extension_abs",
    "upper_extension_share_prev",
    "lower_extension_share_prev",
)
PENETRATION_BASES = (
    "extreme_penetration_from_top",
    "body_penetration_from_top",
    "close_penetration_from_top",
    "wick_only_penetration_from_top",
    "extreme_penetration_from_bottom",
    "body_penetration_from_bottom",
    "close_penetration_from_bottom",
    "wick_only_penetration_from_bottom",
)
PENETRATION_FIELDS = tuple(
    name + suffix for name in PENETRATION_BASES for suffix in ("_abs", "_share_prev")
)
PAIR_VALUE_FIELDS = (
    MOVEMENT_FIELDS
    + RANGE_OVERLAP_FIELDS
    + BODY_OVERLAP_FIELDS
    + EXTENSION_FIELDS
    + PENETRATION_FIELDS
)
FEATURE_COLUMNS = GEOMETRY_FIELDS + PAIR_VALUE_FIELDS
RATIO_0_1_FIELDS = (
    "body_share",
    "upper_wick_share",
    "lower_wick_share",
    "overlap_share_prev",
    "overlap_share_curr",
    "overlap_jaccard",
    "overlap_low_pos_prev",
    "overlap_high_pos_prev",
    "overlap_mid_pos_prev",
    "overlap_low_pos_curr",
    "overlap_high_pos_curr",
    "overlap_mid_pos_curr",
    "body_overlap_share_prev",
    "body_overlap_share_curr",
    "body_overlap_jaccard",
) + tuple(name + "_share_prev" for name in PENETRATION_BASES)


def _feature_dictionary() -> dict[str, dict[str, str]]:
    definitions: dict[str, dict[str, str]] = {}

    def add(names: Iterable[str], formula: str, applicability: str, units: str = "price") -> None:
        for name in names:
            definitions[name] = {
                "formula": formula.replace("{name}", name),
                "units": units,
                "applicability": applicability,
                "null_meaning": f"{applicability} is not satisfied or a required denominator/log domain is invalid",
                "provenance": "validated canonical candle fields; Structure Research v5 contracts",
            }

    add(("full_range",), "high-low", "source candle is complete")
    add(("body_size",), "abs(close-open)", "source candle is complete")
    add(("body_high",), "max(open,close)", "source candle is complete")
    add(("body_low",), "min(open,close)", "source candle is complete")
    add(("upper_wick",), "high-body_high", "source candle is complete")
    add(("lower_wick",), "body_low-low", "source candle is complete")
    add(("body_share", "upper_wick_share", "lower_wick_share"), "named geometry numerator/full_range", "complete candle and full_range>0", "ratio")
    add(("log_full_range",), "ln(high/low)", "complete candle and high,low>0", "log-price")
    add(("log_body_size",), "abs(ln(close/open))", "complete candle and open,close>0", "log-price")
    add(("log_upper_wick",), "ln(high/body_high)", "complete candle and high,body_high>0", "log-price")
    add(("log_lower_wick",), "ln(body_low/low)", "complete candle and body_low,low>0", "log-price")
    add(
        ("complete_volume", "complete_quote_volume", "complete_trade_count", "complete_taker_buy_base_volume", "complete_taker_buy_quote_volume"),
        "source additive value when the candle is complete",
        "source candle is complete",
        "source-native additive units",
    )
    add(("volume_body_up", "volume_body_down", "volume_body_flat"), "volume assigned by sign(close-open)", "source candle is complete", "base volume")
    add(("signed_price_change",), "current.close-previous.close", "eligible adjacent pair")
    add(("absolute_price_change",), "abs(signed_price_change)", "eligible adjacent pair")
    add(("signed_close_return",), "current.close/previous.close-1", "eligible pair and previous.close!=0", "decimal return")
    add(("absolute_close_return",), "abs(signed_close_return)", "eligible pair and previous.close!=0", "decimal return")
    add(("signed_return_pct",), "100*(current.close/previous.close-1)", "eligible pair and previous.close!=0", "percent")
    add(("absolute_return_pct",), "abs(signed_return_pct)", "eligible pair and previous.close!=0", "percent")
    add(("signed_log_move",), "ln(current.close/previous.close)", "eligible pair and both closes>0", "log-price")
    add(("absolute_log_move",), "abs(signed_log_move)", "eligible pair and both closes>0", "log-price")
    add(("local_direction", "close_step_sign"), "mechanical sign of current.close-previous.close", "eligible adjacent pair", "enum/sign")
    add(("duration_hours",), "(current.start-previous.start) in hours", "eligible adjacent pair", "hours")
    add(("raw_signed_speed_pct_per_hour",), "signed_return_pct/duration_hours", "eligible pair and duration_hours>0", "percent/hour")
    add(("signed_log_speed_per_hour",), "signed_log_move/duration_hours", "eligible pair and duration_hours>0", "log-price/hour")
    add(("absolute_log_speed_per_hour",), "absolute_log_move/duration_hours", "eligible pair and duration_hours>0", "log-price/hour")
    add(("alternation_indicator",), "current nonzero close-step sign differs from preceding nonzero eligible sign", "eligible nonzero step with preceding nonzero eligible step", "boolean")
    add(("volume_close_step_up", "volume_close_step_down", "volume_close_step_flat"), "current volume assigned by close-step sign", "eligible adjacent pair", "base volume")
    add(("true_range",), "max(high-low,abs(high-previous.close),abs(low-previous.close))", "eligible adjacent pair")
    add(("atr14_sma",), "mean of latest 14 consecutive valid true_range values after reset", "14 consecutive valid TR values")
    add(("atr14_wilder",), "first 14 valid TR mean, then ((previous*13)+TR)/14", "14 consecutive valid TR values")
    add(RANGE_OVERLAP_FIELDS, "contract range-overlap formula for {name}", "eligible adjacent pair", "price or ratio")
    add(BODY_OVERLAP_FIELDS, "contract body-overlap formula for {name}", "eligible adjacent pair", "price or ratio")
    add(EXTENSION_FIELDS, "contract neutral-extension formula for {name}", "eligible adjacent pair", "price or ratio")
    add(PENETRATION_FIELDS, "contract symmetric-penetration formula for {name}", "eligible adjacent pair", "price or ratio")
    return definitions


FEATURE_DICTIONARY = _feature_dictionary()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    partial = path.with_name(path.name + ".partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def safe_log_ratio(numerator: float, denominator: float) -> float | None:
    return math.log(numerator / denominator) if numerator > 0 and denominator > 0 else None


def sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def geometry(candle: dict[str, Any]) -> dict[str, Any]:
    if not candle["complete"]:
        return {name: None for name in GEOMETRY_FIELDS}
    open_price = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])
    full_range = high - low
    body_high = max(open_price, close)
    body_low = min(open_price, close)
    body_size = abs(close - open_price)
    upper_wick = high - body_high
    lower_wick = body_low - low
    body_sign = sign(close - open_price)
    result = {
        "full_range": full_range,
        "body_size": body_size,
        "body_high": body_high,
        "body_low": body_low,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "body_share": safe_div(body_size, full_range),
        "upper_wick_share": safe_div(upper_wick, full_range),
        "lower_wick_share": safe_div(lower_wick, full_range),
        "log_full_range": safe_log_ratio(high, low),
        "log_body_size": abs(safe_log_ratio(close, open_price)) if safe_log_ratio(close, open_price) is not None else None,
        "log_upper_wick": safe_log_ratio(high, body_high),
        "log_lower_wick": safe_log_ratio(body_low, low),
        "complete_volume": float(candle["volume"]),
        "complete_quote_volume": float(candle["quote_volume"]),
        "complete_trade_count": int(candle["trade_count"]),
        "complete_taker_buy_base_volume": float(candle["taker_buy_base_volume"]),
        "complete_taker_buy_quote_volume": float(candle["taker_buy_quote_volume"]),
        "volume_body_up": float(candle["volume"]) if body_sign > 0 else 0.0,
        "volume_body_down": float(candle["volume"]) if body_sign < 0 else 0.0,
        "volume_body_flat": float(candle["volume"]) if body_sign == 0 else 0.0,
    }
    return result


def pair_is_eligible(previous: dict[str, Any] | None, current: dict[str, Any]) -> tuple[bool, str | None]:
    if previous is None:
        return False, "first_row"
    if not previous["complete"]:
        return False, "previous_incomplete"
    if not current["complete"]:
        return False, "current_incomplete"
    if current["start_time"] != previous["end_time"]:
        return False, "non_adjacent"
    if (
        current["market"] != previous["market"]
        or current["instrument"] != previous["instrument"]
        or current["resolution"] != previous["resolution"]
    ):
        return False, "source_segment_or_resolution_mismatch"
    return True, None


def pair_features(previous: dict[str, Any], current: dict[str, Any], previous_nonzero_sign: int | None) -> dict[str, Any]:
    prev_close = float(previous["close"])
    curr_close = float(current["close"])
    price_change = curr_close - prev_close
    step_sign = sign(price_change)
    close_return = curr_close / prev_close - 1 if prev_close != 0 else None
    log_move = safe_log_ratio(curr_close, prev_close)
    duration_hours = (current["start_time"] - previous["start_time"]).total_seconds() / 3600

    prev_low, prev_high = float(previous["low"]), float(previous["high"])
    curr_low, curr_high = float(current["low"]), float(current["high"])
    prev_range, curr_range = prev_high - prev_low, curr_high - curr_low
    overlap_low, overlap_high = max(prev_low, curr_low), min(prev_high, curr_high)
    overlap_abs = max(0.0, overlap_high - overlap_low)
    range_union = max(prev_high, curr_high) - min(prev_low, curr_low)
    positive_overlap = overlap_abs > 0
    overlap_mid = (overlap_low + overlap_high) / 2 if positive_overlap else None

    prev_body_low, prev_body_high = min(float(previous["open"]), prev_close), max(float(previous["open"]), prev_close)
    curr_body_low, curr_body_high = min(float(current["open"]), curr_close), max(float(current["open"]), curr_close)
    prev_body, curr_body = prev_body_high - prev_body_low, curr_body_high - curr_body_low
    body_overlap_low, body_overlap_high = max(prev_body_low, curr_body_low), min(prev_body_high, curr_body_high)
    body_overlap_abs = max(0.0, body_overlap_high - body_overlap_low)
    body_union = max(prev_body_high, curr_body_high) - min(prev_body_low, curr_body_low)

    upper_extension = max(0.0, curr_high - prev_high)
    lower_extension = max(0.0, prev_low - curr_low)
    clamp = lambda value: min(max(value, 0.0), prev_range)
    top_extreme = clamp(prev_high - curr_low)
    top_body = clamp(prev_high - curr_body_low)
    top_close = clamp(prev_high - curr_close)
    bottom_extreme = clamp(curr_high - prev_low)
    bottom_body = clamp(curr_body_high - prev_low)
    bottom_close = clamp(curr_close - prev_low)
    penetration = {
        "extreme_penetration_from_top_abs": top_extreme,
        "body_penetration_from_top_abs": top_body,
        "close_penetration_from_top_abs": top_close,
        "wick_only_penetration_from_top_abs": max(0.0, top_extreme - top_body),
        "extreme_penetration_from_bottom_abs": bottom_extreme,
        "body_penetration_from_bottom_abs": bottom_body,
        "close_penetration_from_bottom_abs": bottom_close,
        "wick_only_penetration_from_bottom_abs": max(0.0, bottom_extreme - bottom_body),
    }
    for name, value in list(penetration.items()):
        penetration[name.replace("_abs", "_share_prev")] = safe_div(value, prev_range)

    result = {
        "signed_price_change": price_change,
        "absolute_price_change": abs(price_change),
        "signed_close_return": close_return,
        "absolute_close_return": abs(close_return) if close_return is not None else None,
        "signed_return_pct": close_return * 100 if close_return is not None else None,
        "absolute_return_pct": abs(close_return * 100) if close_return is not None else None,
        "signed_log_move": log_move,
        "absolute_log_move": abs(log_move) if log_move is not None else None,
        "local_direction": "up" if step_sign > 0 else "down" if step_sign < 0 else "flat",
        "duration_hours": duration_hours,
        "raw_signed_speed_pct_per_hour": close_return * 100 / duration_hours if close_return is not None and duration_hours > 0 else None,
        "signed_log_speed_per_hour": log_move / duration_hours if log_move is not None and duration_hours > 0 else None,
        "absolute_log_speed_per_hour": abs(log_move) / duration_hours if log_move is not None and duration_hours > 0 else None,
        "close_step_sign": step_sign,
        "alternation_indicator": (step_sign != previous_nonzero_sign) if step_sign != 0 and previous_nonzero_sign is not None else None,
        "volume_close_step_up": float(current["volume"]) if step_sign > 0 else 0.0,
        "volume_close_step_down": float(current["volume"]) if step_sign < 0 else 0.0,
        "volume_close_step_flat": float(current["volume"]) if step_sign == 0 else 0.0,
        "true_range": max(curr_range, abs(curr_high - prev_close), abs(curr_low - prev_close)),
        "atr14_sma": None,
        "atr14_wilder": None,
        "range_overlap_low": overlap_low,
        "range_overlap_high": overlap_high,
        "range_overlap_abs": overlap_abs,
        "range_union_abs": range_union,
        "overlap_share_prev": safe_div(overlap_abs, prev_range),
        "overlap_share_curr": safe_div(overlap_abs, curr_range),
        "overlap_jaccard": safe_div(overlap_abs, range_union),
        "overlap_mid": overlap_mid,
        "overlap_low_pos_prev": safe_div(overlap_low - prev_low, prev_range) if positive_overlap else None,
        "overlap_high_pos_prev": safe_div(overlap_high - prev_low, prev_range) if positive_overlap else None,
        "overlap_mid_pos_prev": safe_div(overlap_mid - prev_low, prev_range) if positive_overlap else None,
        "overlap_low_pos_curr": safe_div(overlap_low - curr_low, curr_range) if positive_overlap else None,
        "overlap_high_pos_curr": safe_div(overlap_high - curr_low, curr_range) if positive_overlap else None,
        "overlap_mid_pos_curr": safe_div(overlap_mid - curr_low, curr_range) if positive_overlap else None,
        "body_overlap_low": body_overlap_low,
        "body_overlap_high": body_overlap_high,
        "body_overlap_abs": body_overlap_abs,
        "body_union_abs": body_union,
        "body_overlap_share_prev": safe_div(body_overlap_abs, prev_body),
        "body_overlap_share_curr": safe_div(body_overlap_abs, curr_body),
        "body_overlap_jaccard": safe_div(body_overlap_abs, body_union),
        "upper_extension_abs": upper_extension,
        "lower_extension_abs": lower_extension,
        "upper_extension_share_prev": safe_div(upper_extension, prev_range),
        "lower_extension_share_prev": safe_div(lower_extension, prev_range),
    }
    result.update(penetration)
    return result


def compute_features(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    tr_run: list[float] = []
    wilder: float | None = None
    previous_nonzero_sign: int | None = None
    previous = None
    for candle in candles:
        eligible, reason = pair_is_eligible(previous, candle)
        row = {
            "timestamp": candle["start_time"],
            "end_time": candle["end_time"],
            "resolution": candle["resolution"],
            "market": candle["market"],
            "instrument": candle["instrument"],
            "source_complete": bool(candle["complete"]),
            "source_constituent_count": int(candle["constituent_count"]),
            "source_expected_constituent_count": int(candle["expected_constituent_count"]),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle["volume"]),
            "quote_volume": float(candle["quote_volume"]),
            "trade_count": int(candle["trade_count"]),
            "taker_buy_base_volume": float(candle["taker_buy_base_volume"]),
            "taker_buy_quote_volume": float(candle["taker_buy_quote_volume"]),
            "previous_timestamp": previous["start_time"] if previous else None,
            "pair_eligible": eligible,
            "pair_ineligibility_reason": reason,
        }
        row.update(geometry(candle))
        if not eligible:
            row.update({name: None for name in PAIR_VALUE_FIELDS})
            tr_run = []
            wilder = None
            previous_nonzero_sign = None
        else:
            features = pair_features(previous, candle, previous_nonzero_sign)
            tr = float(features["true_range"])
            tr_run.append(tr)
            if len(tr_run) >= 14:
                features["atr14_sma"] = sum(tr_run[-14:]) / 14
                if len(tr_run) == 14:
                    wilder = sum(tr_run) / 14
                else:
                    assert wilder is not None
                    wilder = (wilder * 13 + tr) / 14
                features["atr14_wilder"] = wilder
            row.update(features)
            current_sign = int(features["close_step_sign"])
            if current_sign != 0:
                previous_nonzero_sign = current_sign
        output.append(row)
        previous = candle
    return output


def read_candles(tf_dir: Path) -> tuple[list[dict[str, Any]], dict, str]:
    manifest_path = tf_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [Path(item["path"]) for item in manifest["output_files"]]
    for item, path in zip(manifest["output_files"], files):
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Source candle checksum mismatch: {path}")
    candles = pq.read_table(files).to_pylist()
    return candles, manifest, sha256_file(manifest_path)


def write_temp_dataset(rows: list[dict[str, Any]], temp_dir: Path) -> tuple[list[dict], pa.Schema]:
    table = pa.Table.from_pylist(rows)
    output_files = []
    for year in sorted({row["timestamp"].year for row in rows}):
        year_rows = [row for row in rows if row["timestamp"].year == year]
        path = temp_dir / f"part-{year}.parquet"
        pq.write_table(
            pa.Table.from_pylist(year_rows, schema=table.schema),
            path,
            compression="zstd",
            compression_level=9,
            use_dictionary=["resolution", "market", "instrument", "local_direction", "pair_ineligibility_reason"],
            write_statistics=True,
        )
        output_files.append({
            "path": path.name,
            "year": year,
            "rows": len(year_rows),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return output_files, table.schema


def read_feature_parts(directory: Path) -> list[dict[str, Any]]:
    return pq.read_table(sorted(directory.glob("part-*.parquet"))).to_pylist()


def _same_number(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, float) or isinstance(right, float):
        return float(left) == float(right)
    return left == right


def qa_features(candles: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict:
    errors = []
    if len(rows) != len(candles):
        errors.append("row_count")
    timestamps = [row["timestamp"] for row in rows]
    source_timestamps = [row["start_time"] for row in candles]
    if timestamps != source_timestamps:
        errors.append("timestamps_changed")
    if timestamps != sorted(timestamps):
        errors.append("non_monotonic")
    if len(timestamps) != len(set(timestamps)):
        errors.append("duplicates")
    input_pairs = (
        ("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"),
        ("volume", "volume"), ("quote_volume", "quote_volume"), ("trade_count", "trade_count"),
        ("taker_buy_base_volume", "taker_buy_base_volume"),
        ("taker_buy_quote_volume", "taker_buy_quote_volume"),
    )
    for index, (source, row) in enumerate(zip(candles, rows)):
        for source_name, output_name in input_pairs:
            if not _same_number(source[source_name], row[output_name]):
                errors.append(f"input_changed:{index}:{source_name}")
        expected_eligible, _ = pair_is_eligible(candles[index - 1] if index else None, source)
        if row["pair_eligible"] != expected_eligible:
            errors.append(f"eligibility:{index}")
        if not expected_eligible and any(row[name] is not None for name in PAIR_VALUE_FIELDS):
            errors.append(f"ineligible_pair_values:{index}")
        if not source["complete"] and any(row[name] is not None for name in GEOMETRY_FIELDS):
            errors.append(f"incomplete_geometry:{index}")
        for name in FEATURE_COLUMNS:
            value = row[name]
            if isinstance(value, float) and not math.isfinite(value):
                errors.append(f"non_finite:{index}:{name}")
        for name in RATIO_0_1_FIELDS:
            value = row[name]
            if value is not None and not (-1e-12 <= value <= 1 + 1e-12):
                errors.append(f"ratio_range:{index}:{name}")

    eligible_indices = [index for index, row in enumerate(rows) if row["pair_eligible"]]
    spot_indices = sorted({0, eligible_indices[0], next(index for index, row in enumerate(rows) if row["timestamp"].year >= 2024), len(rows) - 1})
    spot_checks = []
    for index in spot_indices:
        source, row = candles[index], rows[index]
        checks = {"full_range": (float(source["high"]) - float(source["low"])) if source["complete"] else None}
        if index and row["pair_eligible"]:
            previous = candles[index - 1]
            overlap = max(0.0, min(float(previous["high"]), float(source["high"])) - max(float(previous["low"]), float(source["low"])))
            union = max(float(previous["high"]), float(source["high"])) - min(float(previous["low"]), float(source["low"]))
            checks.update({
                "signed_price_change": float(source["close"]) - float(previous["close"]),
                "range_overlap_abs": overlap,
                "overlap_jaccard": overlap / union if union > 0 else None,
                "true_range": max(
                    float(source["high"]) - float(source["low"]),
                    abs(float(source["high"]) - float(previous["close"])),
                    abs(float(source["low"]) - float(previous["close"])),
                ),
            })
        passed = all(_same_number(row[name], value) for name, value in checks.items())
        spot_checks.append({"timestamp": row["timestamp"].isoformat(), "passed": passed})
        if not passed:
            errors.append(f"spot_check:{index}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "spot_checks": spot_checks,
        "row_count": len(rows),
        "pair_eligible_rows": sum(bool(row["pair_eligible"]) for row in rows),
        "pair_ineligible_rows": sum(not row["pair_eligible"] for row in rows),
    }


def build(data_root: Path, repo_root: Path) -> dict:
    total_started = time.perf_counter()
    outputs = {}
    temp_dirs: dict[str, Path] = {}
    final_dirs: dict[str, Path] = {}
    try:
        build_started = time.perf_counter()
        source_by_tf = {}
        feature_rows_by_tf = {}
        source_meta_by_tf = {}
        for resolution in RESOLUTIONS:
            candle_dir = data_root / f"derived/BTCUSDT/{resolution}"
            candles, source_manifest, source_manifest_sha = read_candles(candle_dir)
            source_by_tf[resolution] = candles
            source_meta_by_tf[resolution] = (candle_dir / "manifest.json", source_manifest, source_manifest_sha)
            feature_rows_by_tf[resolution] = compute_features(candles)

            final_dir = data_root / f"features/BTCUSDT/{resolution}_atomic"
            if final_dir.exists():
                raise FileExistsError(f"Feature output already exists; refusing unvalidated overwrite: {final_dir}")
            temp_dir = final_dir.parent / f".{final_dir.name}.build-{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=True)
            files, schema = write_temp_dataset(feature_rows_by_tf[resolution], temp_dir)
            temp_dirs[resolution] = temp_dir
            final_dirs[resolution] = final_dir
            outputs[resolution] = {
                "rows": len(feature_rows_by_tf[resolution]),
                "feature_columns": len(FEATURE_COLUMNS),
                "total_columns": len(schema.names),
                "bytes": sum(item["bytes"] for item in files),
                "output_files": files,
                "schema": str(schema),
            }
        build_seconds = time.perf_counter() - build_started

        qa_started = time.perf_counter()
        qa = {}
        for resolution in RESOLUTIONS:
            reloaded = read_feature_parts(temp_dirs[resolution])
            qa[resolution] = qa_features(source_by_tf[resolution], reloaded)
        qa_seconds = time.perf_counter() - qa_started
        if any(result["status"] != "PASS" for result in qa.values()):
            raise RuntimeError("Atomic feature QA failed")

        commit = git_commit(repo_root)
        build_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        pipeline_sha = sha256_file(Path(__file__))
        for resolution in RESOLUTIONS:
            source_manifest_path, source_manifest, source_manifest_sha = source_meta_by_tf[resolution]
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "feature_version": FEATURE_VERSION,
                "build_timestamp_utc": build_timestamp,
                "market": source_manifest["market"],
                "instrument": source_manifest["instrument"],
                "resolution": resolution,
                "source_candle_manifest_path": str(source_manifest_path),
                "source_candle_manifest_sha256": source_manifest_sha,
                "source_1m_manifest_path": source_manifest["source_manifest_path"],
                "source_1m_manifest_sha256": source_manifest["source_manifest_sha256"],
                "source_coverage": source_manifest["output_coverage"],
                "rows": outputs[resolution]["rows"],
                "feature_columns": outputs[resolution]["feature_columns"],
                "total_columns": outputs[resolution]["total_columns"],
                "partitioning": "year",
                "parquet_compression": "zstd",
                "output_files": [
                    {**item, "path": str(final_dirs[resolution] / item["path"])}
                    for item in outputs[resolution]["output_files"]
                ],
                "feature_dictionary": FEATURE_DICTIONARY,
                "deferred_metrics": {
                    "rolling_speed_change_and_acceleration": "contract does not fix row anchoring and compatible window matrix for this atomic fixed-candle table",
                    "rolling_volume_window_comparisons": "contract does not fix row anchoring and compatible window matrix for this atomic fixed-candle table",
                    "fixed_or_rolling_rv": "contract defines Q-sequence semantics but not the atomic fixed-candle output naming/placement requested here",
                    "normalized_volume_metrics": "no approved normalization formula/window is specified for this atomic table",
                },
                "qa": qa[resolution],
                "code_version": {"git_commit_at_build": commit, "pipeline_sha256": pipeline_sha},
            }
            atomic_json(temp_dirs[resolution] / "manifest.json", manifest)

        for resolution in RESOLUTIONS:
            final_dirs[resolution].parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_dirs[resolution], final_dirs[resolution])

        report = {
            "status": "PASS",
            "outputs": {
                resolution: {
                    "path": str(final_dirs[resolution]),
                    "rows": outputs[resolution]["rows"],
                    "feature_columns": outputs[resolution]["feature_columns"],
                    "total_columns": outputs[resolution]["total_columns"],
                    "bytes": outputs[resolution]["bytes"],
                }
                for resolution in RESOLUTIONS
            },
            "qa": qa,
            "runtime_seconds": {
                "build": round(build_seconds, 3),
                "validation": round(qa_seconds, 3),
                "total": round(time.perf_counter() - total_started, 3),
            },
        }
        atomic_json(data_root / "manifests/atomic_features_build_report.json", report)
        return report
    except Exception:
        for temp_dir in temp_dirs.values():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def stamp_git_commit(data_root: Path, commit: str) -> None:
    for resolution in RESOLUTIONS:
        manifest_path = data_root / f"features/BTCUSDT/{resolution}_atomic/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["code_version"]["git_commit"] = commit
        atomic_json(manifest_path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp-git-commit")
    args = parser.parse_args()
    if args.stamp_git_commit:
        stamp_git_commit(args.data_root, args.stamp_git_commit)
        print(json.dumps({"stamped_git_commit": args.stamp_git_commit}, indent=2))
        return
    print(json.dumps(build(args.data_root, args.repo_root), indent=2))


if __name__ == "__main__":
    main()
