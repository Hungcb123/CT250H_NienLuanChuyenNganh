"""Dense forward-return quantile regression vs rare-event classification.

Fixed shallow LightGBM quantile .10, 3y/expanding, raw/vol-normalized log-return
training targets. Evaluation remains actual simple return < -5% at T+20.
"""
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd

import experiment_regime_fresh as fresh
study=fresh.study


def make_model():
    from lightgbm import LGBMRegressor
    params=dict(study.diag.FIXED_PARAMS)
    params.pop('class_weight')
    return LGBMRegressor(**params,objective='quantile',alpha=.1)


def prepare(args):
    old,index,plan=fresh.prepare(args)
    frame,template,names=old[0][1:]
    jobs=[]
    for outer in template['folds']:
        frozen=np.concatenate([b['validation'] for b in outer['blocks']])
        jobs.append(dict(fold=outer['fold'],blocks={w:fresh.make_blocks(frame,frozen,pd.DatetimeIndex(index.Date),w,40,20) for w in ['3y','expanding']}))
    plan.update(mode='dense_return_quantile_development',quantile=.1,
                targets=['future log return','future log return / known trailing horizon sigma'],
                windows=['3y','expanding'],thresholds=['historical p90','fixed log-loss cutoff -log(.95)'],
                parameter_mode='fixed_shallow_quantile_no_tuning',feature_names=names,
                caveat='Dense return supervision avoids rare-class objective but conditional quantiles can still be biased or unstable. No independent test/export.')
    return frame,jobs,names,index,plan


def run(frame,jobs,names):
    records,audits=[],[]
    for outer in jobs:
        for window in ['3y','expanding']:
            for block_no,block in enumerate(outer['blocks'][window],1):
                core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
                if core.label_end_date.max()>=cal.Date.min() or cal.label_end_date.max()>=valid.Date.min():raise ValueError('Noncausal split')
                for normalized in [False,True]:
                    model=make_model()
                    y=core.future_log_return/core.horizon_sigma if normalized else core.future_log_return
                    model.fit(core[names].to_numpy(),y.to_numpy())
                    c=-model.predict(cal[names].to_numpy());s=-model.predict(valid[names].to_numpy())
                    if normalized:c=c*cal.horizon_sigma.to_numpy();s=s*valid.horizon_sigma.to_numpy()
                    if not np.isfinite(c).all() or not np.isfinite(s).all():raise ValueError('Nonfinite predicted quantile')
                    for rule in ['historical_p90','fixed_loss5']:
                        name=window+('_normalized_' if normalized else '_raw_')+rule
                        threshold=study.risk.alarm_threshold(c) if rule=='historical_p90' else -np.log(.95)
                        r=valid[['Date','label_end_date','future_return','label']].copy()
                        r['risk_score'],r['threshold'],r['alarm']=s,threshold,s>threshold
                        r['common_bear']=r.future_return<-.05
                        r['policy'],r['outer_fold'],r['refit_block']=name,outer['fold'],block_no
                        r['predicted_log_return_q10']=-s
                        records.append(r)
                        audits.append(dict(policy=name,outer_fold=outer['fold'],refit_block=block_no,core_end=str(core.Date.max()),core_label_end=str(core.label_end_date.max()),
                                           calibration_start=str(cal.Date.min()),calibration_end=str(cal.Date.max()),calibration_label_end=str(cal.label_end_date.max()),
                                           prediction_start=str(valid.Date.min()),**study.diag.score_stats(c,'calibration_score')))
    return pd.concat(records,ignore_index=True),audits


def main(argv=None):
    args=study.risk.labels.parse_args(argv)
    frame,jobs,names,index,plan=prepare(args)
    output=args.output_dir or study.risk.labels.ROOT/'reports/regime_quantile'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'quantile_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    print('Running dense forward-return quantile heads',flush=True)
    records,audits=run(frame,jobs,names)
    for policy,rows in records.groupby('policy'):rows.to_csv(output/(policy+'_predictions.csv'),index=False)
    pd.DataFrame(study.risk.summary_rows(records)).to_csv(output/'causal_metrics.csv',index=False)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done, historical development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
