"""Predeclared SVC/CatBoost/ExtraTrees nested THREE-CLASS comparison.

Same original 19 features, frozen dates, 3y window and 63-session refits.
Every parameter/scaler fit uses purged past data; historical DEVELOPMENT only.
"""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import hashlib
import json
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import classification_report,f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import experiment_regime as exp

ROOT=Path(__file__).resolve().parent
PREDECLARED=ROOT/'reports/regime_information/20261018T153237_309880Z/next_family_plan.json'
FAMILIES=['SVC','CatBoost','ExtraTrees']


def family_parameters(family,trial):
    if family=='SVC':
        kernel=trial.suggest_categorical('kernel',['linear','rbf'])
        params=dict(kernel=kernel,C=trial.suggest_float('C',.01,30.,log=True),
                    class_weight=trial.suggest_categorical('class_weight',[None,'balanced']),probability=False,
                    cache_size=256,random_state=42)
        if kernel=='rbf':
            mode=trial.suggest_categorical('gamma_mode',['scale','numeric'])
            params['gamma']='scale' if mode=='scale' else trial.suggest_float('gamma',.001,1.,log=True)
        return params
    if family=='CatBoost':
        return dict(loss_function=trial.suggest_categorical('loss_function',['MultiClass','MultiClassOneVsAll']),
                    iterations=trial.suggest_int('iterations',200,500,step=100),depth=trial.suggest_int('depth',3,5),
                    learning_rate=trial.suggest_float('learning_rate',.02,.1,log=True),
                    l2_leaf_reg=trial.suggest_float('l2_leaf_reg',1.,30.,log=True),
                    auto_class_weights=trial.suggest_categorical('auto_class_weights',[None,'Balanced']),
                    allow_writing_files=False,thread_count=2,random_seed=42,verbose=False)
    if family=='ExtraTrees':
        return dict(n_estimators=400,max_depth=trial.suggest_categorical('max_depth',[4,8,None]),
                    min_samples_leaf=trial.suggest_categorical('min_samples_leaf',[10,30,60]),
                    max_features=trial.suggest_categorical('max_features',[.5,.7,1.]),
                    class_weight=trial.suggest_categorical('class_weight',[None,'balanced']),n_jobs=2,random_state=42)
    raise ValueError('Unknown family: '+family)


def build_family(family,parameters):
    if family=='SVC':return make_pipeline(StandardScaler(),SVC(**parameters))
    if family=='ExtraTrees':return ExtraTreesClassifier(**parameters)
    if family=='CatBoost':
        from catboost import CatBoostClassifier
        return CatBoostClassifier(**parameters)
    raise ValueError('Unknown family: '+family)


def assert_family_split(frame,train,validation):
    if len(train)==0 or len(validation)==0:raise ValueError('Empty split')
    boundary=frame.Date.iloc[validation].min()
    if frame.Date.iloc[train].max()>=boundary or frame.label_end_date.iloc[train].max()>=boundary:
        raise ValueError('Unmatured/future labels in model-family split')
    if set(frame.label.iloc[train])!={0,1,2}:raise ValueError('Missing training class')


def tune_family(frame,names,folds,family,trials):
    for tr,va in folds:assert_family_split(frame,tr,va)
    X=frame[names].to_numpy(dtype=np.float32);y=frame.label.to_numpy(dtype=int)
    def objective(trial):
        parameters=family_parameters(family,trial);audits=[];scores=[]
        for tr,va in folds:
            model=build_family(family,parameters)
            model.fit(X[tr],y[tr])
            prediction=np.asarray(model.predict(X[va])).reshape(-1).astype(int)
            score=float(f1_score(y[va],prediction,labels=[0,1,2],average='macro',zero_division=0))
            scores.append(score)
            audits.append(dict(n_train=len(tr),n_validation=len(va),f1=score,
                               latest_train_label_end=str(frame.label_end_date.iloc[tr].max().date()),
                               validation_start=str(frame.Date.iloc[va].min().date())))
        trial.set_user_attr('model_parameters',parameters);trial.set_user_attr('inner_folds',audits)
        return float(np.mean(scores))
    study=optuna.create_study(direction='maximize',sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective,n_trials=trials)
    best=study.best_trial
    return dict(parameters=best.user_attrs['model_parameters'],inner_selection_f1=float(best.value),
                n_trials=len(study.trials),best_trial=best.number,
                trials=[dict(number=t.number,value=t.value,state=t.state.name,parameters=t.params,
                             model_parameters=t.user_attrs.get('model_parameters'),inner_folds=t.user_attrs.get('inner_folds')) for t in study.trials])


def prepare_family_study(args):
    specification=json.loads(PREDECLARED.read_text())
    for package,expected in specification['dependencies'].items():
        if version(package)!=expected:raise ValueError('Predeclared dependency changed: '+package)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','--train-windows','3y',
        '--models','LightGBM','--horizons','20','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    frame,job=frames[20],jobs[0]
    dates=np.concatenate([b['validation'] for o in job['folds'] for b in o['blocks']])
    original=pd.read_csv(args.control_dir/'t20_LightGBM_trend_3y_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label']:
        np.testing.assert_array_equal(frame[key].iloc[dates].to_numpy(),original[key].to_numpy())
    np.testing.assert_allclose(frame.future_return.iloc[dates],original.future_return,rtol=1e-12,atol=1e-12)
    controls=[]
    for group in ['trend','risk']:
        report=json.loads((args.control_dir/'experiment_report.json').read_text())
        controls.append(next(r for r in report['results'] if r['horizon']==20 and r['train_window']=='3y' and r['feature_group']==group))
    timing=[]
    for outer in job['folds']:
        first=outer['blocks'][0]['validation'];assert_family_split(frame,outer['tune'],first)
        inner_frame=frame.iloc[outer['tune']].reset_index(drop=True)
        for tr,va in outer['inner']:assert_family_split(inner_frame,tr,va)
        for block in outer['blocks']:assert_family_split(frame,block['train'],block['validation'])
        timing.append(dict(fold=outer['fold'],n_tuning=len(outer['tune']),inner_boundaries=[dict(train_label_end=str(inner_frame.label_end_date.iloc[tr].max().date()),validation_start=str(inner_frame.Date.iloc[va].min().date())) for tr,va in outer['inner']]))
    plan.update(mode='three_class_nested_family_development',families=FAMILIES,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                predeclared_sha256=hashlib.sha256(PREDECLARED.read_bytes()).hexdigest(),specification=specification,
                control_report_sha256=hashlib.sha256((args.control_dir/'experiment_report.json').read_bytes()).hexdigest(),
                training_timing=timing,parameter_mode='15 trials per family per fold, no outer-label tuning; final refits use selected fixed parameters',
                optuna=dict(n_trials=args.trials,seed=42,pruning=False,timeout=None),
                probability_rule='SVC native class predictions only; probability=False avoids time-insensitive internal Platt CV. No calibrated-confidence claim.',
                assumptions=['Exact same original target, features, outer dates and training cohorts across all families.',
                             'StandardScaler for SVC is fitted inside each inner training split and inside each refit only.',
                             'Each family reported, no unreported outer-label selection or blending.',
                             'Past development history repeatedly inspected; no independent acceptance, profitability or live replacement.'])
    return frame,job,controls,plan


def run_family_study(frame,job,family,trials,output):
    all_rows=[];fold_results=[];selection=[]
    for outer in job['folds']:
        print(f"  {family} outer fold {outer['fold']}: tuning {trials} trials",flush=True)
        tune=frame.iloc[outer['tune']].reset_index(drop=True)
        chosen=tune_family(tune,job['names'],outer['inner'],family,trials)
        if chosen['n_trials']!=trials:raise ValueError('Unequal tuning budget')
        selection.append(dict(outer_fold=outer['fold'],**chosen))
        (output/(family+'_tuning.json')).write_text(json.dumps(selection,indent=2)+'\n')
        records=[];refits=[]
        for block_number,block in enumerate(outer['blocks'],1):
            assert_family_split(frame,block['train'],block['validation'])
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            model=build_family(family,chosen['parameters'])
            model.fit(train[job['names']].to_numpy(dtype=np.float32),train.label.to_numpy(dtype=int))
            prediction=np.asarray(model.predict(valid[job['names']].to_numpy(dtype=np.float32))).reshape(-1).astype(int)
            rows=valid[['Date','label_end_date','label','future_return']].copy()
            rows['prediction']=prediction
            rows['baseline_prediction']=np.bincount(train.label.to_numpy(dtype=int),minlength=3).argmax()
            rows['outer_fold'],rows['refit_block']=outer['fold'],block_number
            records.append(rows)
            refits.append(dict(n_train=len(train),train_label_end=str(train.label_end_date.max().date()),
                               prediction_start=str(valid.Date.min().date()),prediction_end=str(valid.Date.max().date())))
        records=pd.concat(records,ignore_index=True);all_rows.append(records)
        metric=exp.prediction_metrics(records)
        metric.update(fold=outer['fold'],refits=refits,per_class=classification_report(records.label,records.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0))
        fold_results.append(metric)
        pd.concat(all_rows,ignore_index=True).to_csv(output/(family+'_predictions.csv'),index=False)
        (output/(family+'_folds.json')).write_text(json.dumps(fold_results,indent=2)+'\n')
        print(f"  {family} fold {outer['fold']}: F1={metric['f1_macro']:.4f}, MCC={metric['mcc']:.4f}",flush=True)
    rows=pd.concat(all_rows,ignore_index=True)
    f1s=[r['f1_macro'] for r in fold_results];mccs=[r['mcc'] for r in fold_results]
    result=dict(candidate=family,mean_f1=float(np.mean(f1s)),worst_f1=min(f1s),mean_mcc=float(np.mean(mccs)),
                folds=fold_results,pooled=exp.prediction_metrics(rows),
                pooled_class_report=classification_report(rows.label,rows.prediction,labels=[0,1,2],target_names=['bear','side','bull'],output_dict=True,zero_division=0),
                per_year={str(y):exp.prediction_metrics(r) for y,r in rows.groupby(rows.Date.dt.year)})
    return result


def write_family_comparison(results,controls,output):
    table=[]
    for r in results:
        screens=[]
        for control in controls:
            wins=sum(a['f1_macro']>b['f1_macro'] for a,b in zip(r['folds'],control['folds']))
            passed=r['mean_f1']>=control['mean_f1']+.02 and r['worst_f1']>=control['worst_f1'] and r['mean_mcc']>control['mean_mcc'] and wins>=3
            screens.append(dict(control=control['candidate'],delta_f1=r['mean_f1']-control['mean_f1'],fold_wins=wins,passed=bool(passed)))
        table.append(dict(candidate=r['candidate'],mean_f1=r['mean_f1'],worst_f1=r['worst_f1'],mean_mcc=r['mean_mcc'],
                          pooled_f1=r['pooled']['f1_macro'],development_screen_both_controls=all(s['passed'] for s in screens),comparisons=screens))
    (output/'report.json').write_text(json.dumps(dict(role='historical_development_not_independent_test',results=results,controls=controls,comparison=table),indent=2)+'\n')
    pd.DataFrame([{k:v for k,v in r.items() if k!='comparisons'} for r in table]).to_csv(output/'comparison.csv',index=False)
    return table


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if args.trials<1:parser.error('Positive trials required')
    frame,job,controls,plan=prepare_family_study(args)
    output=args.output_dir or ROOT/'reports/regime_families'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    if args.audit_only:return output
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    results=[]
    for family in FAMILIES:
        result=run_family_study(frame,job,family,args.trials,output)
        results.append(result);write_family_comparison(results,controls,output)
        print(f"{family} mean F1={result['mean_f1']:.4f}, worst={result['worst_f1']:.4f}, mean MCC={result['mean_mcc']:.4f}",flush=True)
    print('Done; three-class development only. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':main()
