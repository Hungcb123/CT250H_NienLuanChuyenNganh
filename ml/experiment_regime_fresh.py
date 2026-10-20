"""Core-training freshness ablation: shorter calibration and faster refits.

Only fixed shallow LightGBM, volatility target, close-only features. Exact
previous prediction dates; all core/calibration labels strictly matured.
"""
import copy
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import experiment_regime_history as history
study=history.study
CONFIGS=[('expanding_cal20_refit20','expanding',20,20),
         ('expanding_cal40_refit20','expanding',40,20),
         ('expanding_cal20_refit5','expanding',20,5),
         ('3y_cal20_refit20','3y',20,20)]


def make_blocks(frame, frozen, calendar, window, calibration_rows, refit_sessions):
    result=[]
    for valid in study.risk.exp.refit_blocks(frame,frozen,calendar,refit_sessions):
        start=frame.Date.iloc[valid[0]]
        known=(frame.Date<start)&(frame.label_end_date<start)
        if window!='expanding':known &= frame.Date>=start-pd.DateOffset(years=int(window[:-1]))
        train=np.flatnonzero(known)
        calibration=train[-calibration_rows:]
        core=train[:-calibration_rows]
        core=core[(frame.label_end_date.iloc[core]<frame.Date.iloc[calibration[0]]).to_numpy()]
        if len(core)<150 or len(calibration)!=calibration_rows or frame.label.iloc[core].nunique()!=3:
            raise ValueError('Insufficient calibration/core rows or regimes')
        if frame.label_end_date.iloc[core].max()>=frame.Date.iloc[calibration[0]] or frame.label_end_date.iloc[calibration].max()>=start:
            raise ValueError('Noncausal split')
        result.append(dict(core=core,calibration=calibration,validation=valid))
    return result


def prepare(args):
    old,index,plan=history.prepare_history(args)
    source=next(c for c in old if c[0]=='lightgbm_vol_close_expanding')
    frame,template,names=source[3:]
    candidates=[]
    for name,window,n_cal,refit in CONFIGS:
        job=copy.deepcopy(template)
        for outer in job['folds']:
            frozen=np.concatenate([b['validation'] for b in outer['blocks']])
            outer['blocks']=make_blocks(frame,frozen,pd.DatetimeIndex(index.Date),window,n_cal,refit)
        candidates.append((name,frame,job,names))
    plan.update(mode='training_freshness_development_ablation',
                candidates=[dict(name=n,window=w,calibration_rows=c,refit_sessions=r) for n,w,c,r in CONFIGS],
                parameter_mode='fixed_shallow',parameters=study.diag.FIXED_PARAMS,
                assumptions=['Same close-only full-history features and exact frozen dates.',
                             'Last 20/40 mature training rows reserved for calibration; core labels purged at calibration start.',
                             'Static calibration p90 from same model; no rolling policy requiring 120 out-of-fit history rows.',
                             'Short calibration has high quantile uncertainty. All variants reported, none auto-selected.',
                             'These are already-inspected development dates; no independent test/deployment claim.'])
    return candidates,index,plan


def run_candidate(name,frame,job,names):
    records,audits=[],[]
    for outer in job['folds']:
        for block_no,block in enumerate(outer['blocks'],1):
            core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
            model=study.make_model('lightgbm')
            model.fit(core[names].to_numpy(),core.label.to_numpy())
            cal_score=study.score_model(model,cal[names].to_numpy(),'lightgbm','vol_1sigma')
            score=study.score_model(model,valid[names].to_numpy(),'lightgbm','vol_1sigma')
            threshold=study.risk.alarm_threshold(cal_score)
            r=valid[['Date','label_end_date','future_return','label']].copy()
            r['risk_score'],r['threshold'],r['alarm']=score,threshold,score>threshold
            r['common_bear']=r.future_return<-.05
            r['policy'],r['outer_fold'],r['refit_block']=name,outer['fold'],block_no
            records.append(r)
            audits.append(dict(policy=name,outer_fold=outer['fold'],refit_block=block_no,n_core=len(core),n_calibration=len(cal),
                               core_end=str(core.Date.max()),core_label_end=str(core.label_end_date.max()),
                               calibration_start=str(cal.Date.min()),calibration_end=str(cal.Date.max()),
                               calibration_label_end=str(cal.label_end_date.max()),prediction_start=str(valid.Date.min()),
                               core_age_calendar_days=int((valid.Date.min()-core.Date.max()).days),
                               **study.diag.score_stats(cal_score,'calibration_score')))
    return pd.concat(records,ignore_index=True),audits


def main(argv=None):
    args=study.risk.labels.parse_args(argv)
    candidates,index,plan=prepare(args)
    output=args.output_dir or study.risk.labels.ROOT/'reports/regime_fresh'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'freshness_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    records,audits=[],[]
    for candidate in candidates:
        print('Running '+candidate[0],flush=True)
        predictions,refits=run_candidate(*candidate)
        predictions.to_csv(output/(candidate[0]+'_predictions.csv'),index=False)
        records.append(predictions);audits.extend(refits)
        pd.DataFrame(study.risk.summary_rows(pd.concat(records,ignore_index=True))).to_csv(output/'causal_metrics.csv',index=False)
    records=pd.concat(records,ignore_index=True)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done, development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
