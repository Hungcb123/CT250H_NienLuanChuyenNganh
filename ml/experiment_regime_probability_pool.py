"""Fixed 50/50 causal-prior/conditional-return forecast pools.

Post-hoc DEVELOPMENT sensitivity only. All-four pool is designated in advance;
no replacing it with the outer-best individual variant or optimizing weights.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

import evaluate_regime_probabilities as audit
native=audit.native
ROOT=native.ROOT
PLAN=native.CONTRACT.parent/'probability_pool_plan.json'
METHODS=['sigma_std20_mean_zero','sigma_std20_mean_shrink','sigma_ewma_mean_zero','sigma_ewma_mean_shrink']


def linear_probability_pool(prior,conditional):
    prior=np.asarray(prior,dtype=float);conditional=np.asarray(conditional,dtype=float)
    if conditional.ndim==3:conditional=conditional.mean(axis=0)
    if prior.shape!=conditional.shape or prior.ndim!=2 or prior.shape[1]!=3:raise ValueError('Invalid probability pool shape')
    for values in [prior,conditional]:
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid probability pool values')
        np.testing.assert_allclose(values.sum(axis=1),1.)
    return .5*prior+.5*conditional


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=PLAN)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);plan=json.loads(args.plan.read_text())
    folder=audit.source.resolved(plan['source']);reference=audit.source.resolved(plan['reference'])
    if native.sha(folder/'probabilities.csv')!=plan['source_probability_sha256'] or native.sha(reference/'probabilities.csv')!=plan['reference_probability_sha256']:raise ValueError('Pool inputs changed')
    rows=pd.read_csv(folder/'probabilities.csv',parse_dates=['Date','label_end_date'])
    prior_rows=pd.read_csv(reference/'probabilities.csv',parse_dates=['Date','label_end_date'])
    for field in ['Date','label_end_date','label','outer_fold','prediction']:np.testing.assert_array_equal(rows[field],prior_rows[field])
    active=prior_rows.calibration_active.to_numpy(dtype=bool)
    np.testing.assert_array_equal(active,rows.active_comparison)
    if len(rows)!=1560 or int(active.sum())!=1280:raise ValueError('Changed probability comparison cohort')
    prior=prior_rows[['causal_prior_'+c for c in audit.CLASSES]].to_numpy()
    raw={name:rows[[name+'_'+c for c in audit.CLASSES]].to_numpy() for name in METHODS}
    predictions={'pooled_'+name:linear_probability_pool(prior,value) for name,value in raw.items()}
    predictions['pooled_all']=linear_probability_pool(prior,np.stack(list(raw.values())))
    output=args.output_dir or ROOT/'reports/regime_probability_pool'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    saved=dict(plan,source_sha256=native.sha(__file__),plan_sha256=native.sha(args.plan),executed_at=datetime.now(timezone.utc).isoformat())
    (output/'plan.json').write_text(json.dumps(saved,indent=2)+'\n')
    summary={};intervals=[];table=[];baseline_loss=audit.proper_losses(rows.label.to_numpy(),prior)
    for name,p in predictions.items():
        metrics=dict(all=audit.probability_metrics(rows,p,np.ones(len(rows),dtype=bool)),active=audit.probability_metrics(rows,p,active),folds=[])
        losses=audit.proper_losses(rows.label.to_numpy(),p)
        for fold in sorted(rows.outer_fold.unique()):metrics['folds'].append(dict(fold=int(fold),**audit.probability_metrics(rows,p,active&(rows.outer_fold.to_numpy()==fold))))
        for metric in ['brier','log_loss']:
            difference=baseline_loss[metric]-losses[metric]
            for block in [20,60]:intervals.append(dict(method=name,metric=metric,block_sessions=block,point_improvement=float(difference[active].mean()),**audit.bootstrap_probability_delta(difference,active,rows.outer_fold.to_numpy(),block)))
        wins=sum(f['n']>0 and f['brier']<float(baseline_loss['brier'][active&(rows.outer_fold.to_numpy()==f['fold'])].mean()) for f in metrics['folds'])
        point=metrics['active']['brier']<float(baseline_loss['brier'][active].mean()) and metrics['active']['log_loss']<float(baseline_loss['log_loss'][active].mean()) and wins>=3
        paired=all(x['low'] is not None and x['low']>0 for x in intervals if x['method']==name)
        metrics['screen']=dict(point=bool(point),paired=bool(paired),passed=bool(point and paired),brier_fold_wins=wins)
        summary[name]=metrics
        table.append(dict(method=name,all_brier=metrics['all']['brier'],active_brier=metrics['active']['brier'],active_log_loss=metrics['active']['log_loss'],
                          mean_fold_argmax_f1=metrics['all']['mean_fold_argmax_f1'],brier_fold_wins=wins,proper_score_screen=bool(point and paired)))
    result=dict(role='Post-hoc pooled probability DEVELOPMENT, not independent acceptance',default_candidate='pooled_all',n=len(rows),active_n=int(active.sum()),
                prior_all=audit.probability_metrics(rows,prior,np.ones(len(rows),dtype=bool)),prior_active=audit.probability_metrics(rows,prior,active),summary=summary,intervals=intervals,
                frozen_point_f1=float(np.mean([f1_score(part.label,part.prediction,labels=[0,1,2],average='macro',zero_division=0) for _,part in rows.groupby('outer_fold')])),
                disclosure='Probability argmax is distinct from unchanged .420 balanced decision. Do not label these outputs calibrated confidence of that point model.')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    exported=rows[['Date','label_end_date','label','outer_fold','prediction']].copy();exported['active_comparison']=active
    for name,p in predictions.items():
        for code,cls in enumerate(audit.CLASSES):exported[name+'_'+cls]=p[:,code]
    exported.to_csv(output/'probabilities.csv',index=False)
    print(pd.DataFrame(table).to_string(index=False),flush=True)
    print('Done; no independent acceptance or policy replacement. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
