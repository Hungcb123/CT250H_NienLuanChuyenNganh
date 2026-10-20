"""Calibrate fusion/temperature using mature archived outcomes only.

No refitting on current or future target labels; preset coarse grid, no outer
winner selection. Current ground truth remains the original adaptive target.
"""
import argparse
from datetime import datetime,timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import numpy as np
import pandas as pd

from experiment_regime_forecast_smoothing import causal_forecast_ema
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
GRID=[(.5,1.,1.)]+[v for v in product([.25,.4,.5,.6,.75],[.75,1.,1.5],[.75,1.,1.5]) if v!=(.5,1.,1.)]


def macro_scores_many(actual,predictions):
    actual=np.asarray(actual,dtype=int);predictions=np.asarray(predictions,dtype=int)
    if predictions.ndim!=2 or predictions.shape[1]!=len(actual) or not np.isin(actual,[0,1,2]).all() or not np.isin(predictions,[0,1,2]).all():raise ValueError('Invalid fixed-class macro inputs')
    n=len(predictions)
    flat=9*np.arange(n)[:,None]+3*actual[None,:]+predictions
    matrix=np.bincount(flat.ravel(),minlength=n*9).reshape(n,3,3)
    numerator=2*np.diagonal(matrix,axis1=1,axis2=2)
    denominator=matrix.sum(axis=1)+matrix.sum(axis=2)
    return np.divide(numerator,denominator,out=np.zeros_like(numerator,dtype=float),where=denominator>0).mean(axis=1)


def choose_temporal_fusion(base,classifier,density,calendar):
    classifier,density=np.asarray(classifier),np.asarray(density)
    positions=pd.DatetimeIndex(calendar).get_indexer(base.Date)
    if (positions<0).any() or classifier.shape!=(len(base),3) or density.shape!=classifier.shape:raise ValueError('Invalid fusion input')
    all_scores=[]
    for weight,tc,td in GRID:
        c=np.maximum(classifier,0.)**(1/tc);c/=c.sum(axis=1,keepdims=True)
        d=np.maximum(density,0.)**(1/td);d/=d.sum(axis=1,keepdims=True)
        all_scores.append((1-weight)*c+weight*d)
    all_scores=np.asarray(all_scores)
    predictions=all_scores.argmax(axis=2)
    penalty=np.array([.005*((2*(w-.5))**2+np.log(tc)**2+np.log(td)**2) for w,tc,td in GRID])
    output={252:[],504:[]};audit=[];selected={252:0,504:0};last_bucket=None
    buckets=(positions-positions[0])//20
    for row,boundary in enumerate(base.Date):
        if buckets[row]!=last_bucket:
            known=np.flatnonzero(((base.Date<boundary)&(base.label_end_date<boundary)).to_numpy())
            for window in [252,504]:
                ids=known[-window:];y=base.label.iloc[ids].to_numpy(dtype=int)
                counts=np.bincount(y,minlength=3) if len(y) else np.zeros(3,dtype=int)
                ready=len(ids)>=126 and len(counts)==3 and (counts>=5).all()
                selected[window]=0
                info=dict(Date=str(boundary.date()),window=window,n_history=len(ids),latest_label_end=str(base.label_end_date.iloc[ids].max()) if len(ids) else None,ready=bool(ready))
                if ready:
                    values=macro_scores_many(y,predictions[:,ids])-penalty
                    best=int(values.argmax())
                    if values[best]>=values[0]+.01:selected[window]=best
                    info.update(past_best=float(values[best]),past_incumbent=float(values[0]))
                info.update(choice=selected[window],parameters=GRID[selected[window]])
                audit.append(info)
            last_bucket=buckets[row]
        for window in output:output[window].append(all_scores[selected[window],row])
    return {k:np.asarray(v) for k,v in output.items()},audit


def run_temporal_fusion(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-dir',type=Path,default=ROOT/'reports/regime_density_seeds/20261019T061537_193740Z')
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_forecast_smoothing/20261019T062316_546117Z')
    parser.add_argument('--info-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source=args.source_dir/'ema5_shrink_predictions.csv';base=pd.read_csv(source,parse_dates=['Date','label_end_date']);base['majority']=base.baseline_prediction
    columns=['p_bear','p_side','p_bull']
    index=pd.read_csv(args.data_dir/'VNINDEX.csv',parse_dates=['Date'])
    for folder in [args.seed_dir,args.source_dir]:
        parent=json.loads((folder/'plan.json').read_text())
        for path,digest in parent['source_hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+path)
    old=args.parent_dir/'vol_1sigma';risk=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],risk[key])
    selected=np.empty((len(base),3));paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_forecast_smoothing.py',source,args.seed_dir/'plan.json',args.data_dir/'VNINDEX.csv',args.info_dir/'inner_selection.json',old/'risk_predictions.csv']
    for choice in json.loads((args.info_dir/'inner_selection.json').read_text()):
        path=args.info_dir/(choice['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        mask=base.outer_fold.eq(choice['fold']).to_numpy();selected[mask]=rows.loc[mask,columns].to_numpy()
    classifier=.5*(selected+risk[columns].to_numpy())
    parts=[]
    for seed in [7,21,42,84,126]:
        for target in ['raw','normalized']:
            path=old/('expanding_'+target+'_mapped_predictions.csv') if seed==42 else args.seed_dir/f'seed{seed}_{target}_scores.csv'
            paths.append(path);rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            score=rows[columns].to_numpy()
            if seed==42:
                score=score/rows[['base_bear','base_side','base_bull']].to_numpy();score/=score.sum(axis=1,keepdims=True)
            parts.append(score)
    density=np.mean(parts,axis=0);fixed=.5*classifier+.5*density
    expected=.5*fixed+.5*causal_forecast_ema(base.Date,fixed,index.Date,5)
    np.testing.assert_allclose(expected,base[columns],atol=1e-12,rtol=1e-12)
    output=args.output_dir or ROOT/'reports/regime_temporal_fusion'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='past_outcome_fusion_calibration_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},grid=GRID,
        timing='Refresh20 raw sessions; only archived outcomes whose label_end_date STRICTLY precedes boundary; min126 rows and5 each class. Hold weights between refreshes.',
        selection='Regularized past macroF1 on fixed grid, require >=.01 improvement over w=.5,Tc=Td=1. Penalty .005*[(2(w-.5))^2+logTc^2+logTd^2].',
        primary='adaptive_pool_smoothed: pool .5 fixed/.25 adaptive252/.25 adaptive504 scores, then equal current/causalEMA5',
        secondary='adaptive504_smoothed: equal current adaptive504/its causalEMA5',
        caveat='Training-only temperatures transform decision scores, not calibrated probabilities. No ground-truth label smoothing, outer winner selection, independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print('Output: '+str(output.resolve()),flush=True)
    values,audit=choose_temporal_fusion(base,classifier,density,index.Date)
    pooled=.5*fixed+.25*values[252]+.25*values[504]
    matrices=dict(incumbent=base[columns].to_numpy(),adaptive_pool_smoothed=.5*pooled+.5*causal_forecast_ema(base.Date,pooled,index.Date,5),
        adaptive504_smoothed=.5*values[504]+.5*causal_forecast_ema(base.Date,values[504],index.Date,5))
    for window in values:matrices['adaptive'+str(window)+'_raw']=values[window]
    checks=[]
    for end in [390,780,1170,1460,1560]:
        prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_=choose_temporal_fusion(prefix,classifier[:end],density[:end],index.Date[index.Date<=cutoff])
        for window in values:np.testing.assert_allclose(actual[window],values[window][:end],atol=1e-12,rtol=1e-12)
        checks.append(dict(rows=end,future_label_corruption_invariant=True))
    (output/'weight_history.json').write_text(json.dumps(audit,indent=2)+'\n')
    (output/'causality_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
    finish_research_study(base,matrices,output,['adaptive_pool_smoothed','adaptive504_smoothed'])
    return output


if __name__=='__main__':run_temporal_fusion()
