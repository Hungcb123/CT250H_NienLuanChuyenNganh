"""Export native historical OOF scores for honest probability evaluation.

No model fitting or emission. Decision scores are explicitly NOT calibrated.
"""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

import regime_multiclass_native as native

ROOT=native.ROOT
CLASSES=['bear','side','bull']


def resolved(path):
    path=Path(path)
    return path if path.is_absolute() else ROOT.parent/path


def verify_native_artifacts(contract_path=native.CONTRACT):
    contract_path=Path(contract_path);artifact=contract_path.parent
    lock=json.loads((artifact/'native_runtime_lock.json').read_text())
    if native.sha(contract_path)!=lock['contract_sha256']:raise ValueError('Native contract changed')
    if native.sha(native.__file__)!=lock['native_source_sha256']:raise ValueError('Native source changed')
    if platform.python_version()!=lock['python']:raise ValueError('Native Python version changed')
    for package,expected in lock['packages'].items():
        if version(package)!=expected:raise ValueError('Native dependency changed: '+package)
    if native.sha(artifact/'historical_replay_manifest.json')!=lock['historical_manifest_sha256']:raise ValueError('Native historical manifest changed')
    if native.sha(artifact/'native_parity_reference.json')!=lock['reference_lock_sha256']:raise ValueError('Native reference lock changed')
    if native.sha(resolved(lock['parity_report']))!=lock['parity_report_sha256']:raise ValueError('Native parity report changed')
    references=json.loads((artifact/'native_parity_reference.json').read_text())
    for path,digest in references['files'].items():
        if native.sha(resolved(path))!=digest:raise ValueError('Native reference archive changed')
    return native.read_native_contract(contract_path),lock,references


def prior_unbalance(scores,prior):
    scores=np.asarray(scores,dtype=float);prior=np.asarray(prior,dtype=float)
    if scores.ndim!=2 or scores.shape[1]!=3 or prior.shape!=(3,) or (prior<=0).any() or not np.isfinite(prior).all():raise ValueError('Invalid prior correction')
    if not np.isfinite(scores).all() or (scores<0).any():raise ValueError('Invalid source decision scores')
    values=scores*prior
    denominator=values.sum(axis=1,keepdims=True)
    if (denominator<=0).any():raise ValueError('Empty corrected mass')
    return values/denominator


def held_choices(dates,events):
    if events.Date.duplicated().any() or not events.Date.is_monotonic_increasing:raise ValueError('Invalid selection events')
    result=pd.merge_asof(pd.DataFrame({'Date':dates}).reset_index(drop=True),events[['Date','selected']],on='Date',direction='backward')
    if result.selected.isna().any():raise ValueError('Forecast before first selector event')
    return result.selected.to_numpy()


def export_native_score_archive(contract_path,output):
    contract_path=Path(contract_path);artifact=contract_path.parent;output=Path(output)
    contract,lock,references=verify_native_artifacts(contract_path)
    parity_dir=resolved(lock['parity_report']).parent
    records=pd.read_csv(parity_dir/'native_predictions.csv',parse_dates=['Date','label_end_date'])
    expected_path=next(resolved(p) for p in references['files'] if Path(p).name=='delayed_selector_predictions.csv')
    expected=pd.read_csv(expected_path,parse_dates=['Date','label_end_date'])
    for field in ['Date','label_end_date','label','prediction']:
        np.testing.assert_array_equal(records[field],expected[field])
    frame,index,etf=native.prepare_multiclass_native(ROOT/'data/research/brokers_2010_20261001_reviewed',contract)
    by_date=frame.set_index('Date',drop=False)
    events=pd.DataFrame(json.loads((parity_dir/'selector_history.json').read_text()));events['Date']=pd.to_datetime(events.Date)
    original_events_path=next(resolved(p) for p in references['files'] if Path(p).name=='selector_history.json')
    old=pd.DataFrame(json.loads(original_events_path.read_text()));old.Date=pd.to_datetime(old.Date)
    np.testing.assert_array_equal(events.Date,old.Date);np.testing.assert_array_equal(events.selected,old.chosen)
    parts=[];union=list(dict.fromkeys(contract['feature_schemas']['trend']+contract['feature_schemas']['risk']))
    for key,rows in records.groupby('bundle',sort=False):
        directory=artifact/'native_bundles'/key
        if native.sha(directory/'bundle.json')!=lock['historical_bundle_metadata_sha256'].get(key):raise ValueError('Unknown/changed historical model bundle')
        meta=json.loads((directory/'bundle.json').read_text());boundary=pd.Timestamp(meta['refit_date'])
        if rows.Date.min()!=boundary:raise ValueError('Incorrect bundle time assignment')
        expected_identity=dict(contract_sha256=lock['contract_sha256'],runtime_sha256=lock['native_source_sha256'],training_prefix_sha256=native.prefix_digest(index,etf,boundary))
        meta,models=native.load_native_bundle(directory,expected_identity)
        valid=by_date.loc[rows.Date].reset_index(drop=True)
        scores,mass=native.infer_native_experts(valid,meta,models,contract)
        train=native.native_partition(frame,boundary,union,'3y')
        prior=np.bincount(train.label.to_numpy(dtype=int),minlength=3)/len(train)
        diagnostics={name:prior_unbalance(scores[name],prior) for name in ['legacy_trend','legacy_risk']}
        diagnostics['legacy_equal']=(diagnostics['legacy_trend']+diagnostics['legacy_risk'])/2
        diagnostics['density_all']=np.mean([mass[name] for name in ['3y_raw','3y_normalized','expanding_raw','expanding_normalized']],axis=0)
        diagnostics['density_expanding']=(mass['expanding_raw']+mass['expanding_normalized'])/2
        selected=held_choices(rows.Date,events)
        result=rows[['Date','label_end_date','label','future_return','outer_fold','prediction','bundle']].copy().reset_index(drop=True)
        result['selected_expert']=selected
        chosen_scores=np.stack([scores[name][i] for i,name in enumerate(selected)])
        chosen_mass=np.stack([diagnostics[name][i] for i,name in enumerate(selected)])
        np.testing.assert_array_equal(chosen_scores.argmax(axis=1),result.prediction)
        for name in contract['selector_pool']:
            for k,cls in enumerate(CLASSES):result[name+'_score_'+cls]=scores[name][:,k]
        for k,cls in enumerate(CLASSES):
            result['decision_score_'+cls]=chosen_scores[:,k]
            result['component_mass_'+cls]=chosen_mass[:,k]
        parts.append(result)
    archive=pd.concat(parts,ignore_index=True).sort_values('Date').reset_index(drop=True)
    np.testing.assert_array_equal(archive.Date,records.Date)
    np.testing.assert_array_equal(archive.prediction,records.prediction)
    for prefix in ['decision_score_','component_mass_']:
        values=archive[[prefix+c for c in CLASSES]].to_numpy()
        np.testing.assert_allclose(values.sum(axis=1),1.)
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid archive vector')
    path=output/'native_expert_scores.csv';archive.to_csv(path,index=False)
    manifest=dict(role='Native historical OOF research replay, NOT prospective forecasts or calibrated probabilities',rows=len(archive),
                  created_at=datetime.now(timezone.utc).isoformat(),candidate_id=contract['candidate_id'],contract_sha256=native.sha(contract_path),
                  native_lock_sha256=native.sha(artifact/'native_runtime_lock.json'),source_sha256=native.sha(__file__),
                  data_sha256=native.sha(path),source_parity_report_sha256=lock['parity_report_sha256'],
                  semantics={'decision_score':'Class-balanced expert score used by frozen point-decision policy, NOT event probability',
                             'component_mass':'Approximate prior unbalance for classifier or raw quantile mass for density; requires evaluation/calibration, NOT established probability',
                             'label':'T+20 realized class, available only once label_end_date strictly precedes a calibration/refit date'},
                  label_timing_rule='Every later calibrator must use label_end_date < current decision/refit date; never random CV.',
                  selector_event_identity_matches=len(events),point_decision_matches=len(archive))
    (output/'archive_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2),flush=True)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=native.CONTRACT)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    output=args.output_dir or ROOT/'reports/regime_native_scores'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    print('Output: '+str(output.resolve()),flush=True)
    return export_native_score_archive(args.contract,output)


if __name__=='__main__':main()
