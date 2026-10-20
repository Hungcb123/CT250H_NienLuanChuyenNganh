"""Controlled three-class endpoint forecasting, historical development only.

All variants share frozen T+20 +/-5% labels, features and monthly refit dates.
Decision weights may use ONLY archived out-of-fit predictions with mature labels.
No change to the independently frozen risk shadow candidate or production model.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, log_loss, matthews_corrcoef
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import experiment_regime as exp

ROOT = Path(__file__).resolve().parent
PARAMS = dict(n_estimators=150, learning_rate=.03, max_depth=3, num_leaves=7,
              min_child_samples=50, colsample_bytree=.7, reg_alpha=.1, reg_lambda=1.,
              random_state=42, n_jobs=2, verbosity=-1)
CONFIGS = [(family, balanced, window) for window in ['3y', 'expanding']
           for family, balanced in [('gbm', True), ('gbm', False), ('ordinal', False),
                                    ('logistic', True), ('logistic', False)]]
PROB_COLUMNS = ['p_bear', 'p_side', 'p_bull']
WEIGHTS = [.5, .75, 1., 1.5, 2.]


def ordered_probabilities(lower, upper):
    """Project P(y>0),P(y>1) onto monotone cumulative probabilities."""
    a, b = np.asarray(lower, dtype=float).copy(), np.asarray(upper, dtype=float).copy()
    crossing = a < b
    pooled = (a[crossing] + b[crossing]) / 2
    a[crossing], b[crossing] = pooled, pooled
    result = np.column_stack([1-a, a-b, b])
    if not np.isfinite(result).all() or (result < -1e-12).any():
        raise ValueError('Invalid ordinal probabilities')
    return result


def fit_probabilities(train, valid, names, family, balanced):
    X, V = train[names].to_numpy(dtype=float), valid[names].to_numpy(dtype=float)
    y = train.label.to_numpy(dtype=int)
    if family == 'ordinal':
        margins = []
        for threshold in [0, 1]:
            target = (y > threshold).astype(int)
            if len(np.unique(target)) == 1:
                margins.append(np.full(len(V), float(target[0])))
            else:
                model = LGBMClassifier(**PARAMS)
                model.fit(X, target)
                margins.append(model.predict_proba(V)[:, 1])
        probability = ordered_probabilities(*margins)
    else:
        if family == 'gbm':
            model = LGBMClassifier(**PARAMS, class_weight='balanced' if balanced else None)
        elif family == 'logistic':
            model = make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=3000,
                                  class_weight='balanced' if balanced else None, random_state=42))
        else:
            raise ValueError('Unknown learner')
        model.fit(X, y)
        probability = np.zeros((len(V), 3))
        probability[:, np.asarray(model.classes_, dtype=int)] = model.predict_proba(V)
    np.testing.assert_allclose(probability.sum(axis=1), 1., atol=1e-10)
    if not np.isfinite(probability).all() or (probability < 0).any():
        raise ValueError('Nonfinite/negative probabilities')
    return probability


def causal_decision_weights(archive, boundary):
    """Coarse macro-F1 decision weights from at most 252 matured OOF rows.

    Empty/rare-class history uses identity. The regularizer and grid are fixed
    in the pre-run plan; no outer-period label can affect an earlier decision.
    """
    identity = np.ones(3)
    if archive.empty:
        return identity, dict(n=0, latest_label_end=None)
    boundary = pd.Timestamp(boundary)
    history = archive.loc[(archive.Date < boundary) & (archive.label_end_date < boundary)].tail(252)
    info = dict(n=len(history), latest_label_end=str(history.label_end_date.max()) if len(history) else None)
    if len(history) < 120 or (history.label.value_counts().reindex([0, 1, 2], fill_value=0) < 10).any():
        return identity, info
    y, p = history.label.to_numpy(dtype=int), history[PROB_COLUMNS].to_numpy(dtype=float)
    best, best_score = identity, f1_score(y, p.argmax(axis=1), labels=[0, 1, 2], average='macro', zero_division=0)
    for bear, bull in product(WEIGHTS, repeat=2):
        weights = np.array([bear, 1., bull])
        value = f1_score(y, (p*weights).argmax(axis=1), labels=[0, 1, 2], average='macro', zero_division=0)
        value -= .005 * np.square(np.log(weights)).sum()
        if value > best_score + 1e-12:
            best, best_score = weights, value
    return best, info


def prepare_multiclass(args):
    inherited = exp.parse_args(['--reference-report', str(args.reference_report), '--data-dir', str(args.data_dir),
         '--base-feature-set', 'close-etf', '--feature-groups', 'trend', '--train-windows', '3y', 'expanding',
         '--models', 'LightGBM', '--horizons', '20', '--refit-sessions', '20'])
    frames, jobs, plan = exp.prepare_experiment(inherited)
    if plan['errors']:
        raise ValueError('Preflight: '+str(plan['errors']))
    frame = frames[20]
    by_window = {j['window']: j for j in jobs}
    plan.update(mode='three_class_controlled_development_not_fresh_test', target='T+20 simple return; below -5% bearish, above +5% bullish, equality sideway',
                candidates=[dict(family=f, balanced=b, window=w) for f,b,w in CONFIGS],
                parameters=PARAMS, logistic=dict(C=.1, max_iter=3000, scaler='training-only StandardScaler'),
                decision_rules=['argmax', 'causal_macro_weights'],
                decision_history=dict(rows_max=252, rows_min=120, each_class_min=10, weight_grid=WEIGHTS,
                                      regularizer=.005, timing='archived out-of-fit predictions, label_end_date strictly before refit start'),
                optuna=None, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                acceptance='Development screen only: compare same-run balanced GBM 3y argmax; require mean F1 +.02, worst F1 >= control, MCC gain, >=3/4 improved folds. Paired intervals describe inspected history, not independent acceptance.')
    return frame, by_window, plan


def metrics(rows, prediction):
    actual, pred = rows.label.to_numpy(dtype=int), rows[prediction].to_numpy(dtype=int)
    matrix = confusion_matrix(actual, pred, labels=[0, 1, 2])
    return dict(f1=float(f1_score(actual, pred, labels=[0, 1, 2], average='macro', zero_division=0)),
                mcc=float(matthews_corrcoef(actual, pred)), accuracy=float((actual == pred).mean()),
                confusion_matrix=matrix.tolist(),
                per_class=classification_report(actual, pred, labels=[0, 1, 2], target_names=['bear', 'side', 'bull'], output_dict=True, zero_division=0))


def run_multiclass(frame, job, family, balanced):
    records, audits = [], []
    for outer in job['folds']:
        for block_number, block in enumerate(outer['blocks'], 1):
            train, valid = frame.iloc[block['train']], frame.iloc[block['validation']]
            boundary = valid.Date.min()
            if train.label_end_date.max() >= boundary:
                raise ValueError('Noncausal training labels')
            probability = fit_probabilities(train, valid, job['names'], family, balanced)
            archive = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
            weights, info = causal_decision_weights(archive, boundary)
            row = valid[['Date','label_end_date','label','future_return']].copy()
            row[PROB_COLUMNS] = probability
            row['argmax'] = probability.argmax(axis=1)
            row['causal_macro_weights'] = (probability*weights).argmax(axis=1)
            counts = np.bincount(train.label.to_numpy(dtype=int), minlength=3)
            row['majority'] = counts.argmax()
            row['outer_fold'], row['refit_block'] = outer['fold'], block_number
            records.append(row)
            audits.append(dict(fold=outer['fold'], block=block_number, prediction_start=str(boundary.date()),
                               train_start=str(train.Date.min().date()), train_label_end=str(train.label_end_date.max().date()),
                               n_train=len(train), train_counts=counts.tolist(), decision_weights=weights.tolist(),
                               decision_history=info))
    records = pd.concat(records, ignore_index=True)
    return records, audits


def summarize_multiclass(name, rows):
    result = []
    for decision in ['argmax', 'causal_macro_weights']:
        folds = [dict(fold=int(fold), **metrics(part, decision)) for fold, part in rows.groupby('outer_fold')]
        result.append(dict(candidate=name+'/'+decision, learner=name, decision=decision, n=len(rows),
                           mean_f1=float(np.mean([f['f1'] for f in folds])), worst_f1=min(f['f1'] for f in folds),
                           mean_mcc=float(np.mean([f['mcc'] for f in folds])), folds=folds, pooled=metrics(rows, decision),
                           raw_probability_log_loss=float(log_loss(rows.label, rows[PROB_COLUMNS], labels=[0,1,2])),
                           majority=metrics(rows,'majority')))
    return result


def write_multiclass_report(results, output):
    control = next(r for r in results if r['candidate']=='gbm_balanced_3y/argmax')
    lines = ['# Three-class T+20 forecasting: development evidence', '',
             'Fixed +/-5% labels, identical 1560 previously inspected dates. No unseen-test or deployment claim.', '',
             '| Candidate | Mean F1 | Worst F1 | Mean MCC | Better folds vs control | Screen |',
             '|---|---:|---:|---:|---:|---|']
    table=[]
    for r in results:
        wins=sum(a['f1']>b['f1'] for a,b in zip(r['folds'],control['folds']))
        passed=r['mean_f1']>=control['mean_f1']+.02 and r['worst_f1']>=control['worst_f1'] and r['mean_mcc']>control['mean_mcc'] and wins>=3
        row={k:r[k] for k in ['candidate','mean_f1','worst_f1','mean_mcc']}
        row.update(folds_improved=wins,development_screen=passed)
        table.append(row)
        lines.append(f"| {r['candidate']} | {r['mean_f1']:.4f} | {r['worst_f1']:.4f} | {r['mean_mcc']:.4f} | {wins}/4 | {passed} |")
    (output/'report.json').write_text(json.dumps(dict(role='historical_development_only',control=control['candidate'],results=results),indent=2)+'\n')
    pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    (output/'comparison.md').write_text('\n'.join(lines)+'\n')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    frame,jobs,plan=prepare_multiclass(args)
    output=args.output_dir or ROOT/'reports/regime_multiclass'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    results=[]
    for family,balanced,window in CONFIGS:
        name=family+'_'+('balanced' if balanced else 'unweighted')+'_'+window
        print('Running '+name,flush=True)
        records,audit=run_multiclass(frame,jobs[window],family,balanced)
        records.to_csv(output/(name+'_predictions.csv'),index=False)
        (output/(name+'_refits.json')).write_text(json.dumps(audit,indent=2)+'\n')
        summary=summarize_multiclass(name,records);results.extend(summary)
        write_multiclass_report(results,output)
        print([(r['decision'],round(r['mean_f1'],4),round(r['worst_f1'],4),round(r['mean_mcc'],4)) for r in summary],flush=True)
    print('Done: development only; original three-class objective retained. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
