"""Matched63-session purged-inner forecasts for complete-fusion calibration.

All component refits occur before their inner forecast block; no outer-fitted
models are reused to score inner validation. Outer archives used after choice.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_information as information
import experiment_regime_return_distribution as density
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from experiment_regime_temporal_fusion import GRID
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_dynamic_tuning import assert_dynamic_inner_timing
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
SEEDS=[7,21,42,84,126]


def fused_scores(classifier,density,parameters):
    weight,tc,td=parameters
    c=np.maximum(classifier,0.)**(1/tc);c/=c.sum(axis=1,keepdims=True)
    d=np.maximum(density,0.)**(1/td);d/=d.sum(axis=1,keepdims=True)
    return (1-weight)*c+weight*d


def run_matched_fusion_calibration(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);args.trials=1;args.timeout=1
    base,outer_c,outer_d,calendar,paths=load_seed_components()
    parent_path=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z/plan.json';parent=json.loads(parent_path.read_text())
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y',
        '--models','LightGBM','--horizons','20','--inner-splits','3','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frames[20],book,'vol_1sigma')
    info,variants,_,_=information.prepare_information(args)
    extra=[c for c in info if c not in frame]
    frame=frame.merge(info[['Date']+extra],on='Date',how='left',validate='one_to_one',sort=False)
    dframe,djobs,_,dplan=density.prepare_return_distribution(args)
    dframe=labels.relabel_cohort(dframe,book,'vol_1sigma')
    choices=json.loads((ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z/inner_selection.json').read_text())
    trend_names={o['fold']:next(j['names'] for n,j in variants if n==o['chosen']) for o in choices}
    paths += [Path(__file__),ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'experiment_regime_temporal_fusion.py',ROOT/'experiment_regime_dynamic_tuning.py',parent_path]
    plan.update(mode='matched63_purged_inner_complete_fusion_calibration_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},grid=GRID,seeds=SEEDS,
        inner_fit='Three purged training validation periods per outer fold; refit63 actual market sessions INSIDE each period. Classifier3y and densityexpanding mature windows match outer algorithms. Both density targets/all5 seeds are re-trained.',
        selection='Macro or directional robustness of complete EMA-blended pipeline on3 inner folds. Subtract .005 squared deviation penalty; keep default(.5,1,1) unless gain>=.005.',
        known_constants='Original outer-fold classifier params/information feature choices reused as constants known at outer decision. Inner score is a research selection score, not an independent hyperparameter test.',
        primary='matched_macro: chosen inner macro coefficients, raw fusion then equal current/causalEMA5',
        secondary='matched_shrink: half matched_macro + half current adaptive0.497292 incumbent; robust criterion diagnostic',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, MCC gain, >=3 wins and paired20/60 lower>0 for provisional evidence.',
        caveat='All outer periods previously inspected; no outer coefficient choice, independent acceptance, calibration guarantee or deployment.')
    output=args.output_dir or ROOT/'reports/regime_matched_calibration'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    selections=[];timings=[]
    for outer in jobs[0]['folds']:
        tuning=frame.iloc[outer['tune']].reset_index(drop=True);folds=exp.base.purged_folds(tuning,3)
        outer_boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tuning,folds,outer_boundary)
        class_results=[]
        for inner_number,(_,valid_ids) in enumerate(folds,1):
            blocks=exp.refit_blocks(tuning,valid_ids,index.Date,63);records=[]
            for block_number,ids in enumerate(blocks,1):
                valid=tuning.iloc[ids];boundary=valid.Date.min()
                train=frame.iloc[exp.training_indices(frame,boundary,'3y')]
                dt=dframe.iloc[exp.training_indices(dframe,boundary,'expanding')]
                dv=valid[['Date']].merge(dframe,on='Date',how='left',validate='one_to_one',sort=False)
                if dv.label_end_date.isna().any():raise ValueError('Missing density validation')
                np.testing.assert_array_equal(valid.label,dv.label)
                parts=[]
                for group in ['trend','risk']:
                    params=next(r['best_params'] for r in parent['classifier_parameters'][group] if r['outer_fold']==outer['fold'])
                    names=trend_names[outer['fold']] if group=='trend' else next(j['names'] for j in jobs if j['group']=='risk')
                    model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=params),train,names)
                    parts.append(model.predict_proba(valid[names].to_numpy(dtype=np.float32)))
                c=np.mean(parts,axis=0);densities=[];prior=np.bincount(dt.label,minlength=3)/len(dt)
                for seed in SEEDS:
                    specification=deepcopy(dplan['specification']);specification['parameters']['random_state']=seed
                    for normalized in [False,True]:
                        _,points,_=density.fit_return_quantiles(dt,dv,djobs['expanding']['names'],normalized,specification)
                        sigma=dv.horizon_sigma.to_numpy();mass=dynamic_quantile_mass(points,specification['quantile_atom_weights'],-sigma,sigma)
                        score=mass/prior;score/=score.sum(axis=1,keepdims=True);densities.append(score)
                d=np.mean(densities,axis=0)
                rows=valid[['Date','label_end_date','label']].copy();rows[['c_bear','c_side','c_bull']]=c;rows[['d_bear','d_side','d_bull']]=d
                rows['inner_fold'],rows['refit_block']=inner_number,block_number;records.append(rows)
                timing=dict(outer_fold=outer['fold'],inner_fold=inner_number,block=block_number,boundary=str(boundary.date()),
                    classifier_label_end=str(train.label_end_date.max().date()),density_label_end=str(dt.label_end_date.max().date()),n_classifier=len(train),n_density=len(dt),n_valid=len(valid))
                if train.label_end_date.max()>=boundary or dt.label_end_date.max()>=boundary:raise ValueError('Unmatured matched refit')
                timings.append(timing)
                print(f'Outer{outer["fold"]} inner{inner_number} refit{block_number} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            rows.to_csv(output/f'outer{outer["fold"]}_inner{inner_number}_forecasts.csv',index=False)
            c=rows[['c_bear','c_side','c_bull']].to_numpy();d=rows[['d_bear','d_side','d_bull']].to_numpy()
            values=[]
            for parameters in GRID:
                raw=fused_scores(c,d,parameters)
                scores=.5*raw+.5*causal_forecast_ema(rows.Date,raw,index.Date,5)
                classes=precision_recall_fscore_support(rows.label,scores.argmax(axis=1),labels=[0,1,2],zero_division=0)[2]
                values.append(classes)
            class_results.append(np.asarray(values))
        classes=np.asarray(class_results);macro=classes.mean(axis=2)
        mean=macro.mean(axis=0);robust=.5*mean+.25*macro.min(axis=0)+.25*classes.mean(axis=0)[:,[0,2]].min(axis=1)
        penalty=np.array([.005*((2*(w-.5))**2+np.log(tc)**2+np.log(td)**2) for w,tc,td in GRID])
        chosen={}
        for rule,values in [('macro',mean),('robust',robust)]:
            penalized=values-penalty;best=int(penalized.argmax());chosen[rule]=best if penalized[best]>=penalized[0]+.005 else 0
        selections.append(dict(fold=outer['fold'],outer_boundary=str(outer_boundary.date()),latest_tuning_label_end=str(tuning.label_end_date.max().date()),chosen=chosen,
            candidates=[dict(parameters=parameters,mean_f1=float(mean[i]),robust=float(robust[i]),penalty=float(penalty[i])) for i,parameters in enumerate(GRID)]))
        (output/'selection.json').write_text(json.dumps(selections,indent=2)+'\n');(output/'timing_audit.json').write_text(json.dumps(timings,indent=2)+'\n')
        print('Outer '+str(outer['fold'])+' choices '+str({k:GRID[v] for k,v in chosen.items()}),flush=True)
    raw={rule:np.empty_like(outer_c) for rule in ['macro','robust']}
    for outer in selections:
        mask=base.outer_fold.eq(outer['fold']).to_numpy()
        for rule,choice in outer['chosen'].items():raw[rule][mask]=fused_scores(outer_c[mask],outer_d[mask],GRID[choice])
    matrices={'incumbent':base[['p_bear','p_side','p_bull']].to_numpy()}
    for rule,values in raw.items():matrices['matched_'+rule]=.5*values+.5*causal_forecast_ema(base.Date,values,index.Date,5)
    matrices['matched_shrink']=.5*matrices['incumbent']+.5*matrices['matched_macro']
    finish_research_study(base,matrices,output,['matched_macro','matched_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_matched_fusion_calibration()
