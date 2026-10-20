"""Common fixed-cohort DEVELOPMENT reporting; never replaces a live model."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import experiment_regime_expert_selection as experts
from audit_regime_expert_selection import fold_f1


def finish_research_study(base, matrices, output, primary_names):
    output=Path(output)
    if base.Date.duplicated().any() or not base.Date.is_monotonic_increasing:
        raise ValueError('Evaluation dates must be unique and ordered')
    results=[];predictions={};table=[]
    for name,values in matrices.items():
        values=np.asarray(values,dtype=float)
        if values.shape!=(len(base),3) or not np.isfinite(values).all() or (values<0).any():
            raise ValueError('Invalid scores: '+name)
        np.testing.assert_allclose(values.sum(axis=1),1.,atol=1e-12)
        result,rows=experts.expert_metrics(name,base,values.argmax(axis=1))
        rows[experts.PROBS]=values
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
        results.append(result);predictions[name]=rows.prediction.to_numpy(dtype=int)
        summary={k:result[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']}
        for c in ['bear','side','bull']:
            summary[c+'_mean_f1']=float(np.mean([f['per_class'][c]['f1-score'] for f in result['folds']]))
        table.append(summary)
    control=next(r for r in table if r['candidate']=='incumbent')
    control_result=next(r for r in results if r['candidate']=='incumbent')
    groups=[np.flatnonzero(base.outer_fold.to_numpy()==n) for n in sorted(base.outer_fold.unique())]
    y=base.label.to_numpy(dtype=int);intervals=[];comparisons=[]
    for name in primary_names:
        r=next(r for r in table if r['candidate']==name)
        detailed=next(r for r in results if r['candidate']==name)
        wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(detailed['folds'],control_result['folds']))
        passed=(r['mean_f1']>=control['mean_f1']+.01 and r['worst_f1']>=control['worst_f1']
            and r['mean_mcc']>control['mean_mcc'] and wins>=3
            and all(r[c+'_mean_f1']>=control[c+'_mean_f1'] for c in ['bear','bull']))
        for length in [20,60]:
            rng=np.random.default_rng(42);deltas=[]
            for _ in range(1000):
                sample=[]
                for ids in groups:
                    starts=rng.integers(0,len(ids),size=int(np.ceil(len(ids)/length)))
                    sample.append(ids[((starts[:,None]+np.arange(length))%len(ids)).ravel()[:len(ids)]])
                deltas.append(fold_f1(y,predictions[name],sample)-fold_f1(y,predictions['incumbent'],sample))
            low,high=np.quantile(deltas,[.025,.975])
            intervals.append(dict(candidate=name,block_sessions=length,delta=r['mean_f1']-control['mean_f1'],low=float(low),high=float(high)))
        comparisons.append(dict(candidate=name,fold_wins=wins,point_screen=bool(passed),
            provisional_robust_evidence=bool(passed and all(i['low']>0 for i in intervals if i['candidate']==name))))
    report=dict(role='Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment',
        results=results,comparisons=comparisons,paired_intervals=intervals)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    lines=['# Historical development experiment','',report['role'],'',
        'Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.','',
        '| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |','|---|---:|---:|---:|---:|---:|']
    for r in table:lines.append(f"| {r['candidate']} | {r['mean_f1']:.4f} | {r['worst_f1']:.4f} | {r['bear_mean_f1']:.4f} | {r['bull_mean_f1']:.4f} | {r['mean_mcc']:.4f} |")
    lines+=['','Preset primary screens:', '```json',json.dumps(comparisons,indent=2),'```','',
        'Paired circular-block intervals are descriptive sensitivity on repeatedly inspected history, not multiple-testing-adjusted independent inference. No outer-best diagnostic is automatically promoted.','',
        '```json',json.dumps(intervals,indent=2),'```','',
        'See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.']
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    print(pd.DataFrame(table).to_string(index=False),flush=True)
    print(json.dumps(comparisons),flush=True)
    return report
