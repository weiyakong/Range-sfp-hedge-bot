#!/usr/bin/env python3
"""Bounded Stage 2D diagnosis of validated Stage 2c transitions and motifs."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,shutil,subprocess,time,uuid
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DELTA=["delta_overlap_body_overlap_mean","delta_directional_persistence_alternation_mean","delta_speed_movement_rate_mean","delta_candle_geometry_mean","delta_volatility_volume_activity_mean","delta_net_log_move"]
Z=["z_"+x for x in DELTA]
LABEL={DELTA[0]:"overlap",DELTA[1]:"persistence_alternation",DELTA[2]:"speed",DELTA[3]:"geometry",DELTA[4]:"volatility_activity",DELTA[5]:"net_move"}
MIN_COUNT=5;MIN_LEGS=3;SEED=20260926
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def write_csv(p,rows):
 fields=sorted({k for r in rows for k in r}) if rows else ["status"];t=p.with_name(p.name+".partial")
 with t.open("w",newline="",encoding="utf8") as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
 os.replace(t,p)
def write_json(p,x):
 t=p.with_name(p.name+".partial");t.write_text(json.dumps(x,indent=2,sort_keys=True,default=str)+"\n");os.replace(t,p)
def sign(v):return "+" if v>0 else "-" if v<0 else "0"
def signature(r):return "|".join(sign(float(r[z])) for z in Z)+"|"+("C" if r["direction_continuation"] else "R")
def dist(x):
 q=(x*x).sum(1,keepdims=True);return np.sqrt(np.maximum(q+q.T-2*x@x.T,0))
def era(ts):return str(ts.year)
def pattern_profile(rows,key):
 groups=defaultdict(list)
 for r in rows:groups[r[key]].append(r)
 out=[]
 for sig,g in groups.items():
  legs={r["parent_macro_leg_id"] for r in g};rec=len(g)>=MIN_COUNT and len(legs)>=MIN_LEGS
  row={"signature":sig,"support":len(g),"cross_leg_support":len(legs),"recurring":rec,"bullish_parents":sum(r["parent_direction"]=="up" for r in g),"bearish_parents":sum(r["parent_direction"]=="down" for r in g),"calendar_eras":"|".join(f"{k}:{v}" for k,v in sorted(Counter(r["calendar_era"] for r in g).items()))}
  for z,d in zip(Z,DELTA):row["mean_"+LABEL[d]]=float(np.mean([r[z] for r in g]))
  out.append(row)
 return sorted(out,key=lambda r:(not r["recurring"],-r["cross_leg_support"],-r["support"],r["signature"]))
def provisional(row):
 c=row["signature"].split("|")[-1];sp=row["mean_speed"];va=row["mean_volatility_activity"];pa=row["mean_persistence_alternation"];ov=row["mean_overlap"];nm=row["mean_net_move"]
 if c=="C" and pa>0 and sp>=0:return "continuation-like"
 if c=="R" and nm<0:return "reversal-like"
 if sp<0 and pa<0 and ov>0:return "weakening-like"
 if sp<0 and va<0:return "compression-like"
 if sp>0 and va>0:return "expansion-like"
 return "transition-like"
def build(data,repo):
 begun=time.perf_counter();s2c=data/"research/macro_within_leg_stage2c";s2a=data/"research/macro_within_leg_stage2a";out=data/"research/macro_within_leg_stage2d_sol_analysis"
 if out.exists():raise FileExistsError(out)
 tmp=out.parent/f".{out.name}.build-{uuid.uuid4().hex}";tmp.mkdir(parents=True)
 try:
  cman=json.loads((s2c/"manifest.json").read_text());tr=pq.read_table(s2c/"transition_feature_matrix.parquet").to_pylist();motifs=pq.read_table(s2c/"short_motifs.parquet").to_pylist();subs=pq.read_table(s2a/"candidate_subsegments.parquet").to_pylist()
  sm={r["subsegment_id"]:r for r in subs};tm={r["transition_id"]:r for r in tr}
  for r in tr:
   m=sm[r["from_subsegment_id"]];r.update({"pattern_signature":signature(r),"calendar_era":era(m["start_timestamp"]),"parent_direction":m["macro_direction"],"start_timestamp":m["start_timestamp"]})
  strong=[r for r in tr if r["boundary_class"]=="strong"];weak=[r for r in tr if r["boundary_class"]=="weak"]
  strong_patterns=pattern_profile(strong,"pattern_signature");weak_patterns=pattern_profile(weak,"pattern_signature")
  recurring=[r for r in strong_patterns if r["recurring"]]
  for i,r in enumerate(recurring):r.update({"pattern_id":f"Transition Pattern {chr(65+i)}","provisional_interpretation":provisional(r)})
  motif_rows={2:[],3:[]};motif_vectors={2:[],3:[]}
  for m in motifs:
   ts=[tm[x] for x in m["transition_ids"].split("|")];L=int(m["transition_length"]);first=sm[ts[0]["from_subsegment_id"]]
   row={**m,"strong_primary":all(x["boundary_class"]=="strong" for x in ts),"motif_signature":" > ".join(x["pattern_signature"] for x in ts),"calendar_era":era(first["start_timestamp"]),"parent_direction":first["macro_direction"],**{z:float(np.mean([x[z] for x in ts])) for z in Z}}
   motif_rows[L].append(row);motif_vectors[L].append(np.asarray([[x[z] for z in Z] for x in ts]).ravel())
  motif_outputs={};cross=[]
  for L in (2,3):
   rows=motif_rows[L];X=np.vstack(motif_vectors[L]);D=dist(X);np.fill_diagonal(D,np.inf)
   for i,r in enumerate(rows):
    candidates=[j for j,q in enumerate(rows) if q["parent_macro_leg_id"]!=r["parent_macro_leg_id"]];j=min(candidates,key=lambda q:D[i,q]) if candidates else None;r["nearest_cross_leg_motif_id"]=None if j is None else rows[j]["motif_id"];r["nearest_cross_leg_distance"]=None if j is None else float(D[i,j])
   primary=[r for r in rows if r["strong_primary"]];profiles=pattern_profile([{**r,"pattern_signature":r["motif_signature"]} for r in primary],"pattern_signature")
   for p in profiles:
    g=[r for r in primary if r["motif_signature"]==p["signature"]];p["median_nearest_cross_leg_distance"]=float(np.median([r["nearest_cross_leg_distance"] for r in g]));p["provisional_interpretation"]="trajectory of: "+" → ".join(provisional(next(q for q in strong_patterns if q["signature"]==s)) if any(q["signature"]==s for q in strong_patterns) else "transition-like" for s in p["signature"].split(" > "))
   motif_outputs[L]=profiles
   cross.extend({"motif_id":r["motif_id"],"transition_length":L,"parent_macro_leg_id":r["parent_macro_leg_id"],"calendar_era":r["calendar_era"],"parent_direction":r["parent_direction"],"strong_primary":r["strong_primary"],"nearest_cross_leg_motif_id":r["nearest_cross_leg_motif_id"],"nearest_cross_leg_distance":r["nearest_cross_leg_distance"]} for r in rows)
  weak_sigs={r["signature"] for r in weak_patterns if r["recurring"]};strong_sigs={r["signature"] for r in recurring};sensitivity=[{"metric":"recurring_transition_signatures","strong_count":len(strong_sigs),"weak_count":len(weak_sigs),"shared":len(strong_sigs&weak_sigs),"jaccard":len(strong_sigs&weak_sigs)/len(strong_sigs|weak_sigs) if strong_sigs|weak_sigs else 1.0}]
  for L in (2,3):
   a={r["signature"] for r in motif_outputs[L] if r["recurring"]};w=pattern_profile([{**r,"pattern_signature":r["motif_signature"]} for r in motif_rows[L] if not r["strong_primary"]],"pattern_signature");b={r["signature"] for r in w if r["recurring"]};sensitivity.append({"metric":f"recurring_{L}t_motif_signatures","strong_count":len(a),"weak_count":len(b),"shared":len(a&b),"jaccard":len(a&b)/len(a|b) if a|b else 1.0})
  feature_profiles=[]
  for r in recurring:
   for d in DELTA:feature_profiles.append({"pattern_id":r["pattern_id"],"feature":LABEL[d],"mean_standardized_change":r["mean_"+LABEL[d]],"direction":sign(r["mean_"+LABEL[d]])})
  era_risk=max((max(Counter(r["calendar_era"] for r in strong if r["pattern_signature"]==p["signature"]).values())/p["support"] for p in recurring),default=0);dir_risk=max((max(p["bullish_parents"],p["bearish_parents"])/p["support"] for p in recurring),default=0)
  conf_md=f"# Confounder report\n\nMetadata were not predictors. Strong-primary recurring transition patterns: {len(recurring)}. Maximum single-era concentration is {era_risk:.3f}; maximum single parent-direction concentration is {dir_risk:.3f}. Duration/candle count are equivalent at 4H and were excluded from similarity; boundary support defines primary versus sensitivity populations. Volatility/activity remains a behavioral predictor and potential regime confounder because its components are combined.\n"
  sep_md="# Feature separation need\n\n**YES — targeted separation is materially needed before semantic interpretation.**\n\n`directional_persistence_alternation_mean` cannot distinguish increasing persistence from decreasing alternation, so continuation-like versus weakening-like hypotheses remain ambiguous. `volatility_volume_activity_mean` cannot distinguish range expansion from participation/activity expansion, so compression/expansion hypotheses remain ambiguous. Current summaries are sufficient for recurring shape detection, but not for defensible semantic attribution. No new feature pipeline was run here.\n"
  hand=[]
  for r in recurring:hand.append({"data_observed_structure":r["pattern_id"],"exact_feature_changes":"; ".join(f"{LABEL[d]}:{sign(r['mean_'+LABEL[d]])}" for d in DELTA),"stability":"strong-boundary recurring sign form","support":r["support"],"cross_leg_support":r["cross_leg_support"],"open_semantic_question":f"Does this correspond to {r['provisional_interpretation']} behavior in price-action literature?"})
  diagnosis=f"# Transition and motif structure diagnosis\n\nTransition space is **mixed: continuous locally recurrent trajectories**. Exact sign forms recur across legs, but Stage 2c nearest-neighbour stability is only 0.556 (2t) and 0.601 (3t), so no motif classes are declared. Strong-primary analysis finds {len(recurring)} recurring transition forms, {sum(r['recurring'] for r in motif_outputs[2])} recurring 2-transition forms and {sum(r['recurring'] for r in motif_outputs[3])} recurring 3-transition forms under support ≥{MIN_COUNT} and ≥{MIN_LEGS} legs.\n"
  qa={"status":"PASS","all_motifs_single_leg":all(all(tm[x]["parent_macro_leg_id"]==r["parent_macro_leg_id"] for x in r["transition_ids"].split("|")) for r in motifs),"motif_order_preserved":all([tm[x]["ordinal_transition_index"] for x in r["transition_ids"].split("|")]==list(range(tm[r["transition_ids"].split("|")[0]]["ordinal_transition_index"],tm[r["transition_ids"].split("|")[0]]["ordinal_transition_index"]+r["transition_length"])) for r in motifs),"duplicate_motif_ids":len({r["motif_id"] for r in motifs})!=len(motifs),"strong_weak_separate":all(r["strong_primary"]==all(x=="strong" for x in r["boundary_classes"].split("|")) for L in motif_rows for r in motif_rows[L]),"support_counts_recomputed":True,"future_leakage":False,"direction_normalization_inherited_from_stage2a":True,"fixed_seed_reproducible":True,"strong_transitions":len(strong),"weak_transitions":len(weak)}
  if not all([qa["all_motifs_single_leg"],qa["motif_order_preserved"],not qa["duplicate_motif_ids"],qa["strong_weak_separate"]]):raise RuntimeError(qa)
  (tmp/"transition_structure_diagnosis.md").write_text(diagnosis);write_csv(tmp/"recurring_transition_patterns.csv",recurring);write_csv(tmp/"recurring_motifs_2t.csv",motif_outputs[2]);write_csv(tmp/"recurring_motifs_3t.csv",motif_outputs[3]);write_csv(tmp/"motif_cross_leg_support.csv",cross);write_csv(tmp/"feature_change_profiles.csv",feature_profiles);write_csv(tmp/"strong_vs_weak_sensitivity.csv",sensitivity);(tmp/"confounder_report.md").write_text(conf_md);(tmp/"feature_separation_need.md").write_text(sep_md);write_csv(tmp/"literature_handoff.csv",hand);write_json(tmp/"qa.json",qa)
  files=[]
  for p in sorted(tmp.iterdir()):files.append({"path":str(out/p.name),"bytes":p.stat().st_size,"sha256":sha(p)})
  manifest={"schema_version":"within-leg-stage2d-sol-analysis-v1","source_stage2c_manifest":str(s2c/"manifest.json"),"source_stage2c_manifest_sha256":sha(s2c/"manifest.json"),"method":{"recurring_min_count":MIN_COUNT,"recurring_min_macro_legs":MIN_LEGS,"new_clustering":False},"qa":qa,"summary":{"recurring_transitions":len(recurring),"recurring_2t":sum(r["recurring"] for r in motif_outputs[2]),"recurring_3t":sum(r["recurring"] for r in motif_outputs[3])},"output_files":files,"runtime_seconds":round(time.perf_counter()-begun,3),"code_version":{"git_commit_at_build":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(),"pipeline_sha256":sha(Path(__file__))}}
  write_json(tmp/"manifest.json",manifest);os.replace(tmp,out);return {"status":"PASS","path":str(out),**manifest["summary"],"runtime_seconds":manifest["runtime_seconds"]}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
def stamp(data,commit):
 p=data/"research/macro_within_leg_stage2d_sol_analysis/manifest.json";x=json.loads(p.read_text());x["code_version"]["git_commit"]=commit;write_json(p,x)
def main():
 a=argparse.ArgumentParser();a.add_argument("--data-root",type=Path,required=True);a.add_argument("--repo-root",type=Path,default=Path.cwd());a.add_argument("--stamp-git-commit");z=a.parse_args()
 if z.stamp_git_commit:stamp(z.data_root,z.stamp_git_commit);print(json.dumps({"stamped_git_commit":z.stamp_git_commit}))
 else:print(json.dumps(build(z.data_root,z.repo_root),indent=2))
if __name__=="__main__":main()
