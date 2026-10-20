"""Fixed heterogeneous mixtures and delayed-feedback expert selection.

Source predictions are already inspected DEVELOPMENT; none is a new holdout.
No weight grid. Selector uses only mature past forecasts, never current labels.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score,classification_report

import experiment_regime as exp
import experiment_regime_families as reports

ROOT=Path(__file__).resolve().parent
PROBS=['p_bear','p_side','p_bull']
POOl=['legacy_equal','legacy_trend','legacy_risk','density_all','density_expanding']
RULE=dict(history_rows=126,min_class_count=5,improvement_margin=.03,refit_market_sessions=20)


def select_past_expert(history,boundary,experts=POOl,rule=RULE):
    boundary=pd.Timestamp(boundary)
    known=history.loc[(history.Date<boundary)&(history.label_end_date<boundary)].tail(rule['history_rows'])
    counts=known.label.value_counts().reindex([0,1,2],fill_value=0).to_numpy()
    info=dict(n=len(known),latest_label_end=str(known.label_end_date.max()) if len(known) else None,class_counts=counts.tolist())
    if len(known)<rule['history_rows'] or (counts<rule['min_class_count']).any():
        return 'legacy_equal',dict(**info,reason='insufficient_mature_class_history',scores={})
    scores={name:float(f1_score(known.label,known[name],labels=[0,1,2],average='macro',zero_division=0)) for name in experts}
    best=max(experts,key=lambda name:scores[name])
    chosen=best if scores[best]>=scores['legacy_equal']+rule['improvement_margin'] else 'legacy_equal'
    return chosen,dict(**info,reason='mature_macro_f1_with_baseline_margin',scores=scores)


def load_expert_sources(args):
    base=pd.read_csv(args.classifier_dir/'legacy_equal_63_predictions.csv',parse_dates=['Date','label_end_date'])
    matrices={};hashes={}
    for name,file in [('legacy_equal','legacy_equal_63'),('legacy_trend','legacy_trend_63'),('legacy_risk','legacy_risk_63')]:
        path=args.classifier_dir/(file+'_predictions.csv')
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        matrices[name]=rows[PROBS].to_numpy(dtype=float);hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    density={}
    for window in ['3y','expanding']:
        for target in ['raw','normalized']:
            path=args.density_dir/(window+'_'+target+'_predictions.csv')
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            prior=rows[['base_bear','base_side','base_bull']].to_numpy(dtype=float)
            if (prior<=0).any():raise ValueError('Undefined training frequency')
            value=rows[PROBS].to_numpy(dtype=float)/prior
            value/=value.sum(axis=1,keepdims=True)
            density[window+'_'+target]=value;hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    matrices['density_all']=np.mean(list(density.values()),axis=0)
    matrices['density_expanding']=(density['expanding_raw']+density['expanding_normalized'])/2
    matrices['blend_all']=.5*matrices['legacy_equal']+.5*matrices['density_all']
    matrices['blend_expanding']=.5*matrices['legacy_equal']+.5*matrices['density_expanding']
    for values in matrices.values():
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid expert scores')
        np.testing.assert_allclose(values.sum(axis=1),1.)
    return base,matrices,hashes


def delayed_expert_predictions(base,matrices,calendar):
    positions=pd.DatetimeIndex(calendar).get_indexer(base.Date)
    if (positions<0).any():raise ValueError('Missing actual market session')
    outcomes=base[['Date','label_end_date','label']].copy()
    for name in POOl:outcomes[name]=matrices[name].argmax(axis=1)
    bucket=(positions-positions[0])//RULE['refit_market_sessions']
    predictions=[];choices=[];last_bucket=None;chosen=None
    for row in range(len(base)):
        if bucket[row]!=last_bucket:
            boundary=base.Date.iloc[row]
            chosen,audit=select_past_expert(outcomes.iloc[:row],boundary)
            choices.append(dict(Date=str(boundary.date()),chosen=chosen,bucket=int(bucket[row]),**audit))
            last_bucket=bucket[row]
        predictions.append(int(matrices[chosen][row].argmax()))
    return np.asarray(predictions),choices


def expert_metrics(name,base,prediction):
    rows=base[['Date','label_end_date','label','future_return','outer_fold']].copy()
    rows['prediction']=prediction
    rows['baseline_prediction']=base.majority.to_numpy()
    folds=[dict(fold=int(n),**exp.prediction_metrics(part),per_class=classification_report(part.label,part.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0)) for n,part in rows.groupby('outer_fold')]
    return dict(candidate=name,mean_f1=float(np.mean([f['f1_macro'] for f in folds])),worst_f1=min(f['f1_macro'] for f in folds),
                mean_mcc=float(np.mean([f['mcc'] for f in folds])),folds=folds,pooled=exp.prediction_metrics(rows)),rows


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classifier-dir',type=Path,default=ROOT/'reports/regime_multiclass_reuse/20261018T151747_040696Z')
    parser.add_argument('--density-dir',type=Path,default=ROOT/'reports/regime_return_distribution/20261018T155423_383833Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    base,matrices,hashes=load_expert_sources(args)
    index,audit=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    parent=json.loads((args.density_dir/'plan.json').read_text())
    if audit['sha256']!=parent['input_hashes']['VNINDEX']:raise ValueError('Source calendar/data changed')
    original=json.loads((args.control_dir/'experiment_report.json').read_text())
    controls=[next(r for r in original['results'] if r['horizon']==20 and r['train_window']=='3y' and r['feature_group']==group) for group in ['trend','risk']]
    output=args.output_dir or ROOT/'reports/regime_expert_selection'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='posthoc_heterogeneous_development',created_at=datetime.now(timezone.utc).isoformat(),
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_hashes=hashes,calendar_hash=audit['sha256'],
              fixed_mixtures=dict(density_all='equal all FOUR density forecasters, no best-only selection',density_expanding='equal RAW/NORMALIZED expanding density',blend_all='half legacy_equal + half density_all',blend_expanding='half legacy_equal + half density_expanding'),
              selector_pool=POOl,selector_rule=RULE,candidates=['density_all','density_expanding','blend_all','blend_expanding','delayed_selector'],
              timing='History rows label_end_date strictly before selection date. Selector refreshes each20 raw sessions, holds selected expert between refreshes. Warmup/insufficient class history falls back to legacy_equal.',
              caveats=['Study motivated by already inspected outer results; all comparisons are DEVELOPMENT only.',
                       'Class-balanced expert vectors are decision scores, not calibrated event probabilities.',
                       'Small overlapping samples give uncertain expert selection; margin is a heuristic, no statistical guarantee.',
                       'No new learner fits, weight grid, label changes or automatic deployment.'])
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    results=[]
    for name in ['density_all','density_expanding','blend_all','blend_expanding']:
        result,rows=expert_metrics(name,base,matrices[name].argmax(axis=1));results.append(result)
        rows.to_csv(output/(name+'_predictions.csv'),index=False)
    prediction,choices=delayed_expert_predictions(base,matrices,index.Date)
    result,rows=expert_metrics('delayed_selector',base,prediction);results.append(result)
    rows.to_csv(output/'delayed_selector_predictions.csv',index=False)
    (output/'selector_history.json').write_text(json.dumps(choices,indent=2)+'\n')
    table=reports.write_family_comparison(results,controls,output)
    print(pd.DataFrame([{k:v for k,v in r.items() if k!='comparisons'} for r in table]).to_string(index=False),flush=True)
    print('Done. DEVELOPMENT only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
