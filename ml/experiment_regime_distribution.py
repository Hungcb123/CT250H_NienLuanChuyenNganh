"""Map volatility-normalized regime probabilities to an absolute-loss CDF.

For mature core returns Z=log(P[t+20]/P[t]) / horizon_sigma[t], estimate
F_k(z|class k). At prediction t, sum p(class k|X_t)*F_k(log(.95)/sigma_t).
The within-class CDF is empirical and assumes stability beyond the regime
features. This approximation is tested FORWARD, not asserted calibrated.
"""
import json
from datetime import datetime,timezone

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

import experiment_regime_fresh as fresh
study=fresh.study


def mixture_risk(probabilities,classes,core_labels,core_z,horizon_sigma,undo_balancing=True):
    classes=list(classes)
    if set(classes)!={0,1,2}:raise ValueError('Need all three volatility regimes')
    q=np.asarray(probabilities,dtype=float)[:,[classes.index(i) for i in range(3)]]
    y=np.asarray(core_labels,dtype=int);z=np.asarray(core_z,dtype=float);sigma=np.asarray(horizon_sigma,dtype=float)
    if len(y)!=len(z) or not np.isfinite(z).all() or not np.isfinite(sigma).all() or (sigma<=0).any():raise ValueError('Invalid mature return distribution or known volatility')
    if q.shape!=(len(sigma),3) or not np.isfinite(q).all() or (q<0).any() or not np.allclose(q.sum(axis=1),1):raise ValueError('Invalid regime probabilities')
    counts=np.bincount(y,minlength=3)
    if (counts==0).any():raise ValueError('Missing core regime')
    if undo_balancing:
        # Balanced class weights distort the effective class prior. This is an
        # approximate prior correction, not a guarantee of calibrated probabilities.
        q=q*(counts/counts.sum())
        q=q/q.sum(axis=1,keepdims=True)
    threshold=np.log(.95)/sigma
    conditional=np.column_stack([np.searchsorted(np.sort(z[y==k]),threshold,side='left')/counts[k] for k in range(3)])
    # Strict < matches the existing simple-return < -5% target.
    return (q*conditional).sum(axis=1)


def prepare(args):
    old,index,plan=fresh.prepare(args)
    frame,template,names=old[0][1:]
    jobs=[]
    for outer in template['folds']:
        frozen=np.concatenate([b['validation'] for b in outer['blocks']])
        blocks={w:fresh.make_blocks(frame,frozen,pd.DatetimeIndex(index.Date),w,40,20) for w in ['3y','expanding']}
        jobs.append(dict(fold=outer['fold'],blocks=blocks))
    plan.update(mode='conditional_return_distribution_development',
                transform='Sum_k p(k|X)*empirical_core_CDF(Z|k)[log(.95)/known horizon sigma]',
                variants=['3y/expanding x raw/prior-corrected probabilities x historical-p90/fixed-.25 thresholds'],
                parameter_mode='fixed_shallow',feature_names=names,
                assumptions=['Within-regime standardized return shape estimated from mature core only; may be misspecified or unstable.',
                             'Optional class-prior correction reverses balanced-weight prior shift approximately, not calibration proof.',
                             'Current horizon sigma comes solely from trailing 20 completed daily log returns.',
                             'Calibration static p90 and predeclared probability cutoff .25 both reported.',
                             'All existing historical development dates have been inspected; no independent test or export.'])
    return frame,jobs,names,index,plan


def run(frame,jobs,names):
    records,audits=[],[]
    for outer in jobs:
        for window in ['3y','expanding']:
            for block_no,block in enumerate(outer['blocks'][window],1):
                core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
                if core.label_end_date.max()>=cal.Date.min() or cal.label_end_date.max()>=valid.Date.min():raise ValueError('Noncausal split')
                model=study.make_model('lightgbm');model.fit(core[names].to_numpy(),core.label.to_numpy())
                core_z=(core.future_log_return/core.horizon_sigma).to_numpy()
                qcal=model.predict_proba(cal[names].to_numpy());qvalid=model.predict_proba(valid[names].to_numpy())
                for corrected in [False,True]:
                    c=mixture_risk(qcal,model.classes_,core.label,core_z,cal.horizon_sigma,corrected)
                    s=mixture_risk(qvalid,model.classes_,core.label,core_z,valid.horizon_sigma,corrected)
                    for rule in ['historical_p90','fixed_p25']:
                        name=window+('_prior_corrected_' if corrected else '_raw_')+rule
                        threshold=study.risk.alarm_threshold(c) if rule=='historical_p90' else .25
                        r=valid[['Date','label_end_date','future_return','label']].copy()
                        r['risk_score'],r['threshold'],r['alarm']=s,threshold,s>threshold
                        r['common_bear']=r.future_return<-.05
                        r['policy'],r['outer_fold'],r['refit_block']=name,outer['fold'],block_no
                        records.append(r)
                        audits.append(dict(policy=name,outer_fold=outer['fold'],refit_block=block_no,core_end=str(core.Date.max()),
                                           core_label_end=str(core.label_end_date.max()),calibration_start=str(cal.Date.min()),calibration_end=str(cal.Date.max()),
                                           calibration_label_end=str(cal.label_end_date.max()),prediction_start=str(valid.Date.min()),
                                           prior_correction=corrected,threshold=threshold,**study.diag.score_stats(c,'calibration_score')))
    return pd.concat(records,ignore_index=True),audits


def main(argv=None):
    args=study.risk.labels.parse_args(argv)
    frame,jobs,names,index,plan=prepare(args)
    output=args.output_dir or study.risk.labels.ROOT/'reports/regime_distribution'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'distribution_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    print('Running volatility-to-absolute-loss mixture heads',flush=True)
    records,audits=run(frame,jobs,names)
    for policy,rows in records.groupby('policy'):rows.to_csv(output/(policy+'_predictions.csv'),index=False)
    pd.DataFrame(study.risk.summary_rows(records)).to_csv(output/'causal_metrics.csv',index=False)
    calibration=[]
    for (policy,fold),rows in records.groupby(['policy','outer_fold']):
        calibration.append(dict(policy=policy,fold=int(fold),brier=float(brier_score_loss(rows.common_bear,rows.risk_score)),
                                mean_estimated_risk=float(rows.risk_score.mean()),actual_prevalence=float(rows.common_bear.mean())))
    pd.DataFrame(calibration).to_csv(output/'probability_diagnostics.csv',index=False)
    (output/'distribution_refits.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done, historical development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
