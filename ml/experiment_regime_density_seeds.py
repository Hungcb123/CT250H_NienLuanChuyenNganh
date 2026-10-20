"""Fixed multi-seed density ensemble; no outer seed selection.

Keep seed42 snapshots and fit seeds7/21/84/126 on identical original cohorts.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
SEEDS=[7,21,42,84,126]


def run_density_seed_ensemble(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--challenger-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    index,_=density.exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    parts=[];paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',args.challenger_dir/'inner_selection.json',args.challenger_dir/'inner_selected_blend_predictions.csv']
    for group in ['trend','risk']:
        path=old/(group+'_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        parts.append(rows[experts.PROBS].to_numpy())
    old_equal=np.mean(parts,axis=0)
    selected_trend=np.empty_like(parts[0]);selection=json.loads((args.challenger_dir/'inner_selection.json').read_text())
    for outer in selection:
        path=args.challenger_dir/(outer['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        mask=base.outer_fold.eq(outer['fold']).to_numpy();selected_trend[mask]=rows.loc[mask,experts.PROBS].to_numpy()
    info_equal=.5*(selected_trend+parts[1])
    cached=[]
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);cached.append(score)
    seed_scores={42:np.mean(cached,axis=0)}
    challenger=pd.read_csv(args.challenger_dir/'inner_selected_blend_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],challenger[key])
    np.testing.assert_allclose(.5*info_equal+.5*seed_scores[42],challenger[experts.PROBS],atol=1e-12,rtol=1e-12)
    plan.update(mode='fixed_density_multiseed_ensemble_DEVELOPMENT',optuna=None,seeds=SEEDS,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        primary='info_seed5: .5 fixed inner-selected information classifier + .5 equal density over all5 seeds, each seed equal raw/normalized',
        secondary='info_seed5_shrink: .5 same classifier + .25 old42 density + .25 equal5 density',
        seed_policy='Fixed before scoring; never select best outer seed. Seed42 reused exactly from archived original forecasts. All other learner parameters/cohorts/refit63 unchanged.',
        acceptance='Mean macro F1 highest incumbent +.01, no worst/directional decline, MCC gain, >=3 wins; paired20/60 lower>0 for provisional evidence.',
        caveat='Seed diversity is not new economic information. All historical dates repeatedly inspected; no independent acceptance, confidence claim or deployment.')
    output=args.output_dir or ROOT/'reports/regime_density_seeds'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    job=jobs['expanding']
    for seed in SEEDS:
        if seed==42:continue
        specification=deepcopy(plan['specification']);specification['parameters']['random_state']=seed
        targets=[]
        for normalized in [False,True]:
            target='normalized' if normalized else 'raw';records=[];audits=[]
            for outer in job['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    _,points,crossings=density.fit_return_quantiles(train,valid,job['names'],normalized,specification)
                    sigma=valid.horizon_sigma.to_numpy()
                    mass=dynamic_quantile_mass(points,specification['quantile_atom_weights'],-sigma,sigma)
                    prior=np.bincount(train.label,minlength=3)/len(train)
                    score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),prior=prior.tolist(),crossings=crossings))
                pd.concat(records,ignore_index=True).to_csv(output/f'seed{seed}_{target}_scores.csv',index=False)
                (output/f'seed{seed}_{target}_refits.json').write_text(json.dumps(audits,indent=2)+'\n')
                print(f'Seed{seed} {target} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
            targets.append(rows[experts.PROBS].to_numpy())
        seed_scores[seed]=np.mean(targets,axis=0)
    mean=np.mean([seed_scores[s] for s in SEEDS],axis=0)
    matrices=dict(incumbent=challenger[experts.PROBS].to_numpy(),stable63=.5*old_equal+.5*seed_scores[42],
        info_seed5=.5*info_equal+.5*mean,info_seed5_shrink=.5*info_equal+.25*seed_scores[42]+.25*mean,
        stable_seed5=.5*old_equal+.5*mean)
    for seed,score in seed_scores.items():matrices[f'seed{seed}_diagnostic']=.5*info_equal+.5*score
    finish_research_study(base,matrices,output,['info_seed5','info_seed5_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_density_seed_ensemble()
