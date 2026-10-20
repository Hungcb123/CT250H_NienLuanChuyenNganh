"""Adaptive-label OHLCV/VIX/size-index information, inner-selected inputs."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_information as information
import experiment_regime_labels as labels
import experiment_regime_multiclass_reuse as reuse
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_tuning import dynamic_inner_score,assert_dynamic_inner_timing
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def run_dynamic_information(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv);args.trials=1;args.timeout=1
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    frame,variants,plan,consensus=information.prepare_information(args)
    index,_=information.exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in variants[0][1]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    source=dict(inner_tuning=parent['classifier_parameters']['trend'])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_dynamic_tuning.py',
        args.parent_dir/'plan.json',old/'trend_predictions.csv',old/'risk_predictions.csv',
        old/'expanding_raw_mapped_predictions.csv',old/'expanding_normalized_mapped_predictions.csv']
    paths += [Path(module.__file__) for module in [information,information.ohlcv,information.global_risk,information.indices]]
    plan.update(mode='adaptive_label_information_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        parameters='Original per-outer trend LightGBM params frozen; only information features vary. No hyperparameter tuning.',
        primary='inner_selected_blend: choose one of control/OHLCV/VIX/indices/combined on three purged inner folds; equal with old risk classifier, then fixed half old expanding density.',
        secondary='combined_blend, no outer selection',
        label_rule=parent['label_rule'],selector_objective='Half mean inner F1 + quarter worst inner F1 + quarter lower mean bear/bull F1',
        acceptance='Mean F1 +.01, no worst or mean bear/bull F1 degradation, MCC gain and >=3 fold wins; both paired20/60 lower bounds >0 for provisional robust evidence.',
        caveat='Data-source consensus is not independent point-in-time certification. Missing information stays NaN. Historical development only, no deployment.')
    output=args.output_dir or ROOT/'reports/regime_dynamic_information'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    consensus.to_csv(output/'consensus_fields.csv',index=False)
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    completed={}
    for name,job in variants:
        print('Fitting information group '+name,flush=True)
        rows,audits=reuse.run_reused(frame,job,source)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        if name=='control':np.testing.assert_allclose(rows[experts.PROBS],base[experts.PROBS],atol=1e-12,rtol=1e-12)
        rows.to_csv(output/(name+'_scores.csv'),index=False)
        (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
        completed[name]=rows[experts.PROBS].to_numpy()
    selected=np.empty((len(base),3));choices=[]
    for outer in variants[0][1]['folds']:
        tuning=frame.iloc[outer['tune']].reset_index(drop=True)
        folds=information.exp.base.purged_folds(tuning,3)
        boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tuning,folds,boundary)
        params=next(r['best_params'] for r in source['inner_tuning'] if r['outer_fold']==outer['fold'])
        scores=[]
        for name,job in variants:
            metrics=[]
            for t,v in folds:
                train,valid=tuning.iloc[t],tuning.iloc[v]
                model,_=information.exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=params),train,job['names'])
                pred=model.predict(valid[job['names']].to_numpy(dtype=np.float32))
                metrics.append(information.exp.base.classification_metrics(valid.label,pred,train.label))
            scores.append(dict(name=name,score=dynamic_inner_score(metrics),folds=metrics))
        choice=max(scores,key=lambda r:r['score'])['name']
        mask=base.outer_fold.eq(outer['fold']).to_numpy();selected[mask]=completed[choice][mask]
        choices.append(dict(fold=outer['fold'],chosen=choice,outer_boundary=str(boundary.date()),
            latest_tuning_label_end=str(tuning.label_end_date.max().date()),scores=scores))
    (output/'inner_selection.json').write_text(json.dumps(choices,indent=2)+'\n')
    risk=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(risk[key],base[key])
    densities=[]
    for target in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);densities.append(score)
    density=np.mean(densities,axis=0)
    matrices={name+'_blend':.25*score+.25*risk[experts.PROBS].to_numpy()+.5*density for name,score in completed.items()}
    matrices['incumbent']=matrices['control_blend']
    matrices['inner_selected_blend']=.25*selected+.25*risk[experts.PROBS].to_numpy()+.5*density
    finish_research_study(base,matrices,output,['inner_selected_blend','combined_blend'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_dynamic_information()
