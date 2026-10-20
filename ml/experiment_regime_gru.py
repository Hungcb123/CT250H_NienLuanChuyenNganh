"""Small causal GRU: matched one-session/ten-session input ablation.

Train entirely on mature outcomes; no random validation or outer early stopping.
Original fixed calendar and adaptive labels are retained on all1,560 dates.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn

import experiment_regime as exp
import experiment_regime_labels as labels
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
torch.set_num_threads(2)


class TemporalGRU(nn.Module):
    def __init__(self,n_features,hidden=8):
        super().__init__()
        self.dropout=nn.Dropout(.1)
        self.gru=nn.GRU(n_features,hidden,batch_first=True)
        self.head=nn.Linear(hidden,3)

    def forward(self,x):
        _,state=self.gru(self.dropout(x))
        return self.head(state[-1])


def prepare_temporal_inputs(full_values,positions,length,normalizer=None):
    values=np.asarray(full_values,dtype=float);positions=np.asarray(positions,dtype=int)
    if length<1 or (positions<0).any() or (positions>=len(values)).any():raise ValueError('Invalid sequence endpoints')
    windows=np.full((len(positions),length,values.shape[1]),np.nan,dtype=float)
    for row,end in enumerate(positions):
        start=max(0,end-length+1);part=values[start:end+1]
        windows[row,-len(part):]=part
    missing=~np.isfinite(windows)
    if normalizer is None:
        flat=windows.reshape(-1,values.shape[1]);median=np.nanmedian(flat,axis=0)
        if not np.isfinite(median).all():raise ValueError('Entire feature unavailable in training')
        filled=np.where(np.isfinite(flat),flat,median)
        mean=filled.mean(axis=0);scale=filled.std(axis=0);scale=np.where(scale>1e-6,scale,1.)
        normalizer=dict(median=median,mean=mean,scale=scale)
    filled=np.where(missing,normalizer['median'],windows)
    z=np.clip((filled-normalizer['mean'])/normalizer['scale'],-10.,10.)
    # Missing FEATURE indicators are imputed for the network, never market prices.
    result=np.concatenate([z,missing.astype(float)],axis=2).astype(np.float32)
    return result,normalizer


def fit_temporal_gru(train,valid,full_values,calendar,names,length,seed,epochs,device,checkpoint):
    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured GRU supervision')
    calendar=pd.DatetimeIndex(calendar)
    train_ids=calendar.get_indexer(train.Date);valid_ids=calendar.get_indexer(valid.Date)
    X,normalizer=prepare_temporal_inputs(full_values,train_ids,length)
    V,_=prepare_temporal_inputs(full_values,valid_ids,length,normalizer)
    y=train.label.to_numpy(dtype=int);counts=np.bincount(y,minlength=3)
    if (counts<=0).any():raise ValueError('Missing GRU class')
    torch.manual_seed(seed)
    if device.type=='cuda':torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    model=TemporalGRU(X.shape[2]).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=.05)
    loss_fn=nn.CrossEntropyLoss(weight=torch.tensor(len(y)/(3*counts),dtype=torch.float32,device=device))
    data=torch.from_numpy(X).to(device);truth=torch.from_numpy(y).long().to(device)
    generator=torch.Generator().manual_seed(seed)
    model.train()
    for _ in range(epochs):
        order=torch.randperm(len(y),generator=generator)
        for start in range(0,len(y),128):
            ids=order[start:start+128].to(device)
            optimizer.zero_grad(set_to_none=True)
            loss=loss_fn(model(data[ids]),truth[ids])
            if not torch.isfinite(loss):raise ValueError('Nonfinite GRU loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
    model.eval()
    with torch.no_grad():probability=torch.softmax(model(torch.from_numpy(V).to(device)),dim=1).cpu().numpy().astype(float)
    probability/=probability.sum(axis=1,keepdims=True)
    state=dict(weights={k:v.detach().cpu() for k,v in model.state_dict().items()},normalizer={k:torch.as_tensor(v) for k,v in normalizer.items()},
        n_features=X.shape[2],sequence_length=length,seed=seed,epochs=epochs,feature_names=names,
        latest_training_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()))
    torch.save(state,checkpoint)
    restored=torch.load(checkpoint,map_location='cpu',weights_only=True)
    other=TemporalGRU(restored['n_features']).to(device);other.load_state_dict(restored['weights']);other.eval()
    with torch.no_grad():again=torch.softmax(other(torch.from_numpy(V).to(device)),dim=1).cpu().numpy().astype(float)
    again/=again.sum(axis=1,keepdims=True)
    np.testing.assert_allclose(probability,again,atol=1e-7,rtol=1e-7)
    np.testing.assert_array_equal(probability.argmax(axis=1),again.argmax(axis=1))
    return probability,dict(n_train=len(train),n_valid=len(valid),latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(valid.Date.min().date()),
        checkpoint=str(checkpoint),sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),reload_max_error=float(np.abs(probability-again).max()))


def run_gru_experiment(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--seed-dir',type=Path,default=ROOT/'reports/regime_density_seeds/20261019T061537_193740Z')
    parser.add_argument('--info-dir',type=Path,default=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z')
    parser.add_argument('--source-dir',type=Path,default=ROOT/'reports/regime_forecast_smoothing/20261019T062316_546117Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--epochs',type=int,default=40)
    parser.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    args=parser.parse_args(argv)
    if args.epochs<1:parser.error('Require positive epochs')
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv');etf,_=exp.base.load_market_data(args.data_dir/'E1VFVN30.csv')
    frame=labels.relabel_cohort(frames[20],labels.build_label_book(index),'vol_1sigma')
    names=list(dict.fromkeys(n for j in jobs for n in j['names']))
    full,_=exp.base.build_feature_matrix(index,etf,'close-etf');full=pd.concat([full,exp.long_features(index)],axis=1)
    full_values=full[names].to_numpy(dtype=float)
    source=args.source_dir/'ema5_shrink_predictions.csv';base=pd.read_csv(source,parse_dates=['Date','label_end_date']);base['majority']=base.baseline_prediction
    columns=['p_bear','p_side','p_bull']
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    risk=pd.read_csv(args.parent_dir/'vol_1sigma/risk_predictions.csv',parse_dates=['Date','label_end_date'])
    selected=np.empty((len(base),3));paths=[Path(__file__),ROOT/'regime_research_evaluation.py',source,args.parent_dir/'plan.json',args.info_dir/'inner_selection.json',args.parent_dir/'vol_1sigma/risk_predictions.csv']
    for choice in json.loads((args.info_dir/'inner_selection.json').read_text()):
        path=args.info_dir/(choice['chosen']+'_scores.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        mask=base.outer_fold.eq(choice['fold']).to_numpy();selected[mask]=rows.loc[mask,columns].to_numpy()
    old_class=.5*(selected+risk[columns].to_numpy());densities=[]
    for seed in [7,21,42,84,126]:
        for target in ['raw','normalized']:
            path=args.parent_dir/'vol_1sigma'/('expanding_'+target+'_mapped_predictions.csv') if seed==42 else args.seed_dir/f'seed{seed}_{target}_scores.csv'
            paths.append(path);rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            score=rows[columns].to_numpy()
            if seed==42:score=score/rows[['base_bear','base_side','base_bull']].to_numpy();score/=score.sum(axis=1,keepdims=True)
            densities.append(score)
    old_density=np.mean(densities,axis=0)
    device=torch.device('cuda' if args.device=='auto' and torch.cuda.is_available() else ('cpu' if args.device=='auto' else args.device))
    plan.update(mode='small_causal_GRU_sequence_ablation_DEVELOPMENT',optuna=None,features=names,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        model=dict(hidden=8,layers=1,dropout=.1,epochs=args.epochs,batch=128,optimizer='AdamW',lr=.003,weight_decay=.05,seeds=[7,21,42],lengths=[1,10]),
        preprocessing='Raw accepted calendar windows ending at t; training-only feature median/mean/std, z clip10, missing-feature mask. Never fill prices or future features.',
        primary='gru10_supplement: .25 old information classifier + .25 equal3seed GRU10 + .5 old five-seed density, followed by equal current/causalEMA5',
        secondary='gru10_replace: .5 GRU10 + .5 density, same causalEMA5 mixture. Length1 matched network is diagnostic control.',
        timing='Each outer block fits only labels ending before first predicted date; fixed40epochs, no validation outcomes or early stopping. Training batches may shuffle within permitted past only.',
        environment=dict(torch=torch.__version__,cuda=torch.version.cuda,device=str(device),gpu=torch.cuda.get_device_name(device) if device.type=='cuda' else None),
        caveat='Small correlated dataset; neural networks may overfit. Class-balanced outputs are scores, not calibrated probabilities. Repeatedly inspected history; no independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_gru'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'models').mkdir();(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True);print('Device: '+str(device),flush=True)
    by_length={};audits=[]
    for length in [1,10]:
        seed_scores=[]
        for seed in [7,21,42]:
            records=[]
            for outer in jobs[0]['folds']:
                for number,block in enumerate(outer['blocks'],1):
                    train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
                    path=output/'models'/f'len{length}_seed{seed}_fold{outer["fold"]}_block{number}.pt'
                    score,audit=fit_temporal_gru(train,valid,full_values,index.Date,names,length,seed,args.epochs,device,path)
                    rows=valid[['Date','label_end_date','label','future_return']].copy();rows[columns]=score
                    rows['outer_fold'],rows['refit_block']=outer['fold'],number;records.append(rows)
                    audits.append(dict(length=length,seed=seed,fold=outer['fold'],block=number,**audit))
                pd.concat(records,ignore_index=True).to_csv(output/f'len{length}_seed{seed}_scores.csv',index=False)
                (output/'refit_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
                print(f'GRU{length} seed{seed} fold{outer["fold"]} complete',flush=True)
            rows=pd.concat(records,ignore_index=True)
            for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
            seed_scores.append(rows[columns].to_numpy())
        by_length[length]=np.mean(seed_scores,axis=0)
    from experiment_regime_forecast_smoothing import causal_forecast_ema
    matrices={'incumbent':base[columns].to_numpy()}
    for length,score in by_length.items():
        supplement=.25*old_class+.25*score+.5*old_density
        replace=.5*score+.5*old_density
        matrices[f'gru{length}']=score
        matrices[f'gru{length}_supplement']=.5*supplement+.5*causal_forecast_ema(base.Date,supplement,index.Date,5)
        matrices[f'gru{length}_replace']=.5*replace+.5*causal_forecast_ema(base.Date,replace,index.Date,5)
    finish_research_study(base,matrices,output,['gru10_supplement','gru10_replace'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_gru_experiment()
