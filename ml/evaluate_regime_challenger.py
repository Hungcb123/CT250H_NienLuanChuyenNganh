"""Paired development diagnostics against a specific archived baseline.

Bootstrap intervals are conditional on already-inspected historical development
and DO NOT account for model-selection multiplicity or replace a fresh test.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import experiment_regime_risk as risk


def compare(baseline_path,challenger_path,output):
    baseline_path,challenger_path,output=map(Path,[baseline_path,challenger_path,output])
    baseline=pd.read_csv(baseline_path,parse_dates=['Date','label_end_date'])
    challenger=pd.read_csv(challenger_path,parse_dates=['Date','label_end_date'])
    baseline=baseline.sort_values('Date').reset_index(drop=True)
    challenger=challenger.sort_values('Date').reset_index(drop=True)
    for col in ['Date','label_end_date','common_bear','outer_fold']:
        if not baseline[col].equals(challenger[col]):raise ValueError('Paired dates/target mismatch: '+col)
    np.testing.assert_allclose(baseline.future_return,challenger.future_return,atol=1e-12)
    output.mkdir(parents=True,exist_ok=False)
    reference=str(baseline.policy.iloc[0]);candidate=str(challenger.policy.iloc[0])
    # Existing bootstrap helper names its reference fixed_5pct. Alias ONLY the
    # transient frame, then restore the actual reference name in final artifacts.
    baseline['policy']='fixed_5pct'
    if candidate=='fixed_5pct':challenger['policy']='challenger'
    intervals=risk.bootstrap_deltas(pd.concat([baseline,challenger],ignore_index=True))
    for row in intervals:row.update(reference=reference,policy=candidate)
    pd.DataFrame(intervals).to_csv(output/'paired_block_sensitivity.csv',index=False)
    metrics=[]
    for name,frame in [(reference,baseline),(candidate,challenger)]:
        metrics.append(dict(policy=name,**risk.binary_metrics(frame.common_bear,frame.alarm)))
    pd.DataFrame(metrics).to_csv(output/'comparison.csv',index=False)
    record=dict(role='Paired historical DEVELOPMENT sensitivity, not independent test or multiple-testing-adjusted inference',
                baseline_path=str(baseline_path.resolve()),baseline_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                challenger_path=str(challenger_path.resolve()),challenger_sha256=hashlib.sha256(challenger_path.read_bytes()).hexdigest(),
                internal_reference_alias='fixed_5pct is only an implementation alias inside resampling, never a target/source substitution',
                results=metrics)
    (output/'comparison.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--challenger',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    record=compare(args.baseline,args.challenger,args.output_dir)
    print(json.dumps(record['results'],indent=2))


if __name__=='__main__':main()
