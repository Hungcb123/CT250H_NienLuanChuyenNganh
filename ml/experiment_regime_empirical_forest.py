"""Fixed empirical leaf-return density ablation, same dynamic target/cohort.

Regress continuous future log returns, then use the mature training return
distribution in each reached leaf. No target-dependent forest hyperparameter
search or outer ensemble selection. Research scores are not calibrated odds.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT = Path(__file__).resolve().parent
CALIBRATION = ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z'


def empirical_leaf_mass(train_leaves, valid_leaves, returns, low, high):
    """Equal tree mixture, uniform mature observations within each reached leaf."""
    train_leaves = np.asarray(train_leaves)
    valid_leaves = np.asarray(valid_leaves)
    returns = np.asarray(returns, dtype=float)
    low, high = np.asarray(low, dtype=float), np.asarray(high, dtype=float)
    if (train_leaves.ndim != 2 or valid_leaves.ndim != 2
            or train_leaves.shape[1] != valid_leaves.shape[1]
            or train_leaves.shape[0] != len(returns)
            or low.shape != (len(valid_leaves),) or high.shape != low.shape
            or train_leaves.shape[1] == 0 or not np.isfinite(returns).all()
            or not np.isfinite(low).all() or not np.isfinite(high).all()
            or (low > high).any()):
        raise ValueError('Invalid leaf distribution inputs')
    mass = np.zeros((len(valid_leaves), 3))
    for tree in range(train_leaves.shape[1]):
        for leaf in np.unique(valid_leaves[:, tree]):
            ids = np.flatnonzero(valid_leaves[:, tree] == leaf)
            observed = np.sort(returns[train_leaves[:, tree] == leaf])
            if not len(observed):
                raise ValueError('Reached leaf has no mature observations')
            bear = np.searchsorted(observed, low[ids], side='left')/len(observed)
            bull = 1-np.searchsorted(observed, high[ids], side='right')/len(observed)
            mass[ids] += np.column_stack([bear, 1-bear-bull, bull])
    return np.maximum(mass/train_leaves.shape[1], 0.)


def run_empirical_forest_density(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path, default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir', type=Path, default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    base, classifier, old_density, index, paths = load_seed_components(CALIBRATION/'matched_robust_predictions.csv')
    frame, jobs, _, plan = density.prepare_return_distribution(args)
    market, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame = labels.relabel_cohort(frame, labels.build_label_book(market), 'vol_1sigma')
    selection_path = CALIBRATION/'selection.json'
    selections = json.loads(selection_path.read_text())
    anchors = {}
    for item in selections:
        if pd.Timestamp(item['latest_tuning_label_end']) >= pd.Timestamp(item['outer_boundary']):
            raise ValueError('Unmatured anchor selection')
        anchors[item['fold']] = GRID[item['chosen']['robust']]
    paths += [Path(__file__), ROOT/'regime_component_archive.py', ROOT/'regime_research_evaluation.py',
              ROOT/'experiment_regime_matched_calibration.py', ROOT/'experiment_regime_forecast_smoothing.py', selection_path]
    params = dict(n_estimators=300, max_depth=6, min_samples_leaf=30,
                  max_features=.7, n_jobs=2, random_state=42)
    plan.update(mode='empirical_leaf_return_density_DEVELOPMENT', optuna=None,
        reference_labels=plan['labels'], labels={'20':dict(policy='vol_1sigma', k=1., lookback=20, horizon=20, ddof=1, equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        parameters=params, families=['RandomForestRegressor', 'ExtraTreesRegressor'],
        density='Equal raw/volatility-normalized regression forests; uniform all mature training observations in each reached leaf, equal tree mixture. Raw thresholds use prediction-day known sigma; normalized thresholds +/-1. Strict outside thresholds, equality neutral. RF bootstrap affects tree splits, not empirical leaf observation multiplicity.',
        fusion='Keep pre-existing per-outer robust inner anchors. Primary: replace half old density with new forest density, same fusion temperatures/current-EMA5 rule. Full replacement diagnostic. No outer choice.',
        maturity='Expanding windows, refit63 market sessions; every training target label_end_date strictly precedes prediction start.',
        caveat='Repeatedly inspected historical development; no independent confirmation, calibrated-probability or deployment claim.',
        official_api='https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html')
    output = args.output_dir or ROOT/'reports/regime_empirical_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('Output: '+str(output.resolve()), flush=True)
    job = jobs['expanding']; forests = {}; audits = []
    for family in ['RandomForest', 'ExtraTrees']:
        parts = []
        for normalized in [False, True]:
            records = []
            for outer in job['folds']:
                for number, block in enumerate(outer['blocks'], 1):
                    train, valid = frame.iloc[block['train']], frame.iloc[block['validation']]
                    if train.label_end_date.max() >= valid.Date.min():
                        raise ValueError('Unmatured forest return')
                    x = train[job['names']].to_numpy(dtype=np.float32)
                    xv = valid[job['names']].to_numpy(dtype=np.float32)
                    target = train.future_log_return.to_numpy()
                    sigma = valid.horizon_sigma.to_numpy()
                    if normalized:
                        target = target/train.horizon_sigma.to_numpy()
                        sigma = np.ones(len(valid))
                    cls = RandomForestRegressor if family == 'RandomForest' else ExtraTreesRegressor
                    model = cls(**params).fit(x, target)
                    mass = empirical_leaf_mass(model.apply(x), model.apply(xv), target, -sigma, sigma)
                    prior = np.bincount(train.label, minlength=3)/len(train)
                    score = mass/prior
                    score /= score.sum(axis=1, keepdims=True)
                    rows = valid[['Date','label_end_date','label','future_return']].copy()
                    rows[['p_bear','p_side','p_bull']] = score
                    rows['outer_fold'], rows['refit_block'] = outer['fold'], number
                    records.append(rows)
                    audits.append(dict(family=family, normalized=normalized, fold=outer['fold'], block=number,
                        latest_label_end=str(train.label_end_date.max().date()), prediction_start=str(valid.Date.min().date()), n_train=len(train)))
                print(f'{family} normalized={normalized} fold{outer["fold"]} complete', flush=True)
            rows = pd.concat(records, ignore_index=True)
            for field in ['Date','label_end_date','label','outer_fold']:
                np.testing.assert_array_equal(base[field], rows[field])
            rows.to_csv(output/f'{family}_{"normalized" if normalized else "raw"}_scores.csv', index=False)
            parts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
        forests[family] = np.mean(parts, axis=0)
    (output/'timing_audit.json').write_text(json.dumps(audits, indent=2)+'\n')
    def combine(d):
        raw = np.empty_like(d)
        for fold, coefficients in anchors.items():
            mask = base.outer_fold.eq(fold).to_numpy()
            raw[mask] = fused_scores(classifier[mask], d[mask], coefficients)
        return .5*raw+.5*causal_forecast_ema(base.Date, raw, index.Date, 5)
    incumbent = combine(old_density)
    np.testing.assert_allclose(incumbent, base[['p_bear','p_side','p_bull']], atol=1e-12, rtol=1e-12)
    matrices = dict(incumbent=incumbent)
    for family, d in forests.items():
        matrices[family+'_shrink'] = combine(.5*old_density+.5*d)
        matrices[family+'_replace_diagnostic'] = combine(d)
    finish_research_study(base, matrices, output, [family+'_shrink' for family in forests])
    print('Done. No deployment. '+str(output.resolve()), flush=True)
    return output


if __name__ == '__main__':
    run_empirical_forest_density()
