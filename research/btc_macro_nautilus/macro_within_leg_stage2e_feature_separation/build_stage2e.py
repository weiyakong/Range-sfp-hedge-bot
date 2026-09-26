#!/usr/bin/env python3
"""Refine frozen Stage 2c transitions with approved separated atomic components."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,shutil,subprocess,time,uuid
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
NEW=['persistence','alternation','volatility','volume','trade_count'];EPS=np.finfo(float).eps
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def pqw(p,r):
 if r:pq.write_table(pa.Table.from_pylist(r),p,compression='zstd')
def csvw(p,r):
 fs=sorted({k for x in r for k in x}) if r else ['status'];t=p.with_name(p.name+'.partial')
 with t.open('w',newline='') as f:w=csv.DictWriter(f,fs);w.writeheader();w.writerows(r)
 os.replace(t,p)
def jw(p,x):
 t=p.with_name(p.name+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,default=str)+'\n');os.replace(t,p)
def sg(x):return '+' if x>0 else '-' if x<0 else '0'
def ratio(a,b):return None if abs(a)<=EPS else b/a
def build(data,repo):
 began=time.perf_counter();a2=data/'research/macro_within_leg_stage2a';c2=data/'research/macro_within_leg_stage2c';d2=data/'research/macro_within_leg_stage2d_sol_analysis';out=data/'research/macro_within_leg_stage2e_feature_separation'
 if out.exists():raise FileExistsError(out)
 tmp=out.parent/f'.{out.name}.build-{uuid.uuid4().hex}';tmp.mkdir(parents=True)
 try:
  subs=pq.read_table(a2/'candidate_subsegments.parquet').to_pylist();seq=pq.read_table(a2/'normalized_4h_sequences.parquet').to_pylist();tr=pq.read_table(c2/'adjacent_transitions.parquet').to_pylist();patterns=list(csv.DictReader((d2/'recurring_transition_patterns.csv').open()));motifs=list(csv.DictReader((d2/'recurring_motifs_2t.csv').open()))
  atomroot=data/'features/BTCUSDT/4h_atomic';am=json.loads((atomroot/'manifest.json').read_text());files=[Path(x['path']) for x in am['output_files']];atomic=pq.read_table(files,columns=['timestamp','close_step_sign','alternation_indicator','log_full_range','complete_volume','complete_trade_count']).to_pylist();byts={r['timestamp']:r for r in atomic}
  byseg={};
  for r in seq:byseg.setdefault(r['segment_id'],[]).append(r)
  sm={r['subsegment_id']:r for r in subs};features=[];checks=[]
  for s in subs:
   rows=sorted(byseg[s['segment_id']],key=lambda r:r['sequence_index'])[s['start_index']:s['end_index_exclusive']];ar=[byts[r['candle_timestamp']] for r in rows]
   direction=(1 if s['macro_direction']=='up' else -1)*(1 if s['net_move_direction_relative_to_macro']=='forward' else -1)
   persist=[x['close_step_sign']*direction for x in ar if x['close_step_sign'] is not None];alt=[float(x['alternation_indicator']) for x in ar if x['alternation_indicator'] is not None]
   def mean(k):
    v=[float(x[k]) for x in ar if x[k] is not None];return None if not v else float(np.mean(v))
   f={'subsegment_id':s['subsegment_id'],'parent_macro_leg_id':s['segment_id'],'candle_count':s['candle_count'],'duration_hours':s['duration_hours'],'macro_direction':s['macro_direction'],'net_direction_relative':s['net_move_direction_relative_to_macro'],'persistence':None if not persist else float(np.mean(persist)),'alternation':None if not alt else float(np.mean(alt)),'volatility':mean('log_full_range'),'volume':mean('complete_volume'),'trade_count':mean('complete_trade_count'),'overlap':s['overlap_body_overlap_mean'],'speed':s['speed_movement_rate_mean'],'geometry':s['candle_geometry_mean'],'net_move':s['net_log_move_leg_relative']};features.append(f)
   if len(checks)<3:checks.append({'subsegment_id':s['subsegment_id'],'atomic_rows':len(ar),'expected_candles':s['candle_count'],'passed':len(ar)==s['candle_count']})
  fm={r['subsegment_id']:r for r in features};ref=[]
  for r in tr:
   a,b=fm[r['from_subsegment_id']],fm[r['to_subsegment_id']];o={**r}
   for n in NEW:
    o['delta_'+n]=None if a[n] is None or b[n] is None else b[n]-a[n];o['ratio_'+n]=None if a[n] is None or b[n] is None else ratio(a[n],b[n])
   ref.append(o)
  for n in NEW:
   vals=np.array([np.nan if r['delta_'+n] is None else r['delta_'+n] for r in ref]);m=np.nanmean(vals);s=np.nanstd(vals);s=1 if s==0 else s
   for r,v in zip(ref,vals):r['z_delta_'+n]=None if not np.isfinite(v) else float((v-m)/s)
  pmap={r['pattern_id']:r for r in patterns if r['pattern_id'] in [f'Transition Pattern {c}' for c in 'ABCDEFG']};sigmap={r['signature']:r for r in pmap.values()};
  ret=[];mag=[]
  for pid,p in pmap.items():
   g=[r for r in ref if r['boundary_class']=='strong' and '|'.join(sg(r['delta_'+n]) for n in ['overlap_body_overlap_mean','directional_persistence_alternation_mean','speed_movement_rate_mean','candle_geometry_mean','volatility_volume_activity_mean','net_log_move'])+'|'+('C' if r['direction_continuation'] else 'R')==p['signature']]
   combos=Counter('|'.join(sg(r['delta_'+n]) for n in NEW) for r in g);modal=max(combos.values())/len(g) if g else 0;status='SUPPORTED' if modal>=.8 else 'MODIFIED' if modal>=.5 else 'SPLITS' if g else 'NOT SUPPORTED'
   ret.append({'pattern':pid,'status':status,'support':len(g),'macro_leg_support':len({r['parent_macro_leg_id'] for r in g}),'refined_sign_combinations':len(combos),'modal_refined_combination_share':modal,**{f'mean_delta_{n}':float(np.nanmean([r['delta_'+n] for r in g])) for n in NEW}})
   for n in NEW:
    v=[r['delta_'+n] for r in g if r['delta_'+n] is not None];mag.append({'item':pid,'feature':n,'n':len(v),'median_delta':float(np.median(v)) if v else None,'p25_delta':float(np.quantile(v,.25)) if v else None,'p75_delta':float(np.quantile(v,.75)) if v else None,'min_delta':float(np.min(v)) if v else None,'max_delta':float(np.max(v)) if v else None})
  mr=[]
  for m in [x for x in motifs if x['recurring'].lower()=='true']:
   sig=m['signature'];parts=sig.split(' > ');ts=[]
   for leg in {r['parent_macro_leg_id'] for r in ref}:
    z=sorted([r for r in ref if r['parent_macro_leg_id']==leg],key=lambda r:r['ordinal_transition_index'])
    for i in range(len(z)-1):
     ss=[]
     for r in z[i:i+2]:ss.append('|'.join(sg(r['delta_'+n]) for n in ['overlap_body_overlap_mean','directional_persistence_alternation_mean','speed_movement_rate_mean','candle_geometry_mean','volatility_volume_activity_mean','net_log_move'])+'|'+('C' if r['direction_continuation'] else 'R'))
     if ss==parts:ts.append(z[i:i+2])
   mr.append({'motif':m['provisional_interpretation'],'status':'SUPPORTED' if ts else 'NOT SUPPORTED','support':len(ts),'macro_leg_support':len({x[0]['parent_macro_leg_id'] for x in ts}),'mean_delta_persistence':float(np.nanmean([np.nanmean([x['delta_persistence'] for x in t]) for t in ts])) if ts else None,'mean_delta_alternation':float(np.nanmean([np.nanmean([x['delta_alternation'] for x in t]) for t in ts])) if ts else None,'mean_delta_volatility':float(np.nanmean([np.nanmean([x['delta_volatility'] for x in t]) for t in ts])) if ts else None,'mean_delta_volume':float(np.nanmean([np.nanmean([x['delta_volume'] for x in t]) for t in ts])) if ts else None,'mean_delta_trade_count':float(np.nanmean([np.nanmean([x['delta_trade_count'] for x in t]) for t in ts])) if ts else None})
  sens=[]
  for pid,p in pmap.items():
   base=[r for r in ref if '|'.join(sg(r['delta_'+n]) for n in ['overlap_body_overlap_mean','directional_persistence_alternation_mean','speed_movement_rate_mean','candle_geometry_mean','volatility_volume_activity_mean','net_log_move'])+'|'+('C' if r['direction_continuation'] else 'R')==p['signature']];sens.append({'pattern':pid,'strong':sum(r['boundary_class']=='strong' for r in base),'weak':sum(r['boundary_class']=='weak' for r in base)})
  length=np.asarray([r['candle_count'] for r in features],float)
  intensity_length_correlation={n:float(np.corrcoef(length,np.asarray([r[n] for r in features],float))[0,1]) for n in ('volume','trade_count')}
  ratio_check=all(r['ratio_'+n] is None or np.isclose(r['ratio_'+n],fm[r['to_subsegment_id']][n]/fm[r['from_subsegment_id']][n]) for r in ref for n in NEW if fm[r['from_subsegment_id']][n] is not None and fm[r['to_subsegment_id']][n] is not None and abs(fm[r['from_subsegment_id']][n])>EPS)
  qa={'status':'PASS','subsegments':len(features),'transitions':len(ref),'strong':sum(r['boundary_class']=='strong' for r in ref),'weak':sum(r['boundary_class']=='weak' for r in ref),'duplicate_subsegments':len(fm)!=len(features),'duplicate_transitions':len({r['transition_id'] for r in ref})!=len(ref),'cross_leg':any(sm[r['from_subsegment_id']]['segment_id']!=sm[r['to_subsegment_id']]['segment_id'] for r in ref),'finite':all(np.isfinite(r['z_delta_'+n]) for r in ref for n in NEW if r['z_delta_'+n] is not None),'membership_checks':checks,'unaffected_dimensions_preserved':all(r['delta_overlap_body_overlap_mean'] is not None for r in ref),'activity_measure':'mean_per_4h_candle_not_total','activity_intensity_vs_candle_count_pearson':intensity_length_correlation,'ratio_check':ratio_check}
  if qa['subsegments']!=533 or qa['transitions']!=454 or qa['strong']!=367 or qa['weak']!=87 or qa['duplicate_subsegments'] or qa['duplicate_transitions'] or qa['cross_leg'] or not qa['finite'] or not qa['ratio_check'] or not all(x['passed'] for x in checks):raise RuntimeError(qa)
  pqw(tmp/'separated_subsegment_features.parquet',features);pqw(tmp/'refined_adjacent_transitions.parquet',ref);csvw(tmp/'pattern_A_G_retest.csv',ret);csvw(tmp/'motif_retest.csv',mr);csvw(tmp/'magnitude_profiles.csv',mag);csvw(tmp/'strong_vs_weak_sensitivity.csv',sens);jw(tmp/'qa.json',qa)
  files=[{'path':str(out/p.name),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(tmp.iterdir())];man={'schema_version':'stage2e-feature-separation-v1','source_stage2a':str(a2/'manifest.json'),'source_stage2c':str(c2/'manifest.json'),'approved_measures':{'persistence':'mean direction-relative close_step_sign','alternation':'mean alternation_indicator','volatility':'mean log_full_range','volume':'mean complete_volume per 4H candle','trade_count':'mean complete_trade_count per 4H candle'},'ratio_rule':'current/previous; null if abs(previous)<=machine epsilon','qa':qa,'output_files':files,'runtime_seconds':round(time.perf_counter()-began,3),'code_version':{'git_commit_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'pipeline_sha256':sha(Path(__file__))}};jw(tmp/'feature_separation_manifest.json',man);os.replace(tmp,out);return {'status':'PASS','path':str(out),'runtime_seconds':man['runtime_seconds']}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
def main():
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,required=True);a.add_argument('--repo-root',type=Path,default=Path.cwd());z=a.parse_args();print(json.dumps(build(z.data_root,z.repo_root),indent=2))
if __name__=='__main__':main()
