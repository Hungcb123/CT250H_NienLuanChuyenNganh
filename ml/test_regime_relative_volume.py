import unittest
import numpy as np
import pandas as pd
from experiment_regime_relative_volume import relative_volume_consensus,relative_volume_features,VOLUME_NAMES


class RelativeVolumeTests(unittest.TestCase):
    def test_unique_group_accepts_bounded_rounding_rejects_conflict_and_chain(self):
        volume,voters=relative_volume_consensus({'a':1000000.,'b':1000050.,'c':1100000.})
        self.assertEqual(volume,1000025.)
        self.assertEqual(voters,'a+b')
        for values in [{'a':1000000.},{'a':1000000.,'b':1100000.},
                       {'a':1000000.,'b':1000090.,'c':1000180.}, {'a':0.,'b':np.nan}]:
            value,voters=relative_volume_consensus(values)
            self.assertTrue(np.isnan(value));self.assertEqual(voters,'')

    def test_future_invariance_and_missing_full_calendar_lag(self):
        dates=pd.bdate_range('2010-01-01',periods=200)
        volume=1e6*(1+.2*np.sin(np.arange(200)/11))
        panel=pd.DataFrame(dict(Date=dates,a=volume,b=volume+30,c=volume*1.1))
        panel.loc[:49,'b']=np.nan;panel.loc[100,['a','b','c']]=np.nan
        before=relative_volume_features(panel)
        self.assertTrue(before.loc[:49,'RelativeConsensusVolume'].isna().all())
        self.assertTrue(before.loc[:49,VOLUME_NAMES].isna().all().all())
        self.assertTrue(np.isnan(before.RelativeVolumeLogChange5.iloc[105]))
        self.assertTrue(np.isnan(before.RelativeConsensusVolume.iloc[100]))
        self.assertTrue(np.isfinite(before.RelativeVolumeLogRatio60.iloc[90]))
        later=panel.copy();later.loc[150:,['a','b','c']]*=2.
        after=relative_volume_features(later)
        pd.testing.assert_frame_equal(before.iloc[:150],after.iloc[:150])
        with self.assertRaises(ValueError):relative_volume_features(panel.iloc[::-1])


if __name__=='__main__':unittest.main()
