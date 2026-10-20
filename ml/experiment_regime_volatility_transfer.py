"""More historical dates and correlated-asset transfer for normalized returns.

T+20 labels/endpoints stay on the FULL VNINDEX calendar. No fill or constituents.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_indices as indices
import experiment_regime_return_distribution as density
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
MODES=['matched_target','extended_target','extended_pooled']


def build_volatility_panel(calendar,observations,symbol):
    if observations.Date.duplicated().any() or len(pd.DatetimeIndex(observations.Date).difference(pd.DatetimeIndex(calendar))):
        raise ValueError('Invalid asset/calendar dates')
    source=pd.DataFrame({'Date':calendar}).merge(observations[['Date','Price']],on='Date',how='left',validate='one_to_one',sort=False)
    features,names=exp.base.build_feature_matrix(source,feature_set='close')
    fixed=exp.base.create_labels(features,20,names)
    book=labels.build_label_book(source)
    known=fixed[['Date']].merge(book[['Date','horizon_sigma']],on='Date',validate='one_to_one')
    fixed=fixed.loc[(np.isfinite(known.horizon_sigma)&(known.horizon_sigma>0)).to_numpy()].reset_index(drop=True)
    frame=labels.relabel_cohort(fixed,book,'vol_1sigma')
    frame=frame.merge(book[['Date','horizon_sigma','future_log_return']],on='Date',validate='one_to_one',sort=False)
    frame['symbol']=symbol
    frame['target_z']=frame.future_log_return/frame.horizon_sigma
    if not np.isfinite(frame[names+['horizon_sigma','target_z']]).all().all():raise ValueError('Nonfinite panel target/features')
    return frame,names


def volatility_training_panel(target,auxiliary,boundary,matched_dates,mode):
    if mode not in MODES:raise ValueError('Unknown transfer mode')
    boundary=pd.Timestamp(boundary)
    core=target.loc[(target.Date<boundary)&(target.label_end_date<boundary)].copy()
    if mode=='matched_target':core=core.loc[core.Date.isin(matched_dates)].copy()
    if len(core)<150 or core.label.nunique()!=3:raise ValueError('Insufficient mature target history')
    rows=[core]
    if mode=='extended_pooled':
        other=auxiliary.loc[(auxiliary.Date<boundary)&(auxiliary.label_end_date<boundary)&auxiliary.Date.isin(core.Date)].copy()
        rows.append(other)
    train=pd.concat(rows,ignore_index=True).sort_values(['Date','symbol']).reset_index(drop=True)
    if train.duplicated(['Date','symbol']).any():raise ValueError('Duplicate asset date')
    target_mask=train.symbol.eq('VNINDEX').to_numpy()
    count=train.Date.map(train.loc[~target_mask].groupby('Date').size()).fillna(0).to_numpy()
    weights=np.where(target_mask,np.where(count>0,.5,1.),np.divide(.5,count,out=np.zeros(len(count)),where=count>0))
    np.testing.assert_allclose(pd.Series(weights).groupby(train.Date).sum(),1.,atol=1e-12)
    if train.label_end_date.max()>=boundary:raise ValueError('Unmatured pooled supervision')
    prior=np.bincount(core.label.to_numpy(dtype=int),minlength=3)/len(core)
    audit=dict(n_target=len(core),n_auxiliary=int((~target_mask).sum()),unique_dates=int(train.Date.nunique()),
        by_symbol={str(k):int(v) for k,v in train.symbol.value_counts().items()},
        target_start=str(core.Date.min().date()),latest_label_end=str(train.label_end_date.max().date()),
        target_class_prior=prior.tolist(),total_date_mass=float(weights.sum()))
    return train,weights,prior,audit


def run_volatility_transfer(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--index-dir',type=Path,default=indices.INDEX_DIR)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    original,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    calendar=pd.DatetimeIndex(index.Date)
    target,names=build_volatility_panel(calendar,index,'VNINDEX')
    groups,manifest=indices.load_indices(args.index_dir)
    etf,_=exp.base.load_market_data(args.data_dir/'E1VFVN30.csv')
    outside=pd.DatetimeIndex(etf.Date).difference(calendar)
    excluded_dates=pd.DatetimeIndex(['2018-01-23','2018-01-24'])
    if len(outside.difference(excluded_dates)):
        raise ValueError('Unexpected ETF session outside accepted calendar')
    etf=etf.loc[~etf.Date.isin(outside)].copy()
    auxiliary=[]
    for symbol,source in [('E1VFVN30',etf)]+[(s,f.rename(columns={'Close':'Price'})) for s,f in groups.items()]:
        rows,other_names=build_volatility_panel(calendar,source,symbol)
        if names!=other_names:raise ValueError('Panel schemas differ')
        auxiliary.append(rows)
    auxiliary=pd.concat(auxiliary,ignore_index=True)
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    positions=pd.DatetimeIndex(target.Date).get_indexer(base.Date)
    if (positions<0).any():raise ValueError('Missing target validation dates')
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(target.iloc[positions][key],base[key])
    mapping=pd.Series(np.arange(len(target)),index=target.Date)
    blocks=[]
    for outer in jobs['expanding']['folds']:
        for number,block in enumerate(outer['blocks'],1):
            valid=original.iloc[block['validation']]
            blocks.append(dict(fold=outer['fold'],block=number,validation=mapping.loc[valid.Date].to_numpy(dtype=int)))
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',args.index_dir/'manifest.json']
    paths += [args.index_dir/(s+'.csv') for s in groups]
    paths += [old/n for n in ['trend_predictions.csv','risk_predictions.csv','expanding_raw_mapped_predictions.csv','expanding_normalized_mapped_predictions.csv']]
    training=[]
    for mode in MODES:
        _,_,_,audit=volatility_training_panel(target,auxiliary,base.Date.iloc[0],original.Date,mode)
        training.append(dict(mode=mode,**audit))
    plan.update(mode='volatility_normalized_history_and_asset_transfer_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},features=names,
        configs=MODES,supervision='Future log return / sigma20*sqrt20, nine quantile regressors; same predeclared LightGBM parameters',
        first_boundary_training=training,asset_counts={str(s):len(f) for s,f in pd.concat([target,auxiliary]).groupby('symbol')},
        etf_excluded_non_sessions=[str(d.date()) for d in outside],
        primary='extended_pooled_blend: .5 old classifier + .25 old density + .25 pooled normalized density',
        secondary='extended_target_blend: same mix with target-only extended history; matched_target is same-feature control on old date exposure',
        weighting='Each eligible target date has unit total mass; if auxiliaries exist, target .5 and auxiliaries share .5. No class weights on quantile loss. Decision prior uses only target rows.',
        label_rule=parent['label_rule'],acceptance='Mean macro F1 +.01, no loss worst fold or mean bear/bull F1, MCC gain, >=3 fold wins; paired20/60 lower bounds >0 for provisional robust evidence.',
        caveats='Correlated assets do not create independent events. Two-broker historical consensus is not original release-vintage proof. No filled prelaunch prices. Inspected historical development only; no deployment.')
    output=args.output_dir or ROOT/'reports/regime_volatility_transfer'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    print(json.dumps(training),flush=True)
    if args.audit_only:return output
    classifiers=[];old_densities=[]
    for g in ['trend','risk']:
        rows=pd.read_csv(old/(g+'_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        classifiers.append(rows[experts.PROBS].to_numpy())
    for t in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+t+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_densities.append(score)
    classifier=np.mean(classifiers,axis=0);old_density=np.mean(old_densities,axis=0)
    matrices={'incumbent':.5*classifier+.5*old_density}
    for mode in MODES:
        records=[];audits=[]
        for block in blocks:
            valid=target.iloc[block['validation']]
            train,weights,prior,audit=volatility_training_panel(target,auxiliary,valid.Date.min(),original.Date,mode)
            points=[]
            for alpha in plan['specification']['quantile_levels']:
                model=LGBMRegressor(**plan['specification']['parameters'],alpha=alpha)
                model.fit(train[names].to_numpy(dtype=np.float32),train.target_z.to_numpy(),sample_weight=weights)
                points.append(model.predict(valid[names].to_numpy(dtype=np.float32)))
            points=np.sort(np.column_stack(points),axis=1)
            mass=dynamic_quantile_mass(points,plan['specification']['quantile_atom_weights'],-np.ones(len(valid)),np.ones(len(valid)))
            score=mass/prior;score/=score.sum(axis=1,keepdims=True)
            rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
            rows['outer_fold'],rows['refit_block']=block['fold'],block['block'];records.append(rows)
            audits.append(dict(fold=block['fold'],block=block['block'],boundary=str(valid.Date.min().date()),**audit))
            if block['block']==len(jobs['expanding']['folds'][block['fold']-1]['blocks']):
                pd.concat(records,ignore_index=True).to_csv(output/(mode+'_scores.csv'),index=False)
                (output/(mode+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
                print(mode+' fold '+str(block['fold'])+' complete',flush=True)
        rows=pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        score=rows[experts.PROBS].to_numpy()
        matrices[mode]=score
        matrices[mode+'_blend']=.5*classifier+.25*old_density+.25*score
    finish_research_study(base,matrices,output,['extended_pooled_blend','extended_target_blend'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_volatility_transfer()
