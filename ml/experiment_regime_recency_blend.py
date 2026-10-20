"""Fixed 2:1 recency blend of archived standardized 3y and expanding experts.

A single predeclared blend, not a grid optimized on outer labels. Prior studies
showed the short-history expert was more consistent across folds, while the
expanding expert retained stronger detection in several periods. Historical
DEVELOPMENT only; no claim that choosing this rule after those studies is unbiased.
"""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_online as online
risk=online.risk

WEIGHTS=[2/3,1/3]


def blend(short,long):
    short=short.sort_values('Date').reset_index(drop=True)
    long=long.sort_values('Date').reset_index(drop=True)
    for column in ['Date','label_end_date','outer_fold','refit_block','common_bear']:
        if not short[column].equals(long[column]):raise ValueError('Experts are not aligned: '+column)
    np.testing.assert_allclose(short.future_return,long.future_return,atol=1e-12)
    result=short.copy()
    result['risk_score']=WEIGHTS[0]*short.risk_score+WEIGHTS[1]*long.risk_score
    # Causal warmup threshold only; this weighted sum is NOT the quantile of the
    # blended calibration distribution. After 120 predictions use actual history.
    result['threshold']=WEIGHTS[0]*short.threshold+WEIGHTS[1]*long.threshold
    result['alarm']=result.risk_score>result.threshold
    result['policy']='recency_2to1'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ensemble-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source_plan=json.loads((args.ensemble_dir/'ensemble_plan.json').read_text())
    if source_plan.get('mode')!='two_history_causal_ensemble_development':raise ValueError('Need standardized expert archive')
    experts=[];hashes={}
    for policy in ['3y_standardized','expanding_standardized']:
        path=args.ensemble_dir/(policy+'_predictions.csv')
        experts.append(pd.read_csv(path,parse_dates=['Date','label_end_date']))
        hashes[policy]=hashlib.sha256(path.read_bytes()).hexdigest()
    records=online.online_records(blend(*experts),120)
    output=args.output_dir or risk.labels.ROOT/'reports/regime_recency_blend'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    records.to_csv(output/'recency_2to1_online120_predictions.csv',index=False)
    pd.DataFrame(risk.summary_rows(records)).to_csv(output/'causal_metrics.csv',index=False)
    plan=dict(mode='fixed_recency_blend_development',source=str(args.ensemble_dir.resolve()),source_hashes=hashes,input_hashes=source_plan['input_hashes'],
              weights=WEIGHTS,online_window=120,quantile=.9,
              warmup='First 120 predictions use weighted expert calibration thresholds; not exact mixture p90. No rows dropped.',
              selection_caveat='Predeclared rule motivated by already-inspected prior experiments; scores remain DEVELOPMENT evidence, not independent test.')
    (output/'blend_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print('Archived causal replay, no fitting. '+str(output.resolve()));return output


if __name__=='__main__':main()
