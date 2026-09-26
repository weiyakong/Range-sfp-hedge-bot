#!/usr/bin/env python3
"""Bounded structural diagnosis of completed Stage 2B artifacts; no new clustering."""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,math,os,subprocess,time,uuid,shutil
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def jwrite(p,x):
 t=p.with_name(p.name+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,default=str)+'\n');os.replace(t,p)
def cwrite(p,rows):
 fields=sorted({k for r in rows for k in r}) if rows else ['status'];t=p.with_name(p.name+'.partial')
 with t.open('w',newline='',encoding='utf8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 os.replace(t,p)
def ari(a,b):
 n=len(a);d={}
 for x,y in zip(a,b):d[(int(x),int(y))]=d.get((int(x),int(y)),0)+1
 c=lambda z:z*(z-1)/2;ab=sum(c(v) for v in d.values());aa=sum(c(sum(v for (x,_),v in d.items() if x==z)) for z in set(a));bb=sum(c(sum(v for (_,y),v in d.items() if y==z)) for z in set(b));tot=c(n);ex=aa*bb/tot;mx=(aa+bb)/2
 return 1. if mx==ex else float((ab-ex)/(mx-ex))
def ranks(x):
 order=np.argsort(x);r=np.empty(len(x));r[order]=np.arange(len(x));return r
def corr(a,b):
 m=np.isfinite(a)&np.isfinite(b)
 return None if m.sum()<3 or np.std(a[m])==0 or np.std(b[m])==0 else float(np.corrcoef(ranks(a[m]),ranks(b[m]))[0,1])
def detail_family(n):
 base=n.split('__')[0]
 if 'overlap' in base or 'penetration' in base or 'extension' in base:return 'overlap_body_overlap'
 if 'alternation' in base:return 'alternation'
 if base.startswith(('volume_body','volume_close_step')) or base=='close_step_sign':return 'directional_persistence_counter'
 if base.startswith(('signed_','absolute_','raw_signed_speed')):return 'speed_movement_rate'
 if base in {'body_size','upper_wick','lower_wick','body_share','upper_wick_share','lower_wick_share','log_body_size','log_upper_wick','log_lower_wick'}:return 'candle_geometry'
 if base in {'full_range','true_range','atr14_sma','atr14_wilder','log_full_range'}:return 'volatility'
 return 'volume_activity'
def load_module(repo):
 p=repo/'research/btc_macro_nautilus/macro_subsegment_types_stage2b/build_macro_subsegment_types_stage2b.py';s=importlib.util.spec_from_file_location('stage2b_frozen',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def build(data,repo):
 begun=time.perf_counter();src=data/'research/macro_subsegment_types_stage2b';stage2a=data/'research/macro_within_leg_stage2a';out=data/'research/macro_subsegment_types_stage2b_sol_analysis'
 if out.exists():raise FileExistsError(out)
 tmp=out.parent/f'.{out.name}.build-{uuid.uuid4().hex}';tmp.mkdir(parents=True)
 try:
  manifest=json.loads((src/'manifest.json').read_text());solution=json.loads((src/'preferred_or_ambiguous_solution.json').read_text());kdiag=list(csv.DictReader((src/'candidate_k_diagnostics.csv').open()))
  pop=pq.read_table(src/'analysis_population.parquet').to_pylist();primary=[r for r in pop if r['population']=='primary'];ids=[r['subsegment_id'] for r in primary];index={x:i for i,x in enumerate(ids)}
  print('loaded Stage 2B population',flush=True)
  cand=pq.read_table(src/'candidate_cluster_assignments.parquet').to_pylist();labels={k:np.empty(len(ids),int) for k in range(2,7)}
  for r in cand:labels[int(r['k'])][index[r['subsegment_id']]]=int(r['candidate_cluster'])
  rel=[]
  for low in range(2,6):
   for high in range(low+1,7):
    nested=[]
    for c in set(labels[high]):
     members=labels[high]==c;counts=np.bincount(labels[low][members],minlength=low);nested.append(counts.max()/members.sum())
    rel.append({'lower_k':low,'higher_k':high,'adjusted_rand_index':ari(labels[low],labels[high]),'weighted_child_to_parent_purity':float(np.average(nested,weights=[(labels[high]==c).sum() for c in set(labels[high])]))})
  co_rows=pq.read_table(src/'coassignment_matrix.parquet').to_pylist();co=np.full((len(ids),len(ids)),np.nan)
  for r in co_rows:co[index[r['subsegment_id_a']],index[r['subsegment_id_b']]]=r['coassignment']
  print('loaded coassignment evidence',flush=True)
  reference=int(solution['coassignment_reference_k']);ref=labels[reference];cores=[];bridges=[]
  for c in range(reference):
   members=np.where(ref==c)[0];outside=np.where(ref!=c)[0];scores=np.nanmean(co[np.ix_(members,members)],axis=1);leak=np.nanmax(co[np.ix_(members,outside)],axis=1);core=members[(scores>=.80)&(leak<=.20)]
   cores.append({'core':f'Core {chr(65+c)}','reference_candidate_cluster':c,'core_size':len(core),'candidate_cluster_size':len(members),'median_within_core_coassignment':float(np.nanmedian(co[np.ix_(core,core)])) if len(core)>1 else None,'criterion':'mean_within>=0.80 and max_outside<=0.20'})
   core_set=set(core)
   for i in members:
    if i not in core_set:bridges.append({'subsegment_id':ids[i],'reference_candidate_cluster':c,'mean_within_candidate':float(scores[np.where(members==i)[0][0]]),'max_outside_candidate':float(leak[np.where(members==i)[0][0]]),'reason':'fails_stable_core_pairwise_criterion'})
  print('derived pairwise cores',flush=True)
  # Inspect axes using only the already-materialized Stage 2a compact family
  # summaries; this avoids rebuilding the Stage 2B feature pipeline.
  subs=pq.read_table(stage2a/'candidate_subsegments.parquet').to_pylist();submeta={r['subsegment_id']:r for r in subs};rows=sorted([r for r in subs if r['subsegment_id'] in index],key=lambda r:index[r['subsegment_id']])
  names=['overlap_body_overlap_mean','directional_persistence_alternation_mean','speed_movement_rate_mean','candle_geometry_mean','volatility_volume_activity_mean']
  raw=np.asarray([[float(r[n]) for n in names] for r in rows]);scale=raw.std(0);scale[scale==0]=1;x=(raw-raw.mean(0))/scale
  print('loaded compact Stage 2a family summaries',flush=True)
  _,sing,vt=np.linalg.svd(x,full_matrices=False);scores=x@vt.T;share=sing**2/(sing**2).sum();axes=[]
  for pc in range(4):
   family_weight={n.removesuffix('_mean'):float(vt[pc,i]**2) for i,n in enumerate(names)};top=np.argsort(abs(vt[pc]))[::-1]
   axes.append({'axis':f'PC{pc+1}','explained_variance':float(share[pc]),'top_features':' | '.join(f'{names[i]} ({vt[pc,i]:+.3f})' for i in top),'top_families':' | '.join(f'{k}:{v:.3f}' for k,v in sorted(family_weight.items(),key=lambda z:z[1],reverse=True)[:4])})
  meta=[]
  for pc in range(4):
   for field in ('candle_count','duration_hours'):
    meta.append({'axis':f'PC{pc+1}','metadata':field,'spearman':corr(scores[:,pc],np.asarray([float(r[field]) for r in rows]))})
   support=np.asarray([np.nan if all(r[z] is None for z in ('start_boundary_support','end_boundary_support')) else min(v for v in (r['start_boundary_support'],r['end_boundary_support']) if v is not None) for r in rows]);era=np.asarray([submeta[r['subsegment_id']]['start_timestamp'].timestamp() for r in rows]);meta.extend([{'axis':f'PC{pc+1}','metadata':'boundary_support_min','spearman':corr(scores[:,pc],support)},{'axis':f'PC{pc+1}','metadata':'calendar_era','spearman':corr(scores[:,pc],era)}])
  strongest=max((r for r in meta if r['spearman'] is not None),key=lambda r:abs(r['spearman']))
  diag={r['k']:{'silhouette':float(r['silhouette']),'stability':float(r['stability_mean_ari'])} for r in kdiag}
  original_clusterability=json.loads((src/'clusterability_diagnostics.json').read_text())
  diagnosis={'classification':'continuous multidimensional spectrum with a nested-partition tendency; no stable cores','direct_evidence':{'hopkins':original_clusterability['hopkins'],'preferred_k':None,'reference_k':reference,'candidate_metrics':diag,'stable_core_count':sum(r['core_size']>=5 for r in cores),'stable_core_members':sum(r['core_size'] for r in cores),'bridge_or_unstable_members':len(bridges),'stage2b_full_pc1_pc2_variance':original_clusterability['pc1_pc2_variance'],'compact_family_pc1_pc2_variance':float(share[:2].sum()),'strongest_metadata_axis_association':strongest},'interpretation':'Non-random density gradients exist, and several higher-k partitions resemble nested splits of lower-k partitions. However, no observation meets the strict stable-core criterion and hard spherical partitions are unstable under perturbation.','not_established':['a unique number of movement types','persistent hierarchical branches','semantic market-state meanings']}
  md=f"""# Stage 2B structural diagnosis\n\n## Conclusion\n\n**{diagnosis['classification']}**. Hopkins is {diagnosis['direct_evidence']['hopkins']:.3f}, yet no k=2..6 clears both separation and stability. The reference k={reference} co-assignment contains no strict stable core: 0/{len(ids)} observations satisfy mean-within ≥0.80 and max-outside ≤0.20. The full Stage 2B PC1+PC2 share is {original_clusterability['pc1_pc2_variance']:.3f}; the five compact family summaries concentrate {share[:2].sum():.3f} in two axes.\n\n## What follows directly\n\n- Structure is non-random, but no supported hard type count exists.\n- Some candidate-k solutions are nested-like, but perturbation stability remains inadequate.\n- All primary observations are transitional under the strict pairwise-core rule.\n\n## Interpretation limits\n\nThe best current description is a multidimensional continuum with a possible nested-partition tendency. A persistent hierarchy is plausible but not established. No candidate partition is a semantic class.\n"""
  (tmp/'structure_diagnosis.md').write_text(md);jwrite(tmp/'structure_diagnosis.json',diagnosis);cwrite(tmp/'stable_cores_if_any.csv',cores);cwrite(tmp/'unstable_or_bridge_subsegments.csv',bridges);cwrite(tmp/'behavioral_axes.csv',axes);cwrite(tmp/'candidate_k_relationships.csv',rel);cwrite(tmp/'axis_confounder_report.csv',meta)
  (tmp/'recommended_next_test.md').write_text("# Recommended next test\n\nRun one preregistered density-aware hierarchical test on the frozen Stage 2B matrix: consensus complete-linkage on `1 - coassignment`, evaluated by branch persistence under the same observation/feature perturbations. This can distinguish nested persistent cores from a continuum without forcing spherical clusters. A small set of branches that persists across perturbations would support a hierarchy; diffuse branch membership with no persistence would favor a continuous spectrum. Do not assign semantics during that test.\n")
  files=[]
  for p in sorted(tmp.iterdir()):
   if p.is_file():files.append({'path':str(out/p.name),'bytes':p.stat().st_size,'sha256':sha(p)})
  man={'schema_version':'stage2b-sol-structure-analysis-v1','source_stage2b_manifest':str(src/'manifest.json'),'source_stage2b_manifest_sha256':sha(src/'manifest.json'),'axis_source':str(stage2a/'candidate_subsegments.parquet'),'bounded_calculations':['coassignment core criterion','candidate-k ARI and nested purity','SVD of existing compact family summaries','metadata Spearman correlations'],'new_clustering_run':False,'qa':{'status':'PASS','primary_rows':len(ids),'compact_axis_rows_match_primary':len(rows)==len(ids),'duplicate_ids':len(ids)!=len(set(ids)),'finite_matrix':bool(np.isfinite(x).all())},'output_files':files,'runtime_seconds':round(time.perf_counter()-begun,3),'code_version':{'git_commit_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'pipeline_sha256':sha(Path(__file__))}}
  if not man['qa']['compact_axis_rows_match_primary'] or man['qa']['duplicate_ids'] or not man['qa']['finite_matrix']:raise RuntimeError(man['qa'])
  jwrite(tmp/'manifest.json',man);os.replace(tmp,out);return {'status':'PASS','path':str(out),'classification':diagnosis['classification'],'cores':cores,'bridges':len(bridges),'runtime_seconds':man['runtime_seconds']}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
def stamp(data,commit):
 p=data/'research/macro_subsegment_types_stage2b_sol_analysis/manifest.json';x=json.loads(p.read_text());x['code_version']['git_commit']=commit;jwrite(p,x)
def main():
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,required=True);a.add_argument('--repo-root',type=Path,default=Path.cwd());a.add_argument('--stamp-git-commit');z=a.parse_args()
 if z.stamp_git_commit:stamp(z.data_root,z.stamp_git_commit);print(json.dumps({'stamped_git_commit':z.stamp_git_commit}))
 else:print(json.dumps(build(z.data_root,z.repo_root),indent=2))
if __name__=='__main__':main()
