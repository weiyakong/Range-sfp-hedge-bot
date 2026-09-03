from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from structure_research_v4.canonical import canonicalize_legs
from structure_research_v4.causal_features import build_rolling_features, compute_path_features
from structure_research_v4.checkpoint import save_partial, write_checkpoint_index
from structure_research_v4.config import BuildConfig, KNOWN_COVERAGE_END
from structure_research_v4.decision_support import build_decision_tables
from structure_research_v4.dynamic_ranges import build_dynamic_range_candidates
from structure_research_v4.events import build_retrospective_events
from structure_research_v4.excursions import build_excursions
from structure_research_v4.fibtime import audit_duplicates, build_fibtime_events
from structure_research_v4.io import ensure_directory, load_table, save_json, save_table
from structure_research_v4.qa import run_qa
from structure_research_v4.relationships import build_parent_reference_tables, compute_previous_relationships
from structure_research_v4.schemas import FEATURE_DICTIONARY_ROWS
from structure_research_v4.source_discovery import (
    SourceDescriptor,
    build_source_discovery_report,
    compute_gap_metrics,
    read_manifest,
    read_schema,
    validate_source_bars,
)


def parse_args() -> BuildConfig:
    parser = argparse.ArgumentParser()
    for arg in [
        "--base-run-dir",
        "--daily-parquet",
        "--daily-merge-summary",
        "--merged-h4-parquet",
        "--spot-h4-parquet",
        "--futures-h4-parquet",
        "--merged-15m-parquet",
        "--spot-15m-parquet",
        "--futures-15m-parquet",
        "--aggtrades-root",
        "--parquet-manifest",
        "--parquet-schema",
        "--output-dir",
        "--mode",
    ]:
        parser.add_argument(arg, required=True)
    parser.add_argument("--resume", action="store_true")
    ns = parser.parse_args()
    return BuildConfig(
        base_run_dir=Path(ns.base_run_dir),
        daily_parquet=Path(ns.daily_parquet),
        daily_merge_summary=Path(ns.daily_merge_summary),
        merged_h4_parquet=Path(ns.merged_h4_parquet),
        spot_h4_parquet=Path(ns.spot_h4_parquet),
        futures_h4_parquet=Path(ns.futures_h4_parquet),
        merged_15m_parquet=Path(ns.merged_15m_parquet),
        spot_15m_parquet=Path(ns.spot_15m_parquet),
        futures_15m_parquet=Path(ns.futures_15m_parquet),
        aggtrades_root=Path(ns.aggtrades_root),
        parquet_manifest=Path(ns.parquet_manifest),
        parquet_schema=Path(ns.parquet_schema),
        output_dir=Path(ns.output_dir),
        mode=ns.mode,
        resume=bool(ns.resume),
    )


def _load_upstream(base_run_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "macro_legs_log20": load_table(base_run_dir / "macro_legs_log20.csv"),
        "movement_segments_log20_fibtime": load_table(base_run_dir / "movement_segments_log20_fibtime.csv"),
        "structural_impulses_log20_fibtime": load_table(base_run_dir / "structural_impulses_log20_fibtime.csv"),
        "corrections_log20_fibtime": load_table(base_run_dir / "corrections_log20_fibtime.csv"),
        "fibtime_events_log20": load_table(base_run_dir / "fibtime_events_log20.csv"),
    }


def _apply_smoke_window(config: BuildConfig, daily: pd.DataFrame, h4: pd.DataFrame, m15: pd.DataFrame, canonical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if config.mode != "smoke":
        return daily, h4, m15, canonical
    h4_smoke = h4.tail(600).copy()
    start = h4_smoke["open_datetime"].min()
    end = h4_smoke["close_datetime"].max()
    daily_smoke = daily[daily["open_datetime"] <= end].tail(120).copy()
    m15_smoke = m15[(m15["open_datetime"] >= start - pd.Timedelta(days=2)) & (m15["open_datetime"] <= end + pd.Timedelta(days=2))].copy()
    canonical_smoke = canonical[
        (canonical["start_time"] <= end)
        & (canonical["end_time"] >= start)
    ].copy()
    return daily_smoke, h4_smoke, m15_smoke, canonical_smoke


def _leg_bars(canonical_legs: pd.DataFrame, bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rows = []
    for leg in canonical_legs.to_dict(orient="records"):
        start = leg["start_time"]
        end = leg["end_time"]
        subset = bars[(bars["open_datetime"] >= start) & (bars["open_datetime"] < end)].copy()
        if subset.empty:
            continue
        subset["canonical_leg_id"] = leg["canonical_leg_id"]
        subset["timeframe"] = timeframe
        rows.append(subset)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _coverage(legs: pd.DataFrame, bars: pd.DataFrame, timeframe: str, market_source: str) -> pd.DataFrame:
    expected_hours = {"1d": 24, "4h": 4, "15m": 0.25}[timeframe]
    rows = []
    for leg in legs.to_dict(orient="records"):
        subset = bars[(bars["open_datetime"] >= leg["start_time"]) & (bars["open_datetime"] < leg["end_time"])].copy()
        expected_rows = max(int((leg["end_time"] - leg["start_time"]).total_seconds() / 3600.0 / expected_hours), 0) if expected_hours else len(subset)
        actual_rows = len(subset)
        gap_count, _ = compute_gap_metrics(subset, max(expected_hours, 1))
        status = "complete" if expected_rows == actual_rows and gap_count == 0 else "gapped" if gap_count else "partial_end" if actual_rows < expected_rows else "complete"
        rows.append(
            {
                "canonical_leg_id": leg["canonical_leg_id"],
                "timeframe": timeframe,
                "coverage_start": subset["open_datetime"].min() if actual_rows else pd.NaT,
                "coverage_end": subset["close_datetime"].max() if actual_rows else pd.NaT,
                "expected_rows": expected_rows,
                "actual_rows": actual_rows,
                "coverage_share": actual_rows / expected_rows if expected_rows else 0.0,
                "gap_count": gap_count,
                "is_partial_start": bool(actual_rows and subset["open_datetime"].min() > leg["start_time"]),
                "is_partial_end": bool(actual_rows and subset["close_datetime"].max() < leg["end_time"]),
                "market_source": market_source,
                "coverage_status": status if actual_rows else "timeframe_unavailable",
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    config = parse_args()
    ensure_directory(config.output_dir)
    upstream = _load_upstream(config.base_run_dir)
    manifest = read_manifest(config.parquet_manifest)
    schema = read_schema(config.parquet_schema)
    descriptors = [
        SourceDescriptor(config.daily_parquet, "1d", "merged", "explicit"),
        SourceDescriptor(config.merged_h4_parquet, "4h", "merged", "explicit"),
        SourceDescriptor(config.spot_h4_parquet, "4h", "spot", "explicit"),
        SourceDescriptor(config.futures_h4_parquet, "4h", "futures", "explicit"),
        SourceDescriptor(config.merged_15m_parquet, "15m", "merged", "explicit"),
        SourceDescriptor(config.spot_15m_parquet, "15m", "spot", "explicit"),
        SourceDescriptor(config.futures_15m_parquet, "15m", "futures", "explicit"),
    ]
    discovery = build_source_discovery_report(manifest, schema, descriptors)
    save_table(discovery, config.output_dir / "source_discovery_report.csv")

    daily, daily_issues = validate_source_bars(load_table(config.daily_parquet))
    h4, h4_issues = validate_source_bars(load_table(config.merged_h4_parquet))
    m15, m15_issues = validate_source_bars(load_table(config.merged_15m_parquet))

    canonical, memberships = canonicalize_legs(
        {
            "macro_legs_log20": upstream["macro_legs_log20"],
            "movement_segments_log20_fibtime": upstream["movement_segments_log20_fibtime"],
        }
    )
    daily, h4, m15, canonical = _apply_smoke_window(config, daily, h4, m15, canonical)
    save_table(canonical, config.output_dir / "structure_canonical_legs.csv")
    save_table(memberships, config.output_dir / "structure_source_memberships.csv")

    market_bars_1d = daily.assign(market_source="merged", source_file=str(config.daily_parquet), source_type="raw_ohlcv", source_symbol="BTCUSDT", source_timeframe="1d", source_start=daily["open_datetime"].min(), source_end=daily["close_datetime"].max(), source_row_count=len(daily))
    market_bars_4h = h4.assign(market_source="merged", source_file=str(config.merged_h4_parquet), source_type="raw_ohlcv", source_symbol="BTCUSDT", source_timeframe="4h", source_start=h4["open_datetime"].min(), source_end=h4["close_datetime"].max(), source_row_count=len(h4))
    market_bars_15m = m15.assign(market_source="merged", source_file=str(config.merged_15m_parquet), source_type="raw_ohlcv", source_symbol="BTCUSDT", source_timeframe="15m", source_start=m15["open_datetime"].min(), source_end=m15["close_datetime"].max(), source_row_count=len(m15))

    rolling = build_rolling_features(market_bars_4h)
    path4h = compute_path_features(market_bars_4h, "4h")
    path15m = compute_path_features(market_bars_15m, "15m")
    rolling = rolling.merge(path4h, on=["available_at_time", "window_size_bars"], how="left")
    candidates = build_dynamic_range_candidates(market_bars_4h, rolling)
    excursions = build_excursions(market_bars_4h, candidates)

    leg_bars_1d = _leg_bars(canonical, market_bars_1d, "1d")
    leg_bars_4h = _leg_bars(canonical, market_bars_4h, "4h")
    leg_bars_15m = _leg_bars(canonical, market_bars_15m, "15m")
    previous = compute_previous_relationships(canonical)
    candidate_table, relationships = build_parent_reference_tables(canonical)
    leg_events = build_retrospective_events(leg_bars_4h, relationships)

    feature_dictionary = pd.DataFrame(FEATURE_DICTIONARY_ROWS)
    save_table(feature_dictionary, config.output_dir / "feature_dictionary.csv")

    raw_fibtime = upstream["fibtime_events_log20"]
    duplicate_audit = audit_duplicates(raw_fibtime)
    fibtime = build_fibtime_events(raw_fibtime, upstream["structural_impulses_log20_fibtime"], pd.Timestamp(KNOWN_COVERAGE_END))

    coverage = pd.concat(
        [
            _coverage(canonical, market_bars_1d, "1d", "merged"),
            _coverage(canonical, market_bars_4h, "4h", "merged"),
            _coverage(canonical, market_bars_15m, "15m", "merged"),
        ],
        ignore_index=True,
    )

    outputs = {
        "market_bars_1d.parquet": market_bars_1d,
        "market_bars_4h.parquet": market_bars_4h,
        "market_bars_15m.parquet": market_bars_15m,
        "market_features_rolling_4h_causal.parquet": rolling,
        "dynamic_range_candidates_4h_causal.parquet": candidates,
        "dynamic_range_excursions_4h.parquet": excursions,
        "structure_leg_bars_1d_retrospective.parquet": leg_bars_1d,
        "structure_leg_bars_4h_retrospective.parquet": leg_bars_4h,
        "structure_leg_bars_15m_retrospective.parquet": leg_bars_15m,
        "structure_leg_features_static.csv": canonical.merge(previous, left_on="canonical_leg_id", right_on="current_leg_id", how="left"),
        "structure_leg_features_rolling_4h_retrospective.parquet": leg_bars_4h,
        "structure_leg_events_retrospective.parquet": leg_events,
        "structure_canonical_legs.csv": canonical,
        "structure_source_memberships.csv": memberships,
        "decision_parent_reference_candidates.csv": candidate_table,
        "structure_leg_relationships.csv": relationships,
        "fibtime_event_duplicate_audit.csv": duplicate_audit,
        "fibtime_events_v4.csv": fibtime,
        "coverage_report.csv": coverage,
    }

    for name, frame in outputs.items():
        save_table(frame, config.output_dir / name)
    decision_tables = build_decision_tables(rolling, candidates, excursions, coverage)
    for name, frame in decision_tables.items():
        save_table(frame, config.output_dir / name)

    qa, failure_report = run_qa(outputs, feature_dictionary)
    qa["invalid_source_bars"] = sorted(set(daily_issues + h4_issues + m15_issues))
    qa["final_status"] = "complete_with_known_coverage_limits"
    save_json(qa, config.output_dir / "structure_research_qa_v4.json")
    save_json(failure_report, config.output_dir / "failure_report.json")

    checkpoint_entries = {
        "config_hash": config.config_hash(),
        "partials": {
            "causal_4h": save_partial(rolling, config.output_dir / "partials/causal_4h/2026-07.parquet"),
            "dynamic_candidates": save_partial(candidates, config.output_dir / "partials/dynamic_candidates/2026-07.parquet"),
            "dynamic_excursions": save_partial(excursions, config.output_dir / "partials/dynamic_excursions/2026-07.parquet"),
            "decision_support": save_partial(decision_tables["decision_window_comparison.csv"], config.output_dir / "partials/decision_support/2026-07.parquet"),
        },
    }
    write_checkpoint_index(checkpoint_entries, config.output_dir / "checkpoint_index.json")
    return 0 if not qa["critical_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
