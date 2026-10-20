"""Add earlier mature index history to forests while preserving missing ETF data.

Index labels are shifted on the full original calendar, before warmup filtering.
No synthetic ETF prices, bfill, filled prices, constituent universe or new labels.
"""
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


def extended_feature_history(index,etf):
    features,names=exp.base.build_feature_matrix(index,etf,feature_set='close-etf')
    features=pd.concat([features,exp.long_features(index)],axis=1)
    # Create full-calendar endpoints BEFORE any feature eligibility filtering.
    book=labels.build_label_book(index)
    frame=features.merge(book[['Date','label_end_date','future_return','horizon_sigma','vol_label']],
        on='Date',how='left',sort=False,validate='one_to_one')
    core=exp.base.CLOSE_V1_NAMES+exp.TREND_NAMES
    eligible=np.isfinite(frame[core].to_numpy(dtype=float)).all(axis=1)
    eligible &= frame.vol_label.notna().to_numpy() & frame.label_end_date.notna().to_numpy()
    frame=frame.loc[eligible].reset_index(drop=True)
    frame['label']=frame.pop('vol_label').astype(np.int64)
    frame['future_log_return']=np.log1p(frame.future_return)
    return frame,names+exp.TREND_NAMES


def run_extended_forest(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,classifier,quantile,calendar,paths=load_seed_components(ANALOG/'analog_shrink_predictions.csv')
    old_frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    etf,_=exp.base.load_market_data(args.data_dir/'E1VFVN30.csv')
    outside=pd.DatetimeIndex(etf.Date).difference(pd.DatetimeIndex(index.Date))
    allowed=pd.DatetimeIndex(['2018-01-23','2018-01-24'])
    if len(outside.difference(allowed)):raise ValueError('Unexpected ETF sessions outside reviewed index calendar')
    etf=etf.loc[~etf.Date.isin(outside)].copy()
    frame,names=extended_feature_history(index,etf)
    if names!=jobs['expanding']['names']:raise ValueError('Forest feature schema changed')
    old_frame=labels.relabel_cohort(old_frame,labels.build_label_book(index),'vol_1sigma')
    matched=old_frame[['Date']].merge(frame,on='Date',how='left',sort=False,validate='one_to_one')
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(old_frame[key],matched[key])
    np.testing.assert_allclose(old_frame[names+['future_log_return','horizon_sigma']],matched[names+['future_log_return','horizon_sigma']],rtol=0,atol=1e-12)
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    old_forest=np.mean(old_parts,axis=0)
    parts=[]
    for view in ['compact','full']:
        for target in ['raw','normalized']:
            path=ANALOG/f'{view}_{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    analog=np.mean(parts,axis=0)
    params=json.loads((FOREST/'plan.json').read_text())['parameters']
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'experiment_regime_empirical_forest.py',ROOT/'experiment_regime_labels.py',
        ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_forecast_smoothing.py',
        ROOT/'experiment_regime_matched_calibration.py',CALIBRATION/'selection.json',args.data_dir/'E1VFVN30.csv']
    plan.update(mode='extended_history_missing_ETF_empirical_forest_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,
        feature_names=names,excluded_reviewed_ETF_outside_calendar=[str(d.date()) for d in outside],
        eligibility='Close-v1 core and long trend features must be finite, plus defined dynamic target/end. ETF features may remain NaN before source begins or at gaps; native RF missing branches. All endpoints built on complete VNINDEX calendar before filtering. No ETF price or feature fill.',
        feature_parity='All original training/evaluation dates match old frame exactly to1e-12 for core/ETF features and continuous target/sigma.',
        primary='extended_shrink: density .375quantile+.1875old forest+.1875extended forest+.25analog. Replace half original37.5% forest component without changing other weights.',
        secondary='extended_replace: density .375quantile+.375extended forest+.25analog. Mean/magnitude x raw/normalized equal4 models, same classifier/anchors/EMA5.',
        maturity='Expanding training, same old63-session validation blocks, target endpoints strictly before boundary. Adds earlier rows and ETF-missing rows, never new evaluation dates.',
        caveat='Earlier dates are not independent fresh tests. ETF availability pattern can encode historical era. No source vintage certification, independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_extended_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (output/'feature_parity.json').write_text(json.dumps(dict(original_rows=len(old_frame),extended_rows=len(frame),earliest_original=str(old_frame.Date.min().date()),earliest_extended=str(frame.Date.min().date()),max_feature_error=float(np.abs(old_frame[names].to_numpy()-matched[names].to_numpy()).max())),indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    audits=[];parts=[]
    for architecture in ['mean','magnitude']:
        for normalized in [False,True]:
            records=[]
            for outer in jobs['expanding']['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    valid=old_frame.iloc[block['validation']]
                    boundary=valid.Date.min()
                    train=frame.loc[(frame.Date<boundary)&(frame.label_end_date<boundary)]
                    if train.label_end_date.max()>=boundary:raise ValueError('Unmatured extended forest target')
                    y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                    target=y
                    if architecture=='magnitude':
                        target=np.column_stack([y,np.abs(y)]);target=(target-target.mean(axis=0))/target.std(axis=0,ddof=1)
                    x=train[names].to_numpy(dtype=np.float32);v=valid[names].to_numpy(dtype=np.float32)
                    if np.isinf(x).any() or np.isinf(v).any():raise ValueError('Infinite extended feature')
                    model=RandomForestRegressor(**params).fit(x,target)
                    mass=empirical_leaf_mass(model.apply(x),model.apply(v),y,-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train);score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(architecture=architecture,normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),old_n_train=len(block['train']),
                        train_start=str(train.Date.min().date()),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(boundary.date()),
                        rows_missing_ETF=int(train[exp.base.ETF_FEATURE_NAMES].isna().any(axis=1).sum()),train_nan_fraction=float(np.isnan(x).mean())))
                print(f'Extended {architecture} normalized={normalized} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            rows.to_csv(output/f'{architecture}_{"normalized" if normalized else "raw"}_scores.csv',index=False)
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n');new_forest=np.mean(parts,axis=0)
    def combine(d):
        raw=np.empty_like(d)
        for outer in anchors:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured anchor')
            mask=base.outer_fold.eq(outer['fold']).to_numpy();raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(.375*quantile+.375*old_forest+.25*analog)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    finish_research_study(base,dict(incumbent=incumbent,extended_shrink=combine(.375*quantile+.1875*old_forest+.1875*new_forest+.25*analog),
        extended_replace=combine(.375*quantile+.375*new_forest+.25*analog)),output,['extended_shrink','extended_replace'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_extended_forest()
