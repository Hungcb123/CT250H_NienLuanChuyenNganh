"""Causal online thresholds on archived, refit-standardized out-of-fit scores.

Every archived score was generated before its own return outcome. Rolling
threshold uses only earlier decision dates, including earlier refitted models
AFTER their core-calibration score standardization. This cross-model stability
assumption is tested, not guaranteed. No current/future quantile information.
"""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import experiment_regime_risk as risk

POLICIES=['3y_standardized','expanding_standardized','equal_ensemble','calibration_ap_ensemble']
WINDOWS=[60,120]


def online_records(records,window):
    result=records.sort_values('Date').reset_index(drop=True).copy()
    if result.Date.duplicated().any():raise ValueError('Duplicate prediction dates')
    # Keep the existing causal calibration threshold until enough archived
    # predictions exist. No shrinking prediction cohort or fabricated history.
    threshold=result.risk_score.shift(1).rolling(window,min_periods=window).quantile(.9,interpolation='higher')
    warmup=threshold.isna()
    result['threshold']=threshold.where(~warmup,result.threshold)
    result['alarm']=result.risk_score>result.threshold
    result['online_warmup']=warmup
    result['policy']=result.policy+f'_online{window}'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ensemble-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source_plan=json.loads((args.ensemble_dir/'ensemble_plan.json').read_text())
    if source_plan.get('mode')!='two_history_causal_ensemble_development':raise ValueError('Need archived standardized expert scores, not raw scores')
    output=args.output_dir or risk.labels.ROOT/'reports/regime_online'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    records=[];hashes={}
    for policy in POLICIES:
        path=args.ensemble_dir/(policy+'_predictions.csv')
        raw=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        if not (raw.policy==policy).all():raise ValueError('Mismatched source policy')
        hashes[policy]=hashlib.sha256(path.read_bytes()).hexdigest()
        for window in WINDOWS:
            result=online_records(raw,window)
            result.to_csv(output/(policy+f'_online{window}_predictions.csv'),index=False)
            records.append(result)
    records=pd.concat(records,ignore_index=True)
    plan=dict(mode='archived_online_threshold_development',source=str(args.ensemble_dir.resolve()),source_hashes=hashes,
              input_hashes=source_plan['input_hashes'],windows=WINDOWS,quantile=.9,
              warmup='First W predictions retain original causal calibration threshold; no sample drop.',
              assumptions=['All rolling thresholds shift scores by one decision observation before quantile.',
                           'Score standardization was core-calibration only at the time of each refit; cross-refit scores may still drift.',
                           'Archives immutable; no rescoring past data with a future model.',
                           'No outcome labels used to set this threshold; historical development, not a fresh test.'])
    (output/'online_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    pd.DataFrame(risk.summary_rows(records)).to_csv(output/'causal_metrics.csv',index=False)
    print('Online replay only; no fitting. '+str(output.resolve()));return output


if __name__=='__main__':main()
