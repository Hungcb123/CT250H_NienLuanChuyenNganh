"""Pre-existing inner-selected market context for empirical return forests.

Same dynamic target/evaluation cohort. Forest parameters and source timing
unchanged. Missing information stays NaN; no price imputation or outer search.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_information as information
import experiment_regime_return_distribution as density
from experiment_regime_empirical_forest import empirical_leaf_mass, CALIBRATION
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
FOREST=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
MAGNITUDE=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
INFORMATION=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z'


def run_information_forest_density(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv);args.trials=1;args.timeout=1
    base,classifier,quantile,calendar,paths=load_seed_components(MAGNITUDE/'magnitude_shrink_predictions.csv')
    frame,jobs,_,plan=density.prepare_return_distribution(args)
    market,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frame,labels.build_label_book(market),'vol_1sigma')
    context,variants,context_plan,_=information.prepare_information(args)
    extra=[name for name in context if name not in frame]
    frame=frame.merge(context[['Date']+extra],on='Date',how='left',validate='one_to_one',sort=False)
    names_by_group={name:job['names'] for name,job in variants}
    selected=json.loads((INFORMATION/'inner_selection.json').read_text())
    for item in selected:
        if pd.Timestamp(item['latest_tuning_label_end'])>=pd.Timestamp(item['outer_boundary']):raise ValueError('Unmatured context choice')
    chosen={item['fold']:item['chosen'] for item in selected}
    old_parts=[]
    for folder,prefix in [(FOREST,'RandomForest_'),(MAGNITUDE,'')]:
        parts=[]
        for target in ['raw','normalized']:
            path=folder/f'{prefix}{target}_scores.csv';paths.append(path)
            rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        old_parts.append(np.mean(parts,axis=0))
    old_forest=np.mean(old_parts,axis=0);old_density=.5*quantile+.5*old_forest
    params=json.loads((FOREST/'plan.json').read_text())['parameters']
    anchors=json.loads((CALIBRATION/'selection.json').read_text())
    paths += [Path(__file__),ROOT/'experiment_regime_information.py',ROOT/'experiment_regime_empirical_forest.py',
        ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'experiment_regime_matched_calibration.py',
        ROOT/'regime_component_archive.py',ROOT/'regime_research_evaluation.py',INFORMATION/'inner_selection.json',
        INFORMATION/'plan.json',CALIBRATION/'selection.json']
    original=json.loads((INFORMATION/'plan.json').read_text())
    for name,digest in original['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Context source changed: '+name)
        paths.append(Path(name))
    plan.update(mode='trusted_context_empirical_forest_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,
        feature_names=names_by_group,context_choices=chosen,context_source_plan=context_plan,
        architectures=['mean','magnitude'],targets=['raw','normalized'],
        missing='Native sklearn1.7 RandomForest NaN branches; preserve absent/conflicted fields. No feature/price filling or dropped evaluation rows.',
        primary='context_shrink: .75 existing density+.25 new context forest density, average4 mean/magnitude x raw/normalized forests.',
        secondary='context_forest_replace: .5 quantile+.5 new context forest density. Combined all-information variant diagnostic only. Existing classifier/inner anchors/current-EMA5 fixed.',
        maturity='Expanding, refit63. All target endpoints before block start. Context choice known at outer start; VIX observation+2 calendar days, stale<=7; source disagreements remain missing.',
        caveat='Context group originally chosen for classifier, not forest. No outer feature selection. Vintage/release timestamps not independently certified; repeatedly inspected historical development, no independent test/deployment.',
        official_missing_api='https://scikit-learn.org/1.7/modules/impute.html#estimators-that-handle-nan-values')
    output=args.output_dir or ROOT/'reports/regime_information_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    frame[['Date','VIX_ObservationDate','VIX_AvailableDate']].to_csv(output/'vix_timing.csv',index=False)
    print('Output: '+str(output.resolve()),flush=True)
    audits=[];densities={}
    for treatment in ['selected','combined']:
        parts=[]
        for architecture in ['mean','magnitude']:
            for normalized in [False,True]:
                records=[]
                for outer in jobs['expanding']['folds']:
                    group=chosen[outer['fold']] if treatment=='selected' else 'combined'
                    names=names_by_group[group]
                    for number,block in enumerate(outer['blocks'],1):
                        train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                        if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured context forest')
                        y=train.future_log_return.to_numpy();sigma=valid.horizon_sigma.to_numpy()
                        if normalized:y=y/train.horizon_sigma.to_numpy();sigma=np.ones(len(valid))
                        target=y
                        if architecture=='magnitude':
                            target=np.column_stack([y,np.abs(y)]);target=(target-target.mean(axis=0))/target.std(axis=0,ddof=1)
                        x=train[names].to_numpy(dtype=np.float32);v=valid[names].to_numpy(dtype=np.float32)
                        if np.isinf(x).any() or np.isinf(v).any():raise ValueError('Infinite context feature')
                        model=RandomForestRegressor(**params).fit(x,target)
                        mass=empirical_leaf_mass(model.apply(x),model.apply(v),y,-sigma,sigma)
                        prior=np.bincount(train.label,minlength=3)/len(train)
                        score=mass/prior;score/=score.sum(axis=1,keepdims=True)
                        rows=valid[['Date','label_end_date','label','future_return']].copy();rows[['p_bear','p_side','p_bull']]=score
                        rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                        audits.append(dict(treatment=treatment,architecture=architecture,normalized=normalized,group=group,
                            fold=outer['fold'],refit_block=number,n_train=len(train),n_features=len(names),
                            latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),
                            train_nan_fraction=float(np.isnan(x).mean()),valid_nan_fraction=float(np.isnan(v).mean())))
                    print(f'{treatment} {architecture} normalized={normalized} fold{outer["fold"]} complete',flush=True)
                rows=pd.concat(records,ignore_index=True)
                for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
                rows.to_csv(output/f'{treatment}_{architecture}_{"normalized" if normalized else "raw"}_scores.csv',index=False)
                parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        densities[treatment]=np.mean(parts,axis=0)
    # On the fold whose pre-existing inner choice was control, the selected
    # treatment must exactly reproduce all four original forest components.
    control_mask=base.outer_fold.isin([fold for fold,group in chosen.items() if group=='control']).to_numpy()
    np.testing.assert_allclose(densities['selected'][control_mask],old_forest[control_mask],atol=1e-12,rtol=1e-12)
    (output/'control_parity.json').write_text(json.dumps(dict(rows=int(control_mask.sum()),max_error=float(np.abs(densities['selected'][control_mask]-old_forest[control_mask]).max())),indent=2)+'\n')
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    def combine(d):
        raw=np.empty_like(d)
        for outer in anchors:
            mask=base.outer_fold.eq(outer['fold']).to_numpy()
            raw[mask]=fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent=combine(old_density)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    finish_research_study(base,dict(incumbent=incumbent,context_shrink=combine(.75*old_density+.25*densities['selected']),
        context_forest_replace=combine(.5*quantile+.5*densities['selected']),
        combined_context_diagnostic=combine(.75*old_density+.25*densities['combined'])),output,['context_shrink','context_forest_replace'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_information_forest_density()
