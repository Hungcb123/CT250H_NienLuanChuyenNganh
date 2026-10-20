"""Causal two-history ensemble, fixed shallow trees and recent calibration only.

3y and expanding experts; same target/features, exact frozen dates. Ensemble
weights use ONLY matured calibration outcomes, never an outer-fold winner.
"""
import json
from datetime import datetime,timezone

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from scipy.special import logit,softmax

import experiment_regime_fresh as fresh
study=fresh.study
POLICIES=['3y_standardized','expanding_standardized','equal_ensemble','calibration_ap_ensemble']


def standardize_scores(calibration,scores):
    calibration=np.asarray(calibration,dtype=float)
    scores=np.asarray(scores,dtype=float)
    if not np.isfinite(calibration).all() or not np.isfinite(scores).all():raise ValueError('Nonfinite expert score')
    if ((calibration<0)|(calibration>1)).any() or ((scores<0)|(scores>1)).any():raise ValueError('Expected classifier probabilities before standardization')
    cal=logit(np.clip(calibration,1e-6,1-1e-6))
    prediction=logit(np.clip(scores,1e-6,1-1e-6))
    center=float(cal.mean());scale=max(float(cal.std()),.25)
    return (cal-center)/scale,(prediction-center)/scale,dict(logit_center=center,logit_scale=scale)


def calibration_weights(y,scores):
    y=np.asarray(y,dtype=int)
    support=int(y.sum())
    if support<2 or len(y)-support<2:return np.full(len(scores),1/len(scores)),[None]*len(scores)
    ap=np.array([average_precision_score(y,s) for s in scores])
    # Predeclared shrinkage discourages hard selection from a few overlapping labels.
    shrink=support/(support+10.)
    weights=softmax(4.*shrink*(ap-y.mean()))
    return weights,ap.tolist()


def prepare(args):
    old,index,plan=fresh.prepare(args)
    frame,template,names=old[0][1:]
    jobs=[]
    for outer in template['folds']:
        frozen=np.concatenate([b['validation'] for b in outer['blocks']])
        blocks={window:fresh.make_blocks(frame,frozen,pd.DatetimeIndex(index.Date),window,40,20) for window in ['3y','expanding']}
        for a,b in zip(blocks['3y'],blocks['expanding']):
            np.testing.assert_array_equal(a['validation'],b['validation']);np.testing.assert_array_equal(a['calibration'],b['calibration'])
        jobs.append(dict(fold=outer['fold'],blocks=blocks))
    plan.update(mode='two_history_causal_ensemble_development',policies=POLICIES,
                experts=['fixed shallow LightGBM 3y','fixed shallow LightGBM expanding'],
                feature_names=names,calibration_rows=40,refit_sessions=20,
                normalization='Logit classifier scores, centered/scaled using calibration mean/std only; std floor .25.',
                weights='softmax(4 * (support/(support+10)) * (calibration AP - calibration prevalence)); equal if either class has <2 calibration samples.',
                caveat='Calibration outcomes already mature; meta-weights fit on calibration, not independent validation evidence. No hard future-fold switching, no auto-winner or export.')
    return frame,jobs,names,index,plan


def run(frame,jobs,names):
    records,audits=[],[]
    for outer in jobs:
        for block_no,(a,b) in enumerate(zip(outer['blocks']['3y'],outer['blocks']['expanding']),1):
            valid=frame.iloc[a['validation']];cal=frame.iloc[a['calibration']]
            if cal.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured calibration outcome')
            raw_cal,cal_scores,pred_scores,experts=[],[],[],[]
            for window,block in [('3y',a),('expanding',b)]:
                core=frame.iloc[block['core']]
                if core.label_end_date.max()>=cal.Date.min():raise ValueError('Core/calibration label overlap')
                model=study.make_model('lightgbm');model.fit(core[names].to_numpy(),core.label.to_numpy())
                c=study.score_model(model,cal[names].to_numpy(),'lightgbm','vol_1sigma')
                s=study.score_model(model,valid[names].to_numpy(),'lightgbm','vol_1sigma')
                normalized_c,normalized_s,normalization=standardize_scores(c,s)
                raw_cal.append(c);cal_scores.append(normalized_c);pred_scores.append(normalized_s)
                experts.append(dict(window=window,core_end=str(core.Date.max()),core_label_end=str(core.label_end_date.max()),**normalization))
            weights,aps=calibration_weights(cal.future_return<-.05,raw_cal)
            matrix_cal,matrix_prediction=np.array(cal_scores),np.array(pred_scores)
            outputs=[(matrix_cal[0],matrix_prediction[0]),(matrix_cal[1],matrix_prediction[1]),
                     (matrix_cal.mean(axis=0),matrix_prediction.mean(axis=0)),
                     (weights@matrix_cal,weights@matrix_prediction)]
            for policy,(c,s) in zip(POLICIES,outputs):
                threshold=study.risk.alarm_threshold(c)
                r=valid[['Date','label_end_date','future_return','label']].copy()
                r['risk_score'],r['threshold'],r['alarm']=s,threshold,s>threshold
                r['common_bear']=r.future_return<-.05
                r['policy'],r['outer_fold'],r['refit_block']=policy,outer['fold'],block_no
                records.append(r)
                audits.append(dict(policy=policy,outer_fold=outer['fold'],refit_block=block_no,
                                   calibration_start=str(cal.Date.min()),calibration_end=str(cal.Date.max()),
                                   calibration_label_end=str(cal.label_end_date.max()),prediction_start=str(valid.Date.min()),
                                   calibration_support=int((cal.future_return<-.05).sum()),weights=weights.tolist(),
                                   calibration_aps=aps,experts=experts,**study.diag.score_stats(c,'calibration_score')))
    return pd.concat(records,ignore_index=True),audits


def main(argv=None):
    args=study.risk.labels.parse_args(argv)
    frame,jobs,names,index,plan=prepare(args)
    output=args.output_dir or study.risk.labels.ROOT/'reports/regime_ensemble'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'ensemble_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    print('Running fixed 3y + expanding experts and causal blends',flush=True)
    records,audits=run(frame,jobs,names)
    for policy,rows in records.groupby('policy'):rows.to_csv(output/(policy+'_predictions.csv'),index=False)
    (output/'ensemble_refits.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    pd.DataFrame(study.risk.summary_rows(records)).to_csv(output/'causal_metrics.csv',index=False)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done, development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
