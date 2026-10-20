"""Two predeclared T+20 target definitions on fixed dates: absolute +/-5% and
one trailing-volatility unit of 20-session log return. LightGBM + trend + 3y;
historical development only. No kernel/model search, holdout scoring or export.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

import experiment_regime as exp

ROOT = Path(__file__).resolve().parent
HORIZON = 20
VOL_LOOKBACK = 20
VOL_MULTIPLIER = 1.0
POLICIES = ['fixed_5pct', 'vol_1sigma']


def label_counts(values):
    return {name: int((values == code).sum()) for code, name in enumerate(['bearish', 'sideway', 'bullish'])}


def build_label_book(index):
    """Shift on the FULL index calendar before joining any feature-filtered rows.

    Daily sigma uses 20 completed log returns at t (21 closes), ddof=1, in
    decimal units. sqrt(H) is a predeclared normalization, not an assertion
    that future conditional variance necessarily scales linearly in H.
    """
    price = index['Price'].astype(float)
    daily_sigma = np.log(price).diff().rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std(ddof=1)
    horizon_sigma = daily_sigma * np.sqrt(HORIZON)
    forward_simple = price.shift(-HORIZON) / price - 1
    forward_log = np.log(price.shift(-HORIZON) / price)
    fixed = pd.Series(pd.NA, index=index.index, dtype='Int64')
    observed = forward_simple.notna()
    fixed.loc[observed] = np.where(forward_simple[observed] < -.05, 0,
                                  np.where(forward_simple[observed] > .05, 2, 1))
    valid = np.isfinite(horizon_sigma) & (horizon_sigma > 0) & forward_log.notna()
    standardized = (forward_log / horizon_sigma.where(valid)).where(valid)
    dynamic = pd.Series(pd.NA, index=index.index, dtype='Int64')
    dynamic.loc[valid] = np.where(standardized[valid] < -VOL_MULTIPLIER, 0,
                                 np.where(standardized[valid] > VOL_MULTIPLIER, 2, 1))
    return pd.DataFrame({
        'Date': index['Date'], 'label_end_date': index['Date'].shift(-HORIZON),
        'future_return': forward_simple, 'future_log_return': forward_log,
        'fixed_label': fixed, 'vol_label': dynamic, 'daily_sigma': daily_sigma,
        'horizon_sigma': horizon_sigma, 'z_forward': standardized,
        'vol_upper_simple_threshold': np.expm1(VOL_MULTIPLIER * horizon_sigma),
        'vol_lower_simple_threshold': np.expm1(-VOL_MULTIPLIER * horizon_sigma),
    })


def relabel_cohort(frame, book, policy):
    if policy not in POLICIES:
        raise ValueError(f'Unknown label policy: {policy}')
    matched = frame[['Date']].merge(book, on='Date', how='left', validate='one_to_one', sort=False)
    if matched[['fixed_label', 'vol_label', 'label_end_date']].isna().any().any():
        raise ValueError('A label/volatility is undefined on the frozen cohort; do not silently remove dates')
    if not np.array_equal(matched['Date'].to_numpy(), frame['Date'].to_numpy()):
        raise ValueError('Label join changed date ordering')
    if not np.array_equal(matched['label_end_date'].to_numpy(), frame['label_end_date'].to_numpy()):
        raise ValueError('Raw-calendar horizon changed after feature filtering')
    np.testing.assert_allclose(matched['future_return'], frame['future_return'], rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(matched['fixed_label'].to_numpy(dtype=int), frame['label'].to_numpy(dtype=int))
    result = frame.copy()
    result['label'] = matched['fixed_label' if policy == 'fixed_5pct' else 'vol_label'].to_numpy(dtype=np.int64)
    return result


def prepare_label_experiment(args):
    fixed_args = exp.parse_args([
        '--reference-report', str(args.reference_report), '--data-dir', str(args.data_dir),
        '--base-feature-set', 'close-etf', '--feature-groups', 'trend', '--train-windows', '3y',
        '--models', 'LightGBM', '--horizons', '20', '--inner-splits', str(args.inner_splits),
        '--refit-sessions', str(args.refit_sessions), '--trials', str(args.trials), '--timeout', str(args.timeout),
        *(['--quick'] if args.quick else []),
    ])
    frames, jobs, original = exp.prepare_experiment(fixed_args)
    index, index_audit = exp.base.load_market_data(args.data_dir / 'VNINDEX.csv')
    if index_audit['sha256'] != original['input_hashes']['VNINDEX']:
        raise ValueError('VNINDEX changed while preparing the experiment')
    book = build_label_book(index)
    frame, template = frames[HORIZON], jobs[0]
    plan = {key: original[key] for key in ['reference_report', 'reference_sha256', 'input_hashes', 'optuna']}
    plan.update(
        mode='target_definition_development_study_not_final_test',
        model='LightGBM', feature_group='trend', feature_names=template['names'], train_window='3y', horizon=HORIZON,
        refit_market_sessions=args.refit_sessions, inner_splits=args.inner_splits,
        target_definitions={
            'fixed_5pct': {'return': 'simple', 'bear_below': -.05, 'bull_above': .05},
            'vol_1sigma': {'return': 'log', 'sigma': 'std of trailing completed DAILY log returns, ddof=1, decimal units',
                           'vol_lookback': VOL_LOOKBACK, 'horizon': HORIZON, 'k': VOL_MULTIPLIER,
                           'formula': 'log(P[t+20]/P[t]) / (daily_sigma[t] * sqrt(20))',
                           'bear_below_z': -VOL_MULTIPLIER, 'bull_above_z': VOL_MULTIPLIER}},
        label_encoding={'0': 'bearish (-1)', '1': 'sideway (0)', '2': 'bullish (+1)'},
        boundary_equality='sideway', frozen_validation=original['datasets'][0]['folds'],
        comparison_rule='Native F1 scores describe DIFFERENT tasks: no cross-target winner. Common risk diagnostics use actual simple return < -5% for both.',
        assumptions=[
            'Only target labels change; feature columns, sample dates, train windows, refit schedule and tuning budget are identical.',
            'Volatility thresholds depend only on prices at or before decision t, never on future returns.',
            'k=1 and lookback=20 are predeclared and are not tuned to outer validation F1 or class balance.',
            'This is endpoint volatility-adjusted labeling, NOT first-touch triple-barrier labeling.',
            'Volatility sigma is not annualized and not multiplied by 100; sqrt(20) normalizes the horizon.',
            'Each policy tunes parameters on its own purged inner training/validation labels; no outer-label tuning.',
            'Each prediction block trains only on labels whose end date is strictly before that block.',
            'No qcut, confidence threshold, new model family, independent holdout, return backtest or export.',
            'Forward returns conditional on a signal are descriptive overlapping outcomes, not portfolio profits.'],
        policies={}, errors=list(original['errors']))
    variants = []
    for policy in POLICIES:
        relabeled = relabel_cohort(frame, book, policy)
        job = copy.deepcopy(template)
        info = {'cohort_rows': len(relabeled), 'date_hash': exp.date_hash(relabeled['Date']),
                'class_counts': label_counts(relabeled['label']), 'folds': []}
        for outer in job['folds']:
            validation = np.concatenate([b['validation'] for b in outer['blocks']])
            start = relabeled['Date'].iloc[validation[0]]
            try:
                tune = exp.training_indices(relabeled, start, '3y')
                np.testing.assert_array_equal(tune, outer['tune'])
                outer['inner'] = exp.base.purged_folds(relabeled.iloc[tune].reset_index(drop=True), args.inner_splits)
                for block in outer['blocks']:
                    actual = exp.training_indices(relabeled, relabeled['Date'].iloc[block['validation'][0]], '3y')
                    np.testing.assert_array_equal(actual, block['train'])
                info['folds'].append({'fold': outer['fold'], 'n_train_at_start': len(tune),
                                      'train_class_counts': label_counts(relabeled['label'].iloc[tune]),
                                      'n_validation': len(validation),
                                      'validation_class_counts': label_counts(relabeled['label'].iloc[validation]),
                                      'validation_dates_sha256': exp.date_hash(relabeled['Date'].iloc[validation])})
            except ValueError as exc:
                plan['errors'].append(f"{policy} fold {outer['fold']}: {exc}")
        plan['policies'][policy] = info
        variants.append((policy, relabeled, job))
    matched = frame[['Date']].merge(book, on='Date', validate='one_to_one', sort=False)
    plan['vol_simple_threshold_percentiles'] = {
        column: {str(q): float(matched[column].quantile(q)) for q in [.1, .5, .9]}
        for column in ['vol_lower_simple_threshold', 'vol_upper_simple_threshold']}
    return variants, book, plan


def common_outcomes(records):
    """Same absolute-return yardstick for both policies; no trading/profit claim."""
    matrix = confusion_matrix(records['fixed_label'], records['prediction'], labels=[0, 1, 2])
    outcomes = {}
    for code, name in enumerate(['bearish', 'sideway', 'bullish']):
        returns = records.loc[records['prediction'] == code, 'future_return']
        outcomes[name] = {
            'n_samples': len(returns),
            'mean_forward_return': float(returns.mean()) if len(returns) else None,
            'median_forward_return': float(returns.median()) if len(returns) else None,
            'fraction_return_below_minus5pct': float((returns < -.05).mean()) if len(returns) else None,
            'fraction_return_above_plus5pct': float((returns > .05).mean()) if len(returns) else None,
        }
    return {'absolute_5pct_bear': exp.bear_errors(matrix), 'forward_return_by_prediction': outcomes}


def attach_label_metadata(records, book):
    columns = ['Date', 'fixed_label', 'vol_label', 'daily_sigma', 'horizon_sigma', 'z_forward',
               'vol_upper_simple_threshold', 'vol_lower_simple_threshold']
    result = records.merge(book[columns], on='Date', how='left', validate='one_to_one', sort=False)
    if result[['fixed_label', 'vol_label']].isna().any().any():
        raise ValueError('Predictions contain dates without mature labels')
    result['fixed_label'], result['vol_label'] = result['fixed_label'].astype(int), result['vol_label'].astype(int)
    return result


def write_label_summary(results, output):
    native_rows, common_rows, fold_rows, outcomes = [], [], [], []
    lines = ['# Target-definition development study', '',
             'LightGBM + close-etf/trend + 3y. Same dates, features and refits; labels differ.',
             '**Native F1 values below describe different tasks and must not be ranked against each other.**', '',
             '| Policy | Own-label mean F1 | Own-label majority F1 | Own-label MCC | Own-label worst F1 |',
             '|---|---|---|---|---|']
    for result in results:
        policy = result['label_policy']
        native_rows.append({'policy': policy, **{key: result[key] for key in ['mean_f1', 'std_f1', 'worst_f1',
                                                                           'mean_mcc', 'mean_baseline_f1', 'folds_beating_majority']}})
        common_rows.append({'policy': policy, **result['common_outcomes']['absolute_5pct_bear']})
        for name, values in result['common_outcomes']['forward_return_by_prediction'].items():
            outcomes.append({'policy': policy, 'prediction': name, **values})
        for fold, common in zip(result['folds'], result['common_outcomes_by_fold']):
            fold_rows.append({'policy': policy, 'fold': fold['fold'], 'start': fold['validation_start'],
                              'end': fold['validation_end'], 'own_label_f1': fold['f1_macro'],
                              'own_label_majority_f1': fold['baseline_f1'], 'own_label_mcc': fold['mcc'],
                              **{'common_' + key: value for key, value in common['absolute_5pct_bear'].items()}})
        lines.append(f"| {policy} | {result['mean_f1']:.3f} | {result['mean_baseline_f1']:.3f} | "
                     f"{result['mean_mcc']:.3f} | {result['worst_f1']:.3f} |")
    lines.extend(['', '## Common yardstick: actual simple return below -5% after 20 market sessions', '',
                  '| Policy | True bearish samples | Correct alarms (TP) | False alarms (FP) | Missed (FN) | Precision | Recall |',
                  '|---|---|---|---|---|---|---|'])
    for row in common_rows:
        precision = f"{row['bear_precision']:.1%}" if row['bear_precision'] is not None else 'undefined'
        recall = f"{row['bear_recall']:.1%}" if row['bear_recall'] is not None else 'undefined'
        lines.append(f"| {row['policy']} | {row['bear_support']} | {row['bear_hits']} | {row['bear_false_alarms']} | "
                     f"{row['bear_missed']} | {precision} | {recall} |")
    lines.extend(['', 'The shared yardstick is not the volatility-label ground truth. It asks whether a relative bearish signal detects the original absolute loss goal.',
                  'Overlapping labelled days are not independent crashes or trades. No fees/execution/backtest were modeled.',
                  'No final holdout was scored and no winner is automatically selected.'])
    pd.DataFrame(native_rows).to_csv(output / 'native_metrics.csv', index=False)
    pd.DataFrame(common_rows).to_csv(output / 'common_5pct_risk.csv', index=False)
    pd.DataFrame(fold_rows).to_csv(output / 'fold_metrics.csv', index=False)
    pd.DataFrame(outcomes).to_csv(output / 'conditional_forward_returns.csv', index=False)
    (output / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--trials', type=int, default=15)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--inner-splits', type=int, default=2)
    parser.add_argument('--refit-sessions', type=int, default=63)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if min(args.trials, args.timeout, args.refit_sessions) < 1 or args.inner_splits < 2:
        parser.error('Require positive trials/timeout/refit-sessions and inner-splits >=2')
    return args


def main(argv=None):
    args = parse_args(argv)
    variants, book, plan = prepare_label_experiment(args)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = args.output_dir or ROOT / 'reports/regime_labels' / stamp
    output.mkdir(parents=True, exist_ok=False)
    (output / 'label_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    # Only write the shared feature-eligible cohort, retaining the full-calendar label end dates.
    dates = variants[0][1]['Date']
    book.loc[book['Date'].isin(dates)].to_csv(output / 'label_definitions.csv', index=False)
    print(f'Output: {output.resolve()}; fixed setup: LightGBM / trend / 3y / T+20')
    for policy, info in plan['policies'].items():
        print(policy, json.dumps(info))
    if plan['errors']:
        raise ValueError('Preflight failed; no training started. ' + '; '.join(plan['errors']))
    if args.audit_only:
        print('Audit passed. No model fitted, holdout scored, or ONNX exported.')
        return plan
    report = {'mode': plan['mode'], 'plan': 'label_plan.json', 'comparison_rule': plan['comparison_rule'], 'results': []}
    for policy, frame, job in variants:
        print(f'Running label policy {policy}', flush=True)
        result, records = exp.run_candidate(frame, job, plan['optuna'])
        records = attach_label_metadata(records, book)
        result.update(label_policy=policy, candidate=policy + '_' + result['candidate'])
        result['common_outcomes'] = common_outcomes(records)
        result['common_outcomes_by_fold'] = [common_outcomes(rows) for _, rows in records.groupby('outer_fold', sort=True)]
        result['common_outcomes_by_decision_year'] = {str(year): common_outcomes(rows)
                                                     for year, rows in records.groupby(records['Date'].dt.year)}
        records.to_csv(output / (policy + '_predictions.csv'), index=False)
        report['results'].append(result)
        (output / 'label_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        write_label_summary(report['results'], output)
        shared = result['common_outcomes']['absolute_5pct_bear']
        print(f"{policy}: own-label F1={result['mean_f1']:.3f}, MCC={result['mean_mcc']:.3f}; "
              f"COMMON -5% goal TP/FP/FN={shared['bear_hits']}/{shared['bear_false_alarms']}/{shared['bear_missed']}")
    print(f'Done. Different label tasks; no cross-target winner or final test claim. Results: {output.resolve()}')
    return report


if __name__ == '__main__':
    main()
