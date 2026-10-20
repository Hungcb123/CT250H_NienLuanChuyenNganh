"""Reuse original purged-inner parameters; refit-frequency and equal-view ablation.

Historical development only. First replicate each original 63-session prediction
exactly; reject the study if parity fails. No retuning on inspected outer labels.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import experiment_regime_multiclass as study
exp=study.exp
ROOT=study.ROOT


def reused_job(reference,group,refit):
    args=exp.parse_args(['--reference-report',str(reference),'--base-feature-set','close-etf',
        '--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--refit-sessions',str(refit)])
    frames,jobs,plan=exp.prepare_experiment(args)
    if plan['errors']:raise ValueError(str(plan['errors']))
    return frames[20],next(j for j in jobs if j['group']==group),plan


def run_reused(frame,job,source):
    params={r['outer_fold']:r['best_params'] for r in source['inner_tuning']}
    records,audits=[],[]
    for outer in job['folds']:
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured training labels')
            model,scaler=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=params[outer['fold']]),train,job['names'])
            if scaler is not None:raise ValueError('Unexpected scaler for legacy GBM')
            probability=model.predict_proba(valid[job['names']].to_numpy(dtype=np.float32))
            row=valid[['Date','label_end_date','label','future_return']].copy()
            row[study.PROB_COLUMNS]=probability
            row['argmax']=probability.argmax(axis=1)
            row['majority']=np.bincount(train.label.to_numpy(dtype=int),minlength=3).argmax()
            row['outer_fold'],row['refit_block']=outer['fold'],number
            archive=pd.concat(records,ignore_index=True) if records else pd.DataFrame()
            weights,info=study.causal_decision_weights(archive,valid.Date.min())
            row['causal_macro_weights']=(probability*weights).argmax(axis=1)
            records.append(row)
            audits.append(dict(fold=outer['fold'],block=number,prediction_start=str(valid.Date.min().date()),
                               train_start=str(train.Date.min().date()),train_label_end=str(train.label_end_date.max().date()),
                               n_train=len(train),parameters=params[outer['fold']],decision_weights=weights.tolist(),decision_history=info))
    return pd.concat(records,ignore_index=True),audits


def equal_views(first,second):
    for column in ['Date','label_end_date','label','future_return','outer_fold','refit_block','majority']:
        np.testing.assert_array_equal(first[column],second[column])
    rows=first.copy()
    rows[study.PROB_COLUMNS]=(first[study.PROB_COLUMNS].to_numpy()+second[study.PROB_COLUMNS].to_numpy())/2
    rows['argmax']=rows[study.PROB_COLUMNS].to_numpy().argmax(axis=1)
    completed=[];audits=[]
    for (fold,block),part in rows.groupby(['outer_fold','refit_block'],sort=False):
        part=part.copy()
        archive=pd.concat(completed,ignore_index=True) if completed else pd.DataFrame()
        weights,info=study.causal_decision_weights(archive,part.Date.min())
        part['causal_macro_weights']=(part[study.PROB_COLUMNS].to_numpy()*weights).argmax(axis=1)
        completed.append(part)
        audits.append(dict(fold=int(fold),block=int(block),prediction_start=str(part.Date.min().date()),weights=weights.tolist(),history=info))
    return pd.concat(completed,ignore_index=True),audits


def parity_check(records,path):
    old=pd.read_csv(path,parse_dates=['Date','label_end_date'])
    for name in ['Date','label_end_date','label','outer_fold','refit_block']:
        np.testing.assert_array_equal(records[name],old[name])
    np.testing.assert_allclose(records.future_return,old.future_return,atol=1e-12,rtol=1e-12)
    np.testing.assert_array_equal(records.argmax,old.prediction)
    return dict(passed=True,rows=len(old),prediction_matches=int((records.argmax.to_numpy()==old.prediction.to_numpy()).sum()),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--original-report',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z/experiment_report.json')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    original=json.loads(args.original_report.read_text())
    oldplan=json.loads((args.original_report.parent/'experiment_plan.json').read_text())
    output=args.output_dir or ROOT/'reports/regime_multiclass_reuse'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    jobs={};sources={}
    for refit in [63,20]:
        for group in ['trend','risk']:
            frame,job,plan=reused_job(args.reference_report,group,refit)
            if plan['input_hashes']!=oldplan['input_hashes']:raise ValueError('Legacy data changed')
            source=next(r for r in original['results'] if r['feature_group']==group and r['train_window']=='3y' and r['horizon']==20)
            if source['features']!=job['names']:raise ValueError('Legacy feature schema changed')
            jobs[(refit,group)]=(frame,job);sources[group]=source
    plan.update(mode='legacy_parameter_reuse_three_class_development',candidates=['trend_63','risk_63','equal_63','trend_20','risk_20','equal_20'],
                parameters_origin='Original per-outer-fold purged INNER tuning, reused unchanged; no new tuning',
                original_report_sha256=hashlib.sha256(args.original_report.read_bytes()).hexdigest(),
                original_plan_sha256=hashlib.sha256((args.original_report.parent/'experiment_plan.json').read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                control='legacy_trend_63/argmax; also compare legacy_risk_63/argmax',
                acceptance='Only development screen: gain >=.02 mean fold F1, no worst-fold degradation, MCC gain and >=3 improved folds against BOTH original controls. No fresh-test acceptance.',
                equal_view_weights=[.5,.5],decisions=['argmax','causal_macro_weights'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    results=[];parity={}
    for refit in [63,20]:
        completed={}
        for group in ['trend','risk']:
            name=f'legacy_{group}_{refit}'
            print('Running '+name,flush=True)
            records,audits=run_reused(*jobs[(refit,group)],sources[group])
            if refit==63:
                parity[group]=parity_check(records,args.original_report.parent/(sources[group]['candidate']+'_predictions.csv'))
                (output/'legacy_parity.json').write_text(json.dumps(parity,indent=2)+'\n')
            completed[group]=records
            records.to_csv(output/(name+'_predictions.csv'),index=False)
            (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
            summary=study.summarize_multiclass(name,records);results.extend(summary)
            (output/'report.json').write_text(json.dumps(dict(role='development_only',results=results),indent=2)+'\n')
            print([(r['decision'],round(r['mean_f1'],4),round(r['worst_f1'],4),round(r['mean_mcc'],4)) for r in summary],flush=True)
        name=f'legacy_equal_{refit}'
        records,audits=equal_views(completed['trend'],completed['risk'])
        records.to_csv(output/(name+'_predictions.csv'),index=False)
        (output/(name+'_refits.json')).write_text(json.dumps(audits,indent=2)+'\n')
        summary=study.summarize_multiclass(name,records);results.extend(summary)
        (output/'report.json').write_text(json.dumps(dict(role='development_only',results=results),indent=2)+'\n')
        print(name,[(r['decision'],round(r['mean_f1'],4),round(r['worst_f1'],4),round(r['mean_mcc'],4)) for r in summary],flush=True)
    table=[]
    controls=[r for r in results if r['candidate'] in ['legacy_trend_63/argmax','legacy_risk_63/argmax']]
    for r in results:
        passed=all(r['mean_f1']>=c['mean_f1']+.02 and r['worst_f1']>=c['worst_f1'] and r['mean_mcc']>c['mean_mcc'] and sum(a['f1']>b['f1'] for a,b in zip(r['folds'],c['folds']))>=3 for c in controls)
        table.append(dict(candidate=r['candidate'],mean_f1=r['mean_f1'],worst_f1=r['worst_f1'],mean_mcc=r['mean_mcc'],pooled_f1=r['pooled']['f1'],development_screen=passed))
    pd.DataFrame(table).to_csv(output/'comparison.csv',index=False)
    print('Done. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
