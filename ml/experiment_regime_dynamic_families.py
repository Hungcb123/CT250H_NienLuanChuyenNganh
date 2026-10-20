"""Fixed diverse adaptive-target learners; choose using purged inner folds.

No outer tuning or label changes. Frozen old classifier remains a fallback.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import HistGradientBoostingClassifier,RandomForestClassifier,ExtraTreesClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from threadpoolctl import threadpool_limits

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_expert_selection as experts
from experiment_regime_dynamic_tuning import dynamic_inner_score,assert_dynamic_inner_timing
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
FAMILIES=['legacy_equal','CatBoost','HistGBM','RandomForest','ExtraTrees','SVC_RBF','MLP','ShrinkageLDA','KNN']


def fit_dynamic_family(train,valid,names,family,legacy=None):
    if train.label_end_date.max()>=valid.Date.min():raise ValueError('Unmatured family training label')
    y=train.label.to_numpy(dtype=int)
    if set(y)!={0,1,2}:raise ValueError('Missing training class')
    X,V=train[names].to_numpy(dtype=np.float32),valid[names].to_numpy(dtype=np.float32)
    if not np.isfinite(X).all() or not np.isfinite(V).all():raise ValueError('Nonfinite family input')
    with threadpool_limits(limits=2):
        if family=='legacy_equal':
            parts=[]
            for group in ['trend','risk']:
                spec=legacy[group]
                model,_=exp.base.fit_selected_candidate(dict(model_name='LightGBM',best_params=spec['params']),train,spec['names'])
                parts.append(model.predict_proba(valid[spec['names']].to_numpy(dtype=np.float32)))
            return np.mean(parts,axis=0)
        if family=='CatBoost':model=CatBoostClassifier(iterations=300,depth=4,learning_rate=.03,l2_leaf_reg=5.,loss_function='MultiClass',auto_class_weights='Balanced',random_seed=42,thread_count=2,verbose=False,allow_writing_files=False)
        elif family=='HistGBM':model=HistGradientBoostingClassifier(max_iter=200,learning_rate=.03,max_leaf_nodes=15,min_samples_leaf=30,l2_regularization=1.,class_weight='balanced',early_stopping=False,random_state=42)
        elif family in ['RandomForest','ExtraTrees']:
            cls=RandomForestClassifier if family=='RandomForest' else ExtraTreesClassifier
            model=cls(n_estimators=300,max_depth=6,min_samples_leaf=10,max_features=.7,class_weight='balanced',random_state=42,n_jobs=2)
        elif family=='SVC_RBF':model=SVC(C=1.,kernel='rbf',gamma='scale',class_weight='balanced',probability=True,random_state=42)
        elif family=='MLP':model=MLPClassifier(hidden_layer_sizes=(32,16),activation='tanh',solver='lbfgs',alpha=1.,max_iter=500,random_state=42)
        elif family=='ShrinkageLDA':model=LinearDiscriminantAnalysis(solver='lsqr',shrinkage='auto',priors=np.ones(3)/3)
        elif family=='KNN':model=KNeighborsClassifier(n_neighbors=min(60,len(train)),weights='distance',n_jobs=2)
        else:raise ValueError('Unknown family')
        if family in ['SVC_RBF','MLP','ShrinkageLDA','KNN']:
            scaler=StandardScaler().fit(X);X,V=scaler.transform(X),scaler.transform(V)
        if family=='MLP':model.fit(X,y,sample_weight=compute_sample_weight('balanced',y))
        else:model.fit(X,y)
        np.testing.assert_array_equal(model.classes_,[0,1,2])
        scores=model.predict_proba(V)
        if family=='KNN':
            scores/=np.bincount(y,minlength=3)/len(y)
            scores/=scores.sum(axis=1,keepdims=True)
    if not np.isfinite(scores).all() or (scores<0).any():raise ValueError('Invalid family scores')
    np.testing.assert_allclose(scores.sum(axis=1),1.,atol=1e-10)
    return scores


def run_dynamic_families(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    inherited=exp.parse_args(['--reference-report',str(args.reference_report),'--data-dir',str(args.data_dir),
        '--base-feature-set','close-etf','--feature-groups','trend','risk','--train-windows','3y','--models','LightGBM',
        '--horizons','20','--inner-splits','3','--refit-sessions','63'])
    frames,jobs,plan=exp.prepare_experiment(inherited)
    if plan['errors']:raise ValueError(str(plan['errors']))
    index,_=exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame=labels.relabel_cohort(frames[20],labels.build_label_book(index),'vol_1sigma')
    names=list(dict.fromkeys(c for j in jobs for c in j['names']))
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    ids=np.concatenate([b['validation'] for o in jobs[0]['folds'] for b in o['blocks']])
    for key in ['Date','label_end_date','label']:np.testing.assert_array_equal(frame.iloc[ids][key],base[key])
    paths=[Path(__file__),ROOT/'regime_research_evaluation.py',ROOT/'experiment_regime_dynamic_tuning.py',args.parent_dir/'plan.json']
    paths += [old/n for n in ['trend_predictions.csv','risk_predictions.csv','expanding_raw_mapped_predictions.csv','expanding_normalized_mapped_predictions.csv']]
    plan.update(mode='diverse_adaptive_target_families_DEVELOPMENT',optuna=None,families=FAMILIES,features=names,
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        parameters='Fixed parameters in fit_dynamic_family; no new hyperparameter search. Class balancing is training-only; scalers training-only; no early stopping.',
        primary='inner_supplement_blend: .25 old equal classifier + .25 inner-selected classifier + .5 old density',
        secondary='inner_replacement_blend: .5 inner-selected classifier + .5 old density',
        selection='Three purged inner folds: .5 mean macro + .25 worst macro + .25 weaker mean directional F1. Default legacy_equal; switch only for >=.01 objective gain. No outer choice.',
        acceptance='Mean F1 +.01, no worst fold or mean bear/bull F1 degradation, MCC gain, >=3 wins; both paired20/60 lower bounds >0 for provisional evidence.',
        caveats='Previously inspected historical development. SVC probabilities use internal training-only calibration, not temporal probability validation; every score is a decision score. No independent acceptance or deployment.')
    output=args.output_dir or ROOT/'reports/regime_dynamic_families'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False);(output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    records={name:[] for name in FAMILIES};selected=[];choices=[]
    for outer in jobs[0]['folds']:
        legacy={j['group']:dict(names=j['names'],params=next(r['best_params'] for r in parent['classifier_parameters'][j['group']] if r['outer_fold']==outer['fold'])) for j in jobs}
        tune=frame.iloc[outer['tune']].reset_index(drop=True);folds=exp.base.purged_folds(tune,3)
        boundary=frame.Date.iloc[outer['blocks'][0]['validation'][0]]
        assert_dynamic_inner_timing(tune,folds,boundary)
        scores=[]
        for family in FAMILIES:
            metrics=[]
            for t,v in folds:
                train,valid=tune.iloc[t],tune.iloc[v]
                probability=fit_dynamic_family(train,valid,names,family,legacy)
                metrics.append(exp.base.classification_metrics(valid.label,probability.argmax(axis=1),train.label))
            scores.append(dict(family=family,score=dynamic_inner_score(metrics),folds=metrics))
        best=max(scores,key=lambda r:r['score'])
        chosen=best['family'] if best['score']>=scores[0]['score']+.01 else 'legacy_equal'
        choices.append(dict(fold=outer['fold'],chosen=chosen,outer_boundary=str(boundary.date()),latest_tuning_label_end=str(tune.label_end_date.max().date()),scores=scores))
        (output/'inner_selection.json').write_text(json.dumps(choices,indent=2)+'\n')
        print('Fold '+str(outer['fold'])+' inner choice '+chosen,flush=True)
        for number,block in enumerate(outer['blocks'],1):
            train,valid=frame.iloc[block['train']],frame.iloc[block['validation']]
            for family in FAMILIES:
                probability=fit_dynamic_family(train,valid,names,family,legacy)
                rows=valid[['Date','label_end_date','label','future_return']].copy();rows[experts.PROBS]=probability
                rows['outer_fold'],rows['refit_block']=outer['fold'],number
                records[family].append(rows)
                if family==chosen:selected.append(rows.copy())
        for family,chunks in records.items():pd.concat(chunks,ignore_index=True).to_csv(output/(family+'_scores.csv'),index=False)
        print('Fold '+str(outer['fold'])+' all families complete',flush=True)
    selected=pd.concat(selected,ignore_index=True)
    matrices={family:pd.concat(chunks,ignore_index=True)[experts.PROBS].to_numpy() for family,chunks in records.items()}
    old_classifiers=[];old_densities=[]
    for g in ['trend','risk']:
        rows=pd.read_csv(old/(g+'_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        old_classifiers.append(rows[experts.PROBS].to_numpy())
    old_equal=np.mean(old_classifiers,axis=0)
    np.testing.assert_allclose(matrices['legacy_equal'],old_equal,atol=1e-12,rtol=1e-12)
    for t in ['raw','normalized']:
        rows=pd.read_csv(old/('expanding_'+t+'_mapped_predictions.csv'),parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(rows[key],base[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);old_densities.append(score)
    old_density=np.mean(old_densities,axis=0)
    matrices.update({name+'_blend':.5*score+.5*old_density for name,score in list(matrices.items())})
    chosen=selected[experts.PROBS].to_numpy()
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(selected[key],base[key])
    matrices['inner_supplement_blend']=.25*old_equal+.25*chosen+.5*old_density
    matrices['inner_replacement_blend']=.5*chosen+.5*old_density
    matrices['family_pool_blend']=.5*np.mean([matrices[n] for n in FAMILIES],axis=0)+.5*old_density
    matrices['incumbent']=.5*old_equal+.5*old_density
    finish_research_study(base,matrices,output,['inner_supplement_blend','inner_replacement_blend'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_dynamic_families()
