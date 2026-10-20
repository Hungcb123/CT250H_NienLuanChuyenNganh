"""Audit unchanged raw-price target, inner selection, source hashes and metrics."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, matthews_corrcoef, precision_recall_fscore_support

ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
market=pd.read_csv(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv',parse_dates=['Date'])
logp=np.log(market.Close);sigma=logp.diff().rolling(20,min_periods=20).std(ddof=1)*np.sqrt(20)
forward=logp.shift(-20)-logp
book=pd.DataFrame(dict(Date=market.Date,label_end_date=market.Date.shift(-20),label=np.where(forward<-sigma,0,np.where(forward>sigma,2,1))))
directories=[ROOT/'reports/regime_inner_forest/20261019T070804_899122Z',ROOT/'reports/regime_magnitude_forest/20261019T070928_701705Z',ROOT/'reports/regime_soft_margin/20261019T071331_554457Z']
sources={};metrics=[];audits=[]
for directory in directories:
    assert (directory/'comparison.csv').exists(), 'Study still incomplete: '+str(directory)
    plan=json.loads((directory/'plan.json').read_text())
    assert plan['labels']['20']['policy']=='vol_1sigma'
    for path,expected in plan['source_hashes'].items():
        actual=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert actual==expected,path;sources[path]=actual
    for item in pd.read_csv(directory/'comparison.csv').to_dict('records'):
        path=directory/(item['candidate']+'_predictions.csv')
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date'])
        assert len(rows)==1560 and rows.Date.is_monotonic_increasing and not rows.Date.duplicated().any()
        assert rows.groupby('outer_fold').size().tolist()==[390]*4
        truth=rows[['Date']].merge(book,on='Date',validate='one_to_one')
        for key in ['label','label_end_date']:np.testing.assert_array_equal(rows[key],truth[key])
        score=rows[['p_bear','p_side','p_bull']].to_numpy()
        np.testing.assert_array_equal(rows.prediction,score.argmax(axis=1))
        np.testing.assert_allclose(score.sum(axis=1),1.,atol=1e-12)
        assert np.isfinite(score).all() and (score>=0).all()
        groups=[g for _,g in rows.groupby('outer_fold')]
        f1=[f1_score(g.label,g.prediction,labels=[0,1,2],average='macro',zero_division=0) for g in groups]
        perclass=np.mean([precision_recall_fscore_support(g.label,g.prediction,labels=[0,1,2],zero_division=0)[2] for g in groups],axis=0)
        computed=dict(mean_f1=float(np.mean(f1)),worst_f1=float(min(f1)),mean_mcc=float(np.mean([matthews_corrcoef(g.label,g.prediction) for g in groups])))
        computed.update({c+'_mean_f1':float(v) for c,v in zip(['bear','side','bull'],perclass)})
        for key,value in computed.items():np.testing.assert_allclose(item[key],value,rtol=0,atol=1e-15)
        metrics.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fold_f1=f1,**computed))
    timing=json.loads((directory/'timing_audit.json').read_text())
    for item in timing:
        assert pd.Timestamp(item['latest_label_end'])<pd.Timestamp(item['prediction_start'])
    audits.append(dict(study=directory.name,parent=directory.parent.name,strictly_mature_fit_boundaries=len(timing)))

# Independently use pandas EMA and sklearn confusion metrics to recover every
# archived inner candidate and final coefficient choice, including fallback.
directory=directories[0];selection=json.loads((directory/'selection.json').read_text());replays=[]
positions=pd.Series(np.arange(len(market)),index=market.Date)
for outer in selection:
    periods=[]
    assert pd.Timestamp(outer['latest_inner_label_end'])<pd.Timestamp(outer['outer_boundary'])
    for i in [1,2,3]:
        rows=pd.read_csv(directory/f'outer{outer["fold"]}_inner{i}_forecasts.csv',parse_dates=['Date','label_end_date'])
        truth=rows[['Date']].merge(book,on='Date',validate='one_to_one')
        for field in ['label','label_end_date']:np.testing.assert_array_equal(rows[field],truth[field])
        assert rows.label_end_date.max()<pd.Timestamp(outer['outer_boundary'])
        c=rows[['c_bear','c_side','c_bull']].to_numpy();d=rows[['d_bear','d_side','d_bull']].to_numpy();f=rows[['f_bear','f_side','f_bull']].to_numpy()
        locations=positions.loc[rows.Date].to_numpy();cuts=np.r_[0,np.flatnonzero(np.diff(locations)!=1)+1,len(rows)]
        values=[]
        for candidate in outer['candidates']:
            share=candidate['share'];w,tc,td=candidate['coefficients']
            cc=c**(1/tc);cc/=cc.sum(axis=1,keepdims=True)
            dd=((1-share)*d+share*f)**(1/td);dd/=dd.sum(axis=1,keepdims=True)
            raw=(1-w)*cc+w*dd;ema=np.empty_like(raw)
            for a,b in zip(cuts[:-1],cuts[1:]):ema[a:b]=pd.DataFrame(raw[a:b]).ewm(alpha=1/3,adjust=False).mean()
            values.append(precision_recall_fscore_support(rows.label,((raw+ema)/2).argmax(axis=1),labels=[0,1,2],zero_division=0)[2])
        periods.append(values)
    classes=np.asarray(periods);macro=classes.mean(axis=2);mean=macro.mean(axis=0)
    robust=.5*mean+.25*macro.min(axis=0)+.25*classes.mean(axis=0)[:,[0,2]].min(axis=1)
    aw,ac,ad=outer['anchor'];penalty=[];default=None
    for j,candidate in enumerate(outer['candidates']):
        share=candidate['share'];w,tc,td=candidate['coefficients']
        penalty.append(.005*((2*(share-.5))**2+(2*(w-aw))**2+np.log(tc/ac)**2+np.log(td/ad)**2))
        if share==.5 and candidate['coefficients']==outer['anchor']:default=j
    assert default is not None
    for rule,values in [('macro',mean),('robust',robust)]:
        np.testing.assert_allclose(values,[v['mean_f1' if rule=='macro' else 'robust'] for v in outer['candidates']],rtol=0,atol=1e-14)
        adjusted=values-np.asarray(penalty);best=int(adjusted.argmax())
        chosen=best if adjusted[best]>=adjusted[default]+.005 else default
        assert chosen==outer['chosen'][rule]
    replays.append(dict(fold=outer['fold'],candidates=len(outer['candidates']),chosen=outer['chosen'],strict_inner_maturity=True))

# Independently reconstruct OUTER score mixing and EMA with pandas, including
# fold-specific anchors. Source reader only supplies previously audited inputs.
from regime_component_archive import load_seed_components
base,c,d,calendar,_=load_seed_components(directories[1]/'magnitude_shrink_predictions.csv')
forest=ROOT/'reports/regime_empirical_forest/20261019T070202_443313Z'
anchors=json.loads((ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z/selection.json').read_text())
anchor_grid=json.loads((ROOT/'reports/regime_matched_calibration/20261019T064830_252658Z/plan.json').read_text())['grid']
rf=np.mean([pd.read_csv(forest/f'RandomForest_{t}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for t in ['raw','normalized']],axis=0)
mag=np.mean([pd.read_csv(directories[1]/f'{t}_scores.csv')[['p_bear','p_side','p_bull']].to_numpy() for t in ['raw','normalized']],axis=0)
soft=pd.read_csv(directories[2]/'soft_scores.csv')[['p_bear','p_side','p_bull']].to_numpy()
outer_specs=[]
for name in ['incumbent','joint_macro','joint_robust']:
    specs=[]
    for outer in selection:
        if name=='incumbent':coeff=outer['anchor'];den=.5*d+.5*rf
        else:
            item=outer['candidates'][outer['chosen'][name.removeprefix('joint_')]]
            share=item['share'];coeff=item['coefficients'];den=(1-share)*d+share*rf
        specs.append((outer['fold'],coeff,den))
    outer_specs.append((directories[0],name,specs))
for directory,definitions in [(directories[1],{'incumbent':.5*d+.5*rf,'magnitude_shrink':.5*d+.25*rf+.25*mag,'magnitude_replace':.5*d+.5*mag}),
    (directories[2],{'incumbent':.5*d+.25*rf+.25*mag,'soft_margin_shrink':.75*(.5*d+.25*rf+.25*mag)+.25*soft,'soft_margin_replace':soft})]:
    for name,den in definitions.items():
        outer_specs.append((directory,name,[(o['fold'],anchor_grid[o['chosen']['robust']],den) for o in anchors]))
locations=positions.loc[base.Date].to_numpy();cuts=np.r_[0,np.flatnonzero(np.diff(locations)!=1)+1,len(base)]
rebuilt={};outer_parity=[]
for directory,name,specs in outer_specs:
    raw=np.empty_like(c)
    for fold,(w,tc,td),den in specs:
        mask=base.outer_fold.eq(fold).to_numpy()
        cc=c[mask]**(1/tc);cc/=cc.sum(axis=1,keepdims=True)
        dd=den[mask]**(1/td);dd/=dd.sum(axis=1,keepdims=True)
        raw[mask]=(1-w)*cc+w*dd
    ema=np.empty_like(raw)
    for a,b in zip(cuts[:-1],cuts[1:]):ema[a:b]=pd.DataFrame(raw[a:b]).ewm(alpha=1/3,adjust=False).mean()
    score=(raw+ema)/2
    expected=pd.read_csv(directory/(name+'_predictions.csv'))[['p_bear','p_side','p_bull']].to_numpy()
    np.testing.assert_allclose(score,expected,rtol=0,atol=1e-12)
    rebuilt[(directory,name)]=score
    outer_parity.append(dict(study=directory.parent.name,candidate=name,max_score_error=float(np.abs(score-expected).max())))
score=(rebuilt[(directories[0],'incumbent')]+rebuilt[(directories[0],'joint_robust')])/2
expected=pd.read_csv(directories[0]/'joint_shrink_predictions.csv')[['p_bear','p_side','p_bull']].to_numpy()
np.testing.assert_allclose(score,expected,rtol=0,atol=1e-12)
outer_parity.append(dict(study=directories[0].parent.name,candidate='joint_shrink',max_score_error=float(np.abs(score-expected).max())))

result=dict(role='Independent implementation audit of historical DEVELOPMENT, not independent data validation',
    forecast_files=metrics,source_hashes_verified=len(sources),timing_audits=audits,selection_replay=replays,
    independent_outer_score_parity=outer_parity,
    caveat='Same frozen dynamic target, 1560 outer dates. Repeated research exposure remains; no test or production acceptance.')
(OUT/'independent_metric_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(files=len(metrics),source_hashes=len(sources),timing_audits=audits,selection_replay=replays,outer_score_parity=outer_parity),indent=2))
