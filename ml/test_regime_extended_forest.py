import unittest
import numpy as np
import pandas as pd
from experiment_regime_extended_forest import extended_feature_history
import experiment_regime as exp


class ExtendedHistoryTests(unittest.TestCase):
    def test_no_pre_etf_fill_and_targets_stay_on_full_calendar(self):
        dates=pd.bdate_range('2010-01-01',periods=600)
        p=100*np.exp(.0002*np.arange(600)+.03*np.sin(np.arange(600)/7))
        index=pd.DataFrame(dict(Date=dates,Price=p))
        etf=pd.DataFrame(dict(Date=dates[300:],Price=p[300:]/5))
        etf=etf.loc[etf.Date.ne(dates[350])].reset_index(drop=True)
        frame,names=extended_feature_history(index,etf)
        self.assertEqual(len(names),19)
        before=frame.Date<dates[300]
        self.assertTrue(before.any())
        self.assertTrue(frame.loc[before,exp.base.ETF_FEATURE_NAMES].isna().all().all())
        missing=frame.loc[frame.Date.eq(dates[350])].iloc[0]
        self.assertEqual(missing.label_end_date,dates[370])
        self.assertTrue(missing[exp.base.ETF_FEATURE_NAMES].isna().all())
        np.testing.assert_allclose(missing.future_return,p[370]/p[350]-1.)
        self.assertTrue(np.isfinite(frame[exp.base.CLOSE_V1_NAMES+exp.TREND_NAMES]).all().all())

    def test_later_index_or_etf_values_cannot_change_mature_prefix(self):
        dates=pd.bdate_range('2010-01-01',periods=600)
        p=100*np.exp(.0002*np.arange(600)+.03*np.sin(np.arange(600)/7))
        index=pd.DataFrame(dict(Date=dates,Price=p));etf=pd.DataFrame(dict(Date=dates[300:],Price=p[300:]/5))
        original,_=extended_feature_history(index,etf)
        changed=index.copy();changed.loc[560:,'Price']*=2
        other=etf.copy();other.loc[other.Date>=dates[560],'Price']*=3
        rebuilt,_=extended_feature_history(changed,other)
        pd.testing.assert_frame_equal(original.loc[original.Date<dates[540]].reset_index(drop=True),
            rebuilt.loc[rebuilt.Date<dates[540]].reset_index(drop=True))


if __name__=='__main__':unittest.main()
