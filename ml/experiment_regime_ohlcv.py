"""Two-broker-consensus OHLCV feature ablation, historical development only.

Never changes reviewed closes, original snapshots or evaluation dates. Conflicts
stay missing. Source agreement is corroboration, NOT exchange certification or
point-in-time data-vintage verification.
"""
import hashlib
import itertools
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import experiment_regime_history as history
import prepare_regime_data as sources

study = history.study
OHLCV_NAMES = ['IntradayRangeSigma', 'CloseLocation', 'UpperWickSigma', 'BodySigma',
               'VolumeLogRatio60', 'RangeVolumeInteraction']
CONFIGS = [
    ('logistic_vol_ohlcv_3y', 'logistic_vol_close_3y', 'logistic_missing'),
    ('logistic_vol_ohlcv_expanding', 'logistic_vol_close_expanding', 'logistic_missing'),
    ('lightgbm_vol_ohlcv_expanding', 'lightgbm_vol_close_expanding', 'lightgbm'),
    ('logistic_binary_ohlcv_expanding', 'logistic_binary_close_expanding', 'logistic_missing'),
]


def consensus_value(values, tolerance):
    """Unique largest pairwise-agreeing subset of >=2 independent broker values.

    Reject a chain A~B, B~C, A!~C rather than arbitrarily resolving a tie.
    """
    valid = {k: float(v) for k, v in values.items() if pd.notna(v) and np.isfinite(v) and v > 0}
    groups = []
    for size in range(len(valid), 1, -1):
        for group in itertools.combinations(valid, size):
            selected = [valid[k] for k in group]
            if max(selected) - min(selected) <= tolerance:
                groups.append(group)
        if groups:
            break
    if len(groups) != 1:
        return np.nan, ''
    return float(np.median([valid[k] for k in groups[0]])), '+'.join(sorted(groups[0]))


def load_consensus(data_dir, index):
    manifest = json.loads((data_dir / 'manifest.json').read_text())
    frames, audits = {}, {}
    for provider in ['vci', 'kbs', 'vnd']:
        path = data_dir / 'sources' / f'{provider}_VNINDEX.json'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = manifest['sources'][f'{provider}_VNINDEX']['response_sha256']
        if digest != expected:
            raise ValueError(f'{provider}: archived source hash changed')
        frames[provider] = sources.normalize_response(json.loads(path.read_text()), provider, 'VNINDEX',
                                                       index.Date.min(), index.Date.max()).set_index('Date')
        audits[provider] = dict(sha256=digest, rows=len(frames[provider]))
    rows = []
    for record in index.itertuples():
        eligible = {}
        for provider, frame in frames.items():
            if record.Date not in frame.index:
                continue
            bar = frame.loc[record.Date]
            valid_bounds = bar.High + .011 >= max(bar.Open, bar.Close, bar.Low) and bar.Low - .011 <= min(bar.Open, bar.Close, bar.High)
            if valid_bounds and abs(bar.Close - record.Price) <= .011:
                eligible[provider] = bar
        result = dict(Date=record.Date, Price=record.Price)
        for column in ['Open', 'High', 'Low', 'Volume']:
            value, voters = consensus_value({p: bar[column] for p, bar in eligible.items()}, 1. if column == 'Volume' else .011)
            result[column], result[column + '_sources'] = value, voters
        # A field-wise majority must still obey the reviewed close/bar geometry.
        high, low, opening = result['High'], result['Low'], result['Open']
        if pd.notna(high) and (high + .011 < record.Price or (pd.notna(low) and high < low)):
            result['High'], result['High_sources'] = np.nan, ''
        if pd.notna(low) and low - .011 > record.Price:
            result['Low'], result['Low_sources'] = np.nan, ''
        if pd.notna(opening) and ((pd.notna(high) and opening > high + .011) or (pd.notna(low) and opening < low - .011)):
            result['Open'], result['Open_sources'] = np.nan, ''
        rows.append(result)
    return pd.DataFrame(rows), audits


def ohlcv_features(consensus):
    price = consensus.Price
    sigma = np.log(price).diff().rolling(20).std(ddof=1).replace(0, np.nan)
    spread = (consensus.High - consensus.Low).where(consensus.High > consensus.Low)
    volume_median = consensus.Volume.rolling(60, min_periods=30).median().where(lambda x: x > 0)
    volume_log = np.log(consensus.Volume / volume_median)
    normalized_range = (spread / price) / sigma
    feature = pd.DataFrame(dict(Date=consensus.Date,
        IntradayRangeSigma=normalized_range,
        CloseLocation=((price - consensus.Low) / spread).clip(0, 1),
        UpperWickSigma=((consensus.High - np.maximum(consensus.Open, price)) / price / sigma).clip(lower=0),
        BodySigma=(price - consensus.Open) / price / sigma,
        VolumeLogRatio60=volume_log,
        RangeVolumeInteraction=normalized_range * volume_log))
    return feature.replace([np.inf, -np.inf], np.nan)


def prepare_ohlcv(args):
    baselines, index, plan = history.prepare_history(args)
    consensus, audits = load_consensus(args.data_dir, index)
    features = ohlcv_features(consensus)
    candidates = []
    for name, baseline_name, family in CONFIGS:
        baseline = next(c for c in baselines if c[0] == baseline_name)
        _, policy, _, frame, job, names = baseline
        frame = frame.merge(features, on='Date', how='left', validate='one_to_one', sort=False)
        candidates.append((name, policy, family, frame, job, names + OHLCV_NAMES))
    plan.update(mode='consensus_ohlcv_ablation_development', candidates=[dict(name=n, paired_baseline=b, family=f) for n,b,f in CONFIGS],
                ohlcv_source_hashes=audits, consensus_coverage={col: float(consensus[col].notna().mean()) for col in ['Open','High','Low','Volume']},
                features=candidates[0][-1], missing_policy='Raw source conflicts remain NaN. Logistic: core-fit median imputation + missing indicators, including all-empty columns. LightGBM: native missing handling.',
                consensus_rule='Unique largest pairwise-agreeing subset >=2 brokers, tolerance .011 index points / 1 share. Reject invalid source bar or close mismatching reviewed close.',
                source_caveat='Consensus not exchange certification; historical source revisions/volume basis are not independently verified. No forward filling or retroactive source fallback.')
    return candidates, index, plan, consensus


def main(argv=None):
    args = study.risk.labels.parse_args(argv)
    candidates, index, plan, consensus = prepare_ohlcv(args)
    output = args.output_dir or study.risk.labels.ROOT / 'reports/regime_ohlcv' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'ohlcv_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    consensus.to_csv(output / 'consensus_fields.csv', index=False)
    if plan['errors']:
        raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. ' + str(output.resolve()))
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
    print('Done, development only. ' + str(output.resolve()))
    return output


if __name__ == '__main__':
    main()
