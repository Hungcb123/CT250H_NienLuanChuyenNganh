"""Tune adaptive labels only on purged inner data; compare to frozen 48.93% blend.

All outer dates are previously inspected development. No fresh-test claim.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from audit_regime_expert_selection import fold_f1

ROOT = Path(__file__).resolve().parent


def dynamic_inner_score(folds):
    macro = np.array([f['f1_macro'] for f in folds])
    directional = np.array([[f['per_class'][exp.base.LABEL_NAMES[c]]['f1'] for c in [0, 2]] for f in folds])
    return float(.5*macro.mean()+.25*macro.min()+.25*directional.mean(axis=0).min())


def assert_dynamic_inner_timing(frame, folds, outer_boundary):
    if frame.label_end_date.max() >= pd.Timestamp(outer_boundary):
        raise ValueError('Tuning includes unavailable outer outcome')
    for train, valid in folds:
        if (frame.label_end_date.iloc[train].max() >= frame.Date.iloc[valid].min()
                or np.intersect1d(train, valid).size or (train >= valid.min()).any()):
            raise ValueError('Inner labels overlap validation boundary')


def dynamic_error_tables(candidates, book, output):
    table = []
    for name, rows in candidates.items():
        joined = rows.merge(book[['Date', 'horizon_sigma']], on='Date', validate='one_to_one')
        # Fixed buckets, no target-conditioned or retrospective regime detection.
        joined['volatility_bucket'] = pd.cut(np.expm1(joined.horizon_sigma), [-np.inf, .03, .05, np.inf],
                                            labels=['upper_threshold_below3pct', 'upper_threshold_3to5pct', 'upper_threshold_above5pct'])
        for grouping in ['outer_fold', 'year', 'volatility_bucket']:
            if grouping == 'year':
                joined['year'] = joined.Date.dt.year
            for value, part in joined.groupby(grouping, observed=True):
                m = exp.prediction_metrics(part)
                matrix = np.asarray(m['confusion_matrix'])
                for code, label in enumerate(['bear', 'side', 'bull']):
                    support, signals, tp = matrix[code].sum(), matrix[:, code].sum(), matrix[code, code]
                    table.append(dict(candidate=name, grouping=grouping, group=str(value), label=label,
                        n_rows=len(part), support=int(support), signals=int(signals), hits=int(tp),
                        missed=int(support-tp), false_alarms=int(signals-tp),
                        precision=float(tp/signals) if signals else None, recall=float(tp/support) if support else None,
                        f1=float(2*tp/(support+signals)) if support+signals else 0.,
                        macro_f1=m['f1_macro']))
    pd.DataFrame(table).to_csv(output/'error_analysis.csv', index=False)


def run_dynamic_tuning(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir', type=Path, default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report', type=Path, default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--trials', type=int, default=24)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if args.trials < 2:
        parser.error('Require at least two trials including frozen warm start')
    parent = json.loads((args.parent_dir/'plan.json').read_text())
    for path, digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError('Parent source changed: '+path)
    inherited = exp.parse_args(['--reference-report', str(args.reference_report), '--data-dir', str(args.data_dir),
        '--base-feature-set', 'close-etf', '--feature-groups', 'trend', 'risk', '--train-windows', '3y',
        '--models', 'LightGBM', '--horizons', '20', '--inner-splits', '3', '--refit-sessions', '63'])
    frames, jobs, plan = exp.prepare_experiment(inherited)
    if plan['errors']:
        raise ValueError(str(plan['errors']))
    index, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    book = labels.build_label_book(index)
    frame = labels.relabel_cohort(frames[20], book, 'vol_1sigma')
    known = args.parent_dir/'vol_1sigma'
    baseline = pd.read_csv(known/'trend_predictions.csv', parse_dates=['Date', 'label_end_date'])
    validation = np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date', 'label_end_date', 'label']:
        np.testing.assert_array_equal(frame.iloc[validation][key], baseline[key])
    inner_audits = []
    for job in jobs:
        for outer in job['folds']:
            tuning = frame.iloc[outer['tune']].reset_index(drop=True)
            inner = exp.base.purged_folds(tuning, 3)
            boundary = frame.Date.iloc[outer['blocks'][0]['validation'][0]]
            assert_dynamic_inner_timing(tuning, inner, boundary)
            outer['inner'] = inner
            inner_audits.append(dict(group=job['group'], fold=outer['fold'], outer_boundary=str(boundary.date()),
                max_tuning_label_end=str(tuning.label_end_date.max().date()),
                inner=[dict(train_label_end=str(tuning.label_end_date.iloc[t].max().date()),
                            validation_start=str(tuning.Date.iloc[v].min().date()), n_train=len(t), n_validation=len(v)) for t, v in inner]))
    output = args.output_dir or ROOT/'reports/regime_dynamic_tuning'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    input_paths = [args.parent_dir/'plan.json', args.parent_dir/'report.json', *known.glob('*.csv'), *known.glob('*refits.json')]
    hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    plan.update(mode='adaptive_target_nested_inner_tuning_DEVELOPMENT', source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parent_hashes=hashes, label_rule=parent['label_rule'], trials_per_group_per_outer=args.trials, seed=42,
        search_space='Unchanged base._optuna_lightgbm; balanced class weights, two CPU threads. One frozen-parameter warm-start trial plus TPE search.',
        optimization='0.5*mean(inner macro F1) + 0.25*min(inner macro F1) + 0.25*min(mean inner bear F1, mean inner bull F1)',
        candidate_rules=['Best robustness objective', 'Best inner mean macro F1 among the SAME robustness-search trials'],
        mixtures='Equal trend/risk, then fixed 50/50 mix with unchanged expanding raw/normalized quantile experts. No outer weight selection.',
        acceptance='Within dynamic target only: mean F1 gain >=.01, no decline in worst fold or mean bear/bull F1, MCC gain, >=3 fold wins versus frozen blend. Paired20/60 block lower bounds >0 also required for provisional robust evidence; never independent acceptance.',
        inner_timing=inner_audits, uncertainty={'blocks': [20,60], 'repeats':1000,'seed':42},
        caveat='Repeated historical development. Both target and original pipeline chosen after prior outer inspection. No calibrated probability claim, new threshold, fresh holdout or deployment.')
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('Output: '+str(output.resolve()), flush=True)
    old_candidates = {}
    for name in ['legacy_equal', 'blend_expanding']:
        old_candidates['frozen_'+name] = pd.read_csv(known/(name+'_predictions.csv'), parse_dates=['Date', 'label_end_date'])
    dynamic_error_tables(old_candidates, book, output)
    if args.audit_only:
        return output
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    fitted, tuning_records = {}, []
    for job in jobs:
        group = job['group']
        records = {name: [] for name in ['robust', 'macro']}
        for outer in job['folds']:
            tuning = frame.iloc[outer['tune']].reset_index(drop=True)
            X, y = tuning[job['names']].to_numpy(dtype=np.float32), tuning.label.to_numpy(dtype=int)
            def objective(trial):
                params = exp.base._optuna_lightgbm(trial)
                metrics = []
                for train, valid in outer['inner']:
                    model = exp.base.create_model('LightGBM', params)
                    model.fit(X[train], y[train])
                    metrics.append(exp.base.classification_metrics(y[valid], model.predict(X[valid]), y[train]))
                trial.set_user_attr('fold_metrics', metrics)
                trial.set_user_attr('mean_macro', float(np.mean([m['f1_macro'] for m in metrics])))
                return dynamic_inner_score(metrics)
            study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
            frozen = next(r['best_params'] for r in parent['classifier_parameters'][group] if r['outer_fold'] == outer['fold'])
            study.enqueue_trial({k:v for k,v in frozen.items() if k not in ['class_weight','random_state','n_jobs','verbosity']})
            print(f'Tuning {group} fold {outer["fold"]}: {args.trials} trials x 3 purged inner folds', flush=True)
            study.optimize(objective, n_trials=args.trials)
            best = {'robust': study.best_trial, 'macro': max(study.trials, key=lambda t:t.user_attrs['mean_macro'])}
            trials = [dict(number=t.number, params=t.params, robust=t.value, **t.user_attrs) for t in study.trials]
            (output/f'{group}_fold{outer["fold"]}_trials.json').write_text(json.dumps(trials, indent=2)+'\n')
            for rule, trial in best.items():
                params = exp.base._optuna_lightgbm(trial)
                tuning_records.append(dict(group=group, fold=outer['fold'], rule=rule, trial=trial.number,
                    robust=trial.value, mean_macro=trial.user_attrs['mean_macro'], parameters=params))
                for number, block in enumerate(outer['blocks'], 1):
                    train, valid = frame.iloc[block['train']], frame.iloc[block['validation']]
                    if train.label_end_date.max() >= valid.Date.min():
                        raise ValueError('Unmatured classifier refit')
                    model, _ = exp.base.fit_selected_candidate(dict(model_name='LightGBM', best_params=params), train, job['names'])
                    rows = valid[['Date','label_end_date','label','future_return']].copy()
                    rows[experts.PROBS] = model.predict_proba(valid[job['names']].to_numpy(dtype=np.float32))
                    rows['majority'] = np.bincount(train.label, minlength=3).argmax()
                    rows['outer_fold'], rows['refit_block'] = outer['fold'], number
                    rows['train_label_end'] = str(train.label_end_date.max().date())
                    rows['inner_selected_trial'] = trial.number
                    records[rule].append(rows)
            print(f'Finished {group} fold {outer["fold"]}; inner chosen trials '+str({k:v.number for k,v in best.items()}), flush=True)
        for rule, chunks in records.items():
            fitted[(rule,group)] = pd.concat(chunks, ignore_index=True)
            fitted[(rule,group)].to_csv(output/f'{rule}_{group}_scores.csv', index=False)
        (output/'selected_parameters.json').write_text(json.dumps(tuning_records, indent=2)+'\n')
    masses = []
    for name in ['expanding_raw','expanding_normalized']:
        part = pd.read_csv(known/(name+'_mapped_predictions.csv'), parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:
            np.testing.assert_array_equal(baseline[key], part[key])
        raw = part[experts.PROBS].to_numpy()/part[['base_bear','base_side','base_bull']].to_numpy()
        raw /= raw.sum(axis=1, keepdims=True)
        masses.append(raw)
    density = np.mean(masses, axis=0)
    candidates = dict(old_candidates)
    for rule in ['robust','macro']:
        first, second = fitted[(rule,'trend')], fitted[(rule,'risk')]
        for key in ['Date','label_end_date','label','outer_fold','majority']:
            np.testing.assert_array_equal(first[key], second[key])
        equal = (first[experts.PROBS].to_numpy()+second[experts.PROBS].to_numpy())/2
        for name, scores in [(rule+'_equal', equal), (rule+'_blend', .5*equal+.5*density)]:
            np.testing.assert_allclose(scores.sum(axis=1), 1.)
            result, rows = experts.expert_metrics(name, first, scores.argmax(axis=1))
            candidates[name] = rows
    results = []
    for name, rows in candidates.items():
        source = baseline.copy()
        for key in ['Date','label_end_date','label','outer_fold']:
            np.testing.assert_array_equal(source[key], rows[key])
        result, _ = experts.expert_metrics(name, source, rows.prediction.to_numpy())
        results.append(result)
        rows.to_csv(output/(name+'_predictions.csv'), index=False)
    dynamic_error_tables(candidates, book, output)
    control = next(r for r in results if r['candidate'] == 'frozen_blend_expanding')
    groups = [np.flatnonzero(baseline.outer_fold.to_numpy()==f) for f in sorted(baseline.outer_fold.unique())]
    y = baseline.label.to_numpy(dtype=int)
    intervals, comparisons = [], []
    for r in results:
        if r['candidate'].startswith('frozen_'):
            continue
        mean_class = lambda entry,c:float(np.mean([f['per_class'][c]['f1-score'] for f in entry['folds']]))
        wins = sum(f['f1_macro']>c['f1_macro'] for f,c in zip(r['folds'], control['folds']))
        gate = (r['mean_f1']>=control['mean_f1']+.01 and r['worst_f1']>=control['worst_f1']
                and r['mean_mcc']>control['mean_mcc'] and wins>=3
                and all(mean_class(r,c)>=mean_class(control,c) for c in ['bear','bull']))
        comparisons.append(dict(candidate=r['candidate'], fold_wins=wins, point_screen=bool(gate)))
        a = candidates[r['candidate']].prediction.to_numpy(dtype=int)
        b = candidates['frozen_blend_expanding'].prediction.to_numpy(dtype=int)
        for length in [20,60]:
            rng, deltas = np.random.default_rng(42), []
            for _ in range(1000):
                sampled=[]
                for ids in groups:
                    starts=rng.integers(0,len(ids),size=int(np.ceil(len(ids)/length)))
                    sampled.append(ids[((starts[:,None]+np.arange(length))%len(ids)).ravel()[:len(ids)]])
                deltas.append(fold_f1(y,a,sampled)-fold_f1(y,b,sampled))
            low,high=np.quantile(deltas,[.025,.975])
            intervals.append(dict(candidate=r['candidate'],block=length,delta=r['mean_f1']-control['mean_f1'],low=float(low),high=float(high)))
    for row in comparisons:
        row['provisional_robust_evidence']=bool(row['point_screen'] and all(i['low']>0 for i in intervals if i['candidate']==row['candidate']))
    (output/'report.json').write_text(json.dumps(dict(role='Previously inspected historical DEVELOPMENT only', results=results,comparisons=comparisons,paired_intervals=intervals),indent=2)+'\n')
    pd.DataFrame([{k:r[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']} for r in results]).to_csv(output/'comparison.csv',index=False)
    print(pd.read_csv(output/'comparison.csv').to_string(index=False),flush=True)
    print('Done. DEVELOPMENT only; no automatic promotion. '+str(output.resolve()),flush=True)
    return output


if __name__ == '__main__':
    run_dynamic_tuning()
