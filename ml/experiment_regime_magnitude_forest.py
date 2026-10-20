"""Empirical density forests jointly partitioning return and return magnitude.

One fixed multi-output RF specification, no outer parameter or weight search.
Only split-learning targets change; actual three-class labels stay unchanged.
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
import experiment_regime_return_distribution as density
from experiment_regime_empirical_forest import empirical_leaf_mass, CALIBRATION
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT = Path(__file__).resolve().parent
FOREST = ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'


def run_magnitude_forest_density(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args = parser.parse_args(argv)
    base, classifier, old_density, calendar, paths = load_seed_components(FOREST/'RandomForest_shrink_predictions.csv')
    frame, jobs, _, plan = density.prepare_return_distribution(args)
    market, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame = labels.relabel_cohort(frame,labels.build_label_book(market),'vol_1sigma')
    params = json.loads((FOREST/'plan.json').read_text())['parameters']
    selection = json.loads((CALIBRATION/'selection.json').read_text())
    old_parts = []
    for target in ['raw','normalized']:
        path = FOREST/f'RandomForest_{target}_scores.csv'; paths.append(path)
        rows = pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:
            np.testing.assert_array_equal(base[key],rows[key])
        old_parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    forest_density = np.mean(old_parts,axis=0)
    paths += [Path(__file__),ROOT/'experiment_regime_empirical_forest.py',ROOT/'regime_component_archive.py',
        ROOT/'experiment_regime_forecast_smoothing.py',ROOT/'experiment_regime_matched_calibration.py',
        ROOT/'regime_research_evaluation.py',CALIBRATION/'selection.json']
    plan.update(mode='joint_return_magnitude_density_DEVELOPMENT',optuna=None,
        reference_labels=plan['labels'],labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},parameters=params,
        auxiliary_targets='For raw or volatility-normalized future log return z: two split targets [z,abs(z)], center each and divide by its mature-training sample std(ddof1). No clipping. Native multi-output RF. Leaf empirical distributions still use ORIGINAL scalar z.',
        primary='magnitude_shrink: keep classifier + chosen anchors/EMA5, density .5 old quantiles+.25 old mean-forest+.25 new multi-output forest.',
        secondary='magnitude_replace: density .5 old quantiles+.5 multi-output forest. Fixed weights, no outer choice.',
        maturity='Expanding, refit63 market sessions. Every fitted target endpoint strictly precedes prediction start.',
        official_api='https://scikit-learn.org/stable/modules/tree.html#multi-output-problems',
        caveat='Hypothesis: squared-error splits for mean return alone may miss conditional return magnitude. No guarantee; repeatedly inspected development, no independent confirmation/deployment.')
    output = args.output_dir or ROOT/'reports/regime_magnitude_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False); (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    job = jobs['expanding']; parts = []; audits = []
    for normalized in [False,True]:
        records = []
        for outer in job['folds']:
            for number,block in enumerate(outer['blocks'],1):
                train,valid = frame.iloc[block['train']],frame.iloc[block['validation']]
                if train.label_end_date.max() >= valid.Date.min():
                    raise ValueError('Unmatured magnitude target')
                target = train.future_log_return.to_numpy(); sigma = valid.horizon_sigma.to_numpy()
                if normalized:
                    target = target/train.horizon_sigma.to_numpy(); sigma = np.ones(len(valid))
                split_targets = np.column_stack([target,np.abs(target)])
                center = split_targets.mean(axis=0); scale = split_targets.std(axis=0,ddof=1)
                if not np.isfinite(scale).all() or (scale<=0).any():
                    raise ValueError('Invalid mature split-target scale')
                x = train[job['names']].to_numpy(dtype=np.float32); xv = valid[job['names']].to_numpy(dtype=np.float32)
                model = RandomForestRegressor(**params).fit(x,(split_targets-center)/scale)
                mass = empirical_leaf_mass(model.apply(x),model.apply(xv),target,-sigma,sigma)
                prior = np.bincount(train.label,minlength=3)/len(train)
                score = mass/prior; score /= score.sum(axis=1,keepdims=True)
                rows = valid[['Date','label_end_date','label','future_return']].copy()
                rows[['p_bear','p_side','p_bull']] = score; rows['outer_fold'],rows['refit_block'] = outer['fold'],number
                records.append(rows)
                audits.append(dict(normalized=normalized,fold=outer['fold'],refit_block=number,n_train=len(train),
                    latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),
                    target_center=center.tolist(),target_scale=scale.tolist()))
            print(f'Magnitude normalized={normalized} fold{outer["fold"]} complete',flush=True)
        rows = pd.concat(records,ignore_index=True)
        for key in ['Date','label_end_date','label','outer_fold']:
            np.testing.assert_array_equal(base[key],rows[key])
        rows.to_csv(output/f'{"normalized" if normalized else "raw"}_scores.csv',index=False)
        parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    (output/'timing_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    new_density = np.mean(parts,axis=0)
    def combine(d):
        raw = np.empty_like(d)
        for outer in selection:
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):
                raise ValueError('Unmatured coefficient anchor')
            mask = base.outer_fold.eq(outer['fold']).to_numpy()
            raw[mask] = fused_scores(classifier[mask],d[mask],GRID[outer['chosen']['robust']])
        return .5*raw+.5*causal_forecast_ema(base.Date,raw,calendar.Date,5)
    incumbent = combine(.5*old_density+.5*forest_density)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    matrices = dict(incumbent=incumbent,
        magnitude_shrink=combine(.5*old_density+.25*forest_density+.25*new_density),
        magnitude_replace=combine(.5*old_density+.5*new_density))
    finish_research_study(base,matrices,output,['magnitude_shrink','magnitude_replace'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__ == '__main__':
    run_magnitude_forest_density()
