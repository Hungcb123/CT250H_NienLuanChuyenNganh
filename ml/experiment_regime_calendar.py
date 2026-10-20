"""Calendar-seasonality features for both components of the fixed ensemble.

Calendar values are known at t. No absolute year/time index or target relabeling.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_information as information
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_experts import dynamic_quantile_mass
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def calendar_features(dates):
    dates=pd.DatetimeIndex(dates)
    frame=pd.DataFrame({'Date':dates})
    for name,phase in [('month',(dates.month-1)/12),('month_day',(dates.day-1)/31),('weekday',dates.dayofweek/7)]:
        frame[name+'_sin']=np.sin(2*np.pi*phase);frame[name+'_cos']=np.cos(2*np.pi*phase)
    return frame


def run_calendar_ablation(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--challenger-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);args.trials=1;args.timeout=1
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');book=labels.build_label_book(index)
    frame=labels.relabel_cohort(frames[20],book,'vol_1sigma')
    info,variants,_,_=information.prepare_information(args)
    extra=[c for c in info if c not in frame]
    frame=frame.merge(info[['Date']+extra],on='Date',how='left',validate='one_to_one',sort=False)
    calendar=calendar_features(index.Date);calendar_names=[c for c in calendar if c!='Date']
    frame=frame.merge(calendar,on='Date',validate='one_to_one',sort=False)
    density_frame,density_jobs,_,density_plan=density.prepare_return_distribution(args)
    density_frame=labels.relabel_cohort(density_frame,book,'vol_1sigma').merge(calendar,on='Date',validate='one_to_one',sort=False)
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    choices=json.loads((args.challenger_dir/'inner_selection.json').read_text())
    selected_names={o['fold']:next(j['names'] for n,j in variants if n==o['chosen']) for o in choices}
    challenger=pd.read_csv(args.challenger_dir/'inner_selected_blend_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],challenger[key])
    risk=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date'])
    selected=np.empty((len(base),3));paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',args.challenger_dir/'inner_selection.json',args.challenger_dir/'inner_selected_blend_predictions.csv',old/'risk_predictions.csv']
    for choice in choices:
        path=args.challenger_dir/(choice['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        mask=base.outer_fold.eq(choice['fold']).to_numpy();selected[mask]=rows.loc[mask,experts.PROBS].to_numpy()
    old_classifier=.5*(selected+risk[experts.PROBS].to_numpy())
    old_densities=[]
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[density.BASE_PROBS].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_densities.append(score)
    old_density=np.mean(old_densities,axis=0)
    np.testing.assert_allclose(.5*old_classifier+.5*old_density,challenger[experts.PROBS],atol=1e-12,rtol=1e-12)
    plan.update(mode='calendar_seasonality_ablation_DEVELOPMENT',optuna=None,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},new_features=calendar_names,
        primary='calendar_full: .5 calendar-augmented information/risk classifier + .5 calendar-augmented expanding raw/normalized density',
        secondary='calendar_regularized: equal incumbent/calendar_full scores; no outer feature or weight selection',
        parameters='Original classifier per-fold params and quantile specification unchanged. Original information feature choices frozen; only six calendar features added.',
        timing='Month, day-of-month and weekday sine/cosine from current decision date; no year, absolute timestamp, future prices or future calendar sessions.',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, MCC gain, >=3 wins; paired20/60 lower>0 for provisional evidence.',
        caveat='Seasonality is a hypothesis, not assumed financial predictability. Same repeatedly inspected history; no independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_calendar'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    parts=[]
    for job in jobs:
        group=job['group'];records=[];audits=[]
        for outer in job['folds']:
            params=next(r['best_params'] for r in parent['classifier_parameters'][group] if r['outer_fold']==outer['fold'])
            names=(selected_names[outer['fold']] if group=='trend' else job['names'])+calendar_names
            for number,block in enumerate(outer['blocks'],1):
                train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured calendar classifier')
                model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=params),train,names)
                score=model.predict_proba(valid[names].to_numpy(dtype=np.float32))
                rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
                rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),features=names))
            pd.concat(records,ignore_index=True).to_csv(output/(group+'_scores.csv'),index=False)
            print(group+' fold '+str(outer['fold'])+' complete',flush=True)
        (output/(group+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
        rows=pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        parts.append(rows[experts.PROBS].to_numpy())
    new_classifier=np.mean(parts,axis=0);densities=[]
    job=density_jobs['expanding'];names=job['names']+calendar_names
    for normalized in [False,True]:
        target='normalized' if normalized else 'raw';records=[];audits=[]
        for outer in job['folds']:
            for number,block in enumerate(outer['blocks'],1):
                train,valid=density_frame.iloc[block['train']],density_frame.iloc[block['validation']]
                _,points,_=density.fit_return_quantiles(train,valid,names,normalized,density_plan['specification'])
                sigma=valid.horizon_sigma.to_numpy();prior=np.bincount(train.label,minlength=3)/len(train)
                mass=dynamic_quantile_mass(points,density_plan['specification']['quantile_atom_weights'],-sigma,sigma)
                score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=score
                rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                audits.append(dict(fold=outer['fold'],block=number,n_train=len(train),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date())))
            pd.concat(records,ignore_index=True).to_csv(output/(target+'_scores.csv'),index=False)
            (output/(target+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
            print(target+' density fold '+str(outer['fold'])+' complete',flush=True)
        rows=pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        densities.append(rows[experts.PROBS].to_numpy())
    new_density=np.mean(densities,axis=0);full=.5*new_classifier+.5*new_density
    matrices=dict(incumbent=challenger[experts.PROBS].to_numpy(),calendar_full=full,
        calendar_regularized=.5*challenger[experts.PROBS].to_numpy()+.5*full,
        calendar_classifier_only=.5*new_classifier+.5*old_density,calendar_density_only=.5*old_classifier+.5*new_density)
    finish_research_study(base,matrices,output,['calendar_full','calendar_regularized'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_calendar_ablation()
