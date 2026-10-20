"""Predeclared dense-return quantiles mapped to the ORIGINAL three classes.

Same old dates/labels/features. Four return forecasters, two fixed decisions.
No confidence subset, target relabeling, outer tuning or live export.
"""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import classification_report,log_loss

import experiment_regime as exp

ROOT=Path(__file__).resolve().parent
SPEC_PATH=ROOT/'reports/regime_families/20261018T154106_332331Z/next_return_distribution_plan.json'
PROBS=['p_bear','p_side','p_bull']
BASE_PROBS=['base_bear','base_side','base_bull']
DECISIONS=['prediction_raw','prediction_prior_balanced']


def trailing_horizon_sigma(index):
    returns=np.log(index.Price.astype(float)).diff()
    return pd.DataFrame(dict(Date=index.Date,horizon_sigma=returns.rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)))


def quantile_class_mass(log_quantiles,weights):
    points=np.sort(np.asarray(log_quantiles,dtype=float),axis=1)
    weights=np.asarray(weights,dtype=float)
    if points.ndim!=2 or points.shape[1]!=len(weights) or not np.isfinite(points).all():raise ValueError('Invalid quantile predictions')
    if not np.isfinite(weights).all() or (weights<0).any() or not np.isclose(weights.sum(),1.):raise ValueError('Invalid quadrature weights')
    bear=points<np.log(.95);bull=points>np.log(1.05);side=~(bear|bull)
    probability=np.column_stack([(mask*weights).sum(axis=1) for mask in [bear,side,bull]])
    probability/=probability.sum(axis=1,keepdims=True)
    np.testing.assert_allclose(probability.sum(axis=1),1.)
    return probability,points


def fit_return_quantiles(train,valid,names,normalized,specification):
    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured return supervision')
    y=train.future_log_return.to_numpy(dtype=float)
    if normalized:
        if not np.isfinite(train.horizon_sigma).all() or (train.horizon_sigma<=0).any():raise ValueError('Invalid training sigma')
        y=y/train.horizon_sigma.to_numpy()
    if not np.isfinite(y).all():raise ValueError('Invalid regression target')
    X,V=train[names].to_numpy(dtype=np.float32),valid[names].to_numpy(dtype=np.float32)
    predictions=[]
    for alpha in specification['quantile_levels']:
        model=LGBMRegressor(**specification['parameters'],alpha=alpha)
        model.fit(X,y)
        predictions.append(model.predict(V))
    raw=np.column_stack(predictions)
    crossings=int((np.diff(raw,axis=1)<0).any(axis=1).sum())
    if normalized:
        if not np.isfinite(valid.horizon_sigma).all() or (valid.horizon_sigma<=0).any():raise ValueError('Invalid known prediction sigma')
        raw=raw*valid.horizon_sigma.to_numpy()[:,None]
    probability,ordered=quantile_class_mass(raw,specification['quantile_atom_weights'])
    return probability,ordered,crossings


def prepare_return_distribution(args):
    specification=json.loads(SPEC_PATH.read_text())
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','--train-windows','3y','expanding',
        '--models','LightGBM','--horizons','20','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    frame=frames[20]
    index,audit=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    if audit['sha256']!=plan['input_hashes']['VNINDEX']:raise ValueError('Index input changed')
    frame=frame.merge(trailing_horizon_sigma(index),on='Date',how='left',validate='one_to_one',sort=False)
    frame['future_log_return']=np.log1p(frame.future_return)
    if not np.isfinite(frame[['horizon_sigma','future_log_return']]).all().all() or (frame.horizon_sigma<=0).any():raise ValueError('Undefined return/sigma on fixed cohort')
    reference=pd.read_csv(args.control_dir/'t20_LightGBM_trend_3y_predictions.csv',parse_dates=['Date','label_end_date'])
    for job in jobs:
        frozen=np.concatenate([b['validation'] for o in job['folds'] for b in o['blocks']])
        for key in ['Date','label_end_date','label']:
            np.testing.assert_array_equal(frame[key].iloc[frozen].to_numpy(),reference[key].to_numpy())
        np.testing.assert_allclose(frame.future_return.iloc[frozen],reference.future_return,rtol=1e-12,atol=1e-12)
        for outer in job['folds']:
            for block in outer['blocks']:
                if frame.label_end_date.iloc[block['train']].max()>=frame.Date.iloc[block['validation']].min():raise ValueError('Invalid return training boundary')
    source=json.loads((args.control_dir/'experiment_report.json').read_text())
    controls=[next(r for r in source['results'] if r['horizon']==20 and r['feature_group']==group and r['train_window']=='3y') for group in ['trend','risk']]
    plan.update(mode='dense_return_to_original_three_class_development',specification=specification,
                specification_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                configs=[dict(window=w,normalized=n) for w in ['3y','expanding'] for n in [False,True]],
                optuna=None,decisions=DECISIONS,environment={p:version(p) for p in ['numpy','pandas','scikit-learn','lightgbm']},
                supplementary_metrics='Raw quadrature mass log loss/Brier vs causal training-class frequency; descriptive only, not substituted for original macro-F1 acceptance.',
                control_report_sha256=hashlib.sha256((args.control_dir/'experiment_report.json').read_bytes()).hexdigest())
    return frame,{j['window']:j for j in jobs},controls,plan


def run_return_distribution(frame,job,normalized,specification,output,name):
    records=[];audits=[]
    for outer in job['folds']:
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            probability,ordered,crossings=fit_return_quantiles(train,valid,job['names'],normalized,specification)
            prior=np.bincount(train.label.to_numpy(dtype=int),minlength=3)/len(train)
            if (prior<=0).any():raise ValueError('Missing training prior')
            rows=valid[['Date','label_end_date','label','future_return','horizon_sigma']].copy()
            rows[PROBS]=probability;rows[BASE_PROBS]=np.tile(prior,(len(rows),1))
            rows['prediction_raw']=probability.argmax(axis=1)
            rows['prediction_prior_balanced']=(probability/prior).argmax(axis=1)
            rows['baseline_prediction']=prior.argmax()
            rows['outer_fold'],rows['refit_block']=outer['fold'],number
            for k,alpha in enumerate(specification['quantile_levels']):rows[f'ordered_log_q{round(alpha*100):02d}']=ordered[:,k]
            records.append(rows)
            audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),
                               train_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),
                               prediction_end=str(valid.Date.max().date()),class_prior=prior.tolist(),pre_sort_crossing_rows=crossings))
        pd.concat(records,ignore_index=True).to_csv(output/(name+'_predictions.csv'),index=False)
        (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
        print(name,'fold',outer['fold'],'complete',flush=True)
    return pd.concat(records,ignore_index=True)


def summarize_return_forecasts(name,rows):
    results=[]
    for decision in DECISIONS:
        record=rows.assign(prediction=rows[decision])
        folds=[dict(fold=int(n),**exp.prediction_metrics(part),
                    per_class=classification_report(part.label,part.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0)) for n,part in record.groupby('outer_fold')]
        probabilities=rows[PROBS].to_numpy();priors=rows[BASE_PROBS].to_numpy();truth=np.eye(3)[rows.label.to_numpy(dtype=int)]
        results.append(dict(candidate=name+'/'+decision,mean_f1=float(np.mean([f['f1_macro'] for f in folds])),worst_f1=min(f['f1_macro'] for f in folds),
                            mean_mcc=float(np.mean([f['mcc'] for f in folds])),folds=folds,pooled=exp.prediction_metrics(record),
                            raw_mass_log_loss=float(log_loss(rows.label,probabilities,labels=[0,1,2])),prior_log_loss=float(log_loss(rows.label,priors,labels=[0,1,2])),
                            raw_mass_brier=float(np.square(probabilities-truth).sum(axis=1).mean()),prior_brier=float(np.square(priors-truth).sum(axis=1).mean())))
    return results


def write_return_report(results,controls,output):
    table=[]
    for r in results:
        comparisons=[]
        for c in controls:
            wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(r['folds'],c['folds']))
            passed=r['mean_f1']>=c['mean_f1']+.02 and r['worst_f1']>=c['worst_f1'] and r['mean_mcc']>c['mean_mcc'] and wins>=3
            comparisons.append(dict(control=c['candidate'],fold_wins=wins,passed=bool(passed)))
        table.append(dict(candidate=r['candidate'],mean_f1=r['mean_f1'],worst_f1=r['worst_f1'],mean_mcc=r['mean_mcc'],pooled_f1=r['pooled']['f1_macro'],
                          mass_brier=r['raw_mass_brier'],prior_brier=r['prior_brier'],development_screen_both_controls=all(c['passed'] for c in comparisons),comparisons=comparisons))
    (output/'report.json').write_text(json.dumps(dict(role='three_class_development_not_independent_test',results=results,controls=controls,comparison=table),indent=2)+'\n')
    pd.DataFrame([{k:v for k,v in r.items() if k!='comparisons'} for r in table]).to_csv(output/'comparison.csv',index=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    frame,jobs,controls,plan=prepare_return_distribution(args)
    output=args.output_dir or ROOT/'reports/regime_return_distribution'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    results=[]
    for window in ['3y','expanding']:
        for normalized in [False,True]:
            name=window+('_normalized' if normalized else '_raw')
            rows=run_return_distribution(frame,jobs[window],normalized,plan['specification'],output,name)
            summary=summarize_return_forecasts(name,rows);results.extend(summary)
            write_return_report(results,controls,output)
            print([(r['candidate'],round(r['mean_f1'],4),round(r['worst_f1'],4)) for r in summary],flush=True)
    print('Done; original three-class target, DEVELOPMENT only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
