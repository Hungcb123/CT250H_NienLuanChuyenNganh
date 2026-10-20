"""Select complete fused pipelines on genuine purged inner forecasts.

Refit density heads within every inner fold; never reuse outer-fitted heads for
inner scoring. Archived outer candidates are used only AFTER choices are fixed.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_information as information
import experiment_regime_return_distribution as density
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from experiment_regime_dynamic_families import fit_dynamic_family,FAMILIES
from experiment_regime_dynamic_losses import fit_dynamic_loss,LOSSES
from experiment_regime_dynamic_tuning import dynamic_inner_score,assert_dynamic_inner_timing
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
SOURCES={
 'family':ROOT/'reports/regime_dynamic_families/20261019T052530_594387Z',
 'loss':ROOT/'reports/regime_dynamic_losses/20261019T052808_023744Z',
 'info':ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z'}


def run_fusion_selection(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);args.trials=1;args.timeout=1
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    for directory in SOURCES.values():
        source=json.loads((directory/'plan.json').read_text())
        for name,digest in source['source_hashes'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--inner-splits','3','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frames[20],book,'vol_1sigma')
    names=list(dict.fromkeys(n for j in jobs for n in j['names']))
    info_frame,variants,_,_=information.prepare_information(args)
    extras=[c for c in info_frame if c not in frame]
    frame=frame.merge(info_frame[['Date']+extras],on='Date',how='left',validate='one_to_one',sort=False)
    return_frame,return_jobs,_,return_plan=density.prepare_return_distribution(args)
    return_frame=labels.relabel_cohort(return_frame,book,'vol_1sigma')
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    candidates=[('family',n) for n in FAMILIES if n!='legacy_equal']+[('loss',n) for n in LOSSES]+[('info',n) for n,j in variants if n!='control']
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_dynamic_families.py',ROOT/'experiment_regime_dynamic_losses.py',ROOT/'experiment_regime_dynamic_tuning.py',args.parent_dir/'plan.json']
    for directory in SOURCES.values():paths += [directory/'plan.json']+list(directory.glob('*_scores.csv'))
    paths += [old/n for n in ['trend_predictions.csv','risk_predictions.csv','expanding_raw_mapped_predictions.csv','expanding_normalized_mapped_predictions.csv']]
    plan.update(mode='inner_complete_pipeline_fusion_selection_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},candidates=candidates,
        inner_density='Independently train old raw and normalized expanding quantile models BEFORE each inner boundary; same dynamic CDF and mature target-only prior. NO outer-fitted density leakage.',
        inner_classifier='3y rolling history before each inner boundary; fixed source parameters. Original fold parameters reused as research constants known at outer boundary; these inner scores are selection scores, not independent parameter tests.',
        fusion_choices={'replace':'.5 candidate classifier + .5 density','supplement':'.25 candidate classifier + .25 old equal classifier + .5 density'},
        primary='Choose complete fusion by mean three-inner-fold macro F1, switch only for >=.005 above complete incumbent; deterministic candidate order.',
        secondary='Same pipeline pool but inner directional robustness objective; same margin. Outer results never choose source/fusion.',
        acceptance='Mean F1 +.01, no worse worst fold or mean bear/bull F1, MCC increase, >=3 fold wins; both paired20/60 lower bounds >0 for provisional evidence.',
        caveat='Research prompted by previously inspected outer outcomes. Chronological fitting is preserved but no independent-test or calibrated probability claim is possible. No deployment.')
    output=args.output_dir or ROOT/'reports/regime_fusion_selection'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    selections=[];all_inner=[]
    for outer in jobs[0]['folds']:
        legacy={j['group']:dict(names=j['names'],params=next(r['best_params'] for r in parent['classifier_parameters'][j['group']] if r['outer_fold']==outer['fold'])) for j in jobs}
        tuning=frame.iloc[outer['tune']].reset_index(drop=True);folds=exp.base.purged_folds(tuning,3)
        outer_boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tuning,folds,outer_boundary)
        metrics={'incumbent':[]}
        for kind,name in candidates:
            for mix in ['replace','supplement']:metrics[kind+'/'+name+'/'+mix]=[]
        for number,(_,valid_ids) in enumerate(folds,1):
            valid=tuning.iloc[valid_ids].copy();boundary=valid.Date.min()
            train=frame.iloc[exp.training_indices(frame,boundary,'3y')]
            density_train=return_frame.iloc[exp.training_indices(return_frame,boundary,'expanding')]
            density_valid=valid[['Date']].merge(return_frame,on='Date',how='left',validate='one_to_one',sort=False)
            if density_valid.label_end_date.isna().any():raise ValueError('Missing inner-density features')
            np.testing.assert_array_equal(valid.label,density_valid.label)
            parts={}
            for group in ['trend','risk']:
                spec=legacy[group];model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=spec['params']),train,spec['names'])
                parts[group]=model.predict_proba(valid[spec['names']].to_numpy(dtype=np.float32))
            equal=.5*(parts['trend']+parts['risk'])
            prior=np.bincount(density_train.label,minlength=3)/len(density_train)
            densities=[]
            for normalized in [False,True]:
                _,points,_=density.fit_return_quantiles(density_train,density_valid,return_jobs['expanding']['names'],normalized,return_plan['specification'])
                sigma=density_valid.horizon_sigma.to_numpy()
                mass=dynamic_quantile_mass(points,return_plan['specification']['quantile_atom_weights'],-sigma,sigma)
                score=mass/prior;score/=score.sum(axis=1,keepdims=True);densities.append(score)
            d=np.mean(densities,axis=0)
            incumbent=.5*equal+.5*d
            metrics['incumbent'].append(exp.base.classification_metrics(valid.label,incumbent.argmax(axis=1),train.label))
            for kind,name in candidates:
                if kind=='family':score=fit_dynamic_family(train,valid,names,name)
                elif kind=='loss':score=fit_dynamic_loss(train,valid,names,name)
                else:
                    job=next(j for n,j in variants if n==name);spec=legacy['trend']
                    model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=spec['params']),train,job['names'])
                    trend=model.predict_proba(valid[job['names']].to_numpy(dtype=np.float32))
                    score=.5*trend+.5*parts['risk']
                for mix,fused in [('replace',.5*score+.5*d),('supplement',.25*score+.25*equal+.5*d)]:
                    metrics[kind+'/'+name+'/'+mix].append(exp.base.classification_metrics(valid.label,fused.argmax(axis=1),train.label))
            all_inner.append(dict(outer_fold=outer['fold'],inner_fold=number,boundary=str(boundary.date()),
                classifier_label_end=str(train.label_end_date.max().date()),density_label_end=str(density_train.label_end_date.max().date()),
                classifier_rows=len(train),density_rows=len(density_train),validation_rows=len(valid)))
            print(f'Outer {outer["fold"]} inner {number}: full pipelines complete',flush=True)
        summary=[dict(candidate=n,mean_f1=float(np.mean([f['f1_macro'] for f in ms])),robust=dynamic_inner_score(ms),folds=ms) for n,ms in metrics.items()]
        selected={}
        for rule,key in [('macro','mean_f1'),('robust','robust')]:
            best=max(summary,key=lambda r:r[key])
            selected[rule]=best['candidate'] if best[key]>=summary[0][key]+.005 else 'incumbent'
        selections.append(dict(fold=outer['fold'],outer_boundary=str(outer_boundary.date()),chosen=selected,summary=summary))
        (output/'inner_selection.json').write_text(json.dumps(selections,indent=2)+'\n')
        (output/'timing_audit.json').write_text(json.dumps(all_inner,indent=2)+'\n')
        print('Outer '+str(outer['fold'])+' choices '+str(selected),flush=True)
    old_parts=[pd.read_csv(old/(g+'_predictions.csv'))[experts.PROBS].to_numpy() for g in ['trend','risk']]
    equal=np.mean(old_parts,axis=0);densities=[]
    for target in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);densities.append(score)
    d=np.mean(densities,axis=0);incumbent=.5*equal+.5*d
    matrices={'incumbent':incumbent,'fusion_macro':incumbent.copy(),'fusion_robust':incumbent.copy()}
    for outer in selections:
        mask=base.outer_fold.eq(outer['fold']).to_numpy()
        for rule,choice in outer['chosen'].items():
            if choice=='incumbent':continue
            kind,name,mix=choice.split('/')
            rows=pd.read_csv(SOURCES[kind]/(name+'_scores.csv'),parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            score=rows[experts.PROBS].to_numpy()
            if kind=='info':score=.5*score+.5*old_parts[1]
            fused=.5*score+.5*d if mix=='replace' else .25*score+.25*equal+.5*d
            matrices['fusion_'+rule][mask]=fused[mask]
    finish_research_study(base,matrices,output,['fusion_macro','fusion_robust'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_fusion_selection()
