"""Reproduce the candidate, future-label invariance, stress and paired intervals.

This audits already inspected DEVELOPMENT; it cannot create an untouched test.
"""
import argparse
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

import experiment_regime_expert_selection as study


def fold_f1(actual,prediction,groups):
    values=[]
    for ids in groups:
        matrix=np.bincount(3*actual[ids]+prediction[ids],minlength=9).reshape(3,3)
        denominator=matrix.sum(axis=0)+matrix.sum(axis=1)
        values.append(np.divide(2*np.diag(matrix),denominator,out=np.zeros(3),where=denominator>0).mean())
    return float(np.mean(values))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-dir',type=Path,default=study.ROOT/'reports/regime_expert_selection/20261018T160007_360834Z')
    parser.add_argument('--classifier-dir',type=Path,default=study.ROOT/'reports/regime_multiclass_reuse/20261018T151747_040696Z')
    parser.add_argument('--density-dir',type=Path,default=study.ROOT/'reports/regime_return_distribution/20261018T155423_383833Z')
    parser.add_argument('--data-dir',type=Path,default=study.ROOT/'data/research/brokers_2010_20261001_reviewed')
    args=parser.parse_args(argv)
    folder=args.study_dir
    plan=json.loads((folder/'robustness_plan.json').read_text())
    base,matrices,hashes=study.load_expert_sources(args)
    original_plan=json.loads((folder/'plan.json').read_text())
    if hashes!=original_plan['input_hashes']:raise ValueError('Forecast sources changed')
    index,audit=study.exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    if audit['sha256']!=original_plan['calendar_hash']:raise ValueError('Calendar changed')
    baseline,choices=study.delayed_expert_predictions(base,matrices,index.Date,rule=plan['baseline_rule'])
    reference=pd.read_csv(folder/'delayed_selector_predictions.csv',parse_dates=['Date'])
    np.testing.assert_array_equal(base.Date,reference.Date)
    np.testing.assert_array_equal(baseline,reference.prediction)
    known_count=0
    for choice in choices:
        if choice['latest_label_end']:
            if pd.Timestamp(choice['latest_label_end'])>=pd.Timestamp(choice['Date']):raise ValueError('Selector used unmatured outcome')
            known_count+=1
    cuts=[int(np.flatnonzero(base.outer_fold.to_numpy()==fold)[-1])+1 for fold in sorted(base.outer_fold.unique())]
    cuts.append(len(base)-100)
    checks=[]
    for end in sorted(set(cuts)):
        prefix=base.iloc[:end].copy();cutoff=prefix.Date.max()
        # Unmatured outcomes are deliberately corrupted; a causal selector must
        # produce identical predictions throughout the prefix anyway.
        unknown=prefix.label_end_date>=cutoff
        prefix.loc[unknown,'label']=99
        forecast,_=study.delayed_expert_predictions(prefix,{name:value[:end] for name,value in matrices.items()},index.Date.loc[index.Date<=cutoff],rule=plan['baseline_rule'])
        np.testing.assert_array_equal(forecast,baseline[:end])
        checks.append(dict(end=str(cutoff.date()),n=end,unmatured_labels_removed=int(unknown.sum()),matches=end))
    sensitivity=[]
    for variant in [dict(name='baseline',rule=plan['baseline_rule'])]+plan['variants']:
        forecast,_=study.delayed_expert_predictions(base,matrices,index.Date,rule=variant['rule'])
        result,_=study.expert_metrics(variant['name'],base,forecast)
        sensitivity.append(dict(name=variant['name'],mean_f1=result['mean_f1'],worst_f1=result['worst_f1'],mean_mcc=result['mean_mcc'],rule=variant['rule']))
    pd.DataFrame([{k:v for k,v in row.items() if k!='rule'} for row in sensitivity]).to_csv(folder/'parameter_sensitivity.csv',index=False)
    y=base.label.to_numpy(dtype=int);groups=[np.flatnonzero(base.outer_fold.to_numpy()==fold) for fold in sorted(base.outer_fold.unique())]
    bootstrap=plan['bootstrap'];intervals=[]
    for name,expert in [('original_trend','legacy_trend'),('original_risk','legacy_risk'),('original_equal','legacy_equal')]:
        control=matrices[expert].argmax(axis=1)
        point=fold_f1(y,baseline,groups)-fold_f1(y,control,groups)
        for length in bootstrap['block_sessions']:
            rng=np.random.default_rng(bootstrap['seed']);deltas=[]
            for _ in range(bootstrap['repeats']):
                sample=[]
                for ids in groups:
                    starts=rng.integers(0,len(ids),size=int(np.ceil(len(ids)/length)))
                    sample.append(ids[((starts[:,None]+np.arange(length))%len(ids)).ravel()[:len(ids)]])
                deltas.append(fold_f1(y,baseline,sample)-fold_f1(y,control,sample))
            low,high=np.quantile(deltas,[.025,.975])
            intervals.append(dict(reference=name,block_sessions=length,point_delta=point,delta_low=float(low),delta_high=float(high),repeats=bootstrap['repeats']))
    (folder/'paired_intervals.json').write_text(json.dumps(dict(role='Development paired sensitivity, not independent/multiple-testing-adjusted inference',results=intervals),indent=2)+'\n')
    result=dict(role='Post-hoc DEVELOPMENT audit, not goal completion',default_source_interface_parity_matches=len(baseline),
                selection_boundaries=len(choices),boundaries_with_prior_labels=known_count,prefix_future_label_checks=checks,
                sensitivity=sensitivity,paired_intervals=intervals,auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (folder/'robustness_report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(pd.DataFrame(sensitivity)[['name','mean_f1','worst_f1','mean_mcc']].to_string(index=False))
    print(json.dumps(intervals,indent=2))
    print('Audited default/prefix invariance. '+str(folder.resolve()))
    return result


if __name__=='__main__':main()
