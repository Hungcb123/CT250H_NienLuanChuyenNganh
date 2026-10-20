"""Fixed CatBoost joint-quantile ablation on ORIGINAL return features.

Primary: average old and new densities before the existing 50/50 classifier mix.
No new threshold, model/weight search or independent-test claim.
"""
from catboost import CatBoostRegressor
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from experiment_regime_directional import directional_features
from experiment_regime_dynamic_tuning import dynamic_error_tables
from audit_regime_expert_selection import fold_f1

ROOT=Path(__file__).resolve().parent
JOINT_PARAMETERS=dict(iterations=400,depth=4,learning_rate=.03,l2_leaf_reg=5.,
    random_seed=42,thread_count=2,verbose=False,allow_writing_files=False)


def fit_joint_return_quantiles(train,valid,names,normalized,specification):
    if train.label_end_date.max()>=valid.Date.min():
        raise ValueError('Unmatured joint-quantile target')
    target=train.future_log_return.to_numpy(dtype=float)
    if normalized:target=target/train.horizon_sigma.to_numpy()
    X,V=train[names].to_numpy(dtype=np.float32),valid[names].to_numpy(dtype=np.float32)
    if not all(np.isfinite(a).all() for a in [target,X,V]):
        raise ValueError('Nonfinite joint-quantile inputs')
    loss='MultiQuantile:alpha='+','.join(str(v) for v in specification['quantile_levels'])
    model=CatBoostRegressor(**JOINT_PARAMETERS,loss_function=loss)
    model.fit(X,target)
    points=np.asarray(model.predict(V),dtype=float)
    if points.shape!=(len(valid),len(specification['quantile_levels'])) or not np.isfinite(points).all():
        raise ValueError('Invalid joint quantile shape')
    crossings=int((np.diff(points,axis=1)<0).any(axis=1).sum())
    if normalized:points*=valid.horizon_sigma.to_numpy()[:,None]
    return None,np.sort(points,axis=1),crossings


def run_joint_quantiles(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent source changed: '+name)
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=density.exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frame,book,'vol_1sigma')
    new_features=directional_features(index)
    extra=[c for c in new_features if c!='Date']
    frame=frame.merge(new_features,on='Date',how='left',sort=False,validate='one_to_one')
    if not np.isfinite(frame[extra]).all().all():raise ValueError('New features would drop frozen cohort dates')
    job=jobs['expanding']
    feature_names=job['names']
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in job['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    classifiers=[];old_densities=[]
    for group in ['trend','risk']:
        rows=pd.read_csv(old/(group+'_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        classifiers.append(rows[experts.PROBS].to_numpy())
    for target in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_densities.append(score)
    classifier=np.mean(classifiers,axis=0);old_density=np.mean(old_densities,axis=0)
    incumbent=.5*classifier+.5*old_density
    old_predictions=pd.read_csv(old/'blend_expanding_predictions.csv')
    np.testing.assert_array_equal(incumbent.argmax(axis=1),old_predictions.prediction)
    paths=[Path(__file__),ROOT/'experiment_regime_directional.py',ROOT/'experiment_regime_dynamic_tuning.py',
        args.parent_dir/'plan.json',old/'trend_predictions.csv',old/'risk_predictions.csv',old/'blend_expanding_predictions.csv',
        old/'expanding_raw_mapped_predictions.csv',old/'expanding_normalized_mapped_predictions.csv',density.SPEC_PATH]
    plan.update(mode='adaptive_joint_quantile_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        label_rule=parent['label_rule'],feature_names=feature_names,
        configs=['Expanding raw log-return CatBoost joint quantiles','Expanding volatility-normalized log-return CatBoost joint quantiles'],
        primary='expanded_density_blend: classifier/old density/new density weights .5/.25/.25. Equal raw/normalized heads in each density.',
        secondary='new_density_blend: .5 classifier + .5 new density',
        optuna=None,parameters=JOINT_PARAMETERS,learner='CatBoost MultiQuantile, nine outputs jointly; original 19 trend/ETF features, no feature additions or tuning',
        acceptance='Mean macroF1 +.01, no loss in worst fold or mean bear/bull F1, higher MCC and >=3 fold wins vs incumbent. Both paired20/60 intervals >0 required for provisional robust evidence.',
        caveats='All dates are repeatedly inspected development. No threshold or weight tuning, calibrated probability, independent test or automatic deployment.')
    output=args.output_dir or ROOT/'reports/regime_joint_quantiles'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    new_densities=[]
    for normalized in [False,True]:
        name='normalized' if normalized else 'raw'
        records=[];audits=[]
        for outer in job['folds']:
            for number,block in enumerate(outer['blocks'],1):
                train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                _,points,crossings=fit_joint_return_quantiles(train,valid,feature_names,normalized,plan['specification'])
                mass=dynamic_quantile_mass(points,plan['specification']['quantile_atom_weights'],
                    -valid.horizon_sigma.to_numpy(),valid.horizon_sigma.to_numpy())
                prior=np.bincount(train.label,minlength=3)/len(train)
                if (prior<=0).any():raise ValueError('Missing mature training class')
                score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                rows=valid[['Date','label_end_date','label','future_return']].copy()
                rows[experts.PROBS]=score
                for i,alpha in enumerate(plan['specification']['quantile_levels']):rows[f'log_q{round(alpha*100):02d}']=points[:,i]
                rows['outer_fold'],rows['refit_block']=outer['fold'],number
                records.append(rows)
                audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),
                    train_start=str(train.Date.min().date()),train_label_end=str(train.label_end_date.max().date()),
                    prediction_start=str(valid.Date.min().date()),class_prior=prior.tolist(),quantile_crossings=crossings))
            pd.concat(records,ignore_index=True).to_csv(output/(name+'_scores.csv'),index=False)
            (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
            print(name+' fold '+str(outer['fold'])+' complete',flush=True)
        rows=pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        new_densities.append(rows[experts.PROBS].to_numpy())
    new_density=np.mean(new_densities,axis=0)
    matrices=dict(incumbent=incumbent,new_density=new_density,
        new_density_blend=.5*classifier+.5*new_density,
        expanded_density_blend=.5*classifier+.25*old_density+.25*new_density)
    results=[];predictions={}
    for name,score in matrices.items():
        np.testing.assert_allclose(score.sum(axis=1),1.,atol=1e-12)
        result,rows=experts.expert_metrics(name,base,score.argmax(axis=1))
        results.append(result);predictions[name]=rows
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
    dynamic_error_tables(predictions,book,output)
    baseline=results[0];comparisons=[];intervals=[]
    groups=[np.flatnonzero(base.outer_fold.to_numpy()==n) for n in sorted(base.outer_fold.unique())]
    y=base.label.to_numpy(dtype=int)
    for r in results:
        if r['candidate'] not in ['new_density_blend','expanded_density_blend']:continue
        name=r['candidate']
        class_mean=lambda entry,c:float(np.mean([f['per_class'][c]['f1-score'] for f in entry['folds']]))
        wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(r['folds'],baseline['folds']))
        passed=(r['mean_f1']>=baseline['mean_f1']+.01 and r['worst_f1']>=baseline['worst_f1']
            and r['mean_mcc']>baseline['mean_mcc'] and wins>=3
            and all(class_mean(r,c)>=class_mean(baseline,c) for c in ['bear','bull']))
        for length in [20,60]:
            rng=np.random.default_rng(42);deltas=[]
            for _ in range(1000):
                sample=[]
                for group in groups:
                    starts=rng.integers(0,len(group),size=int(np.ceil(len(group)/length)))
                    sample.append(group[((starts[:,None]+np.arange(length))%len(group)).ravel()[:len(group)]])
                deltas.append(fold_f1(y,predictions[name].prediction.to_numpy(),sample)-fold_f1(y,predictions['incumbent'].prediction.to_numpy(),sample))
            low,high=np.quantile(deltas,[.025,.975])
            intervals.append(dict(candidate=name,block=length,delta=r['mean_f1']-baseline['mean_f1'],low=float(low),high=float(high)))
        comparisons.append(dict(candidate=name,fold_wins=wins,point_screen=bool(passed),
            provisional_robust_evidence=bool(passed and all(i['low']>0 for i in intervals if i['candidate']==name))))
    (output/'report.json').write_text(json.dumps(dict(role='Inspected historical DEVELOPMENT only',results=results,comparisons=comparisons,paired_intervals=intervals),indent=2)+'\n')
    pd.DataFrame([{k:r[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']} for r in results]).to_csv(output/'comparison.csv',index=False)
    print(pd.read_csv(output/'comparison.csv').to_string(index=False),flush=True)
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_joint_quantiles()
