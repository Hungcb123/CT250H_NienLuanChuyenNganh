"""Independent metric/receipt checks; run once the native replay is complete."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef, log_loss


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NATIVE = ROOT/'reports/regime_shock_native/20261019T090304_754869Z'
CANDIDATE = ROOT/'artifacts/regime_shock_candidate_20261019T090555_259289Z'
PROBABILITY = ROOT/'reports/regime_shock_probabilities/20261019T090829_984153Z'
index_path = ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv'
index = pd.read_csv(index_path, parse_dates=['Date'])
assert not index.Date.duplicated().any() and index.Date.is_monotonic_increasing
price = index.Close
sigma = np.log(price).diff().rolling(20, min_periods=20).std(ddof=1)*np.sqrt(20)
future = np.log(price.shift(-20)/price)
labels = np.where(future < -sigma, 0, np.where(future > sigma, 2, 1))
endpoints = index.Date.shift(-20)
calendar = pd.DatetimeIndex(index.Date)
audited_files = []
metrics = {}
paths = {
    'analog_shrink': ROOT/'reports/regime_analog_density/20261019T071721_721598Z/analog_shrink_predictions.csv',
    'shock_shrink': ROOT/'reports/regime_shock_forest/20261019T072038_455776Z/shock_shrink_predictions.csv',
    'matched_close_analog': ROOT/'reports/regime_close_history_analog/20261019T090704_554220Z/matched_half_predictions.csv',
    'extended_close_analog': ROOT/'reports/regime_close_history_analog/20261019T090704_554220Z/extended_half_predictions.csv',
    'path_shrink': ROOT/'reports/regime_path_forest/20261019T091101_051315Z/path_shrink_predictions.csv',
    'native_shock': NATIVE/'native_predictions.csv',
}
reference = None
for name, path in paths.items():
    rows = pd.read_csv(path, parse_dates=['Date'])
    assert len(rows) == 1560 and rows.Date.is_monotonic_increasing and not rows.Date.duplicated().any()
    pos = calendar.get_indexer(rows.Date)
    assert (pos >= 0).all() and np.isfinite(future.iloc[pos]).all()
    np.testing.assert_array_equal(rows.label, labels[pos])
    if 'label_end_date' in rows:
        np.testing.assert_array_equal(pd.to_datetime(rows.label_end_date), endpoints.iloc[pos])
    if reference is None:
        reference = rows[['Date', 'label', 'outer_fold']]
    else:
        for key in reference:
            np.testing.assert_array_equal(rows[key], reference[key])
    scores = rows[['p_bear', 'p_side', 'p_bull']].to_numpy()
    assert np.isfinite(scores).all() and (scores >= 0).all()
    np.testing.assert_allclose(scores.sum(axis=1), 1., atol=1e-12, rtol=0)
    prediction = scores.argmax(axis=1)
    if 'prediction' in rows:
        np.testing.assert_array_equal(prediction, rows.prediction)
    folds = [f1_score(part.label, prediction[part.index], labels=[0, 1, 2], average='macro', zero_division=0)
             for _, part in rows.groupby('outer_fold')]
    metrics[name] = dict(mean_f1=float(np.mean(folds)), worst_f1=float(min(folds)), folds=folds)
    audited_files.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
np.testing.assert_allclose(metrics['native_shock']['folds'], metrics['shock_shrink']['folds'], atol=0, rtol=0)
a = pd.read_csv(paths['native_shock'])[['p_bear', 'p_side', 'p_bull']].to_numpy()
b = pd.read_csv(paths['shock_shrink'])[['p_bear', 'p_side', 'p_bull']].to_numpy()
np.testing.assert_allclose(a, b, atol=1e-10, rtol=1e-10)
assert json.loads((NATIVE/'summary.json').read_text())['complete']
payloads = 0; fit_receipts = 0
for item in json.loads((NATIVE/'block_audits.json').read_text()):
    directory = Path(item['bundle'])
    if not directory.is_absolute():
        directory = ROOT.parent/directory
    raw = (directory/'bundle.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (directory/'bundle.sha256').read_text().strip()
    meta = json.loads(raw)
    assert len(meta['models']) == 100
    for filename, digest in meta['files'].items():
        assert Path(filename).name == filename
        assert hashlib.sha256((directory/filename).read_bytes()).hexdigest() == digest
        payloads += 1
    for receipt in meta['training_receipts']:
        assert pd.Timestamp(receipt['latest_label_end']) < pd.Timestamp(meta['boundary'])
        fit_receipts += 1
for filename, digest in json.loads((CANDIDATE/'checksums.json').read_text()).items():
    assert hashlib.sha256((CANDIDATE/filename).read_bytes()).hexdigest() == digest
contract = json.loads((CANDIDATE/'contract.json').read_text())
for filename, digest in {**contract['source_receipts'], **contract['provenance']}.items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest
assert not contract['accepted'] and not contract['deployed']

# Two stronger causal references than a single majority class. The second uses
# the regime whose outcome ENDS today, available at the completed close. No next
# session or future price is used in either baseline prediction.
pos = calendar.get_indexer(reference.Date)
past = np.log(price/price.shift(20)).to_numpy()[pos]
momentum = np.where(past < -sigma.to_numpy()[pos], 0, np.where(past > sigma.to_numpy()[pos], 2, 1))
completed = labels[pos-20]
baselines = {}
for name, prediction in [('momentum20_current_sigma', momentum), ('latest_completed_regime', completed)]:
    fold_scores = [f1_score(part.label, prediction[part.index], labels=[0, 1, 2], average='macro', zero_division=0)
                   for _, part in reference.groupby('outer_fold')]
    baselines[name] = dict(mean_f1=float(np.mean(fold_scores)), worst_f1=float(min(fold_scores)), folds=fold_scores)

prob = pd.read_csv(PROBABILITY/'probability_predictions.csv', parse_dates=['Date', 'label_end_date'])
for key in ['Date', 'label', 'outer_fold']:
    np.testing.assert_array_equal(prob[key], reference[key])
np.testing.assert_array_equal(prob.label_end_date, endpoints.iloc[pos])
probability_metrics = {}
active = prob.calibration_active.to_numpy(dtype=bool)
truth = np.eye(3)[prob.label]
for method in ['raw_score', 'prior', 'logistic']:
    p = prob[[method+'_'+c for c in ['bear', 'side', 'bull']]].to_numpy()
    probability_metrics[method] = dict(rows=int(active.sum()),
        brier=float(np.square(p[active]-truth[active]).sum(axis=1).mean()),
        log_loss=float(log_loss(prob.label[active], p[active], labels=[0, 1, 2])))
for receipt in json.loads((PROBABILITY/'refit_audit.json').read_text()):
    if receipt['latest_label_end'] is not None:
        assert pd.Timestamp(receipt['latest_label_end']) < pd.Timestamp(receipt['session'])

result = dict(complete=True, forecast_files=audited_files, metrics=metrics, causal_baselines=baselines,
              native_payloads_verified=payloads, native_fit_receipts_verified=fit_receipts,
              candidate_snapshot_payloads_verified=True, native_score_max_error=float(np.max(np.abs(a-b))),
              probability_metrics=probability_metrics, independent_test=False, accepted=False, deployed=False)
(HERE/'independent_audit.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
