"""Small causal gate: learn which component wins on mature OOF disagreements."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from experiment_regime_temporal_fusion import choose_temporal_fusion
from experiment_regime_forecast_smoothing import causal_forecast_ema
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent


def replay_component_gate(base,classifier,density,features,calendar,fallback):
    positions=pd.DatetimeIndex(calendar).get_indexer(base.Date)
    if (positions<0).any():raise ValueError('Missing gate calendar date')
    buckets=(positions-positions[0])//20;last_bucket=None;model=None;result=[];audits=[]
    class_prediction=classifier.argmax(axis=1);density_prediction=density.argmax(axis=1)
    for row,boundary in enumerate(base.Date):
        if buckets[row]!=last_bucket:
            known=np.flatnonzero(((base.Date<boundary)&(base.label_end_date<boundary)).to_numpy())[-504:]
            y=base.label.iloc[known].to_numpy(dtype=int)
            if not np.isin(y,[0,1,2]).all():raise ValueError('Invalid mature gate truth')
            counts=np.bincount(y,minlength=3) if len(y) else np.zeros(3,dtype=int)
            c_right=class_prediction[known]==y;d_right=density_prediction[known]==y
            use=c_right!=d_right;ids=known[use];target=d_right[use].astype(int)
            winners=np.bincount(target,minlength=2);model=None
            ready=len(known)>=126 and (counts>=5).all() and len(ids)>=60 and (winners>=15).all()
            info=dict(Date=str(boundary.date()),n_history=len(known),informative_rows=len(ids),winner_counts=winners.tolist(),
                latest_label_end=str(base.label_end_date.iloc[known].max()) if len(known) else None,ready=bool(ready))
            if ready:
                weights=len(known)/(3*counts[base.label.iloc[ids].to_numpy(dtype=int)])
                model=LGBMClassifier(n_estimators=60,learning_rate=.03,max_depth=2,num_leaves=4,min_child_samples=20,
                    reg_alpha=.5,reg_lambda=5.,min_split_gain=.01,random_state=42,n_jobs=2,verbosity=-1)
                model.fit(features[ids],target,sample_weight=weights)
                np.testing.assert_array_equal(model.classes_,[0,1])
                info['training_class_cost']=weights.tolist()
            audits.append(info);last_bucket=buckets[row]
        if model is None:score=fallback[row]
        else:
            weight=float(np.clip(model.predict_proba(features[row:row+1])[0,1],.1,.9))
            score=(1-weight)*classifier[row]+weight*density[row]
        result.append(score)
    return np.asarray(result),audits


def run_component_gate(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_temporal_fusion/20261019T063220_032375Z')
    parser.add_argument('--seed-dir',type=Path,default=ROOT/'reports/regime_density_seeds/20261019T061537_193740Z')
    parser.add_argument('--info-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    source=args.source_dir/'adaptive_pool_smoothed_predictions.csv';base=pd.read_csv(source,parse_dates=['Date','label_end_date']);base['majority']=base.baseline_prediction
    cols=['p_bear','p_side','p_bull'];index=pd.read_csv(args.data_dir/'VNINDEX.csv',parse_dates=['Date'])
    parent=json.loads((args.source_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed: '+name)
    old=args.parent_dir/'vol_1sigma';risk=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date'])
    for k in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[k],risk[k])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_temporal_fusion.py',ROOT/'experiment_regime_forecast_smoothing.py',source,args.source_dir/'plan.json',args.info_dir/'inner_selection.json',old/'risk_predictions.csv',args.data_dir/'VNINDEX.csv']
    selected=np.empty((len(base),3))
    for choice in json.loads((args.info_dir/'inner_selection.json').read_text()):
        path=args.info_dir/(choice['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for k in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[k],rows[k])
        mask=base.outer_fold.eq(choice['fold']).to_numpy();selected[mask]=rows.loc[mask,cols].to_numpy()
    classifier=.5*(selected+risk[cols].to_numpy());parts=[]
    for seed in [7,21,42,84,126]:
        for target in ['raw','normalized']:
            path=old/('expanding_'+target+'_mapped_predictions.csv') if seed==42 else args.seed_dir/f'seed{seed}_{target}_scores.csv'
            paths.append(path);rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for k in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[k],rows[k])
            score=rows[cols].to_numpy()
            if seed==42:score=score/rows[['base_bear','base_side','base_bull']].to_numpy();score/=score.sum(axis=1,keepdims=True)
            parts.append(score)
    density=np.mean(parts,axis=0);fixed=.5*(classifier+density)
    adaptive,_=choose_temporal_fusion(base,classifier,density,index.Date)
    fallback=.5*fixed+.25*adaptive[252]+.25*adaptive[504]
    incumbent=.5*fallback+.5*causal_forecast_ema(base.Date,fallback,index.Date,5)
    np.testing.assert_allclose(incumbent,base[cols],atol=1e-12,rtol=1e-12)
    entropy=lambda p:-np.sum(p*np.log(np.maximum(p,1e-8)),axis=1,keepdims=True)
    margin=lambda p:np.diff(np.sort(p,axis=1)[:,-2:],axis=1)
    raw_sigma=np.log(index.Close).diff().rolling(20).std(ddof=1)*np.sqrt(20)
    context=pd.DataFrame({'Date':index.Date,'log_sigma':np.log(raw_sigma),'past_z20':np.log(index.Close/index.Close.shift(20))/raw_sigma})
    known=base[['Date']].merge(context,on='Date',validate='one_to_one')
    features=np.column_stack([classifier,density,classifier-density,entropy(classifier),entropy(density),margin(classifier),margin(density),known[['log_sigma','past_z20']]])
    if not np.isfinite(features).all():raise ValueError('Nonfinite gate context')
    output=args.output_dir or ROOT/'reports/regime_component_gate'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='mature_OOF_component_reliability_gate_DEVELOPMENT',source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        supervision='Only mature OOF rows where exactly one component predicts the correct class. Binary target1=density wins,0=classifier wins. Both-wrong/both-right rows excluded.',
        features='Both score vectors/difference, entropy/margins, known log horizon sigma and past20 normalized return; no true current label or absolute date.',
        training='Refresh20 sessions, last504 mature rows; min126 history/5 each true class; min60 informative/15 each winner. LightGBM60 depth2 leaves4, minleaf20, L1.5/L2=5. True-class cost weights from whole past history.',
        primary='gate_supplement: .5 existing causal-adaptive raw fusion + .5 gated raw fusion; then equal current/causalEMA5',
        secondary='gate_replace: gated raw fusion with same EMA; insufficient history returns existing causal-adaptive raw fusion exactly',
        acceptance='Mean F1 incumbent+.01, no worst/directional decline, MCC gain, >=3 wins; paired20/60 lower>0 for provisional evidence.',
        caveat='Gate scores and class scores are not calibrated probabilities. Repeatedly inspected historical development; no independent acceptance or deployment.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print('Output: '+str(output.resolve()),flush=True)
    value,audit=replay_component_gate(base,classifier,density,features,index.Date,fallback)
    combined=.5*fallback+.5*value
    matrices=dict(incumbent=incumbent,gate_supplement=.5*combined+.5*causal_forecast_ema(base.Date,combined,index.Date,5),
        gate_replace=.5*value+.5*causal_forecast_ema(base.Date,value,index.Date,5))
    checks=[]
    for end in [390,780,1170,1460,1560]:
        prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_=replay_component_gate(prefix,classifier[:end],density[:end],features[:end],index.Date[index.Date<=cutoff],fallback[:end])
        np.testing.assert_allclose(actual,value[:end],atol=1e-12,rtol=1e-12)
        checks.append(dict(rows=end,unknown_outcome_corruption_invariant=True))
    (output/'gate_history.json').write_text(json.dumps(audit,indent=2)+'\n');(output/'causality_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
    finish_research_study(base,matrices,output,['gate_supplement','gate_replace'])
    return output


if __name__=='__main__':run_component_gate()
