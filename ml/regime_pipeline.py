"""Versioned close-only features, purged evaluation and lagged OOS backtesting.
No synthetic fallback. The same 120-close window is implemented in CloseFeatures.java.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import f1_score, matthews_corrcoef
from sklearn.model_selection import TimeSeriesSplit
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

VERSION = 'close-v1'
FEATURES = ['RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist', 'BB_Width', 'BB_PctB',
            'SMA_20_50_Ratio', 'Dist_SMA20', 'Dist_SMA50', 'Abs_Change_14_Pct', 'ROC_20', 'HV_20']
HORIZON = 20


def close_features(values):
    p = np.asarray(values[-120:], dtype=float)
    if len(p) < 60 or not np.isfinite(p).all() or (p <= 0).any():
        raise ValueError('Need at least 60 finite positive closes')
    def ema(a, period):
        out = [a[0]]
        for x in a[1:]: out.append(out[-1] + (x-out[-1])*2/(period+1))
        return np.array(out)
    change = np.diff(p)[-14:]
    gain, loss = np.maximum(change, 0).mean(), np.maximum(-change, 0).mean()
    rsi = 50 if gain == loss == 0 else (100 if loss == 0 else 100-100/(1+gain/loss))
    macd = (ema(p,12)-ema(p,26))/p*100
    signal = ema(macd,9)[-1]
    s20, s50, std = p[-20:].mean(), p[-50:].mean(), p[-20:].std(ddof=0)
    return np.array([rsi,macd[-1],signal,macd[-1]-signal,4*std/s20,
        .5 if std == 0 else (p[-1]-(s20-2*std))/(4*std),s20/s50,
        p[-1]/s20-1,p[-1]/s50-1,np.abs(change).mean()/p[-1]*100,
        (p[-1]/p[-21]-1)*100,np.diff(np.log(p))[-20:].std(ddof=1)*np.sqrt(252)*100],dtype=np.float32)


def feature_frame(df):
    result = df.copy()
    vals = result.Close.to_numpy(dtype=float)
    rows = [close_features(vals[max(0,i-119):i+1]) if i>=59 else np.full(12,np.nan) for i in range(len(vals))]
    result[FEATURES] = np.array(rows)
    return result.dropna(subset=FEATURES), FEATURES.copy()


def strategy_backtest(dates, returns, signals, confidence, fee=.0015):
    """Decision at previous close; fees on turnover. Same stock/cash universe for baselines."""
    dates=list(dates)
    curves, metrics = {}, {}
    for name in ['BUY_HOLD','SAA','TAA']:
        nav, peak, dd, previous, costs, turnover = 1.,1.,0.,0.,0.,0.
        curve=[]; daily=[]
        for i,r in enumerate(returns):
            w = 1. if name=='BUY_HOLD' else .35
            if name=='TAA' and i>0 and confidence[i-1]>=.55:
                w = float(np.clip(.35+signals[i-1]*confidence[i-1]*.15,0,1))
            traded=abs(w-previous)
            cost=traded*fee
            growth=(1-cost)*(1+w*r) # cash return explicitly zero
            nav*=growth; costs+=cost; turnover+=traded
            # Drifted closing weight, including transaction costs proportionally.
            previous=w*(1+r)/(1+w*r)
            peak=max(peak,nav); dd=max(dd,1-nav/peak)
            curve.append({'date':str(pd.Timestamp(dates[i]).date()),'nav':nav}); daily.append(growth-1)
        vol=float(np.std(daily,ddof=1)*np.sqrt(252)) if len(daily)>1 else 0.
        metrics[name]={'totalReturn':nav-1,'maxDrawdown':dd,'annualVolatility':vol,
            'sharpeRfZero':float(np.mean(daily)*252/vol) if vol else 0.,'turnover':turnover,'costRateSum':costs}
        curves[name]=curve
    return {'assumptions':{'stock':'VNINDEX proxy, not an executable security','cashAnnualReturn':0,'feePerTurnover':fee,
        'execution':'one-session execution delay: close(t) signal, trade at close(t+1), earn next interval; daily rebalance; no slippage','scope':'stock/cash only; gold excluded'},'metrics':metrics,'curves':curves}


def train(ticker='VNINDEX', model_name='stock_regime', output_dir='backend/src/main/resources/models'):
    path=Path('ml/data/raw')/f'{ticker}.csv'
    df=pd.read_csv(path).sort_values('Date').drop_duplicates('Date')
    df['Date']=pd.to_datetime(df.Date)
    if df.Date.max()>pd.Timestamp.today().normalize(): raise ValueError('Future market data')
    if not np.isfinite(df.Close).all() or (df.Close<=0).any(): raise ValueError('Invalid closes')
    frame,_=feature_frame(df)
    future=frame.Close.shift(-HORIZON)/frame.Close-1
    frame=frame.assign(label=np.where(future<-.03,0,np.where(future>.03,2,1)))
    frame=frame.loc[future.notna()].reset_index(drop=True)
    X=frame[FEATURES].to_numpy(dtype=np.float32); y=frame.label.to_numpy(dtype=np.int64)
    def new_model(): return LGBMClassifier(n_estimators=100,max_depth=4,num_leaves=15,learning_rate=.04,
        class_weight='balanced',random_state=42,n_jobs=2,verbosity=-1)
    folds=[]; oos=[]
    for tr,te in TimeSeriesSplit(n_splits=4,gap=HORIZON).split(X):
        model=new_model(); model.fit(X[tr],y[tr]); pred=model.predict(X[te]); prob=model.predict_proba(X[te])
        folds.append({'trainEnd':str(frame.Date.iloc[tr[-1]].date()),'testStart':str(frame.Date.iloc[te[0]].date()),
            'purgeSessions':HORIZON,'f1Macro':f1_score(y[te],pred,average='macro',zero_division=0),
            'mcc':matthews_corrcoef(y[te],pred),'majorityBaselineF1':f1_score(y[te],np.full(len(te),np.bincount(y[tr],minlength=3).argmax()),average='macro',zero_division=0)})
        oos.extend((int(i),int(p)-1,float(c)) for i,p,c in zip(te,pred,prob.max(axis=1)))
    # Published artifact uses only the final training fold, preserving the final OOS period.
    report={'featureVersion':VERSION,'features':FEATURES,'ticker':ticker,'horizon':HORIZON,'folds':folds,
        'artifactTrainEnd':folds[-1]['trainEnd'],'dataEnd':str(df.Date.max().date()),'syntheticData':False}
    if ticker=='VNINDEX':
        oos=[x for x in oos if x[0]+1<len(frame)]
        ids=np.array([x[0] for x in oos]); prices=frame.Close.to_numpy()
        next_returns=prices[ids+1]/prices[ids]-1 # dates align with ending close
        report['backtest']=strategy_backtest(frame.Date.iloc[ids+1],next_returns,
            np.array([x[1] for x in oos]),np.array([x[2] for x in oos]))
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    exported=onnxmltools.convert_lightgbm(model,initial_types=[('float_input',FloatTensorType([None,12]))],target_opset=15)
    for key,value in {'feature_version':VERSION,'features':','.join(FEATURES),'ticker':ticker,
        'train_end':folds[-1]['trainEnd'],'horizon':'20'}.items():
        prop=exported.metadata_props.add(); prop.key=key; prop.value=value
    (out/f'{model_name}.onnx').write_bytes(exported.SerializeToString())
    Path('ml/reports').mkdir(exist_ok=True)
    Path(f'ml/reports/{model_name}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/f'{model_name}_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Java checks both the feature schema and training asset identity.
    fixture={'closes':df.Close.iloc[-120:].tolist(),'features':close_features(df.Close.to_numpy()).tolist()}
    import onnxruntime as ort
    session=ort.InferenceSession(exported.SerializeToString(),providers=['CPUExecutionProvider'])
    label,prob=session.run(None,{'float_input':np.array([fixture['features']],dtype=np.float32)})
    fixture['label']=int(label[0]);fixture['confidence']=float(prob[0][int(label[0])])
    (out/f'{model_name}_fixture.json').write_text(json.dumps(fixture),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='backtest'},indent=2))
    return report
