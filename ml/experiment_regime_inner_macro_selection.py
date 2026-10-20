"""Replay source studies with pure INNER macro-F1 selection, not outer choice."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import experiment_regime_expert_selection as experts
from regime_research_evaluation import finish_research_study

ROOT=Path(__file__).resolve().parent
STUDIES={
 'information':('regime_dynamic_information/20261019T052057_760569Z','name','control'),
 'families':('regime_dynamic_families/20261019T052530_594387Z','family','legacy_equal'),
 'losses':('regime_dynamic_losses/20261019T052808_023744Z','loss','legacy_equal')}


def run_inner_macro_selection(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,default=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args(argv)
    parent=json.loads((args.parent_dir/'plan.json').read_text())
    for name,digest in parent['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Parent changed: '+name)
    old=args.parent_dir/'vol_1sigma'
    base=pd.read_csv(old/'trend_predictions.csv',parse_dates=['Date','label_end_date'])
    trend=base[experts.PROBS].to_numpy()
    risk_frame=pd.read_csv(old/'risk_predictions.csv',parse_dates=['Date','label_end_date'])
    for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],risk_frame[key])
    risk=risk_frame[experts.PROBS].to_numpy();equal=.5*(trend+risk)
    densities=[];paths=[Path(__file__),ROOT/'regime_research_evaluation.py',args.parent_dir/'plan.json',old/'trend_predictions.csv',old/'risk_predictions.csv']
    for target in ['raw','normalized']:
        path=old/('expanding_'+target+'_mapped_predictions.csv');paths.append(path)
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        score=rows[experts.PROBS].to_numpy()/rows[['base_bear','base_side','base_bull']].to_numpy()
        score/=score.sum(axis=1,keepdims=True);densities.append(score)
    density=np.mean(densities,axis=0)
    for study,(directory,key,fallback) in STUDIES.items():
        folder=ROOT/'reports'/directory
        source_plan=json.loads((folder/'plan.json').read_text())
        for name,digest in source_plan['source_hashes'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Study source changed: '+name)
        paths += [folder/'plan.json',folder/'inner_selection.json']+list(folder.glob('*_scores.csv'))
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output=args.output_dir or ROOT/'reports/regime_inner_macro_selection'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True,exist_ok=False)
    plan=dict(mode='pure_inner_macro_selection_DEVELOPMENT',source_hashes=hashes,
        selection='Per source study/outer fold maximize mean of three stored purged inner macro F1 scores; switch only if >=.01 above legacy/control; ties source order. NO outer metrics used to choose.',
        source_studies=STUDIES,primary=['macro_information_blend','macro_families_supplement','macro_families_replacement'],
        mixture='Information: .25 selected trend + .25 old risk + .5 old density. Family supplement: .25 selected classifier + .25 old equal + .5 density. Replacement: .5 selected classifier + .5 density.',
        acceptance='Same mean+1pt/worst/directional/MCC/3fold screen and paired20/60 intervals; no independent acceptance.',
        caveat='Protocol motivated by already inspected outcomes. Reusing true inner scores preserves timing, but cannot undo research selection bias.')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    matrices={'incumbent':.5*equal+.5*density};audit=[]
    for study,(directory,key,fallback) in STUDIES.items():
        folder=ROOT/'reports'/directory;choices=json.loads((folder/'inner_selection.json').read_text())
        selected=np.empty((len(base),3))
        for outer in choices:
            mean=lambda r:float(np.mean([f['f1_macro'] for f in r['folds']]))
            rows=outer['scores'];best=max(rows,key=mean);control=next(r for r in rows if r[key]==fallback)
            choice=best[key] if mean(best)>=mean(control)+.01 else fallback
            mask=base.outer_fold.eq(outer['fold']).to_numpy()
            if pd.Timestamp(outer['latest_tuning_label_end'])>=pd.Timestamp(outer['outer_boundary']):raise ValueError('Unmatured source selection')
            forecasts=pd.read_csv(folder/(choice+'_scores.csv'),parse_dates=['Date','label_end_date'])
            for c in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[c],forecasts[c])
            selected[mask]=forecasts.loc[mask,experts.PROBS].to_numpy()
            audit.append(dict(study=study,fold=outer['fold'],chosen=choice,inner_mean=mean(best),fallback_mean=mean(control),latest_tuning_label_end=outer['latest_tuning_label_end'],outer_boundary=outer['outer_boundary']))
        if study=='information':matrices['macro_information_blend']=.25*selected+.25*risk+.5*density
        else:
            matrices['macro_'+study+'_supplement']=.25*equal+.25*selected+.5*density
            matrices['macro_'+study+'_replacement']=.5*selected+.5*density
    (output/'selection.json').write_text(json.dumps(audit,indent=2)+'\n')
    finish_research_study(base,matrices,output,plan['primary'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__=='__main__':run_inner_macro_selection()
