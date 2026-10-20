"""Causal smoothing of forecast SCORES; never smooth or shift true labels."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def causal_forecast_ema(dates,scores,calendar,span):
    dates=pd.DatetimeIndex(dates);scores=np.asarray(scores,dtype=float)
    positions=pd.DatetimeIndex(calendar).get_indexer(dates)
    if span<=0 or scores.shape!=(len(dates),3) or (positions<0).any() or (np.diff(positions)<=0).any():raise ValueError('Invalid smoothing input')
    if not np.isfinite(scores).all() or (scores<0).any():raise ValueError('Invalid forecast scores')
    alpha=2/(span+1);result=np.empty_like(scores)
    for i in range(len(scores)):
        result[i]=scores[i] if i==0 or positions[i]-positions[i-1]!=1 else alpha*scores[i]+(1-alpha)*result[i-1]
    return result


def run_forecast_smoothing(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_density_seeds/20261019T061537_193740Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source=args.source_dir/'info_seed5_predictions.csv'
    rows=pd.read_csv(source,parse_dates=['Date','label_end_date'])
    index=pd.read_csv(args.data_dir/'VNINDEX.csv',parse_dates=['Date'])
    # Metric helper needs a causal baseline label, not future outcome frequencies.
    rows['majority']=rows.baseline_prediction
    columns=['p_bear','p_side','p_bull'];scores=rows[columns].to_numpy()
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',source,args.source_dir/'plan.json',args.data_dir/'VNINDEX.csv']
    parent=json.loads((args.source_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+name)
    output=args.output_dir or ROOT/'reports/regime_forecast_smoothing'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='causal_forecast_smoothing_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        primary='ema5: causal exponential smoothing span5 of fixed5-seed information-blend score; primary set before scoring',
        secondary='ema5_shrink: .5 current score + .5 ema5',diagnostics=[3,10],
        timing='Only current/past forecast scores, NO outcomes. Reset at first forecast or any missing raw-market session. True labels/dates/endpoints unchanged.',
        hypothesis='T+20 endpoint states and noisy quantile scores may benefit from score persistence; smoothing can also lag turning points.',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, MCC gain, >=3 fold wins and both paired20/60 intervals>0 for provisional evidence.',
        caveat='No label smoothing in evaluation or future averaging. Repeatedly inspected historical development only; no independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    matrices={'incumbent':scores}
    for span in [3,5,10]:matrices['ema'+str(span)]=causal_forecast_ema(rows.Date,scores,index.Date,span)
    matrices['ema5_shrink']=.5*scores+.5*matrices['ema5']
    prefix=[]
    for end in [390,780,1170,1460,1560]:
        shorter=causal_forecast_ema(rows.Date.iloc[:end],scores[:end],index.Date[index.Date<=rows.Date.iloc[end-1]],5)
        np.testing.assert_allclose(shorter,matrices['ema5'][:end],atol=1e-12,rtol=1e-12)
        prefix.append(dict(rows=end,forecast_prefix_invariance=True))
    (output/'causality_audit.json').write_text(json.dumps(prefix,indent=2)+'\n')
    finish_research_study(rows,matrices,output,['ema5','ema5_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_forecast_smoothing()
