"""Predeclared regularized model study; historical development, no deployment.

Fixed hyperparameters, same purged core/calibration/refit dates as risk study.
All models are ranked on one absolute -5% loss outcome. No outer-fold tuning.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import experiment_regime_risk as risk
import regime_risk_diagnostics as diag

CANDIDATES = [
    ('logistic_binary_long', 'binary_5pct', 'logistic'),
    ('logistic_vol_long', 'vol_1sigma', 'logistic'),
    ('svm_binary_long', 'binary_5pct', 'svm'),
    ('svm_vol_long', 'vol_1sigma', 'svm'),
    ('ridge_volreturn_long', 'vol_1sigma', 'ridge'),
    ('lightgbm_vol_long', 'vol_1sigma', 'lightgbm'),
]
EXTRA = ['Stretch20', 'Shock5', 'VolRatio5_20', 'NegativeDays10', 'Drawdown20']


def reversal_features(index):
    price = index.Price.astype(float)
    logret = np.log(price).diff()
    sigma = logret.rolling(20).std(ddof=1).replace(0, np.nan)
    return pd.DataFrame(dict(Date=index.Date,
        Stretch20=np.log(price / price.rolling(20).mean()) / (sigma * np.sqrt(20)),
        Shock5=np.log(price / price.shift(5)) / (sigma * np.sqrt(5)),
        VolRatio5_20=logret.rolling(5).std(ddof=1) / sigma,
        NegativeDays10=(logret < 0).astype(float).where(logret.notna()).rolling(10).mean(),
        Drawdown20=price / price.rolling(20).max() - 1))


def make_model(family):
    if family == 'logistic_missing':
        return make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), StandardScaler(),
                             LogisticRegression(C=.1, class_weight='balanced', max_iter=3000, random_state=42))
    if family == 'logistic':
        return make_pipeline(StandardScaler(), LogisticRegression(C=.1, class_weight='balanced', max_iter=3000, random_state=42))
    if family == 'svm':
        # Decision margin, NOT Platt probabilities with time-insensitive internal CV.
        return make_pipeline(StandardScaler(), SVC(C=1., kernel='rbf', gamma='scale', class_weight='balanced', probability=False))
    if family == 'ridge':
        return make_pipeline(StandardScaler(), Ridge(alpha=100.))
    if family == 'lightgbm':
        return risk.exp.base.create_model('LightGBM', diag.FIXED_PARAMS)
    raise ValueError(f'Unknown family {family}')


def score_model(model, X, family, label_policy):
    if family == 'ridge':
        return model.predict(X)  # Predicted standardized forward LOSS, higher = worse.
    target = 1 if label_policy == 'binary_5pct' else 0
    classes = list(model.classes_)
    if family == 'svm':
        margin = np.asarray(model.decision_function(X))
        return margin * (1 if classes[1] == target else -1) if margin.ndim == 1 else margin[:, classes.index(target)]
    return np.asarray(model.predict_proba(X))[:, classes.index(target)]


def prepare_candidates(args):
    variants, book, plan = risk.prepare(args)
    index, audit = risk.exp.base.load_market_data(args.data_dir / 'VNINDEX.csv')
    if audit['sha256'] != plan['input_hashes']['VNINDEX']:
        raise ValueError('Input changed')
    extra = reversal_features(index)
    candidates = []
    for candidate, policy, family in CANDIDATES:
        _, frame, job = next(v for v in variants if v[0] == policy)
        frame = frame.merge(extra, on='Date', how='left', validate='one_to_one', sort=False)
        frame = frame.merge(book[['Date', 'horizon_sigma', 'future_log_return']], on='Date', validate='one_to_one', sort=False)
        names = job['names'] + risk.exp.RISK_NAMES + EXTRA
        if not np.isfinite(frame[names + ['horizon_sigma', 'future_log_return']].to_numpy(dtype=float)).all():
            raise ValueError('New feature undefined on frozen cohort; refusing to shrink dates')
        candidates.append((candidate, policy, family, frame, job, names))
    plan.update(mode='fixed_regularized_candidate_development',
                candidates=[dict(name=n, label_policy=p, family=f) for n, p, f in CANDIDATES],
                features=candidates[0][-1],
                parameter_mode='predeclared_no_tuning',
                parameters={'logistic': {'C': .1, 'class_weight': 'balanced', 'scaler': 'core-only StandardScaler'},
                            'svm': {'C': 1., 'kernel': 'rbf', 'gamma': 'scale', 'class_weight': 'balanced', 'probability': False},
                            'ridge': {'alpha': 100., 'target': '-future_log_return / trailing horizon_sigma'},
                            'lightgbm': diag.FIXED_PARAMS},
                limitations=['Already inspected development dates; candidate selection is not independent test evidence.',
                             'All features close/ETF only. No claims of volume or OHLC exhaustion detection.',
                             'New features computed on full raw calendar before date joining.',
                             'No winner auto-selected; no calibration probability or portfolio profit claims.'])
    # Remove inherited tuning protocol: these candidates are fixed across every fold.
    plan['protocol'] = ['Purged core/calibration and identical frozen refit dates from risk study.',
                        'All model/scaler fits use core only. Hyperparameters are fixed across all folds.',
                        'Calibration static p90; rolling 60/120 rescores strictly prior out-of-fit observations with current model.',
                        'Targets differ, evaluation always actual simple return < -5%. No native-F1 ranking.']
    plan['tuning_objective'] = 'none'
    return candidates, index, plan


def run_candidate(candidate, policy, family, frame, job, names):
    rows, audits = [], []
    for outer in job['folds']:
        for block_no, block in enumerate(outer['blocks'], 1):
            core, calibration, valid = (frame.iloc[block[key]] for key in ['core', 'calibration', 'validation'])
            if core.label_end_date.max() >= calibration.Date.min() or calibration.label_end_date.max() >= valid.Date.min():
                raise ValueError('Noncausal data split')
            model = make_model(family)
            target = (-core.future_log_return / core.horizon_sigma) if family == 'ridge' else core.label
            model.fit(core[names].to_numpy(dtype=float), target.to_numpy())
            history = frame.loc[(frame.Date > core.Date.max()) & (frame.Date <= valid.Date.max())]
            cal_score = score_model(model, calibration[names].to_numpy(dtype=float), family, policy)
            scores = score_model(model, valid[names].to_numpy(dtype=float), family, policy)
            history_scores = score_model(model, history[names].to_numpy(dtype=float), family, policy)
            if not all(np.isfinite(s).all() for s in [cal_score, scores, history_scores]):
                raise ValueError('Nonfinite model score')
            record = valid[['Date', 'label_end_date', 'future_return', 'label']].copy()
            record['risk_score'], record['threshold'] = scores, risk.alarm_threshold(cal_score)
            record['alarm'] = record.risk_score > record.threshold
            record['common_bear'] = record.future_return < -.05
            record['policy'], record['outer_fold'], record['refit_block'] = candidate, outer['fold'], block_no
            for column, values in diag.rolling_thresholds(history.Date, history_scores, valid.Date).items():
                record[column] = values
                record[column.replace('_threshold', '_alarm')] = record.risk_score > values
            rows.append(record)
            audits.append(dict(policy=candidate, outer_fold=outer['fold'], refit_block=block_no,
                               core_start=str(core.Date.min()), core_end=str(core.Date.max()), core_label_end=str(core.label_end_date.max()),
                               calibration_start=str(calibration.Date.min()), calibration_end=str(calibration.Date.max()),
                               calibration_label_end=str(calibration.label_end_date.max()), prediction_start=str(valid.Date.min()),
                               n_core=len(core), n_calibration=len(calibration), **diag.score_stats(cal_score, 'calibration_score')))
    return pd.concat(rows, ignore_index=True), audits


def main(argv=None):
    args = risk.labels.parse_args(argv)
    candidates, index, plan = prepare_candidates(args)
    output = args.output_dir or risk.labels.ROOT / 'reports/regime_candidates' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'candidate_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    if plan['errors']:
        raise ValueError('Preflight errors: ' + '; '.join(plan['errors']))
    if args.audit_only:
        print(f'Audit passed, no fitting. {output.resolve()}')
        return plan
    records, refits = [], []
    for candidate in candidates:
        print('Running ' + candidate[0], flush=True)
        predictions, audit = run_candidate(*candidate)
        predictions.to_csv(output / (candidate[0] + '_predictions.csv'), index=False)
        records.append(predictions)
        refits.extend(audit)
        # Incremental output preserves completed evidence if interrupted.
        risk.write_rolling_outputs(pd.concat(records, ignore_index=True), output)
    records = pd.concat(records, ignore_index=True)
    pd.DataFrame(risk.equal_count_diagnostic(records)).to_csv(output / 'retrospective_equal_count.csv', index=False)
    diag.write_diagnostics(records, refits, index, output / 'diagnostics')
    print(f'Done. Development evidence only, no winner/export. {output.resolve()}')
    return output


if __name__ == '__main__':
    main()
