"""Balanced multiclass focal/smoothed losses with inner-only selection.

Reference: https://arxiv.org/abs/1708.02002
Custom-objective API: https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html
No claim that an image-detection loss necessarily helps financial forecasting.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from scipy.special import softmax

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_tuning import dynamic_inner_score,assert_dynamic_inner_timing
from experiment_regime_dynamic_families import fit_dynamic_family
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
LOSSES={'ce':(0.,0.),'smooth05':(0.,.05),'smooth10':(0.,.1),'focal1':(1.,0.),'focal2':(2.,0.)}
PARAMETERS=dict(n_estimators=200,learning_rate=.03,max_depth=4,num_leaves=15,min_child_samples=50,
    colsample_bytree=.7,reg_alpha=.1,reg_lambda=1.,max_delta_step=1.,random_state=42,n_jobs=2,verbosity=-1)


def multiclass_loss_derivatives(y,raw,class_weights,gamma=0.,smoothing=0.):
    y=np.asarray(y,dtype=int);raw=np.asarray(raw,dtype=float)
    if raw.shape!=(len(y),3) or (gamma and smoothing):raise ValueError('Invalid loss configuration')
    p=softmax(raw,axis=1);truth=np.eye(3)[y];alpha=np.asarray(class_weights)[y,None]
    if gamma==0.:
        target=(1-smoothing)*truth+smoothing/3
        grad=alpha*(p-target)
        hess=alpha*p*(1-p)
    else:
        u=np.clip(p[np.arange(len(y)),y],1e-12,1-1e-12)
        t=1-u;logu=np.log(u)
        a=t**gamma-gamma*u*t**(gamma-1)*logu
        da=-2*gamma*t**(gamma-1)-gamma*t**(gamma-1)*logu+gamma*u*(gamma-1)*t**(gamma-2)*logu
        error=p-truth
        grad=alpha*a[:,None]*error
        hess=alpha*(a[:,None]*p*(1-p)-da[:,None]*u[:,None]*error**2)
    # Positive diagonal Newton surrogate; focal loss may have negative curvature.
    return grad,1.5*np.maximum(hess,1e-4)


def fit_dynamic_loss(train,valid,names,loss):
    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured loss training')
    y=train.label.to_numpy(dtype=int)
    counts=np.bincount(y,minlength=3)
    if (counts<=0).any():raise ValueError('Missing class')
    weights=len(y)/(3*counts);gamma,smoothing=LOSSES[loss]
    def objective(actual,raw):
        return multiclass_loss_derivatives(actual,raw,weights,gamma,smoothing)
    model=LGBMClassifier(**PARAMETERS,objective=objective,num_class=3)
    model.fit(train[names].to_numpy(dtype=np.float32),y)
    raw=model.booster_.predict(valid[names].to_numpy(dtype=np.float32),raw_score=True)
    return softmax(raw,axis=1)


def run_dynamic_losses(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--inner-splits','3','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frames[20],labels.build_label_book(index),'vol_1sigma')
    names=list(dict.fromkeys(c for j in jobs for c in j['names']))
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_dynamic_families.py',ROOT/'experiment_regime_dynamic_tuning.py',args.parent_dir/'plan.json']
    paths += [old/n for n in ['trend_predictions.csv','risk_predictions.csv','expanding_raw_mapped_predictions.csv','expanding_normalized_mapped_predictions.csv']]
    plan.update(mode='adaptive_multiclass_loss_ablation_DEVELOPMENT',optuna=None,losses=LOSSES,parameters=PARAMETERS,
        features=names,source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        primary='inner_supplement_blend: .25 old classifier + .25 inner-selected loss classifier + .5 old density',
        secondary='inner_replacement_blend: .5 selected classifier + .5 old density',
        selection='Legacy equal fallback; switch only for >=.01 gain in three purged-inner robustness score. No outer choice.',
        hessian='Exact focal gradient; Hessian diagonal clipped positive then multiplied1.5; max_delta_step1 bounds Newton updates. This is an optimization surrogate, not a convexity claim.',
        references=['https://arxiv.org/abs/1708.02002','https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html'],
        acceptance='Mean F1 +.01, no worse worst fold or mean bear/bull F1, MCC gain and >=3 wins; paired20/60 lower bounds >0 for provisional evidence.',
        caveat='All historical periods inspected. Label smoothing only affects training loss, never ground truth. No independent acceptance, calibration claim or deployment.')
    output=args.output_dir or ROOT/'reports/regime_dynamic_losses'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    records={name:[] for name in ['legacy_equal']+list(LOSSES)};selected=[];choices=[]
    for outer in jobs[0]['folds']:
        legacy={j['group']:dict(names=j['names'],params=next(r['best_params'] for r in parent['classifier_parameters'][j['group']] if r['outer_fold']==outer['fold'])) for j in jobs}
        tuning=frame.iloc[outer['tune']].reset_index(drop=True);folds=exp.base.purged_folds(tuning,3)
        boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tuning,folds,boundary)
        scores=[]
        for loss in records:
            metrics=[]
            for t,v in folds:
                train,valid=tuning.iloc[t],tuning.iloc[v]
                probability=fit_dynamic_family(train,valid,names,'legacy_equal',legacy) if loss=='legacy_equal' else fit_dynamic_loss(train,valid,names,loss)
                metrics.append(exp.base.classification_metrics(valid.label,probability.argmax(axis=1),train.label))
            scores.append(dict(loss=loss,score=dynamic_inner_score(metrics),folds=metrics))
        best=max(scores,key=lambda r:r['score']);chosen=best['loss'] if best['score']>=scores[0]['score']+.01 else 'legacy_equal'
        choices.append(dict(fold=outer['fold'],chosen=chosen,outer_boundary=str(boundary.date()),latest_tuning_label_end=str(tuning.label_end_date.max().date()),scores=scores))
        (output/'inner_selection.json').write_text(json.dumps(choices,indent=2)+'\n')
        print('Fold '+str(outer['fold'])+' loss choice '+chosen,flush=True)
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            for loss in records:
                probability=fit_dynamic_family(train,valid,names,'legacy_equal',legacy) if loss=='legacy_equal' else fit_dynamic_loss(train,valid,names,loss)
                rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=probability
                rows['outer_fold'],rows['refit_block']=outer['fold'],number
                records[loss].append(rows)
                if loss==chosen:selected.append(rows.copy())
        for loss,chunks in records.items():pd.concat(chunks,ignore_index=True).to_csv(output/(loss+'_scores.csv'),index=False)
        print('Fold '+str(outer['fold'])+' loss refits complete',flush=True)
    selected=pd.concat(selected,ignore_index=True)
    matrices={loss:pd.concat(chunks,ignore_index=True)[experts.PROBS].to_numpy() for loss,chunks in records.items()}
    old_equal=np.mean([pd.read_csv(old/(g+'_predictions.csv'))[experts.PROBS].to_numpy() for g in ['trend','risk']],axis=0)
    np.testing.assert_allclose(matrices['legacy_equal'],old_equal,atol=1e-12,rtol=1e-12)
    densities=[]
    for t in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+t+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);densities.append(score)
    old_density=np.mean(densities,axis=0)
    matrices.update({name+'_blend':.5*score+.5*old_density for name,score in list(matrices.items())})
    chosen=selected[experts.PROBS].to_numpy()
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(selected[key],base[key])
    matrices['inner_supplement_blend']=.25*old_equal+.25*chosen+.5*old_density
    matrices['inner_replacement_blend']=.5*chosen+.5*old_density
    matrices['incumbent']=.5*old_equal+.5*old_density
    finish_research_study(base,matrices,output,['inner_supplement_blend','inner_replacement_blend'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_dynamic_losses()
