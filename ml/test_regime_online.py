import unittest
import numpy as np
import pandas as pd
import experiment_regime_online as study


class OnlineTests(unittest.TestCase):
    def test_future_and_current_score_excluded_from_threshold(self):
        n=200
        frame=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=n),risk_score=np.arange(n,dtype=float),threshold=100.,policy='3y_standardized'))
        before=study.online_records(frame,60)
        changed=frame.copy();changed.loc[100:,'risk_score']=10000.
        after=study.online_records(changed,60)
        np.testing.assert_array_equal(before.threshold.iloc[:101],after.threshold.iloc[:101])
        self.assertEqual(before.threshold.iloc[100],np.quantile(frame.risk_score.iloc[40:100],.9,method='higher'))

    def test_warmup_keeps_frozen_cohort_and_original_causal_threshold(self):
        n=100
        frame=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=n),risk_score=np.arange(n,dtype=float),threshold=100.,policy='3y_standardized'))
        result=study.online_records(frame,60)
        self.assertEqual(len(result),n)
        self.assertTrue((result.threshold.iloc[:60]==100).all())
        self.assertEqual(result.online_warmup.sum(),60)
