"""Matched vs extended CLOSE-only analog history; fixed half-component ablation.

Separate dropping ETF distance features from adding earlier/missing-ETF history.
Same dynamic labels,1560 dates,k100,views and all non-analog components fixed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_analog_density import analog_return_mass, COMPACT
from experiment_regime_extended_forest import extended_feature_history
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from regime_research_evaluation import finish_research_study


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT/'reports/regime_runtime_parity/20261019T090001_796250Z'
ANALOG = ROOT/'reports/regime_analog_density/20261019T071721_721598Z'


def run_close_history_analog(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path, default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir', type=Path, default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    paths = [Path(__file__), ROOT/'experiment_regime_analog_density.py', ROOT/'experiment_regime_extended_forest.py',
             ROOT/'regime_research_evaluation.py', ROOT/'experiment_regime_forecast_smoothing.py',
             ROOT/'experiment_regime_matched_calibration.py', FIXTURE/'historical_component_fixture.npz', FIXTURE/'checksums.json']
    for name, digest in json.loads((FIXTURE/'sources.json').read_text()).items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Archived source changed: '+name)
        paths.append(Path(name))
    for name, digest in json.loads((FIXTURE/'checksums.json').read_text()).items():
        if hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Changed component fixture')
    with np.load(FIXTURE/'historical_component_fixture.npz', allow_pickle=False) as archive:
        fixed = {name: archive[name] for name in archive.files}
    base = pd.read_csv(ANALOG/'analog_shrink_predictions.csv', parse_dates=['Date', 'label_end_date'])
    base['majority'] = base.baseline_prediction
    np.testing.assert_array_equal(fixed['dates'], base.Date.dt.strftime('%Y-%m-%d'))
    original, jobs, _, plan = density.prepare_return_distribution(args)
    index, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    etf, _ = exp.base.load_market_data(args.data_dir/'E1VFVN30.csv')
    original = labels.relabel_cohort(original, labels.build_label_book(index), 'vol_1sigma')
    # The full-calendar helper preserves unavailable ETF features as NaN. These
    # distance views select only CLOSE fields; never replace missing ETF prices.
    extended, _ = extended_feature_history(index, etf)
    views = dict(compact=[n for n in COMPACT if not n.startswith('ETF_')],
                 full=[n for n in jobs['expanding']['names'] if not n.startswith('ETF_')])
    matched = extended.set_index('Date').loc[original.Date]
    np.testing.assert_allclose(matched[views['full']], original[views['full']], atol=1e-12, rtol=0)
    for name in ['label', 'label_end_date']:
        np.testing.assert_array_equal(matched[name], original[name])
    np.testing.assert_allclose(matched.future_log_return, original.future_log_return, atol=1e-12, rtol=0)
    paths += [ANALOG/'analog_shrink_predictions.csv', args.data_dir/'E1VFVN30.csv']
    plan.update(mode='close_only_matched_extended_analog_DEVELOPMENT', optuna=None,
                source_hashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in dict.fromkeys(paths)},
                reference_labels=plan['labels'], labels={'20': dict(policy='vol_1sigma', k=1, lookback=20, horizon=20, ddof=1)},
                feature_views=views, neighbors=100, original_rows=len(original), extended_rows=len(extended),
                primary=['matched_half', 'extended_half'],
                intervention='Replace HALF the existing25% analog component with a new equal compact/full x raw/normalized analog. All other components/anchors/current-EMA5 fixed. Two comparisons only; no outer weight search.',
                matched='Original mature training dates and priors, remove4 ETF full-view fields and1 compact field.',
                extended='Same close-only feature views; all mature close-eligible history since2010 including missing-ETF sessions. Scale and class priors learned separately on this training set.',
                hypothesis='Older state analogs may help rare transitions; matched control distinguishes distance-feature change from history change.',
                caveat='Historical development repeatedly inspected, no independent holdout, acceptance or deployment claim.')
    output = args.output_dir or ROOT/'reports/regime_close_history_analog'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('Output: '+str(output), flush=True)
    new = {}; audits = []
    for policy in ['matched', 'extended']:
        parts = []
        for view, names in views.items():
            for normalized in [False, True]:
                records = []
                for outer in jobs['expanding']['folds']:
                    for number, block in enumerate(outer['blocks'], 1):
                        valid = original.iloc[block['validation']]
                        boundary = valid.Date.min()
                        train = (original.iloc[block['train']] if policy == 'matched' else
                                 extended.loc[(extended.Date < boundary) & (extended.label_end_date < boundary)])
                        if train.label_end_date.max() >= boundary:
                            raise ValueError('Unmatured analog atom')
                        atoms = train.future_log_return.to_numpy()
                        sigma = valid.horizon_sigma.to_numpy()
                        if normalized:
                            atoms = atoms/train.horizon_sigma.to_numpy(); sigma = np.ones(len(valid))
                        mass, detail = analog_return_mass(train[names], valid[names], atoms, -sigma, sigma)
                        prior = np.bincount(train.label, minlength=3)/len(train)
                        if (prior <= 0).any():
                            raise ValueError('Missing mature prior class')
                        score = mass/prior; score /= score.sum(axis=1, keepdims=True)
                        row = valid[['Date', 'label_end_date', 'label', 'future_return']].copy()
                        row[['p_bear', 'p_side', 'p_bull']] = score
                        row['outer_fold'], row['refit_block'] = outer['fold'], number
                        records.append(row)
                        audits.append(dict(policy=policy, view=view, normalized=normalized, fold=outer['fold'],
                                           block=number, n_train=len(train), earliest_train=str(train.Date.min().date()),
                                           latest_label_end=str(train.label_end_date.max().date()),
                                           prediction_start=str(boundary.date()), **detail))
                rows = pd.concat(records, ignore_index=True)
                for key in ['Date', 'label_end_date', 'label', 'outer_fold']:
                    np.testing.assert_array_equal(rows[key], base[key])
                rows.to_csv(output/f'{policy}_{view}_{"normalized" if normalized else "raw"}_scores.csv', index=False)
                parts.append(rows[['p_bear', 'p_side', 'p_bull']].to_numpy())
        new[policy] = np.mean(parts, axis=0)
        print(policy+' analog history complete', flush=True)
    (output/'timing_audit.json').write_text(json.dumps(audits, indent=2)+'\n')
    basic = .5*fixed['quantile']+.25*fixed['forest']+.25*fixed['magnitude']
    def compose(analog):
        d = .75*basic+.25*analog
        raw = np.empty_like(d)
        for i in range(len(base)):
            raw[i] = fused_scores(fixed['classifier'][i:i+1], d[i:i+1], fixed['parameters'][i])[0]
        return .5*raw+.5*causal_forecast_ema(base.Date, raw, index.Date, 5)
    incumbent = compose(fixed['analog'])
    np.testing.assert_allclose(incumbent, base[['p_bear', 'p_side', 'p_bull']], atol=1e-12, rtol=1e-12)
    finish_research_study(base, dict(incumbent=incumbent,
                          matched_half=compose(.5*fixed['analog']+.5*new['matched']),
                          extended_half=compose(.5*fixed['analog']+.5*new['extended'])), output,
                          ['matched_half', 'extended_half'])
    print('Done. Same task/development only. '+str(output), flush=True)
    return output


if __name__ == '__main__':
    run_close_history_analog()
