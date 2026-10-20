"""Train-only covariance and nonoverlapping-neighbor analog density ablations.

Fixed target/cohort. No supervised distance fitting or outer weight search.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.covariance import LedoitWolf

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_empirical_forest import CALIBRATION
from experiment_regime_analog_density import COMPACT
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
FOREST=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
MAGNITUDE=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
ANALOG=ROOT/'reports/regime_analog_density/20261019T071721_721598Z'
MODES={'mahal':('mahalanobis',0),'separated':('euclidean',20),'joint':('mahalanobis',20)}


def metric_analog_mass(train_x,valid_x,returns,low,high,positions,metric='mahalanobis',gap=0,neighbors=100):
    x=np.asarray(train_x,dtype=float);v=np.asarray(valid_x,dtype=float)
    y=np.asarray(returns,dtype=float);low=np.asarray(low,dtype=float);high=np.asarray(high,dtype=float)
    positions=np.asarray(positions)
    if (x.ndim!=2 or v.ndim!=2 or x.shape[1]!=v.shape[1] or not len(x) or not x.shape[1]
            or y.shape!=(len(x),) or low.shape!=(len(v),) or high.shape!=low.shape or neighbors<1
            or positions.shape!=(len(x),) or not np.issubdtype(positions.dtype,np.integer)
            or (np.diff(positions)<=0).any() or gap<0 or metric not in ['euclidean','mahalanobis']
            or any(not np.isfinite(a).all() for a in [x,v,y,low,high]) or (low>high).any()):
        raise ValueError('Invalid mature metric analog inputs')
    center=np.median(x,axis=0);q=np.quantile(x,[.25,.75],axis=0);scale=q[1]-q[0]
    scale=np.where(scale>1e-12,scale,1.);x=(x-center)/scale;v=(v-center)/scale
    shrinkage=None;precision=None;ridge=0.
    if metric=='mahalanobis':
        estimator=LedoitWolf().fit(x)
        ridge=1e-8*max(float(np.trace(estimator.covariance_)/x.shape[1]),1.)
        precision=np.linalg.inv(estimator.covariance_+ridge*np.eye(x.shape[1]))
        distance=cdist(v,x,metric='mahalanobis',VI=precision)
        shrinkage=float(estimator.shrinkage_)
    else:
        distance=cdist(v,x,metric='euclidean')
    if not np.isfinite(distance).all():raise ValueError('Invalid train-fitted metric')
    order=np.argsort(distance,axis=1,kind='stable')
    mass=[];counts=[];effective=[];minimum_gaps=[];hashes=[]
    for row in range(len(v)):
        if gap==0:
            ids=order[row,:min(neighbors,len(x))]
        else:
            allowed=np.ones(len(x),dtype=bool);selected=[]
            for candidate in order[row]:
                if not allowed[candidate]:continue
                selected.append(int(candidate))
                left=np.searchsorted(positions,positions[candidate]-gap+1,side='left')
                right=np.searchsorted(positions,positions[candidate]+gap,side='left')
                allowed[left:right]=False
                if len(selected)==neighbors:break
            ids=np.asarray(selected,dtype=np.int64)
        ds=distance[row,ids];bandwidth=float(np.median(ds))
        weight=np.exp(-.5*(ds/bandwidth)**2) if bandwidth>0 else (ds==0).astype(float)
        weight/=weight.sum();atoms=y[ids]
        mass.append([weight[atoms<low[row]].sum(),weight[(atoms>=low[row])&(atoms<=high[row])].sum(),weight[atoms>high[row]].sum()])
        counts.append(len(ids));effective.append(float(1/(weight**2).sum()))
        if len(ids)>1:minimum_gaps.append(int(np.diff(np.sort(positions[ids])).min()))
        if gap and len(ids)>1 and minimum_gaps[-1]<gap:raise ValueError('Overlapping chosen target windows')
        hashes.append(hashlib.sha256(np.asarray(ids,dtype=np.int64).tobytes()).hexdigest())
    mass=np.asarray(mass);mass/=mass.sum(axis=1,keepdims=True)
    details=dict(metric=metric,gap=gap,center=center.tolist(),scale=scale.tolist(),
        covariance_shrinkage=shrinkage,covariance_ridge=ridge,
        precision=precision.tolist() if precision is not None else None,
        min_neighbors=int(min(counts)),mean_neighbors=float(np.mean(counts)),max_neighbors=int(max(counts)),
        min_effective_neighbors=float(min(effective)),mean_effective_neighbors=float(np.mean(effective)),
        minimum_calendar_separation=min(minimum_gaps) if minimum_gaps else None,
        selection_sha256=hashlib.sha256(json.dumps(hashes).encode()).hexdigest())
    return mass,details


def run_metric_analog(argv=None):
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
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    basic_density=.5*quantile+.25*old_parts[0]+.25*old_parts[1]
    parts=[]
    for view in ['compact','full']:
        for target in ['raw','normalized']:
            path=ANALOG/f'{view}_{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    old_analog=np.mean(parts,axis=0)
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'experiment_regime_analog_density.py',ROOT/'regime_component_archive.py',
        ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_matched_calibration.py',
        ROOT/'experiment_regime_forecast_smoothing.py',CALIBRATION/'selection.json']
    plan.update(mode='covariance_and_nonoverlapping_analog_density_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        feature_views={'compact':COMPACT,'full':jobs['expanding']['names']},modes=MODES,neighbors=100,
        covariance='Train-only median/IQR scaling, LedoitWolf covariance with ridge1e-8*max(trace/d,1). Explicit train-fitted inverse passed to cdist Mahalanobis, never auto-estimated from validation.',
        separation='Stable distance order, greedily select nearest candidate then exclude any training origin whose FULL market-calendar position differs by<20. At most100 selected, fewer if insufficient nonoverlapping origins. Adjacent selected target windows do not overlap; this does not prove statistical independence.',
        kernel='Gaussian with median selected distance bandwidth; zero bandwidth uses only exact-zero selected distances. Same actual class priors, strict thresholds, equal raw/normalized and compact/full components.',
        primary='mahal_half,separated_half,joint_half: replace HALF existing25% analog component. Density .75basic+.125oldEuclidean+.125new. Fixed weights; no outer metric choice.',
        secondary='Each *_replace fully replaces existing analog component: .75basic+.25new. Diagnostic; classifier/inner anchors/current-EMA5 unchanged.',
        maturity='Expanding mature train, refit63. Every selected training target endpoint strictly precedes block prediction start.',
        caveat='Repeated research exposure. No independent confirmation, calibrated probability or deployment claim. Compare each declared method; no outer-best automatic promotion.',
        official_covariance_api='https://scikit-learn.org/1.7/modules/generated/sklearn.covariance.LedoitWolf.html')
    output=args.output_dir or ROOT/'reports/regime_metric_analog'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    new_densities={};audits=[]
    for mode,(metric,gap) in MODES.items():
        parts=[]
        for view,names in plan['feature_views'].items():
            for normalized in [False,True]:
                records=[]
                for outer in jobs['expanding']['folds']:
                    for number,block in enumerate(outer['blocks'],1):
                        train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                        if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured metric analog target')
                        y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                        if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                        positions=pd.DatetimeIndex(calendar.Date).get_indexer(train.Date)
                        if (positions<0).any():raise ValueError('Unknown market calendar position')
                        mass,details=metric_analog_mass(train[names],valid[names],y,-sigma,sigma,positions,metric,gap)
                        prior=np.bincount(train.label,minlength=3)/len(train);score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                        rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                        rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                        audits.append(dict(mode=mode,view=view,normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),
                            latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),**details))
                rows=pd.concat(records,ignore_index=True)
                for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
                rows.to_csv(output/f'{mode}_{view}_{"normalized" if normalized else "raw"}_scores.csv',index=False)
                parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
                print(mode+' '+view+' normalized='+str(normalized)+' complete',flush=True)
        new_densities[mode]=np.mean(parts,axis=0)
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    def combine(d):
        raw=np.empty_like(d)
        for outer in anchors:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured anchor')
            mask=base.outer_fold.eq(outer['fold']).to_numpy();raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(.75*basic_density+.25*old_analog)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    matrices=dict(incumbent=incumbent)
    for mode,d in new_densities.items():
        matrices[mode+'_half']=combine(.75*basic_density+.125*old_analog+.125*d)
        matrices[mode+'_replace']=combine(.75*basic_density+.25*d)
    finish_research_study(base,matrices,output,[mode+'_half' for mode in MODES])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_metric_analog()
