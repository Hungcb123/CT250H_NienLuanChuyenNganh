import unittest
import numpy as np
import pandas as pd
import experiment_regime_global as study


class VixTests(unittest.TestCase):
    def test_conservative_lag_and_future_independence(self):
        source=pd.DataFrame({'VIX_ObservationDate':pd.bdate_range('2010-01-01',periods=300),'CLOSE':20+np.sin(np.arange(300)/10)})
        decisions=pd.bdate_range('2010-06-01',periods=100)
        before=study.vix_features(source,decisions)
        self.assertTrue((before.VIX_AvailableDate<=before.Date).all())
        self.assertTrue(((before.Date-before.VIX_ObservationDate).dt.days>=2).all())
        changed=source.copy()
        changed.loc[changed.VIX_ObservationDate>=decisions[50],'CLOSE']*=3
        after=study.vix_features(changed,decisions)
        pd.testing.assert_frame_equal(before.iloc[:51],after.iloc[:51])

    def test_stale_values_do_not_forward_fill_forever(self):
        source=pd.DataFrame({'VIX_ObservationDate':pd.bdate_range('2010-01-01',periods=100),'CLOSE':np.full(100,20.)})
        result=study.vix_features(source,pd.Series([pd.Timestamp('2020-01-01')]))
        self.assertTrue(result.VIX_LogLevel.isna().all())

    def test_snapshot_hash_and_frozen_cohort(self):
        root=study.study.risk.labels.ROOT
        reference=root/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():self.skipTest('Local snapshot missing')
        args=study.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        candidates,index,plan=study.prepare_global(args)
        self.assertEqual(len(candidates),4)
        for _,_,_,frame,job,names in candidates:
            self.assertTrue(np.isfinite(frame[names].to_numpy()).all())
            self.assertEqual(sum(len(b['validation']) for outer in job['folds'] for b in outer['blocks']),1560)
            self.assertTrue((frame.VIX_AvailableDate<=frame.Date).all())
