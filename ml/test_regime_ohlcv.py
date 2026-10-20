import unittest
import numpy as np
import pandas as pd
import experiment_regime_ohlcv as study


class ConsensusTests(unittest.TestCase):
    def test_consensus_rejects_disagreement_single_source_and_chain(self):
        value, voters = study.consensus_value({'a': 100, 'b': 100.005, 'c': 110}, .011)
        self.assertAlmostEqual(value, 100.0025)
        self.assertEqual(voters, 'a+b')
        for row in [{'a': 100}, {'a':100, 'b':110}, {'a':100,'b':100.01,'c':100.02}]:
            self.assertTrue(np.isnan(study.consensus_value(row, .011)[0]))

    def test_features_causal_and_missing_not_backfilled(self):
        n=200
        price=100*np.exp(np.sin(np.arange(n)/10)*.1)
        frame=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=n),Price=price,Open=price*.999,High=price*1.02,Low=price*.98,Volume=1e6+np.arange(n)*100))
        frame.loc[:50,['Open','High','Low','Volume']]=np.nan
        before=study.ohlcv_features(frame)
        self.assertTrue(before[study.OHLCV_NAMES].iloc[:51].isna().all().all())
        frame.loc[150:,['Open','High','Low','Volume']]*=2
        after=study.ohlcv_features(frame)
        pd.testing.assert_frame_equal(before.iloc[:150],after.iloc[:150])

    def test_imputation_statistics_fit_only_training(self):
        X=np.array([[1,np.nan],[2,np.nan],[3,np.nan],[4,np.nan]])
        model=study.study.make_model('logistic_missing')
        model.fit(X,np.array([0,1,0,1]))
        imputer=model.named_steps['simpleimputer']
        self.assertEqual(imputer.statistics_[0],2.5)
        predictions=model.predict_proba(np.array([[999,500],[np.nan,1000]]))
        self.assertTrue(np.isfinite(predictions).all())
        self.assertEqual(imputer.statistics_[0],2.5)

    def test_real_snapshot_consensus_and_frozen_dates(self):
        root=study.study.risk.labels.ROOT
        reference=root/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():self.skipTest('Snapshot missing')
        args=study.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        candidates,index,plan,consensus=study.prepare_ohlcv(args)
        self.assertEqual(len(consensus),len(index))
        np.testing.assert_array_equal(consensus.Price,index.Price)
        for col in ['Open','High','Low','Volume']:
            self.assertTrue(consensus.loc[consensus[col].notna(),col+'_sources'].str.contains('+',regex=False).all())
        for candidate in candidates:
            frame,job=candidate[3:5]
            dates=np.concatenate([frame.Date.iloc[b['validation']].to_numpy() for outer in job['folds'] for b in outer['blocks']])
            self.assertEqual(len(dates),1560)
            self.assertEqual(len(np.unique(dates)),1560)
