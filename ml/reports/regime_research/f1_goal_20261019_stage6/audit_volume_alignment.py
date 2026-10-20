"""Read-only check of source volume units/date alignment; never repairs values."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import prepare_regime_data as sources
data=ROOT/'data/research/brokers_2010_20261001_reviewed'
index=pd.read_csv(data/'VNINDEX.csv',parse_dates=['Date']).set_index('Date')
manifest=json.loads((data/'manifest.json').read_text());frames={};hashes={}
for provider in ['vci','kbs','vnd']:
    path=data/'sources'/f'{provider}_VNINDEX.json'
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==manifest['sources'][provider+'_VNINDEX']['response_sha256']
    frame=sources.normalize_response(json.loads(path.read_text()),provider,'VNINDEX',index.index.min(),index.index.max()).set_index('Date').reindex(index.index)
    bounds=(frame.High+.011>=frame[['Open','Close','Low']].max(axis=1))&(frame.Low-.011<=frame[['Open','Close','High']].min(axis=1))
    eligible=bounds&(frame.Close-index.Close).abs().le(.011)&frame.Volume.gt(0)
    frames[provider]=frame.Volume.where(eligible);hashes[str(path.resolve())]=digest
ratios=[];lags=[]
for a,b in [('vci','kbs'),('vci','vnd'),('kbs','vnd')]:
    left,right=frames[a],frames[b];ratio=(left/right).dropna()
    ratios.append(dict(source_a=a,source_b=b,n=len(ratio),ratio_p05=float(ratio.quantile(.05)),ratio_median=float(ratio.median()),ratio_p95=float(ratio.quantile(.95)),
        fraction_within_1pct=float(ratio.between(.99,1.01).mean()),fraction_within_0_01pct=float(ratio.between(.9999,1.0001).mean()),fraction_ratio_10_or_100_or_1000=float(((np.minimum.reduce([np.abs(np.log(ratio)-np.log(factor)) for factor in [.001,.01,.1,10.,100.,1000.]])<np.log(1.01))).mean())))
    # Differences on FULL index sessions: missing values cannot compress dates.
    l=np.log(left).diff();r=np.log(right).diff()
    for lag in [-2,-1,0,1,2]:
        joined=pd.concat([l.rename('a'),r.shift(lag).rename('b')],axis=1).dropna()
        lags.append(dict(source_a=a,source_b=b,shift_b_market_sessions=lag,n=len(joined),correlation=float(joined.a.corr(joined.b))))
pd.DataFrame(ratios).to_csv(OUT/'volume_ratio_audit.csv',index=False)
pd.DataFrame(lags).to_csv(OUT/'volume_lag_audit.csv',index=False)
result=dict(role='Read-only source semantics diagnostic on previously inspected history; no data repair, features or model update',source_hashes=hashes,
    ratios=ratios,best_lags=[max([v for v in lags if v['source_a']==a and v['source_b']==b],key=lambda v:v['correlation']) for a,b in [('vci','kbs'),('vci','vnd'),('kbs','vnd')]],
    caveat='High correlation or similar units do not establish identical definitions of exchange volume. No provider is treated as exchange ground truth; no rescaling, filling or shifted-volume feature is authorized by this audit.')
(OUT/'volume_alignment_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
