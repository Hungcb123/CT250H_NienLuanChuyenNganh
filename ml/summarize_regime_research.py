"""Audit prediction-backed historical research results against fixed screening gates.

A passing development screen is NOT an independent test or deployment approval.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import experiment_regime_risk as risk

ROOT=Path(__file__).resolve().parent
FAMILIES=['regime_risk','regime_candidates','regime_history','regime_ohlcv','regime_global','regime_fresh','regime_fresh_followup','regime_indices','regime_ensemble','regime_distribution','regime_online','regime_recency_blend','regime_quantile']


def gate_result(pooled,folds,gate):
    reasons=[]
    for metric,bound,direction in [('precision',gate['causal_precision_min'],'min'),('recall',gate['causal_recall_min'],'min'),('alarm_rate',gate['causal_alarm_rate_max'],'max')]:
        value=pooled.get(metric)
        if value is None or not np.isfinite(value) or (value<bound if direction=='min' else value>bound):
            reasons.append(metric)
    if len(folds)!=4 or set(str(x) for x in folds['fold'])!={'1','2','3','4'}:
        reasons.append('missing_folds')
    count=int((folds.average_precision>folds.prevalence).sum())
    minimum=float(folds.roc_auc.min())
    if count<gate['folds_ap_above_prevalence_min']:reasons.append('fold_ap')
    if folds.roc_auc.isna().any() or minimum<gate['no_fold_auroc_below']:reasons.append('fold_auc')
    return dict(passes_development_screen=not reasons,failed_gates=';'.join(reasons),folds_ap_above_base=count,min_fold_auc=minimum)


def audit_metrics(rows,predictions,scheme,reference_dates):
    if predictions.Date.duplicated().any() or not predictions.Date.sort_values().reset_index(drop=True).equals(reference_dates):
        raise ValueError('Study prediction dates differ from canonical frozen dates')
    outcome=predictions.future_return<-.05
    if not np.array_equal(outcome,predictions.common_bear):raise ValueError('Common risk target changed')
    column='alarm' if scheme=='static' else scheme+'_alarm'
    for row in rows.to_dict('records'):
        p=predictions if str(row['fold'])=='all' else predictions.loc[predictions.outer_fold==int(row['fold'])]
        actual=risk.binary_metrics(p.common_bear,p[column])
        for metric in ['n','support','alarms','tp','fp','fn','tn','precision','recall','alarm_rate']:
            a,b=actual[metric],row[metric]
            if a is None and pd.isna(b):continue
            if a is None or not np.isclose(a,b,rtol=1e-9,atol=1e-10):raise ValueError('Summary contradicts predictions: '+metric)


def summarize(root=ROOT):
    root=Path(root)
    state=json.loads((root/'reports/regime_research/progress.json').read_text())
    gate=state['research_gate']
    canonical=pd.read_csv(root/'reports/regime_risk/20261017T152147_353782Z/vol_1sigma_predictions.csv',parse_dates=['Date']).Date.sort_values().reset_index(drop=True)
    results=[]
    for family in FAMILIES:
        for report in sorted((root/'reports'/family).glob('*')):
            path=report/'threshold_comparison.csv'
            if not path.exists():path=report/'causal_metrics.csv'
            if not path.exists():continue
            table=pd.read_csv(path,dtype={'fold':str})
            if 'threshold_scheme' not in table:table['threshold_scheme']='static'
            for (policy,scheme),rows in table.groupby(['policy','threshold_scheme']):
                predictions=pd.read_csv(report/(policy+'_predictions.csv'),parse_dates=['Date'])
                audit_metrics(rows,predictions,scheme,canonical)
                pooled=rows.loc[rows.fold=='all'].iloc[0].to_dict()
                folds=rows.loc[rows.fold!='all']
                results.append(dict(report=str(report.relative_to(root)),policy=policy,threshold_scheme=scheme,
                                    **{k:pooled[k] for k in ['precision','recall','alarm_rate','average_precision','roc_auc','tp','fp','fn']},
                                    **gate_result(pooled,folds,gate)))
    output=root/'reports/regime_research'
    pd.DataFrame(results).to_csv(output/'audited_comparison.csv',index=False)
    passed=[r for r in results if r['passes_development_screen']]
    summary=dict(role='Audited historical DEVELOPMENT screening, not independent test evidence',
                 configurations_screened=len(results),passes=len(passed),passed_candidates=passed,
                 canonical_prediction_days=len(canonical),gate=gate)
    (output/'screening_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='gate'},indent=2))
    return summary


if __name__=='__main__':summarize()
