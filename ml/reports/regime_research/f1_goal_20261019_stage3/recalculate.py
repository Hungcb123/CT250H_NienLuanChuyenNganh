"""Independent raw-price labels/metrics plus calibration-selection replay audit."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT = Path(__file__).resolve().parent
market = pd.read_csv(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv',parse_dates=['Date'])
logprice = np.log(market.Close)
sigma = logprice.diff().rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
future = logprice.shift(-20)-logprice
book = pd.DataFrame(dict(Date=market.Date,label_end_date=market.Date.shift(-20),
    label=np.where(future < -sigma,0,np.where(future > sigma,2,1))))
directories = [ROOT/'reports'/name for name in [
    'regime_matched_calibration/20261019T064830_252658Z',
    'regime_anchored_fusion/20261019T065633_437477Z',
    'regime_block_density/20261019T065257_068617Z',
    'regime_empirical_forest/20261019T070202_443313Z']]
verified=[];sources={};timings=[]
for directory in directories:
    if not (directory/'comparison.csv').exists():
        continue
    plan=json.loads((directory/'plan.json').read_text())
    for filename,digest in plan['source_hashes'].items():
        actual=hashlib.sha256(Path(filename).read_bytes()).hexdigest()
        assert actual==digest, filename
        sources[filename]=actual
    table=pd.read_csv(directory/'comparison.csv')
    for row in table.to_dict('records'):
        path=directory/(row['candidate']+'_predictions.csv')
        frame=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        assert len(frame)==1560 and frame.Date.is_monotonic_increasing and not frame.Date.duplicated().any()
        assert frame.groupby('outer_fold').size().tolist()==[390]*4
        truth=frame[['Date']].merge(book,on='Date',validate='one_to_one')
        np.testing.assert_array_equal(frame.label,truth.label)
        np.testing.assert_array_equal(frame.label_end_date,truth.label_end_date)
        score=frame[['p_bear','p_side','p_bull']].to_numpy()
        assert np.isfinite(score).all() and (score>=0).all()
        np.testing.assert_allclose(score.sum(axis=1),1.,atol=1e-12)
        np.testing.assert_array_equal(score.argmax(axis=1),frame.prediction)
        folds=[];classes=[];mcc=[]
        for _,group in frame.groupby('outer_fold'):
            folds.append(f1_score(group.label,group.prediction,labels=[0,1,2],average='macro',zero_division=0))
            classes.append(precision_recall_fscore_support(group.label,group.prediction,labels=[0,1,2],zero_division=0)[2])
            mcc.append(matthews_corrcoef(group.label,group.prediction))
        computed=dict(mean_f1=float(np.mean(folds)),worst_f1=float(min(folds)),mean_mcc=float(np.mean(mcc)))
        computed.update({name+'_mean_f1':float(value) for name,value in zip(['bear','side','bull'],np.mean(classes,axis=0))})
        for name,value in computed.items():
            np.testing.assert_allclose(value,row[name],rtol=0,atol=1e-15)
        verified.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fold_f1=folds,**computed))
    path=directory/'timing_audit.json'
    if path.exists():
        for item in json.loads(path.read_text()):
            if 'boundary' in item:
                assert pd.Timestamp(item['classifier_label_end'])<pd.Timestamp(item['boundary'])
                assert pd.Timestamp(item['density_label_end'])<pd.Timestamp(item['boundary'])
            elif 'prediction_start' in item:
                assert pd.Timestamp(item['latest_label_end'])<pd.Timestamp(item['prediction_start'])
        timings.append(dict(path=str(path.relative_to(ROOT)),rows=len(json.loads(path.read_text())),strict_maturity=True))
    path=directory/'resampling_audit.json'
    if path.exists():
        for item in json.loads(path.read_text()):
            assert pd.Timestamp(item['latest_label_end'])<pd.Timestamp(item['prediction_start'])
            assert item['weight_sum']==item['n_train']
        timings.append(dict(path=str(path.relative_to(ROOT)),rows=len(json.loads(path.read_text())),strict_maturity=True,mass_preserved=True))

# Reconstruct complete inner-score smoothing and coefficient choices without
# importing the experiment fusion or smoothing functions.
cal=directories[0];selection=json.loads((cal/'selection.json').read_text())
grid=[tuple(item['parameters']) for item in selection[0]['candidates']]
positions=pd.Series(np.arange(len(market)),index=market.Date)
selection_verified=[]
for outer in selection:
    allclasses=[]
    for inner in [1,2,3]:
        frame=pd.read_csv(cal/f'outer{outer["fold"]}_inner{inner}_forecasts.csv',parse_dates=['Date','label_end_date'])
        assert frame.label_end_date.max()<pd.Timestamp(outer['outer_boundary'])
        truth=frame[['Date']].merge(book,on='Date',validate='one_to_one')
        np.testing.assert_array_equal(truth.label,frame.label)
        np.testing.assert_array_equal(truth.label_end_date,frame.label_end_date)
        c=frame[['c_bear','c_side','c_bull']].to_numpy();d=frame[['d_bear','d_side','d_bull']].to_numpy()
        ids=positions.loc[frame.Date].to_numpy();metrics=[]
        for w,tc,td in grid:
            cc=c**(1/tc);cc/=cc.sum(axis=1,keepdims=True)
            dd=d**(1/td);dd/=dd.sum(axis=1,keepdims=True)
            raw=(1-w)*cc+w*dd
            cuts=np.r_[0,np.flatnonzero(np.diff(ids)!=1)+1,len(frame)]
            ema=np.empty_like(raw)
            for a,b in zip(cuts[:-1],cuts[1:]):
                ema[a:b]=pd.DataFrame(raw[a:b]).ewm(alpha=1/3,adjust=False).mean().to_numpy()
            pred=(.5*(raw+ema)).argmax(axis=1)
            metrics.append(precision_recall_fscore_support(frame.label,pred,labels=[0,1,2],zero_division=0)[2])
        allclasses.append(metrics)
    classes=np.asarray(allclasses);macro=classes.mean(axis=2)
    mean=macro.mean(axis=0)
    robust=.5*mean+.25*macro.min(axis=0)+.25*classes.mean(axis=0)[:,[0,2]].min(axis=1)
    penalty=np.array([.005*((2*(w-.5))**2+np.log(tc)**2+np.log(td)**2) for w,tc,td in grid])
    for rule,values in [('macro',mean),('robust',robust)]:
        np.testing.assert_allclose(values,[x['mean_f1' if rule=='macro' else 'robust'] for x in outer['candidates']],atol=1e-15)
        adjusted=values-penalty;best=int(adjusted.argmax())
        chosen=best if adjusted[best]>=adjusted[0]+.005 else 0
        assert chosen==outer['chosen'][rule]
    selection_verified.append(dict(outer_fold=outer['fold'],chosen=outer['chosen'],inner_rows=[len(pd.read_csv(cal/f'outer{outer["fold"]}_inner{i}_forecasts.csv')) for i in [1,2,3]]))

result=dict(role='Independent implementation recalculation on historical DEVELOPMENT; not an independent data test',
    forecast_files=verified,source_hashes_verified=len(sources),timing_audits=timings,selection_replay=selection_verified,
    raw_price_sha256=hashlib.sha256((ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv').read_bytes()).hexdigest(),
    caveat='All outer history repeatedly inspected. Robust calibration was a predeclared diagnostic; reporting it after inspection adds selection exposure. Its higher mean F1 does not erase its worse weakest fold.')
(OUT/'independent_metric_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(forecast_files_verified=len(verified),source_hashes_verified=len(sources),selection_folds_verified=len(selection_verified),timing_audits=timings),indent=2))
