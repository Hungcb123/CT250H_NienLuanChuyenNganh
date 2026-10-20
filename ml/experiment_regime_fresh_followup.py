"""Predeclared follow-up to training freshness: 3y/5y, calibration 20/40.

Same frozen prediction dates, fixed shallow trees, no independent test claim.
"""
import copy
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import experiment_regime_fresh as fresh

CONFIGS=[('3y_cal40_refit20','3y',40,20),('3y_cal40_refit5','3y',40,5),
         ('5y_cal20_refit20','5y',20,20),('5y_cal40_refit20','5y',40,20)]


def prepare(args):
    old,index,plan=fresh.prepare(args)
    frame,template,names=old[0][1:]
    candidates=[]
    for name,window,ncal,refit in CONFIGS:
        job=copy.deepcopy(template)
        for outer in job['folds']:
            dates=np.concatenate([b['validation'] for b in outer['blocks']])
            outer['blocks']=fresh.make_blocks(frame,dates,pd.DatetimeIndex(index.Date),window,ncal,refit)
        candidates.append((name,frame,job,names))
    plan.update(mode='freshness_followup_development',candidates=[dict(name=n,window=w,calibration_rows=c,refit_sessions=r) for n,w,c,r in CONFIGS],
                rationale='Prior 3y short-calibration model had all fold AUROC >.5 but excessive alarm rate; test calibration length and intermediate train window without hyperparameter search.')
    return candidates,index,plan


def main(argv=None):
    args=fresh.study.risk.labels.parse_args(argv)
    candidates,index,plan=prepare(args)
    output=args.output_dir or fresh.study.risk.labels.ROOT/'reports/regime_fresh_followup'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'followup_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    records,audits=[],[]
    for candidate in candidates:
        print('Running '+candidate[0],flush=True)
        predictions,refits=fresh.run_candidate(*candidate)
        predictions.to_csv(output/(candidate[0]+'_predictions.csv'),index=False)
        records.append(predictions);audits.extend(refits)
        pd.DataFrame(fresh.study.risk.summary_rows(pd.concat(records,ignore_index=True))).to_csv(output/'causal_metrics.csv',index=False)
    records=pd.concat(records,ignore_index=True)
    pd.DataFrame(fresh.study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    fresh.study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done, development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
