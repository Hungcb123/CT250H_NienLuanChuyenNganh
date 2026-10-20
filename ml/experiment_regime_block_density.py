"""Moving-block loss-weight bagging for the fixed quantile-density model.

Bootstrap only mature original rows. No synthetic sessions/prices or outer seed
selection; each candidate preserves the frozen target and evaluation cohort.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_temporal_fusion import choose_temporal_fusion
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
SEEDS=[7,21,42,84,126]


def moving_block_counts(size,length,seed,classes):
    classes=np.asarray(classes,dtype=int)
    if size<1 or length<1 or classes.shape!=(size,) or set(classes)!={0,1,2}:raise ValueError('Invalid bootstrap cohort')
    rng=np.random.default_rng(seed);minimum=np.minimum(np.bincount(classes,minlength=3),10)
    for attempt in range(100):
        starts=rng.integers(0,size,size=int(np.ceil(size/length)))
        sampled=((starts[:,None]+np.arange(length))%size).ravel()[:size]
        counts=np.bincount(sampled,minlength=size).astype(float)
        if (np.bincount(classes,weights=counts,minlength=3)>=minimum).all():return counts,attempt+1
    return np.ones(size),100


def run_block_density_ensemble(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,classifier,old_density,index,paths=load_seed_components()
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    market,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(market),'vol_1sigma')
    paths += [Path(__file__),ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_temporal_fusion.py',ROOT/'experiment_regime_forecast_smoothing.py']
    plan.update(mode='mature_moving_block_quantile_ensemble_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':{'policy':'vol_1sigma','k':1.,'lookback':20,'horizon':20,'ddof':1,'equality':'sideway'}},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},seeds=SEEDS,block_length=20,
        resampling='Circular consecutive20-session blocks inside permitted training rows. Multiplicity weights sum to original row count. Reject up to100 draws lacking min(10,original_count) mass in any target class; fallback uniform. Same draw for raw/normalized targets.',
        learner='Original quantile hyperparameters including random_state42 held constant; change only training row multiplicities. Decision prior remains original full mature target class frequency.',
        primary='bagged_adaptive: equal five bagged densities; same mature-past fusion/temperature learner and current/EMA5 mixture as incumbent',
        secondary='bagged_shrink: equal incumbent/bagged_adaptive. No best-bag outer choice.',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, higher MCC and >=3 wins; both paired20/60 lower>0 for provisional evidence.',
        caveat='Blocks do not create independent economic events or new historical data. No target change, outer bag selection, independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_block_density'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    bag_scores=[];audits=[]
    job=jobs['expanding']
    for seed in SEEDS:
        targets=[]
        for normalized in [False,True]:
            target='normalized' if normalized else 'raw';records=[]
            for outer in job['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured bootstrap target')
                    weights,attempts=moving_block_counts(len(train),20,seed+1000*outer['fold']+number,train.label)
                    y=train.future_log_return.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy()
                    points=[]
                    for alpha in plan['specification']['quantile_levels']:
                        model=LGBMRegressor(**plan['specification']['parameters'],alpha=alpha)
                        model.fit(train[job['names']].to_numpy(dtype=np.float32),y,sample_weight=weights)
                        value=model.predict(valid[job['names']].to_numpy(dtype=np.float32))
                        if normalized:value*=valid.horizon_sigma.to_numpy()
                        points.append(value)
                    points=np.sort(np.column_stack(points),axis=1);sigma=valid.horizon_sigma.to_numpy()
                    mass=dynamic_quantile_mass(points,plan['specification']['quantile_atom_weights'],-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train)
                    score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(seed=seed,target=target,fold=outer['fold'],block=number,n_train=len(train),nonzero_rows=int((weights>0).sum()),
                        attempts=attempts,weight_sum=float(weights.sum()),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),
                        weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest()))
                pd.concat(records,ignore_index=True).to_csv(output/f'bag{seed}_{target}_scores.csv',index=False)
                (output/'resampling_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
                print(f'Bag{seed} {target} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            targets.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        bag_scores.append(np.mean(targets,axis=0))
    new_density=np.mean(bag_scores,axis=0)
    def causal_fusion(d):
        fixed=.5*classifier+.5*d;adapted,_=choose_temporal_fusion(base,classifier,d,index.Date)
        pooled=.5*fixed+.25*adapted[252]+.25*adapted[504]
        return .5*pooled+.5*causal_forecast_ema(base.Date,pooled,index.Date,5)
    incumbent=causal_fusion(old_density)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    combined=causal_fusion(new_density)
    static=.5*classifier+.5*new_density
    matrices=dict(incumbent=incumbent,bagged_adaptive=combined,bagged_shrink=.5*incumbent+.5*combined,
        bagged_static=.5*static+.5*causal_forecast_ema(base.Date,static,index.Date,5))
    for seed,score in zip(SEEDS,bag_scores):
        raw=.5*classifier+.5*score
        matrices[f'bag{seed}_diagnostic']=.5*raw+.5*causal_forecast_ema(base.Date,raw,index.Date,5)
    finish_research_study(base,matrices,output,['bagged_adaptive','bagged_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_block_density_ensemble()
