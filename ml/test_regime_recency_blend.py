import unittest
import numpy as np
import pandas as pd
import experiment_regime_recency_blend as study


class RecencyBlendTests(unittest.TestCase):
    def test_aligned_blend_and_future_score_invariance(self):
        n=200
        short=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=n),label_end_date=pd.bdate_range('2020-02-01',periods=n),
                                outer_fold=1,refit_block=1,common_bear=False,future_return=.01,risk_score=np.arange(n,dtype=float),threshold=100.))
        long=short.copy();long.risk_score=long.risk_score/2
        combined=study.blend(short,long)
        np.testing.assert_allclose(combined.risk_score,(2*short.risk_score+long.risk_score)/3)
        result=study.online.online_records(combined,120)
        changed=combined.copy();changed.loc[150:,'risk_score']=10000
        later=study.online.online_records(changed,120)
        np.testing.assert_array_equal(result.threshold.iloc[:151],later.threshold.iloc[:151])
        self.assertEqual(len(result),n)

    def test_date_mismatch_rejected(self):
        frame=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=2)))
        other=frame.copy();other.Date+=pd.Timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'aligned'):
            study.blend(frame,other)
