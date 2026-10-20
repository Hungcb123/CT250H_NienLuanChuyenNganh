"""Close-only 2010+ history study on EXACT previously frozen prediction dates.

Predeclared regularized models and 3y/5y/expanding histories. Historical
DEVELOPMENT, no unseen-test or guaranteed performance claim, no deployment.
"""
import copy
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import experiment_regime_candidates as study

CONFIGS = [
    ('logistic_vol_close_3y', 'vol_1sigma', 'logistic', '3y'),
    ('logistic_vol_close_5y', 'vol_1sigma', 'logistic', '5y'),
    ('logistic_vol_close_expanding', 'vol_1sigma', 'logistic', 'expanding'),
    ('lightgbm_vol_close_5y', 'vol_1sigma', 'lightgbm', '5y'),
    ('lightgbm_vol_close_expanding', 'vol_1sigma', 'lightgbm', 'expanding'),
    ('logistic_binary_close_expanding', 'binary_5pct', 'logistic', 'expanding'),
]


def prepare_history(args):
    old, index, plan = study.prepare_candidates(args)
    features, names = study.risk.exp.base.build_feature_matrix(index, feature_set='close')
    features = pd.concat([features, study.risk.exp.long_features(index)], axis=1)
    extra = study.reversal_features(index)
    features = features.merge(extra, on='Date', validate='one_to_one')
    names += study.risk.exp.TREND_NAMES + study.risk.exp.RISK_NAMES + study.EXTRA
    frame = study.risk.exp.base.create_labels(features, 20, names)
    book = study.risk.labels.build_label_book(index)
    variants = []
    template_frame, template_job = old[0][3], old[0][4]
    for candidate, policy, family, window in CONFIGS:
        relabeled = study.risk.labels.relabel_cohort(frame, book, 'vol_1sigma' if policy == 'vol_1sigma' else 'fixed_5pct')
        if policy == 'binary_5pct':
            relabeled['label'] = (relabeled.label == 0).astype(int)
        relabeled = relabeled.merge(book[['Date', 'horizon_sigma', 'future_log_return']], on='Date', validate='one_to_one')
        job = copy.deepcopy(template_job)
        for outer in job['folds']:
            for block in outer['blocks']:
                frozen_dates = template_frame.Date.iloc[block['validation']]
                validation = pd.DatetimeIndex(relabeled.Date).get_indexer(frozen_dates)
                if (validation < 0).any():
                    raise ValueError('Missing frozen validation date')
                start = relabeled.Date.iloc[validation[0]]
                known = (relabeled.Date < start) & (relabeled.label_end_date < start)
                if window != 'expanding':
                    known &= relabeled.Date >= start - pd.DateOffset(years=int(window[:-1]))
                train = np.flatnonzero(known)
                core, calibration = study.risk.split_calibration(relabeled, train)
                expected = 2 if policy == 'binary_5pct' else 3
                if relabeled.label.iloc[core].nunique() != expected:
                    raise ValueError('Missing core classes')
                history = relabeled.loc[(relabeled.Date > relabeled.Date.iloc[core].max()) & (relabeled.Date <= relabeled.Date.iloc[validation].max())]
                study.diag.rolling_thresholds(history.Date, np.zeros(len(history)), relabeled.Date.iloc[validation])
                block.update(train=train, core=core, calibration=calibration, validation=validation)
        variants.append((candidate, policy, family, relabeled, job, names))
    plan.update(mode='close_only_long_history_development', features=names,
                candidates=[dict(name=n, policy=p, family=f, window=w) for n,p,f,w in CONFIGS],
                cohort_start=str(frame.Date.min()), cohort_rows=len(frame),
                history_change='No ETF requirement; older close-only history allowed for training. EXACT prior prediction dates and end-date labels retained.',
                caveat='Oldest source history has single-broker segments; no new independent test.')
    return variants, index, plan


def main(argv=None):
    args = study.risk.labels.parse_args(argv)
    candidates, index, plan = prepare_history(args)
    output = args.output_dir or study.risk.labels.ROOT / 'reports/regime_history' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'history_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    if plan['errors']:
        raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed; no fitting. ' + str(output.resolve()))
        return plan
    records, refits = [], []
    for candidate in candidates:
        print('Running ' + candidate[0], flush=True)
        predictions, audits = study.run_candidate(*candidate)
        predictions.to_csv(output / (candidate[0] + '_predictions.csv'), index=False)
        records.append(predictions)
        refits.extend(audits)
        study.risk.write_rolling_outputs(pd.concat(records, ignore_index=True), output)
    records = pd.concat(records, ignore_index=True)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output / 'retrospective_equal_count.csv', index=False)
    study.diag.write_diagnostics(records, refits, index, output / 'diagnostics')
    print('Done. No export; development only. ' + str(output.resolve()))
    return output


if __name__ == '__main__':
    main()
