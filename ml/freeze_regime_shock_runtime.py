"""Freeze a research recipe and verify streaming score composition parity.

Does not train/export model weights, select prospective parameters, or deploy.
The archive of component scores is a historical replay fixture, not inference.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from regime_component_archive import load_seed_components
from regime_shock_score_runtime import RECIPE, RECIPE_ID, ShockScoreRuntime
from experiment_regime_temporal_fusion import GRID


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT/'reports'
SHOCK = REPORTS/'regime_shock_forest/20261019T072038_455776Z'


def freeze_shock_runtime(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    base, classifier, quantile, calendar, sources = load_seed_components(SHOCK/'shock_shrink_predictions.csv')
    sources += [Path(__file__), ROOT/'regime_shock_score_runtime.py']
    groups = {
        'forest': (REPORTS/'regime_empirical_forest/20261019T070202_443313Z',
                   ['RandomForest_raw_scores.csv', 'RandomForest_normalized_scores.csv']),
        'magnitude': (REPORTS/'regime_magnitude_forest/20261019T070928_701705Z',
                      ['raw_scores.csv', 'normalized_scores.csv']),
        'analog': (REPORTS/'regime_analog_density/20261019T071721_721598Z',
                   [f'{view}_{target}_scores.csv' for view in ['compact', 'full'] for target in ['raw', 'normalized']]),
        'shock': (SHOCK, [f'{head}_{target}_scores.csv' for head in ['mean', 'magnitude'] for target in ['raw', 'normalized']]),
    }
    columns = ['p_bear', 'p_side', 'p_bull']
    components = {'classifier': classifier, 'quantile': quantile}
    for name, (folder, files) in groups.items():
        sources.append(folder/'plan.json')
        parts = []
        for filename in files:
            path = folder/filename; sources.append(path)
            rows = pd.read_csv(path, parse_dates=['Date', 'label_end_date'])
            for key in ['Date', 'label_end_date', 'label', 'outer_fold']:
                np.testing.assert_array_equal(base[key], rows[key])
            np.testing.assert_allclose(base.future_return, rows.future_return, atol=1e-12, rtol=1e-12)
            parts.append(rows[columns].to_numpy())
        components[name] = np.mean(parts, axis=0)
    selection = REPORTS/'regime_matched_calibration/20261019T064830_252658Z/selection.json'
    sources.append(selection)
    anchors = json.loads(selection.read_text())
    params = np.full((len(base), 3), np.nan)
    for anchor in anchors:
        if pd.Timestamp(anchor['latest_tuning_label_end']) >= pd.Timestamp(anchor['outer_boundary']):
            raise ValueError('Unmatured fusion parameter selection')
        params[base.outer_fold.eq(anchor['fold'])] = GRID[anchor['chosen']['robust']]
    if not np.isfinite(params).all():
        raise ValueError('Missing historical fusion parameters')
    # Verify transitive source receipts, including training recipes and inputs.
    pending = list(dict.fromkeys(sources))
    verified = {}
    while pending:
        path = pending.pop()
        key = str(path.resolve())
        if key in verified:
            continue
        verified[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name == 'plan.json':
            for source, digest in json.loads(path.read_text()).get('source_hashes', {}).items():
                other = Path(source)
                if hashlib.sha256(other.read_bytes()).hexdigest() != digest:
                    raise ValueError('Changed pinned source: '+source)
                pending.append(other)
    positions = pd.DatetimeIndex(calendar.Date).get_indexer(base.Date)
    if (positions < 0).any() or (np.diff(positions) <= 0).any():
        raise ValueError('Invalid full exchange calendar')
    stream_id = 'VNINDEX:shock_shrink:historical_replay:'+RECIPE_ID
    runtime = ShockScoreRuntime(stream_id)
    predictions = []
    for i, pos in enumerate(positions):
        # Simulate process shutdown and JSON round-trip at EVERY session.
        state = json.loads(json.dumps(runtime.dump_state()))
        runtime = ShockScoreRuntime(stream_id); runtime.restore_state(state)
        previous = calendar.Date.iloc[pos-1].date().isoformat() if pos else None
        answer = runtime.predict(base.Date.iloc[i].date().isoformat(), previous,
                                 {key: matrix[i] for key, matrix in components.items()}, params[i])
        predictions.append(answer['class_scores'])
    predicted = np.asarray(predictions)
    expected = base[columns].to_numpy()
    np.testing.assert_allclose(predicted, expected, rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(predicted.argmax(axis=1), expected.argmax(axis=1))
    fold_f1 = [f1_score(base.loc[base.outer_fold.eq(fold), 'label'],
                       predicted[base.outer_fold.eq(fold)].argmax(axis=1),
                       labels=[0, 1, 2], average='macro', zero_division=0)
               for fold in sorted(base.outer_fold.unique())]
    output = args.output_dir or REPORTS/'regime_runtime_parity'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output/'historical_component_fixture.npz', **components,
                        parameters=params, dates=base.Date.dt.strftime('%Y-%m-%d').to_numpy(dtype='U10'))
    (output/'recipe.json').write_text(json.dumps(RECIPE, indent=2)+'\n')
    (output/'state.json').write_text(json.dumps(runtime.dump_state(), indent=2)+'\n')
    audit = dict(recipe_id=RECIPE_ID, rows=len(base), restarts=len(base),
                 max_score_error=float(np.max(np.abs(predicted-expected))),
                 all_labels_match=True, fold_f1=fold_f1, mean_f1=float(np.mean(fold_f1)),
                 verified_sources=len(verified), native_model_weights_exported=False,
                 prospective_parameter_selection_frozen=False,
                 independent_test=False, deployed=False,
                 role='Historical component-score replay; no feature-to-score inference')
    (output/'audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    (output/'sources.json').write_text(json.dumps(verified, indent=2)+'\n')
    (output/'checksums.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in sorted(output.iterdir())}, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), **audit), indent=2))
    return output


if __name__ == '__main__':
    freeze_shock_runtime()
