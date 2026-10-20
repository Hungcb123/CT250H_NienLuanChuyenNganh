"""Causal refit cadence ablation for the adaptive-target ensemble.

Same labels, dates, features, hyperparameters and fusion weights; only age of
fitted components changes. Compare against highest observed information model.
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
import experiment_regime_return_distribution as density
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def run_dynamic_refresh(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--challenger-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y',
        '--models','LightGBM','--horizons','20','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frames[20],book,'vol_1sigma')
    density_frame,density_jobs,_,density_plan=density.prepare_return_distribution(args)
    density_frame=labels.relabel_cohort(density_frame,book,'vol_1sigma')
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    challenger_path=args.challenger_dir/'inner_selected_blend_predictions.csv'
    challenger=pd.read_csv(challenger_path,parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],challenger[key])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',challenger_path,args.challenger_dir/'plan.json']
    paths += [old/n for n in ['trend_predictions.csv','risk_predictions.csv','expanding_raw_mapped_predictions.csv','expanding_normalized_mapped_predictions.csv']]
    counts={}
    for cadence in [20,5]:
        counts['classifier_'+str(cadence)]=sum(len(exp.refit_blocks(frame,np.concatenate([b['validation'] for b in o['blocks']]),index.Date,cadence)) for o in jobs[0]['folds'])
    counts['density20']=sum(len(exp.refit_blocks(density_frame,np.concatenate([b['validation'] for b in o['blocks']]),index.Date,20)) for o in density_jobs['expanding']['folds'])
    plan.update(mode='adaptive_target_component_refresh_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        original_classifier_parameters=parent['classifier_parameters'],density_specification=density_plan['specification'],refit_counts=counts,
        primary='both20: .5 equal refreshed trend/risk classifiers (20 sessions) + .5 refreshed equal raw/normalized expanding density (20 sessions)',
        secondary='fast_class_ensemble: .25 equal20 classifier + .25 equal5 classifier + .5 density20',
        controls='Highest observed information challenger is incumbent. Stable original63 ensemble also reported; separate classifier-only/density-only refresh diagnostics.',
        timing='Anchor each cadence at original outer fold first evaluation session. Every refit uses labels ending STRICTLY before its actual first prediction. Target shift remains20 raw sessions.',
        acceptance='Mean macro F1 incumbent +.01, no worst fold or mean bear/bull F1 loss, higher MCC and >=3 fold wins; paired20/60 intervals lower>0 for provisional evidence.',
        caveat='Repeatedly inspected historical development; no independent-test, confidence or deployment claim.')
    output=args.output_dir or ROOT/'reports/regime_dynamic_refresh'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True);print('Refit counts: '+str(counts),flush=True)
    if args.audit_only:return output
    old_parts={}
    for g in ['trend','risk']:
        rows=pd.read_csv(old/(g+'_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        old_parts[g]=rows[experts.PROBS].to_numpy()
    old_classifier=.5*(old_parts['trend']+old_parts['risk'])
    old_density=[]
    for target in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_density.append(score)
    old_density=np.mean(old_density,axis=0)
    classifier={};parity={}
    for cadence in [20,5]:
        parts=[]
        for job in jobs:
            group=job['group'];records=[];audits=[]
            for outer in job['folds']:
                params=next(r['best_params'] for r in parent['classifier_parameters'][group] if r['outer_fold']==outer['fold'])
                validation=np.concatenate([b['validation'] for b in outer['blocks']])
                blocks=exp.refit_blocks(frame,validation,index.Date,cadence)
                for number,valid_ids in enumerate(blocks,1):
                    valid=frame.iloc[valid_ids];boundary=valid.Date.min()
                    train=frame.iloc[exp.training_indices(frame,boundary,'3y')]
                    if train.label_end_date.max()>=boundary:raise ValueError('Unmatured classifier label')
                    model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=params),train,job['names'])
                    probability=model.predict_proba(valid[job['names']].to_numpy(dtype=np.float32))
                    if number==1:
                        reference=base.Date.isin(valid.Date).to_numpy()
                        np.testing.assert_allclose(probability,old_parts[group][reference],rtol=1e-12,atol=1e-12)
                        parity[f'{cadence}_{group}_fold{outer["fold"]}']=len(valid)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=probability
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(fold=outer['fold'],block=number,boundary=str(boundary.date()),n_train=len(train),latest_label_end=str(train.label_end_date.max().date())))
                pd.concat(records,ignore_index=True).to_csv(output/f'classifier{cadence}_{group}_scores.csv',index=False)
                print(f'Classifier{cadence} {group} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            (output/f'classifier{cadence}_{group}_refits.json').write_text(json.dumps(audits,indent=2)+'\n')
            parts.append(rows[experts.PROBS].to_numpy())
        classifier[cadence]=np.mean(parts,axis=0)
    densities=[]
    for normalized in [False,True]:
        target='normalized' if normalized else 'raw';records=[];audits=[]
        source=pd.read_csv(old/('expanding_'+target+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        job=density_jobs['expanding']
        for outer in job['folds']:
            validation=np.concatenate([b['validation'] for b in outer['blocks']])
            blocks=exp.refit_blocks(density_frame,validation,index.Date,20)
            for number,valid_ids in enumerate(blocks,1):
                valid=density_frame.iloc[valid_ids];boundary=valid.Date.min()
                train=density_frame.iloc[exp.training_indices(density_frame,boundary,'expanding')]
                _,points,crossings=density.fit_return_quantiles(train,valid,job['names'],normalized,density_plan['specification'])
                sigma=valid.horizon_sigma.to_numpy()
                mass=dynamic_quantile_mass(points,density_plan['specification']['quantile_atom_weights'],-sigma,sigma)
                prior=np.bincount(train.label,minlength=3)/len(train)
                score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                if number==1:
                    reference=source.loc[source.Date.isin(valid.Date)]
                    before=reference[experts.PROBS].to_numpy()/reference[density.BASE_PROBS].to_numpy();before/=before.sum(axis=1,keepdims=True)
                    np.testing.assert_allclose(score,before,atol=1e-12,rtol=1e-12)
                    parity[f'density20_{target}_fold{outer["fold"]}']=len(valid)
                rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
                rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                for i,q in enumerate(density_plan['specification']['quantile_levels']):rows[f'log_q{round(q*100):02d}']=points[:,i]
                audits.append(dict(fold=outer['fold'],block=number,boundary=str(boundary.date()),n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prior=prior.tolist(),crossings=crossings))
            pd.concat(records,ignore_index=True).to_csv(output/f'density20_{target}_scores.csv',index=False)
            (output/f'density20_{target}_refits.json').write_text(json.dumps(audits,indent=2)+'\n')
            print(f'Density20 {target} fold{outer["fold"]} complete',flush=True)
        rows=pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        densities.append(rows[experts.PROBS].to_numpy())
    d20=np.mean(densities,axis=0)
    matrices=dict(incumbent=challenger[experts.PROBS].to_numpy(),stable63=.5*old_classifier+.5*old_density,
        classifier20_only=.5*classifier[20]+.5*old_density,classifier5_only=.5*classifier[5]+.5*old_density,
        density20_only=.5*old_classifier+.5*d20,both20=.5*classifier[20]+.5*d20,
        fast_class_ensemble=.25*classifier[20]+.25*classifier[5]+.5*d20,
        mixed_density20=.5*classifier[20]+.25*old_density+.25*d20)
    (output/'first_refit_parity.json').write_text(json.dumps(parity,indent=2)+'\n')
    finish_research_study(base,matrices,output,['both20','fast_class_ensemble'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_dynamic_refresh()
