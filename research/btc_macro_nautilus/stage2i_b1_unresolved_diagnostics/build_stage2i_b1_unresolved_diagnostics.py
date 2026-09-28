"""Stage 2I-B1 Unresolved Diagnostics Builder.

Performs diagnostic analysis of the 1,583 UNRESOLVED pivot events in the canonical
Stage 2I-B1 layered retrospective reference contract. Identifies exact code-level
blocking reasons, required inputs, computability under current semantics, required
methodological decisions, scenario event counts, and downstream reranking impacts.

DOES NOT modify canonical contracts, DOES NOT fill fictional values, and DOES NOT
select solutions for the user.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

STAGE_VERSION = "stage2i-b1-unresolved-diagnostics-v1"
CANONICAL_SPEC_FILE = "PA_STRUCTURE_CANONICAL.md"

# 19 Canonical Fields across 4 Layers
CANONICAL_FIELDS: List[Tuple[str, str, str]] = [
    # (canonical_layer, canonical_field, default_current_status)
    ("Layer 1 — Structural Components", "reference__prominence_min_log", "None"),
    ("Layer 1 — Structural Components", "reference__prominence_geo_log", "None"),
    ("Layer 1 — Structural Components", "reference__prominence_balance", "None"),
    ("Layer 1 — Structural Components", "reference__prominence_vol_norm", "None"),
    ("Layer 1 — Structural Components", "reference__hierarchy_min_scale", "None"),
    ("Layer 1 — Structural Components", "reference__hierarchy_geo_scale", "None"),
    ("Layer 2 — Continuous Ordering", "reference__rank_prominence_min", "None"),
    ("Layer 2 — Continuous Ordering", "reference__rank_hierarchy_min", "None"),
    ("Layer 2 — Continuous Ordering", "reference__rank_consensus_mean", "None"),
    ("Layer 2 — Continuous Ordering", "reference__rank_consensus_median", "None"),
    ("Layer 3 — Structural Survival Scale", "reference__ord_survival_scale", "None"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_unanimous_t10", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_majority_t10", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_unanimous_t20", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_majority_t20", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_unanimous_t25", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_majority_t25", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_unanimous_t30", "UNRESOLVED"),
    ("Layer 4 — Cross-View Agreement States", "reference__conf_majority_t30", "UNRESOLVED"),
]


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def write_deterministic_parquet(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty Parquet artifact: {path}")
    columns = sorted({column for row in rows for column in row})
    normalized = [{column: row.get(column) for column in columns} for row in rows]
    table = pa.Table.from_pylist(normalized)
    temporary = path.with_name(f"{path.name}.incomplete")
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, temporary, compression="snappy")
    temporary.replace(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    columns = [
        "unresolved_group",
        "event_count",
        "canonical_layer",
        "canonical_field",
        "current_status",
        "exact_blocking_reason",
        "required_inputs",
        "computable_under_current_contract",
        "methodological_decision_required",
        "decision_description",
        "would_change_existing_resolved_values",
        "notes",
    ]
    # Include any extra keys if present
    extra = sorted({k for r in rows for k in r.keys() if k not in columns})
    fieldnames = columns + extra
    temp = path.with_name(f"{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    temp.replace(path)


def get_git_info(repo_root: Path) -> Tuple[str, bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True)
    return commit, bool(status.strip())


def build_diagnostics_records() -> List[Dict[str, Any]]:
    """Builds the 76 canonical group diagnostics records (4 groups x 19 fields)."""
    records: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. dual_unordered (N = 300)
    # -------------------------------------------------------------------------
    group = "dual_unordered"
    count = 300
    for layer, field, status in CANONICAL_FIELDS:
        if "prominence" in field:
            if field == "reference__prominence_vol_norm":
                reason = "Prominence numerator is None due to lack of alternating temporal neighbors; TR-42 volatility scale is available for 298/300 events but unnormalized."
                inputs = "Two-sided prominence (missing) and local TR-42 volatility scale (available for 298/300)."
            else:
                reason = "Dual HIGH and LOW share identical 4H bar; intrabar execution order is unobserved on 4H candles. Excluded from alternating sequence and serves as segment barrier."
                inputs = "Ordered left and right alternating neighbors with positive bar distance."
            computable = False
            decision_req = True
            decision_desc = "Must choose between: (a) lower-timeframe intrabar sequencing, (b) joint dual-box / interval prominence, or (c) retaining as permanently unresolved."
            affects_resolved = "YES if lower-timeframe ordering merges segments and alters existing hierarchy; NO if treated as auxiliary non-sequence object."
            notes = "Intra-candle log range log(high/low) is well-defined (median 2.62%, span 0.42%-20.62%) and invariant to order, but is not a canonical 2-sided prominence."

        elif "hierarchy" in field:
            reason = "Dual candles partition timeline into isolated segments and are excluded from alternating sequences; never enter iterative segment hierarchy."
            inputs = "Membership in alternating sequence entering hierarchical_simplification_segment."
            computable = False
            decision_req = True
            decision_desc = "Requires defining hierarchical simplification over unordered dual nodes or resolving intrabar order to integrate into sequence."
            affects_resolved = "YES if sequence integration alters segment boundaries or hierarchy removal order of existing 2,867 events."
            notes = "Cannot participate in segment hierarchy without order resolution."

        elif "rank" in field:
            reason = "Underlying Layer 1 continuous metric (prominence or hierarchy scale) is None."
            inputs = "Valid Layer 1 continuous metric and empirical reference ranking distribution."
            computable = False
            decision_req = True
            decision_desc = "Requires computing underlying Layer 1 quantity, plus deciding whether to rerank existing population (in-sample) or project against frozen reference."
            affects_resolved = "YES if added to ranking denominator (changes percentile ranks of 2,867 events); NO only if evaluated against frozen distribution."
            notes = "Reranking existing 2,867 events mathematically shifts percentile ranks whenever denominator increases."

        elif "survival" in field:
            reason = "hierarchy_min_scale is None; survival tier counts thresholds reached in minimum hierarchy."
            inputs = "Valid reference__hierarchy_min_scale."
            computable = False
            decision_req = True
            decision_desc = "Requires hierarchical simplification scale for dual events."
            affects_resolved = "YES if hierarchy is restructured."
            notes = "Survival scale requires hierarchical simplification context."

        elif "conf" in field:
            reason = "Constituent retrospective view ranks (prominence, hierarchy, vol-norm) are None; agreement voting requires 3 valid views."
            inputs = "rank_prominence_min, rank_hierarchy_min, rank_prominence_vol."
            computable = False
            decision_req = True
            decision_desc = "Requires all 3 constituent ranks, or an explicit revision of voting rules to allow partial input voting."
            affects_resolved = "NO to existing event classifications unless ranking distribution changes."
            notes = "Current voting contract strictly requires all 3 view ranks."

        records.append({
            "unresolved_group": group,
            "event_count": count,
            "canonical_layer": layer,
            "canonical_field": field,
            "current_status": status,
            "exact_blocking_reason": reason,
            "required_inputs": inputs,
            "computable_under_current_contract": computable,
            "methodological_decision_required": decision_req,
            "decision_description": decision_desc,
            "would_change_existing_resolved_values": affects_resolved,
            "notes": notes,
        })

    # -------------------------------------------------------------------------
    # 2. technical_same_type_exclusion (N = 865)
    # -------------------------------------------------------------------------
    group = "technical_same_type_exclusion"
    count = 865
    for layer, field, status in CANONICAL_FIELDS:
        if "prominence" in field:
            if field == "reference__prominence_vol_norm":
                reason = "Prominence numerator is None because pivot was excluded from alternating sequence; TR-42 volatility scale is available for 865/865 events."
                inputs = "Two-sided prominence (missing) and local TR-42 volatility scale (available for all 865)."
            else:
                reason = "Excluded by same-type prepass before alternating sequence construction. Raw immediate neighbors are same-type pivots, so alternating excursion is undefined."
                inputs = "Opposite-type left and right alternating neighbors."
            computable = False
            decision_req = True
            decision_desc = "Must choose between: (Option B1) adverse excursion relative to winning sibling, (Option B2) inheriting bracketed alternating neighbors from winning sibling, or (Option B3) full non-alternating hierarchy."
            affects_resolved = "NO for Option B1/B2 (evaluates excluded pivot against existing cluster/context); YES for Option B3 (abolishing prepass alters existing 2,867 hierarchy)."
            notes = "Under fixed B+C policy, technical exclusion does NOT mean micro or scale=0; audit proved median adverse departure is 2.18%."

        elif "hierarchy" in field:
            reason = "Pivot is not in segment_alternating; only alternating candidates enter segment hierarchical simplification."
            inputs = "Participation in alternating sequence undergoing hierarchical simplification."
            computable = False
            decision_req = True
            decision_desc = "Requires either DAG/tree hierarchy encompassing same-type clusters or assigning a surrogate removal scale."
            affects_resolved = "YES if altering the simplification sequence of the alternating chain."
            notes = "Hierarchy simplification strictly assumes an alternating chain of extrema."

        elif "rank" in field:
            reason = "Underlying Layer 1 continuous metrics are None."
            inputs = "Valid Layer 1 continuous metric."
            computable = False
            decision_req = True
            decision_desc = "Requires computing underlying metric and choosing ranking policy (in-sample expansion from 2,867 to 3,732 vs frozen reference ranking)."
            affects_resolved = "YES if added to empirical ranking denominator (shifts percentile ranks of 2,867 events); NO if evaluated against frozen distribution."
            notes = "Denominator expansion (2,867 -> 3,732) mathematically alters all existing resolved ranks."

        elif "survival" in field:
            reason = "hierarchy_min_scale is None."
            inputs = "Valid reference__hierarchy_min_scale."
            computable = False
            decision_req = True
            decision_desc = "Requires defining hierarchical survival for same-type clusters."
            affects_resolved = "YES if hierarchy is restructured."
            notes = "Survival scale is tied to hierarchy iterations."

        elif "conf" in field:
            reason = "Constituent retrospective view ranks are None."
            inputs = "All 3 constituent retrospective view ranks."
            computable = False
            decision_req = True
            decision_desc = "Requires constituent ranks and voting policy."
            affects_resolved = "NO unless ranking distribution changes."
            notes = "Strict 3-view voting rule cannot execute on None inputs."

        records.append({
            "unresolved_group": group,
            "event_count": count,
            "canonical_layer": layer,
            "canonical_field": field,
            "current_status": status,
            "exact_blocking_reason": reason,
            "required_inputs": inputs,
            "computable_under_current_contract": computable,
            "methodological_decision_required": decision_req,
            "decision_description": decision_desc,
            "would_change_existing_resolved_values": affects_resolved,
            "notes": notes,
        })

    # -------------------------------------------------------------------------
    # 3. dual_separator_boundary (N = 416)
    # -------------------------------------------------------------------------
    group = "dual_separator_boundary"
    count = 416
    for layer, field, status in CANONICAL_FIELDS:
        if "prominence" in field:
            reason = "Split subgroup behavior: 283 segment endpoints lack left or right neighbor (bounded by dual candle); 133 interior hierarchy survivors HAVE both neighbors and prominence was computed internally, but gated out in output because boundary_ids included all hierarchy survivors."
            inputs = "Left and right alternating neighbors in segment (available for 133 interior survivors; 1 neighbor missing for 283 endpoints)."
            computable = False
            decision_req = True
            decision_desc = "For 133 interior survivors: decide whether to decouple prominence output from hierarchy removal status (exposing valid two-sided prominence). For 283 endpoints: decide whether to define one-sided excursion or leave uncomputed."
            affects_resolved = "NO (does not alter any existing resolved values or segment geometry)."
            notes = "CRITICAL FINDING: 133 interior DSB events already have mathematically valid two-sided prominence in pipeline memory; only 283 endpoints lack geometric neighbors."

        elif "hierarchy" in field:
            reason = "Both segment endpoints (283) and interior hierarchy survivors (133) survive simplification down to the last 2 events in their segment; hierarchical simplification assigns scale=None (boundary_survivor=True)."
            inputs = "Interior removal by lower-cost excursion within segment."
            computable = False
            decision_req = True
            decision_desc = "Requires choosing whether to: (a) simplify across dual barriers into adjacent segments, (b) assign a censored/bounded survival scale, or (c) accept scale=None as the valid survivor state."
            affects_resolved = "YES if simplifying across dual barriers (changes segment partition); NO if using censored/bounded representation."
            notes = "Boundary survivors are never removed; their removal cost is undefined within isolated segments."

        elif "rank" in field:
            if "prominence" in field:
                reason = "Prominence rank is blocked because prominence was gated out; for 133 interior survivors, prominence exists and could be ranked if exposed."
                inputs = "Valid prominence_min_log."
                computable = False
                decision_req = True
                decision_desc = "Requires exposing prominence for 133 interior survivors and selecting ranking policy (frozen vs in-sample)."
                affects_resolved = "YES if added to ranking denominator; NO if projected against frozen 2,867 distribution."
                notes = "Only applicable to 133 interior survivors; 283 endpoints remain without two-sided prominence."
            else:
                reason = "hierarchy_min_scale is None for all 416 events (all are boundary survivors); consensus rank is blocked by missing constituent."
                inputs = "hierarchy_min_scale and constituent ranks."
                computable = False
                decision_req = True
                decision_desc = "Requires solving hierarchy scale for boundary survivors."
                affects_resolved = "YES if denominator changes."
                notes = "Consensus mean and median require all 3 ranks under current contract."

        elif "survival" in field:
            reason = "hierarchy_min_scale is None for all 416 boundary survivors. Assigning Tier 10 would falsely claim survival up to 25% for events in short segments with small total excursion."
            inputs = "Finite hierarchy_min_scale."
            computable = False
            decision_req = True
            decision_desc = "Requires defining censored survival scale for boundary survivors."
            affects_resolved = "NO if right-censored tier is introduced."
            notes = "Survival cannot be evaluated beyond segment boundaries without bridging across dual candles."

        elif "conf" in field:
            reason = "Constituent retrospective view ranks are incomplete."
            inputs = "All 3 constituent retrospective view ranks."
            computable = False
            decision_req = True
            decision_desc = "Requires complete constituent ranks or revised partial voting rule."
            affects_resolved = "NO unless ranking distribution changes."
            notes = "Current voting rules require all 3 views."

        records.append({
            "unresolved_group": group,
            "event_count": count,
            "canonical_layer": layer,
            "canonical_field": field,
            "current_status": status,
            "exact_blocking_reason": reason,
            "required_inputs": inputs,
            "computable_under_current_contract": computable,
            "methodological_decision_required": decision_req,
            "decision_description": decision_desc,
            "would_change_existing_resolved_values": affects_resolved,
            "notes": notes,
        })

    # -------------------------------------------------------------------------
    # 4. dataset_edge_censored (N = 2)
    # -------------------------------------------------------------------------
    group = "dataset_edge_censored"
    count = 2
    for layer, field, status in CANONICAL_FIELDS:
        if "prominence" in field:
            reason = "P4H_000006_HIGH (bar 6) lacks preceding 4H history (start of dataset; also lacks TR-42 lookback); P4H_015442_LOW (bar 15442) lacks subsequent 4H history (end of dataset). Excursion path is truncated by dataset boundary."
            inputs = "Preceding 4H candles for left edge; succeeding 4H candles for right edge."
            computable = False
            decision_req = True
            decision_desc = "Can be resolved only by expanding the historical dataset coverage (adding pre-2019 data for left edge; appending post-2026 data for right edge) or defining one-sided boundary estimators."
            affects_resolved = "NO to existing interior resolved events."
            notes = "Fundamental boundary censoring. Cannot be resolved by algorithmic redefinition within the fixed 15,445-bar dataset."

        elif "hierarchy" in field:
            reason = "Segment endpoints at dataset boundaries (pos 0 of segment 0; pos 7 of segment 144); preserved as permanent boundary survivors in hierarchy."
            inputs = "External adjacent segments and continuous candle history beyond dataset edges."
            computable = False
            decision_req = True
            decision_desc = "Requires expanded dataset coverage."
            affects_resolved = "NO."
            notes = "Boundary survivors by mathematical construction."

        elif "rank" in field:
            reason = "Underlying Layer 1 metrics are None due to dataset boundary censoring."
            inputs = "Valid Layer 1 metrics."
            computable = False
            decision_req = True
            decision_desc = "Requires resolving Layer 1 via dataset expansion."
            affects_resolved = "Negligible (N=2 relative to 2,867)."
            notes = "Edge pivots."

        elif "survival" in field:
            reason = "hierarchy_min_scale is None (boundary survivors)."
            inputs = "Finite hierarchy_min_scale."
            computable = False
            decision_req = True
            decision_desc = "Requires expanded dataset coverage."
            affects_resolved = "NO."
            notes = "Dataset edge survivors."

        elif "conf" in field:
            reason = "Constituent view ranks are None."
            inputs = "All 3 constituent view ranks."
            computable = False
            decision_req = True
            decision_desc = "Requires expanded dataset coverage."
            affects_resolved = "NO."
            notes = "Unresolved due to boundary censoring."

        records.append({
            "unresolved_group": group,
            "event_count": count,
            "canonical_layer": layer,
            "canonical_field": field,
            "current_status": status,
            "exact_blocking_reason": reason,
            "required_inputs": inputs,
            "computable_under_current_contract": computable,
            "methodological_decision_required": decision_req,
            "decision_description": decision_desc,
            "would_change_existing_resolved_values": affects_resolved,
            "notes": notes,
        })

    return records


def build_subgroup_diagnostics_records() -> List[Dict[str, Any]]:
    """Builds fine-grained subgroup diagnostics (6 subgroups x 19 fields = 114 rows).

    Subgroups:
      1. dual_unordered (N=300)
      2. technical_same_type_exclusion (N=865)
      3. dual_separator_boundary_endpoint (N=283)
      4. dual_separator_boundary_interior_survivor (N=133)
      5. dataset_left_edge_censored (N=1)
      6. dataset_right_edge_censored (N=1)
      Total = 300 + 865 + 283 + 133 + 1 + 1 = 1,583.
    """
    records: List[Dict[str, Any]] = []
    subgroups = [
        ("dual_unordered", 300, "dual_unordered"),
        ("technical_same_type_exclusion", 865, "technical_same_type_exclusion"),
        ("dual_separator_boundary_endpoint", 283, "dual_separator_boundary"),
        ("dual_separator_boundary_interior_survivor", 133, "dual_separator_boundary"),
        ("dataset_left_edge_censored", 1, "dataset_edge_censored"),
        ("dataset_right_edge_censored", 1, "dataset_edge_censored"),
    ]

    for sg_name, sg_count, parent_group in subgroups:
        for layer, field, status in CANONICAL_FIELDS:
            # Tailor description to subgroup
            if sg_name == "dual_separator_boundary_interior_survivor":
                if "prominence" in field:
                    reason = "Two-sided prominence WAS calculated internally during pipeline execution (both left and right alternating neighbors exist in segment); masked out to None only because the output builder gated on interior_resolved_ids which excluded all hierarchy survivors."
                    inputs = "Left and right alternating neighbors in segment (ALREADY AVAILABLE)."
                    computable = False  # under current published contract definition
                    decision_req = True
                    decision_desc = "Decouple prominence availability from hierarchy removal resolution in canonical table output."
                    affects_resolved = "NO (purely exposes already-computed geometric values for 133 events)."
                    notes = "133 events have valid prominence min, geo, balance, and vol-norm."
                elif "hierarchy" in field:
                    reason = "Survived hierarchical simplification to the end of segment; was never removed by interior excursion (scale=None, boundary_survivor=True)."
                    inputs = "Iterative simplification removal cost within segment."
                    computable = False
                    decision_req = True
                    decision_desc = "Requires cross-segment hierarchy bridging or censored survival scale representation."
                    affects_resolved = "YES if cross-barrier hierarchy; NO if censored representation."
                    notes = "Removal cost undefined within isolated segment."
                elif field == "reference__rank_prominence_min":
                    reason = "Blocked because prominence_min_log was masked out; could be computed if prominence is exposed."
                    inputs = "reference__prominence_min_log."
                    computable = False
                    decision_req = True
                    decision_desc = "Decide ranking policy: in-sample rerank vs frozen reference projection."
                    affects_resolved = "YES if in-sample rerank; NO if frozen reference projection."
                    notes = "Recoverable if prominence is decoupled."
                else:
                    reason = "Blocked by missing hierarchy scale or incomplete constituent views."
                    inputs = "hierarchy_min_scale and complete view ranks."
                    computable = False
                    decision_req = True
                    decision_desc = "Requires hierarchy scale solution."
                    affects_resolved = "Depends on hierarchy policy."
                    notes = "Consensus and agreement require complete constituent views."

            elif sg_name == "dual_separator_boundary_endpoint":
                if "prominence" in field:
                    reason = "Segment endpoint adjacent to dual candle separator. Exactly one alternating neighbor is missing within the segment (139 left-only lack left neighbor; 139 right-only lack right neighbor; 5 singletons lack both)."
                    inputs = "Two-sided alternating neighbors within segment (one or both missing)."
                    computable = False
                    decision_req = True
                    decision_desc = "Requires defining one-sided excursion metric or bridging across dual candle barrier."
                    affects_resolved = "NO for one-sided; YES for cross-barrier bridging."
                    notes = "283 events truly lack two-sided segment neighbors."
                else:
                    reason = "Segment endpoint never removed in hierarchy (boundary_survivor=True, scale=None); downstream ranks and agreement states blocked."
                    inputs = "Finite removal scale and constituent view ranks."
                    computable = False
                    decision_req = True
                    decision_desc = "Requires one-sided methodology or cross-barrier hierarchy."
                    affects_resolved = "Depends on cross-barrier choices."
                    notes = "Initial segment boundaries."

            elif sg_name == "dataset_left_edge_censored":
                reason = "Pivot P4H_000006_HIGH (bar index 6) at beginning of historical dataset; no preceding 4H history exists; lookback is insufficient for TR-42 median true range (requires >= 10 bars)."
                inputs = "Preceding 4H candles prior to 2019-09-08."
                computable = False
                decision_req = True
                decision_desc = "Resolve by adding pre-2019 historical 4H candle data."
                affects_resolved = "NO."
                notes = "True historical left-censoring."

            elif sg_name == "dataset_right_edge_censored":
                reason = "Pivot P4H_015442_LOW (bar index 15442) at end of dataset; no subsequent 4H history exists; right excursion is unobserved."
                inputs = "Subsequent 4H candles after 2026-09-03."
                computable = False
                decision_req = True
                decision_desc = "Resolve by appending subsequent 4H candle data as new bars form."
                affects_resolved = "NO."
                notes = "True future right-censoring; volatility scale is available (840.25 USDT)."

            else:
                # dual_unordered and technical_same_type_exclusion match parent
                reason = f"Blocked by {parent_group} structural constraints."
                inputs = "Required canonical inputs."
                computable = False
                decision_req = True
                decision_desc = f"Methodological decision required for {parent_group}."
                affects_resolved = "Depends on methodology."
                notes = f"Subgroup {sg_name}."

            records.append({
                "subgroup_name": sg_name,
                "unresolved_group": parent_group,
                "event_count": sg_count,
                "canonical_layer": layer,
                "canonical_field": field,
                "current_status": status,
                "exact_blocking_reason": reason,
                "required_inputs": inputs,
                "computable_under_current_contract": computable,
                "methodological_decision_required": decision_req,
                "decision_description": decision_desc,
                "would_change_existing_resolved_values": affects_resolved,
                "notes": notes,
            })

    return records


def run_pipeline(
    data_root: Path,
    repo_root: Path,
    output_dir: Path,
    mode: str = "production",
) -> Mapping[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    b1_dir = data_root / "research" / "stage2i_b1_reference_contract_comparison"
    canonical_spec = repo_root / "docs" / "research" / "pa_structure" / CANONICAL_SPEC_FILE

    if not b1_dir.exists():
        raise FileNotFoundError(f"Missing B1 comparison artifact directory: {b1_dir}")
    if not canonical_spec.exists():
        raise FileNotFoundError(f"Missing canonical spec file: {canonical_spec}")

    # 1. Verify inputs
    master_table = pq.read_table(b1_dir / "master_event_reference.parquet")
    bplusc_table = pq.read_table(b1_dir / "bplusc_sequence_reference.parquet")
    master_rows = master_table.to_pylist()
    bplusc_rows = bplusc_table.to_pylist()
    bplusc_by_id = {r["event_id"]: r for r in bplusc_rows}

    # Population accounting
    total_master = len(master_rows)
    resolved_rows = [r for r in master_rows if r["representation_resolved"]]
    unresolved_rows = [r for r in master_rows if not r["representation_resolved"]]
    resolved_count = len(resolved_rows)
    unresolved_count = len(unresolved_rows)

    if total_master != 4450 or resolved_count != 2867 or unresolved_count != 1583:
        raise ValueError(
            f"Population mismatch: total={total_master} (exp 4450), "
            f"resolved={resolved_count} (exp 2867), unresolved={unresolved_count} (exp 1583)"
        )

    # Category counts
    duals = [r for r in unresolved_rows if r["special_state"] == "dual_unordered"]
    same_type = [r for r in unresolved_rows if r["special_state"] == "technical_same_type_exclusion"]
    dsb = [r for r in unresolved_rows if r["special_state"] == "dual_separator_boundary"]
    left_edges = [r for r in unresolved_rows if r["special_state"] == "dataset_left_edge_censored"]
    right_edges = [r for r in unresolved_rows if r["special_state"] == "dataset_right_edge_censored"]
    dataset_edges = left_edges + right_edges

    count_dual = len(duals)
    count_same_type = len(same_type)
    count_dsb = len(dsb)
    count_edges = len(dataset_edges)

    if count_dual != 300 or count_same_type != 865 or count_dsb != 416 or count_edges != 2:
        raise ValueError(
            f"Category count mismatch: dual={count_dual} (exp 300), same_type={count_same_type} (exp 865), "
            f"dsb={count_dsb} (exp 416), edges={count_edges} (exp 2)"
        )

    # Subgroup breakdown for DSB
    dsb_interior = [
        r for r in dsb
        if r["event_id"] in bplusc_by_id
        and not bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
        and not bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
    ]
    dsb_endpoints = [
        r for r in dsb
        if r["event_id"] in bplusc_by_id
        and (
            bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
            or bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
        )
    ]
    dsb_left_only = [
        r for r in dsb_endpoints
        if bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
        and not bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
    ]
    dsb_right_only = [
        r for r in dsb_endpoints
        if not bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
        and bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
    ]
    dsb_singletons = [
        r for r in dsb_endpoints
        if bplusc_by_id[r["event_id"]]["is_segment_left_boundary"]
        and bplusc_by_id[r["event_id"]]["is_segment_right_boundary"]
    ]

    count_dsb_interior = len(dsb_interior)
    count_dsb_endpoints = len(dsb_endpoints)
    count_dsb_left_only = len(dsb_left_only)
    count_dsb_right_only = len(dsb_right_only)
    count_dsb_singletons = len(dsb_singletons)

    if count_dsb_interior != 133 or count_dsb_endpoints != 283:
        raise ValueError(
            f"DSB sub-breakdown mismatch: interior={count_dsb_interior} (exp 133), endpoints={count_dsb_endpoints} (exp 283)"
        )

    # 2. Build diagnostics tables
    group_records = build_diagnostics_records()
    subgroup_records = build_subgroup_diagnostics_records()

    # 3. Write artifacts
    group_csv_path = output_dir / "unresolved_group_diagnostics.csv"
    group_parquet_path = output_dir / "unresolved_group_diagnostics.parquet"
    subgroup_csv_path = output_dir / "unresolved_subgroup_diagnostics.csv"
    subgroup_parquet_path = output_dir / "unresolved_subgroup_diagnostics.parquet"

    write_csv(group_csv_path, group_records)
    write_deterministic_parquet(group_parquet_path, group_records)
    write_csv(subgroup_csv_path, subgroup_records)
    write_deterministic_parquet(subgroup_parquet_path, subgroup_records)

    # 4. Git info & input checksums
    git_commit, git_dirty = get_git_info(repo_root)
    input_files = [
        b1_dir / "master_event_reference.parquet",
        b1_dir / "bplusc_sequence_reference.parquet",
        b1_dir / "reference_continuous.parquet",
        b1_dir / "reference_ordinal.parquet",
        b1_dir / "reference_confidence.parquet",
        canonical_spec,
    ]
    input_manifest = [{"path": str(p), "sha256": sha256(p)} for p in input_files]

    # Output manifest
    output_files = [
        group_csv_path,
        group_parquet_path,
        subgroup_csv_path,
        subgroup_parquet_path,
    ]

    # 5. Summary metrics
    summary_data: Dict[str, Any] = {
        "stage": STAGE_VERSION,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "master_population": total_master,
        "resolved_population": resolved_count,
        "unresolved_population": unresolved_count,
        "unresolved_category_counts": {
            "dual_unordered": count_dual,
            "technical_same_type_exclusion": count_same_type,
            "dual_separator_boundary": count_dsb,
            "dataset_edge_censored": count_edges,
        },
        "unresolved_subgroup_counts": {
            "dual_unordered": count_dual,
            "technical_same_type_exclusion": count_same_type,
            "dual_separator_boundary_interior_survivor": count_dsb_interior,
            "dual_separator_boundary_endpoint_total": count_dsb_endpoints,
            "dual_separator_boundary_endpoint_left_only": count_dsb_left_only,
            "dual_separator_boundary_endpoint_right_only": count_dsb_right_only,
            "dual_separator_boundary_endpoint_singleton": count_dsb_singletons,
            "dataset_left_edge_censored": len(left_edges),
            "dataset_right_edge_censored": len(right_edges),
        },
        "scenario_counts": {
            "scenario_0_strict_current_contract": {
                "description": "Zero methodological changes; strict current contract preserved.",
                "layer1_at_least_one_field": 0,
                "layer1_full": 0,
                "layer2_full": 0,
                "layer3_full": 0,
                "layer4_full": 0,
                "completely_unresolved": 1583,
                "affects_existing_2867": "NO",
            },
            "scenario_1_decouple_interior_dsb_prominence": {
                "description": "Decouple prominence availability from hierarchy removal resolution for 133 interior segment survivors.",
                "layer1_at_least_one_field": 133,
                "layer1_full": 0,
                "layer2_prominence_rank_only_frozen": 133,
                "layer2_full_consensus": 0,
                "layer3_full": 0,
                "layer4_full": 0,
                "completely_unresolved": 1450,
                "affects_existing_2867": "NO (if frozen reference ranking is used)",
            },
            "scenario_2_bracketed_prominence_same_type": {
                "description": "Inherit cluster-bracketed alternating neighbors for 865 same-type exclusions (combined with Scenario 1).",
                "layer1_at_least_one_field": 998,
                "layer1_full": 0,
                "layer2_prominence_rank_only_frozen": 998,
                "layer2_full_consensus": 0,
                "layer3_full": 0,
                "layer4_full": 0,
                "completely_unresolved": 585,
                "affects_existing_2867": "NO (if frozen reference ranking is used)",
            },
            "scenario_3_one_sided_excursion_endpoints": {
                "description": "Introduce one-sided excursion for 280 endpoints/edges with exactly 1 alternating neighbor.",
                "layer1_at_least_one_field_non_canonical": 280,
                "completely_unresolved_dual_and_singletons": 305,
                "affects_existing_2867": "NO (if kept as separate one-sided namespace)",
            },
            "scenario_4_lower_timeframe_dual_sequencing": {
                "description": "Use lower-timeframe candles (1m/5m/1h) to resolve intrabar order for 300 dual events.",
                "potential_sequence_integration": 300,
                "affects_existing_2867": "YES (eliminates dual barriers, merges segments, changes hierarchy and ranks of 2,867 events)",
            },
            "scenario_5_full_non_alternating_hierarchy": {
                "description": "Abolish same-type prepass and execute hierarchical simplification on all 4,150 non-dual events directly.",
                "potential_hierarchy_integration": 1148,
                "affects_existing_2867": "YES (fundamentally alters existing 2,867 hierarchy iterations and ranks)",
            },
        },
        "recovery_matrix_summary": {
            "dual_unordered": {
                "count": 300,
                "layer1_recoverable": "NO",
                "layer2_recoverable": "NO",
                "layer3_recoverable": "NO",
                "layer4_recoverable": "NO",
                "needs_new_methodology": "YES",
                "would_affect_existing_2867": "OPEN",
            },
            "technical_same_type_exclusion": {
                "count": 865,
                "layer1_recoverable": "PARTIAL",
                "layer2_recoverable": "PARTIAL",
                "layer3_recoverable": "NO",
                "layer4_recoverable": "NO",
                "needs_new_methodology": "YES",
                "would_affect_existing_2867": "OPEN",
            },
            "dual_separator_boundary": {
                "count": 416,
                "layer1_recoverable": "PARTIAL",
                "layer2_recoverable": "PARTIAL",
                "layer3_recoverable": "NO",
                "layer4_recoverable": "NO",
                "needs_new_methodology": "YES",
                "would_affect_existing_2867": "OPEN",
            },
            "dataset_edge_censored": {
                "count": 2,
                "layer1_recoverable": "NO",
                "layer2_recoverable": "NO",
                "layer3_recoverable": "NO",
                "layer4_recoverable": "NO",
                "needs_new_methodology": "YES",
                "would_affect_existing_2867": "NO",
            },
        },
    }

    summary_path = output_dir / "summary.json"
    atomic_json(summary_path, summary_data)
    output_files.append(summary_path)

    # 6. Checksums and manifest
    checksum_lines: List[str] = []
    output_manifest: List[Dict[str, str]] = []
    for out_p in output_files:
        c_hash = sha256(out_p)
        checksum_lines.append(f"{c_hash}  {out_p.name}\n")
        output_manifest.append({"path": str(out_p), "sha256": c_hash})

    checksums_path = output_dir / "checksums.sha256"
    atomic_text(checksums_path, "".join(checksum_lines))

    manifest_data = {
        "stage": STAGE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "input_files": input_manifest,
        "output_files": output_manifest,
    }
    manifest_path = output_dir / "manifest.json"
    atomic_json(manifest_path, manifest_data)

    print(f"=== Stage 2I-B1 Unresolved Diagnostics Built Successfully ===")
    print(f"Output directory: {output_dir}")
    print(f"Total unresolved events: {unresolved_count}")
    print(f"  - dual_unordered: {count_dual}")
    print(f"  - technical_same_type_exclusion: {count_same_type}")
    print(f"  - dual_separator_boundary: {count_dsb} (interior survivors: {count_dsb_interior}, endpoints: {count_dsb_endpoints})")
    print(f"  - dataset_edge_censored: {count_edges}")
    print(f"Diagnostic rows generated: {len(group_records)} (groups x fields) + {len(subgroup_records)} (subgroups x fields)")

    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage 2I-B1 Unresolved Diagnostics")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data"),
        help="Path to authoritative data root",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/Users/yeshevika/Documents/Codex/2026-09-27/range-sfp-pa-structure"),
        help="Path to authoritative repository worktree root",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to output artifact directory",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="production",
        choices=["production", "smoke"],
        help="Pipeline execution mode",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (args.data_root / "research" / "stage2i_b1_unresolved_diagnostics")
    run_pipeline(
        data_root=args.data_root,
        repo_root=args.repo_root,
        output_dir=output_dir,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
