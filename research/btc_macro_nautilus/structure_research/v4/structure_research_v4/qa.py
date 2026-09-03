from __future__ import annotations

import math

import pandas as pd


def run_qa(outputs: dict[str, pd.DataFrame], feature_dictionary: pd.DataFrame) -> tuple[dict, dict]:
    critical_failures: list[str] = []
    warnings: list[str] = []
    candidates = outputs.get("dynamic_range_candidates_4h_causal.parquet", pd.DataFrame())
    excursions = outputs.get("dynamic_range_excursions_4h.parquet", pd.DataFrame())
    canonical = outputs.get("structure_canonical_legs.csv", pd.DataFrame())
    if canonical["canonical_leg_id"].duplicated().any():
        critical_failures.append("duplicate_canonical_legs")
    if not candidates.empty:
        for column in ["close_path_efficiency"]:
            invalid = candidates[column].dropna()
            if ((invalid < 0.0) | (invalid > 1.0000001)).any():
                critical_failures.append("path_efficiency_out_of_range")
                break
    if not excursions.empty and not excursions[(~excursions["wick_outside"]) & (~excursions["close_outside"])].empty:
        critical_failures.append("inside_rows_in_excursion_table")
    unresolved = feature_dictionary[feature_dictionary["formula_status"] == "unresolved"]
    if not unresolved.empty:
        critical_failures.append("unresolved_mandatory_formula")
    qa = {
        "status": "green" if not critical_failures else "red",
        "critical_failures": critical_failures,
        "warnings": warnings,
    }
    failure_report = {
        "critical_failure_count": len(critical_failures),
        "warning_count": len(warnings),
        "critical_failures": critical_failures,
        "warnings": warnings,
    }
    return qa, failure_report
