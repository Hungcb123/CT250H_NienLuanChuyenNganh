"""Quantile-CDF reconstruction and resolution, unchanged adaptive labels.

Primary: linear inverse-CDF interpolation with 19 fixed quantile knots.
No outer weight/threshold search, no probability calibration claim.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr
from lightgbm import LGBMRegressor

import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def quantile_event_masses(points,levels,lower,upper,method='linear',sigma=None):
    points=np.asarray(points,dtype=float);levels=np.asarray(levels,dtype=float)
    lower,upper=np.asarray(lower,dtype=float),np.asarray(upper,dtype=float)
    if (points.shape!=(len(lower),len(levels)) or len(levels)<2 or upper.shape!=lower.shape
        or not all(np.isfinite(v).all() for v in [points,levels,lower,upper])
        or (np.diff(points,axis=1)<0).any() or (np.diff(levels)<=0).any()
        or levels[0]<=0 or levels[-1]>=1 or (lower>=upper).any()):
        raise ValueError('Invalid CDF reconstruction inputs')
    if method=='kernel':
        sigma=np.asarray(sigma,dtype=float)
        if sigma.shape!=lower.shape or not np.isfinite(sigma).all() or (sigma<=0).any():raise ValueError('Invalid smoothing scale')
        edges=np.r_[0.,(levels[:-1]+levels[1:])/2,1.];weights=np.diff(edges)
        bear=(ndtr((lower[:,None]-points)/(.1*sigma[:,None]))*weights).sum(axis=1)
        bull=(ndtr((points-upper[:,None])/(.1*sigma[:,None]))*weights).sum(axis=1)
    elif method=='linear':
        q=np.r_[0.,levels,1.]
        left=points[:,0]-(points[:,1]-points[:,0])*levels[0]/(levels[1]-levels[0])
        right=points[:,-1]+(points[:,-1]-points[:,-2])*(1-levels[-1])/(levels[-1]-levels[-2])
        knots=np.column_stack([left,points,right])
        bear=[];bull=[]
        for row,lo,hi in zip(knots,lower,upper):
            def cdf(x,side):
                j=np.searchsorted(row,x,side=side)
                if j==0:return 0.
                if j==len(row):return 1.
                return float(q[j-1]+(q[j]-q[j-1])*(x-row[j-1])/(row[j]-row[j-1]))
            bear.append(cdf(lo,'left'));bull.append(1-cdf(hi,'right'))
        bear,bull=np.asarray(bear),np.asarray(bull)
    else:raise ValueError('Unknown CDF reconstruction')
    result=np.column_stack([bear,1-bear-bull,bull])
    if (result < -1e-12).any():raise ValueError('Invalid reconstructed event mass')
    result=np.maximum(result,0.);result/=result.sum(axis=1,keepdims=True)
    return result


def run_quantile_resolution(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
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
    classifiers=[];old_scores=[];sources={}
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json']
    for g in ['trend','risk']:
        path=old/(g+'_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        classifiers.append(rows[experts.PROBS].to_numpy())
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        prior=rows[density.BASE_PROBS].to_numpy()
        score=rows[experts.PROBS].to_numpy()/prior;score/=score.sum(axis=1,keepdims=True);old_scores.append(score)
        sources[target]=rows
    classifier=np.mean(classifiers,axis=0);old_density=np.mean(old_scores,axis=0)
    old_levels=np.asarray(plan['specification']['quantile_levels'])
    levels=np.arange(1,20)/20
    added=[float(q) for q in levels if not np.isclose(q,old_levels).any()]
    plan.update(mode='adaptive_quantile_resolution_and_CDF_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},levels19=levels.tolist(),new_levels_to_fit=added,
        primary='linear19_blend: .5 old classifier + .5 reconstructed 19-knot expanding density (equal raw/normalized)',
        secondary='linear19_supplement: .5 old classifier + .25 old density + .25 reconstructed 19-knot density',
        interpolation='Piecewise linear inverse quantile function; extrapolate first/last segment to probability0/1. Flat segments are atoms. Strict event bounds use CDF left/right limits.',
        kernel='Diagnostic Gaussian smoothing of old nine atoms with bandwidth .1 known horizon sigma, fixed before evaluation.',
        reuse='Reuse archived old nine point SETS; fit ten additional quantiles on exact same original cohorts/parameters, then sort all19 together. Old stored points are rearranged but their multiset is unchanged.',
        acceptance='Mean F1 +.01, no decline worst fold or mean bear/bull F1, higher MCC and >=3 fold wins; both paired20/60 lower bounds >0 for provisional evidence.',
        caveats='No new label/weight search or independent test. CDF interpolation is a modeling assumption, not proof of calibrated event probabilities. Inspected development only.')
    output=args.output_dir or ROOT/'reports/regime_quantile_resolution'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    reconstructed={'linear9':[],'kernel9':[],'linear19':[]}
    job=jobs['expanding']
    for normalized in [False,True]:
        target='normalized' if normalized else 'raw';saved=sources[target]
        points=saved[[f'ordered_log_q{round(q*100):02d}' for q in old_levels]].to_numpy()
        sigma=saved.horizon_sigma.to_numpy();prior=saved[density.BASE_PROBS].to_numpy()
        for method,key in [('linear','linear9'),('kernel','kernel9')]:
            mass=quantile_event_masses(points,old_levels,-sigma,sigma,method,sigma)
            score=mass/prior;score/=score.sum(axis=1,keepdims=True);reconstructed[key].append(score)
        high=[];audits=[]
        for outer in job['folds']:
            for number,block in enumerate(outer['blocks'],1):
                train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured additional quantile target')
                part=saved.loc[(saved.outer_fold==outer['fold'])&(saved.refit_block==number)]
                for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(part[key],valid[key])
                expected=np.bincount(train.label,minlength=3)/len(train)
                np.testing.assert_allclose(part[density.BASE_PROBS],np.tile(expected,(len(part),1)),atol=1e-12)
                y=train.future_log_return.to_numpy()
                if normalized:y=y/train.horizon_sigma.to_numpy()
                new=[]
                for alpha in added:
                    model=LGBMRegressor(**plan['specification']['parameters'],alpha=alpha)
                    model.fit(train[job['names']].to_numpy(dtype=np.float32),y)
                    values=model.predict(valid[job['names']].to_numpy(dtype=np.float32))
                    if normalized:values*=valid.horizon_sigma.to_numpy()
                    new.append(values)
                old_points=part[[f'ordered_log_q{round(q*100):02d}' for q in old_levels]].to_numpy()
                combined=np.sort(np.column_stack([old_points]+new),axis=1)
                mass=quantile_event_masses(combined,levels,-valid.horizon_sigma.to_numpy(),valid.horizon_sigma.to_numpy())
                score=mass/expected;score/=score.sum(axis=1,keepdims=True);high.append(score)
                rows=valid[['Date','label_end_date','label']].copy()
                for i,q in enumerate(levels):rows[f'log_q{round(q*100):02d}']=combined[:,i]
                rows.to_csv(output/(target+'_knots19.csv'),mode='a',header=not (output/(target+'_knots19.csv')).exists(),index=False)
                audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date())))
            (output/(target+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
            print(target+' fold '+str(outer['fold'])+' extra quantiles complete',flush=True)
        reconstructed['linear19'].append(np.concatenate(high))
    matrices={'incumbent':.5*classifier+.5*old_density}
    for name,values in reconstructed.items():
        score=np.mean(values,axis=0)
        matrices[name]=score
        matrices[name+'_blend']=.5*classifier+.5*score
        matrices[name+'_supplement']=.5*classifier+.25*old_density+.25*score
    finish_research_study(base,matrices,output,['linear19_blend','linear19_supplement'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_quantile_resolution()
