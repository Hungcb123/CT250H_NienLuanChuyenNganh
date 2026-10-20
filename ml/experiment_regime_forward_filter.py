"""Forward-only state filtering with mature historical transition estimates.

Decision pseudo-likelihoods are not calibrated observation probabilities.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import experiment_regime as exp
import experiment_regime_labels as labels
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def mature_transition_matrix(book,boundary):
    boundary=pd.Timestamp(boundary)
    eligible=(book.Date>=boundary-pd.DateOffset(years=3))&(book.Date<boundary)&(book.label_end_date<boundary)&book.vol_label.notna()
    ids=np.flatnonzero(eligible.to_numpy());y=book.vol_label.iloc[ids].to_numpy(dtype=int)
    if not np.isin(y,[0,1,2]).all():raise ValueError('Invalid mature transition label')
    counts=np.ones((3,3),dtype=float)
    if len(ids)>1:
        valid=np.diff(ids)==1
        counts+=np.bincount(3*y[:-1][valid]+y[1:][valid],minlength=9).reshape(3,3)
    matrix=counts/counts.sum(axis=1,keepdims=True)
    matrix=.5*matrix+.5/3
    return matrix,dict(n_history=len(ids),latest_label_end=str(book.label_end_date.iloc[ids].max()) if len(ids) else None,raw_pair_counts=(counts-1).astype(int).tolist())


def forward_regime_filter(dates,scores,book,calendar,power=2.):
    dates=pd.DatetimeIndex(dates);scores=np.asarray(scores,dtype=float)
    positions=pd.DatetimeIndex(calendar).get_indexer(dates)
    if scores.shape!=(len(dates),3) or not np.isfinite(scores).all() or (scores<0).any() or (positions<0).any() or (np.diff(positions)<=0).any():raise ValueError('Invalid forward-filter input')
    result=[];states=[];previous=np.ones(3)/3;matrix=np.ones((3,3))/3;last_bucket=None
    buckets=(positions-positions[0])//20
    for i,(date,score) in enumerate(zip(dates,scores)):
        if buckets[i]!=last_bucket:
            matrix,info=mature_transition_matrix(book,date)
            states.append(dict(Date=str(date.date()),matrix=matrix.tolist(),**info));last_bucket=buckets[i]
        if i==0 or positions[i]-positions[i-1]!=1:previous=np.ones(3)/3
        prior=previous@matrix
        posterior=prior*np.maximum(score,1e-8)**power
        posterior/=posterior.sum();result.append(posterior);previous=posterior
    return np.asarray(result),states


def run_forward_filter(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_forecast_smoothing/20261019T062316_546117Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source=args.source_dir/'ema5_shrink_predictions.csv';base=pd.read_csv(source,parse_dates=['Date','label_end_date']);base['majority']=base.baseline_prediction
    scores=base[['p_bear','p_side','p_bull']].to_numpy()
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');book=labels.build_label_book(index)
    parent=json.loads((args.source_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+name)
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',source,args.source_dir/'plan.json',args.data_dir/'VNINDEX.csv']
    output=args.output_dir or ROOT/'reports/regime_forward_filter'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='causal_forward_transition_filter_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        transition='Last3 calendar years of raw-market adjacent target labels with BOTH endpoints strictly mature before refresh; Laplace1 counts, half transition/half uniform; update20 market sessions',
        primary='filter2: forward posterior using incumbent decision scores squared as pseudo-likelihood',
        secondary='filter2_shrink: .5 incumbent scores + .5 filter2',diagnostic_powers=[1.,4.],
        timing='No backward smoothing or Viterbi decoding. Uniform state after missing forecast sessions. Current/future true label never enters filter.',
        score_semantics='Pseudo-likelihood state scores; not certified event probabilities',
        acceptance='Mean F1 +.01, no worst/directional decline, MCC gain, >=3 wins, paired20/60 lower>0 for provisional evidence.',
        caveat='Repeatedly inspected history, no independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print('Output: '+str(output.resolve()),flush=True)
    matrices={'incumbent':scores};checks=[]
    for power in [1.,2.,4.]:
        value,states=forward_regime_filter(base.Date,scores,book,index.Date,power)
        matrices['filter'+str(int(power))]=value
        (output/f'filter{int(power)}_states.json').write_text(json.dumps(states,indent=2)+'\n')
        if power==2.:
            for end in [390,780,1170,1460,1560]:
                cutoff=base.Date.iloc[end-1];changed=book.copy()
                changed.loc[changed.label_end_date>=cutoff,'vol_label']=99
                prefix,_=forward_regime_filter(base.Date.iloc[:end],scores[:end],changed,index.Date[index.Date<=cutoff],power)
                np.testing.assert_allclose(prefix,value[:end],atol=1e-12,rtol=1e-12)
                checks.append(dict(rows=end,unmatured_label_corruption_invariant=True))
    matrices['filter2_shrink']=.5*scores+.5*matrices['filter2']
    (output/'causality_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
    finish_research_study(base,matrices,output,['filter2','filter2_shrink'])
    return output


if __name__=='__main__':run_forward_filter()
