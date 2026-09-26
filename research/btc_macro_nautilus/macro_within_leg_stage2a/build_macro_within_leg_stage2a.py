#!/usr/bin/env python3
"""Label-free within-leg 4H change-point discovery for approved macro legs.

This deliberately does not assign state names or compare/cluster subsegments
across legs.  It consumes only validated 4H atomic features and approved
whole-candle interior bounds already materialized in macro segment aggregates.
"""
from __future__ import annotations

import argparse
import csv
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
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SEED = 20260926
SCHEMA_VERSION = "macro-within-leg-stage2a-v1"
FAMILIES = ("overlap_body_overlap", "directional_persistence_alternation", "speed_movement_rate", "candle_geometry", "volatility_volume_activity")
SIGNED = {"signed_price_change", "signed_close_return", "signed_return_pct", "signed_log_move", "raw_signed_speed_pct_per_hour", "signed_log_speed_per_hour", "close_step_sign"}
TECHNICAL = {"timestamp", "end_time", "resolution", "market", "instrument", "source_complete", "source_constituent_count", "source_expected_constituent_count", "previous_timestamp", "pair_eligible", "pair_ineligibility_reason", "open", "high", "low", "close", "body_high", "body_low", "duration_hours", "local_direction"}
CONFIG = {"seed": SEED, "coverage_minimum": 0.80, "near_duplicate_abs_correlation": 0.999999, "high_redundancy_abs_correlation": 0.98, "min_feature_count": 2, "sensitivity_min_lengths": [3, 4, 5], "sensitivity_penalties": [8.0, 10.0, 12.0], "primary_min_length": 4, "primary_penalty": 10.0, "strong_boundary_support": 0.60}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True, default=str)
        f.write("\n")
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({k for row in rows for k in row}) if rows else ["status"]
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    if rows:
        pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd", compression_level=9)


def family(name: str) -> str | None:
    if any(x in name for x in ("overlap", "penetration", "extension")):
        return "overlap_body_overlap"
    if name in {"alternation_indicator", "close_step_sign", "volume_body_up", "volume_body_down", "volume_body_flat", "volume_close_step_up", "volume_close_step_down", "volume_close_step_flat"}:
        return "directional_persistence_alternation"
    if name in SIGNED or name.startswith("absolute_"):
        return "speed_movement_rate"
    if name in {"body_size", "upper_wick", "lower_wick", "body_share", "upper_wick_share", "lower_wick_share", "log_body_size", "log_upper_wick", "log_lower_wick"}:
        return "candle_geometry"
    if name in {"full_range", "true_range", "atr14_sma", "atr14_wilder", "log_full_range", "volume", "quote_volume", "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume", "complete_volume", "complete_quote_volume", "complete_trade_count", "complete_taker_buy_base_volume", "complete_taker_buy_quote_volume"}:
        return "volatility_volume_activity"
    return None


def load_inputs(data: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    agg_root = data / "research/macro_segment_aggregates"
    agg_manifest = json.loads((agg_root / "manifest.json").read_text())
    agg_files = [Path(x["path"]) for x in agg_manifest["output_files"]]
    for entry, path in zip(agg_manifest["output_files"], agg_files):
        if sha256(path) != entry["sha256"]: raise ValueError(f"aggregate checksum mismatch: {path}")
    legs = [x for x in pq.read_table(agg_files).to_pylist() if x["resolution"] == "4h"]
    atomic_root = data / "features/BTCUSDT/4h_atomic"
    atomic_manifest = json.loads((atomic_root / "manifest.json").read_text())
    files = [atomic_root / x["path"] if not Path(x["path"]).is_absolute() else Path(x["path"]) for x in atomic_manifest["output_files"]]
    for entry, path in zip(atomic_manifest["output_files"], files):
        if sha256(path) != entry["sha256"]: raise ValueError(f"atomic checksum mismatch: {path}")
    return legs, pq.read_table(files).to_pylist(), agg_manifest, atomic_manifest


def oriented_row(row: dict[str, Any], direction: str, features: list[str]) -> dict[str, Any]:
    sign = 1.0 if direction == "up" else -1.0
    out = {"candle_timestamp": row["timestamp"], "candle_end_time": row["end_time"], "source_complete": bool(row["source_complete"]), "pair_eligible": bool(row["pair_eligible"])}
    for name in features:
        value = row.get(name)
        out[name] = None if value is None else float(value) * sign if name in SIGNED else float(value)
    # Exact direction swap for existing up/down activity primitives.
    for base in ("volume_body", "volume_close_step"):
        out[f"{base}_forward"] = row.get(f"{base}_up" if direction == "up" else f"{base}_down")
        out[f"{base}_counter"] = row.get(f"{base}_down" if direction == "up" else f"{base}_up")
        out[f"{base}_flat"] = row.get(f"{base}_flat")
    return out


def clean_features(rows: list[dict[str, Any]], candidates: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    values = {n: np.asarray([np.nan if r.get(n) is None else float(r[n]) for r in rows], dtype=float) for n in candidates}
    audit, kept = [], []
    for n in sorted(candidates):
        x, finite = values[n], np.isfinite(values[n]); coverage = float(finite.mean())
        status = "retained_pre_redundancy"
        if coverage < CONFIG["coverage_minimum"]: status = "excluded_near_empty"
        elif not finite.any(): status = "excluded_no_finite"
        elif np.nanstd(x) == 0: status = "excluded_constant"
        else: kept.append(n)
        audit.append({"feature": n, "family": family(n) or "directional_persistence_alternation", "coverage": coverage, "status": status})
    matrix = np.column_stack([values[n] for n in kept])
    complete = np.all(np.isfinite(matrix), axis=1)
    matrix = matrix[complete]
    selected = []
    for i, name in enumerate(kept):
        if np.std(matrix[:, i]) == 0:
            next(x for x in audit if x["feature"] == name)["status"] = "excluded_constant_after_complete_case"
            continue
        if not selected:
            selected.append(i); continue
        corr = [abs(np.corrcoef(matrix[:, i], matrix[:, j])[0, 1]) for j in selected if np.std(matrix[:, j]) > 0]
        if not corr:
            selected.append(i); continue
        strength = max(corr)
        if np.isfinite(strength) and strength >= CONFIG["near_duplicate_abs_correlation"]: status = "excluded_near_duplicate"
        elif np.isfinite(strength) and strength >= CONFIG["high_redundancy_abs_correlation"]: status = "excluded_high_correlation"
        else: selected.append(i); continue
        next(x for x in audit if x["feature"] == name)["status"] = status
    return [kept[i] for i in selected], audit


def balanced_standardize(matrix: np.ndarray, names: list[str]) -> np.ndarray:
    scale = matrix.std(axis=0)
    # A feature may vary globally yet be constant in one parent leg.  Its
    # standardized within-leg contribution is exactly zero, never NaN.
    scale[scale == 0] = 1.0
    out = (matrix - matrix.mean(axis=0)) / scale
    for fam in FAMILIES:
        indices = [i for i, n in enumerate(names) if family(n) == fam or (fam == "directional_persistence_alternation" and n.startswith("volume_"))]
        if indices: out[:, indices] /= math.sqrt(len(indices))
    return out


def sse(x: np.ndarray, start: int, end: int) -> float:
    part = x[start:end]
    return float(((part - part.mean(axis=0)) ** 2).sum())


def binary_segmentation(x: np.ndarray, min_length: int, penalty: float) -> list[int]:
    """One deterministic binary-segmentation method with an SSE-gain penalty."""
    boundaries: list[int] = []
    pending = [(0, len(x))]
    while pending:
        start, end = pending.pop(0)
        if end - start < 2 * min_length: continue
        parent = sse(x, start, end); best_gain, best = -float("inf"), None
        for split in range(start + min_length, end - min_length + 1):
            gain = parent - sse(x, start, split) - sse(x, split, end)
            if gain > best_gain + 1e-12:
                best_gain, best = gain, split
        if best is not None and best_gain > penalty:
            boundaries.append(best); pending.extend([(start, best), (best, end)])
    return sorted(boundaries)


def sequence_matrix(seq: list[dict[str, Any]], names: list[str], medians: dict[str, float]) -> tuple[np.ndarray, list[int]]:
    raw = np.asarray([[np.nan if r.get(n) is None else float(r[n]) for n in names] for r in seq], dtype=float)
    imputed = []
    for col, name in enumerate(names):
        missing = ~np.isfinite(raw[:, col]); imputed.append(int(missing.sum()))
        if missing.any():
            replacement = np.nanmedian(raw[:, col])
            raw[missing, col] = medians[name] if not np.isfinite(replacement) else replacement
    return balanced_standardize(raw, names), imputed


def check_cover(subsegments: list[dict[str, Any]], sequence: list[dict[str, Any]], leg: str) -> None:
    parts = [x for x in subsegments if x["segment_id"] == leg]
    if not parts or parts[0]["start_index"] != 0 or parts[-1]["end_index_exclusive"] != len(sequence): raise ValueError(f"coverage failure {leg}")
    if any(a["end_index_exclusive"] != b["start_index"] for a, b in zip(parts, parts[1:])): raise ValueError(f"noncontiguous {leg}")


def build(data: Path, repo: Path) -> dict[str, Any]:
    begun = time.perf_counter(); legs, atomic, agg_manifest, atomic_manifest = load_inputs(data)
    if len(legs) != 79: raise ValueError("expected 79 approved 4H legs")
    output = data / "research/macro_within_leg_stage2a"
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    tmp = output.parent / f".{output.name}.build-{uuid.uuid4().hex}"; tmp.mkdir(parents=True)
    try:
        # Registry is CSV; use its candidate sources only, never identifiers or labels.
        with (data / "research/macro_structure_stage1/feature_registry.csv").open() as f:
            registry = list(csv.DictReader(f))
        candidates = sorted({r["atomic_source_feature"] for r in registry if r["predictor_candidate"].lower() == "true" and r["atomic_source_feature"] and r["atomic_source_feature"] not in TECHNICAL})
        candidates += ["volume_body_forward", "volume_body_counter", "volume_body_flat", "volume_close_step_forward", "volume_close_step_counter", "volume_close_step_flat"]
        candidates = sorted(set(candidates))
        atomic_sorted = sorted(atomic, key=lambda x: x["timestamp"])
        per_leg: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        all_oriented = []
        for leg in legs:
            seq = [oriented_row(r, leg["direction"], candidates) for r in atomic_sorted if r["source_complete"] and r["timestamp"] >= leg["measurement_first_timestamp"] and r["end_time"] <= leg["measurement_last_end_time"]]
            if len(seq) != leg["complete_candle_count"]: raise ValueError(f"membership mismatch {leg['segment_id']}: {len(seq)}")
            per_leg[leg["segment_id"]] = (leg, seq); all_oriented.extend(seq)
        names, audit = clean_features(all_oriented, candidates)
        if len(names) < CONFIG["min_feature_count"]: raise ValueError("insufficient compact predictors")
        medians = {n: float(np.nanmedian([np.nan if r.get(n) is None else float(r[n]) for r in all_oriented])) for n in names}
        sequence_rows=[]; boundaries=[]; subsegments=[]; sensitivity=[]
        configs=[(m,p) for m in CONFIG["sensitivity_min_lengths"] for p in CONFIG["sensitivity_penalties"]]
        for segment_id, (leg, seq) in sorted(per_leg.items()):
            x, imputed = sequence_matrix(seq, names, medians)
            all_runs = {(m,p): binary_segmentation(x,m,p) for m,p in configs}
            primary = all_runs[(CONFIG["primary_min_length"], CONFIG["primary_penalty"])]
            support = {i: sum(i in b for b in all_runs.values()) / len(all_runs) for i in range(1,len(seq))}
            for (m,p), bs in all_runs.items(): sensitivity.append({"segment_id":segment_id,"minimum_length":m,"penalty":p,"boundary_count":len(bs),"boundaries":json.dumps(bs)})
            for i, row in enumerate(seq):
                sequence_rows.append({"segment_id":segment_id,"macro_direction":leg["direction"],"candle_timestamp":row["candle_timestamp"],"relative_position":i/max(len(seq)-1,1),"sequence_index":i,"source_complete":row["source_complete"],"pair_eligible":row["pair_eligible"],"imputed_feature_count":sum(not np.isfinite(np.nan if row.get(n) is None else float(row[n])) for n in names), **{n: row.get(n) for n in names}})
            for index in primary:
                boundaries.append({"segment_id":segment_id,"boundary_index":index,"boundary_timestamp":seq[index]["candle_timestamp"],"support":support[index],"supporting_configs":sum(index in b for b in all_runs.values()),"total_configs":len(all_runs),"strength":"strong" if support[index] >= CONFIG["strong_boundary_support"] else "weak"})
            cuts=[0]+primary+[len(seq)]
            for k,(start,end) in enumerate(zip(cuts,cuts[1:]),1):
                piece=seq[start:end]; signed=np.asarray([0.0 if r.get("signed_log_move") is None else r["signed_log_move"] for r in piece]); steps=np.asarray([np.nan if r.get("close_step_sign") is None else r["close_step_sign"] for r in piece]); eligible=np.isfinite(steps) & (steps!=0)
                counter=float((steps[eligible]<0).mean()) if eligible.any() else None
                subsegments.append({"segment_id":segment_id,"subsegment_id":f"{segment_id}_S{k:02d}","subsegment_order":k,"start_index":start,"end_index_exclusive":end,"start_timestamp":piece[0]["candle_timestamp"],"end_timestamp":piece[-1]["candle_end_time"],"candle_count":end-start,"duration_hours":float((end-start)*4),"macro_direction":leg["direction"],"net_log_move_leg_relative":float(signed.sum()),"net_move_direction_relative_to_macro":"forward" if signed.sum()>0 else "counter" if signed.sum()<0 else "flat","counter_move_share":counter,"start_boundary_support":None if start==0 else support[start],"end_boundary_support":None if end==len(seq) else support[end], **{f"{fam}_mean":float(np.nanmean([[np.nan if r.get(n) is None else float(r[n]) for n in names if family(n)==fam] for r in piece])) for fam in FAMILIES}})
            check_cover(subsegments,seq,segment_id)
        # Re-run fixed configuration without rereading input to enforce reproducibility.
        rerun = {sid: binary_segmentation(sequence_matrix(seq,names,medians)[0], CONFIG["primary_min_length"], CONFIG["primary_penalty"]) for sid,(_,seq) in per_leg.items()}
        expected = {sid:[b["boundary_index"] for b in boundaries if b["segment_id"]==sid] for sid in per_leg}
        qa={"status":"PASS","macro_legs":len(per_leg),"all_sequences_covered_once":True,"fixed_config_reproducible":rerun==expected,"labels_or_fibtime_consumed":False,"semantic_classes_assigned":False,"predictor_identity_leakage":sorted(set(names)&TECHNICAL)}
        if not qa["fixed_config_reproducible"] or qa["predictor_identity_leakage"]: raise RuntimeError(f"QA failed {qa}")
        atomic_csv(tmp/"preprocessing_feature_audit.csv",audit); write_parquet(tmp/"normalized_4h_sequences.parquet",sequence_rows); write_parquet(tmp/"candidate_boundaries.parquet",boundaries); write_parquet(tmp/"candidate_subsegments.parquet",subsegments); atomic_csv(tmp/"boundary_sensitivity_diagnostics.csv",sensitivity); atomic_json(tmp/"qa.json",qa)
        files=[]
        for p in sorted(tmp.iterdir()):
            if p.is_file(): files.append({"path":str(output/p.name),"bytes":p.stat().st_size,"sha256":sha256(p)})
        manifest={"schema_version":SCHEMA_VERSION,"build_timestamp_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"source_atomic_manifest":str(data/"features/BTCUSDT/4h_atomic/manifest.json"),"source_atomic_manifest_sha256":sha256(data/"features/BTCUSDT/4h_atomic/manifest.json"),"source_aggregate_manifest":str(data/"research/macro_segment_aggregates/manifest.json"),"source_aggregate_manifest_sha256":sha256(data/"research/macro_segment_aggregates/manifest.json"),"stage1_registry":str(data/"research/macro_structure_stage1/feature_registry.csv"),"config":CONFIG,"predictors":names,"qa":qa,"labels_used":False,"semantic_classification":False,"output_files":files,"code_version":{"git_commit_at_build":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(),"pipeline_sha256":sha256(Path(__file__))}}
        atomic_json(tmp/"manifest.json",manifest); os.replace(tmp,output)
        return {"status":"PASS","path":str(output),"macro_legs":len(per_leg),"subsegments":len(subsegments),"boundaries":len(boundaries),"runtime_seconds":round(time.perf_counter()-begun,3)}
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise


def stamp(data: Path, commit: str) -> None:
    p=data/"research/macro_within_leg_stage2a/manifest.json"; x=json.loads(p.read_text()); x["code_version"]["git_commit"]=commit; atomic_json(p,x)


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--data-root",type=Path,required=True); ap.add_argument("--repo-root",type=Path,default=Path.cwd()); ap.add_argument("--stamp-git-commit"); a=ap.parse_args()
    if a.stamp_git_commit: stamp(a.data_root,a.stamp_git_commit); print(json.dumps({"stamped_git_commit":a.stamp_git_commit})); return
    print(json.dumps(build(a.data_root,a.repo_root),indent=2))
if __name__ == "__main__": main()
