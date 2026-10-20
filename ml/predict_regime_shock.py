"""Run a local native shock bundle on completed-close market inputs.

Historical preview by default; no emission to web and no confidence probability.
Persistent state is optional and must belong to the same versioned model stream.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from regime_shock_features import completed_shock_features
from regime_shock_native import ShockNativeBundle, shock_file_digest
from regime_shock_score_runtime import RECIPE_ID, ShockScoreRuntime


def predict_shock_snapshot(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--as-of', type=str)
    parser.add_argument('--parameters', type=float, nargs=3, required=True,
                        metavar=('DENSITY_WEIGHT', 'CLASSIFIER_TEMPERATURE', 'DENSITY_TEMPERATURE'))
    parser.add_argument('--state-file', type=Path)
    parser.add_argument('--output-json', type=Path)
    parser.add_argument('--require-fresh', action='store_true')
    parser.add_argument('--max-data-age-days', type=int, default=4)
    args = parser.parse_args(argv)
    if args.max_data_age_days < 0:
        parser.error('max-data-age-days must be nonnegative')
    frame, audits = completed_shock_features(args.data_dir)
    date = pd.Timestamp(args.as_of) if args.as_of else frame.Date.max()
    ids = np.flatnonzero(frame.Date.eq(date))
    if len(ids) != 1:
        raise ValueError('as-of must be an observed completed market session')
    pos = int(ids[0])
    age = (datetime.now(timezone.utc).date()-date.date()).days
    if age < 0 or (args.require_fresh and age > args.max_data_age_days):
        raise ValueError('Input session outside allowed freshness window')
    bundle = ShockNativeBundle(args.bundle)
    boundary = pd.Timestamp(bundle.meta['boundary'])
    boundary_ids = np.flatnonzero(frame.Date.eq(boundary))
    if len(boundary_ids) != 1 or pos < int(boundary_ids[0]) or pos-int(boundary_ids[0]) >= 63:
        raise ValueError('Forecast outside the bundle 63-market-session refit window')
    names = list(dict.fromkeys(n for item in bundle.meta['models'] for n in item['features']))
    valid = frame.iloc[[pos]]
    components = bundle.predict_components({n: valid[n].to_numpy() for n in names}, valid.horizon_sigma.to_numpy())
    # Bind state to the decision parameters as well as recipe version. Refit
    # bundles can share a stream only when the candidate policy is unchanged.
    stream_id = 'VNINDEX:'+RECIPE_ID+':'+json.dumps(args.parameters, separators=(',', ':'))
    runtime = ShockScoreRuntime(stream_id)
    if args.state_file and args.state_file.exists():
        runtime.restore_state(json.loads(args.state_file.read_text()))
    result = runtime.predict(str(date.date()), str(frame.Date.iloc[pos-1].date()) if pos else None,
                             {n: values[0] for n, values in components.items()}, args.parameters)
    result.update(role='local_historical_snapshot_preview', independent_prospective_prediction=False,
                  data_age_calendar_days=age, bundle_boundary=str(boundary.date()),
                  bundle_sha256=shock_file_digest(args.bundle/'bundle.json'),
                  class_name=['bearish', 'sideway', 'bullish'][result['signal']+1],
                  state_was_supplied=args.state_file is not None,
                  note='Cold start resets EMA; full historical parity requires the preceding causal state. No per-forecast confidence or live-deployment claim.')
    # Refuse output overwrite; durable logging/locking belongs to a serving layer.
    if args.output_json:
        with args.output_json.open('x') as stream:
            stream.write(json.dumps(result, indent=2)+'\n')
    if args.state_file:
        temporary = args.state_file.with_suffix(args.state_file.suffix+'.tmp')
        with temporary.open('x') as stream:
            stream.write(json.dumps(runtime.dump_state(), indent=2)+'\n')
        temporary.replace(args.state_file)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    predict_shock_snapshot()
