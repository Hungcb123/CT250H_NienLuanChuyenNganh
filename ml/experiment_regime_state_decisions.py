"""Fixed causal hysteresis/confirmation on incumbent forecast scores."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def causal_state_decisions(dates,scores,calendar,margin=0.,confirmation=1):
    scores=np.asarray(scores,dtype=float);positions=pd.DatetimeIndex(calendar).get_indexer(dates)
    if scores.shape!=(len(positions),3) or not np.isfinite(scores).all() or (positions<0).any() or (np.diff(positions)<=0).any():raise ValueError('Invalid state input')
    if margin<0 or confirmation<1:raise ValueError('Invalid state rule')
    output=[];current=None;pending=None;count=0
    for i,row in enumerate(scores):
        best=int(row.argmax())
        if current is None or positions[i]-positions[i-1]!=1:
            current=best;pending=None;count=0
        elif best!=current and row[best]>=row[current]+margin:
            if pending==best:count+=1
            else:pending=best;count=1
            if count>=confirmation:current=best;pending=None;count=0
        else:pending=None;count=0
        output.append(current)
    return np.asarray(output,dtype=int)


def run_state_decisions(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_forecast_smoothing/20261019T062316_546117Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source=args.source_dir/'ema5_shrink_predictions.csv';base=pd.read_csv(source,parse_dates=['Date','label_end_date'])
    base['majority']=base.baseline_prediction
    columns=['p_bear','p_side','p_bull'];scores=base[columns].to_numpy()
    index=pd.read_csv(args.data_dir/'VNINDEX.csv',parse_dates=['Date'])
    parent=json.loads((args.source_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+name)
    output=args.output_dir or ROOT/'reports/regime_state_decisions'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    configs={'hysteresis05':dict(margin=.05,confirmation=1),'confirm2':dict(margin=0.,confirmation=2),
        'hysteresis025':dict(margin=.025,confirmation=1),'hysteresis10':dict(margin=.1,confirmation=1)}
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',source,args.source_dir/'plan.json',args.data_dir/'VNINDEX.csv']
    plan=dict(mode='causal_state_decision_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        configs=configs,primary=['hysteresis05','confirm2'],
        timing='Only current/past scores; reset over any absent market session. Ground-truth labels and endpoints untouched.',
        score_semantics='One-hot selected decisions for metric interface, NOT probabilities or confidence.',
        acceptance='Mean F1 +.01, no worst/directional decline, MCC gain, >=3 fold wins, paired20/60 lower>0 for provisional evidence.',
        caveat='Inspected historical DEVELOPMENT; no outer margin selection, independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    matrices={'incumbent':scores};checks=[]
    for name,rule in configs.items():
        prediction=causal_state_decisions(base.Date,scores,index.Date,**rule)
        matrices[name]=np.eye(3)[prediction]
        for end in [390,780,1170,1460,1560]:
            prefix=causal_state_decisions(base.Date.iloc[:end],scores[:end],index.Date[index.Date<=base.Date.iloc[end-1]],**rule)
            np.testing.assert_array_equal(prefix,prediction[:end]);checks.append(dict(candidate=name,rows=end,prefix_invariance=True))
    (output/'causality_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
    finish_research_study(base,matrices,output,plan['primary'])
    return output


if __name__=='__main__':run_state_decisions()
