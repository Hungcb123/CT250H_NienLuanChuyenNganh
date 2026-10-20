"""Causal decision adaptation of the frozen dynamic-target blend.

Primary rule fixed before evaluation: half incumbent, half equal four adapters.
All historical dates are inspected development, not an independent test.
"""
import argparse
from datetime import datetime,timezone
import hashlib
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score

import experiment_regime as exp
import experiment_regime_expert_selection as experts
import experiment_regime_labels as labels
from experiment_regime_dynamic_tuning import dynamic_error_tables
from audit_regime_expert_selection import fold_f1

ROOT=Path(__file__).resolve().parent
WINDOWS=[252,504]
GRID=[.5,.75,1.,1.5,2.]


def replay_adaptive_decisions(base,scores,features,calendar):
    scores=np.asarray(scores,dtype=float)
    features=np.asarray(features,dtype=float)
    if scores.shape!=(len(base),3) or not np.isfinite(scores).all() or not np.isfinite(features).all():
        raise ValueError('Invalid adapter input')
    positions=pd.DatetimeIndex(calendar).get_indexer(base.Date)
    if (positions<0).any():raise ValueError('Missing market date')
    clipped=np.log(np.clip(scores,1e-6,1.))
    X=np.column_stack([clipped-clipped.mean(axis=1,keepdims=True),features])
    values={f'{method}_{window}':[] for window in WINDOWS for method in ['weights','logistic']}
    states=[];models={};weights={};last_bucket=None
    buckets=(positions-positions[0])//20
    for row in range(len(base)):
        boundary=base.Date.iloc[row]
        if buckets[row]!=last_bucket:
            known=np.flatnonzero(((base.Date<boundary)&(base.label_end_date<boundary)).to_numpy())
            for window in WINDOWS:
                ids=known[-window:]
                counts=np.bincount(base.label.iloc[ids].to_numpy(dtype=int),minlength=3) if len(ids) else np.zeros(3,dtype=int)
                ready=len(ids)>=126 and len(counts)==3 and (counts>=5).all()
                weights[window]=np.ones(3);models[window]=None
                info=dict(Date=str(boundary.date()),window=window,n_history=len(ids),class_counts=counts.tolist(),
                    latest_label_end=str(base.label_end_date.iloc[ids].max()) if len(ids) else None,ready=bool(ready))
                if ready:
                    y=base.label.iloc[ids].to_numpy(dtype=int)
                    best=f1_score(y,scores[ids].argmax(axis=1),labels=[0,1,2],average='macro',zero_division=0)
                    for bear,bull in product(GRID,repeat=2):
                        candidate=np.array([bear,1.,bull])
                        value=f1_score(y,(scores[ids]*candidate).argmax(axis=1),labels=[0,1,2],average='macro',zero_division=0)
                        value-=.005*np.square(np.log(candidate)).sum()
                        if value>best+1e-12:
                            weights[window],best=candidate,value
                    scaler=StandardScaler().fit(X[ids])
                    model=LogisticRegression(C=.1,class_weight='balanced',max_iter=2000,random_state=42)
                    model.fit(scaler.transform(X[ids]),y)
                    np.testing.assert_array_equal(model.classes_,[0,1,2])
                    models[window]=(scaler,model)
                    info.update(weights=weights[window].tolist(),regularized_past_f1=float(best),
                        scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),
                        coefficient=model.coef_.tolist(),intercept=model.intercept_.tolist())
                states.append(info)
            last_bucket=buckets[row]
        for window in WINDOWS:
            adjusted=scores[row]*weights[window]
            adjusted/=adjusted.sum()
            values[f'weights_{window}'].append(adjusted)
            pair=models[window]
            probability=pair[1].predict_proba(pair[0].transform(X[row:row+1]))[0] if pair else scores[row]
            values[f'logistic_{window}'].append(probability)
    values={name:np.asarray(rows) for name,rows in values.items()}
    values['pooled_adapter']=.5*scores+.5*np.mean(list(values.values()),axis=0)
    values['incumbent']=scores
    return values,states


def run_adaptive_decisions(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for path,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Parent source changed: '+path)
    index,audit=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    if audit['sha256']!=parent['input_hashes']['VNINDEX']:raise ValueError('Index changed')
    book=labels.build_label_book(index)
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    pieces=[];paths=[Path(__file__),args.parent_dir/'plan.json',ROOT/'experiment_regime_dynamic_tuning.py']
    for group in ['trend','risk']:
        path=old/(group+'_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        pieces.append(rows[experts.PROBS].to_numpy())
    densities=[]
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        mass=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        mass/=mass.sum(axis=1,keepdims=True);densities.append(mass)
    incumbent=.5*np.mean(pieces,axis=0)+.5*np.mean(densities,axis=0)
    path=old/'blend_expanding_predictions.csv';paths.append(path)
    np.testing.assert_array_equal(incumbent.argmax(axis=1),pd.read_csv(path).prediction)
    r=np.log(index.Price.astype(float)).diff()
    sigma=r.rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
    feature_frame=pd.DataFrame(dict(Date=index.Date,log_sigma=np.log(sigma),momentum_z20=np.log(index.Price/index.Price.shift(20))/sigma))
    joined=base[['Date']].merge(feature_frame,on='Date',validate='one_to_one')
    X=joined[['log_sigma','momentum_z20']].to_numpy()
    output=args.output_dir or ROOT/'reports/regime_adaptive_decisions'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='causal_dynamic_target_decision_adaptation_DEVELOPMENT',created_at=datetime.now(timezone.utc).isoformat(),
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},windows=WINDOWS,
        min_history=126,min_each_class=5,refit_raw_market_sessions=20,weight_grid=GRID,weight_penalty=.005,
        logistic=dict(C=.1,class_weight='balanced',scaler='training-only StandardScaler',inputs='CLR log incumbent scores, log known horizon sigma, normalized past20 return'),
        primary='pooled_adapter = .5 incumbent + .5 equal four adapters; standalone adapters diagnostic only',
        timing='Use ONLY archived OOF outcomes with label_end_date strictly before refresh; hold adapter until next20-session bucket; insufficient history -> incumbent.',
        score_semantics='Decision scores, NOT calibrated probabilities',
        acceptance='Mean F1 +.01, no decline worst fold or mean bear/bull F1, higher MCC, >=3 wins vs incumbent; both paired20/60 lower bounds >0 for provisional robust evidence.',
        caveat='Repeatedly inspected historical development; no independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    matrices,states=replay_adaptive_decisions(base,incumbent,X,index.Date)
    (output/'adapter_states.json').write_text(json.dumps(states,indent=2)+'\n')
    checks=[]
    for end in [390,780,1170,1460,1560]:
        prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_=replay_adaptive_decisions(prefix,incumbent[:end],X[:end],index.Date[index.Date<=cutoff])
        for name in matrices:np.testing.assert_allclose(actual[name],matrices[name][:end],atol=1e-12,rtol=1e-12)
        checks.append(dict(rows=end,future_label_corruption_invariant=True))
    results=[];predictions={}
    for name,score in matrices.items():
        result,rows=experts.expert_metrics(name,base,score.argmax(axis=1))
        results.append(result);predictions[name]=rows
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
    dynamic_error_tables(predictions,book,output)
    control=next(r for r in results if r['candidate']=='incumbent')
    candidate=next(r for r in results if r['candidate']=='pooled_adapter')
    class_mean=lambda r,c:float(np.mean([f['per_class'][c]['f1-score'] for f in r['folds']]))
    wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(candidate['folds'],control['folds']))
    passed=(candidate['mean_f1']>=control['mean_f1']+.01 and candidate['worst_f1']>=control['worst_f1']
        and candidate['mean_mcc']>control['mean_mcc'] and wins>=3
        and all(class_mean(candidate,c)>=class_mean(control,c) for c in ['bear','bull']))
    groups=[np.flatnonzero(base.outer_fold.to_numpy()==f) for f in sorted(base.outer_fold.unique())]
    y=base.label.to_numpy(dtype=int);intervals=[]
    for length in [20,60]:
        rng=np.random.default_rng(42);deltas=[]
        for _ in range(1000):
            ids=[]
            for group in groups:
                starts=rng.integers(0,len(group),size=int(np.ceil(len(group)/length)))
                ids.append(group[((starts[:,None]+np.arange(length))%len(group)).ravel()[:len(group)]])
            deltas.append(fold_f1(y,predictions['pooled_adapter'].prediction.to_numpy(),ids)-fold_f1(y,predictions['incumbent'].prediction.to_numpy(),ids))
        low,high=np.quantile(deltas,[.025,.975])
        intervals.append(dict(block=length,delta=candidate['mean_f1']-control['mean_f1'],low=float(low),high=float(high)))
    report=dict(role='Inspected historical DEVELOPMENT only',results=results,prefix_checks=checks,paired_intervals=intervals,
        comparison=dict(primary='pooled_adapter',fold_wins=wins,point_screen=bool(passed),provisional_robust_evidence=bool(passed and all(i['low']>0 for i in intervals))))
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    pd.DataFrame([{k:r[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']} for r in results]).to_csv(output/'comparison.csv',index=False)
    print(pd.read_csv(output/'comparison.csv').to_string(index=False),flush=True)
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_adaptive_decisions()
