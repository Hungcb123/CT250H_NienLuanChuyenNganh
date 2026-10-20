"""Adaptive-target specialist/feature ablation with inner-only model choice.

No label or mixture-weight search. All outer history is inspected development.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from lightgbm import LGBMClassifier
import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_tuning import dynamic_inner_score, assert_dynamic_inner_timing, dynamic_error_tables
from audit_regime_expert_selection import fold_f1

ROOT = Path(__file__).resolve().parent
PARAMS = dict(n_estimators=150, learning_rate=.03, max_depth=3, num_leaves=7,
              min_child_samples=50, colsample_bytree=.7, reg_alpha=.1, reg_lambda=1.,
              random_state=42, n_jobs=2, verbosity=-1, class_weight='balanced')
CONFIGS = [(architecture, features) for features in ['core', 'directional']
           for architecture in ['multiclass', 'ovr', 'hierarchical']]


def directional_features(index):
    price = index.Price.astype(float)
    r = np.log(price).diff()
    sigma = r.rolling(20, min_periods=20).std(ddof=1).replace(0, np.nan)
    data = {'Date': index.Date}
    for h in [3,5,10,20,60]:
        data[f'momentum_z{h}'] = np.log(price/price.shift(h))/(sigma*np.sqrt(h))
    shock = r/sigma.shift(1)
    down_energy = r.clip(upper=0).pow(2).rolling(20, min_periods=20).sum()
    all_energy = r.pow(2).rolling(20, min_periods=20).sum().replace(0, np.nan)
    data.update(shock_now=shock, shock_lag1=shock.shift(1), shock_lag2=shock.shift(2),
        downside_energy_share20=down_energy/all_energy,
        negative_share5=(r<0).astype(float).rolling(5,min_periods=5).mean(),
        negative_share20=(r<0).astype(float).rolling(20,min_periods=20).mean(),
        volatility5_20=r.rolling(5,min_periods=5).std(ddof=1)/sigma,
        drawdown_z20=np.log(price/price.rolling(20,min_periods=20).max())/(sigma*np.sqrt(20)),
        drawdown_z60=np.log(price/price.rolling(60,min_periods=60).max())/(sigma*np.sqrt(60)),
        skew20=r.rolling(20,min_periods=20).skew())
    data['momentum_acceleration'] = data['momentum_z5']-data['momentum_z20']
    return pd.DataFrame(data).replace([np.inf,-np.inf],np.nan)


def fit_directional_heads(train, valid, names, architecture):
    if train.label_end_date.max() >= valid.Date.min():
        raise ValueError('Unmatured specialist labels')
    X, V = train[names].to_numpy(dtype=np.float32), valid[names].to_numpy(dtype=np.float32)
    y = train.label.to_numpy(dtype=int)
    if set(y) != {0,1,2} or not np.isfinite(X).all() or not np.isfinite(V).all():
        raise ValueError('Invalid specialist training cohort')
    if architecture == 'multiclass':
        model = LGBMClassifier(**PARAMS).fit(X,y)
        scores = model.predict_proba(V)
    elif architecture == 'ovr':
        scores = np.column_stack([LGBMClassifier(**PARAMS).fit(X,(y==c).astype(int)).predict_proba(V)[:,1] for c in [0,1,2]])
        scores /= scores.sum(axis=1,keepdims=True)
    elif architecture == 'hierarchical':
        move = y!=1
        movement = LGBMClassifier(**PARAMS).fit(X,move.astype(int)).predict_proba(V)[:,1]
        direction = LGBMClassifier(**PARAMS).fit(X[move],(y[move]==2).astype(int)).predict_proba(V)[:,1]
        scores = np.column_stack([movement*(1-direction),1-movement,movement*direction])
    else:
        raise ValueError('Unknown specialist architecture')
    if not np.isfinite(scores).all() or (scores<0).any():
        raise ValueError('Invalid specialist scores')
    np.testing.assert_allclose(scores.sum(axis=1),1.,atol=1e-12)
    return scores


def run_directional_specialists(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Parent helper/source changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','long','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--inner-splits','3','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frames[20],book,'vol_1sigma')
    added=directional_features(index)
    extra=[c for c in added if c!='Date']
    frame=frame.merge(added,on='Date',how='left',sort=False,validate='one_to_one')
    if not np.isfinite(frame[extra]).all().all():raise ValueError('New feature would shrink frozen training/evaluation cohort')
    job=jobs[0]
    names={'core':job['names'],'directional':job['names']+extra}
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in job['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:
        np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    control=pd.read_csv(old/'blend_expanding_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:
        np.testing.assert_array_equal(control[key],base[key])
    source_paths=[args.parent_dir/'plan.json',args.parent_dir/'report.json',old/'blend_expanding_predictions.csv',
        old/'trend_predictions.csv',old/'risk_predictions.csv',old/'expanding_raw_mapped_predictions.csv',old/'expanding_normalized_mapped_predictions.csv',
        ROOT/'experiment_regime_dynamic_tuning.py',Path(__file__)]
    source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    plan.update(mode='adaptive_directional_specialists_DEVELOPMENT',created_at=datetime.now(timezone.utc).isoformat(),
        source_hashes=source_hashes,parameters=PARAMS,configs=CONFIGS,feature_names=names,
        label_rule=parent['label_rule'],optuna=None,
        primary='inner_selected_blend: choose among six by purged-inner directional robustness objective, then fixed half old blend + half specialist scores',
        selection='0.5*mean inner macroF1 + .25*worst inner macroF1 + .25*min(mean inner bearF1, mean inner bullF1); deterministic config order for ties',
        secondary='equal_pool_blend: equal all SIX specialists then fixed half old blend. Individual variants are diagnostic only, no outer winner promotion.',
        acceptance='Mean F1 +.01, worst fold >= old, mean bear/bull F1 >= old, MCC increase, >=3 fold wins; paired20/60 lower interval >0 for provisional robust evidence.',
        timing='All heads require label_end_date strictly before prediction boundary; hierarchical direction head trains only on mature non-neutral rows.',
        score_semantics='Balanced-head and hierarchical scores are decision scores, NOT calibrated probabilities.',
        assumptions='No new target threshold, weight grid, missing-date removal, OHLC/volume data, independent holdout or deployment. Repeatedly inspected historical development.')
    output=args.output_dir or ROOT/'reports/regime_directional'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    # Reconstruct the incumbent scores, rather than treating its predictions as probabilities.
    classifier_scores=[]
    for group in ['trend','risk']:
        rows=pd.read_csv(old/(group+'_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        classifier_scores.append(rows[experts.PROBS].to_numpy())
    density_scores=[]
    for target in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);density_scores.append(score)
    incumbent=.5*np.mean(classifier_scores,axis=0)+.5*np.mean(density_scores,axis=0)
    np.testing.assert_array_equal(incumbent.argmax(axis=1),control.prediction)
    records={a+'_'+f:[] for a,f in CONFIGS}
    selected_chunks=[];selection=[]
    for outer in job['folds']:
        tuning=frame.iloc[outer['tune']].reset_index(drop=True)
        folds=exp.base.purged_folds(tuning,3)
        boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tuning,folds,boundary)
        inner=[]
        for architecture,features in CONFIGS:
            metrics=[]
            for train_ids,valid_ids in folds:
                train,valid=tuning.iloc[train_ids],tuning.iloc[valid_ids]
                score=fit_directional_heads(train,valid,names[features],architecture)
                metrics.append(exp.base.classification_metrics(valid.label,score.argmax(axis=1),train.label))
            inner.append(dict(name=architecture+'_'+features,score=dynamic_inner_score(metrics),folds=metrics))
        chosen=max(inner,key=lambda r:r['score'])['name']
        selection.append(dict(fold=outer['fold'],chosen=chosen,outer_boundary=str(boundary.date()),
            latest_tuning_label_end=str(tuning.label_end_date.max().date()),candidates=inner))
        (output/'inner_selection.json').write_text(json.dumps(selection,indent=2)+'\n')
        print('Fold '+str(outer['fold'])+' inner choice: '+chosen,flush=True)
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            for architecture,features in CONFIGS:
                name=architecture+'_'+features
                score=fit_directional_heads(train,valid,names[features],architecture)
                rows=valid[['Date','label_end_date','label','future_return']].copy()
                rows[experts.PROBS]=score
                rows['majority']=np.bincount(train.label,minlength=3).argmax()
                rows['outer_fold'],rows['refit_block']=outer['fold'],number
                rows['train_label_end']=str(train.label_end_date.max().date())
                records[name].append(rows)
                if name==chosen:selected_chunks.append(rows.copy())
        print('Fold '+str(outer['fold'])+' refits complete',flush=True)
        for name,chunks in records.items():pd.concat(chunks,ignore_index=True).to_csv(output/(name+'_scores.csv'),index=False)
    selected=pd.concat(selected_chunks,ignore_index=True)
    matrices={name:pd.concat(chunks,ignore_index=True)[experts.PROBS].to_numpy() for name,chunks in records.items()}
    matrices['inner_selected']=selected[experts.PROBS].to_numpy()
    matrices['equal_pool']=np.mean([matrices[a+'_'+f] for a,f in CONFIGS],axis=0)
    source=selected
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(source[key],base[key])
    matrices.update({name+'_blend':.5*value+.5*incumbent for name,value in list(matrices.items())})
    matrices['incumbent']=incumbent
    results=[];predictions={}
    for name,score in matrices.items():
        np.testing.assert_allclose(score.sum(axis=1),1.,atol=1e-12)
        result,rows=experts.expert_metrics(name,source,score.argmax(axis=1))
        results.append(result);predictions[name]=rows
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
    dynamic_error_tables(predictions,book,output)
    baseline_result=next(r for r in results if r['candidate']=='incumbent')
    groups=[np.flatnonzero(base.outer_fold.to_numpy()==n) for n in sorted(base.outer_fold.unique())]
    y=base.label.to_numpy(dtype=int);comparisons=[];intervals=[]
    for name in ['inner_selected_blend','equal_pool_blend']:
        r=next(r for r in results if r['candidate']==name)
        class_mean=lambda row,c:float(np.mean([f['per_class'][c]['f1-score'] for f in row['folds']]))
        wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(r['folds'],baseline_result['folds']))
        passed=(r['mean_f1']>=baseline_result['mean_f1']+.01 and r['worst_f1']>=baseline_result['worst_f1']
            and r['mean_mcc']>baseline_result['mean_mcc'] and wins>=3
            and all(class_mean(r,c)>=class_mean(baseline_result,c) for c in ['bear','bull']))
        for length in [20,60]:
            rng=np.random.default_rng(42);deltas=[]
            for _ in range(1000):
                ids=[]
                for group in groups:
                    starts=rng.integers(0,len(group),size=int(np.ceil(len(group)/length)))
                    ids.append(group[((starts[:,None]+np.arange(length))%len(group)).ravel()[:len(group)]])
                deltas.append(fold_f1(y,predictions[name].prediction.to_numpy(),ids)-fold_f1(y,control.prediction.to_numpy(),ids))
            low,high=np.quantile(deltas,[.025,.975])
            intervals.append(dict(candidate=name,block=length,delta=r['mean_f1']-baseline_result['mean_f1'],low=float(low),high=float(high)))
        comparisons.append(dict(candidate=name,point_screen=bool(passed),fold_wins=wins,
            provisional_robust_evidence=bool(passed and all(row['low']>0 for row in intervals if row['candidate']==name))))
    (output/'report.json').write_text(json.dumps(dict(role='Historical DEVELOPMENT, primary inner-selected blend; individual variants diagnostic only',results=results,comparisons=comparisons,paired_intervals=intervals),indent=2)+'\n')
    pd.DataFrame([{k:r[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']} for r in results]).to_csv(output/'comparison.csv',index=False)
    print(pd.read_csv(output/'comparison.csv').to_string(index=False),flush=True)
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_directional_specialists()
