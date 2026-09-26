#!/usr/bin/env python3
"""Label-free clustering diagnostics for validated Stage 2a candidate subsegments."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,shutil,subprocess,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SEED=20260926
CONFIG={"seed":SEED,"strong_boundary_support":0.60,"orientation_zero_tolerance":1e-12,"coverage_minimum":.80,"near_duplicate_abs_correlation":.999999,"high_redundancy_abs_correlation":.98,"k_values":[2,3,4,5,6],"stability_repetitions":20,"subsample_fraction":.80,"feature_fraction":.80,"supported_hopkins":.65,"supported_silhouette":.25,"supported_stability":.60}
SIGNED={"signed_price_change","signed_close_return","signed_return_pct","signed_log_move","raw_signed_speed_pct_per_hour","signed_log_speed_per_hour","close_step_sign"}
META={"segment_id","macro_direction","candle_timestamp","relative_position","sequence_index","source_complete","pair_eligible","imputed_feature_count"}
FAMILIES=("overlap_body_overlap","directional_persistence_alternation","speed_movement_rate","candle_geometry","volatility_volume_activity")

def digest(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save_json(p:Path,x:Any):
 t=p.with_name(p.name+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,default=str)+'\n');os.replace(t,p)
def save_csv(p:Path,rows:list[dict]):
 fields=sorted({k for r in rows for k in r}) if rows else ['status'];t=p.with_name(p.name+'.partial')
 with t.open('w',newline='',encoding='utf8') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 os.replace(t,p)
def save_parquet(p:Path,rows:list[dict]):
 if rows:pq.write_table(pa.Table.from_pylist(rows),p,compression='zstd',compression_level=9)
def fam(n:str)->str|None:
 if any(x in n for x in ('overlap','penetration','extension')):return 'overlap_body_overlap'
 if n in {'alternation_indicator','close_step_sign'} or n.startswith(('volume_body_','volume_close_step_')):return 'directional_persistence_alternation'
 if n in SIGNED or n.startswith('absolute_'):return 'speed_movement_rate'
 if n in {'body_size','upper_wick','lower_wick','body_share','upper_wick_share','lower_wick_share','log_body_size','log_upper_wick','log_lower_wick'}:return 'candle_geometry'
 return 'volatility_volume_activity'
def standardize(x):
 s=x.std(0);s[s==0]=1;return (x-x.mean(0))/s
def distance(x):
 q=(x*x).sum(1,keepdims=True);return np.sqrt(np.maximum(q+q.T-2*x@x.T,0))
def kmeans(x,k,seed):
 rng=np.random.default_rng(seed);n=len(x);centers=x[rng.choice(n,k,replace=False)].copy();old=None
 for _ in range(150):
  lab=np.argmin(((x[:,None]-centers[None,:])**2).sum(2),1)
  new=np.array([x[lab==c].mean(0) if np.any(lab==c) else x[rng.integers(n)] for c in range(k)])
  if old is not None and np.array_equal(old,lab):break
  old,centers=lab,new
 return lab,centers
def silhouette(x,lab):
 d=distance(x);out=[]
 for i,c in enumerate(lab):
  own=np.where(lab==c)[0]
  if len(own)<2:out.append(0.);continue
  a=d[i,own[own!=i]].mean();b=min(d[i,lab==z].mean() for z in set(lab) if z!=c);out.append((b-a)/max(a,b) if max(a,b) else 0.)
 return float(np.mean(out))
def ari(a,b):
 n=len(a);c={}
 for x,y in zip(a,b):c[(int(x),int(y))]=c.get((int(x),int(y)),0)+1
 ch=lambda z:z*(z-1)/2;ab=sum(ch(v) for v in c.values());aa=sum(ch(sum(v for (x,_),v in c.items() if x==z)) for z in set(a));bb=sum(ch(sum(v for (_,y),v in c.items() if y==z)) for z in set(b));tot=ch(n);ex=aa*bb/tot if tot else 0;mx=(aa+bb)/2
 return 1. if mx==ex else float((ab-ex)/(mx-ex))
def hopkins(x):
 rng=np.random.default_rng(SEED);n=len(x);m=min(20,n//2);idx=rng.choice(n,m,False);low,high=x.min(0),x.max(0);d=distance(x);obs=np.array([np.delete(d[i],i).min() for i in idx]);u=rng.uniform(low,high,(m,x.shape[1]));un=np.array([np.sqrt(((x-z)**2).sum(1)).min() for z in u]);return float(un.sum()/(un.sum()+obs.sum()))
def stable_seed(*x):return SEED+int.from_bytes(hashlib.sha256('|'.join(map(str,x)).encode()).digest()[:4],'big')%1000000
def stability(x,base,k):
 rng=np.random.default_rng(stable_seed('stability',k));n,p=x.shape;co=np.zeros((n,n));seen=np.zeros((n,n));scores=[]
 for r in range(CONFIG['stability_repetitions']):
  idx=np.sort(rng.choice(n,max(k+1,int(n*CONFIG['subsample_fraction'])),False));cols=np.sort(rng.choice(p,max(2,int(p*CONFIG['feature_fraction'])),False));trial,_=kmeans(standardize(x[idx][:,cols]),k,stable_seed(k,r));scores.append(ari(base[idx],trial));ix=np.ix_(idx,idx);co[ix]+=trial[:,None]==trial;seen[ix]+=1
 return {"stability_mean_ari":float(np.mean(scores)),"stability_min_ari":float(np.min(scores)),"stability_max_ari":float(np.max(scores))},np.divide(co,seen,out=np.full_like(co,np.nan),where=seen>0)
def clean(rows,features):
 values={n:np.asarray([np.nan if r.get(n) is None else float(r[n]) for r in rows]) for n in features};audit=[];keep=[]
 for n in sorted(features):
  x=values[n];cov=float(np.isfinite(x).mean());status='retained_pre_redundancy'
  if cov<CONFIG['coverage_minimum']:status='excluded_near_empty'
  elif not np.isfinite(x).any():status='excluded_no_finite'
  elif np.nanstd(x)==0:status='excluded_constant'
  else:keep.append(n)
  audit.append({'feature':n,'family':fam(n),'coverage':cov,'status':status})
 med={n:float(np.nanmedian(values[n])) for n in keep};mat=np.column_stack([np.where(np.isfinite(values[n]),values[n],med[n]) for n in keep]);selected=[]
 for i,n in enumerate(keep):
  if mat[:,i].std()==0:next(a for a in audit if a['feature']==n)['status']='excluded_constant_after_imputation';continue
  if not selected:selected.append(i);continue
  corr=[abs(np.corrcoef(mat[:,i],mat[:,j])[0,1]) for j in selected];z=max(corr)
  if z>=CONFIG['near_duplicate_abs_correlation']:next(a for a in audit if a['feature']==n)['status']='excluded_near_duplicate'
  elif z>=CONFIG['high_redundancy_abs_correlation']:next(a for a in audit if a['feature']==n)['status']='excluded_high_correlation'
  else:selected.append(i)
 names=[keep[i] for i in selected];return names,mat[:,selected],audit
def balance(x,names):
 x=standardize(x)
 for f in FAMILIES:
  ids=[i for i,n in enumerate(names) if fam(n)==f]
  if ids:x[:,ids]/=math.sqrt(len(ids))
 return x
def load(root:Path):
 m=json.loads((root/'manifest.json').read_text());files={Path(x['path']).name:x for x in m['output_files']}
 for name,x in files.items():
  p=root/name
  if digest(p)!=x['sha256']:raise ValueError('checksum '+name)
 return pq.read_table(root/'candidate_subsegments.parquet').to_pylist(),pq.read_table(root/'normalized_4h_sequences.parquet').to_pylist(),m
def summarize(sub,seq_cols):
 # The Stage 2a sequence is macro-oriented; flip exact directional primitives when the subsegment net is counter-to-macro.
 reverse=sub['net_move_direction_relative_to_macro']=='counter';directional_ok=abs(float(sub['net_log_move_leg_relative']))>CONFIG['orientation_zero_tolerance'];start,end=int(sub['start_index']),int(sub['end_index_exclusive']);rows=seq_cols[sub['segment_id']][start:end];out={}
 for n in seq_cols['_features']:
  vals=[]
  for r in rows:
   v=r.get(n)
   if v is not None and reverse and n in SIGNED:v=-float(v)
   if v is not None and reverse and n.endswith('_forward'):v=r.get(n.replace('_forward','_counter'))
   elif v is not None and reverse and n.endswith('_counter'):v=r.get(n.replace('_counter','_forward'))
   vals.append(np.nan if v is None else float(v))
  a=np.asarray(vals)
  # Directional features are intentionally absent for ambiguous net movement.
  if not directional_ok and (n in SIGNED or n.endswith(('_forward','_counter'))):a[:]=np.nan
  for stat,v in [('mean',np.nanmean(a)),('std',np.nanstd(a)),('p25',np.nanquantile(a,.25)),('p75',np.nanquantile(a,.75))]:out[f'{n}__{stat}']=None if not np.isfinite(v) else float(v)
 return out,directional_ok
def build(data:Path,repo:Path):
 began=time.perf_counter();root=data/'research/macro_within_leg_stage2a';subs,seq,source=load(root);outroot=data/'research/macro_subsegment_types_stage2b'
 if outroot.exists():raise FileExistsError(outroot)
 tmp=outroot.parent/f'.{outroot.name}.build-{uuid.uuid4().hex}';tmp.mkdir(parents=True)
 try:
  features=[x for x in seq[0] if x not in META and isinstance(seq[0].get(x),(int,float))]
  by={'_features':features}
  for r in seq:by.setdefault(r['segment_id'],[]).append(r)
  population=[];excluded=[]
  for s in subs:
   strong=(s['start_boundary_support'] is None or s['start_boundary_support']>=CONFIG['strong_boundary_support']) and (s['end_boundary_support'] is None or s['end_boundary_support']>=CONFIG['strong_boundary_support'])
   vals,orient=summarize(s,by);row={**s,**vals,'orientation_unambiguous':orient,'primary_boundary_eligible':strong}
   if not orient:excluded.append({'subsegment_id':s['subsegment_id'],'reason':'ambiguous_net_move_orientation'})
   else:population.append(row)
  primary=[r for r in population if r['primary_boundary_eligible']];weak=[r for r in population if not r['primary_boundary_eligible']]
  summary_features=sorted(k for k in primary[0] if '__' in k and k.rsplit('__',1)[1] in {'mean','std','p25','p75'})
  names,raw,audit=clean(primary,summary_features);x=balance(raw,names)
  if not np.isfinite(x).all():raise ValueError('nonfinite matrix')
  pca=np.linalg.svd(x,full_matrices=False)[1]**2/max(len(x)-1,1);share=pca/pca.sum();dist=distance(x);clusterability={'hopkins':hopkins(x),'pc1_variance':float(share[0]),'pc1_pc2_variance':float(share[:2].sum()),'pairwise_distance_median':float(np.median(dist[np.triu_indices(len(x),1)]))}
  diagnostics=[];solutions={};coassign={}
  for k in CONFIG['k_values']:
   lab,cent=kmeans(x,k,stable_seed('kmeans',k));st,co=stability(x,lab,k);sil=silhouette(x,lab);sizes=[int((lab==c).sum()) for c in range(k)];re,_=kmeans(x,k,stable_seed('kmeans',k));repro=bool(np.array_equal(lab,re));row={'k':k,'cluster_sizes':json.dumps(sizes),'smallest_cluster':min(sizes),'silhouette':sil,'fixed_seed_reproducible':repro,**st};diagnostics.append(row);solutions[k]=(lab,cent);coassign[k]=co
  supported=clusterability['hopkins']>=CONFIG['supported_hopkins'];good=[d for d in diagnostics if d['silhouette']>=CONFIG['supported_silhouette'] and d['stability_mean_ari']>=CONFIG['supported_stability'] and d['smallest_cluster']>=5]
  preferred=max(good,key=lambda d:(d['stability_mean_ari'],d['silhouette']))['k'] if supported and good else None
  ambiguity=[d['k'] for d in good if preferred is not None and d['stability_mean_ari']>=next(q for q in good if q['k']==preferred)['stability_mean_ari']-.05 and d['silhouette']>=next(q for q in good if q['k']==preferred)['silhouette']-.05]
  result={'status':'preferred' if preferred is not None and len(ambiguity)==1 else 'ambiguous' if good else 'unsupported','preferred_k':preferred,'plausible_k':ambiguity,'clusterability_supported':supported,'reason':'no_solution_clears_separation_and_stability_thresholds' if not good else 'multiple_close_solutions' if len(ambiguity)>1 else 'single_solution_clears_thresholds'}
  # Preserve all limited candidate assignments as evidence even when the data
  # do not justify declaring a movement-type solution.
  candidate_assignments=[]
  for k,(labels,_) in solutions.items():
   candidate_assignments.extend({'subsegment_id':r['subsegment_id'],'k':k,'candidate_cluster':int(z)} for r,z in zip(primary,labels))
  reference=max(diagnostics,key=lambda d:(d['stability_mean_ari'],d['silhouette']))['k']
  result['coassignment_reference_k']=reference
  reference_co=coassign[reference]
  pairs=[{'subsegment_id_a':primary[i]['subsegment_id'],'subsegment_id_b':primary[j]['subsegment_id'],'coassignment':None if math.isnan(reference_co[i,j]) else float(reference_co[i,j]),'reference_k':reference} for i in range(len(primary)) for j in range(len(primary))]
  save_parquet(tmp/'coassignment_matrix.parquet',pairs)
  assignments=[];profiles=[];weak_sensitivity=[]
  if preferred is not None:
   lab,cent=solutions[preferred];order=np.argsort(cent[:,0]);remap={int(old):int(new) for new,old in enumerate(order)};lab=np.array([remap[int(z)] for z in lab]);co=coassign[preferred]
   for r,z in zip(primary,lab):assignments.append({'subsegment_id':r['subsegment_id'],'analysis_population':'primary','type':f'Type {chr(65+z)}','cluster':int(z),'candle_count':r['candle_count'],'duration_hours':r['duration_hours'],'parent_macro_segment_id':r['segment_id'],'boundary_support_min':min(v for v in [r['start_boundary_support'],r['end_boundary_support']] if v is not None) if any(v is not None for v in [r['start_boundary_support'],r['end_boundary_support']]) else None})
   for c in range(preferred):
    ids=np.where(lab==c)[0];diff=cent[order[c]]-x.mean(0);top=np.argsort(abs(diff))[-5:][::-1]
    for i in top:profiles.append({'type':f'Type {chr(65+c)}','count':len(ids),'feature':names[i],'family':fam(names[i]),'center_difference_standardized':float(diff[i]),'median':float(np.median(raw[ids,i])),'p25':float(np.quantile(raw[ids,i],.25)),'p75':float(np.quantile(raw[ids,i],.75))})
   # Same retained space, primary scaling; fitting with weak-boundary rows is sensitivity only.
   if weak:
    med=np.nanmedian(raw,0);wm=np.array([[np.nan if r.get(n) is None else float(r[n]) for n in names] for r in weak]);wm=np.where(np.isfinite(wm),wm,med);mean=raw.mean(0);scale=raw.std(0);scale[scale==0]=1;wx=(wm-mean)/scale
    for f in FAMILIES:
     ids=[i for i,n in enumerate(names) if fam(n)==f]
     if ids:wx[:,ids]/=math.sqrt(len(ids))
    comb=np.vstack([x,wx]);cl,_=kmeans(comb,preferred,stable_seed('weak',preferred));weak_sensitivity.append({'k':preferred,'primary_ari_when_weak_included':ari(lab,cl[:len(lab)]),'weak_boundary_rows':len(weak)})
  if preferred is None: weak_sensitivity.append({'status':'not_assessed_no_preferred_solution','reference_k':reference,'weak_boundary_rows':len(weak)})
  # Metadata-only confounder audit, deliberately after clustering.
  conf=[]
  if assignments:
   label=np.array([a['cluster'] for a in assignments],float)
   for field in ('candle_count','duration_hours','boundary_support_min'):
    v=np.asarray([np.nan if a[field] is None else float(a[field]) for a in assignments]);mask=np.isfinite(v);conf.append({'variable':field,'metric':'eta_squared_cluster_membership','value':float(np.var([v[label==c].mean() for c in set(label)])/np.var(v[mask])) if mask.any() and np.var(v[mask]) else None,'samples':int(mask.sum())})
  qa={'status':'PASS','source_subsegments':len(subs),'primary_rows':len(primary),'weak_boundary_rows':len(weak),'excluded_rows':len(excluded),'duplicate_analyzed_ids':len({r['subsegment_id'] for r in primary})!=len(primary),'predictor_identity_leakage':sorted(set(names)&{'segment_id','subsegment_id','timestamp','candle_count','duration_hours'}),'labels_or_fibtime_used':False,'matrix_finite':bool(np.isfinite(x).all()),'fixed_seed_rerun':True,'empty_clusters':False if preferred is None else any((solutions[preferred][0]==c).sum()==0 for c in range(preferred))}
  if qa['duplicate_analyzed_ids'] or qa['predictor_identity_leakage'] or not qa['matrix_finite'] or qa['empty_clusters']:raise RuntimeError(qa)
  save_parquet(tmp/'analysis_population.parquet',[{'subsegment_id':r['subsegment_id'],'population':'primary' if r['primary_boundary_eligible'] else 'weak_boundary_sensitivity','orientation_unambiguous':r['orientation_unambiguous'],'parent_macro_segment_id':r['segment_id'],'candle_count':r['candle_count'],'duration_hours':r['duration_hours']} for r in population]);save_csv(tmp/'retained_features.csv',audit);save_json(tmp/'clusterability_diagnostics.json',clusterability);save_csv(tmp/'candidate_k_diagnostics.csv',diagnostics);save_json(tmp/'preferred_or_ambiguous_solution.json',result);save_parquet(tmp/'candidate_cluster_assignments.parquet',candidate_assignments);save_parquet(tmp/'cluster_assignments.parquet',assignments);save_csv(tmp/'cluster_assignments_status.csv',[{'status':'preferred_solution' if preferred is not None else 'no_preferred_solution','preferred_k':preferred}]);save_csv(tmp/'cluster_profiles.csv',profiles);save_csv(tmp/'weak_boundary_sensitivity.csv',weak_sensitivity);save_csv(tmp/'confounder_report.csv',conf);save_csv(tmp/'excluded_subsegments.csv',excluded);save_json(tmp/'qa.json',qa)
  files=[]
  for p in sorted(tmp.iterdir()):
   if p.is_file():files.append({'path':str(outroot/p.name),'bytes':p.stat().st_size,'sha256':digest(p)})
  manifest={'schema_version':'macro-subsegment-types-stage2b-v1','build_timestamp_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'source_stage2a_manifest':str(root/'manifest.json'),'source_stage2a_manifest_sha256':digest(root/'manifest.json'),'config':CONFIG,'predictors':names,'labels_used':False,'semantic_cluster_names_used':False,'qa':qa,'output_files':files,'code_version':{'git_commit_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'pipeline_sha256':digest(Path(__file__))}}
  save_json(tmp/'manifest.json',manifest);os.replace(tmp,outroot);return {'status':'PASS','path':str(outroot),'primary':len(primary),'weak':len(weak),'excluded':len(excluded),'preferred':preferred,'runtime_seconds':round(time.perf_counter()-began,3)}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
def stamp(data,commit):
 p=data/'research/macro_subsegment_types_stage2b/manifest.json';x=json.loads(p.read_text());x['code_version']['git_commit']=commit;save_json(p,x)
def main():
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,required=True);a.add_argument('--repo-root',type=Path,default=Path.cwd());a.add_argument('--stamp-git-commit');z=a.parse_args()
 if z.stamp_git_commit:stamp(z.data_root,z.stamp_git_commit);print(json.dumps({'stamped_git_commit':z.stamp_git_commit}))
 else:print(json.dumps(build(z.data_root,z.repo_root),indent=2))
if __name__=='__main__':main()
