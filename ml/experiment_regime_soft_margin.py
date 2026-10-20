"""Distance-to-boundary soft supervision, fixed original evaluation labels.

Three regression heads estimate a smooth membership distribution around the
unchanged +/-1 sigma boundaries. Fixed logistic width .25; no width search.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit
from lightgbm import LGBMRegressor

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


def soft_margin_memberships(z,width=.25):
    """Stable logistic CDF interval mass, including extreme standardized returns."""
    z=np.asarray(z,dtype=float)
    if z.ndim!=1 or not np.isfinite(z).all() or not np.isfinite(width) or width<=0:
        raise ValueError('Invalid standardized returns or margin width')
    bear=expit((-1-z)/width);bull=expit((z-1)/width)
    # sigmoid(b)-sigmoid(a), with b-a=2/width, in a nonnegative
    # product form. Subtracting near-unit tails loses the middle mass.
    side=expit((1-z)/width)*expit((1+z)/width)*(-np.expm1(-2/width))
    mass=np.column_stack([bear,side,bull])
    mass/=mass.sum(axis=1,keepdims=True)
    return mass


def run_soft_margin_density(argv=None):
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
    forests=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv'; paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:
                np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        forests.append(np.mean(parts,axis=0))
    old_density=.5*quantile+.25*forests[0]+.25*forests[1]
    selection=json.loads((CALIBRATION/'selection.json').read_text())
    params=dict(plan['specification']['parameters']);params['objective']='regression'
    paths += [Path(__file__),ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',
        ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'experiment_regime_matched_calibration.py',
        CALIBRATION/'selection.json',MAGNITUDE/'plan.json']
    plan.update(mode='soft_margin_membership_regression_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,width=.25,
        training_targets='z=future_log_return/known_sigma. soft_bear=expit((-1-z)/.25), soft_bull=expit((z-1)/.25), soft_side=1-soft_bear-soft_bull. Three squared-error regressors. Clip negative predictions and renormalize, divide by actual mature hard-label priors and renormalize. Actual evaluation labels unchanged.',
        primary='soft_margin_shrink: .75 existing density+.25 new soft-margin density; same classifier/anchors/current-EMA5.',
        secondary='soft_margin_replace diagnostic only: new density replaces whole old density.',
        maturity='Expanding mature training, refit63 market sessions. No target or width/weight search on outer results.',
        caveat='Research hypothesis: soften supervision in proportion to proximity to threshold. Membership/decision scores are not certified calibrated probabilities; repeated development, no independent test/deployment.')
    output=args.output_dir or ROOT/'reports/regime_soft_margin'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    job=jobs['expanding'];records=[];audits=[]
    for outer in job['folds']:
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured soft membership target')
            z=train.future_log_return.to_numpy()/train.horizon_sigma.to_numpy()
            membership=soft_margin_memberships(z,.25)
            assert (membership>=0).all()
            X=train[job['names']].to_numpy(dtype=np.float32);V=valid[job['names']].to_numpy(dtype=np.float32)
            mass=np.column_stack([LGBMRegressor(**params).fit(X,membership[:,c]).predict(V) for c in range(3)])
            mass=np.maximum(mass,0.)
            if (mass.sum(axis=1)<=0).any():raise ValueError('No soft membership mass')
            mass/=mass.sum(axis=1,keepdims=True)
            prior=np.bincount(train.label,minlength=3)/len(train)
            score=mass/prior;score/=score.sum(axis=1,keepdims=True)
            rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
            rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
            audits.append(dict(fold=outer['fold'],refit_block=number,n_train=len(train),
                latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date())))
        print('Soft margin fold'+str(outer['fold'])+' complete',flush=True)
    rows=pd.concat(records,ignore_index=True)
    for key in ['Date','label_end_date','label','outer_fold']:
        np.testing.assert_array_equal(base[key],rows[key])
    rows.to_csv(output/'soft_scores.csv',index=False)
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    soft=rows[['p_bear','p_side','p_bull']].to_numpy()
    def combine(d):
        raw=np.empty_like(d)
        for outer in selection:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured anchor')
            mask=base.outer_fold.eq(outer['fold']).to_numpy()
            raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(old_density)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    finish_research_study(base,dict(incumbent=incumbent,soft_margin_shrink=combine(.75*old_density+.25*soft),
        soft_margin_replace=combine(soft)),output,['soft_margin_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':
    run_soft_margin_density()
