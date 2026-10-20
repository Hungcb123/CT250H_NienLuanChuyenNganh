"""Matched63 purged-inner empirical forest/quantile fusion selection.

Research on the frozen dynamic-label cohort, with no outer coefficient search.
Reuse archived inner classifier/quantile forecasts; fit forests only on mature
rows preceding each original inner refit. Preserve the 51.21% reference archive.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import precision_recall_fscore_support

import experiment_regime as exp
import experiment_regime_labels as labels
import experiment_regime_return_distribution as density
from experiment_regime_empirical_forest import empirical_leaf_mass, CALIBRATION
from experiment_regime_forecast_smoothing import causal_forecast_ema
from experiment_regime_matched_calibration import fused_scores
from experiment_regime_temporal_fusion import GRID
from regime_component_archive import load_seed_components
from regime_research_evaluation import finish_research_study

ROOT = Path(__file__).resolve().parent
FOREST = ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
SHARES = [0., .25, .5, .75, 1.]


def select_inner_forest_mixture(periods, calendar, anchor):
    """Select a complete smoothed fusion using only the supplied inner periods."""
    candidates = [(share, coefficients) for share in SHARES for coefficients in GRID]
    default = candidates.index((.5, tuple(anchor)))
    per_period = []
    for rows in periods:
        c = rows[['c_bear','c_side','c_bull']].to_numpy()
        d = rows[['d_bear','d_side','d_bull']].to_numpy()
        f = rows[['f_bear','f_side','f_bull']].to_numpy()
        values = []
        for share, coefficients in candidates:
            raw = fused_scores(c, (1-share)*d+share*f, coefficients)
            score = .5*raw+.5*causal_forecast_ema(rows.Date, raw, calendar, 5)
            values.append(precision_recall_fscore_support(rows.label, score.argmax(axis=1),
                labels=[0,1,2], zero_division=0)[2])
        per_period.append(values)
    classes = np.asarray(per_period)
    macro = classes.mean(axis=2)
    mean = macro.mean(axis=0)
    robust = .5*mean+.25*macro.min(axis=0)+.25*classes.mean(axis=0)[:,[0,2]].min(axis=1)
    aw, ac, ad = anchor
    penalty = np.array([.005*((2*(share-.5))**2+(2*(w-aw))**2
        +np.log(tc/ac)**2+np.log(td/ad)**2) for share,(w,tc,td) in candidates])
    choices = {}
    for rule, values in [('macro', mean), ('robust', robust)]:
        adjusted = values-penalty
        best = int(adjusted.argmax())
        choices[rule] = best if adjusted[best] >= adjusted[default]+.005 else default
    return choices, [dict(share=share, coefficients=coefficients, mean_f1=float(mean[i]),
        robust=float(robust[i]), penalty=float(penalty[i])) for i,(share,coefficients) in enumerate(candidates)]


def run_inner_forest_calibration(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-report',type=Path,default=ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json')
    parser.add_argument('--control-dir',type=Path,default=ROOT/'reports/regime_experiments/20261017T141838_654956Z')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--output-dir',type=Path)
    args = parser.parse_args(argv)
    base, outer_c, outer_d, calendar, paths = load_seed_components(FOREST/'RandomForest_shrink_predictions.csv')
    parent = json.loads((FOREST/'plan.json').read_text())
    frame, jobs, _, plan = density.prepare_return_distribution(args)
    market, _ = exp.base.load_market_data(args.data_dir/'VNINDEX.csv')
    frame = labels.relabel_cohort(frame, labels.build_label_book(market), 'vol_1sigma')
    selection = json.loads((CALIBRATION/'selection.json').read_text())
    fparts = []
    for target in ['raw','normalized']:
        path = FOREST/f'RandomForest_{target}_scores.csv'; paths.append(path)
        rows = pd.read_csv(path, parse_dates=['Date','label_end_date'])
        for field in ['Date','label_end_date','label','outer_fold']:
            np.testing.assert_array_equal(base[field], rows[field])
        fparts.append(rows[['p_bear','p_side','p_bull']].to_numpy())
    outer_f = np.mean(fparts, axis=0)
    for outer in selection:
        for inner in [1,2,3]:
            paths.append(CALIBRATION/f'outer{outer["fold"]}_inner{inner}_forecasts.csv')
    paths += [Path(__file__), ROOT/'experiment_regime_empirical_forest.py',
        ROOT/'experiment_regime_forecast_smoothing.py', ROOT/'experiment_regime_matched_calibration.py',
        ROOT/'experiment_regime_temporal_fusion.py', ROOT/'regime_component_archive.py',
        ROOT/'regime_research_evaluation.py', CALIBRATION/'selection.json']
    plan.update(mode='matched63_inner_forest_complete_fusion_DEVELOPMENT', optuna=None,
        reference_labels=plan['labels'], labels={'20':dict(policy='vol_1sigma',k=1.,lookback=20,horizon=20,ddof=1,equality='sideway')},
        source_hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        forest_parameters=parent['parameters'], shares=SHARES, grid=GRID,
        selection='Mean inner macro or robustness(.5 mean+.25 worst+.25 weaker directional F1) of complete current/EMA5 score. Quadratic .005 penalty around pre-existing(.5 forest share, robust anchor). Switch only penalized gain>=.005.',
        inner_fit='Reuse matched classifier/quantile inner forecasts; train empirical raw/normalized RF at each same63-market-session block with expanding mature data. Every inner label_end_date precedes outer boundary.',
        primary='joint_robust: inner robust joint coefficient/share selection; secondary half incumbent/joint_robust; macro diagnostic.',
        caveat='Outer history repeatedly inspected, information group/hyperparams fixed at outer decision and reused inside inner scoring; no independent nested-HPO, probability calibration or deployment claim.')
    output = args.output_dir or ROOT/'reports/regime_inner_forest'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('Output: '+str(output.resolve()),flush=True)
    names = jobs['expanding']['names']; timings = []; chosen = []
    for outer in selection:
        periods = []
        for inner in [1,2,3]:
            saved = pd.read_csv(CALIBRATION/f'outer{outer["fold"]}_inner{inner}_forecasts.csv',parse_dates=['Date','label_end_date'])
            if saved.label_end_date.max() >= pd.Timestamp(outer['outer_boundary']):
                raise ValueError('Inner selection used an outer/future outcome')
            records = []
            for number, block in saved.groupby('refit_block',sort=True):
                valid = block[['Date']].merge(frame,on='Date',how='left',validate='one_to_one',sort=False)
                np.testing.assert_array_equal(block.label,valid.label)
                boundary = valid.Date.min()
                train = frame.iloc[exp.training_indices(frame,boundary,'expanding')]
                if train.label_end_date.max() >= boundary:
                    raise ValueError('Unmatured inner forest target')
                scores = []
                for normalized in [False,True]:
                    target = train.future_log_return.to_numpy(); sigma = valid.horizon_sigma.to_numpy()
                    if normalized:
                        target = target/train.horizon_sigma.to_numpy(); sigma = np.ones(len(valid))
                    model = RandomForestRegressor(**parent['parameters']).fit(train[names].to_numpy(dtype=np.float32),target)
                    mass = empirical_leaf_mass(model.apply(train[names].to_numpy(dtype=np.float32)),
                        model.apply(valid[names].to_numpy(dtype=np.float32)),target,-sigma,sigma)
                    prior = np.bincount(train.label,minlength=3)/len(train)
                    score = mass/prior; score /= score.sum(axis=1,keepdims=True); scores.append(score)
                rows = block.copy(); rows[['f_bear','f_side','f_bull']] = np.mean(scores,axis=0); records.append(rows)
                timings.append(dict(outer_fold=outer['fold'],inner_fold=inner,refit_block=int(number),n_train=len(train),
                    latest_label_end=str(train.label_end_date.max().date()),prediction_start=str(boundary.date())))
            rows = pd.concat(records,ignore_index=True)
            rows.to_csv(output/f'outer{outer["fold"]}_inner{inner}_forecasts.csv',index=False); periods.append(rows)
            print(f'Outer{outer["fold"]} inner{inner} forest complete',flush=True)
        anchor = GRID[outer['chosen']['robust']]
        choices, candidates = select_inner_forest_mixture(periods,calendar.Date,anchor)
        chosen.append(dict(fold=outer['fold'],outer_boundary=outer['outer_boundary'],
            latest_inner_label_end=str(max(r.label_end_date.max() for r in periods).date()),anchor=anchor,chosen=choices,candidates=candidates))
        (output/'selection.json').write_text(json.dumps(chosen,indent=2)+'\n')
        (output/'timing_audit.json').write_text(json.dumps(timings,indent=2)+'\n')
        print('Outer '+str(outer['fold'])+' choices '+str({k:candidates[v] for k,v in choices.items()}),flush=True)
    raw = {rule:np.empty_like(outer_c) for rule in ['macro','robust']}; default = np.empty_like(outer_c)
    for outer in chosen:
        mask = base.outer_fold.eq(outer['fold']).to_numpy()
        default[mask] = fused_scores(outer_c[mask],.5*outer_d[mask]+.5*outer_f[mask],outer['anchor'])
        for rule,choice in outer['chosen'].items():
            item = outer['candidates'][choice]; share = item['share']
            raw[rule][mask] = fused_scores(outer_c[mask],(1-share)*outer_d[mask]+share*outer_f[mask],item['coefficients'])
    incumbent = .5*default+.5*causal_forecast_ema(base.Date,default,calendar.Date,5)
    np.testing.assert_allclose(incumbent,base[['p_bear','p_side','p_bull']],atol=1e-12,rtol=1e-12)
    matrices = dict(incumbent=incumbent)
    for rule,values in raw.items():
        matrices['joint_'+rule] = .5*values+.5*causal_forecast_ema(base.Date,values,calendar.Date,5)
    matrices['joint_shrink'] = .5*incumbent+.5*matrices['joint_robust']
    finish_research_study(base,matrices,output,['joint_robust','joint_shrink'])
    print('Done. No deployment. '+str(output.resolve()),flush=True)
    return output


if __name__ == '__main__':
    run_inner_forest_calibration()
