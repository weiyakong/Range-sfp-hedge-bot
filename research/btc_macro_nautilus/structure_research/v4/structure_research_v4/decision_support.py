from __future__ import annotations

import pandas as pd


def build_decision_register() -> pd.DataFrame:
    questions = [
        ("DEC001", "Which dynamic range method is most stable?", "decision_dynamic_range_candidates.csv"),
        ("DEC002", "How should excursions be thresholded?", "decision_dynamic_range_excursions.csv"),
        ("DEC003", "Which window sizes preserve useful context?", "decision_window_comparison.csv"),
    ]
    rows = []
    for decision_id, question, support_file in questions:
        rows.append(
            {
                "decision_id": decision_id,
                "question": question,
                "status": "open",
                "candidate_methods": "A|B|C",
                "decision_support_file": support_file,
                "required_columns": "",
                "final_choice": "",
                "choice_reason": "",
            }
        )
    return pd.DataFrame(rows)


def build_decision_tables(
    rolling: pd.DataFrame,
    candidates: pd.DataFrame,
    excursions: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    merged = candidates.merge(
        rolling,
        left_on=["candidate_available_at", "window_size_bars"],
        right_on=["available_at_time", "window_size_bars"],
        how="left",
        suffixes=("", "_rolling"),
    )
    coverage_window = coverage[["canonical_leg_id", "coverage_status", "coverage_share"]].copy() if not coverage.empty else pd.DataFrame(columns=["canonical_leg_id", "coverage_status", "coverage_share"])
    return {
        "decision_register.csv": build_decision_register(),
        "decision_parent_reference_candidates.csv": pd.DataFrame(),
        "decision_window_comparison.csv": merged,
        "decision_dynamic_range_candidates.csv": candidates,
        "decision_dynamic_range_excursions.csv": excursions,
        "decision_boundary_alignment.csv": pd.DataFrame(),
        "decision_path_efficiency_comparison.csv": rolling,
        "decision_threshold_research.csv": merged[["range_candidate_id", "method", "window_size_bars"]] if not merged.empty else pd.DataFrame(),
        "decision_coverage_issues.csv": coverage_window,
        "smoke_case_candidates.csv": pd.DataFrame(),
    }
