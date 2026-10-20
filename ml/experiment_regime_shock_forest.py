"""Fixed short-shock feature ablation for empirical return-density forests."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_directional import directional_features
from experiment_regime_empirical_forest import empirical_leaf_mass,CALIBRATION
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
FOREST=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
MAGNITUDE=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
ANALOG=ROOT/'reports/regime_analog_density/20261019T071721_721598Z'


def run_shock_forest_density(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,classifier,quantile,calendar,paths=load_seed_components(ANALOG/'analog_shrink_predictions.csv')
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
    features=directional_features(index);extras=[n for n in features if n!='Date']
    frame=frame.merge(features,on='Date',how='left',validate='one_to_one',sort=False)
    names=jobs['expanding']['names']+extras
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    analogs=[]
    for view in ['compact','full']:
        for target in ['raw','normalized']:
            path=ANALOG/f'{view}_{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            analogs.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    old_density=.75*(.5*quantile+.25*old_parts[0]+.25*old_parts[1])+.25*np.mean(analogs,axis=0)
    params=json.loads((FOREST/'plan.json').read_text())['parameters']
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'experiment_regime_directional.py',ROOT/'experiment_regime_empirical_forest.py',
        ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_forecast_smoothing.py',
        ROOT/'experiment_regime_matched_calibration.py',CALIBRATION/'selection.json']
    plan.update(mode='short_shock_empirical_forest_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,
        feature_names=names,extra_features=extras,
        architectures=['mean','magnitude'],targets=['raw','normalized'],
        primary='shock_shrink: .75 current analog-shrink density+.25 new shock forest density. Equal4 raw/normalized x mean/magnitude models, same classifier/anchors/current-EMA5.',
        secondary='shock_half: half existing/half new density. Fixed weights; no outer feature/weight/threshold search.',
        feature_timing='Existing directional_features(index) uses completed-close backward rolling information only: momentum3/5/10/20/60, lagged normalized shocks, downside energy, down-session shares, vol5/20, drawdown20/60, skew20, momentum acceleration. No centered rolls, backward fill or revised external source.',
        maturity='Expanding training, refit63; every training target endpoint strictly precedes prediction start. All1560 validation dates retained.',
        caveat='Features previously tried with classifiers/quantile heads; new test is their use in empirical forest partitioning. Repeated development exposure, no independent acceptance/deployment.')
    output=args.output_dir or ROOT/'reports/regime_shock_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    audits=[];parts=[]
    for architecture in ['mean','magnitude']:
        for normalized in [False,True]:
            records=[]
            for outer in jobs['expanding']['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured shock target')
                    y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                    target=y
                    if architecture=='magnitude':
                        target=np.column_stack([y,np.abs(y)]);target=(target-target.mean(axis=0))/target.std(axis=0,ddof=1)
                    x=train[names].to_numpy(dtype=np.float32);v=valid[names].to_numpy(dtype=np.float32)
                    if np.isinf(x).any() or np.isinf(v).any():raise ValueError('Infinite shock feature')
                    model=RandomForestRegressor(**params).fit(x,target)
                    mass=empirical_leaf_mass(model.apply(x),model.apply(v),y,-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train);score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(architecture=architecture,normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),
                        latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),n_features=len(names),train_nan_fraction=float(np.isnan(x).mean()),valid_nan_fraction=float(np.isnan(v).mean())))
                print(f'Shock {architecture} normalized={normalized} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            rows.to_csv(output/f'{architecture}_{"normalized" if normalized else "raw"}_scores.csv',index=False)
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n');new_density=np.mean(parts,axis=0)
    def combine(d):
        raw=np.empty_like(d)
        for outer in anchors:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured anchor')
            mask=base.outer_fold.eq(outer['fold']).to_numpy()
            raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(old_density)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    finish_research_study(base,dict(incumbent=incumbent,shock_shrink=combine(.75*old_density+.25*new_density),
        shock_half=combine(.5*old_density+.5*new_density)),output,['shock_shrink','shock_half'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_shock_forest_density()
