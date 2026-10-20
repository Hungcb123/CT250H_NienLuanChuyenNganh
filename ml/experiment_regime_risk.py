"""Historical T+20 risk study. No training unless explicitly run without --audit-only.

Three target definitions, one common outcome (simple return < -5%). Causal
calibration thresholds and retrospective equal-count diagnostics are separate.
"""
import argparse
import copy
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import experiment_regime_labels as labels
import regime_risk_diagnostics as diagnostics

exp = labels.exp
POLICIES = ['fixed_5pct', 'vol_1sigma', 'binary_5pct']
ALARM_RATE = .10
CALIBRATION_FRACTION = .20


def split_calibration(frame, indices):
    """Reserve last 20% of mature history; purge core labels across boundary."""
    indices = np.asarray(indices, dtype=int)
    cut = int(len(indices) * (1 - CALIBRATION_FRACTION))
    calibration = indices[cut:]
    core = indices[:cut]
    core = core[(frame['label_end_date'].iloc[core] < frame['Date'].iloc[calibration[0]]).to_numpy()]
    if len(core) < 150 or len(calibration) < 30:
        raise ValueError('Insufficient purged core/calibration history')
    return core, calibration


def risk_score(model, X, policy):
    code = 1 if policy == 'binary_5pct' else 0
    classes = list(model.classes_)
    if code not in classes:
        raise ValueError('Missing risk class in fitted model')
    score = np.asarray(model.predict_proba(X))[:, classes.index(code)]
    if not np.isfinite(score).all() or ((score < 0) | (score > 1)).any():
        raise ValueError('Invalid risk scores')
    return score


def alarm_threshold(scores):
    # Strict > makes tie handling conservative and reproducible.
    return float(np.quantile(scores, 1 - ALARM_RATE, method='higher'))


def binary_metrics(y, alarm):
    y, alarm = np.asarray(y, dtype=bool), np.asarray(alarm, dtype=bool)
    tp, fp = int((y & alarm).sum()), int((~y & alarm).sum())
    fn, tn = int((y & ~alarm).sum()), int((~y & ~alarm).sum())
    return dict(n=len(y), support=int(y.sum()), alarms=int(alarm.sum()), tp=tp, fp=fp, fn=fn, tn=tn,
                alarm_rate=float(alarm.mean()), prevalence=float(y.mean()),
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                false_positive_rate=fp / (fp + tn) if fp + tn else None)


def prepare(args):
    variants, book, plan = labels.prepare_label_experiment(args)
    result = list(variants)
    _, fixed, template = variants[0]
    binary = fixed.copy()
    binary['label'] = (binary['label'] == 0).astype(int)
    result.append(('binary_5pct', binary, copy.deepcopy(template)))
    for policy, frame, job in result:
        for outer in job['folds']:
            for block in outer['blocks']:
                core, calibration = split_calibration(frame, block['train'])
                if frame['label_end_date'].iloc[calibration].max() >= frame['Date'].iloc[block['validation'][0]]:
                    raise ValueError('Calibration labels overlap prediction block')
                expected = 2 if policy == 'binary_5pct' else 3
                if frame['label'].iloc[core].nunique() != expected:
                    raise ValueError(f'{policy}: missing class in core training')
                history = frame.loc[(frame.Date > frame.Date.iloc[core].max()) & (frame.Date <= frame.Date.iloc[block['validation']].max())]
                diagnostics.rolling_thresholds(history.Date, np.zeros(len(history)), frame.Date.iloc[block['validation']])
                block['core'], block['calibration'] = core, calibration
            first_core = outer['blocks'][0]['core']
            core_frame = frame.iloc[first_core].reset_index(drop=True)
            outer['risk_inner'] = risk_inner_folds(core_frame, args.inner_splits, expected)
    plan.pop('assumptions', None)  # Prior label-study assumptions do not describe this protocol.
    plan.update(mode='historical_risk_development_not_fresh_test', policies=POLICIES,
                common_outcome='simple VNINDEX return at T+20 < -5%', alarm_rate_target=ALARM_RATE,
                calibration_fraction=CALIBRATION_FRACTION,
                tuning_objective='mean inner-fold average precision on common -5% outcome for ALL policies',
                score_meaning='ranking scores from balanced-weight models; not calibrated event probabilities',
                protocol=['Same features, dates, 3y history windows and refit blocks across all three candidates.',
                          'Core fit excludes last 20% of mature history, reserved for calibration; core labels purged at calibration start.',
                          'Tune only on purged inner folds of first core in each outer fold, then freeze hyperparameters within outer fold.',
                          'Calibration and outer predictions use SAME core model; calibration rows are not refitted into model.',
                          'Threshold = historical calibration 90th percentile (higher); alarm strictly above; realized rate may differ from 10%.',
                          'Equal-count top10% per outer fold uses future score distribution: retrospective ranking diagnostic ONLY.',
                          'Inner validation with no loss event contributes AP=0 for every trial; all-positive validation contributes AP=1. Such folds cannot discriminate rankings.',
                          'New tuning objective and calibration split mean these are NOT reproductions of previous native-F1 runs.',
                          'No independent crash count, profit backtest, final holdout, deployment or export.'])
    return result, book, plan


def risk_inner_folds(frame, n_splits, n_classes):
    from sklearn.model_selection import TimeSeriesSplit
    folds = []
    for train, valid in TimeSeriesSplit(n_splits=n_splits, test_size=len(frame) // (n_splits + 2)).split(frame):
        train = train[(frame['label_end_date'].iloc[train] < frame['Date'].iloc[valid[0]]).to_numpy()]
        if len(train) < 30 or frame['label'].iloc[train].nunique() != n_classes:
            raise ValueError('Insufficient purged inner history or target classes')
        folds.append((train, valid))
    return folds


def select_params(frame, names, inner, policy, budget):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    X = frame[names].to_numpy(dtype=np.float32)
    y = frame['label'].to_numpy(dtype=int)
    common = (frame['future_return'].to_numpy() < -.05).astype(int)

    def objective(trial):
        params = exp.base.OPTUNA_PARAM_FNS['LightGBM'](trial)
        scores = []
        for train, valid in inner:
            if frame['label_end_date'].iloc[train].max() >= frame['Date'].iloc[valid].min():
                raise ValueError('Inner label overlap')
            model = exp.base.create_model('LightGBM', params)
            model.fit(X[train], y[train])
            scores.append(average_precision_score(common[valid], risk_score(model, X[valid], policy)) if common[valid].any() else 0.0)
        return float(np.mean(scores))

    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=budget['n_trials'], timeout=budget['timeout_seconds'])
    return exp.base.OPTUNA_PARAM_FNS['LightGBM'](study.best_trial), dict(
        inner_common_average_precision=float(study.best_value), n_trials=len(study.trials))


def run_policy(policy, frame, job, budget, fixed_params=False):
    rows, audits = [], []
    for outer in job['folds']:
        first = outer['blocks'][0]['core']
        if fixed_params:
            params, tuning = dict(diagnostics.FIXED_PARAMS), dict(parameter_mode='fixed_shallow', n_trials=0)
        else:
            params, tuning = select_params(frame.iloc[first].reset_index(drop=True), job['names'], outer['risk_inner'], policy, budget)
        for block_no, block in enumerate(outer['blocks'], 1):
            core, calibration, valid = (frame.iloc[block[key]] for key in ['core', 'calibration', 'validation'])
            if core['label_end_date'].max() >= calibration['Date'].min() or calibration['label_end_date'].max() >= valid['Date'].min():
                raise ValueError('Noncausal core/calibration/prediction split')
            model = exp.base.create_model('LightGBM', params)
            model.fit(core[job['names']].to_numpy(dtype=np.float32), core['label'].to_numpy(dtype=int))
            calibration_score = risk_score(model, calibration[job['names']].to_numpy(dtype=np.float32), policy)
            threshold = alarm_threshold(calibration_score)
            record = valid[['Date', 'label_end_date', 'future_return', 'label']].copy()
            record['risk_score'] = risk_score(model, valid[job['names']].to_numpy(dtype=np.float32), policy)
            record['threshold'], record['alarm'] = threshold, record['risk_score'] > threshold
            # Rescore trailing history with THIS core model; never combine scores from different refits.
            history = frame.loc[(frame.Date > core.Date.max()) & (frame.Date <= valid.Date.max())]
            history_scores = risk_score(model, history[job['names']].to_numpy(dtype=np.float32), policy)
            rolling = diagnostics.rolling_thresholds(history.Date, history_scores, valid.Date)
            for column, values in rolling.items():
                record[column] = values
                record[column.replace('_threshold', '_alarm')] = record.risk_score > values
            record['common_bear'] = record['future_return'] < -.05
            record['outer_fold'], record['refit_block'], record['policy'] = outer['fold'], block_no, policy
            rows.append(record)
            audits.append(dict(outer_fold=outer['fold'], refit_block=block_no,
                               core_start=str(core.Date.min()), core_end=str(core.Date.max()),
                               core_label_end=str(core.label_end_date.max()), calibration_start=str(calibration.Date.min()),
                               calibration_end=str(calibration.Date.max()), calibration_label_end=str(calibration.label_end_date.max()),
                               prediction_start=str(valid.Date.min()), n_core=len(core), n_calibration=len(calibration),
                               threshold=threshold, calibration_alarm_rate=float((calibration_score > threshold).mean()),
                               **diagnostics.score_stats(calibration_score, 'calibration_score'),
                               best_params=params, **tuning))
    return pd.concat(rows, ignore_index=True), audits


def summary_rows(records):
    output = []
    for policy, data in records.groupby('policy', sort=False):
        for fold, rows in [('all', data), *list(data.groupby('outer_fold'))]:
            metrics = binary_metrics(rows.common_bear, rows.alarm)
            both = rows.common_bear.nunique() == 2
            output.append(dict(policy=policy, fold=fold, **metrics,
                               average_precision=float(average_precision_score(rows.common_bear, rows.risk_score)) if both else None,
                               roc_auc=float(roc_auc_score(rows.common_bear, rows.risk_score)) if both else None))
    return output


def equal_count_diagnostic(records):
    result = records.copy()
    result['alarm'] = False
    for _, rows in result.groupby(['policy', 'outer_fold']):
        # Stable date tie-break; uses whole future fold's scores: NEVER a live rule.
        selected = rows.sort_values(['risk_score', 'Date'], ascending=[False, True], kind='stable').head(int(np.floor(len(rows) * ALARM_RATE)))
        result.loc[selected.index, 'alarm'] = True
    return summary_rows(result)


def bootstrap_deltas(records, repeats=1000):
    """Paired circular moving-block resampling WITHIN folds; descriptive sensitivity.

    20/60-session blocks check overlap sensitivity. Not independent holdout inference,
    and does not account for prior experiments/model selection on these same dates.
    """
    policies = list(records.policy.unique())
    groups = {p: records.loc[records.policy == p].sort_values('Date').reset_index(drop=True) for p in policies}
    reference = groups['fixed_5pct']
    for p in policies:
        if not groups[p].Date.equals(reference.Date) or not groups[p].common_bear.equals(reference.common_bear):
            raise ValueError('Paired bootstrap requires identical dates and common outcomes')
    rng, output = np.random.default_rng(42), []
    folds = [g.index.to_numpy() for _, g in reference.groupby('outer_fold')]
    for length in [20, 60]:
        draws = {p: {'precision': [], 'recall': []} for p in policies if p != 'fixed_5pct'}
        for _ in range(repeats):
            indices = []
            for fold in folds:
                starts = rng.integers(0, len(fold), size=int(np.ceil(len(fold) / length)))
                local = np.concatenate([(s + np.arange(length)) % len(fold) for s in starts])[:len(fold)]
                indices.extend(fold[local])
            metrics = {p: binary_metrics(g.common_bear.iloc[indices], g.alarm.iloc[indices]) for p, g in groups.items()}
            for p in draws:
                for key in draws[p]:
                    a, b = metrics[p][key], metrics['fixed_5pct'][key]
                    if a is not None and b is not None:
                        draws[p][key].append(a - b)
        for p, values in draws.items():
            for metric, samples in values.items():
                interval = np.quantile(samples, [.025, .975]) if samples else [None, None]
                output.append(dict(policy=p, reference='fixed_5pct', metric=metric, block_sessions=length,
                                   valid_draws=len(samples), delta_low=interval[0], delta_high=interval[1]))
    return output


def write_outputs(records, output, parameter_mode='nested_tuned'):
    rows = summary_rows(records)
    pd.DataFrame(rows).to_csv(output / 'causal_metrics.csv', index=False)
    pd.DataFrame(equal_count_diagnostic(records)).to_csv(output / 'retrospective_equal_count.csv', index=False)
    pd.DataFrame(bootstrap_deltas(records)).to_csv(output / 'paired_block_sensitivity.csv', index=False)
    years = []
    for (policy, year), group in records.groupby(['policy', records.Date.dt.year]):
        years.append(dict(policy=policy, year=int(year), **binary_metrics(group.common_bear, group.alarm)))
    pd.DataFrame(years).to_csv(output / 'year_metrics.csv', index=False)
    lines = ['# Common T+20 loss-risk development comparison', '',
             f'Outcome: simple return < -5%. LightGBM / trend / 3y. Parameter mode: {parameter_mode}.',
             'Risk scores are NOT calibrated event probabilities. No final holdout, export or profit claim.', '',
             '| Policy | Actual alarm rate | TP | FP | FN | Precision | Recall | AP |',
             '|---|---|---|---|---|---|---|---|']
    for row in rows:
        if row['fold'] != 'all':
            continue
        percent = lambda x: f'{x:.1%}' if x is not None else 'undefined'
        lines.append(f"| {row['policy']} | {percent(row['alarm_rate'])} | {row['tp']} | {row['fp']} | {row['fn']} | {percent(row['precision'])} | {percent(row['recall'])} | {row['average_precision']:.3f} |")
    lines.extend(['', 'Causal thresholds target 10% on historical calibration; realized outer alarm counts can differ.',
                  'retrospective_equal_count.csv forces identical floor(10% * fold size) alarm counts using WHOLE fold scores.',
                  'That is a ranking diagnostic with future distribution information, NEVER an executable threshold/backtest.',
                  'Read individual folds/year_metrics.csv. Overlapping samples are not independent crash events.',
                  'paired_block_sensitivity.csv: paired circular 20/60-session block bootstrap intervals for causal precision/recall differences.',
                  'Intervals are descriptive, conditional on historical selections; they do not remove repeated development reuse or structural change.'])
    (output / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_rolling_outputs(records, output):
    rows = []
    for scheme in ['static', 'rolling_60', 'rolling_120']:
        variant = records.copy()
        if scheme != 'static':
            variant['alarm'] = variant[scheme + '_alarm']
        rows.extend(dict(threshold_scheme=scheme, **row) for row in summary_rows(variant))
    pd.DataFrame(rows).to_csv(output / 'threshold_comparison.csv', index=False)


def main(argv=None):
    extras = argparse.ArgumentParser(add_help=False)
    extras.add_argument('--fixed-params', action='store_true', help='Use predeclared shallow trees; no Optuna tuning')
    extra, remaining = extras.parse_known_args(argv)
    args = labels.parse_args(remaining)
    variants, book, plan = prepare(args)
    plan.update(parameter_mode='fixed_shallow' if extra.fixed_params else 'nested_tuned',
                rolling_windows=list(diagnostics.WINDOWS),
                rolling_protocol='Quantile of strictly prior eligible out-of-fit observations, rescored by current core model; excludes current score; no guarantee of alarm rate.')
    if extra.fixed_params:
        plan['fixed_params'] = dict(diagnostics.FIXED_PARAMS)
        plan['tuning_objective'] = 'No tuning; predeclared fixed shallow parameters'
        plan['protocol'] = [line for line in plan['protocol'] if not line.startswith(('Tune only', 'New tuning', 'Inner validation'))]
        plan['protocol'].append('All folds and refits use the same predeclared shallow parameters; no tuning.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = args.output_dir or labels.ROOT / 'reports/regime_risk' / stamp
    output.mkdir(parents=True, exist_ok=False)
    (output / 'risk_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    if plan['errors']:
        raise ValueError('Preflight failed: ' + '; '.join(plan['errors']))
    if args.audit_only:
        print(f'Audit passed. No training or export. Output: {output.resolve()}')
        return plan
    all_records, all_refits = [], []
    for policy, frame, job in variants:
        print(f'Running risk policy {policy}', flush=True)
        records, audits = run_policy(policy, frame, job, plan['optuna'], fixed_params=True) if extra.fixed_params else run_policy(policy, frame, job, plan['optuna'])
        records.to_csv(output / (policy + '_predictions.csv'), index=False)
        (output / (policy + '_refits.json')).write_text(json.dumps(audits, indent=2), encoding='utf-8')
        all_records.append(records)
        all_refits.extend(dict(policy=policy, **audit) for audit in audits)
    records = pd.concat(all_records, ignore_index=True)
    write_outputs(records, output, parameter_mode=plan['parameter_mode'])
    context = records.loc[records.outer_fold == 3].merge(variants[0][1][['Date'] + variants[0][2]['names']], on='Date', validate='many_to_one')
    context.to_csv(output / 'fold3_feature_context.csv', index=False)
    write_rolling_outputs(records, output)
    index, index_audit = exp.base.load_market_data(args.data_dir / 'VNINDEX.csv')
    if index_audit['sha256'] != plan['input_hashes']['VNINDEX']:
        raise ValueError('Input changed during run')
    diagnostics.write_diagnostics(records, all_refits, index, output / 'diagnostics')
    print(f'Done. Historical development only; no deployment. Results: {output.resolve()}')
    return summary_rows(records)


if __name__ == '__main__':
    main()
