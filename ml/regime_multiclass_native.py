"""Independent native replay of frozen THREE-CLASS research challenger.

Research only. Fits mature labels, saves/reloads native boosters, independently
recomputes quantile masses and delayed expert choice. No deployment/emission.
"""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import tempfile

import lightgbm as lgb
import numpy as np
import pandas as pd

import train_regime_v2 as features
from experiment_regime import long_features

ROOT=Path(__file__).resolve().parent
CONTRACT=ROOT/'artifacts/regime_multiclass_candidate_20261018/contract.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_native_contract(path=CONTRACT):
    contract=json.loads(Path(path).read_text())
    if contract['candidate_id']!='multiclass_delayed_experts_v1':raise ValueError('Unsupported candidate')
    for name,digest in contract['source_component_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen component changed: '+name)
    for package,expected in contract['environment'].items():
        if version(package)!=expected:raise ValueError('Frozen dependency changed: '+package)
    for path,digest in contract['source_prediction_hashes'].items():
        if sha(path)!=digest:raise ValueError('Source forecast archive changed')
    for path,digest in contract['source_reports'].items():
        resolved=Path(path) if Path(path).is_absolute() else ROOT.parent/path
        if sha(resolved)!=digest:raise ValueError('Frozen source report changed')
    return contract


def prepare_multiclass_native(data_dir,contract):
    data_dir=Path(data_dir)
    index,index_audit=features.load_market_data(data_dir/'VNINDEX.csv')
    etf,etf_audit=features.load_market_data(data_dir/'E1VFVN30.csv')
    for name,audit in [('VNINDEX',index_audit),('E1VFVN30',etf_audit)]:
        if audit['sha256']!=contract['source_data_hashes'][name]:raise ValueError('Reviewed source changed: '+name)
    frame=feature_frame_native(index,etf)
    return frame,index,etf


def feature_frame_native(index,etf):
    frame,_=features.build_feature_matrix(index,etf,'close-etf')
    frame=pd.concat([frame,long_features(index)],axis=1)
    price=index.Price.astype(float)
    future=price.shift(-20)/price-1
    frame['label_end_date']=index.Date.shift(-20)
    frame['future_return']=future
    frame['future_log_return']=np.log1p(future)
    frame['horizon_sigma']=np.log(price).diff().rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
    label=pd.Series(pd.NA,index=frame.index,dtype='Int64')
    known=future.notna()
    label.loc[known]=np.where(future[known]<-.05,0,np.where(future[known]>.05,2,1))
    frame['label']=label
    # Keep current unlabelled rows; partitions alone decide label availability.
    return frame


def native_partition(frame,boundary,names,window):
    boundary=pd.Timestamp(boundary)
    valid=np.isfinite(frame[names].to_numpy(dtype=float)).all(axis=1)
    valid &= frame.label.notna()&frame.label_end_date.notna()&(frame.Date<boundary)&(frame.label_end_date<boundary)
    if window=='3y':valid &= frame.Date>=boundary-pd.DateOffset(years=3)
    elif window!='expanding':raise ValueError('Unsupported window')
    train=frame.loc[valid].copy()
    if len(train)<30 or set(train.label.astype(int))!={0,1,2}:raise ValueError('Insufficient mature three-class training')
    return train


def prefix_digest(index,etf,boundary):
    digest=hashlib.sha256()
    for frame in [index,etf]:
        names=['Date','Price']+(['Volume'] if 'Volume' in frame else [])
        digest.update(frame.loc[frame.Date<boundary,names].to_csv(index=False).encode())
    return digest.hexdigest()


def load_native_bundle(directory,identity):
    directory=Path(directory);metadata=directory/'bundle.json'
    if sha(metadata)!=(directory/'bundle.sha256').read_text().strip():raise ValueError('Native bundle metadata changed')
    meta=json.loads(metadata.read_text())
    for key,value in identity.items():
        if meta.get(key)!=value:raise ValueError('Native bundle identity mismatch: '+key)
    models={}
    for item in meta['components']:
        for model in item['models']:
            path=directory/model['file']
            if path.parent!=directory or sha(path)!=model['sha256']:raise ValueError('Native booster changed')
            models[model['file']]=lgb.Booster(model_file=str(path))
    return meta,models


def fit_native_bundle(frame,index,etf,boundary,legacy_parameters,contract,contract_path,cache,check):
    boundary=pd.Timestamp(boundary);cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    identity=dict(contract_sha256=sha(contract_path),runtime_sha256=sha(__file__),refit_date=str(boundary.date()),
                  training_prefix_sha256=prefix_digest(index,etf,boundary),
                  legacy_parameters_sha256=hashlib.sha256(json.dumps(legacy_parameters,sort_keys=True).encode()).hexdigest())
    key=identity['refit_date']+'_'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    directory=cache/key
    if directory.exists():return key,*load_native_bundle(directory,identity)
    temp=Path(tempfile.mkdtemp(prefix='building_',dir=cache));components=[]
    union=list(dict.fromkeys(contract['feature_schemas']['trend']+contract['feature_schemas']['risk']))
    legacy_train=native_partition(frame,boundary,union,'3y')
    for group in ['trend','risk']:
        names=contract['feature_schemas'][group]
        X=legacy_train[names].to_numpy(dtype=np.float32);V=check[names].to_numpy(dtype=np.float32)
        model=lgb.LGBMClassifier(**legacy_parameters[group])
        model.fit(X,legacy_train.label.to_numpy(dtype=np.int64))
        if list(model.classes_)!=[0,1,2]:raise ValueError('Unexpected class ordering')
        file='legacy_'+group+'.txt';model.booster_.save_model(str(temp/file))
        native=lgb.Booster(model_file=str(temp/file));a=model.predict_proba(V);b=native.predict(V,num_threads=2)
        np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-12)
        components.append(dict(name='legacy_'+group,kind='classifier',features=names,classes=[0,1,2],n_train=len(legacy_train),
                               train_label_end=str(legacy_train.label_end_date.max().date()),
                               roundtrip_max_error=float(np.max(np.abs(a-b))),models=[dict(file=file,sha256=sha(temp/file))]))
    names=contract['density_features'];refit=contract['model_refit']
    for window in refit['density_train_windows']:
        train=native_partition(frame,boundary,names,window)
        if not np.isfinite(train.horizon_sigma).all() or (train.horizon_sigma<=0).any():raise ValueError('Invalid known sigma')
        prior=np.bincount(train.label.to_numpy(dtype=int),minlength=3)/len(train)
        for normalized in [False,True]:
            component=window+('_normalized' if normalized else '_raw')
            y=train.future_log_return.to_numpy(dtype=float)
            if normalized:y=y/train.horizon_sigma.to_numpy()
            X=train[names].to_numpy(dtype=np.float32);V=check[names].to_numpy(dtype=np.float32)
            models=[];error=0.
            for alpha in refit['quantiles']:
                model=lgb.LGBMRegressor(**refit['density_parameters'],alpha=alpha);model.fit(X,y)
                file=f'{component}_q{round(alpha*100):02d}.txt';model.booster_.save_model(str(temp/file))
                native=lgb.Booster(model_file=str(temp/file));a=model.predict(V);b=native.predict(V,num_threads=2)
                np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-12);error=max(error,float(np.max(np.abs(a-b))))
                models.append(dict(alpha=alpha,file=file,sha256=sha(temp/file)))
            components.append(dict(name=component,kind='quantiles',features=names,window=window,normalized=normalized,class_prior=prior.tolist(),
                                   n_train=len(train),train_label_end=str(train.label_end_date.max().date()),roundtrip_max_error=error,models=models))
    meta=dict(**identity,components=components)
    (temp/'bundle.json').write_text(json.dumps(meta,indent=2)+'\n');(temp/'bundle.sha256').write_text(sha(temp/'bundle.json')+'\n')
    try:os.rename(temp,directory)
    except FileExistsError:
        import shutil
        shutil.rmtree(temp)
    return key,*load_native_bundle(directory,identity)


def infer_native_experts(valid,metadata,models,contract):
    experts={};density={};raw_mass={};refit=contract['model_refit'];weights=np.asarray(refit['quantile_atom_weights'])
    for item in metadata['components']:
        X=valid[item['features']].to_numpy(dtype=np.float32)
        if item['kind']=='classifier':
            experts[item['name']]=np.asarray(models[item['models'][0]['file']].predict(X,num_threads=2))
        else:
            q=np.column_stack([models[m['file']].predict(X,num_threads=2) for m in item['models']])
            if item['normalized']:q*=valid.horizon_sigma.to_numpy()[:,None]
            q=np.sort(q,axis=1)
            bear=q<np.log(.95);bull=q>np.log(1.05)
            mass=np.column_stack([(mask*weights).sum(axis=1) for mask in [bear,~(bear|bull),bull]])
            mass/=mass.sum(axis=1,keepdims=True);raw_mass[item['name']]=mass
            corrected=mass/np.asarray(item['class_prior']);corrected/=corrected.sum(axis=1,keepdims=True)
            density[item['name']]=corrected
    experts['legacy_equal']=(experts['legacy_trend']+experts['legacy_risk'])/2
    experts['density_all']=np.mean([density[name] for name in ['3y_raw','3y_normalized','expanding_raw','expanding_normalized']],axis=0)
    experts['density_expanding']=(density['expanding_raw']+density['expanding_normalized'])/2
    for values in experts.values():
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid native expert scores')
        np.testing.assert_allclose(values.sum(axis=1),1.)
    return experts,raw_mass


def native_choose(history,boundary,contract):
    rule=contract['selector'];pool=contract['selector_pool']
    known=history.loc[(history.Date<boundary)&(history.label_end_date<boundary)].tail(rule['history_rows'])
    counts=np.bincount(known.label.to_numpy(dtype=int),minlength=3) if len(known) else np.zeros(3,dtype=int)
    info=dict(n=len(known),label_end=str(known.label_end_date.max()) if len(known) else None)
    if len(known)<rule['history_rows'] or (counts<rule['min_class_count']).any():return 'legacy_equal',info
    scores={}
    for name in pool:
        matrix=np.bincount(3*known.label.to_numpy(dtype=int)+known[name].to_numpy(dtype=int),minlength=9).reshape(3,3)
        denominator=matrix.sum(axis=0)+matrix.sum(axis=1)
        scores[name]=float(np.divide(2*np.diag(matrix),denominator,out=np.zeros(3),where=denominator>0).mean())
    best=max(pool,key=lambda name:scores[name])
    return (best if scores[best]>=scores['legacy_equal']+rule['improvement_margin'] else 'legacy_equal'),dict(**info,scores=scores)


def native_selector(records,calendar,contract):
    records=records.sort_values('Date').reset_index(drop=True)
    positions=pd.DatetimeIndex(calendar).get_indexer(records.Date)
    anchor=pd.DatetimeIndex(calendar).get_indexer([pd.Timestamp(contract['selector_anchor'])])[0]
    if (positions<0).any() or anchor<0:raise ValueError('Missing selector calendar/anchor')
    buckets=(positions-anchor)//contract['selector']['refit_market_sessions']
    result=[];audits=[];last=None;selected=None
    for i in range(len(records)):
        if buckets[i]!=last:
            selected,audit=native_choose(records.iloc[:i],records.Date.iloc[i],contract)
            audits.append(dict(Date=str(records.Date.iloc[i].date()),selected=selected,**audit));last=buckets[i]
        result.append(int(records[selected].iloc[i]))
    return np.asarray(result),audits


def replay_native(contract_path,data_dir,output):
    contract_path=Path(contract_path);contract=read_native_contract(contract_path);artifact=contract_path.parent
    manifest=json.loads((artifact/'historical_replay_manifest.json').read_text())
    original=ROOT.parent/manifest['original_report']
    if sha(original)!=manifest['original_report_sha256']:raise ValueError('Historical parameter report changed')
    frame,index,etf=prepare_multiclass_native(data_dir,contract)
    source=next(Path(p) for p in contract['source_prediction_hashes'] if Path(p).name=='legacy_equal_63_predictions.csv')
    cohort=pd.read_csv(source,parse_dates=['Date','label_end_date'])
    by_date=frame.set_index('Date',drop=False);records=[];all_scores={name:[] for name in contract['selector_pool']};all_masses={};bundles=[]
    for fold,rows in cohort.groupby('outer_fold',sort=True):
        positions=pd.DatetimeIndex(index.Date).get_indexer(rows.Date);buckets=(positions-positions[0])//contract['model_refit']['market_sessions']
        params={group:next(r['best_params'] for r in manifest['legacy_models'][group]['per_fold_parameters'] if r['outer_fold']==int(fold)) for group in ['trend','risk']}
        for number in np.unique(buckets):
            dates=rows.Date.iloc[np.flatnonzero(buckets==number)]
            valid=by_date.loc[dates].reset_index(drop=True);boundary=valid.Date.min()
            key,meta,models=fit_native_bundle(frame,index,etf,boundary,params,contract,contract_path,artifact/'native_bundles',valid)
            experts,masses=infer_native_experts(valid,meta,models,contract)
            row=valid[['Date','label_end_date','label','future_return']].copy();row['outer_fold']=int(fold);row['bundle']=key
            for name in contract['selector_pool']:
                row[name]=experts[name].argmax(axis=1);all_scores[name].append(experts[name])
            for name,values in masses.items():all_masses.setdefault(name,[]).append(values)
            records.append(row);bundles.append(dict(fold=int(fold),bucket=int(number),bundle=key,components=len(meta['components']),models=sum(len(c['models']) for c in meta['components'])))
        print('Native fold',int(fold),'complete',flush=True)
    records=pd.concat(records,ignore_index=True);records['prediction'],selector_audit=native_selector(records,index.Date,contract)
    np.testing.assert_array_equal(records.Date,cohort.Date)
    output=Path(output);records.to_csv(output/'native_predictions.csv',index=False)
    selector_source=next((ROOT.parent/Path(p)).parent for p in contract['source_reports'] if Path(p).name=='report.json' and 'regime_expert_selection' in p)
    expected=pd.read_csv(selector_source/'delayed_selector_predictions.csv',parse_dates=['Date'])
    matches=int((records.prediction.to_numpy()==expected.prediction.to_numpy()).sum());max_error=0.;expert_matches={}
    reference_matrices={}
    for name in ['legacy_trend','legacy_risk','legacy_equal']:
        path=next(Path(p) for p in contract['source_prediction_hashes'] if Path(p).name==name+'_63_predictions.csv')
        reference_matrices[name]=pd.read_csv(path)[['p_bear','p_side','p_bull']].to_numpy()
    corrected={}
    for name,masses in all_masses.items():
        path=next(Path(p) for p in contract['source_prediction_hashes'] if Path(p).name==name+'_predictions.csv')
        expected_density=pd.read_csv(path);actual=np.concatenate(masses)
        raw=expected_density[['p_bear','p_side','p_bull']].to_numpy();np.testing.assert_allclose(actual,raw,rtol=1e-12,atol=1e-12)
        prior=expected_density[['base_bear','base_side','base_bull']].to_numpy();values=raw/prior;values/=values.sum(axis=1,keepdims=True);corrected[name]=values
    reference_matrices['density_all']=np.mean([corrected[name] for name in ['3y_raw','3y_normalized','expanding_raw','expanding_normalized']],axis=0)
    reference_matrices['density_expanding']=(corrected['expanding_raw']+corrected['expanding_normalized'])/2
    for name,matrices in all_scores.items():
        actual=np.concatenate(matrices);reference=reference_matrices[name]
        max_error=max(max_error,float(np.max(np.abs(actual-reference))))
        expert_matches[name]=int((actual.argmax(axis=1)==reference.argmax(axis=1)).sum())
    report=dict(role='Native independent DEVELOPMENT replay; not independent forecast-quality test',passed=matches==len(records) and max_error<1e-12 and all(n==len(records) for n in expert_matches.values()),
                n_predictions=len(records),selector_matches=matches,expert_matches=expert_matches,max_score_error=max_error,
                bundles=len(bundles),native_models=sum(b['models'] for b in bundles),contract_sha256=sha(contract_path),runtime_sha256=sha(__file__),
                metadata_manifest_sha256=sha(artifact/'historical_replay_manifest.json'),created_at=datetime.now(timezone.utc).isoformat())
    (output/'parity_report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'bundles.json').write_text(json.dumps(bundles,indent=2)+'\n');(output/'selector_history.json').write_text(json.dumps(selector_audit,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if not report['passed']:raise ValueError('Native parity failed; do not freeze or emit')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=CONTRACT)
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    output=args.output_dir or ROOT/'reports/regime_multiclass_native'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    print('Output: '+str(output.resolve()),flush=True)
    return replay_native(args.contract,args.data_dir,output)


if __name__=='__main__':main()
