"""Controlled transfer across historical indices for THREE-CLASS T+20 forecasts.

No present-day constituent basket. All labels shift on the full VNINDEX calendar
before filtering; all assets share the same causal time boundary. DEVELOPMENT.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

import experiment_regime as exp
import experiment_regime_indices as indices
import experiment_regime_multiclass as metrics

ROOT=Path(__file__).resolve().parent
CONFIGS=[(window,capacity,pooled) for window in ['3y','expanding']
         for capacity in ['shallow','medium'] for pooled in [False,True]]
PARAMETERS={
 'shallow':dict(n_estimators=150,learning_rate=.03,max_depth=3,num_leaves=7,min_child_samples=50),
 'medium':dict(n_estimators=300,learning_rate=.03,max_depth=4,num_leaves=15,min_child_samples=30)}
COMMON=dict(colsample_bytree=.7,reg_alpha=.1,reg_lambda=1.,random_state=42,n_jobs=2,verbosity=-1)


def panel_features(calendar,observations,symbol):
    """Every source uses full market calendar and the same scale-free 12 features."""
    if observations.Date.duplicated().any():raise ValueError('Duplicate source session')
    if len(pd.DatetimeIndex(observations.Date).difference(pd.DatetimeIndex(calendar))):
        raise ValueError('Source outside VNINDEX market calendar')
    joined=pd.DataFrame({'Date':calendar}).merge(observations[['Date','Price']],on='Date',how='left',validate='one_to_one',sort=False)
    feature,names=exp.base.build_feature_matrix(joined,feature_set='close')
    # Critical: missing rows remain here until raw-calendar end dates are set.
    frame=exp.base.create_labels(feature,20,names)
    frame['symbol']=symbol
    return frame,names


def training_panel(target,auxiliary,boundary,window,pooled):
    """Date selection BEFORE concatenation; no row-count split across assets."""
    boundary=pd.Timestamp(boundary)
    earliest=boundary-pd.DateOffset(years=3) if window=='3y' else pd.Timestamp.min
    target_rows=target.loc[(target.Date>=earliest)&(target.Date<boundary)&(target.label_end_date<boundary)].copy()
    if len(target_rows)<150 or target_rows.label.nunique()!=3:
        raise ValueError('Insufficient target history/classes')
    rows=[target_rows]
    if pooled:
        # Only add assets on target-eligible dates: total date exposure is held fixed.
        aux=auxiliary.loc[(auxiliary.Date>=earliest)&(auxiliary.Date<boundary)&(auxiliary.label_end_date<boundary)&auxiliary.Date.isin(target_rows.Date)].copy()
        rows.append(aux)
    train=pd.concat(rows,ignore_index=True).sort_values(['Date','symbol']).reset_index(drop=True)
    if train.duplicated(['Date','symbol']).any():raise ValueError('Duplicate asset/session')
    target_mask=train.symbol.eq('VNINDEX')
    if pooled:
        aux_count=train.loc[~target_mask].groupby('Date').size()
        count=train.Date.map(aux_count).fillna(0).to_numpy()
        weights=np.where(target_mask.to_numpy(),np.where(count>0,.5,1.),np.divide(.5,count,out=np.zeros(len(count)),where=count>0))
    else:
        weights=np.ones(len(train))
    base_weights=pd.Series(weights,index=train.index)
    np.testing.assert_allclose(base_weights.groupby(train.Date).sum().to_numpy(),1.,atol=1e-12)
    # Compute class cost from weighted DATE mass, not correlated row counts.
    class_mass=np.bincount(train.label.to_numpy(dtype=int),weights=weights,minlength=3)
    factors=weights.sum()/(3*class_mass)
    fit_weights=weights*factors[train.label.to_numpy(dtype=int)]
    if train.label_end_date.max()>=boundary:raise ValueError('Unmatured pooled label')
    audit=dict(n_target=len(target_rows),n_auxiliary=int((~target_mask).sum()),unique_dates=int(train.Date.nunique()),
               by_symbol={str(k):int(v) for k,v in train.symbol.value_counts().items()},
               latest_label_end=str(train.label_end_date.max().date()),
               auxiliary_latest_label_end=str(train.loc[~target_mask,'label_end_date'].max().date()) if (~target_mask).any() else None,
               base_mass=float(weights.sum()),class_base_mass=class_mass.tolist(),class_cost_factors=factors.tolist(),
               weighted_class_mass=np.bincount(train.label.to_numpy(dtype=int),weights=fit_weights,minlength=3).tolist())
    return train,fit_weights,audit


def map_frozen_dates(target,reference_frame,reference_folds):
    calendar=pd.DatetimeIndex(target.Date)
    mapped=[]
    for fold in reference_folds:
        dates=reference_frame.Date.iloc[fold]
        positions=calendar.get_indexer(dates)
        if (positions<0).any():raise ValueError('Missing frozen prediction date')
        np.testing.assert_array_equal(target.Date.iloc[positions].to_numpy(),dates.to_numpy())
        mapped.append(positions)
    return mapped


def prepare_panel(args):
    index,index_audit=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    reference=json.loads(args.reference_report.read_text())
    reference_audit=json.loads((args.reference_report.parent/'data_audit.json').read_text())
    if index_audit['sha256']!=reference_audit['inputs']['VNINDEX']['sha256']:raise ValueError('Reference index changed')
    target,names=panel_features(pd.DatetimeIndex(index.Date),index,'VNINDEX')
    groups,manifest=indices.load_indices(args.index_dir)
    auxiliary=[]
    for symbol,source in groups.items():
        frame,other_names=panel_features(pd.DatetimeIndex(index.Date),source.rename(columns={'Close':'Price'}),symbol)
        if names!=other_names:raise ValueError('Different feature schema across assets')
        auxiliary.append(frame)
    auxiliary=pd.concat(auxiliary,ignore_index=True)
    etf,etf_audit=exp.base.load_market_data(args.data_dir/'E1VFVN30.csv')
    if etf_audit['sha256']!=reference_audit['inputs']['E1VFVN30']['sha256']:raise ValueError('Reference ETF changed')
    reference_features,reference_names=exp.base.build_feature_matrix(index,etf,'close-etf')
    reference_frame=exp.base.create_labels(reference_features,20,reference_names)
    reference_folds=exp.freeze_reference(reference_frame,reference,20,'close-etf')
    folds=map_frozen_dates(target,reference_frame,reference_folds)
    blocks=[]
    for number,validation in enumerate(folds,1):
        for block_number,valid in enumerate(exp.refit_blocks(target,validation,pd.DatetimeIndex(index.Date),63),1):
            blocks.append(dict(fold=number,block=block_number,validation=valid))
    # Full preflight for every time boundary; report retained samples, not fictitious growth.
    training_audit=[]
    for window in ['3y','expanding']:
        for block in blocks:
            boundary=target.Date.iloc[block['validation'][0]]
            _,_,audit=training_panel(target,auxiliary,boundary,window,True)
            training_audit.append(dict(window=window,fold=block['fold'],block=block['block'],boundary=str(boundary.date()),**audit))
    plan=dict(mode='historical_three_class_index_transfer_development',target='VNINDEX simple T+20 return: < -5% class0; > +5% class2; otherwise class1',
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_hash=index_audit['sha256'],reference_etf_hash=etf_audit['sha256'],
              reference_sha256=hashlib.sha256(args.reference_report.read_bytes()).hexdigest(),index_inputs=manifest['canonical'],
              features=names,feature_choice='12 shared relative features; chosen on availability before fitting, long-window features leave little early auxiliary history',
              cohorts={s:dict(rows=len(f),start=str(f.Date.min().date()),end=str(f.Date.max().date())) for s,f in pd.concat([target,auxiliary]).groupby('symbol')},
              validation_folds=[dict(fold=n,n=len(v),date_sha256=exp.date_hash(target.Date.iloc[v]),start=str(target.Date.iloc[v[0]].date()),end=str(target.Date.iloc[v[-1]].date())) for n,v in enumerate(folds,1)],
              configs=[dict(window=w,capacity=c,pooled=p) for w,c,p in CONFIGS],parameters=PARAMETERS,common_parameters=COMMON,
              refit_market_sessions=63,decision='argmax; no new decision-rule search',
              weights='Before class costs, each target date has unit mass: target .5, available auxiliaries share .5; without auxiliary target weight1. Class factors computed on weighted date mass. Correlated assets are not independent samples.',
              preflight_training=training_audit,
              local_screen='Pooled vs matched target-only: mean fold macro F1 +.02, no worst-fold decline, mean MCC increase, >=3 improved folds.',
              objective_screen='Also compare BOTH original trend/risk controls; no independent acceptance on inspected history.',
              caveats=['No filling or current constituent list; broker historical revisions not independently point-in-time certified.',
                       'Additional asset rows are correlated; date weights do not create independent economic events.',
                       'Fixed -5/+5 labels have different frequencies across assets; transfer may be negative.',
                       'All results saved. No ONNX export, runtime changes or automatic winner deployment.'])
    return target,auxiliary,names,blocks,plan


def run_panel(target,auxiliary,names,blocks,window,capacity,pooled):
    records=[];audits=[]
    for block in blocks:
        valid=target.iloc[block['validation']]
        train,weights,audit=training_panel(target,auxiliary,valid.Date.min(),window,pooled)
        model=LGBMClassifier(**PARAMETERS[capacity],**COMMON)
        model.fit(train[names].to_numpy(dtype=np.float32),train.label.to_numpy(dtype=int),sample_weight=weights)
        probability=model.predict_proba(valid[names].to_numpy(dtype=np.float32))
        np.testing.assert_array_equal(model.classes_,[0,1,2])
        np.testing.assert_allclose(probability.sum(axis=1),1.)
        rows=valid[['Date','label_end_date','future_return','label']].copy()
        rows[metrics.PROB_COLUMNS]=probability
        rows['argmax']=probability.argmax(axis=1)
        # Same output schema for existing metric helper; no extra decision variant.
        rows['causal_macro_weights']=rows['argmax']
        counts=train.loc[train.symbol=='VNINDEX','label'].value_counts().reindex([0,1,2],fill_value=0).to_numpy()
        rows['majority']=counts.argmax()
        rows['outer_fold'],rows['refit_block']=block['fold'],block['block']
        records.append(rows)
        audits.append(dict(fold=block['fold'],block=block['block'],prediction_start=str(valid.Date.min().date()),**audit))
    return pd.concat(records,ignore_index=True),audits


def write_panel_report(results,output):
    table=[]
    for r in results:
        control=next(c for c in results if c['window']==r['window'] and c['capacity']==r['capacity'] and not c['pooled_training'])
        wins=sum(a['f1']>b['f1'] for a,b in zip(r['folds'],control['folds']))
        passed=r['pooled_training'] and r['mean_f1']>=control['mean_f1']+.02 and r['worst_f1']>=control['worst_f1'] and r['mean_mcc']>control['mean_mcc'] and wins>=3
        table.append(dict(candidate=r['learner'],mean_f1=r['mean_f1'],worst_f1=r['worst_f1'],mean_mcc=r['mean_mcc'],pooled_f1=r['pooled']['f1'],delta_vs_matched_control=r['mean_f1']-control['mean_f1'],better_folds=wins,local_development_screen=bool(passed)))
    (output/'report.json').write_text(json.dumps(dict(role='development_only',results=results),indent=2)+'\n')
    pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    return table


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--index-dir',type=Path,default=indices.INDEX_DIR)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    target,auxiliary,names,blocks,plan=prepare_panel(args)
    output=args.output_dir or ROOT/'reports/regime_panel'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    results=[]
    for window,capacity,pooled in CONFIGS:
        name=f'{window}_{capacity}_'+('pooled' if pooled else 'target_only')
        print('Running '+name,flush=True)
        rows,audits=run_panel(target,auxiliary,names,blocks,window,capacity,pooled)
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
        (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
        summary=metrics.summarize_multiclass(name,rows)[0]
        summary.update(window=window,capacity=capacity,pooled_training=pooled)
        results.append(summary)
        (output/'report.json').write_text(json.dumps(dict(role='development_only',results=results),indent=2)+'\n')
        print({key:summary[key] for key in ['mean_f1','worst_f1','mean_mcc']},flush=True)
    write_panel_report(results,output)
    print('Done; three-class DEVELOPMENT only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
