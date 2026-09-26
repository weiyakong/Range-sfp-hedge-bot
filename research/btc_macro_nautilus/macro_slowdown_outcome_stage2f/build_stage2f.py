#!/usr/bin/env python3
"""Pre-outcome comparison of slowdown subsegments using frozen Stage 2E data."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,shutil,subprocess,time,uuid
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
SEED=20260926
CURRENT=['persistence','alternation','volatility','volume','trade_count','overlap','speed','geometry','net_move']
DELTAS=['delta_persistence','delta_alternation','delta_volatility','delta_volume','delta_trade_count','delta_overlap_body_overlap_mean','delta_speed_movement_rate_mean','delta_candle_geometry_mean','delta_net_log_move']
REFINED_DELTAS=['delta_directional_persistence_alternation_mean','delta_volatility_volume_activity_mean','delta_counter_move_share']
RATIOS=['ratio_persistence','ratio_alternation','ratio_volatility','ratio_volume','ratio_trade_count']
STANDARDIZED=['z_delta_persistence','z_delta_alternation','z_delta_volatility','z_delta_volume','z_delta_trade_count']
# The model uses complete, non-duplicated raw measures. Ratios and standardized
# magnitudes remain available to the required univariate analysis.
PRED=CURRENT+DELTAS
ANALYSIS_FEATURES=PRED+REFINED_DELTAS+RATIOS+STANDARDIZED
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
def write_checksums(root):
 targets=sorted(p for p in root.iterdir() if p.name!='checksums.sha256')
 (root/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in targets))
 lines=(root/'checksums.sha256').read_text().splitlines()
 return len(targets)==len(lines) and all(sha(p)==line.split(maxsplit=1)[0] and p.name==line.split(maxsplit=1)[1].strip() for p,line in zip(targets,lines))
def cliff(a,b):
 return float(np.mean(np.sign(np.asarray(a)[:,None]-np.asarray(b)[None,:])))
def bootstrap(a,b,seed,reps=1000):
 rng=np.random.default_rng(seed);v=[]
 for _ in range(reps):v.append(float(np.median(rng.choice(a,len(a),True))-np.median(rng.choice(b,len(b),True))))
 return float(np.quantile(v,.025)),float(np.quantile(v,.975))
def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-30,30)))
def fit(x,y,lam=.1):
 w=np.zeros(x.shape[1]+1)
 for _ in range(500):
  p=sigmoid(w[0]+x@w[1:]);g0=np.mean(p-y);g=x.T@(p-y)/len(y)+lam*w[1:];w-=.05*np.r_[g0,g]
 return w
def auc(y,p):
 pos=p[y==1];neg=p[y==0];return float((np.sum(pos[:,None]>neg)+.5*np.sum(pos[:,None]==neg))/(len(pos)*len(neg))) if len(pos) and len(neg) else None
def build(data,repo):
 begun=time.perf_counter();e2=data/'research/macro_within_leg_stage2e_feature_separation';a2=data/'research/macro_within_leg_stage2a';out=data/'research/macro_slowdown_outcome_stage2f'
 if out.exists():raise FileExistsError(out)
 tmp=out.parent/f'.{out.name}.build-{uuid.uuid4().hex}';tmp.mkdir(parents=True)
 try:
  feat=pq.read_table(e2/'separated_subsegment_features.parquet').to_pylist();trans=pq.read_table(e2/'refined_adjacent_transitions.parquet').to_pylist();orig=pq.read_table(a2/'candidate_subsegments.parquet').to_pylist();fm={r['subsegment_id']:r for r in feat};om={r['subsegment_id']:r for r in orig};tm={r['to_subsegment_id']:r for r in trans};groups={}
  for r in feat:groups.setdefault(r['parent_macro_leg_id'],[]).append(r)
  population=[];edges=0;slowdown_candidates=0;ambiguous=0;missing=0
  for leg,rows in groups.items():
   rows.sort(key=lambda r:om[r['subsegment_id']]['subsegment_order'])
   for i,cur in enumerate(rows):
    if i==0 or i==len(rows)-1:edges+=1;continue
    inbound=tm[cur['subsegment_id']]
    if inbound['delta_speed_movement_rate_mean']>=0:continue
    slowdown_candidates+=1
    nxt=rows[i+1];cd=cur['net_direction_relative'];nd=nxt['net_direction_relative']
    if cd not in {'forward','counter'} or nd not in {'forward','counter'}:ambiguous+=1;continue
    outcome='CONTINUATION' if cd==nd else 'REVERSAL';base=om[cur['subsegment_id']]
    row={'slowdown_id':cur['subsegment_id'],'parent_macro_leg_id':leg,'previous_subsegment_id':rows[i-1]['subsegment_id'],'next_subsegment_id':nxt['subsegment_id'],'outcome':outcome,'outcome_binary':1 if outcome=='REVERSAL' else 0,'boundary_population':inbound['boundary_class'],'calendar_era':str(base['start_timestamp'].year),'parent_direction':cur['macro_direction'],'candle_count':cur['candle_count'],'duration_hours':cur['duration_hours'],'counter_move_share':base['counter_move_share'],**{n:cur[n] for n in CURRENT},**{n:inbound[n] for n in DELTAS+REFINED_DELTAS+RATIOS+STANDARDIZED}}
    if any(row[n] is None or not np.isfinite(row[n]) for n in PRED):missing+=1;continue
    population.append(row)
  strong=[r for r in population if r['boundary_population']=='strong'];weak=[r for r in population if r['boundary_population']=='weak']
  uni=[];effects=[];boots=[]
  for n in ANALYSIS_FEATURES+['counter_move_share','candle_count','duration_hours']:
   a=np.asarray([r[n] for r in strong if r['outcome']=='CONTINUATION' and r[n] is not None],float);b=np.asarray([r[n] for r in strong if r['outcome']=='REVERSAL' and r[n] is not None],float)
   if len(a)==0 or len(b)==0:
    uni.append({'feature':n,'status':'not_assessed_no_values','continuation_n':len(a),'reversal_n':len(b)});effects.append({'feature':n,'status':'not_assessed_no_values'});boots.append({'feature':n,'status':'not_assessed_no_values','repetitions':0});continue
   lo,hi=bootstrap(a,b,SEED+len(uni));d=cliff(a,b);uni.append({'feature':n,'continuation_median':float(np.median(a)),'continuation_p25':float(np.quantile(a,.25)),'continuation_p75':float(np.quantile(a,.75)),'reversal_median':float(np.median(b)),'reversal_p25':float(np.quantile(b,.25)),'reversal_p75':float(np.quantile(b,.75)),'median_difference_cont_minus_rev':float(np.median(a)-np.median(b)),'distribution_overlap_proxy':1-abs(d)})
   effects.append({'feature':n,'cliffs_delta_cont_minus_rev':d,'absolute_effect':abs(d),'direction':'higher_continuation' if d>0 else 'higher_reversal' if d<0 else 'equal'});boots.append({'feature':n,'bootstrap_median_difference_ci_low':lo,'bootstrap_median_difference_ci_high':hi,'excludes_zero':lo>0 or hi<0,'repetitions':1000})
  X=np.asarray([[r[n] for n in PRED] for r in strong],float);y=np.asarray([r['outcome_binary'] for r in strong]);legs=np.asarray([r['parent_macro_leg_id'] for r in strong]);pred=np.full(len(y),np.nan);fold=[];grouped_disjoint=True
  for leg in sorted(set(legs)):
   te=legs==leg;train=~te
   grouped_disjoint=grouped_disjoint and not np.any(legs[train]==leg) and np.all(legs[te]==leg)
   if len(set(y[train]))<2:continue
   mean=X[train].mean(0);sd=X[train].std(0);sd[sd==0]=1;w=fit((X[train]-mean)/sd,y[train]);pred[te]=sigmoid(w[0]+((X[te]-mean)/sd)@w[1:]);fold.append({'held_out_macro_leg':leg,'rows':int(te.sum()),'reversal_rows':int(y[te].sum()),'mean_probability':float(np.mean(pred[te]))})
  valid=np.isfinite(pred);a=auc(y[valid],pred[valid]);bal=float(((pred[valid][y[valid]==1]>=.5).mean()+(pred[valid][y[valid]==0]<.5).mean())/2);base_rate=float(y.mean())
  full_mean=X.mean(0);full_sd=X.std(0);full_sd[full_sd==0]=1;full_w=fit((X-full_mean)/full_sd,y)
  coefficients=sorted(({'feature':n,'standardized_coefficient_for_reversal':float(v)} for n,v in zip(PRED,full_w[1:])),key=lambda r:-abs(r['standardized_coefficient_for_reversal']))
  multi={'method':'fixed ridge logistic regression; lambda=0.1; leave-one-macro-leg-out','predictors':PRED,'rows':len(strong),'macro_legs':len(set(legs)),'pooled_grouped_auc':a,'pooled_grouped_balanced_accuracy':bal,'reversal_rate':base_rate,'full_fit_intercept':float(full_w[0]),'full_fit_standardized_coefficients':coefficients,'coefficient_note':'Descriptive full-population coefficients; performance metrics are from held-out macro legs. Positive coefficients indicate REVERSAL.','future_features_used':False}
  sens=[]
  for n in ANALYSIS_FEATURES:
   for pop,rows in [('strong',strong),('weak',weak)]:
    aa=[r[n] for r in rows if r['outcome']=='CONTINUATION' and r[n] is not None];bb=[r[n] for r in rows if r['outcome']=='REVERSAL' and r[n] is not None];sens.append({'feature':n,'population':pop,'continuation_n':len(aa),'reversal_n':len(bb),'cliffs_delta':cliff(aa,bb) if aa and bb else None,'status':'assessed' if aa and bb else 'not_assessed_no_values'})
  eras=Counter((r['calendar_era'],r['outcome']) for r in strong);dirs=Counter((r['parent_direction'],r['outcome']) for r in strong)
  def strata_table(counts,label):
   lines=[f'## {label}','',f'| {label} | Continuation | Reversal | Reversal rate |','|---|---:|---:|---:|']
   for value in sorted({k[0] for k in counts}):
    c=counts[(value,'CONTINUATION')];rv=counts[(value,'REVERSAL')];lines.append(f'| {value} | {c} | {rv} | {rv/(c+rv):.3f} |')
   return '\n'.join(lines)
  conf=("# Confounder report\n\n"
        "Metadata were excluded from the multivariate predictor matrix. Leave-one-macro-leg-out validation prevents observations from one leg appearing in both train and test. Calendar year and parent direction distributions are shown below; duration and candle-count effects are reported in `univariate_outcome_comparison.csv`. Volatility remains a continuous pre-outcome feature (rather than an outcome-derived regime label) and its robust effect is reported in the same output.\n\n"
        +strata_table(eras,'Calendar year')+'\n\n'+strata_table(dirs,'Parent direction')+'\n')
  representatives=[]
  for r in population[:3]:
   prev=fm[r['previous_subsegment_id']];cur=fm[r['slowdown_id']];nxt=fm[r['next_subsegment_id']]
   recalculated_delta=cur['speed']-prev['speed']
   recalculated_outcome='CONTINUATION' if cur['net_direction_relative']==nxt['net_direction_relative'] else 'REVERSAL'
   representatives.append({'slowdown_id':r['slowdown_id'],'recalculated_delta_speed':recalculated_delta,'stored_delta_speed':r['delta_speed_movement_rate_mean'],'recalculated_outcome':recalculated_outcome,'passed':bool(np.isclose(recalculated_delta,r['delta_speed_movement_rate_mean']) and recalculated_outcome==r['outcome'])})
  qa={'status':'PASS','slowdown_candidates_with_previous_and_next':slowdown_candidates,'slowdowns_with_binary_outcome':len(population),'continuation':sum(r['outcome']=='CONTINUATION' for r in population),'reversal':sum(r['outcome']=='REVERSAL' for r in population),'strong':len(strong),'weak':len(weak),'edge_excluded':edges,'ambiguous_outcome_excluded':ambiguous,'missing_model_predictor_excluded':missing,'all_delta_speed_negative':all(r['delta_speed_movement_rate_mean']<0 for r in population),'same_leg_triples':all(fm[r['previous_subsegment_id']]['parent_macro_leg_id']==r['parent_macro_leg_id']==fm[r['next_subsegment_id']]['parent_macro_leg_id'] for r in population),'duplicate_ids':len({r['slowdown_id'] for r in population})!=len(population),'future_predictor_leakage':False,'strong_weak_separate':len(strong)+len(weak)==len(population),'finite_model_predictors':bool(np.isfinite(np.asarray([[r[n] for n in PRED] for r in population])).all()),'nullable_validated_features_only':all(r[n] is None or np.isfinite(r[n]) for r in population for n in ANALYSIS_FEATURES),'grouped_validation_disjoint':bool(grouped_disjoint),'representative_recompute':representatives}
  if not all([qa['all_delta_speed_negative'],qa['same_leg_triples'],not qa['duplicate_ids'],qa['strong_weak_separate'],qa['finite_model_predictors'],qa['nullable_validated_features_only'],qa['grouped_validation_disjoint'],all(x['passed'] for x in qa['representative_recompute'])]):raise RuntimeError(qa)
  pqw(tmp/'slowdown_population.parquet',population);pqw(tmp/'slowdown_outcomes.parquet',[{k:r[k] for k in ('slowdown_id','parent_macro_leg_id','next_subsegment_id','outcome','boundary_population')} for r in population]);csvw(tmp/'univariate_outcome_comparison.csv',uni);csvw(tmp/'effect_sizes.csv',sorted(effects,key=lambda r:-r.get('absolute_effect',-1)));csvw(tmp/'bootstrap_diagnostics.csv',boots);jw(tmp/'multivariate_diagnostic.json',multi);csvw(tmp/'grouped_validation_results.csv',fold);csvw(tmp/'strong_vs_weak_sensitivity.csv',sens);(tmp/'confounder_report.md').write_text(conf);jw(tmp/'qa.json',qa)
  files=[{'path':str(out/p.name),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(tmp.iterdir())];man={'schema_version':'slowdown-outcome-stage2f-v1','operational_slowdown':'validated delta_speed_movement_rate_mean < 0','source_stage2e_manifest':str(e2/'feature_separation_manifest.json'),'source_stage2e_manifest_sha256':sha(e2/'feature_separation_manifest.json'),'model_predictors':PRED,'univariate_features':ANALYSIS_FEATURES,'qa':qa,'output_files':files,'checksum_index':'checksums.sha256','runtime_seconds':round(time.perf_counter()-begun,3),'code_version':{'git_commit_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'pipeline_sha256':sha(Path(__file__))}};jw(tmp/'manifest.json',man)
  checksum_verified=write_checksums(tmp)
  if not checksum_verified:raise RuntimeError('checksum verification failed')
  os.replace(tmp,out);return {'status':'PASS','path':str(out),'population':len(population),'strong':len(strong),'weak':len(weak),'checksums_verified':checksum_verified,'runtime_seconds':man['runtime_seconds']}
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise
def stamp(data,commit):
 out=data/'research/macro_slowdown_outcome_stage2f';manifest=out/'manifest.json';man=json.loads(manifest.read_text());man['code_version']['git_commit_at_build']=commit;jw(manifest,man)
 verified=write_checksums(out)
 if not verified:raise RuntimeError('checksum verification failed after commit stamp')
 return {'status':'PASS','path':str(out),'git_commit_at_build':commit,'checksums_verified':True}
def main():
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,required=True);a.add_argument('--repo-root',type=Path,default=Path.cwd());a.add_argument('--stamp-git-commit');z=a.parse_args();result=stamp(z.data_root,z.stamp_git_commit) if z.stamp_git_commit else build(z.data_root,z.repo_root);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
