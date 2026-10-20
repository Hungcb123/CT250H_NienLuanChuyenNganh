"""Mature-outcome fusion adaptation initialized by purged-inner coefficients."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID,macro_scores_many
from experiment_regime_forecast_smoothing import causal_forecast_ema
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def replay_anchored_fusion(base,classifier,density,calendar,anchors):
    raw=np.asarray([fused_scores(classifier,density,p) for p in GRID])
    smoothed=np.asarray([.5*p+.5*causal_forecast_ema(base.Date,p,calendar,5) for p in raw])
    positions=pd.DatetimeIndex(calendar).get_indexer(base.Date)
    if (positions<0).any():raise ValueError('Missing anchor calendar date')
    buckets=(positions-positions[0])//20;last_bucket=None;last_fold=None;history=[]
    output={252:[],504:[]};selected={252:0,504:0};prior=[]
    for row,boundary in enumerate(base.Date):
        fold=int(base.outer_fold.iloc[row]);anchor=anchors[fold]
        prior.append(raw[anchor,row])
        if buckets[row]!=last_bucket or fold!=last_fold:
            known=np.flatnonzero(((base.Date<boundary)&(base.label_end_date<boundary)).to_numpy())
            aw,ac,ad=GRID[anchor]
            penalty=np.array([.005*((2*(w-aw))**2+np.log(tc/ac)**2+np.log(td/ad)**2) for w,tc,td in GRID])
            for window in [252,504]:
                ids=known[-window:];y=base.label.iloc[ids].to_numpy(dtype=int)
                counts=np.bincount(y,minlength=3) if len(y) else np.zeros(3,dtype=int)
                ready=len(y)>=126 and len(counts)==3 and (counts>=5).all();choice=anchor
                record=dict(Date=str(boundary.date()),fold=fold,window=window,n_history=len(ids),ready=bool(ready),anchor=anchor,
                    latest_label_end=str(base.label_end_date.iloc[ids].max()) if len(ids) else None)
                if ready:
                    values=macro_scores_many(y,smoothed[:,ids].argmax(axis=2))-penalty
                    best=int(values.argmax())
                    if values[best]>=values[anchor]+.01:choice=best
                    record.update(past_best=float(values[best]),past_anchor=float(values[anchor]))
                selected[window]=choice;record.update(choice=choice,parameters=GRID[choice]);history.append(record)
            last_bucket=buckets[row];last_fold=fold
        for window in output:output[window].append(raw[selected[window],row])
    return {k:np.asarray(v) for k,v in output.items()},np.asarray(prior),history


def run_anchored_fusion(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-dir',type=Path,default=ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,classifier,density,index,paths=load_seed_components(args.calibration_dir/'matched_robust_predictions.csv')
    selection=json.loads((args.calibration_dir/'selection.json').read_text());anchors={}
    for row in selection:
        parameters=tuple(row['candidates'][row['chosen']['robust']]['parameters'])
        anchors[row['fold']]=GRID.index(parameters)
        if pd.Timestamp(row['latest_tuning_label_end'])>=pd.Timestamp(row['outer_boundary']):raise ValueError('Unmatured coefficient anchor')
        if base.loc[base.outer_fold.eq(row['fold']),'Date'].min()<pd.Timestamp(row['outer_boundary']):raise ValueError('Anchor chosen after forecast')
    paths += [Path(__file__),ROOT/'experiment_regime_matched_calibration.py',ROOT/'experiment_regime_temporal_fusion.py',ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',args.calibration_dir/'selection.json']
    output=args.output_dir or ROOT/'reports/regime_anchored_fusion'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='purged_inner_prior_mature_online_fusion_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        anchors={str(k):GRID[v] for k,v in anchors.items()},grid=GRID,windows=[252,504],
        selection='Default to preset purged-inner robust anchor each fold. Every20 market sessions (also at fold change), use only126+ mature OOF outcomes/5 each class. Optimize EMA-blended candidate macroF1 minus squared distance penalty to anchor; require +.01 past improvement.',
        primary='anchored_pool: half inner-prior raw forecast, quarter adaptive252 and quarter adaptive504; then equal current/causalEMA5',
        secondary='anchored_adaptive: equal adaptive252/504 raw forecasts; same EMA5 mixture',
        timing='Anchor chosen before outer start; adjustments require label_end_date strictly before decision. No backward smoothing, current-label fit or outer coefficient selection.',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, higher MCC and >=3 wins; paired20/60 lower>0 for provisional evidence.',
        caveat='Prior branch was identified after inspected historical outcomes; post-hoc study design remains. No independent acceptance, calibrated probabilities or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print('Output: '+str(output.resolve()),flush=True)
    values,prior,history=replay_anchored_fusion(base,classifier,density,index.Date,anchors)
    expected=.5*prior+.5*causal_forecast_ema(base.Date,prior,index.Date,5)
    np.testing.assert_allclose(expected,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    pooled=.5*prior+.25*values[252]+.25*values[504];adaptive=.5*values[252]+.5*values[504]
    matrices=dict(incumbent=expected,anchored_pool=.5*pooled+.5*causal_forecast_ema(base.Date,pooled,index.Date,5),
        anchored_adaptive=.5*adaptive+.5*causal_forecast_ema(base.Date,adaptive,index.Date,5))
    for window in values:matrices[f'anchored{window}_diagnostic']=.5*values[window]+.5*causal_forecast_ema(base.Date,values[window],index.Date,5)
    checks=[]
    for end in [390,780,1170,1460,1560]:
        prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_,_=replay_anchored_fusion(prefix,classifier[:end],density[:end],index.Date[index.Date<=cutoff],anchors)
        for window in values:np.testing.assert_allclose(actual[window],values[window][:end],atol=1e-12,rtol=1e-12)
        checks.append(dict(rows=end,unmatured_target_corruption_invariant=True))
    (output/'weight_history.json').write_text(json.dumps(history,indent=2)+'\n');(output/'causality_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
    finish_research_study(base,matrices,output,['anchored_pool','anchored_adaptive'])
    return output


if __name__=='__main__':run_anchored_fusion()
