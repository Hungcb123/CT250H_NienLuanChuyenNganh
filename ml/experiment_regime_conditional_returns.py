"""Predeclared four conditional-normal T+20 return baselines, no tuning.

Same three classes and old forecast dates. Normality/constant horizon variance
are assumptions, not guaranteed market facts or calibrated-confidence claims.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.metrics import f1_score

import evaluate_regime_probabilities as audit
native=audit.native
ROOT=native.ROOT
PLAN=native.CONTRACT.parent/'conditional_return_baseline_plan.json'


def conditional_inputs(index):
    daily=np.log(index.Price.astype(float)).diff()
    return pd.DataFrame(dict(Date=index.Date,
        sigma_std20=daily.rolling(20,min_periods=20).std(ddof=1),
        sigma_ewma=np.sqrt(daily.pow(2).ewm(alpha=.06,adjust=False,min_periods=60).mean()),
        mean_zero=np.zeros(len(index)),mean_shrink=.25*daily.rolling(252,min_periods=252).mean()))


def conditional_return_probabilities(mean,sigma):
    mean=np.asarray(mean,dtype=float);sigma=np.asarray(sigma,dtype=float)
    if mean.shape!=sigma.shape or not np.isfinite(mean).all() or not np.isfinite(sigma).all() or (sigma<=0).any():raise ValueError('Invalid past mean/volatility')
    spread=np.sqrt(20)*sigma;location=20*mean
    low=(np.log(.95)-location)/spread;high=(np.log(1.05)-location)/spread
    bear=ndtr(low);side=np.maximum(0.,ndtr(high)-bear);bull=ndtr(-high)
    result=np.column_stack([bear,side,bull]);result/=result.sum(axis=1,keepdims=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=native.CONTRACT)
    parser.add_argument('--plan',type=Path,default=PLAN)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    frozen=json.loads(args.plan.read_text())
    rows,book,calendar,contract,prob_plan=audit.prepare_probability_audit(args.contract,audit.PLAN)
    index,_=native.features.load_market_data(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv')
    inputs=rows[['Date']].merge(conditional_inputs(index),on='Date',how='left',validate='one_to_one',sort=False)
    if not np.isfinite(inputs.drop(columns='Date')).all().all():raise ValueError('Missing predictors on frozen dates; never shrink cohort')
    reference_folder=audit.source.resolved(frozen['probability_audit_reference'])
    ref=pd.read_csv(reference_folder/'probabilities.csv',parse_dates=['Date','label_end_date'])
    for field in ['Date','label_end_date','label']:np.testing.assert_array_equal(ref[field],rows[field])
    prior=ref[['causal_prior_'+c for c in audit.CLASSES]].to_numpy();active=ref.calibration_active.to_numpy(dtype=bool)
    # Independently reconstruct the same null, rather than trust a mutable CSV.
    config=prob_plan['calibration'];positions=pd.DatetimeIndex(calendar).get_indexer(rows.Date)
    anchor=pd.DatetimeIndex(calendar).get_indexer([pd.Timestamp(config['anchor'])])[0]
    buckets=(positions-anchor)//config['refit_market_sessions']
    rebuilt=np.zeros_like(prior)
    for bucket in np.unique(buckets):
        ids=np.flatnonzero(buckets==bucket);boundary=rows.Date.iloc[ids[0]]
        value,_=audit.causal_prior(book,boundary,config['history_rows']);rebuilt[ids]=value
    np.testing.assert_allclose(prior,rebuilt,rtol=1e-12,atol=1e-12)
    output=args.output_dir or ROOT/'reports/regime_conditional_returns'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(frozen,source_sha256=native.sha(__file__),plan_sha256=native.sha(args.plan),
              reference_probability_sha256=native.sha(reference_folder/'probabilities.csv'),native_archive_sha256=prob_plan['archive_sha256'])
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    summary={};intervals=[];table=[];predictions={};loss_prior=audit.proper_losses(rows.label.to_numpy(),prior)
    for volatility in ['sigma_std20','sigma_ewma']:
        for drift in ['mean_zero','mean_shrink']:
            name=volatility+'_'+drift
            p=conditional_return_probabilities(inputs[drift].to_numpy(),inputs[volatility].to_numpy());predictions[name]=p
            metrics=dict(all=audit.probability_metrics(rows,p,np.ones(len(rows),dtype=bool)),active=audit.probability_metrics(rows,p,active),folds=[])
            losses=audit.proper_losses(rows.label.to_numpy(),p)
            for fold in sorted(rows.outer_fold.unique()):metrics['folds'].append(dict(fold=int(fold),**audit.probability_metrics(rows,p,active&(rows.outer_fold.to_numpy()==fold))))
            balanced=(p/prior).argmax(axis=1)
            metrics['balanced_point_mean_fold_f1']=float(np.mean([f1_score(rows.label.iloc[ids],balanced[ids],labels=[0,1,2],average='macro',zero_division=0) for ids in [np.flatnonzero(rows.outer_fold.to_numpy()==fold) for fold in sorted(rows.outer_fold.unique())]]))
            for metric in ['brier','log_loss']:
                delta=loss_prior[metric]-losses[metric]
                for block in [20,60]:intervals.append(dict(method=name,metric=metric,block_sessions=block,point_improvement=float(delta[active].mean()),**audit.bootstrap_probability_delta(delta,active,rows.outer_fold.to_numpy(),block)))
            wins=sum(f['n']>0 and f['brier']<float(loss_prior['brier'][active&(rows.outer_fold.to_numpy()==f['fold'])].mean()) for f in metrics['folds'])
            point=metrics['active']['brier']<float(loss_prior['brier'][active].mean()) and metrics['active']['log_loss']<float(loss_prior['log_loss'][active].mean()) and wins>=3
            paired=all(x['low'] is not None and x['low']>0 for x in intervals if x['method']==name)
            metrics['screen']=dict(point=bool(point),paired=bool(paired),passed=bool(point and paired),brier_fold_wins=wins)
            summary[name]=metrics
            table.append(dict(method=name,all_brier=metrics['all']['brier'],active_brier=metrics['active']['brier'],active_log_loss=metrics['active']['log_loss'],
                              raw_argmax_f1=metrics['all']['mean_fold_argmax_f1'],balanced_point_f1=metrics['balanced_point_mean_fold_f1'],proper_score_screen=bool(point and paired)))
    result=dict(role='Conditional-return three-class DEVELOPMENT, not independent acceptance',n=len(rows),active_comparison_rows=int(active.sum()),
                prior_all=audit.probability_metrics(rows,prior,np.ones(len(rows),dtype=bool)),prior_active=audit.probability_metrics(rows,prior,active),summary=summary,intervals=intervals,
                caveat='Forecast mean/variance only from prices through completed decision close; future20 returns assumed conditionally normal. No actual confidence calibration or portfolio-profit claim.')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    exported=rows[['Date','label_end_date','label','outer_fold','prediction']].copy();exported['active_comparison']=active
    for name,p in predictions.items():
        for code,cls in enumerate(audit.CLASSES):exported[name+'_'+cls]=p[:,code]
    exported.to_csv(output/'probabilities.csv',index=False)
    inputs.to_csv(output/'predictors.csv',index=False)
    print(pd.DataFrame(table).to_string(index=False),flush=True)
    print('Done. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
