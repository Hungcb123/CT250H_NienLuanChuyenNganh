"""Read the fixed component archives with common target/calendar validation."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PROBS=['p_bear','p_side','p_bull']


def load_seed_components(source=None):
    source=Path(source or ROOT/'reports/regime_temporal_fusion/20261019T063220_032375Z/adaptive_pool_smoothed_predictions.csv')
    base=pd.read_csv(source,parse_dates=['Date','label_end_date']);base['majority']=base.baseline_prediction
    if len(base)!=1560 or base.Date.duplicated().any() or not base.Date.is_monotonic_increasing:raise ValueError('Invalid frozen forecast cohort')
    old=ROOT/'reports/regime_dynamic_experts/20261019T033757_910222Z/vol_1sigma'
    info=ROOT/'reports/regime_dynamic_information/20261019T052057_760569Z'
    seeds=ROOT/'reports/regime_density_seeds/20261019T061537_193740Z'
    paths=[source,source.parent/'plan.json',info/'inner_selection.json',old/'risk_predictions.csv',ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv']
    for directory in [info,seeds,source.parent]:
        path=directory/'plan.json';paths.append(path);plan=json.loads(path.read_text())
        for name,digest in plan['source_hashes'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Archived source changed: '+name)
    def read(path):
        rows=pd.read_csv(path,parse_dates=['Date','label_end_date']);paths.append(path)
        for key in ['Date','label_end_date','label','outer_fold']:np.testing.assert_array_equal(base[key],rows[key])
        np.testing.assert_allclose(base.future_return,rows.future_return,atol=1e-12,rtol=1e-12)
        return rows
    risk=read(old/'risk_predictions.csv');trend=np.empty((len(base),3))
    for choice in json.loads((info/'inner_selection.json').read_text()):
        rows=read(info/(choice['chosen']+'_scores.csv'))
        mask=base.outer_fold.eq(choice['fold']).to_numpy();trend[mask]=rows.loc[mask,PROBS].to_numpy()
    classifier=.5*(trend+risk[PROBS].to_numpy());parts=[]
    for seed in [7,21,42,84,126]:
        for target in ['raw','normalized']:
            path=old/('expanding_'+target+'_mapped_predictions.csv') if seed==42 else seeds/f'seed{seed}_{target}_scores.csv'
            rows=read(path);score=rows[PROBS].to_numpy()
            if seed==42:score=score/rows[['base_bear','base_side','base_bull']].to_numpy();score/=score.sum(axis=1,keepdims=True)
            parts.append(score)
    density=np.mean(parts,axis=0)
    for matrix in [classifier,density]:
        if not np.isfinite(matrix).all() or (matrix<0).any():raise ValueError('Invalid archived scores')
        np.testing.assert_allclose(matrix.sum(axis=1),1.,atol=1e-12)
    index=pd.read_csv(ROOT/'data/research/brokers_2010_20261001_reviewed/VNINDEX.csv',parse_dates=['Date'])
    return base,classifier,density,index,list(dict.fromkeys(paths))
