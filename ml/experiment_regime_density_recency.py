"""Fixed time-decay quantile losses, adaptive target and original refit63.

Decay uses only observation dates. No future outcomes select half-life or mix.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
HALF_LIVES=[126,252]


def causal_recency_weights(dates,boundary,calendar,half_life):
    dates=pd.DatetimeIndex(dates);calendar=pd.DatetimeIndex(calendar);boundary=pd.Timestamp(boundary)
    positions=calendar.get_indexer(dates);where=calendar.get_indexer([boundary])[0]
    if half_life<=0 or where<0 or (positions<0).any() or (positions>=where).any():raise ValueError('Invalid decay calendar/boundary')
    weights=np.exp2(-(where-positions)/half_life)
    return weights/weights.mean()


def run_density_recency(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--challenger-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=density.exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',args.challenger_dir/'inner_selected_blend_predictions.csv',args.challenger_dir/'inner_selection.json']
    risk=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date']);paths += [old/'risk_predictions.csv']
    selected_trend=np.empty((len(base),3))
    for choice in json.loads((args.challenger_dir/'inner_selection.json').read_text()):
        path=args.challenger_dir/(choice['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        mask=base.outer_fold.eq(choice['fold']).to_numpy();selected_trend[mask]=rows.loc[mask,experts.PROBS].to_numpy()
    classifier=.5*(selected_trend+risk[experts.PROBS].to_numpy())
    old_densities=[]
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_densities.append(score)
    old_density=np.mean(old_densities,axis=0)
    challenger=pd.read_csv(args.challenger_dir/'inner_selected_blend_predictions.csv',parse_dates=['Date','label_end_date'])
    np.testing.assert_allclose(.5*classifier+.5*old_density,challenger[experts.PROBS],atol=1e-12,rtol=1e-12)
    plan.update(mode='causal_time_decay_quantile_DEVELOPMENT',optuna=None,half_lives=HALF_LIVES,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        weight_rule='2**(-raw-market-session age / half-life), normalized to training mean1. Target dates/labels/endpoints unchanged.',
        primary='info_decay_pool: .5 fixed information classifier + .5 equal four raw/normalized,HL126/252 densities with weighted training-class prior',
        secondary='info_decay_shrink: .5 classifier + .25 old density + .25 equal time-decay densities',
        decision_prior='Weighted mature target-class frequencies; unweighted-prior outputs are diagnostic controls to isolate loss weighting from decision cost.',
        acceptance='Mean F1 current incumbent +.01, no worst/directional decline, MCC gain and >=3 wins; both paired20/60 lower>0 for provisional evidence.',
        caveat='Weighted effective row count is not independent economic sample size. No future-label selection, label change, independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_density_recency'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    scores_by_half={};old_prior_scores={};job=jobs['expanding']
    for half_life in HALF_LIVES:
        targets=[];diagnostics=[]
        for normalized in [False,True]:
            name='normalized' if normalized else 'raw';records=[];audits=[]
            for outer in job['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    boundary=valid.Date.min()
                    if train.label_end_date.max()>=boundary:raise ValueError('Unmatured decay supervision')
                    weights=causal_recency_weights(train.Date,boundary,index.Date,half_life)
                    y=train.future_log_return.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy()
                    points=[]
                    for alpha in plan['specification']['quantile_levels']:
                        model=LGBMRegressor(**plan['specification']['parameters'],alpha=alpha)
                        model.fit(train[job['names']].to_numpy(dtype=np.float32),y,sample_weight=weights)
                        values=model.predict(valid[job['names']].to_numpy(dtype=np.float32))
                        if normalized:values*=valid.horizon_sigma.to_numpy()
                        points.append(values)
                    points=np.sort(np.column_stack(points),axis=1);sigma=valid.horizon_sigma.to_numpy()
                    mass=dynamic_quantile_mass(points,plan['specification']['quantile_atom_weights'],-sigma,sigma)
                    prior=np.bincount(train.label,weights=weights,minlength=3)/weights.sum()
                    old_prior=np.bincount(train.label,minlength=3)/len(train)
                    score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    diagnostic=mass/old_prior;diagnostic/=diagnostic.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
                    rows[['oldprior_bear','oldprior_side','oldprior_bull']]=diagnostic
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(boundary.date()),weighted_prior=prior.tolist(),effective_weight_rows=float(weights.sum()**2/np.square(weights).sum())))
                pd.concat(records,ignore_index=True).to_csv(output/f'hl{half_life}_{name}_scores.csv',index=False)
                (output/f'hl{half_life}_{name}_refits.json').write_text(json.dumps(audits,indent=2)+'\n')
                print(f'HL{half_life} {name} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            targets.append(rows[experts.PROBS].to_numpy());diagnostics.append(rows[['oldprior_bear','oldprior_side','oldprior_bull']].to_numpy())
        scores_by_half[half_life]=np.mean(targets,axis=0);old_prior_scores[half_life]=np.mean(diagnostics,axis=0)
    mean=np.mean(list(scores_by_half.values()),axis=0)
    matrices=dict(incumbent=challenger[experts.PROBS].to_numpy(),info_decay_pool=.5*classifier+.5*mean,
        info_decay_shrink=.5*classifier+.25*old_density+.25*mean)
    for half_life,score in scores_by_half.items():
        matrices[f'hl{half_life}_diagnostic']=.5*classifier+.5*score
        matrices[f'hl{half_life}_oldprior_diagnostic']=.5*classifier+.5*old_prior_scores[half_life]
    finish_research_study(base,matrices,output,['info_decay_pool','info_decay_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_density_recency()
