"""Independent target/metric, final fusion and analog-neighborhood audit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef, precision_recall_fscore_support

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--allow-running',action='store_true');args=parser.parse_args()
directories=[ROOT/'reports/regime_information_forest/20261019T071622_321945Z',ROOT/'reports/regime_analog_density/20261019T071721_721598Z',ROOT/'reports/regime_shock_forest/20261019T072038_455776Z']
directories=[p for p in directories if (p/'comparison.csv').exists() or not args.allow_running]
market=pd.read_csv(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv',parse_dates=['Date'])
lp=np.log(market.Close);sigma=lp.diff().rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
forward=lp.shift(-20)-lp
book=pd.DataFrame(dict(Date=market.Date,label_end_date=market.Date.shift(-20),label=np.where(forward<-sigma,0,np.where(forward>sigma,2,1))))
metrics=[];sources={};timings=[]
for directory in directories:
    assert (directory/'comparison.csv').exists(),'Study still running: '+str(directory)
    plan=json.loads((directory/'plan.json').read_text())
    assert plan['labels']['20']['policy']=='vol_1sigma'
    for filename,digest in plan['source_hashes'].items():
        actual=hashlib.sha256(Path(filename).read_bytes()).hexdigest();assert actual==digest,filename;sources[filename]=actual
    for item in pd.read_csv(directory/'comparison.csv').to_dict('records'):
        path=directory/(item['candidate']+'_predictions.csv');rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        assert len(rows)==1560 and rows.Date.is_monotonic_increasing and not rows.Date.duplicated().any()
        assert rows.groupby('outer_fold').size().tolist()==[390]*4
        truth=rows[['Date']].merge(book,on='Date',validate='one_to_one')
        for key in ['label','label_end_date']:np.testing.assert_array_equal(rows[key],truth[key])
        scores=rows[['p_bear','p_side','p_bull']].to_numpy();np.testing.assert_array_equal(scores.argmax(axis=1),rows.prediction)
        assert np.isfinite(scores).all() and (scores>=0).all();np.testing.assert_allclose(scores.sum(axis=1),1.,atol=1e-12)
        groups=[g for _,g in rows.groupby('outer_fold')]
        f1=[f1_score(g.label,g.prediction,labels=[0,1,2],average='macro',zero_division=0) for g in groups]
        classes=np.mean([precision_recall_fscore_support(g.label,g.prediction,labels=[0,1,2],zero_division=0)[2] for g in groups],axis=0)
        computed=dict(mean_f1=float(np.mean(f1)),worst_f1=float(min(f1)),mean_mcc=float(np.mean([matthews_corrcoef(g.label,g.prediction) for g in groups])))
        computed.update({c+'_mean_f1':float(v) for c,v in zip(['bear','side','bull'],classes)})
        for key,value in computed.items():np.testing.assert_allclose(value,item[key],rtol=0,atol=1e-15)
        metrics.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fold_f1=f1,**computed))
    records=json.loads((directory/'timing_audit.json').read_text())
    for item in records:assert pd.Timestamp(item['latest_label_end'])<pd.Timestamp(item['prediction_start'])
    timings.append(dict(study=directory.parent.name,strict_mature_records=len(records)))
    if directory.parent.name=='regime_information_forest':
        vix=pd.read_csv(directory/'vix_timing.csv',parse_dates=['Date','VIX_ObservationDate','VIX_AvailableDate'])
        known=vix.VIX_AvailableDate.notna()
        assert (vix.loc[known,'VIX_ObservationDate']+pd.Timedelta(days=2)<=vix.loc[known,'Date']).all()
        assert (vix.loc[known,'Date']-vix.loc[known,'VIX_AvailableDate']<=pd.Timedelta(days=7)).all()
        assert json.loads((directory/'control_parity.json').read_text())['max_error']<=1e-12

from regime_component_archive import load_seed_components
baseline=ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z'
base,c,q,calendar,_=load_seed_components(baseline/'magnitude_shrink_predictions.csv')
forest=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
rf=np.mean([pd.read_csv(forest/f'RandomForest_{t}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for t in ['raw','normalized']],axis=0)
mag=np.mean([pd.read_csv(baseline/f'{t}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for t in ['raw','normalized']],axis=0)
old=.5*q+.25*rf+.25*mag
cal=ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z';anchors=json.loads((cal/'selection.json').read_text());grid=json.loads((cal/'plan.json').read_text())['grid']
positions=pd.Series(np.arange(len(calendar)),index=calendar.Date).loc[base.Date].to_numpy()
cuts=np.r_[0,np.flatnonzero(np.diff(positions)!=1)+1,len(base)];outer_parity=[]
for directory in directories:
    if directory.parent.name=='regime_information_forest':
        densities={}
        for treatment in ['selected','combined']:
            densities[treatment]=np.mean([pd.read_csv(directory/f'{treatment}_{architecture}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for architecture in ['mean','magnitude'] for target in ['raw','normalized']],axis=0)
        definitions=dict(incumbent=old,context_shrink=.75*old+.25*densities['selected'],context_forest_replace=.5*q+.5*densities['selected'],combined_context_diagnostic=.75*old+.25*densities['combined'])
    elif directory.parent.name=='regime_analog_density':
        analog=np.mean([pd.read_csv(directory/f'{view}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for view in ['compact','full'] for target in ['raw','normalized']],axis=0)
        definitions=dict(incumbent=old,analog_shrink=.75*old+.25*analog,analog_half=.5*old+.5*analog)
    else:
        analog_dir=ROOT/'reports/regime_analog_density/20261019T071721_721598Z'
        analog=np.mean([pd.read_csv(analog_dir/f'{view}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for view in ['compact','full'] for target in ['raw','normalized']],axis=0)
        shock=np.mean([pd.read_csv(directory/f'{architecture}_{target}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for architecture in ['mean','magnitude'] for target in ['raw','normalized']],axis=0)
        previous=.75*old+.25*analog
        definitions=dict(incumbent=previous,shock_shrink=.75*previous+.25*shock,shock_half=.5*previous+.5*shock)
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

# Rebuild first mature neighborhood block of every analog feature/target view
# using broadcast NumPy distances and weighted indicators, without its helper.
analog_dir=ROOT/'reports/regime_analog_density/20261019T071721_721598Z'
import experiment_regime_return_distribution as density
import experiment_regime_labels as labels
import experiment_regime as exp
cfg=SimpleNamespace(reference_report=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json',
    control_dir=ROOT/'reports/regime_experiments/20261017T141838_654956Z',data_dir=ROOT/'data/research/brokers_2010_20261001_reviewed')
frame,jobs,_,_=density.prepare_return_distribution(cfg)
index,_=exp.base.load_market_data(cfg.data_dir/'VNINDEX.csv');frame=labels.relabel_cohort(frame,labels.build_label_book(index),'vol_1sigma')
block=jobs['expanding']['folds'][0]['blocks'][0];train=frame.iloc[block['train']];valid=frame.iloc[block['validation']]
analog_plan=json.loads((analog_dir/'plan.json').read_text());neighborhood_parity=[]
for view,names in analog_plan['feature_views'].items():
    x=train[names].to_numpy();v=valid[names].to_numpy();center=np.median(x,axis=0)
    quantiles=np.quantile(x,[.25,.75],axis=0);scale=np.maximum(quantiles[1]-quantiles[0],0.)
    scale[scale<=1e-12]=1.;x=(x-center)/scale;v=(v-center)/scale
    distances=np.sqrt(((v[:,None,:]-x[None,:,:])**2).sum(axis=2))
    neighbors=np.argsort(distances,axis=1,kind='stable')[:,:100]
    ds=np.take_along_axis(distances,neighbors,axis=1);h=np.median(ds,axis=1)
    weights=np.exp(-.5*(ds/np.where(h>0,h,1.)[:,None])**2)
    weights[h==0]=(ds[h==0]==0).astype(float);weights/=weights.sum(axis=1,keepdims=True)
    for normalized in [False,True]:
        target=train.future_log_return.to_numpy();s=valid.horizon_sigma.to_numpy()
        if normalized:target=target/train.horizon_sigma.to_numpy();s=np.ones(len(valid))
        atoms=target[neighbors]
        mass=np.column_stack([(weights*(atoms<-s[:,None])).sum(axis=1),(weights*((atoms>=-s[:,None])&(atoms<=s[:,None]))).sum(axis=1),(weights*(atoms>s[:,None])).sum(axis=1)])
        score=mass/(np.bincount(train.label,minlength=3)/len(train));score/=score.sum(axis=1,keepdims=True)
        path=analog_dir/f'{view}_{"normalized" if normalized else "raw"}_scores.csv';expected=pd.read_csv(path)[['p_bear','p_side','p_bull']].to_numpy()[:len(valid)]
        np.testing.assert_allclose(score,expected,rtol=0,atol=1e-12)
        neighborhood_parity.append(dict(view=view,normalized=normalized,rows=len(valid),max_error=float(np.abs(score-expected).max())))

result=dict(role='Independent implementation audit of historical DEVELOPMENT, not independent data validation',
    all_studies_complete=len(directories)==3,forecast_files=metrics,source_hashes_verified=len(sources),timing_audits=timings,
    independent_outer_score_parity=outer_parity,neighborhood_parity=neighborhood_parity,
    caveat='All 1560 dates previously inspected. Small gains remain research selection-sensitive; no independent test or deployment acceptance.')
(OUT/'independent_metric_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(all_complete=result['all_studies_complete'],files=len(metrics),sources=len(sources),timing_audits=timings,
    outer_parity=outer_parity,neighborhood_parity=neighborhood_parity),indent=2))
