"""Matched fixed/dynamic target experiment. Historical development only.

Retrain classifiers; reuse label-independent archived return quantiles only after
checking their complete refit cohorts. Never reuse fixed-label class priors.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_multiclass_reuse as reuse
import experiment_regime_return_distribution as density
import experiment_regime_expert_selection as selector
from audit_regime_expert_selection import fold_f1

ROOT = Path(__file__).resolve().parent


def dynamic_quantile_mass(points, weights, lower, upper):
    """Map saved log-return atoms to per-date causal boundaries, equality neutral."""
    points = np.asarray(points, dtype=float)
    weights = np.asarray(weights, dtype=float)
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    if (points.ndim != 2 or weights.shape != (points.shape[1],)
            or lower.shape != (len(points),) or upper.shape != lower.shape):
        raise ValueError('Quantile/boundary shape mismatch')
    if (not all(np.isfinite(v).all() for v in [points, weights, lower, upper])
            or (lower >= upper).any() or (weights < 0).any()
            or not np.isclose(weights.sum(), 1.) or (np.diff(points, axis=1) < 0).any()):
        raise ValueError('Invalid quantile atoms/boundaries')
    bear, bull = points < lower[:, None], points > upper[:, None]
    return np.column_stack([(mask * weights).sum(axis=1) for mask in [bear, ~(bear | bull), bull]])


def run_dynamic_expert_study(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report', type=Path, default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir', type=Path, default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--classifier-dir', type=Path, default=ROOT/'reports/regime_multiclass_reuse/20261018T151747_040696Z')
    parser.add_argument('--density-dir', type=Path, default=ROOT/'reports/regime_return_distribution/20261018T155423_383833Z')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    inherited = exp.parse_args(['--reference-report', str(args.reference_report), '--data-dir', str(args.data_dir),
        '--base-feature-set', 'close-etf', '--feature-groups', 'trend', 'risk', '--train-windows', '3y',
        '--models', 'LightGBM', '--horizons', '20', '--refit-sessions', '63'])
    frames, classifier_jobs, plan = exp.prepare_experiment(inherited)
    if plan['errors']:
        raise ValueError(str(plan['errors']))
    frame = frames[20]
    index, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    book = labels.build_label_book(index)
    dynamic_frame = labels.relabel_cohort(frame, book, 'vol_1sigma')
    density_frame, density_jobs, _, density_plan = density.prepare_return_distribution(SimpleNamespace(
        reference_report=args.reference_report, data_dir=args.data_dir, control_dir=args.control_dir))
    archived_plan = json.loads((args.density_dir/'plan.json').read_text())
    if (archived_plan['input_hashes'] != plan['input_hashes']
            or archived_plan['specification'] != density_plan['specification']
            or archived_plan['feature_groups']['trend'] != density_plan['feature_groups']['trend']
            or archived_plan['source_sha256'] != hashlib.sha256(Path(density.__file__).read_bytes()).hexdigest()):
        raise ValueError('Cached return learner/data specification changed')
    contract = json.loads((ROOT/'artifacts/regime_multiclass_candidate_20261018/contract.json').read_text())
    for name, digest in contract['source_component_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen helper changed: '+name)
    dynamic_density_frame = labels.relabel_cohort(density_frame, book, 'vol_1sigma')
    original = json.loads((args.control_dir/'experiment_report.json').read_text())
    sources = {g: next(r for r in original['results'] if r['horizon'] == 20 and r['train_window'] == '3y'
                       and r['feature_group'] == g) for g in ['trend', 'risk']}
    reference, _, _ = selector.load_expert_sources(args)
    validation = np.concatenate([b['validation'] for o in classifier_jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date', 'label_end_date', 'label']:
        np.testing.assert_array_equal(frame.iloc[validation][key], reference[key])
    thresholds = reference[['Date']].merge(book, on='Date', validate='one_to_one')
    hashes = {}
    paths = [Path(__file__), args.control_dir/'experiment_report.json', args.reference_report]
    paths += [ROOT/name for name in ['experiment_regime.py', 'experiment_regime_labels.py',
        'experiment_regime_multiclass_reuse.py', 'experiment_regime_return_distribution.py',
        'experiment_regime_expert_selection.py', 'audit_regime_expert_selection.py', 'train_regime_v2.py']]
    paths += list(args.density_dir.glob('*_predictions.csv')) + list(args.density_dir.glob('*_refits.json'))
    paths += [args.density_dir/'plan.json', args.classifier_dir/'plan.json']
    for path in paths:
        hashes[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    plan.update(mode='fixed_vs_volatility_target_heterogeneous_DEVELOPMENT', created_at=datetime.now(timezone.utc).isoformat(),
        source_hashes=hashes, optuna=None, policies=['fixed_5pct', 'vol_1sigma'],
        label_rule='log(P[t+20]/P[t]) compared to +/- std(last20 daily log returns,ddof1)*sqrt20; equality sideway',
        fixed_rule='Simple return < -.05 bear, > .05 bull, equality/otherwise sideway',
        parameter_policy='Same original fixed-label purged-inner parameters per outer fold, reused unchanged for both targets. No new tuning; dynamic task may be under-tuned.',
        classifier_parameters={g: s['inner_tuning'] for g, s in sources.items()},
        quantile_policy='Reuse archived quantiles because regression targets/features/training windows are unchanged; verify training dates, n_train and old class priors. Recompute new label priors on each original training cohort.',
        thresholds_predeclared={'lookback': 20, 'horizon': 20, 'k': 1.},
        selector_rule=selector.RULE, selector_pool=selector.POOl,
        mixtures='Equal all four densities; equal two expanding densities; each blended half with equal trend/risk classifiers. No weight search.',
        uncertainty={'paired_circular_blocks': [20, 60], 'repeats': 1000, 'seed': 42, 'comparison': 'selector or fixed expanding blend vs equal classifier, WITHIN each task only'},
        interpretation='Different target tasks: no ranking fixed F1 against dynamic F1. All inspected historical development; no independent test, calibrated probability or trading profitability claim.',
        dynamic_upper_threshold_quantiles={str(q): float(thresholds.vol_upper_simple_threshold.quantile(q)) for q in [0, .1, .5, .9, 1]},
        dynamic_upper_below_fixed_fraction=float((thresholds.vol_upper_simple_threshold < .05).mean()),
        target_transition_counts=pd.crosstab(thresholds.fixed_label, thresholds.vol_label).to_numpy().tolist(),
        target_counts={p: labels.label_counts(f.iloc[validation].label) for p, f in [('fixed_5pct', frame), ('vol_1sigma', dynamic_frame)]})
    output = args.output_dir or ROOT/'reports/regime_dynamic_experts'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    thresholds.to_csv(output/'label_thresholds.csv', index=False)
    print('Output: '+str(output.resolve()), flush=True)
    if args.audit_only:
        return output
    all_results, parity, checks = [], {}, []
    for policy, current, current_density in [('fixed_5pct', frame, density_frame), ('vol_1sigma', dynamic_frame, dynamic_density_frame)]:
        folder = output/policy
        folder.mkdir()
        classifiers = {}
        for job in classifier_jobs:
            group = job['group']
            print('Retraining '+policy+'/'+group, flush=True)
            rows, audits = reuse.run_reused(current, job, sources[group])
            if policy == 'fixed_5pct':
                old = pd.read_csv(args.classifier_dir/f'legacy_{group}_63_predictions.csv', parse_dates=['Date', 'label_end_date'])
                for key in ['Date', 'label_end_date', 'label', 'outer_fold', 'refit_block', 'majority']:
                    np.testing.assert_array_equal(rows[key], old[key])
                np.testing.assert_allclose(rows[selector.PROBS], old[selector.PROBS], atol=1e-12, rtol=1e-12)
                np.testing.assert_array_equal(rows['argmax'], old['argmax'])
                parity[group] = len(rows)
            rows.to_csv(folder/f'{group}_predictions.csv', index=False)
            (folder/f'{group}_refits.json').write_text(json.dumps(audits, indent=2)+'\n')
            classifiers[group] = rows
        base = classifiers['trend'].copy()
        for key in ['Date', 'label_end_date', 'label', 'outer_fold', 'refit_block', 'majority']:
            np.testing.assert_array_equal(base[key], classifiers['risk'][key])
        matrices = {'legacy_'+g: rows[selector.PROBS].to_numpy() for g, rows in classifiers.items()}
        matrices['legacy_equal'] = (matrices['legacy_trend']+matrices['legacy_risk'])/2
        densities = {}
        for window in ['3y', 'expanding']:
            job = density_jobs[window]
            for normalized in [False, True]:
                name = window+('_normalized' if normalized else '_raw')
                saved = pd.read_csv(args.density_dir/(name+'_predictions.csv'), parse_dates=['Date', 'label_end_date'])
                for key in ['Date', 'label_end_date', 'outer_fold']:
                    np.testing.assert_array_equal(base[key], saved[key])
                np.testing.assert_allclose(base.future_return, saved.future_return, rtol=1e-12, atol=1e-12)
                old_audits = json.loads((args.density_dir/(name+'_refits.json')).read_text())
                chunks, audit_rows = [], []
                for outer in job['folds']:
                    for number, block in enumerate(outer['blocks'], 1):
                        train, valid = current_density.iloc[block['train']], current_density.iloc[block['validation']]
                        original_train = density_frame.iloc[block['train']]
                        part = saved.loc[(saved.outer_fold == outer['fold']) & (saved.refit_block == number)].copy()
                        if train.label_end_date.max() >= valid.Date.min():
                            raise ValueError('Unmatured training supervision')
                        for key in ['Date', 'label_end_date']:
                            np.testing.assert_array_equal(part[key], valid[key])
                        np.testing.assert_allclose(part.horizon_sigma, valid.horizon_sigma, rtol=1e-12, atol=1e-12)
                        old_audit = next(a for a in old_audits if a['fold'] == outer['fold'] and a['block'] == number)
                        if (old_audit['n_train'] != len(train) or old_audit['train_label_end'] != str(train.label_end_date.max().date())
                                or old_audit['prediction_start'] != str(valid.Date.min().date())):
                            raise ValueError('Cached quantile refit cohort changed')
                        old_prior = np.bincount(original_train.label, minlength=3)/len(original_train)
                        np.testing.assert_allclose(part[density.BASE_PROBS], np.tile(old_prior, (len(part), 1)), atol=1e-12)
                        q = part[[f'ordered_log_q{round(a*100):02d}' for a in density_plan['specification']['quantile_levels']]].to_numpy()
                        if policy == 'fixed_5pct':
                            lower, upper = np.full(len(part), np.log(.95)), np.full(len(part), np.log(1.05))
                        else:
                            lower, upper = -valid.horizon_sigma.to_numpy(), valid.horizon_sigma.to_numpy()
                        mass = dynamic_quantile_mass(q, density_plan['specification']['quantile_atom_weights'], lower, upper)
                        if policy == 'fixed_5pct':
                            np.testing.assert_allclose(mass, part[density.PROBS], atol=1e-12)
                        prior = np.bincount(train.label, minlength=3)/len(train)
                        if (prior <= 0).any():
                            raise ValueError('Missing training label class')
                        balanced = mass/prior
                        balanced /= balanced.sum(axis=1, keepdims=True)
                        chunks.append(balanced)
                        part['label'] = valid.label.to_numpy()
                        part[density.PROBS] = mass
                        part[density.BASE_PROBS] = np.tile(prior, (len(part), 1))
                        part['prediction_raw'] = mass.argmax(axis=1)
                        part['prediction_prior_balanced'] = balanced.argmax(axis=1)
                        part['baseline_prediction'] = prior.argmax()
                        audit_rows.append(dict(fold=outer['fold'], block=number, n_train=len(train),
                            train_label_end=str(train.label_end_date.max().date()),
                            prediction_start=str(valid.Date.min().date()), class_prior=prior.tolist()))
                        part.to_csv(folder/(name+'_mapped_predictions.csv'), mode='a', header=not (folder/(name+'_mapped_predictions.csv')).exists(), index=False)
                densities[name] = np.concatenate(chunks)
                (folder/(name+'_refits.json')).write_text(json.dumps(audit_rows, indent=2)+'\n')
        matrices['density_all'] = np.mean(list(densities.values()), axis=0)
        matrices['density_expanding'] = (densities['expanding_raw']+densities['expanding_normalized'])/2
        for suffix in ['all', 'expanding']:
            matrices['blend_'+suffix] = .5*matrices['legacy_equal']+.5*matrices['density_'+suffix]
        for value in matrices.values():
            if not np.isfinite(value).all() or (value < 0).any():
                raise ValueError('Invalid decision scores')
            np.testing.assert_allclose(value.sum(axis=1), 1.)
        forecast, choices = selector.delayed_expert_predictions(base, matrices, index.Date)
        (folder/'selector_history.json').write_text(json.dumps(choices, indent=2)+'\n')
        predictions = {name: value.argmax(axis=1) for name, value in matrices.items()}
        predictions.update(delayed_selector=forecast, causal_training_majority=base.majority.to_numpy())
        for name, prediction in predictions.items():
            result, rows = selector.expert_metrics(name, base, prediction)
            result['label_policy'] = policy
            all_results.append(result)
            rows.to_csv(folder/(name+'_predictions.csv'), index=False)
        if policy == 'fixed_5pct':
            saved_selector = pd.read_csv(ROOT/'reports/regime_expert_selection/20261018T160007_360834Z/delayed_selector_predictions.csv')
            np.testing.assert_array_equal(forecast, saved_selector.prediction)
            parity['selector'] = len(forecast)
        for end in [390, 780, 1170, 1460, 1560]:
            prefix = base.iloc[:end].copy()
            cutoff = prefix.Date.iloc[-1]
            prefix.loc[prefix.label_end_date >= cutoff, 'label'] = 99
            value, _ = selector.delayed_expert_predictions(prefix, {k: v[:end] for k, v in matrices.items()}, index.Date[index.Date <= cutoff])
            np.testing.assert_array_equal(value, forecast[:end])
            checks.append(dict(policy=policy, rows=end, future_label_corruption_invariant=True))
        groups = [np.flatnonzero(base.outer_fold.to_numpy() == f) for f in sorted(base.outer_fold.unique())]
        y = base.label.to_numpy(dtype=int)
        intervals = []
        for candidate in ['delayed_selector', 'blend_expanding']:
            a, b = predictions[candidate], predictions['legacy_equal']
            for length in [20, 60]:
                rng, deltas = np.random.default_rng(42), []
                for _ in range(1000):
                    sample = []
                    for ids in groups:
                        starts = rng.integers(0, len(ids), size=int(np.ceil(len(ids)/length)))
                        sample.append(ids[((starts[:, None]+np.arange(length)) % len(ids)).ravel()[:len(ids)]])
                    deltas.append(fold_f1(y, a, sample)-fold_f1(y, b, sample))
                low, high = np.quantile(deltas, [.025, .975])
                intervals.append(dict(candidate=candidate, reference='legacy_equal', block_sessions=length,
                    point_delta=fold_f1(y, a, groups)-fold_f1(y, b, groups), low=float(low), high=float(high)))
        (folder/'paired_intervals.json').write_text(json.dumps(intervals, indent=2)+'\n')
        print(policy, [(r['candidate'], round(r['mean_f1'], 4), round(r['worst_f1'], 4)) for r in all_results if r['label_policy'] == policy], flush=True)
        (output/'report.json').write_text(json.dumps(dict(role='DEVELOPMENT different label tasks; no cross-task winner', results=all_results, fixed_parity=parity, prefix_checks=checks), indent=2)+'\n')
        pd.DataFrame([{k: r[k] for k in ['label_policy', 'candidate', 'mean_f1', 'worst_f1', 'mean_mcc']} for r in all_results]).to_csv(output/'comparison.csv', index=False)
    print('Done. Historical development only. '+str(output.resolve()), flush=True)
    return output


if __name__ == '__main__':
    run_dynamic_expert_study()
