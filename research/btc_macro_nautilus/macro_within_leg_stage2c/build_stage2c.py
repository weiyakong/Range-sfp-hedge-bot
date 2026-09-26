#!/usr/bin/env python3
"""Chronological transition/motif diagnostics; no subsegment clustering."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,shutil,subprocess,time,uuid
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
B=['overlap_body_overlap_mean','directional_persistence_alternation_mean','speed_movement_rate_mean','candle_geometry_mean','volatility_volume_activity_mean','counter_move_share'];S=.60
def h(p):
 x=hashlib.sha256()
 with open(p,'rb') as f:
  for z in iter(lambda:f.read(1048576),b''):x.update(z)
 return x.hexdigest()
def pp(p,r):
 if r:pq.write_table(pa.Table.from_pylist(r),p,compression='zstd')
def cc(p,r):
 ks=sorted({k for x in r for k in x}) if r else ['status'];t=p.with_name(p.name+'.partial')
 with t.open('w',newline='') as f:w=csv.DictWriter(f,ks);w.writeheader();w.writerows(r)
 os.replace(t,p)
def jj(p,x):
 t=p.with_name(p.name+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,default=str)+'\n');os.replace(t,p)
def st(x):
 s=x.std(0);s[s==0]=1;return(x-x.mean(0))/s
def dd(x):
 q=(x*x).sum(1,keepdims=True);return np.sqrt(np.maximum(q+q.T-2*x@x.T,0))
def nn(rows,x,key):
 d=dd(x);np.fill_diagonal(d,np.inf);return[{key:r[key],'nearest_'+key:rows[np.argmin(d[i])][key],'distance':float(d[i].min())}for i,r in enumerate(rows)]
def run(data,repo):
 t0=time.perf_counter();src=data/'research/macro_within_leg_stage2a';out=data/'research/macro_within_leg_stage2c'
 if out.exists():raise FileExistsError(out)
 tmp=out.parent/f'.{out.name}.{uuid.uuid4().hex}';tmp.mkdir(parents=True)
 try:
  subs=pq.read_table(src/'candidate_subsegments.parquet').to_pylist();g={}
  for r in subs:g.setdefault(r['segment_id'],[]).append(r)
  seq=[];tr=[]
  for leg,a in sorted(g.items()):
   a.sort(key=lambda x:x['subsegment_order'])
   for i,r in enumerate(a):seq.append({'parent_macro_leg_id':leg,'subsegment_id':r['subsegment_id'],'ordinal_index':i+1,'start_time':r['start_timestamp'],'end_time':r['end_timestamp'],'candle_count':r['candle_count'],'net_log_move':r['net_log_move_leg_relative'],'direction_relative_to_parent':r['net_move_direction_relative_to_macro'],'boundary_before':r['start_boundary_support'],'boundary_after':r['end_boundary_support'],**{n:r.get(n)for n in B}})
   for i,(a0,a1)in enumerate(zip(a,a[1:]),1):
    b=a0['end_boundary_support'];r={'transition_id':f'{leg}_T{i:02d}','parent_macro_leg_id':leg,'from_subsegment_id':a0['subsegment_id'],'to_subsegment_id':a1['subsegment_id'],'ordinal_transition_index':i,'boundary_support':b,'boundary_class':'strong'if b is not None and b>=S else'weak','same_direction_relative_to_parent':a0['net_move_direction_relative_to_macro']==a1['net_move_direction_relative_to_macro'],'direction_continuation':a0['net_move_direction_relative_to_macro']==a1['net_move_direction_relative_to_macro'],'duration_ratio':a1['duration_hours']/a0['duration_hours'],'candle_count_ratio':a1['candle_count']/a0['candle_count'],'delta_net_log_move':a1['net_log_move_leg_relative']-a0['net_log_move_leg_relative']}
    for n in B:r['delta_'+n]=None if a0.get(n)is None or a1.get(n)is None else a1[n]-a0[n]
    tr.append(r)
  cand=['delta_'+n for n in B]+['delta_net_log_move'];v={n:np.array([np.nan if r[n]is None else r[n]for r in tr])for n in cand};keep=[];audit=[]
  for n,z in v.items():
   q=np.isfinite(z).mean();status='retained'if q>=.8 and np.nanstd(z)>0 else'dropped_near_empty_or_constant';audit.append({'feature':n,'coverage':float(q),'status':status});
   if status=='retained':keep.append(n)
  raw=np.column_stack([np.where(np.isfinite(v[n]),v[n],np.nanmedian(v[n]))for n in keep]);sel=[]
  for i,n in enumerate(keep):
   if not sel:sel.append(i);continue
   if max(abs(np.corrcoef(raw[:,i],raw[:,j])[0,1])for j in sel)>=.98:next(x for x in audit if x['feature']==n)['status']='dropped_high_correlation'
   else:sel.append(i)
  names=[keep[i]for i in sel];x=st(raw[:,sel]);fm=[{**r,**{'z_'+n:float(x[i,j])for j,n in enumerate(names)}}for i,r in enumerate(tr)]
  motifs=[];sim=[];stab=[];idx={r['transition_id']:i for i,r in enumerate(tr)}
  for L in(2,3):
   ms=[]
   for leg in g:
    z=[r for r in tr if r['parent_macro_leg_id']==leg]
    for i in range(len(z)-L+1):ms.append({'motif_id':f'{leg}_M{L}_{i+1:02d}','parent_macro_leg_id':leg,'transition_length':L,'ordinal_start':i+1,'transition_ids':'|'.join(q['transition_id']for q in z[i:i+L]),'boundary_classes':'|'.join(q['boundary_class']for q in z[i:i+L])})
   motifs+=ms
   if ms:
    mx=np.vstack([x[[idx[z]for z in r['transition_ids'].split('|')]].ravel()for r in ms]);z=st(mx);sim+=nn(ms,z,'motif_id');rng=np.random.default_rng(20260926+L);base=np.argmin(np.where(np.eye(len(ms)),np.inf,dd(z)),1);a=[]
    for _ in range(10):
     c=rng.choice(z.shape[1],max(2,int(.8*z.shape[1])),False);q=np.argmin(np.where(np.eye(len(ms)),np.inf,dd(st(mx[:,c]))),1);a.append((q==base).mean())
    stab.append({'transition_length':L,'motifs':len(ms),'nearest_neighbor_feature_subset_agreement_mean':float(np.mean(a)),'minimum':float(np.min(a))})
  conf=[]
  for j,n in enumerate(names):
   for f in('duration_ratio','candle_count_ratio','boundary_support'):
    z=np.array([np.nan if r[f]is None else r[f]for r in tr]);m=np.isfinite(z);conf.append({'transition_feature':n,'metadata':f,'spearman':None if m.sum()<3 else float(np.corrcoef(np.argsort(np.argsort(x[m,j])),np.argsort(np.argsort(z[m])))[0,1])})
  qa={'status':'PASS','macro_legs':len(g),'ordered_subsegments':len(seq),'transitions':len(tr),'strong_transitions':sum(r['boundary_class']=='strong'for r in tr),'weak_transitions':sum(r['boundary_class']=='weak'for r in tr),'duplicate_transition_ids':len({r['transition_id']for r in tr})!=len(tr),'cross_leg_transitions':False,'finite_matrix':bool(np.isfinite(x).all())}
  if qa['duplicate_transition_ids']or not qa['finite_matrix']:raise RuntimeError(qa)
  pp(tmp/'ordered_subsegment_sequences.parquet',seq);pp(tmp/'adjacent_transitions.parquet',tr);pp(tmp/'transition_feature_matrix.parquet',fm);pp(tmp/'transition_similarity.parquet',nn(tr,x,'transition_id'));pp(tmp/'short_motifs.parquet',motifs);pp(tmp/'motif_similarity.parquet',sim);cc(tmp/'motif_stability_diagnostics.csv',stab);cc(tmp/'transition_preprocessing_audit.csv',audit);cc(tmp/'confounder_report.csv',conf);cc(tmp/'strong_vs_weak_sensitivity.csv',[{'population':'strong','transitions':qa['strong_transitions']},{'population':'weak','transitions':qa['weak_transitions']}]);jj(tmp/'qa.json',qa)
  fs=[{'path':str(out/p.name),'bytes':p.stat().st_size,'sha256':h(p)}for p in sorted(tmp.iterdir())];man={'schema_version':'within-leg-stage2c-v1','source_stage2a_manifest':str(src/'manifest.json'),'source_stage2a_manifest_sha256':h(src/'manifest.json'),'predictors':names,'no_subsegment_clustering':True,'qa':qa,'output_files':fs,'runtime_seconds':round(time.perf_counter()-t0,3),'code_version':{'git_commit_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'pipeline_sha256':h(Path(__file__))}};jj(tmp/'manifest.json',man);os.replace(tmp,out);return{'status':'PASS','path':str(out),**qa,'runtime_seconds':man['runtime_seconds']}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,required=True);a.add_argument('--repo-root',type=Path,default=Path.cwd());z=a.parse_args();print(json.dumps(run(z.data_root,z.repo_root),indent=2))
