"""Frozen-plan causal probability audit, historical DEVELOPMENT only.

The .420 point-decision policy is immutable. Calibrated argmax is a different
reported decision, never silently substituted for that policy.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import export_regime_multiclass_scores as source
native=source.native
ROOT=native.ROOT
PLAN=native.CONTRACT.parent/'probability_evaluation_plan.json'
CLASSES=['bear','side','bull']
PREFIXES={'raw_decision':'decision_score_','raw_mass':'component_mass_'}


def outcome_book(index):
    future=index.Price.shift(-20)/index.Price-1
    label=pd.Series(pd.NA,index=index.index,dtype='Int64');known=future.notna()
    label.loc[known]=np.where(future[known]<-.05,0,np.where(future[known]>.05,2,1))
    return pd.DataFrame(dict(Date=index.Date,label_end_date=index.Date.shift(-20),label=label))


def causal_prior(book,boundary,rows=504):
    known=book.loc[book.label.notna()&(book.Date<boundary)&(book.label_end_date<boundary)].tail(rows)
    counts=np.bincount(known.label.to_numpy(dtype=int),minlength=3)
    return (counts+1)/(len(known)+3),dict(n=len(known),latest_label_end=str(known.label_end_date.max()) if len(known) else None,counts=counts.tolist())


def calibration_inputs(frame,prefix,pool):
    values=frame[[prefix+c for c in CLASSES]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid score vector')
    np.testing.assert_allclose(values.sum(axis=1),1.,atol=1e-10)
    logs=np.log(np.clip(values,1e-6,1.));logs-=logs.mean(axis=1,keepdims=True)
    codes=pd.Categorical(frame.selected_expert,categories=pool).codes
    if (codes<0).any():raise ValueError('Unknown frozen expert category')
    return np.column_stack([logs,np.eye(len(pool))[codes]])


def predict_calibration(state,X):
    scaled=(np.asarray(X)-np.asarray(state['mean']))/np.asarray(state['scale'])
    score=scaled@np.asarray(state['coef']).T+np.asarray(state['intercept'])
    score-=score.max(axis=1,keepdims=True);values=np.exp(score)
    return values/values.sum(axis=1,keepdims=True)


def fit_calibration(history,boundary,prefix,pool,config):
    if history.Date.max()>=boundary or history.label_end_date.max()>=boundary:raise ValueError('Unmatured calibration labels')
    if set(history.label)!={0,1,2}:raise ValueError('Calibration lacks a class')
    X=calibration_inputs(history,prefix,pool);y=history.label.to_numpy(dtype=int)
    model=make_pipeline(StandardScaler(),LogisticRegression(C=config['C'],solver=config['solver'],max_iter=config['max_iter'],
                         class_weight=config['class_weight'],random_state=config['random_state']))
    model.fit(X,y)
    scaler,learner=model[0],model[1]
    np.testing.assert_array_equal(learner.classes_,[0,1,2])
    state=dict(mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),coef=learner.coef_.tolist(),intercept=learner.intercept_.tolist(),classes=[0,1,2])
    np.testing.assert_allclose(predict_calibration(state,X),model.predict_proba(X),rtol=1e-12,atol=1e-12)
    return state


def prepare_probability_audit(contract_path,plan_path):
    contract,lock,_=source.verify_native_artifacts(contract_path)
    plan=json.loads(Path(plan_path).read_text())
    if plan['contract_sha256']!=native.sha(contract_path) or plan['native_lock_sha256']!=native.sha(Path(contract_path).parent/'native_runtime_lock.json'):raise ValueError('Probability plan/candidate mismatch')
    archive=source.resolved(plan['native_archive'])
    if native.sha(archive)!=plan['archive_sha256'] or native.sha(archive.parent/'archive_manifest.json')!=plan['archive_manifest_sha256']:raise ValueError('Frozen probability archive changed')
    rows=pd.read_csv(archive,parse_dates=['Date','label_end_date'])
    if len(rows)!=1560 or rows.Date.duplicated().any() or not rows.Date.is_monotonic_increasing:raise ValueError('Changed frozen forecast cohort')
    index,index_audit=native.features.load_market_data(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv')
    if index_audit['sha256']!=contract['source_data_hashes']['VNINDEX']:raise ValueError('Probability outcome source changed')
    book=outcome_book(index)
    matched=rows[['Date']].merge(book,on='Date',validate='one_to_one',sort=False)
    for name in ['Date','label_end_date','label']:np.testing.assert_array_equal(matched[name].to_numpy(),rows[name].to_numpy())
    for prefix in PREFIXES.values():calibration_inputs(rows,prefix,contract['selector_pool'])
    return rows,book,index.Date,contract,plan


def run_probability_stream(rows,book,calendar,pool,plan):
    config=plan['calibration'];positions=pd.DatetimeIndex(calendar).get_indexer(rows.Date)
    anchor=pd.DatetimeIndex(calendar).get_indexer([pd.Timestamp(config['anchor'])])[0]
    if anchor<0 or (positions<anchor).any():raise ValueError('Invalid calibration calendar')
    buckets=(positions-anchor)//config['refit_market_sessions']
    predictions={'causal_prior':np.zeros((len(rows),3))}
    for name,prefix in PREFIXES.items():
        predictions[name]=rows[[prefix+c for c in CLASSES]].to_numpy(dtype=float)
        predictions['cal_'+name]=np.zeros((len(rows),3))
    active=np.zeros(len(rows),dtype=bool);audits=[]
    for bucket in np.unique(buckets):
        ids=np.flatnonzero(buckets==bucket);boundary=rows.Date.iloc[ids[0]]
        history=rows.loc[(rows.Date<boundary)&(rows.label_end_date<boundary)].tail(config['history_rows'])
        counts=history.label.value_counts().reindex([0,1,2],fill_value=0).to_numpy()
        ready=len(history)>=config['min_rows'] and (counts>=config['min_class_count']).all()
        prior,prior_info=causal_prior(book,boundary,config['history_rows'])
        predictions['causal_prior'][ids]=prior
        state=dict(Date=str(boundary.date()),n=len(history),latest_label_end=str(history.label_end_date.max()) if len(history) else None,
                   class_counts=counts.tolist(),active=bool(ready),baseline_prior=prior.tolist(),baseline_training=prior_info,models={})
        for name,prefix in PREFIXES.items():
            if ready:
                model=fit_calibration(history,boundary,prefix,pool,config)
                probabilities=predict_calibration(model,calibration_inputs(rows.iloc[ids],prefix,pool))
                state['models'][name]=model
            else:probabilities=np.tile(prior,(len(ids),1))
            predictions['cal_'+name][ids]=probabilities
        active[ids]=ready;audits.append(state)
    for values in predictions.values():
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid probability output')
        np.testing.assert_allclose(values.sum(axis=1),1.)
    return predictions,active,audits


def proper_losses(actual,probabilities):
    actual=np.asarray(actual,dtype=int);p=np.asarray(probabilities,dtype=float)
    truth=np.eye(3)[actual]
    return dict(brier=np.square(p-truth).sum(axis=1),log_loss=-np.log(np.clip(p[np.arange(len(p)),actual],np.finfo(float).eps,1.)))


def probability_metrics(rows,p,mask):
    ids=np.flatnonzero(mask)
    if len(ids)==0:return dict(n=0,brier=None,log_loss=None,mean_fold_argmax_f1=None)
    losses=proper_losses(rows.label.to_numpy()[ids],p[ids])
    fold_f1=[]
    for fold in sorted(rows.outer_fold.unique()):
        selected=ids[rows.outer_fold.iloc[ids].to_numpy()==fold]
        if len(selected):fold_f1.append(float(f1_score(rows.label.iloc[selected],p[selected].argmax(axis=1),labels=[0,1,2],average='macro',zero_division=0)))
    return dict(n=len(ids),brier=float(losses['brier'].mean()),log_loss=float(losses['log_loss'].mean()),mean_fold_argmax_f1=float(np.mean(fold_f1)),
                frozen_decision_disagreement=float((p[ids].argmax(axis=1)!=rows.prediction.iloc[ids].to_numpy()).mean()))


def bootstrap_probability_delta(difference,active,folds,length,repeats=1000):
    rng=np.random.default_rng(42);groups=[np.flatnonzero(folds==fold) for fold in sorted(np.unique(folds))];values=[]
    for _ in range(repeats):
        sample=[]
        for ids in groups:
            start=rng.integers(0,len(ids),size=int(np.ceil(len(ids)/length)))
            sample.extend(ids[((start[:,None]+np.arange(length))%len(ids)).ravel()[:len(ids)]])
        sample=np.asarray(sample,dtype=int);sample=sample[active[sample]]
        if len(sample):values.append(float(difference[sample].mean()))
    if not values:return dict(low=None,high=None)
    low,high=np.quantile(values,[.025,.975])
    return dict(low=float(low),high=float(high))


def write_probability_report(rows,predictions,active,audits,output):
    all_mask=np.ones(len(rows),dtype=bool);summary={};losses={};intervals=[];curves=[]
    for name,p in predictions.items():
        losses[name]=proper_losses(rows.label.to_numpy(dtype=int),p)
        summary[name]=dict(all=probability_metrics(rows,p,all_mask),active=probability_metrics(rows,p,active),folds=[])
        for fold in sorted(rows.outer_fold.unique()):
            mask=active&(rows.outer_fold.to_numpy()==fold)
            summary[name]['folds'].append(dict(fold=int(fold),**probability_metrics(rows,p,mask)))
        for code,cls in enumerate(CLASSES):
            bins=np.minimum((p[:,code]*10).astype(int),9)
            for b in range(10):
                ids=np.flatnonzero(active&(bins==b))
                curves.append(dict(method=name,cls=cls,bin=b,n=len(ids),mean_probability=float(p[ids,code].mean()) if len(ids) else None,observed_frequency=float((rows.label.iloc[ids].to_numpy()==code).mean()) if len(ids) else None))
    screens={}
    for name in ['cal_raw_decision','cal_raw_mass']:
        for metric in ['brier','log_loss']:
            difference=losses['causal_prior'][metric]-losses[name][metric]
            for block in [20,60]:
                intervals.append(dict(method=name,metric=metric,block_sessions=block,point_improvement=float(difference[active].mean()) if active.any() else None,
                                      **bootstrap_probability_delta(difference,active,rows.outer_fold.to_numpy(),block)))
        own,base=summary[name]['active'],summary['causal_prior']['active']
        wins=sum(a['n']>0 and a['brier']<b['brier'] for a,b in zip(summary[name]['folds'],summary['causal_prior']['folds']))
        point=active.any() and own['brier']<base['brier'] and own['log_loss']<base['log_loss'] and wins>=3
        paired=all(row['low'] is not None and row['low']>0 for row in intervals if row['method']==name)
        screens[name]=dict(point_screen=bool(point),brier_fold_wins=wins,paired_screen=bool(paired),passed=bool(point and paired))
    output=Path(output)
    report=dict(role='Historical causal probability DEVELOPMENT, not independent acceptance',n=len(rows),active_calibration_rows=int(active.sum()),
                fallback_rows=int((~active).sum()),frozen_point_mean_fold_f1=float(np.mean([f1_score(part.label,part.prediction,labels=[0,1,2],average='macro',zero_division=0) for _,part in rows.groupby('outer_fold')])),
                summary=summary,intervals=intervals,screens=screens,disclosure='Calibrated argmax differs from class-balanced frozen point decision. No policy replacement or confidence certification.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'calibration_states.json').write_text(json.dumps(audits,indent=2)+'\n')
    pd.DataFrame(curves).to_csv(output/'reliability_bins.csv',index=False)
    flat=[dict(method=name,scope=scope,**values[scope]) for name,values in summary.items() for scope in ['all','active']]
    pd.DataFrame(flat).to_csv(output/'comparison.csv',index=False)
    exported=rows[['Date','label_end_date','label','outer_fold','prediction']].copy();exported['calibration_active']=active
    for name,p in predictions.items():
        for code,cls in enumerate(CLASSES):exported[name+'_'+cls]=p[:,code]
    exported.to_csv(output/'probabilities.csv',index=False)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=native.CONTRACT)
    parser.add_argument('--plan',type=Path,default=PLAN)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    rows,book,calendar,contract,plan=prepare_probability_audit(args.contract,args.plan)
    output=args.output_dir or ROOT/'reports/regime_probability_audit'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    saved=dict(plan,source_sha256=native.sha(__file__),plan_sha256=native.sha(args.plan))
    (output/'plan.json').write_text(json.dumps(saved,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    probabilities,active,audits=run_probability_stream(rows,book,calendar,contract['selector_pool'],plan)
    report=write_probability_report(rows,probabilities,active,audits,output)
    print(pd.read_csv(output/'comparison.csv').to_string(index=False),flush=True)
    print(json.dumps(report['screens'],indent=2),flush=True)
    print('Done. Probability DEVELOPMENT audit; frozen decisions unchanged. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
