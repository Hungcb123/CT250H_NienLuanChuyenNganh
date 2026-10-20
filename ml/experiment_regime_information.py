"""Causal information ablation for original fixed-target THREE-CLASS forecasts.

Equal purged-inner tuning budget, exact old dates, 3y and 63-session refits.
All source books existed before this study; no new historical holdout claim.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_candidates as extra
import experiment_regime_ohlcv as ohlcv
import experiment_regime_global as global_risk
import experiment_regime_indices as indices

ROOT=Path(__file__).resolve().parent
GROUPS=['control','ohlcv','vix','indices','combined']


def merge_information(frame,book):
    if book.Date.duplicated().any():raise ValueError('Duplicate information date')
    collisions=(set(frame.columns)&set(book.columns))-{'Date'}
    if collisions:raise ValueError('Overlapping feature names: '+str(collisions))
    result=frame.merge(book,on='Date',how='left',validate='one_to_one',sort=False)
    for key in ['Date','label_end_date','label','future_return']:
        np.testing.assert_array_equal(frame[key],result[key])
    return result


def prepare_information(args):
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','--train-windows','3y',
        '--models','LightGBM','--horizons','20','--refit-sessions','63',
        '--trials',str(args.trials),'--timeout',str(args.timeout)])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    frame,template=frames[20],jobs[0]
    index,audit=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    if audit['sha256']!=plan['input_hashes']['VNINDEX']:raise ValueError('Index changed during preparation')
    consensus,consensus_audit=ohlcv.load_consensus(args.data_dir,index)
    bar_features=ohlcv.ohlcv_features(consensus)
    source,vix_audit=global_risk.load_vix()
    vix_features=global_risk.vix_features(source,index.Date)
    stretch=extra.reversal_features(index).Stretch20
    vix_features['VIX_StretchInteraction']=stretch*(vix_features.VIX_LogLevel-np.log(20.))
    groups,index_audit=indices.load_indices()
    group_features=indices.index_features(index,groups)
    book=bar_features.merge(vix_features[['Date','VIX_ObservationDate','VIX_AvailableDate']+global_risk.VIX_NAMES],on='Date',validate='one_to_one',sort=False)
    book=book.merge(group_features,on='Date',validate='one_to_one',sort=False)
    frame=merge_information(frame,book)
    known=frame.VIX_AvailableDate.notna()
    if not (frame.loc[known,'VIX_AvailableDate']<=frame.loc[known,'Date']).all():raise ValueError('Future VIX available date')
    if not (frame.loc[known,'VIX_ObservationDate']+pd.Timedelta(days=2)<=frame.loc[known,'Date']).all():raise ValueError('VIX lag violated')
    extras={'control':[],'ohlcv':ohlcv.OHLCV_NAMES,'vix':global_risk.VIX_NAMES,'indices':indices.NAMES,
            'combined':ohlcv.OHLCV_NAMES+global_risk.VIX_NAMES+indices.NAMES}
    variants=[]
    for group in GROUPS:
        job=copy.deepcopy(template);job['names']=template['names']+extras[group];job['group']=group
        values=frame[job['names']].to_numpy(dtype=float)
        if np.isinf(values).any():raise ValueError('Infinite feature value')
        variants.append((group,job))
    frozen=np.concatenate([b['validation'] for outer in template['folds'] for b in outer['blocks']])
    coverage={group:{name:float(frame[name].iloc[frozen].notna().mean()) for name in extras[group]} for group in GROUPS}
    plan.update(mode='three_class_information_development_ablation',groups=GROUPS,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                source_component_sha256={Path(m.__file__).name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in [exp,extra,ohlcv,global_risk,indices]},
                feature_groups={group:job['names'] for group,job in variants},validation_coverage=coverage,
                consensus_sources=consensus_audit,consensus_coverage={name:float(consensus[name].notna().mean()) for name in ['Open','High','Low','Volume']},
                vix_source=vix_audit,index_sources=index_audit['canonical'],
                missing_policy='Keep all old validation dates. Broker conflicts/unavailable groups remain NaN; native LightGBM missing handling. No global imputation or filling.',
                timing='All local features after same-day close. VIX observation date +2 calendar days, backward join max7 days stale. Inner training labels strictly mature before inner validation; outer-refit labels mature before block.',
                acceptance='Development only: mean F1 control +.02, worst-fold >= control, MCC gain, >=3/4 improved folds; also compare both original trend/risk controls. No independent test acceptance.',
                tuning_budget='Exactly requested trials per outer fold per group, fixed seed42; timeout must not silently reduce budget.',
                caveat='All historical periods inspected. Broker data vintage/release timestamps not independently certified. Missing source patterns may encode historical era.')
    return frame,variants,plan,consensus


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if args.trials<1 or args.timeout<1:parser.error('Positive budget required')
    frame,variants,plan,consensus=prepare_information(args)
    output=args.output_dir or ROOT/'reports/regime_information'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    frame[['Date','VIX_ObservationDate','VIX_AvailableDate']+global_risk.VIX_NAMES].to_csv(output/'vix_timing.csv',index=False)
    consensus.to_csv(output/'consensus_fields.csv',index=False)
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    results=[]
    for group,job in variants:
        print('Running '+group,flush=True)
        result,rows=exp.run_candidate(frame,job,plan['optuna'])
        if any(t['n_trials']!=args.trials for t in result['inner_tuning']):raise ValueError('Unequal trial budget; results not comparable')
        rows.to_csv(output/(group+'_predictions.csv'),index=False)
        results.append(result)
        (output/'report.json').write_text(json.dumps(dict(role='development_only',results=results),indent=2)+'\n')
        table=[];control=results[0]
        for r in results:
            wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(r['folds'],control['folds']))
            passed=r['mean_f1']>=control['mean_f1']+.02 and r['worst_f1']>=control['worst_f1'] and r['mean_mcc']>control['mean_mcc'] and wins>=3
            table.append(dict(group=r['feature_group'],mean_f1=r['mean_f1'],worst_f1=r['worst_f1'],mean_mcc=r['mean_mcc'],pooled_f1=r['pooled']['f1_macro'],fold_wins=wins,development_screen=bool(passed)))
        pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
        print({key:result[key] for key in ['mean_f1','worst_f1','mean_mcc']},flush=True)
    print('Done. Three-class DEVELOPMENT only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
