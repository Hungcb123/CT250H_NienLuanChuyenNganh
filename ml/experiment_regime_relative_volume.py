"""Fixed 0.01% broker-volume agreement precision ablation for forest features.

Never changes prices or original snapshots. This is a bounded-disagreement
measurement hypothesis, not exchange certification or guaranteed data repair.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
import experiment_regime_ohlcv as ohlcv
import prepare_regime_data as sources
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
VOLUME_NAMES=['RelativeVolumeLogRatio60','RelativeVolumeLogChange5']


def relative_volume_consensus(values,rtol=1e-4):
    if not np.isfinite(rtol) or rtol<0:raise ValueError('Invalid relative precision budget')
    valid={k:float(v) for k,v in values.items() if pd.notna(v) and np.isfinite(v) and v>0}
    for size in range(len(valid),1,-1):
        groups=[]
        for group in itertools.combinations(valid,size):
            selected=[valid[k] for k in group]
            if max(selected)-min(selected)<=max(1.,rtol*max(selected)):groups.append(group)
        if groups:
            if len(groups)!=1:return np.nan,''
            group=groups[0]
            return float(np.median([valid[k] for k in group])),'+'.join(sorted(group))
    return np.nan,''


def relative_volume_features(panel,rtol=1e-4):
    if panel.Date.duplicated().any() or not panel.Date.is_monotonic_increasing:
        raise ValueError('Need full ordered market calendar')
    names=[n for n in panel if n!='Date']
    accepted=[relative_volume_consensus({n:row[n] for n in names},rtol) for _,row in panel.iterrows()]
    result=pd.DataFrame(dict(Date=panel.Date,RelativeConsensusVolume=[v for v,_ in accepted],VolumeSources=[v for _,v in accepted]))
    volume=result.RelativeConsensusVolume
    median=volume.rolling(60,min_periods=30).median().where(lambda x:x>0)
    result['RelativeVolumeLogRatio60']=np.log(volume/median)
    result['RelativeVolumeLogChange5']=np.log(volume/volume.shift(5))
    result[VOLUME_NAMES]=result[VOLUME_NAMES].replace([np.inf,-np.inf],np.nan)
    return result


def run_relative_volume_forest(argv=None):
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
    panel=index[['Date']].copy();manifest=json.loads((args.data_dir/'manifest.json').read_text())
    for provider in ['vci','kbs','vnd']:
        path=args.data_dir/'sources'/f'{provider}_VNINDEX.json';paths.append(path)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sources'][provider+'_VNINDEX']['response_sha256']:
            raise ValueError('Volume snapshot changed')
        bars=sources.normalize_response(json.loads(path.read_text()),provider,'VNINDEX',index.Date.min(),index.Date.max())
        aligned=index[['Date','Price']].merge(bars,on='Date',how='left',sort=False,validate='one_to_one')
        bounds=(aligned.High+.011>=aligned[['Open','Close','Low']].max(axis=1))&(aligned.Low-.011<=aligned[['Open','Close','High']].min(axis=1))
        valid=bounds&(aligned.Close-aligned.Price).abs().le(.011)&aligned.Volume.gt(0)
        panel[provider]=aligned.Volume.where(valid)
    features=relative_volume_features(panel)
    old_consensus,_=ohlcv.load_consensus(args.data_dir,index)
    features['OldAbsoluteConsensusVolume']=old_consensus.Volume
    frame=frame.merge(features[['Date']+VOLUME_NAMES],on='Date',how='left',sort=False,validate='one_to_one')
    names=jobs['expanding']['names']+VOLUME_NAMES
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    old_forest=np.mean(old_parts,axis=0);parts=[]
    for view in ['compact','full']:
        for target in ['raw','normalized']:
            path=ANALOG/f'{view}_{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    analog=np.mean(parts,axis=0);params=json.loads((FOREST/'plan.json').read_text())['parameters']
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'prepare_regime_data.py',ROOT/'experiment_regime_ohlcv.py',
        ROOT/'experiment_regime_empirical_forest.py',ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',
        ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'experiment_regime_matched_calibration.py',CALIBRATION/'selection.json',args.data_dir/'manifest.json']
    plan.update(mode='relative_precision_volume_forest_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,
        feature_names=names,relative_volume_tolerance=1e-4,
        agreement='Same broker eligibility as original consensus: valid OHLC geometry and reviewed-close agreement within.011. Unique largest group of>=2 positive volume values with range<=max(1share,.0001*groupmax). Reject ambiguous chains, single-source values and larger disagreements. Never change original absolute-consensus book or any price.',
        feature_timing='Two new features: log volume/60-session trailing median(min30 observed), log volume/volume.shift5 on full index calendar. Undefined/conflicting values stayNaN; no fill or calendar compression.',
        primary='volume_shrink: .375quantile+.1875oldforest+.1875newforest+.25analog. Replace half existing forest component. New forest changes only two volume inputs on original training rows.',
        secondary='volume_replace: .375quantile+.375newforest+.25analog. Fixed parameters/weights, mean/magnitude x raw/normalized equal4 heads.',
        caveat='Precision tolerance is a data-measurement hypothesis chosen from source comparisons before model scoring, not verified exchange volume or source-definition/vintage certification. Repeated development, no independent acceptance/deployment.')
    output=args.output_dir or ROOT/'reports/regime_relative_volume'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    features.to_csv(output/'volume_features.csv',index=False)
    frozen=features.Date.isin(base.Date)
    (output/'coverage.json').write_text(json.dumps(dict(old_field_all=float(features.OldAbsoluteConsensusVolume.notna().mean()),new_field_all=float(features.RelativeConsensusVolume.notna().mean()),
        old_field_frozen=float(features.loc[frozen,'OldAbsoluteConsensusVolume'].notna().mean()),new_field_frozen=float(features.loc[frozen,'RelativeConsensusVolume'].notna().mean()),
        features_frozen={n:float(features.loc[frozen,n].notna().mean()) for n in VOLUME_NAMES}),indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    audits=[];parts=[]
    for architecture in ['mean','magnitude']:
        for normalized in [False,True]:
            records=[]
            for outer in jobs['expanding']['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured volume forest target')
                    y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                    target=y
                    if architecture=='magnitude':
                        target=np.column_stack([y,np.abs(y)]);target=(target-target.mean(axis=0))/target.std(axis=0,ddof=1)
                    x=train[names].to_numpy(dtype=np.float32);v=valid[names].to_numpy(dtype=np.float32)
                    if np.isinf(x).any() or np.isinf(v).any():raise ValueError('Infinite volume feature')
                    model=RandomForestRegressor(**params).fit(x,target)
                    mass=empirical_leaf_mass(model.apply(x),model.apply(v),y,-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train);score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(architecture=architecture,normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),
                        latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),train_nan_fraction=float(np.isnan(x).mean())))
                print(f'Volume {architecture} normalized={normalized} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            rows.to_csv(output/f'{architecture}_{"normalized" if normalized else "raw"}_scores.csv',index=False);parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n');new=np.mean(parts,axis=0)
    def combine(d):
        raw=np.empty_like(d)
        for outer in anchors:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured anchor')
            mask=base.outer_fold.eq(outer['fold']).to_numpy();raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(.375*quantile+.375*old_forest+.25*analog)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    finish_research_study(base,dict(incumbent=incumbent,volume_shrink=combine(.375*quantile+.1875*old_forest+.1875*new+.25*analog),
        volume_replace=combine(.375*quantile+.375*new+.25*analog)),output,['volume_shrink','volume_replace'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_relative_volume_forest()
