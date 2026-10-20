"""Post-hoc DEVELOPMENT sensitivity: best balanced trials from saved inner CV.

No additional hyperparameter search. Selection uses saved inner scores only;
the restriction was prompted by inspected outer failures, so not fresh evidence.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report

import experiment_regime_families as family
exp=family.exp
ROOT=family.ROOT


def select_balanced_trial(tuning,family_name):
    key,value=('auto_class_weights','Balanced') if family_name=='CatBoost' else ('class_weight','balanced')
    eligible=[t for t in tuning['trials'] if t['state']=='COMPLETE' and t['model_parameters'].get(key)==value and np.isfinite(t['value'])]
    if not eligible:raise ValueError('No balanced trial available; do not silently retune')
    for trial in eligible:
        for fold in trial['inner_folds']:
            if pd.Timestamp(fold['latest_train_label_end'])>=pd.Timestamp(fold['validation_start']):raise ValueError('Noncausal source inner score')
    best=min(eligible,key=lambda t:(-t['value'],t['number']))
    return dict(parameters=best['model_parameters'],trial_number=best['number'],inner_f1=best['value'],eligible_trials=len(eligible),original_trials=len(tuning['trials']))


def replay_balanced(frame,job,name,selections,output):
    records=[];folds=[]
    for outer in job['folds']:
        chosen=selections[str(outer['fold'])];rows=[];refits=[]
        for number,block in enumerate(outer['blocks'],1):
            family.assert_family_split(frame,block['train'],block['validation'])
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            model=family.build_family(name,chosen['parameters'])
            model.fit(train[job['names']].to_numpy(dtype=np.float32),train.label.to_numpy(dtype=int))
            pred=np.asarray(model.predict(valid[job['names']].to_numpy(dtype=np.float32))).reshape(-1).astype(int)
            r=valid[['Date','label_end_date','label','future_return']].copy()
            r['prediction']=pred;r['baseline_prediction']=np.bincount(train.label.to_numpy(dtype=int),minlength=3).argmax()
            r['outer_fold'],r['refit_block']=outer['fold'],number;rows.append(r)
            refits.append(dict(n_train=len(train),train_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date())))
        rows=pd.concat(rows,ignore_index=True);records.append(rows)
        metric=exp.prediction_metrics(rows);metric.update(fold=outer['fold'],refits=refits,
            per_class=classification_report(rows.label,rows.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0))
        folds.append(metric)
        pd.concat(records,ignore_index=True).to_csv(output/(name+'_predictions.csv'),index=False)
        print(name,outer['fold'],metric['f1_macro'],metric['mcc'],flush=True)
    records=pd.concat(records,ignore_index=True)
    return dict(candidate=name+'_balanced_reuse',mean_f1=float(np.mean([f['f1_macro'] for f in folds])),worst_f1=min(f['f1_macro'] for f in folds),
                mean_mcc=float(np.mean([f['mcc'] for f in folds])),folds=folds,pooled=exp.prediction_metrics(records),
                pooled_class_report=classification_report(records.label,records.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'reports/regime_families/20261018T154106_332331Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);args.trials=15
    frame,job,controls,plan=family.prepare_family_study(args)
    source=json.loads((args.source/'plan.json').read_text())
    if source['input_hashes']!=plan['input_hashes'] or source['feature_groups']!=plan['feature_groups']:raise ValueError('Source data/features changed')
    if source['source_sha256']!=hashlib.sha256(Path(family.__file__).read_bytes()).hexdigest():raise ValueError('Original family training code changed')
    choices={};hashes={}
    for name in family.FAMILIES:
        path=args.source/(name+'_tuning.json');tuning=json.loads(path.read_text())
        if len(tuning)!=4:raise ValueError('Incomplete source tuning')
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        choices[name]={str(fold['outer_fold']):select_balanced_trial(fold,name) for fold in tuning}
    plan.update(mode='posthoc_balanced_family_selection_development',source_study=str(args.source),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_tuning_hashes=hashes,
                choices=choices,optuna=None,new_trials=0,
                parameter_mode='Best saved balanced trial by INNER score, fixed across each outer fold refits',
                disclosure='Restriction prompted by inspected outer fold3 collapse. Causal replay but POST-HOC DEVELOPMENT, not independent evidence.')
    output=args.output_dir or ROOT/'reports/regime_family_balance'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    results=[]
    for name in family.FAMILIES:
        result=replay_balanced(frame,job,name,choices[name],output)
        results.append(result);family.write_family_comparison(results,controls,output)
    print('Done. Post-hoc DEVELOPMENT only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
