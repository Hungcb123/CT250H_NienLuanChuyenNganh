"""Causal probability diagnostic for dynamic shock scores; point policy unchanged.

One predeclared logistic calibration, refit20 market sessions, last504 mature
OOF scores, minimum120 observations and10 per class. Historical development.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

import train_regime_v2 as base
from experiment_regime_labels import build_label_book


ROOT = Path(__file__).resolve().parent


def audit_shock_probabilities(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    source = ROOT/'reports/regime_shock_forest/20261019T072038_455776Z/shock_shrink_predictions.csv'
    index_path = ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv'
    index, _ = base.load_market_data(index_path)
    book = build_label_book(index)
    rows = pd.read_csv(source, parse_dates=['Date', 'label_end_date'])
    check = book.set_index('Date').loc[rows.Date]
    np.testing.assert_array_equal(rows.label, check.vol_label.astype(int))
    np.testing.assert_array_equal(rows.label_end_date, check.label_end_date)
    score = rows[['p_bear', 'p_side', 'p_bull']].to_numpy()
    x = np.log(np.maximum(score, 1e-8))
    x -= x.mean(axis=1, keepdims=True)
    calendar = pd.DatetimeIndex(index.Date)
    positions = calendar.get_indexer(rows.Date)
    if (positions < 0).any() or (np.diff(positions) <= 0).any():
        raise ValueError('Invalid forecast dates')
    output = args.output_dir or ROOT/'reports/regime_shock_probabilities'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    plan = dict(created_at=datetime.now(timezone.utc).isoformat(), role='Historical development probability diagnostic',
                source_hashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), source, index_path, ROOT/'experiment_regime_labels.py']},
                specification=dict(model='LogisticRegression', C=.1, max_iter=1000, random_state=42,
                                   mature_score_window=504, min_rows=120, min_per_class=10, refit_market_sessions=20,
                                   inputs='Centered log class scores, fixed epsilon1e-8',
                                   fallback='Last504 mature full-index dynamic-label class frequency'),
                comparison='Evaluate all methods on the SAME dates where a mature logistic model was available. Also report whole-cohort prior fallback. No confidence threshold or label/prediction subset optimization.',
                point_policy_changed=False, acceptance=False,
                caveat='No independent test. A lower Brier score is not proof of calibration or trading profitability.')
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    model = None; last_refit = None; records = []; audits = []
    for i, row in rows.iterrows():
        mature = book.loc[(book.label_end_date < row.Date) & book.vol_label.notna()].tail(504)
        prior = np.bincount(mature.vol_label.to_numpy(dtype=int), minlength=3).astype(float)
        if not len(mature) or (prior == 0).any():
            raise ValueError('Missing full-index mature prior')
        prior /= prior.sum()
        if last_refit is None or positions[i]-last_refit >= 20:
            known = np.flatnonzero(((rows.Date < row.Date) & (rows.label_end_date < row.Date)).to_numpy())[-504:]
            counts = np.bincount(rows.label.iloc[known], minlength=3)
            model = None
            if len(known) >= 120 and (counts >= 10).all():
                model = LogisticRegression(C=.1, max_iter=1000, random_state=42).fit(x[known], rows.label.iloc[known])
                np.testing.assert_array_equal(model.classes_, [0, 1, 2])
            audits.append(dict(session=str(row.Date.date()), n_train=len(known), class_counts=counts.tolist(),
                               latest_label_end=str(rows.label_end_date.iloc[known].max().date()) if len(known) else None,
                               model_available=model is not None))
            last_refit = positions[i]
        prediction = model.predict_proba(x[i:i+1])[0] if model is not None else prior
        record = dict(Date=str(row.Date.date()), label_end_date=str(row.label_end_date.date()),
                      label=int(row.label), outer_fold=int(row.outer_fold), calibration_active=model is not None)
        for name, values in [('raw_score', score[i]), ('prior', prior), ('logistic', prediction)]:
            for cls, value in zip(['bear', 'side', 'bull'], values):
                record[name+'_'+cls] = float(value)
        records.append(record)
    result = pd.DataFrame(records)
    truth = np.eye(3)[result.label]
    comparisons = []
    for scope, mask in [('all_with_fallback', np.ones(len(result), dtype=bool)),
                        ('matched_calibration_active', result.calibration_active.to_numpy())]:
        if not mask.any():
            continue
        for name in ['raw_score', 'prior', 'logistic']:
            p = result[[name+'_'+c for c in ['bear', 'side', 'bull']]].to_numpy()
            for fold in [None, *sorted(result.outer_fold.unique())]:
                selected = mask if fold is None else mask & result.outer_fold.eq(fold).to_numpy()
                if not selected.any():
                    continue
                comparisons.append(dict(scope=scope, method=name, fold=None if fold is None else int(fold),
                                        rows=int(selected.sum()), brier=float(np.square(p[selected]-truth[selected]).sum(axis=1).mean()),
                                        log_loss=float(log_loss(result.label[selected], p[selected], labels=[0, 1, 2]))))
    result.to_csv(output/'probability_predictions.csv', index=False)
    (output/'refit_audit.json').write_text(json.dumps(audits, indent=2)+'\n')
    summary = dict(rows=len(result), active_rows=int(result.calibration_active.sum()), comparisons=comparisons,
                   point_policy_changed=False, independent_test=False, accepted=False, deployed=False)
    (output/'report.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), rows=len(result), active_rows=int(result.calibration_active.sum()),
                         matched=[r for r in comparisons if r['scope'] == 'matched_calibration_active' and r['fold'] is None]), indent=2))
    return output


if __name__ == '__main__':
    audit_shock_probabilities()
