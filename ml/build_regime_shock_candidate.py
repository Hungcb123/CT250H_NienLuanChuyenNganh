"""Fit one full native candidate at the latest reviewed historical session.

Freezes the latest previously chosen configuration without a new outer search.
This is a snapshot/backfill preview, NOT a prospective prediction or promotion.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

import experiment_regime as exp
import experiment_regime_information as information
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_directional import directional_features
from experiment_regime_temporal_fusion import GRID
from export_regime_shock_native import export_shock_block, ROOT, PARITY, PARENT, INFO, SHOCK
from regime_shock_features import completed_shock_features
from regime_shock_native import shock_file_digest
from regime_shock_score_runtime import RECIPE_ID, ShockScoreRuntime


def build_shock_candidate(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    frozen = json.loads((PARITY/'sources.json').read_text())
    for name, digest in frozen.items():
        if shock_file_digest(name) != digest:
            raise ValueError('Frozen source changed: '+name)
    config = SimpleNamespace(reference_report=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json',
                             control_dir=ROOT/'reports/regime_experiments/20261017T141838_654956Z',
                             data_dir=ROOT/'data/research/brokers_2010_20261001_reviewed', trials=1, timeout=1)
    full, audits = completed_shock_features(config.data_dir)
    boundary = full.Date.max()
    dframe, jobs, _, dplan = density.prepare_return_distribution(config)
    market, _ = exp.base.load_market_data(config.data_dir/'VNINDEX.csv')
    book = labels.build_label_book(market)
    dframe = labels.relabel_cohort(dframe, book, 'vol_1sigma')
    iframe, variants, _, _ = information.prepare_information(config)
    iframe = labels.relabel_cohort(iframe, book, 'vol_1sigma')
    cargs = exp.parse_args(['--reference-report', str(config.reference_report), '--data-dir', str(config.data_dir),
                           '--base-feature-set', 'close-etf', '--feature-groups', 'trend', 'risk',
                           '--train-windows', '3y', '--models', 'LightGBM', '--horizons', '20'])
    frames, _, cplan = exp.prepare_experiment(cargs)
    if cplan['errors']:
        raise ValueError(str(cplan['errors']))
    cframe = labels.relabel_cohort(frames[20], book, 'vol_1sigma')
    extras = directional_features(market)
    shock_names = jobs['expanding']['names']+[n for n in extras if n != 'Date']
    dframe = dframe.merge(extras, on='Date', how='left', validate='one_to_one', sort=False)
    # Full completed-close builder must reproduce all archived training features.
    feature_error = 0.
    for frame in [dframe, iframe, cframe]:
        columns = [n for n in full if n in frame and n != 'Date' and not n.startswith('VIX_Observation') and not n.startswith('VIX_Available')]
        old = frame.set_index('Date')[columns].to_numpy(dtype=float)
        actual = full.set_index('Date').loc[frame.Date, columns].to_numpy(dtype=float)
        np.testing.assert_allclose(actual, old, atol=1e-12, rtol=1e-12, equal_nan=True)
        finite = np.isfinite(old) & np.isfinite(actual)
        if finite.any():
            feature_error = max(feature_error, float(np.max(np.abs(actual[finite]-old[finite]))))
    parent = json.loads((PARENT/'plan.json').read_text())
    choices = json.loads((INFO/'inner_selection.json').read_text())
    choice = max(choices, key=lambda c: c['fold'])
    fold = choice['fold']
    if pd.Timestamp(choice['latest_tuning_label_end']) >= boundary:
        raise ValueError('Unmatured frozen information configuration')
    groups = dict(variants)
    specs = {g: dict(names=(groups[choice['chosen']]['names'] if g == 'trend' else cplan['feature_groups']['risk']),
                     parameters=next(r['best_params'] for r in parent['classifier_parameters'][g] if r['outer_fold'] == fold))
             for g in ['trend', 'risk']}
    classifiers = dict(trend=iframe.iloc[exp.training_indices(iframe, boundary, '3y')],
                       risk=cframe.iloc[exp.training_indices(cframe, boundary, '3y')])
    train = dframe.iloc[exp.training_indices(dframe, boundary, 'expanding')]
    selection = ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z/selection.json'
    anchor = next(a for a in json.loads(selection.read_text()) if a['fold'] == fold)
    if pd.Timestamp(anchor['latest_tuning_label_end']) >= boundary:
        raise ValueError('Unmatured frozen fusion configuration')
    parameters = GRID[anchor['chosen']['robust']]
    params = json.loads((SHOCK/'plan.json').read_text())['parameters']
    paths = [Path(__file__), ROOT/'export_regime_shock_native.py', ROOT/'regime_shock_native.py',
             ROOT/'regime_shock_features.py', ROOT/'regime_shock_score_runtime.py', PARITY/'sources.json', selection]
    provenance = {str(p.resolve()): shock_file_digest(p) for p in paths}
    output = args.output_dir or ROOT/'artifacts'/('regime_shock_candidate_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    output.mkdir(parents=True, exist_ok=False)
    print('Candidate: '+str(output), flush=True)
    bundle = export_shock_block(output/'native', boundary, train, classifiers, specs,
                                jobs['expanding']['names'], shock_names, dplan['specification'],
                                params, provenance)
    names = list(dict.fromkeys(n for item in bundle.meta['models'] for n in item['features']))
    valid = full.loc[full.Date.eq(boundary)]
    components = bundle.predict_components({n: valid[n].to_numpy() for n in names}, valid.horizon_sigma.to_numpy())
    runtime = ShockScoreRuntime('VNINDEX:'+RECIPE_ID+':'+json.dumps(list(parameters), separators=(',', ':')))
    pos = full.index[full.Date.eq(boundary)][0]
    preview = runtime.predict(str(boundary.date()), str(full.Date.iloc[pos-1].date()),
                               {n: s[0] for n, s in components.items()}, parameters)
    preview.update(role='historical_snapshot_cold_start_preview', independent_prospective_prediction=False,
                   calibrated_probability=None, deployed=False)
    contract = dict(candidate_id='shock_shrink_native_snapshot_v1', created_at=datetime.now(timezone.utc).isoformat(),
                    data_as_of=str(boundary.date()), bundle='native', recipe_id=RECIPE_ID,
                    information_group=choice['chosen'], fusion_parameters=list(parameters),
                    configuration_policy='Fixed latest prior-fold classifier/feature/fusion configuration; no new score-driven search.',
                    component_models=len(bundle.meta['models']), feature_builder_parity_max_error=feature_error,
                    class_scores_are_probabilities=False, native_model_weights_exported=True,
                    source_receipts=frozen, provenance=provenance, independent_test=False, accepted=False, deployed=False,
                    status='Historical research snapshot; needs fresh inputs, serving refit policy, probability evaluation and prospective scoring.')
    (output/'contract.json').write_text(json.dumps(contract, indent=2)+'\n')
    (output/'preview.json').write_text(json.dumps(preview, indent=2)+'\n')
    (output/'input_audits.json').write_text(json.dumps(audits, indent=2, default=str)+'\n')
    (output/'checksums.json').write_text(json.dumps({str(p.relative_to(output)): shock_file_digest(p)
                                                   for p in sorted(output.rglob('*')) if p.is_file()}, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), boundary=str(boundary.date()), models=len(bundle.meta['models']),
                         feature_parity_max_error=feature_error, independent_test=False, deployed=False), indent=2), flush=True)
    return output


if __name__ == '__main__':
    build_shock_candidate()
