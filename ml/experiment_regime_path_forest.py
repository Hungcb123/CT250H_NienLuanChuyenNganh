"""Auxiliary future-path supervision for forests; original endpoint labels fixed.

Only training targets see the future path. Serving features remain completed-close
inputs. Fixed half replacement of shock forest component, no outer weight search.
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
from experiment_regime_directional import directional_features
from experiment_regime_empirical_forest import empirical_leaf_mass
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from regime_research_evaluation import finish_research_study


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT/'reports/regime_runtime_parity/20261019T090001_796250Z'
SHOCK = ROOT/'reports/regime_shock_forest/20261019T072038_455776Z'


def future_path_training_targets(index, horizon=20):
    """Min/max log CLOSE relative to origin over a COMPLETE future H-session path."""
    if horizon < 1:
        raise ValueError('Positive path horizon required')
    price = index.Price.astype(float)
    paths = np.column_stack([np.log(price.shift(-h)/price) for h in range(1, horizon+1)])
    # np.min/max propagates NaN: never label an incomplete final path.
    return pd.DataFrame(dict(Date=index.Date, future_path_min=np.min(paths, axis=1),
                             future_path_max=np.max(paths, axis=1)))


def run_path_supervised_forest(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path, default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir', type=Path, default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    for name, digest in json.loads((FIXTURE/'sources.json').read_text()).items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Pinned source changed: '+name)
    for name, digest in json.loads((FIXTURE/'checksums.json').read_text()).items():
        if hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Fixture checksum changed')
    with np.load(FIXTURE/'historical_component_fixture.npz', allow_pickle=False) as archive:
        fixed = {name: archive[name] for name in archive.files}
    base = pd.read_csv(SHOCK/'shock_shrink_predictions.csv', parse_dates=['Date', 'label_end_date'])
    base['majority'] = base.baseline_prediction
    np.testing.assert_array_equal(fixed['dates'], base.Date.dt.strftime('%Y-%m-%d'))
    frame, jobs, _, plan = density.prepare_return_distribution(args)
    index, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame = labels.relabel_cohort(frame, labels.build_label_book(index), 'vol_1sigma')
    extras = directional_features(index)
    names = jobs['expanding']['names']+[n for n in extras if n != 'Date']
    frame = frame.merge(extras, on='Date', how='left', validate='one_to_one', sort=False)
    frame = frame.merge(future_path_training_targets(index), on='Date', how='left', validate='one_to_one', sort=False)
    if any(n.startswith('future_') for n in names):
        raise ValueError('Future target in serving features')
    params = json.loads((SHOCK/'plan.json').read_text())['parameters']
    paths = [Path(__file__), ROOT/'experiment_regime_empirical_forest.py', ROOT/'experiment_regime_directional.py',
             ROOT/'regime_research_evaluation.py', ROOT/'experiment_regime_forecast_smoothing.py',
             ROOT/'experiment_regime_matched_calibration.py', FIXTURE/'sources.json', FIXTURE/'checksums.json',
             FIXTURE/'historical_component_fixture.npz', SHOCK/'shock_shrink_predictions.csv', SHOCK/'plan.json']
    plan.update(mode='auxiliary_path_supervision_empirical_forest_DEVELOPMENT', optuna=None,
                reference_labels=plan['labels'], labels={'20': dict(policy='vol_1sigma', k=1, lookback=20, horizon=20, ddof=1)},
                source_hashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                features=names, parameters=params, targets=['end_return', 'abs_end_return', 'min_path_log_return', 'max_path_log_return'],
                target_scaling='Raw or origin-sigma normalized, then TRAIN-only mean/std per output. Equal raw/normalized forests. Return atoms remain endpoint returns.',
                primary='path_shrink: replace half25% shock component with path-supervised forest density, all other components/anchors/EMA fixed.',
                maturity='ALL20 future closes of every training path must be known strictly before refit. No path target used as a prediction input; same1560 dates and endpoint labels.',
                hypothesis='Auxiliary path shape may partition similar endpoint returns by directional risk; no new information source or evaluation target.',
                caveat='Historical development reused, no independent validation, probability certification or deployment.')
    output = args.output_dir or ROOT/'reports/regime_path_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('Output: '+str(output), flush=True)
    audits = []; parts = []
    for normalized in [False, True]:
        records = []
        for outer in jobs['expanding']['folds']:
            for number, block in enumerate(outer['blocks'], 1):
                train, valid = frame.iloc[block['train']], frame.iloc[block['validation']]
                if train.label_end_date.max() >= valid.Date.min():
                    raise ValueError('Unmatured complete path target')
                y = train.future_log_return.to_numpy()
                extra = train[['future_path_min', 'future_path_max']].to_numpy()
                threshold = valid.horizon_sigma.to_numpy()
                if normalized:
                    y = y/train.horizon_sigma.to_numpy()
                    extra = extra/train.horizon_sigma.to_numpy()[:, None]
                    threshold = np.ones(len(valid))
                target = np.column_stack([y, np.abs(y), extra])
                if not np.isfinite(target).all():
                    raise ValueError('Incomplete future path used in training')
                target = (target-target.mean(axis=0))/target.std(axis=0, ddof=1)
                x = train[names].to_numpy(dtype=np.float32)
                v = valid[names].to_numpy(dtype=np.float32)
                model = RandomForestRegressor(**params).fit(x, target)
                mass = empirical_leaf_mass(model.apply(x), model.apply(v), y, -threshold, threshold)
                prior = np.bincount(train.label, minlength=3)/len(train)
                score = mass/prior; score /= score.sum(axis=1, keepdims=True)
                row = valid[['Date', 'label_end_date', 'label', 'future_return']].copy()
                row[['p_bear', 'p_side', 'p_bull']] = score
                row['outer_fold'], row['refit_block'] = outer['fold'], number
                records.append(row)
                audits.append(dict(normalized=normalized, fold=outer['fold'], block=number, n_train=len(train),
                                   latest_label_end=str(train.label_end_date.max().date()),
                                   prediction_start=str(valid.Date.min().date()), target_columns=4))
            print(f'Path normalized={normalized} fold{outer["fold"]} complete', flush=True)
        rows = pd.concat(records, ignore_index=True)
        for key in ['Date', 'label_end_date', 'label', 'outer_fold']:
            np.testing.assert_array_equal(rows[key], base[key])
        rows.to_csv(output/f'{"normalized" if normalized else "raw"}_scores.csv', index=False)
        parts.append(rows[['p_bear', 'p_side', 'p_bull']].to_numpy())
    (output/'timing_audit.json').write_text(json.dumps(audits, indent=2)+'\n')
    basic = .5*fixed['quantile']+.25*fixed['forest']+.25*fixed['magnitude']
    analog = .75*basic+.25*fixed['analog']
    def compose(shock):
        d = .75*analog+.25*shock
        raw = np.empty_like(d)
        for i in range(len(base)):
            raw[i] = fused_scores(fixed['classifier'][i:i+1], d[i:i+1], fixed['parameters'][i])[0]
        return .5*raw+.5*causal_forecast_ema(base.Date, raw, index.Date, 5)
    incumbent = compose(fixed['shock'])
    np.testing.assert_allclose(incumbent, base[['p_bear', 'p_side', 'p_bull']], atol=1e-12, rtol=1e-12)
    finish_research_study(base, dict(incumbent=incumbent,
                          path_shrink=compose(.5*fixed['shock']+.5*np.mean(parts, axis=0))), output, ['path_shrink'])
    print('Done. Fixed endpoint evaluation, no deployment. '+str(output), flush=True)
    return output


if __name__ == '__main__':
    run_path_supervised_forest()
