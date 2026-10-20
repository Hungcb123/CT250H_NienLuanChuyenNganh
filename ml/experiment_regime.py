"""Controlled regime experiments: fixed validation dates, causal long features,
purged inner tuning, and periodic refits. Historical DEVELOPMENT research only;
never scores a final holdout, writes the exposure registry, or exports ONNX.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, matthews_corrcoef

import train_regime_v2 as base

ROOT = Path(__file__).resolve().parent
TREND_NAMES = ['ROC60', 'ROC120', 'DistSMA200']
RISK_NAMES = ['Drawdown120', 'Drawdown252', 'HV20_60_Ratio', 'DownsideHV60']
GROUPS = {'baseline': [], 'trend': TREND_NAMES, 'risk': RISK_NAMES, 'long': TREND_NAMES + RISK_NAMES}
LABEL_POLICY = {20: (.05, -.05), 60: (.10, -.10), 120: (.15, -.15)}


def date_hash(dates):
    values = '\n'.join(pd.DatetimeIndex(dates).strftime('%Y-%m-%d'))
    return hashlib.sha256(values.encode()).hexdigest()


def long_features(index):
    """Trailing windows on the full market calendar; percentages except volatility ratio.

    Drawdown is current close / trailing peak - 1, not maximum path drawdown.
    Downside volatility is sqrt(mean(min(log-return, 0)^2)) over ALL 60 returns.
    The volatility ratio is undefined (NaN) for a zero-volatility denominator.
    """
    price = index['Price'].astype(float)
    returns = np.log(price).diff()
    vol20 = returns.rolling(20, min_periods=20).std(ddof=1)
    vol60 = returns.rolling(60, min_periods=60).std(ddof=1)
    frame = pd.DataFrame({
        'ROC60': (price / price.shift(60) - 1) * 100,
        'ROC120': (price / price.shift(120) - 1) * 100,
        'DistSMA200': (price / price.rolling(200, min_periods=200).mean() - 1) * 100,
        'Drawdown120': (price / price.rolling(120, min_periods=120).max() - 1) * 100,
        'Drawdown252': (price / price.rolling(252, min_periods=252).max() - 1) * 100,
        'HV20_60_Ratio': vol20 / vol60.where(vol60 > 0),
        'DownsideHV60': np.sqrt(returns.clip(upper=0).pow(2).rolling(60, min_periods=60).mean()) * np.sqrt(252) * 100,
    }, index=index.index)
    return frame.replace([np.inf, -np.inf], np.nan)


def bear_errors(matrix):
    matrix = np.asarray(matrix, dtype=int)
    if matrix.shape != (3, 3) or (matrix < 0).any():
        raise ValueError('Need a nonnegative 3x3 confusion matrix with actual rows/predicted columns')
    true_bear = int(matrix[0].sum())
    signals = int(matrix[:, 0].sum())
    hits = int(matrix[0, 0])
    false_alarms, missed = signals - hits, true_bear - hits
    non_bear = int(matrix[1:].sum())
    return {'bear_support': true_bear, 'bear_signals': signals, 'bear_hits': hits,
            'bear_false_alarms': false_alarms, 'bear_missed': missed,
            'bear_precision': hits / signals if signals else None,
            'bear_recall': hits / true_bear if true_bear else None,
            'bear_false_alarm_rate': false_alarms / non_bear if non_bear else None,
            'bear_false_discovery_rate': false_alarms / signals if signals else None}


def prediction_metrics(records):
    actual, predicted = records['label'].to_numpy(), records['prediction'].to_numpy()
    matrix = confusion_matrix(actual, predicted, labels=[0, 1, 2])
    return {'f1_macro': float(f1_score(actual, predicted, labels=[0, 1, 2], average='macro', zero_division=0)),
            'mcc': float(matthews_corrcoef(actual, predicted)),
            'accuracy': float(accuracy_score(actual, predicted)),
            'baseline_f1': float(f1_score(actual, records['baseline_prediction'], labels=[0, 1, 2], average='macro', zero_division=0)),
            'confusion_matrix': matrix.tolist(), 'n_samples': len(records), **bear_errors(matrix)}


def training_indices(frame, boundary, window):
    boundary = pd.Timestamp(boundary)
    known = (frame['Date'] < boundary) & (frame['label_end_date'] < boundary)
    if window != 'expanding':
        known &= frame['Date'] >= boundary - pd.DateOffset(years=int(window[:-1]))
    indices = np.flatnonzero(known.to_numpy())
    if len(indices) < 30 or set(frame['label'].iloc[indices]) != {0, 1, 2}:
        raise ValueError(f'{window} before {boundary.date()}: require >=30 purged training rows and all 3 regimes')
    return indices


def refit_blocks(frame, validation_indices, calendar, refit_sessions):
    """Schedule refits in actual index sessions, even if ETF rows have gaps."""
    if refit_sessions < 1:
        raise ValueError('refit_sessions must be positive')
    positions = pd.DatetimeIndex(calendar).get_indexer(frame['Date'].iloc[validation_indices])
    if (positions < 0).any() or len(positions) == 0:
        raise ValueError('Validation dates must belong to the full VNINDEX calendar')
    buckets = (positions - positions[0]) // refit_sessions
    return [validation_indices[buckets == bucket] for bucket in np.unique(buckets)]


def freeze_reference(frame, report, horizon, feature_set):
    matches = [r for r in report['results'] if r['horizon'] == horizon and r['feature_set'] == feature_set]
    if not matches:
        raise ValueError(f'Reference report lacks {feature_set} T+{horizon}')
    signatures = [[(f['validation_start'], f['validation_end'], f['n_validation'])
                   for f in r['validation_folds']] for r in matches]
    if any(s != signatures[0] for s in signatures[1:]):
        raise ValueError('Reference models used different validation periods')
    folds, used = [], set()
    for start, end, expected_count in signatures[0]:
        indices = np.flatnonzero(frame['Date'].between(pd.Timestamp(start), pd.Timestamp(end)).to_numpy())
        if len(indices) != expected_count or not len(indices):
            raise ValueError(f'Frozen period {start} -> {end}: expected {expected_count} dates, got {len(indices)}')
        if str(frame['Date'].iloc[indices[0]].date()) != start or str(frame['Date'].iloc[indices[-1]].date()) != end:
            raise ValueError('Frozen period endpoint missing from current feature cohort')
        if used.intersection(indices.tolist()):
            raise ValueError('Reference validation folds overlap')
        used.update(indices.tolist())
        folds.append(indices)
    return folds


def prepare_experiment(args):
    reference_path = args.reference_report
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    if reference.get('mode') not in ['development_only', 'quick_development_only']:
        raise ValueError('Use a development report as the frozen reference, not a final holdout report')
    reference_audit = json.loads((reference_path.parent / 'data_audit.json').read_text(encoding='utf-8'))
    index, index_audit = base.load_market_data(args.data_dir / 'VNINDEX.csv')
    needs_etf = args.base_feature_set == 'close-etf'
    etf, etf_audit = base.load_market_data(args.data_dir / 'E1VFVN30.csv') if needs_etf else (None, None)
    for symbol, audit in [('VNINDEX', index_audit), ('E1VFVN30', etf_audit)]:
        if audit is not None and audit['sha256'] != reference_audit['inputs'][symbol]['sha256']:
            raise ValueError(f'{symbol}: data hash differs from frozen reference; do not silently change the test cohort')
    features, base_names = base.build_feature_matrix(index, etf, args.base_feature_set)
    features = pd.concat([features, long_features(index)], axis=1)
    names = {group: base_names + GROUPS[group] for group in args.feature_groups}
    required = list(dict.fromkeys(name for columns in names.values() for name in columns))
    frames, jobs = {}, []
    plan = {'mode': 'historical_development_experiments_not_final_test',
            'reference_report': str(reference_path.resolve()),
            'reference_sha256': hashlib.sha256(reference_path.read_bytes()).hexdigest(),
            'input_hashes': {'VNINDEX': index_audit['sha256'], 'E1VFVN30': etf_audit['sha256'] if etf_audit else None},
            'labels': {str(h): base.HORIZONS[h] for h in args.horizons},
            'base_feature_set': args.base_feature_set, 'feature_groups': names,
            'feature_version': 'long-trend-risk-v1-research',
            'train_windows': args.train_windows, 'refit_market_sessions': args.refit_sessions,
            'inner_splits': args.inner_splits, 'models': args.models,
            'optuna': {'n_trials': 5 if args.quick else args.trials, 'timeout_seconds': 30 if args.quick else args.timeout},
            'score_role': 'Nested forward development comparison on already-inspected history; no fresh holdout claim.',
            'assumptions': ['All variants use identical dates and labels; adding a feature cannot remove a frozen validation date.',
                            'Parameters are selected once at each outer fold start using purged inner folds only.',
                            'The model is refitted periodically using labels known strictly before each prediction block.',
                            'Rolling windows are calendar years measured from the prediction block start.',
                            'Each refit uses the same fixed parameters until the next outer fold.',
                            'A drawdown feature measures current distance below the trailing peak.',
                            'No confidence threshold, new label definition, financial backtest, or ONNX deployment.'],
            'datasets': [], 'errors': []}
    calendar = pd.DatetimeIndex(index['Date'])
    for horizon in args.horizons:
        expected_bull, expected_bear = LABEL_POLICY[horizon]
        if (base.HORIZONS[horizon]['bull_threshold'], base.HORIZONS[horizon]['bear_threshold']) != (expected_bull, expected_bear):
            raise ValueError('Label thresholds changed; this experiment must keep the original label policy')
        # Establish validation dates from the OLD base feature schema first.
        baseline = base.create_labels(features, horizon, base_names)
        original_folds = freeze_reference(baseline, reference, horizon, args.base_feature_set)
        valid = np.isfinite(baseline[required].to_numpy(dtype=float)).all(axis=1)
        frozen_ids = np.concatenate(original_folds)
        if not valid[frozen_ids].all():
            raise ValueError('A new feature is missing on frozen validation dates; repair features, do not shrink validation')
        frame = baseline.loc[valid].reset_index(drop=True)
        frames[horizon] = frame
        outer_folds = freeze_reference(frame, reference, horizon, args.base_feature_set)
        # Training dates also share one common feature-eligible cohort across all variants.
        fold_plan = []
        for fold_no, validation in enumerate(outer_folds, 1):
            blocks = refit_blocks(frame, validation, calendar, args.refit_sessions)
            fold_plan.append({'fold': fold_no, 'start': str(frame['Date'].iloc[validation[0]].date()),
                              'end': str(frame['Date'].iloc[validation[-1]].date()), 'n_validation': len(validation),
                              'validation_dates_sha256': date_hash(frame['Date'].iloc[validation]),
                              'n_refits': len(blocks)})
        plan['datasets'].append({'horizon': horizon, 'eligible_history_rows': len(frame), 'folds': fold_plan})
        for window in args.train_windows:
            outer_jobs = []
            for fold_no, validation in enumerate(outer_folds, 1):
                try:
                    tuning_indices = training_indices(frame, frame['Date'].iloc[validation[0]], window)
                    inner = base.purged_folds(frame.iloc[tuning_indices].reset_index(drop=True), args.inner_splits)
                    blocks = []
                    for predictions in refit_blocks(frame, validation, calendar, args.refit_sessions):
                        train = training_indices(frame, frame['Date'].iloc[predictions[0]], window)
                        blocks.append({'train': train, 'validation': predictions})
                    outer_jobs.append({'fold': fold_no, 'tune': tuning_indices, 'inner': inner, 'blocks': blocks})
                except ValueError as exc:
                    plan['errors'].append(f'T+{horizon} {window} fold {fold_no}: {exc}')
            for group in args.feature_groups:
                for model in args.models:
                    jobs.append({'horizon': horizon, 'group': group, 'window': window, 'model': model,
                                 'names': names[group], 'folds': outer_jobs})
    return frames, jobs, plan


def run_candidate(frame, job, optuna):
    all_records, fold_results, tuning = [], [], []
    for outer in job['folds']:
        tune_frame = frame.iloc[outer['tune']].reset_index(drop=True)
        result = base.tune_and_evaluate(job['model'], tune_frame, job['names'], outer['inner'],
                                       n_trials=optuna['n_trials'], timeout=optuna['timeout_seconds'])
        tuning.append({'outer_fold': outer['fold'], 'inner_selection_f1': result['validation_f1_macro'],
                       'best_params': result['best_params'], 'n_trials': result['optuna_n_trials']})
        fold_records, refits = [], []
        for block_no, block in enumerate(outer['blocks'], 1):
            train, validation = frame.iloc[block['train']], frame.iloc[block['validation']]
            if train['label_end_date'].max() >= validation['Date'].min():
                raise ValueError('Training label overlaps its prediction block')
            model, scaler = base.fit_selected_candidate(result, train, job['names'])
            X = validation[job['names']].to_numpy(dtype=np.float32)
            predicted = np.asarray(model.predict(scaler.transform(X) if scaler is not None else X)).reshape(-1).astype(int)
            records = validation[['Date', 'label_end_date', 'label', 'future_return']].copy()
            records['prediction'] = predicted
            records['baseline_prediction'] = int(np.bincount(train['label'].to_numpy(dtype=int), minlength=3).argmax())
            records['outer_fold'], records['refit_block'] = outer['fold'], block_no
            fold_records.append(records)
            refits.append({'train_start': str(train['Date'].min().date()), 'train_end': str(train['Date'].max().date()),
                           'train_label_end': str(train['label_end_date'].max().date()), 'n_train': len(train),
                           'prediction_start': str(validation['Date'].min().date()),
                           'prediction_end': str(validation['Date'].max().date()), 'n_predictions': len(validation)})
        records = pd.concat(fold_records, ignore_index=True)
        metrics = prediction_metrics(records)
        metrics.update(fold=outer['fold'], validation_start=str(records['Date'].min().date()),
                       validation_end=str(records['Date'].max().date()), refits=refits)
        fold_results.append(metrics)
        all_records.append(records)
    records = pd.concat(all_records, ignore_index=True)
    per_year = {str(year): prediction_metrics(rows) for year, rows in records.groupby(records['Date'].dt.year)}
    f1s, mccs = [f['f1_macro'] for f in fold_results], [f['mcc'] for f in fold_results]
    result = {'candidate': f"t{job['horizon']}_{job['model']}_{job['group']}_{job['window']}",
              'horizon': job['horizon'], 'model_name': job['model'], 'feature_group': job['group'],
              'train_window': job['window'], 'features': job['names'], 'folds': fold_results,
              'mean_f1': float(np.mean(f1s)), 'std_f1': float(np.std(f1s)), 'worst_f1': float(min(f1s)),
              'mean_mcc': float(np.mean(mccs)), 'worst_mcc': float(min(mccs)),
              'mean_baseline_f1': float(np.mean([f['baseline_f1'] for f in fold_results])),
              'folds_beating_majority': sum(f['f1_macro'] > f['baseline_f1'] for f in fold_results),
              'pooled': prediction_metrics(records), 'per_decision_year': per_year, 'inner_tuning': tuning,
              'score_role': 'nested_forward_development_comparison_not_fresh_test'}
    return result, records


def diagnose_existing(report_path, output_dir):
    """Derive exact error counts from existing matrices without refitting or changing the report."""
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    rows = []
    for candidate in report['results']:
        for fold_no, fold in enumerate(candidate['validation_folds'], 1):
            errors = bear_errors(fold['confusion_matrix'])
            rows.append({'horizon': candidate['horizon'], 'feature_set': candidate['feature_set'],
                         'model': candidate['model_name'], 'fold': fold_no,
                         'start': fold['validation_start'], 'end': fold['validation_end'],
                         'f1': fold['f1_macro'], 'baseline_f1': fold['baseline_f1'],
                         'mcc': fold['mcc'], **errors})
    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(rows).to_csv(output_dir / 'fold_errors.csv', index=False)
    lines = ['# Regime fold diagnostics', '', f'Source: {Path(report_path).resolve()}', '',
             'Derived from existing validation matrices; no model fitted. These are selection scores, not new test scores.', '',
             '| H | Features / model | Fold | F1 | Baseline | MCC | Bear TP / FP / FN |',
             '|---|---|---|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['horizon']} | {row['feature_set']} / {row['model']} | {row['fold']} | "
                     f"{row['f1']:.3f} | {row['baseline_f1']:.3f} | {row['mcc']:.3f} | "
                     f"{row['bear_hits']} / {row['bear_false_alarms']} / {row['bear_missed']} |")
    (output_dir / 'diagnostics.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rows


def write_summary(results, output_dir):
    rows, fold_rows, year_rows, deltas = [], [], [], []
    for result in results:
        errors = {key: value for key, value in result['pooled'].items() if key.startswith('bear_')}
        rows.append({key: result[key] for key in ['candidate', 'horizon', 'mean_f1', 'std_f1', 'worst_f1',
                                                 'mean_mcc', 'worst_mcc', 'mean_baseline_f1', 'folds_beating_majority']} | errors)
        for fold in result['folds']:
            fold_rows.append({'candidate': result['candidate'], **{
                key: value for key, value in fold.items() if key not in ['confusion_matrix', 'refits']}})
        for year, metrics in result['per_decision_year'].items():
            year_rows.append({'candidate': result['candidate'], 'decision_year': year, **{
                key: value for key, value in metrics.items() if key != 'confusion_matrix'}})
        controls = [r for r in results if r['horizon'] == result['horizon'] and r['model_name'] == result['model_name']
                    and r['feature_group'] == 'baseline' and r['train_window'] == 'expanding']
        if controls:
            control = controls[0]
            deltas.append({'candidate': result['candidate'], 'control': control['candidate'],
                           'mean_f1_delta': result['mean_f1'] - control['mean_f1'],
                           'mean_mcc_delta': result['mean_mcc'] - control['mean_mcc'],
                           'worst_f1_delta': result['worst_f1'] - control['worst_f1'],
                           'bear_false_alarms_delta': result['pooled']['bear_false_alarms'] - control['pooled']['bear_false_alarms'],
                           'bear_missed_delta': result['pooled']['bear_missed'] - control['pooled']['bear_missed'],
                           'folds_beating_control': sum(a['f1_macro'] > b['f1_macro']
                                                       for a, b in zip(result['folds'], control['folds']))})
    pd.DataFrame(rows).to_csv(output_dir / 'comparison.csv', index=False)
    pd.DataFrame(fold_rows).to_csv(output_dir / 'fold_errors.csv', index=False)
    pd.DataFrame(year_rows).to_csv(output_dir / 'year_errors.csv', index=False)
    pd.DataFrame(deltas).to_csv(output_dir / 'paired_deltas.csv', index=False)
    lines = ['# Controlled development comparison', '',
             'Same dates and labels for all candidates. Nested tuning + periodic refits. Historical development only; no fresh test claim.', '',
             '| Candidate | Mean F1 ± fold SD | Worst F1 | MCC | Folds > majority | Bear TP / FP / FN |',
             '|---|---|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['candidate']} | {row['mean_f1']:.3f} ± {row['std_f1']:.3f} | {row['worst_f1']:.3f} | "
                     f"{row['mean_mcc']:.3f} | {row['folds_beating_majority']} | "
                     f"{row['bear_hits']} / {row['bear_false_alarms']} / {row['bear_missed']} |")
    lines.extend(['', 'TP = correctly predicted bearish samples; FP = bearish false alarms; FN = missed bearish samples.',
                  'Fold SD is descriptive dispersion, not a confidence interval. Overlapping labels are not independent events.',
                  'Compare against the baseline candidate from this run, not an older non-nested score.'])
    (output_dir / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def plot_experiments(results, output_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for horizon in sorted({r['horizon'] for r in results}):
        selected = [r for r in results if r['horizon'] == horizon]
        labels = [f"{r['model_name']}\n{r['feature_group']} / {r['train_window']}" for r in selected]
        positions = np.arange(len(selected))
        fig, axes = plt.subplots(2, 1, figsize=(max(10, len(selected) * .9), 9), sharex=True)
        axes[0].bar(positions, [r['mean_f1'] for r in selected],
                    yerr=[r['std_f1'] for r in selected], capsize=3, label='Mean macro F1 ± fold SD')
        axes[0].plot(positions, [r['mean_baseline_f1'] for r in selected], 'o', color='black', label='Mean majority F1')
        axes[0].set_ylim(0, 1)
        axes[0].set_ylabel('Development macro F1')
        axes[0].set_title(f'T+{horizon}: frozen dates, nested tuning, periodic refits (historical development only)')
        axes[0].legend()
        for offset, key, label in [(-.18, 'bear_precision', 'Bear precision'), (.18, 'bear_recall', 'Bear recall')]:
            values = [r['pooled'][key] if r['pooled'][key] is not None else np.nan for r in selected]
            axes[1].bar(positions + offset, values, width=.36, label=label)
        axes[1].set_ylim(0, 1)
        axes[1].set_ylabel('Pooled bearish samples')
        axes[1].set_xticks(positions, labels, rotation=45, ha='right')
        axes[1].legend()
        fig.tight_layout()
        fig.savefig(output_dir / f'model_comparison_t{horizon}.png', dpi=150)
        plt.close(fig)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path)
    parser.add_argument('--diagnose-report', type=Path, help='Read an existing report and export fold error counts; no fitting')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--base-feature-set', choices=['close', 'close-etf'], default='close-etf')
    parser.add_argument('--feature-groups', nargs='+', choices=list(GROUPS), default=list(GROUPS))
    parser.add_argument('--train-windows', nargs='+', choices=['expanding', '3y', '5y'], default=['expanding', '3y', '5y'])
    parser.add_argument('--models', nargs='+', choices=base.MODEL_NAMES, default=['LightGBM'])
    parser.add_argument('--horizons', type=int, nargs='+', choices=list(base.HORIZONS), default=[20])
    parser.add_argument('--refit-sessions', type=int, default=63)
    parser.add_argument('--inner-splits', type=int, default=2)
    parser.add_argument('--trials', type=int, default=15)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if not args.diagnose_report and not args.reference_report:
        parser.error('--reference-report is required for experiments')
    if min(args.refit_sessions, args.trials, args.timeout) < 1 or args.inner_splits < 2:
        parser.error('Require positive refit-sessions/trials/timeout and inner-splits >=2')
    for name in ['feature_groups', 'train_windows', 'models', 'horizons']:
        setattr(args, name, list(dict.fromkeys(getattr(args, name))))
    return args


def main(argv=None):
    args = parse_args(argv)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = args.output_dir or ROOT / 'reports/regime_experiments' / timestamp
    if args.diagnose_report:
        rows = diagnose_existing(args.diagnose_report, output)
        print(f'Diagnosed {len(rows)} fold results without fitting. Output: {output.resolve()}')
        return rows
    frames, jobs, plan = prepare_experiment(args)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'experiment_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    print(f"Prepared {len(jobs)} candidates; output: {output.resolve()}")
    for dataset in plan['datasets']:
        print(json.dumps(dataset))
    if plan['errors']:
        raise ValueError('Preflight failed; no training started. ' + '; '.join(plan['errors']))
    if args.audit_only:
        print('Audit passed. No model fitted, independent holdout scored, or artifact exported.')
        return plan
    report = {'mode': plan['mode'], 'plan': 'experiment_plan.json', 'results': []}
    for job in jobs:
        print(f"Running T+{job['horizon']} {job['model']} / {job['group']} / {job['window']}", flush=True)
        result, predictions = run_candidate(frames[job['horizon']], job, plan['optuna'])
        predictions.to_csv(output / (result['candidate'] + '_predictions.csv'), index=False)
        report['results'].append(result)
        (output / 'experiment_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        write_summary(report['results'], output)
        print(f"Development F1={result['mean_f1']:.3f}, MCC={result['mean_mcc']:.3f}, worst F1={result['worst_f1']:.3f}")
    plot_experiments(report['results'], output)
    print(f'Done. No final holdout scoring or deployment. Results: {output.resolve()}')
    return report


if __name__ == '__main__':
    main()
