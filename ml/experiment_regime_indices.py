"""Cross-index size-group risk features: fixed shallow models, frozen dates.

VN30/VNMidcap/VNSmallcap HISTORICAL index closes, not today's constituent list.
Disputed or unavailable values remain missing; no bfill or reweighted stock basket.
"""
import copy
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_fresh as fresh
study=fresh.study
INDEX_DIR=study.risk.labels.ROOT/'data/research/market_indices_20261001_v3'
SYMBOLS=['VN30','VNMID','VNSML']
NAMES=[f'{symbol}_{feature}' for symbol in SYMBOLS for feature in ['SpreadROC20','HV20Ratio','Corr60']]+['IndexROC20Dispersion','IndexTrendParticipation']
CONFIGS=[('3y_indices_fresh','3y','lightgbm',True),('expanding_indices_fresh','expanding','lightgbm',True),
         ('3y_logistic_close_fresh','3y','logistic',False),('3y_logistic_indices_fresh','3y','logistic_missing',True)]


def load_indices(directory=INDEX_DIR):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    frames={}
    for symbol in SYMBOLS:
        path=directory/(symbol+'.csv')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=manifest['canonical'][symbol]['sha256']:raise ValueError(symbol+' input hash mismatch')
        frame=pd.read_csv(path,parse_dates=['Date'])
        if frame.Date.duplicated().any() or not frame.Date.is_monotonic_increasing or not np.isfinite(frame.Close).all() or (frame.Close<=0).any():raise ValueError('Invalid index data')
        # Both sources only overlap from 2017; no data inferred from base dates or pre-launch backcasts.
        if frame.Date.min()<pd.Timestamp('2017-08-24'):raise ValueError('Unexpected pre-consensus history')
        frames[symbol]=frame
    return frames,manifest


def index_features(index,groups):
    out=pd.DataFrame({'Date':index.Date})
    vnreturn=np.log(index.Price).diff()
    vnvol=vnreturn.rolling(20).std(ddof=1).replace(0,np.nan)
    vnroc=index.Price/index.Price.shift(20)-1
    rocs,participation=[],[]
    for symbol in SYMBOLS:
        joined=index[['Date']].merge(groups[symbol],on='Date',how='left',validate='one_to_one',sort=False)
        price=joined.Close
        returns=np.log(price).diff()
        roc=price/price.shift(20)-1
        # Explicitly require every close in the 21-observation return window.
        complete=price.rolling(21,min_periods=21).count()==21
        roc=roc.where(complete)
        out[symbol+'_SpreadROC20']=roc-vnroc
        out[symbol+'_HV20Ratio']=returns.rolling(20,min_periods=20).std(ddof=1)/vnvol
        out[symbol+'_Corr60']=returns.rolling(60,min_periods=60).corr(vnreturn)
        sma=price.rolling(20,min_periods=20).mean()
        participation.append((price>sma).astype(float).where(sma.notna()&price.notna()))
        rocs.append(roc)
    out['IndexROC20Dispersion']=pd.concat(rocs,axis=1).std(axis=1,ddof=0,skipna=False)
    out['IndexTrendParticipation']=pd.concat(participation,axis=1).mean(axis=1,skipna=False)
    return out.replace([np.inf,-np.inf],np.nan)


def prepare(args):
    old,index,plan=fresh.prepare(args)
    frame,template,names=old[0][1:]
    groups,metadata=load_indices()
    features=index_features(index,groups)
    candidates=[]
    for name,window,family,extended in CONFIGS:
        job=copy.deepcopy(template)
        for outer in job['folds']:
            frozen=np.concatenate([b['validation'] for b in outer['blocks']])
            outer['blocks']=fresh.make_blocks(frame,frozen,pd.DatetimeIndex(index.Date),window,40,20)
        joined=frame.merge(features,on='Date',how='left',validate='one_to_one',sort=False) if extended else frame.copy()
        candidates.append((name,window,family,joined,job,names+(NAMES if extended else [])))
    plan.update(mode='cross_index_freshness_development',
                candidates=[dict(name=n,window=w,family=f,index_features=e) for n,w,f,e in CONFIGS],
                index_inputs=metadata,feature_names=NAMES,
                timing='Two-broker close agreement on exact VNINDEX calendar; no filling, no current constituent history.',
                missing_policy='Core-only median imputer with indicators for logistic; native LightGBM missing.',
                caveat='Broker historical index revisions not independently point-in-time certified. Group-index participation is NOT stock-market breadth.')
    return candidates,index,plan


def run_candidate(name,window,family,frame,job,names):
    records,audits=[],[]
    for outer in job['folds']:
        for block_no,block in enumerate(outer['blocks'],1):
            core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
            if core.label_end_date.max()>=cal.Date.min() or cal.label_end_date.max()>=valid.Date.min():raise ValueError('Noncausal split')
            model=study.make_model(family)
            model.fit(core[names].to_numpy(),core.label.to_numpy())
            cal_score=study.score_model(model,cal[names].to_numpy(),family,'vol_1sigma')
            score=study.score_model(model,valid[names].to_numpy(),family,'vol_1sigma')
            if not np.isfinite(score).all():raise ValueError('Nonfinite risk score')
            threshold=study.risk.alarm_threshold(cal_score)
            r=valid[['Date','label_end_date','future_return','label']].copy()
            r['risk_score'],r['threshold'],r['alarm']=score,threshold,score>threshold
            r['common_bear']=r.future_return<-.05
            r['policy'],r['outer_fold'],r['refit_block']=name,outer['fold'],block_no
            records.append(r)
            audits.append(dict(policy=name,outer_fold=outer['fold'],refit_block=block_no,core_end=str(core.Date.max()),
                               core_label_end=str(core.label_end_date.max()),calibration_start=str(cal.Date.min()),calibration_end=str(cal.Date.max()),
                               calibration_label_end=str(cal.label_end_date.max()),prediction_start=str(valid.Date.min()),
                               **study.diag.score_stats(cal_score,'calibration_score')))
    return pd.concat(records,ignore_index=True),audits


def main(argv=None):
    args=study.risk.labels.parse_args(argv)
    candidates,index,plan=prepare(args)
    output=args.output_dir or study.risk.labels.ROOT/'reports/regime_indices'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'indices_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if plan['errors']:raise ValueError('Preflight errors')
    if args.audit_only:
        print('Audit passed, no fit. '+str(output.resolve()));return plan
    records,audits=[],[]
    for candidate in candidates:
        print('Running '+candidate[0],flush=True)
        predictions,refits=run_candidate(*candidate)
        predictions.to_csv(output/(candidate[0]+'_predictions.csv'),index=False)
        records.append(predictions);audits.extend(refits)
        pd.DataFrame(study.risk.summary_rows(pd.concat(records,ignore_index=True))).to_csv(output/'causal_metrics.csv',index=False)
    records=pd.concat(records,ignore_index=True)
    pd.DataFrame(study.risk.equal_count_diagnostic(records)).to_csv(output/'retrospective_equal_count.csv',index=False)
    study.diag.write_diagnostics(records,audits,index,output/'diagnostics')
    print('Done. Historical development only. '+str(output.resolve()));return output


if __name__=='__main__':main()
