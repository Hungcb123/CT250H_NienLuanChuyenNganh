"""Export complete native shock components; verify against frozen research scores.

Historical replay only. No outer tuning, probability claim or web deployment.
"""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import f1_score

import experiment_regime as exp
import experiment_regime_information as information
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_analog_density import COMPACT
from experiment_regime_directional import directional_features
from regime_shock_native import ShockNativeBundle, shock_file_digest
from regime_shock_score_runtime import RECIPE_ID, ShockScoreRuntime


ROOT = Path(__file__).resolve().parent
PARITY = ROOT/'reports/regime_runtime_parity/20261019T090001_796250Z'
PARENT = ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z'
INFO = ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z'
SHOCK = ROOT/'reports/regime_shock_forest/20261019T072038_455776Z'


def export_shock_block(directory, boundary, density_train, classifier_trains,
                       classifier_specs, density_names, shock_names, specification,
                       forest_parameters, provenance, seeds=(7, 21, 42, 84, 126)):
    """Train only mature rows, persist every distribution ingredient, then reload."""
    directory = Path(directory)
    if directory.exists():
        raise ValueError('Refusing to overwrite a native bundle')
    directory.parent.mkdir(parents=True, exist_ok=True)
    boundary = pd.Timestamp(boundary)
    trains = [density_train, *classifier_trains.values()]
    for train in trains:
        if len(train) < 30 or train.label_end_date.max() >= boundary or train.Date.max() >= boundary:
            raise ValueError('Training labels not strictly mature at refit')
        if set(train.label.astype(int)) != {0, 1, 2}:
            raise ValueError('Missing mature class')
    temp = Path(tempfile.mkdtemp(prefix='building_', dir=directory.parent))
    entries = []; receipts = []
    for name, train in [('density', density_train), *classifier_trains.items()]:
        receipts.append(dict(name=name, rows=len(train), start=str(train.Date.min().date()),
                             latest_label_end=str(train.label_end_date.max().date()),
                             cohort_sha256=__import__('hashlib').sha256(train[['Date', 'label_end_date', 'label']].to_csv(index=False).encode()).hexdigest()))
    # Two classifiers use their original common cohort/3-year policy.
    for group, spec in classifier_specs.items():
        train = classifier_trains[group]; names = spec['names']
        model = lgb.LGBMClassifier(**spec['parameters']).fit(train[names].to_numpy(dtype=np.float32), train.label.to_numpy(dtype=np.int64))
        if list(model.classes_) != [0, 1, 2]:
            raise ValueError('Unexpected classifier ordering')
        filename = group+'.txt'; model.booster_.save_model(str(temp/filename))
        native = lgb.Booster(model_file=str(temp/filename))
        x = train[names].iloc[-3:].to_numpy(dtype=np.float32)
        np.testing.assert_allclose(model.predict_proba(x), native.predict(x, num_threads=2), atol=1e-12, rtol=1e-12)
        entries.append(dict(kind='classifier', file=filename, features=names))
    raw = density_train.future_log_return.to_numpy(dtype=float)
    sigma = density_train.horizon_sigma.to_numpy(dtype=float)
    if not np.isfinite(raw).all() or not np.isfinite(sigma).all() or (sigma <= 0).any():
        raise ValueError('Invalid mature return atoms')
    store = dict(raw_returns=raw, normalized_returns=raw/sigma)
    x = density_train[density_names].to_numpy(dtype=np.float32)
    for seed in seeds:
        for normalized in [False, True]:
            y = raw/sigma if normalized else raw
            for alpha in specification['quantile_levels']:
                params = dict(specification['parameters'], random_state=seed)
                model = lgb.LGBMRegressor(**params, alpha=alpha).fit(x, y)
                filename = f'quantile_{seed}_{int(normalized)}_{alpha:.2f}.txt'
                model.booster_.save_model(str(temp/filename))
                native = lgb.Booster(model_file=str(temp/filename))
                np.testing.assert_allclose(model.predict(x[-3:]), native.predict(x[-3:], num_threads=2), atol=1e-12, rtol=1e-12)
                entries.append(dict(kind='quantile', file=filename, features=density_names,
                                    seed=seed, normalized=normalized, alpha=alpha))
    for group, names, architectures in [('forest', density_names, ['mean']),
                                        ('magnitude', density_names, ['magnitude']),
                                        ('shock', shock_names, ['mean', 'magnitude'])]:
        x = density_train[names].to_numpy(dtype=np.float32)
        for architecture in architectures:
            for normalized in [False, True]:
                y = raw/sigma if normalized else raw
                target = y
                if architecture == 'magnitude':
                    target = np.column_stack([y, np.abs(y)])
                    target = (target-target.mean(axis=0))/target.std(axis=0, ddof=1)
                model = RandomForestRegressor(**forest_parameters).fit(x, target)
                filename = f'{group}_{architecture}_{int(normalized)}.joblib'
                joblib.dump(model, temp/filename, compress=3)
                loaded = joblib.load(temp/filename)
                np.testing.assert_array_equal(model.apply(x[-3:]), loaded.apply(x[-3:]))
                key = filename.removesuffix('.joblib')+'_leaves'
                store[key] = model.apply(x)
                entries.append(dict(kind='forest', group=group, file=filename, features=names,
                                    normalized=normalized, leaf_key=key))
    views = dict(compact=list(COMPACT), full=density_names)
    for view, names in views.items():
        x = density_train[names].to_numpy(dtype=float)
        if not np.isfinite(x).all():
            raise ValueError('Nonfinite analog training view')
        center = np.median(x, axis=0); q = np.quantile(x, [.25, .75], axis=0)
        scale = np.where(q[1]-q[0] > 1e-12, q[1]-q[0], 1.)
        store[view+'_center'], store[view+'_scale'] = center, scale
        store[view+'_scaled'] = (x-center)/scale
    np.savez_compressed(temp/'empirical.npz', **store)
    prior = np.bincount(density_train.label.to_numpy(dtype=int), minlength=3)/len(density_train)
    meta = dict(schema=1, recipe_id=RECIPE_ID, asset='VNINDEX', boundary=str(boundary.date()),
                environment={p: version(p) for p in ['numpy', 'scipy', 'scikit-learn', 'lightgbm', 'joblib']},
                density_prior=prior.tolist(), quantile_atom_weights=specification['quantile_atom_weights'],
                models=entries, analog_views=views, training_receipts=receipts,
                provenance=provenance, score_semantics='decision_scores_not_calibrated_probabilities',
                files={p.name: shock_file_digest(p) for p in sorted(temp.iterdir())})
    (temp/'bundle.json').write_text(json.dumps(meta, indent=2)+'\n')
    (temp/'bundle.sha256').write_text(shock_file_digest(temp/'bundle.json')+'\n')
    os.rename(temp, directory)
    return ShockNativeBundle(directory)


def replay_shock_native(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--limit-blocks', type=int, default=None)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    if args.limit_blocks is not None and args.limit_blocks < 1:
        parser.error('limit-blocks must be positive')
    config = SimpleNamespace(reference_report=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json',
                             control_dir=ROOT/'reports/regime_experiments/20261017T141838_654956Z',
                             data_dir=ROOT/'data/research/brokers_2010_20261001_reviewed', trials=1, timeout=1)
    # Check source receipts before training; runtime never reads these archives.
    for name, digest in json.loads((PARITY/'sources.json').read_text()).items():
        if shock_file_digest(name) != digest:
            raise ValueError('Frozen research source changed: '+name)
    checksums = json.loads((PARITY/'checksums.json').read_text())
    for name, digest in checksums.items():
        if shock_file_digest(PARITY/name) != digest:
            raise ValueError('Changed replay fixture: '+name)
    dframe, djobs, _, dplan = density.prepare_return_distribution(config)
    index, _ = exp.base.load_market_data(config.data_dir/'VNINDEX.csv')
    book = labels.build_label_book(index)
    dframe = labels.relabel_cohort(dframe, book, 'vol_1sigma')
    iframe, variants, _, _ = information.prepare_information(config)
    iframe = labels.relabel_cohort(iframe, book, 'vol_1sigma')
    cargs = exp.parse_args(['--reference-report', str(config.reference_report), '--data-dir', str(config.data_dir),
                           '--base-feature-set', 'close-etf', '--feature-groups', 'trend', 'risk',
                           '--train-windows', '3y', '--models', 'LightGBM', '--horizons', '20', '--refit-sessions', '63'])
    frames, cjobs, cplan = exp.prepare_experiment(cargs)
    if cplan['errors']:
        raise ValueError(str(cplan['errors']))
    cframe = labels.relabel_cohort(frames[20], book, 'vol_1sigma')
    extras = directional_features(index)
    shock_names = djobs['expanding']['names'] + [n for n in extras if n != 'Date']
    dframe = dframe.merge(extras, on='Date', how='left', validate='one_to_one', sort=False)
    parent = json.loads((PARENT/'plan.json').read_text())
    choices = {x['fold']: x for x in json.loads((INFO/'inner_selection.json').read_text())}
    vjobs = dict(variants)
    params = json.loads((SHOCK/'plan.json').read_text())['parameters']
    base = pd.read_csv(SHOCK/'shock_shrink_predictions.csv', parse_dates=['Date', 'label_end_date'])
    with np.load(PARITY/'historical_component_fixture.npz', allow_pickle=False) as fixture:
        expected = {key: fixture[key] for key in fixture.files}
    np.testing.assert_array_equal(expected['dates'], base.Date.dt.strftime('%Y-%m-%d'))
    provenance = {str(p.resolve()): shock_file_digest(p) for p in [Path(__file__), ROOT/'regime_shock_native.py',
                  ROOT/'regime_shock_score_runtime.py', PARITY/'sources.json', PARITY/'checksums.json']}
    output = args.output_dir or ROOT/'reports/regime_shock_native'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if args.resume:
        if json.loads((output/'provenance.json').read_text()) != provenance:
            raise ValueError('Resume source code changed')
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    print('Output: '+str(output), flush=True)
    runtime = ShockScoreRuntime('VNINDEX:shock_shrink:native-replay:'+RECIPE_ID)
    audits = []; records = []; total = 0; calendar = pd.DatetimeIndex(index.Date)
    for outer in djobs['expanding']['folds']:
        fold = outer['fold']; choice = choices[fold]
        if pd.Timestamp(choice['latest_tuning_label_end']) >= pd.Timestamp(choice['outer_boundary']):
            raise ValueError('Unmatured classifier feature selection')
        for number, block in enumerate(outer['blocks'], 1):
            if args.limit_blocks is not None and total >= args.limit_blocks:
                break
            train, valid = dframe.iloc[block['train']], dframe.iloc[block['validation']]
            boundary = valid.Date.min()
            ifold = next(o for o in vjobs[choice['chosen']]['folds'] if o['fold'] == fold)
            cfold = next(o for o in cjobs[0]['folds'] if o['fold'] == fold)
            iblock, cblock = ifold['blocks'][number-1], cfold['blocks'][number-1]
            ct = dict(trend=iframe.iloc[iblock['train']], risk=cframe.iloc[cblock['train']])
            specs = {g: dict(names=(vjobs[choice['chosen']]['names'] if g == 'trend' else cplan['feature_groups']['risk']),
                             parameters=next(r['best_params'] for r in parent['classifier_parameters'][g] if r['outer_fold'] == fold))
                     for g in ['trend', 'risk']}
            for frame, ids in [(iframe, iblock['validation']), (cframe, cblock['validation'])]:
                np.testing.assert_array_equal(frame.Date.iloc[ids], valid.Date)
            directory = output/'bundles'/f'fold{fold}_block{number}_{boundary.date()}'
            if args.resume and directory.exists():
                bundle = ShockNativeBundle(directory)
                if bundle.meta['provenance'] != provenance:
                    raise ValueError('Cached bundle provenance changed')
            else:
                bundle = export_shock_block(directory, boundary, train, ct, specs,
                                            djobs['expanding']['names'], shock_names,
                                            dplan['specification'], params, provenance)
            # Build inputs from market-derived feature tables; exclude ALL outcomes.
            fields = list(dict.fromkeys(n for item in bundle.meta['models'] for n in item['features']))
            combined = valid.set_index('Date').copy()
            for field in fields:
                if field not in combined:
                    combined[field] = iframe.set_index('Date').loc[valid.Date, field].to_numpy()
            components = bundle.predict_components({n: combined[n].to_numpy() for n in fields}, valid.horizon_sigma.to_numpy())
            mask = base.Date.isin(valid.Date).to_numpy(); ids = np.flatnonzero(mask)
            np.testing.assert_array_equal(base.Date.iloc[ids], valid.Date)
            errors = {}
            for name, score in components.items():
                np.testing.assert_allclose(score, expected[name][mask], rtol=1e-10, atol=1e-10,
                                           err_msg=f'fold{fold}/block{number}/{name}')
                errors[name] = float(np.max(np.abs(score-expected[name][mask])))
            for i, (rowid, session) in enumerate(zip(ids, valid.Date)):
                state = json.loads(json.dumps(runtime.dump_state()))
                runtime = ShockScoreRuntime(state['stream_id']); runtime.restore_state(state)
                pos = calendar.get_indexer([session])[0]
                answer = runtime.predict(str(session.date()), str(calendar[pos-1].date()) if pos else None,
                                         {name: score[i] for name, score in components.items()}, expected['parameters'][rowid])
                np.testing.assert_allclose(answer['class_scores'], base.loc[rowid, ['p_bear', 'p_side', 'p_bull']].to_numpy(dtype=float), atol=1e-10, rtol=1e-10)
                records.append(dict(Date=str(session.date()), outer_fold=fold,
                                    label=int(base.label.iloc[rowid]), prediction=answer['signal']+1,
                                    **dict(zip(['p_bear', 'p_side', 'p_bull'], answer['class_scores']))))
            total += 1
            audits.append(dict(fold=fold, block=number, rows=len(valid), bundle=str(directory),
                               models=len(bundle.meta['models']), max_component_errors=errors,
                               training_receipts=bundle.meta['training_receipts']))
            pd.DataFrame(records).to_csv(output/'native_predictions.csv', index=False)
            (output/'block_audits.json').write_text(json.dumps(audits, indent=2)+'\n')
            print(f'Native fold{fold} block{number}: {len(records)}/1560 rows, component parity OK', flush=True)
        if args.limit_blocks is not None and total >= args.limit_blocks:
            break
    rows = pd.DataFrame(records)
    folds = [dict(fold=int(f), rows=len(part), f1=float(f1_score(part.label, part.prediction, labels=[0, 1, 2], average='macro', zero_division=0)))
             for f, part in rows.groupby('outer_fold')]
    summary = dict(rows=len(rows), blocks=total, complete=len(rows) == 1560,
                   native_model_weights_exported=True, all_component_parity=True,
                   all_decisions_match=bool(np.array_equal(rows.prediction, base.iloc[:len(rows)][['p_bear', 'p_side', 'p_bull']].to_numpy().argmax(axis=1))),
                   folds=folds, mean_f1=float(np.mean([f['f1'] for f in folds])) if len(rows) == 1560 else None,
                   prospective_configuration_frozen=False, independent_test=False, deployed=False)
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (output/'state.json').write_text(json.dumps(runtime.dump_state(), indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)
    return output


if __name__ == '__main__':
    replay_shock_native()
