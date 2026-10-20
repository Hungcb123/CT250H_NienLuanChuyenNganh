"""Fixed local empirical return distributions from mature historical analogs.

100 nearest mature observations after TRAIN-only median/IQR scaling. Equal
compact/full feature views and raw/normalized return atoms, no outer search.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_empirical_forest import CALIBRATION
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
FOREST=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
MAGNITUDE=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
COMPACT=['ROC_20','ROC60','DistSMA200','HV_20','ETF_ReturnSpread20','RSI_14']


def analog_return_mass(train_x,valid_x,returns,low,high,neighbors=100):
    x=np.asarray(train_x,dtype=float);v=np.asarray(valid_x,dtype=float)
    y=np.asarray(returns,dtype=float);low=np.asarray(low,dtype=float);high=np.asarray(high,dtype=float)
    if (x.ndim!=2 or v.ndim!=2 or x.shape[1]!=v.shape[1] or not len(x) or not x.shape[1]
            or y.shape!=(len(x),) or low.shape!=(len(v),) or high.shape!=low.shape or neighbors<1
            or any(not np.isfinite(a).all() for a in [x,v,y,low,high]) or (low>high).any()):
        raise ValueError('Invalid mature analog inputs')
    center=np.median(x,axis=0);q=np.quantile(x,[.25,.75],axis=0);scale=q[1]-q[0]
    scale=np.where(scale>1e-12,scale,1.)
    distance=cdist((v-center)/scale,(x-center)/scale,metric='euclidean')
    ids=np.argsort(distance,axis=1,kind='stable')[:,:min(neighbors,len(x))]
    nearest=np.take_along_axis(distance,ids,axis=1);bandwidth=np.median(nearest,axis=1)
    safe=np.where(bandwidth>0,bandwidth,1.)
    weight=np.exp(-.5*(nearest/safe[:,None])**2)
    weight[bandwidth==0]=(nearest[bandwidth==0]==0).astype(float)
    weight/=weight.sum(axis=1,keepdims=True)
    atoms=y[ids]
    bear=(weight*(atoms<low[:,None])).sum(axis=1)
    bull=(weight*(atoms>high[:,None])).sum(axis=1)
    # Explicit middle indicator avoids cancellation if tail mass is near1.
    side=(weight*((atoms>=low[:,None])&(atoms<=high[:,None]))).sum(axis=1)
    mass=np.column_stack([bear,side,bull]);mass/=mass.sum(axis=1,keepdims=True)
    details=dict(n_neighbors=ids.shape[1],center=center.tolist(),scale=scale.tolist(),
        min_effective_neighbors=float((1/(weight**2).sum(axis=1)).min()),
        mean_effective_neighbors=float((1/(weight**2).sum(axis=1)).mean()),
        neighbor_ids_sha256=hashlib.sha256(ids.tobytes()).hexdigest(),
        bandwidth_mean=float(bandwidth.mean()))
    return mass,details


def run_analog_density(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,classifier,quantile,calendar,paths=load_seed_components(MAGNITUDE/'magnitude_shrink_predictions.csv')
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    old_density=.5*quantile+.25*old_parts[0]+.25*old_parts[1]
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',
        ROOT/'experiment_regime_matched_calibration.py',ROOT/'experiment_regime_forecast_smoothing.py',CALIBRATION/'selection.json']
    plan.update(mode='mature_analog_empirical_density_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        feature_views={'compact':COMPACT,'full':jobs['expanding']['names']},neighbors=100,
        method='Median/IQR scaling from mature training rows only, zero IQR->1. Euclidean nearest100 with stable training-order ties. Gaussian weights with median selected distance as bandwidth. At bandwidth0 use only exact-zero-distance selected neighbors. No label-conditioned metric or bandwidth search.',
        targets='Equal raw/normalized empirical return atoms; evaluate strict below/above prediction-day +/-sigma for raw, +/-1 for normalized. Equality neutral. Equal compact/full views. Divide by actual mature hard-label training priors.',
        primary='analog_shrink: .75 existing density+.25 new analog density; secondary .5 existing+.5 analog. Same classifier/anchors/current-EMA5, no outer weight selection.',
        maturity='Expanding mature training, refit63. Every analog target endpoint strictly before first prediction date of block.',
        caveat='Historical analogs remain serially dependent; not independent new samples, calibrated probabilities, independent test or deployment.',
        official_distance_api='https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.cdist.html')
    output=args.output_dir or ROOT/'reports/regime_analog_density'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    audits=[];parts=[]
    for view,names in plan['feature_views'].items():
        for normalized in [False,True]:
            records=[]
            for outer in jobs['expanding']['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured analog target')
                    y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                    if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                    mass,details=analog_return_mass(train[names],valid[names],y,-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train)
                    if (prior<=0).any():raise ValueError('Missing mature target class')
                    score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(view=view,normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),
                        latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),**details))
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            rows.to_csv(output/f'{view}_{"normalized" if normalized else "raw"}_scores.csv',index=False)
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
            print(view+' normalized='+str(normalized)+' complete',flush=True)
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
    finish_research_study(base,dict(incumbent=incumbent,analog_shrink=combine(.75*old_density+.25*new_density),
        analog_half=combine(.5*old_density+.5*new_density)),output,['analog_shrink','analog_half'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_analog_density()
