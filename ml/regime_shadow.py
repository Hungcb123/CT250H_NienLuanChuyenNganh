"""Frozen VNINDEX research challenger runtime. No production or trade execution.

Native LightGBM bundles; fixed causal replay; append-only prospective evidence.
Research backcasts can initialize history but never receive prospective status.
"""
import argparse
from datetime import datetime,timezone,time
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.special import logit

import experiment_regime_candidates as feature_helpers
import experiment_regime_labels as labels
import regime_shadow_ledger as ledger

ROOT=Path(__file__).resolve().parent
CONTRACT=ROOT/'artifacts/regime_shadow_candidate_20261017_v2/contract.json'
BASE_DATA=ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv'
BASE_HASH='19bf8eb2c8dda7d73498d8d21e9303a7627484a8a4e6178458529e4ad5c1c3b6'
TZ=ZoneInfo('Asia/Ho_Chi_Minh')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_contract(path=CONTRACT):
    path=Path(path);contract=json.loads(path.read_text())
    if contract['candidate_id']!='equal_standardized_3y_expanding_online120_v1':raise ValueError('Unsupported candidate contract')
    for name,digest in contract['source_component_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen source changed: '+name)
    import lightgbm,sklearn
    if {'lightgbm':lightgbm.__version__,'sklearn':sklearn.__version__}!=contract['environment']:raise ValueError('Frozen environment versions differ')
    if sha(ROOT/contract['development_source'])!=contract['development_predictions_sha256']:raise ValueError('Development score archive changed')
    return contract


def load_index(path=BASE_DATA):
    if sha(BASE_DATA)!=BASE_HASH:raise ValueError('Reviewed base snapshot changed')
    base,_=labels.exp.base.load_market_data(BASE_DATA)
    index,audit=labels.exp.base.load_market_data(path)
    prefix=index.loc[index.Date<=base.Date.max()].reset_index(drop=True)
    if not prefix.Date.equals(base.Date):raise ValueError('Extended calendar changed reviewed prefix')
    np.testing.assert_allclose(prefix.Price,base.Price,rtol=0,atol=1e-12,err_msg='Reviewed price prefix changed')
    if index.Date.max()>base.Date.max():verify_extension(path,index,base,audit)
    return index,audit


def verify_extension(path,index,base,audit):
    from prepare_regime_indices import close_response
    path=Path(path)
    provenance_path=path.with_suffix('.provenance.json')
    provenance=json.loads(provenance_path.read_text())
    manifest_path=path.parent/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if provenance.get('base_snapshot_sha256')!=BASE_HASH or provenance.get('manifest_sha256')!=sha(manifest_path) or manifest.get('status')!='accepted' or manifest.get('canonical_sha256')!=audit['sha256']:
        raise ValueError('Extended snapshot provenance/acceptance mismatch')
    frames={}
    for provider in ['vci','vnd']:
        item=manifest['sources'][provider];raw=(path.parent/item['response']).resolve()
        if not raw.is_relative_to(path.parent.resolve()) or sha(raw)!=item['response_sha256']:raise ValueError('Archived source changed')
        frames[provider]=close_response(json.loads(raw.read_text()),provider,'VNINDEX',manifest['requested_start'],manifest['requested_end'])
        overlap=base[['Date','Price']].merge(frames[provider],on='Date',validate='one_to_one')
        if len(overlap)<10 or ((overlap.Price-overlap.Close).abs()>.011).any():raise ValueError('Source no longer matches reviewed overlap')
    a,b=[frames[p].loc[frames[p].Date>base.Date.max()].reset_index(drop=True) for p in ['vci','vnd']]
    tail=index.loc[index.Date>base.Date.max()].reset_index(drop=True)
    if not a.Date.equals(b.Date) or not a.Date.equals(tail.Date) or ((a.Close-b.Close).abs()>.011).any():raise ValueError('Fresh source calendar/close disagreement')
    np.testing.assert_allclose(tail.Price,(a.Close+b.Close)/2,rtol=0,atol=1e-12,err_msg='Fresh canonical close differs from source evidence')


def feature_frame(index,contract):
    features,names=labels.exp.base.build_feature_matrix(index,feature_set='close')
    features=pd.concat([features,labels.exp.long_features(index)],axis=1)
    features=features.merge(feature_helpers.reversal_features(index),on='Date',validate='one_to_one',sort=False)
    names+=labels.exp.TREND_NAMES+labels.exp.RISK_NAMES+feature_helpers.EXTRA
    if names!=contract['feature_schema']:raise ValueError('Feature order/schema changed')
    book=labels.build_label_book(index)
    frame=features.merge(book[['Date','label_end_date','future_return','future_log_return','horizon_sigma','vol_label']],on='Date',validate='one_to_one',sort=False)
    frame['label']=frame.vol_label
    # Filter ONLY unavailable features, retaining dates with not-yet-known outcomes.
    return frame.loc[np.isfinite(frame[names].to_numpy()).all(axis=1)].reset_index(drop=True)


def refit_boundary(calendar,decision,contract):
    calendar=pd.DatetimeIndex(calendar)
    anchor=calendar.get_indexer([pd.Timestamp(contract['latest_refit_anchor'])])[0]
    position=calendar.get_indexer([pd.Timestamp(decision)])[0]
    if anchor<0 or position<anchor:raise ValueError('Missing date or decision before frozen refit anchor')
    step=contract['refit_market_sessions']
    return calendar[anchor+((position-anchor)//step)*step]


def partition(frame,boundary,window,contract):
    known=(frame.Date<boundary)&frame.label_end_date.notna()&(frame.label_end_date<boundary)&frame.label.notna()
    if window!='expanding':known &= frame.Date>=boundary-pd.DateOffset(years=int(window[:-1]))
    mature=frame.loc[known]
    n=contract['calibration_rows'];cal=mature.iloc[-n:]
    core=mature.iloc[:-n]
    core=core.loc[core.label_end_date<cal.Date.min()]
    if len(cal)!=n or len(core)<150 or set(core.label.astype(int))!={0,1,2}:raise ValueError('Insufficient purged calibration/core history')
    if core.label_end_date.max()>=cal.Date.min() or cal.label_end_date.max()>=boundary:raise ValueError('Label overlap at runtime')
    return core,cal


def load_bundle(directory,expected):
    import lightgbm
    meta=json.loads((directory/'bundle.json').read_text())
    for key,value in expected.items():
        if meta.get(key)!=value:raise ValueError('Bundle identity mismatch: '+key)
    models=[]
    for expert in meta['experts']:
        path=directory/expert['model_file']
        if sha(path)!=expert['model_sha256']:raise ValueError('Model bundle changed')
        models.append(lightgbm.Booster(model_file=str(path)))
    return meta,models


def fit_bundle(frame,index,boundary,contract,contract_path,cache):
    import lightgbm
    prefix=index.loc[index.Date<boundary,['Date','Price']].to_csv(index=False).encode()
    identity=dict(contract_sha256=sha(contract_path),runtime_sha256=sha(__file__),
                  training_prefix_sha256=hashlib.sha256(prefix).hexdigest(),refit_date=str(boundary.date()))
    key=str(boundary.date())+'_'+identity['contract_sha256'][:8]+'_'+identity['runtime_sha256'][:8]+'_'+identity['training_prefix_sha256'][:8]
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True);directory=cache/key
    if directory.exists():return key,*load_bundle(directory,identity)
    temp=Path(tempfile.mkdtemp(prefix='building_',dir=cache))
    experts=[];calibration_scores=[];calibration_dates=None
    for i,window in enumerate(contract['experts']):
        core,cal=partition(frame,boundary,window,contract)
        if calibration_dates is not None and not cal.Date.equals(calibration_dates):raise ValueError('Expert calibration dates differ')
        calibration_dates=cal.Date
        model=lightgbm.LGBMClassifier(**contract['learner']['parameters'])
        model.fit(core[contract['feature_schema']].to_numpy(),core.label.to_numpy(dtype=np.int64))
        classes=list(map(int,model.classes_))
        if classes!=[0,1,2]:raise ValueError('Unexpected multiclass output order')
        q=model.predict_proba(cal[contract['feature_schema']].to_numpy())[:,0]
        values=logit(np.clip(q,contract['normalization']['clip_epsilon'],1-contract['normalization']['clip_epsilon']))
        center=float(values.mean());scale=max(float(values.std()),.25)
        normalized=(values-center)/scale
        calibration_scores.append(normalized)
        model_file=f'expert_{i}.txt';model.booster_.save_model(str(temp/model_file))
        # Native serialization must preserve probabilities before accepting a bundle.
        restored=lightgbm.Booster(model_file=str(temp/model_file))
        native=restored.predict(cal[contract['feature_schema']].to_numpy(),num_threads=2)[:,0]
        np.testing.assert_allclose(native,q,rtol=1e-12,atol=1e-12)
        experts.append(dict(window=window,classes=classes,model_file=model_file,model_sha256=sha(temp/model_file),
                            logit_center=center,logit_scale=scale,calibration_threshold=float(np.quantile(normalized,.9,method='higher')),n_core=len(core),n_calibration=len(cal),
                            core_start=str(core.Date.min().date()),core_end=str(core.Date.max().date()),
                            core_label_end=str(core.label_end_date.max().date()),calibration_start=str(cal.Date.min().date()),
                            calibration_end=str(cal.Date.max().date()),calibration_label_end=str(cal.label_end_date.max().date())))
    combined=np.asarray(contract['expert_weights'])@np.asarray(calibration_scores)
    meta=dict(**identity,feature_schema=contract['feature_schema'],experts=experts,
              calibration_threshold=float(np.quantile(combined,.9,method='higher')))
    (temp/'bundle.json').write_text(json.dumps(meta,indent=2)+'\n')
    try:os.rename(temp,directory)
    except FileExistsError:
        import shutil
        shutil.rmtree(temp)
    return key,*load_bundle(directory,identity)


def archived_history(contract,start):
    source=pd.read_csv(ROOT/contract['development_source'],parse_dates=['Date'])
    return source.loc[source.Date<pd.Timestamp(start),['Date','risk_score']].sort_values('Date').to_dict('records')


def replay(index,contract,contract_path,start,end,cache):
    frame=feature_frame(index,contract);calendar=pd.DatetimeIndex(index.Date)
    requested_start=pd.Timestamp(start)
    archive_end=pd.read_csv(ROOT/contract['development_source'],parse_dates=['Date']).Date.max()
    internal_start=min(requested_start,archive_end+pd.Timedelta(days=1))
    dates=frame.loc[frame.Date.between(internal_start,pd.Timestamp(end)),'Date']
    if dates.empty or not (dates>=requested_start).any():raise ValueError('No requested feature-complete sessions')
    history=archived_history(contract,dates.iloc[0]);records=[];current_key=None
    for decision in dates:
        boundary=refit_boundary(calendar,decision,contract)
        if current_key is None or pd.Timestamp(meta['refit_date'])!=boundary:
            current_key,meta,models=fit_bundle(frame,index,boundary,contract,contract_path,cache)
        row=frame.loc[frame.Date==decision].iloc[0]
        X=row[contract['feature_schema']].to_numpy(dtype=float).reshape(1,-1)
        scores=[];probabilities=[]
        for expert,model in zip(meta['experts'],models):
            q=np.asarray(model.predict(X,num_threads=2)).reshape(-1)
            if len(q)!=3 or not np.isfinite(q).all():raise ValueError('Invalid native model output')
            probabilities.append(q.tolist())
            p=np.clip(q[0],contract['normalization']['clip_epsilon'],1-contract['normalization']['clip_epsilon'])
            scores.append(float((logit(p)-expert['logit_center'])/expert['logit_scale']))
        value=float(np.dot(contract['expert_weights'],scores))
        if any(pd.Timestamp(h['Date'])>=decision for h in history):raise ValueError('Current/future score in history')
        window=contract['threshold']['window']
        threshold=float(np.quantile([h['risk_score'] for h in history[-window:]],.9,method='higher')) if len(history)>=window else meta['calibration_threshold']
        record=dict(Date=str(decision.date()),decision_close=float(row.Price),risk_score=value,threshold=threshold,alarm=bool(value>threshold),
                    baselines={expert['window']:{'risk_score':score,'threshold':expert['calibration_threshold'],'alarm':bool(score>expert['calibration_threshold'])} for expert,score in zip(meta['experts'],scores)},
                    model_bundle=current_key,refit_date=meta['refit_date'],n_prior_scores=len(history),
                    expert_standardized_scores=scores,relative_regime_probabilities=probabilities,
                    feature_sha256=hashlib.sha256(X.tobytes()).hexdigest(),mode='research_backcast')
        if decision>=requested_start:records.append(record)
        history.append(dict(Date=decision,risk_score=value))
    return records


def prospective_timing(decision,emitted_at,frozen_at):
    emitted=pd.Timestamp(emitted_at)
    if emitted.tz is None:raise ValueError('Emission time must be timezone aware')
    local=emitted.tz_convert(TZ)
    decision=pd.Timestamp(decision)
    if local.date()!=decision.date() or local.dayofweek>=5 or local.time()<time(15,5):raise ValueError('Prospective emission requires SAME completed-session date after 15:05 Vietnam time')
    if emitted<=pd.Timestamp(frozen_at):raise ValueError('Prediction predates runtime freeze')


def write_parity(records,contract,output):
    expected=pd.read_csv(ROOT/contract['development_source'],parse_dates=['Date'])
    actual=pd.DataFrame(records);actual['Date']=pd.to_datetime(actual.Date)
    joined=actual.merge(expected[['Date','risk_score','threshold','alarm']],on='Date',suffixes=('_runtime','_research'),validate='one_to_one')
    if len(joined)!=len(actual):raise ValueError('Parity scope contains dates outside research archive')
    np.testing.assert_allclose(joined.risk_score_runtime,joined.risk_score_research,rtol=1e-9,atol=1e-9)
    np.testing.assert_allclose(joined.threshold_runtime,joined.threshold_research,rtol=1e-9,atol=1e-9)
    np.testing.assert_array_equal(joined.alarm_runtime,joined.alarm_research)
    report=dict(passed=True,n_decisions=len(joined),start=str(actual.Date.min().date()),end=str(actual.Date.max().date()),
                reference_predictions_sha256=contract['development_predictions_sha256'],runtime_sha256=sha(__file__),
                max_score_absolute_error=float((joined.risk_score_runtime-joined.risk_score_research).abs().max()),
                max_threshold_absolute_error=float((joined.threshold_runtime-joined.threshold_research).abs().max()))
    Path(output).write_text(json.dumps(report,indent=2)+'\n');return report


def freeze_runtime(contract_path,parity_path):
    contract=read_contract(contract_path);report=json.loads(Path(parity_path).read_text())
    if not report['passed'] or report['n_decisions']<390 or report['runtime_sha256']!=sha(__file__) or report['reference_predictions_sha256']!=contract['development_predictions_sha256']:
        raise ValueError('Need full latest-fold runtime parity before freezing')
    lock=dict(contract_sha256=sha(contract_path),runtime_sha256=sha(__file__),ledger_sha256=sha(Path(__file__).with_name('regime_shadow_ledger.py')),
              runtime_frozen_at=datetime.now(timezone.utc).isoformat(),parity_report_sha256=sha(parity_path),
              frozen_dependency_sha256={name:sha(ROOT/name) for name in ['regime_shadow_ledger.py','collect_regime_shadow_data.py','prepare_regime_indices.py','prepare_regime_data.py']},
              status='research_only_not_approved_for_live',prospective_ledger='prospective_predictions.jsonl')
    path=Path(contract_path).parent/'runtime_lock.json'
    with path.open('x') as handle:json.dump(lock,handle,indent=2);handle.write('\n')
    return lock


def check_runtime_lock(contract_path=CONTRACT):
    lock=json.loads((Path(contract_path).parent/'runtime_lock.json').read_text())
    if lock['contract_sha256']!=sha(contract_path) or lock['runtime_sha256']!=sha(__file__):raise ValueError('Frozen runtime changed')
    for name,digest in lock['frozen_dependency_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen dependency changed: '+name)
    return lock


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=CONTRACT)
    parser.add_argument('--data',type=Path,default=BASE_DATA)
    parser.add_argument('--cache',type=Path,default=ROOT/'artifacts/regime_shadow_candidate_20261017_v2/bundles')
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--verify-parity',action='store_true')
    parser.add_argument('--freeze-from-parity',type=Path)
    parser.add_argument('--emit',action='store_true')
    args=parser.parse_args(argv)
    contract=read_contract(args.contract)
    if args.freeze_from_parity:
        print(json.dumps(freeze_runtime(args.contract,args.freeze_from_parity),indent=2));return
    index,audit=load_index(args.data)
    if args.emit:
        lock=check_runtime_lock(args.contract)
        decision=index.Date.max()
        prospective_timing(decision,datetime.now(timezone.utc),lock['runtime_frozen_at'])
        path=args.contract.parent/lock['prospective_ledger']
        record_id=contract['candidate_id']+':'+str(decision.date())
        previous=next((r for r in ledger.read_ledger(path) if r['record_id']==record_id),None)
        if previous:
            print(json.dumps(previous,indent=2));return previous
        # Seed any earlier unavailable-to-the-live-log scores explicitly as research
        # backcasts, never as prospective predictions or realized performance.
        source=pd.read_csv(ROOT/contract['development_source'],parse_dates=['Date'])
        start=source.Date.max()+pd.Timedelta(days=1)
        records=replay(index,contract,args.contract,start,decision,args.cache)
        record=records[-1]
        if pd.Timestamp(record['Date'])!=decision:raise ValueError('Latest close has missing features')
        emitted=datetime.now(timezone.utc).isoformat()
        prospective_timing(decision,emitted,lock['runtime_frozen_at'])
        record.update(kind='prediction',record_id=record_id,candidate_id=contract['candidate_id'],mode='prospective',emitted_at=emitted,
                      contract_sha256=sha(args.contract),runtime_sha256=sha(__file__),source_snapshot_sha256=audit['sha256'],
                      history_initialization='archived historical research + causal backcast state; earlier backcasts excluded from prospective metrics')
        result=ledger.append_record(path,record);print(json.dumps(result,indent=2));return result
    if not args.start or not args.end or not args.output_dir:parser.error('Replay requires --start --end --output-dir, or use --emit')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    records=replay(index,contract,args.contract,args.start,args.end,args.cache)
    pd.DataFrame(records).to_json(args.output_dir/'research_backcast.jsonl',orient='records',lines=True)
    pd.DataFrame(records).drop(columns=['relative_regime_probabilities','expert_standardized_scores']).to_csv(args.output_dir/'research_backcast.csv',index=False)
    if args.verify_parity:print(json.dumps(write_parity(records,contract,args.output_dir/'parity_report.json'),indent=2))
    print('Research backcast only. '+str(args.output_dir.resolve()))
    return records


if __name__=='__main__':main()
