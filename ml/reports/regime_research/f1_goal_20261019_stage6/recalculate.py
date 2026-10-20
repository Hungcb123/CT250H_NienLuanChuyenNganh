"""Independent labels/metrics, mixing, calendar selection and history audit."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score,matthews_corrcoef,precision_recall_fscore_support
from sklearn.covariance import LedoitWolf

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--allow-running',action='store_true');args=parser.parse_args()
all_dirs=[ROOT/'reports/regime_metric_analog/20261019T073046_885436Z',ROOT/'reports/regime_extended_forest/20261019T073305_918472Z',ROOT/'reports/regime_relative_volume/20261019T083345_837476Z']
directories=[p for p in all_dirs if (p/'comparison.csv').exists() or not args.allow_running]
market=pd.read_csv(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv',parse_dates=['Date'])
lp=np.log(market.Close);sigma=lp.diff().rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
forward=lp.shift(-20)-lp;end=market.Date.shift(-20)
book=pd.DataFrame(dict(Date=market.Date,label_end_date=end,label=np.where(forward<-sigma,0,np.where(forward>sigma,2,1))))
sources={};verified=[];timings=[]
for directory in directories:
    assert (directory/'comparison.csv').exists(),'Study not complete: '+str(directory)
    plan=json.loads((directory/'plan.json').read_text())
    assert plan['labels']['20']['policy']=='vol_1sigma'
    for path,digest in plan['source_hashes'].items():
        actual=hashlib.sha256(Path(path).read_bytes()).hexdigest();assert actual==digest,path;sources[path]=actual
    for item in pd.read_csv(directory/'comparison.csv').to_dict('records'):
        path=directory/(item['candidate']+'_predictions.csv');rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        assert len(rows)==1560 and rows.Date.is_monotonic_increasing and not rows.Date.duplicated().any()
        assert rows.groupby('outer_fold').size().tolist()==[390]*4
        truth=rows[['Date']].merge(book,on='Date',validate='one_to_one')
        for key in ['label','label_end_date']:np.testing.assert_array_equal(rows[key],truth[key])
        score=rows[['p_bear','p_side','p_bull']].to_numpy();np.testing.assert_array_equal(score.argmax(axis=1),rows.prediction)
        assert np.isfinite(score).all() and (score>=0).all();np.testing.assert_allclose(score.sum(axis=1),1.,atol=1e-12)
        groups=[g for _,g in rows.groupby('outer_fold')]
        values=[f1_score(g.label,g.prediction,labels=[0,1,2],average='macro',zero_division=0) for g in groups]
        classes=np.mean([precision_recall_fscore_support(g.label,g.prediction,labels=[0,1,2],zero_division=0)[2] for g in groups],axis=0)
        computed=dict(mean_f1=float(np.mean(values)),worst_f1=float(min(values)),mean_mcc=float(np.mean([matthews_corrcoef(g.label,g.prediction) for g in groups])))
        computed.update({c+'_mean_f1':float(v) for c,v in zip(['bear','side','bull'],classes)})
        for key,value in computed.items():np.testing.assert_allclose(value,item[key],rtol=0,atol=1e-15)
        verified.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fold_f1=values,**computed))
    records=json.loads((directory/'timing_audit.json').read_text())
    for item in records:
        assert pd.Timestamp(item['latest_label_end'])<pd.Timestamp(item['prediction_start'])
        if item.get('gap',0):assert item['minimum_calendar_separation']>=20
    timings.append(dict(study=directory.parent.name,strict_mature_records=len(records)))

from regime_component_archive import load_seed_components
analog_dir=ROOT/'reports/regime_analog_density/20261019T071721_721598Z'
base,c,q,calendar,_=load_seed_components(analog_dir/'analog_shrink_predictions.csv')
forest=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z';mag=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
old_forest=np.mean([pd.read_csv(folder/f'{prefix}{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for folder,prefix in [(forest,'RandomForest_'),(mag,'')] for target in ['raw','normalized']],axis=0)
basic=.5*q+.5*old_forest
old_analog=np.mean([pd.read_csv(analog_dir/f'{view}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for view in ['compact','full'] for target in ['raw','normalized']],axis=0)
cal=ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z';anchors=json.loads((cal/'selection.json').read_text());grid=json.loads((cal/'plan.json').read_text())['grid']
positions=pd.Series(np.arange(len(calendar)),index=calendar.Date).loc[base.Date].to_numpy();cuts=np.r_[0,np.flatnonzero(np.diff(positions)!=1)+1,len(base)]
outer_parity=[]
for directory in directories:
    definitions=dict(incumbent=.75*basic+.25*old_analog)
    if directory==all_dirs[0]:
        for mode in ['mahal','separated','joint']:
            new=np.mean([pd.read_csv(directory/f'{mode}_{view}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for view in ['compact','full'] for target in ['raw','normalized']],axis=0)
            definitions[mode+'_half']=.75*basic+.125*old_analog+.125*new
            definitions[mode+'_replace']=.75*basic+.25*new
    else:
        new=np.mean([pd.read_csv(directory/f'{architecture}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for architecture in ['mean','magnitude'] for target in ['raw','normalized']],axis=0)
        prefix='extended' if directory==all_dirs[1] else 'volume'
        definitions[prefix+'_shrink']=.375*q+.1875*old_forest+.1875*new+.25*old_analog
        definitions[prefix+'_replace']=.375*q+.375*new+.25*old_analog
    for name,den in definitions.items():
        raw=np.empty_like(c)
        for item in anchors:
            assert pd.Timestamp(item['latest_tuning_label_end'])<pd.Timestamp(item['outer_boundary'])
            mask=base.outer_fold.eq(item['fold']).to_numpy();w,tc,td=grid[item['chosen']['robust']]
            cc=c[mask]**(1/tc);cc/=cc.sum(axis=1,keepdims=True)
            dd=den[mask]**(1/td);dd/=dd.sum(axis=1,keepdims=True);raw[mask]=(1-w)*cc+w*dd
        ema=np.empty_like(raw)
        for a,b in zip(cuts[:-1],cuts[1:]):ema[a:b]=pd.DataFrame(raw[a:b]).ewm(alpha=1/3,adjust=False).mean()
        score=(raw+ema)/2;expected=pd.read_csv(directory/(name+'_predictions.csv'))[['p_bear','p_side','p_bull']].to_numpy()
        np.testing.assert_allclose(score,expected,rtol=0,atol=1e-12)
        outer_parity.append(dict(study=directory.parent.name,candidate=name,max_error=float(np.abs(score-expected).max())))

import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime as exp
cfg=SimpleNamespace(reference_report=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json',control_dir=ROOT/'reports/regime_experiments/20261017T141838_654956Z',data_dir=ROOT/'data/research/brokers_2010_20261001_reviewed')
old,jobs,_,_=density.prepare_return_distribution(cfg);index,_=exp.base.load_market_data(cfg.data_dir/'VNINDEX.csv')
old=labels.relabel_cohort(old,labels.build_label_book(index),'vol_1sigma')
block=jobs['expanding']['folds'][0]['blocks'][0];train=old.iloc[block['train']];valid=old.iloc[block['validation']]
actual_positions=pd.DatetimeIndex(index.Date).get_indexer(train.Date)
metric_plan=json.loads((all_dirs[0]/'plan.json').read_text());neighborhood_parity=[]
for mode,(metric,gap) in metric_plan['modes'].items():
    for view,names in metric_plan['feature_views'].items():
        x=train[names].to_numpy();v=valid[names].to_numpy();center=np.median(x,axis=0)
        quantiles=np.quantile(x,[.25,.75],axis=0);scale=quantiles[1]-quantiles[0];scale[scale<=1e-12]=1.
        x=(x-center)/scale;v=(v-center)/scale;delta=v[:,None,:]-x[None,:,:]
        if metric=='mahalanobis':
            covariance=LedoitWolf().fit(x).covariance_;ridge=1e-8*max(float(np.trace(covariance)/len(names)),1.)
            precision=np.linalg.inv(covariance+ridge*np.eye(len(names)))
            distance=np.sqrt(np.maximum(np.einsum('bnd,de,bne->bn',delta,precision,delta),0.))
        else:distance=np.sqrt((delta**2).sum(axis=2))
        selections=[];weights=[]
        for row in range(len(v)):
            ids=[]
            for candidate in np.argsort(distance[row],kind='stable'):
                if not gap or all(abs(int(actual_positions[candidate])-int(actual_positions[j]))>=gap for j in ids):ids.append(int(candidate))
                if len(ids)==100:break
            ids=np.asarray(ids);ds=distance[row,ids];h=np.median(ds)
            w=np.exp(-.5*(ds/h)**2) if h>0 else (ds==0).astype(float);w/=w.sum()
            selections.append(ids);weights.append(w)
        for normalized in [False,True]:
            target=train.future_log_return.to_numpy();s=valid.horizon_sigma.to_numpy()
            if normalized:target=target/train.horizon_sigma.to_numpy();s=np.ones(len(valid))
            mass=[]
            for row,(ids,w) in enumerate(zip(selections,weights)):
                atoms=target[ids];mass.append([w[atoms<-s[row]].sum(),w[(atoms>=-s[row])&(atoms<=s[row])].sum(),w[atoms>s[row]].sum()])
            score=np.asarray(mass)/(np.bincount(train.label,minlength=3)/len(train));score/=score.sum(axis=1,keepdims=True)
            path=all_dirs[0]/f'{mode}_{view}_{"normalized" if normalized else "raw"}_scores.csv';expected=pd.read_csv(path)[['p_bear','p_side','p_bull']].to_numpy()[:len(valid)]
            np.testing.assert_allclose(score,expected,rtol=0,atol=1e-12)
            neighborhood_parity.append(dict(mode=mode,view=view,normalized=normalized,rows=len(valid),max_error=float(np.abs(score-expected).max())))

history_audit=None
if all_dirs[1] in directories:
    etf,_=exp.base.load_market_data(cfg.data_dir/'E1VFVN30.csv')
    features,_=exp.base.build_feature_matrix(index,etf,'close-etf');features=pd.concat([features,exp.long_features(index)],axis=1)
    # Independent raw-calendar target construction, without the new history helper.
    features['label_end_date']=index.Date.shift(-20);features['horizon_sigma']=sigma.to_numpy()
    features['label']=book.label.to_numpy()
    eligible=np.isfinite(features[exp.base.CLOSE_V1_NAMES+exp.TREND_NAMES]).all(axis=1)&features.label_end_date.notna()&np.isfinite(sigma)&sigma.gt(0)
    rebuilt=features.loc[eligible].reset_index(drop=True)
    records=json.loads((all_dirs[1]/'timing_audit.json').read_text())
    for item in records:
        boundary=pd.Timestamp(item['prediction_start']);allowed=rebuilt.loc[(rebuilt.Date<boundary)&(rebuilt.label_end_date<boundary)]
        assert len(allowed)==item['n_train']
        assert int(allowed[exp.base.ETF_FEATURE_NAMES].isna().any(axis=1).sum())==item['rows_missing_ETF']
        assert str(allowed.Date.min().date())==item['train_start']
    history_audit=dict(extended_eligible_rows=len(rebuilt),start=str(rebuilt.Date.min().date()),fit_records_recounted=len(records),ETF_missing_preserved=True)

volume_audit=None
if all_dirs[2] in directories:
    import prepare_regime_data as data_sources
    panels={}
    for provider in ['vci','kbs','vnd']:
        path=cfg.data_dir/'sources'/f'{provider}_VNINDEX.json'
        source=data_sources.normalize_response(json.loads(path.read_text()),provider,'VNINDEX',index.Date.min(),index.Date.max())
        aligned=index[['Date','Price']].merge(source,on='Date',sort=False,how='left',validate='one_to_one')
        valid=(aligned.High+.011>=aligned[['Open','Close','Low']].max(axis=1))&(aligned.Low-.011<=aligned[['Open','Close','High']].min(axis=1))&(aligned.Close-aligned.Price).abs().le(.011)&aligned.Volume.gt(0)
        panels[provider]=aligned.Volume.where(valid)
    rebuilt_values=[];rebuilt_sources=[]
    for i in range(len(index)):
        present={p:float(v.iloc[i]) for p,v in panels.items() if pd.notna(v.iloc[i])}
        groups=[]
        for count in [3,2]:
            if len(present)<count:continue
            for combination in itertools.combinations(present,count):
                values=[present[p] for p in combination]
                if max(values)-min(values)<=max(1.,1e-4*max(values)):groups.append(combination)
            if groups:break
        if len(groups)==1:
            rebuilt_values.append(float(np.median([present[p] for p in groups[0]])));rebuilt_sources.append('+'.join(sorted(groups[0])))
        else:rebuilt_values.append(np.nan);rebuilt_sources.append('')
    field=pd.Series(rebuilt_values)
    exported=pd.read_csv(all_dirs[2]/'volume_features.csv',parse_dates=['Date'])
    np.testing.assert_array_equal(exported.Date,index.Date)
    np.testing.assert_allclose(field,exported.RelativeConsensusVolume,rtol=1e-12,atol=.001,equal_nan=True)
    np.testing.assert_array_equal(rebuilt_sources,exported.VolumeSources.fillna('').to_numpy())
    ratio=np.log(field/field.rolling(60,min_periods=30).median().where(lambda x:x>0))
    change=np.log(field/field.shift(5))
    np.testing.assert_allclose(ratio,exported.RelativeVolumeLogRatio60,rtol=0,atol=1e-12,equal_nan=True)
    np.testing.assert_allclose(change,exported.RelativeVolumeLogChange5,rtol=0,atol=1e-12,equal_nan=True)
    frozen=exported.Date.isin(base.Date)
    volume_audit=dict(rows=len(exported),relative_field_frozen=float(field[frozen].notna().mean()),
        absolute_field_frozen=float(exported.loc[frozen,'OldAbsoluteConsensusVolume'].notna().mean()),
        two_or_more_source_fields=int(sum(bool(x) for x in rebuilt_sources)),relative_budget=1e-4,feature_reconstruction=True,
        caveat='Bounded disagreement is not verified identity of source-volume definitions or exchange certification.')

result=dict(role='Independent implementation audit of historical DEVELOPMENT; not independent data test',all_studies_complete=len(directories)==3,
    forecast_files=verified,source_hashes_verified=len(sources),timing_audits=timings,independent_outer_score_parity=outer_parity,
    neighborhood_parity=neighborhood_parity,history_audit=history_audit,volume_precision_audit=volume_audit,caveat='All dates repeatedly inspected. No independent acceptance or deployment.')
(OUT/'independent_metric_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(all_complete=result['all_studies_complete'],files=len(verified),sources=len(sources),timing_audits=timings,
    outer_parity=outer_parity,neighborhood_parity=neighborhood_parity,history_audit=history_audit,volume_precision_audit=volume_audit),indent=2))
