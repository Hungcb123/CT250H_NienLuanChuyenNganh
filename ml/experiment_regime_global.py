"""Lagged official Cboe VIX feature ablation on frozen VNINDEX development dates."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_history as history
study = history.study
GLOBAL_DIR = study.risk.labels.ROOT / 'data/research/global_risk'
VIX_NAMES = ['VIX_LogLevel', 'VIX_LogChange5', 'VIX_LogChange20', 'VIX_DistMean60', 'VIX_StretchInteraction']
CONFIGS = [
    ('logistic_vol_vix_3y', 'logistic_vol_close_3y'),
    ('logistic_vol_vix_expanding', 'logistic_vol_close_expanding'),
    ('lightgbm_vol_vix_expanding', 'lightgbm_vol_close_expanding'),
    ('logistic_binary_vix_expanding', 'logistic_binary_close_expanding'),
]


def load_vix(directory=GLOBAL_DIR):
    directory = Path(directory)
    metadata = json.loads((directory / 'VIX.provenance.json').read_text())
    path = directory / 'sources/VIX_History.csv'
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']:
        raise ValueError('VIX input hash changed')
    source = pd.read_csv(path)
    source['VIX_ObservationDate'] = pd.to_datetime(source.DATE, format='%m/%d/%Y')
    source = source.sort_values('VIX_ObservationDate').reset_index(drop=True)
    if source.VIX_ObservationDate.duplicated().any() or not np.isfinite(source.CLOSE).all() or (source.CLOSE <= 0).any():
        raise ValueError('Invalid VIX source dates/prices')
    return source, metadata


def vix_features(source, decisions):
    source = source.sort_values('VIX_ObservationDate').reset_index(drop=True)
    close = source.CLOSE.astype(float)
    feature = pd.DataFrame(dict(VIX_ObservationDate=source.VIX_ObservationDate,
        VIX_AvailableDate=source.VIX_ObservationDate + pd.Timedelta(days=2),
        VIX_LogLevel=np.log(close), VIX_LogChange5=np.log(close / close.shift(5)),
        VIX_LogChange20=np.log(close / close.shift(20)),
        VIX_DistMean60=np.log(close / close.rolling(60).mean())))
    if not pd.DatetimeIndex(decisions).is_monotonic_increasing:
        raise ValueError('Decision dates must be sorted')
    aligned = pd.merge_asof(pd.DataFrame({'Date':decisions}).reset_index(drop=True), feature,
                            left_on='Date', right_on='VIX_AvailableDate', direction='backward', tolerance=pd.Timedelta(days=7))
    known = aligned.VIX_AvailableDate.notna()
    if not (aligned.loc[known, 'VIX_AvailableDate'] <= aligned.loc[known,'Date']).all():
        raise ValueError('Future VIX data joined')
    return aligned


def prepare_global(args):
    baselines, index, plan = history.prepare_history(args)
    source, metadata = load_vix()
    features = vix_features(source, index.Date)
    candidates = []
    for name, baseline_name in CONFIGS:
        _, policy, family, frame, job, names = next(c for c in baselines if c[0] == baseline_name)
        frame = frame.merge(features, on='Date', how='left', validate='one_to_one', sort=False)
        frame['VIX_StretchInteraction'] = frame.Stretch20 * (frame.VIX_LogLevel - np.log(20.))
        names = names + VIX_NAMES
        if not np.isfinite(frame[names].to_numpy()).all():
            raise ValueError('VIX missing/stale on historical cohort; refusing to drop prediction dates')
        candidates.append((name, policy, family, frame, job, names))
    plan.update(mode='lagged_vix_feature_ablation_development',
                candidates=[dict(name=n, paired_baseline=b) for n,b in CONFIGS], features=candidates[0][-1],
                vix_source=metadata, vix_availability_lag_calendar_days=2, max_staleness_after_availability_days=7,
                timing='VIX features calculated on complete source observation calendar, joined backward on observation date +2 calendar days.',
                caveat='Conservative timing assumption, not original release-vintage proof; existing development labels already inspected.')
    return candidates,index,plan


def main(argv=None):
    args = study.risk.labels.parse_args(argv)
    candidates,index,plan = prepare_global(args)
    output = args.output_dir or study.risk.labels.ROOT / 'reports/regime_global' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'global_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:
        raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()))
        return plan
    records,refits=[],[]
    for candidate in candidates:
        print('Running '+candidate[0],flush=True)
        predictions,audits=study.run_candidate(*candidate)
        predictions.to_csv(output/(candidate[0]+'_predictions.csv'),index=False)
        frame=candidate[3]
        if not records:
            frame[['Date','VIX_ObservationDate','VIX_AvailableDate']+VIX_NAMES].to_csv(output/'global_feature_timing.csv',index=False)
        records.append(predictions)
        refits.extend(audits)
        study.risk.write_rolling_outputs(pd.concat(records,ignore_index=True),output)
    records=pd.concat(records,ignore_index=True)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,refits,index,output/'diagnostics')
    print('Done. Historical development only. '+str(output.resolve()))
    return output


if __name__=='__main__':
    main()
