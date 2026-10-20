"""Completed-close feature inputs, retaining the current UNLABELLED sessions.

No forward return/label is computed here. Historical frozen source loaders are
reused with their original missing-value and availability rules.
"""
from pathlib import Path

import numpy as np

import experiment_regime as exp
import experiment_regime_information as information
from experiment_regime_directional import directional_features


def completed_shock_features(data_dir):
    data_dir = Path(data_dir)
    index, index_audit = exp.base.load_market_data(data_dir/'VNINDEX.csv')
    etf, etf_audit = exp.base.load_market_data(data_dir/'E1VFVN30.csv')
    frame, _ = exp.base.build_feature_matrix(index, etf, 'close-etf')
    long = exp.long_features(index)
    for name in long:
        frame[name] = long[name]
    consensus, consensus_audit = information.ohlcv.load_consensus(data_dir, index)
    bars = information.ohlcv.ohlcv_features(consensus)
    vix, vix_audit = information.global_risk.load_vix()
    vix_fields = information.global_risk.vix_features(vix, index.Date)
    stretch = information.extra.reversal_features(index).Stretch20
    vix_fields['VIX_StretchInteraction'] = stretch*(vix_fields.VIX_LogLevel-np.log(20.))
    groups, group_audit = information.indices.load_indices()
    group_fields = information.indices.index_features(index, groups)
    for book in [bars, vix_fields, group_fields, directional_features(index)]:
        collisions = (set(frame) & set(book))-{'Date'}
        if collisions:
            raise ValueError('Feature book collision: '+str(collisions))
        frame = frame.merge(book, on='Date', how='left', validate='one_to_one', sort=False)
    frame['horizon_sigma'] = np.log(index.Price.astype(float)).diff().rolling(20, min_periods=20).std(ddof=1)*np.sqrt(20)
    np.testing.assert_array_equal(frame.Date, index.Date)
    known = frame.VIX_AvailableDate.notna()
    if not (frame.loc[known, 'VIX_AvailableDate'] <= frame.loc[known, 'Date']).all():
        raise ValueError('VIX not available at completed session')
    return frame, dict(index=index_audit, etf=etf_audit, consensus=consensus_audit,
                       vix=vix_audit, group_indices=group_audit)
