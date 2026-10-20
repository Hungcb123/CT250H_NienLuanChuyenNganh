import unittest
import numpy as np
import pandas as pd
import experiment_regime_fresh as study
from test_regime_risk import fixture


class FreshTests(unittest.TestCase):
    def test_all_labels_mature_and_calibration_shortens_age(self):
        frame=fixture(1500)
        frozen=np.arange(1000,1200)
        blocks=study.make_blocks(frame,frozen,pd.DatetimeIndex(frame.Date),'3y',20,20)
        np.testing.assert_array_equal(np.concatenate([b['validation'] for b in blocks]),frozen)
        for block in blocks:
            core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
            self.assertEqual(len(cal),20)
            self.assertLess(core.label_end_date.max(),cal.Date.min())
            self.assertLess(cal.label_end_date.max(),valid.Date.min())
            self.assertLess((valid.Date.min()-core.Date.max()).days,100)

    def test_snapshot_preserves_exact_dates(self):
        reference=study.study.risk.labels.ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():self.skipTest('Snapshot missing')
        args=study.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        candidates,index,plan=study.prepare(args)
        self.assertEqual(len(candidates),4)
        for _,frame,job,names in candidates:
            dates=np.concatenate([frame.Date.iloc[b['validation']].to_numpy() for outer in job['folds'] for b in outer['blocks']])
            self.assertEqual(len(dates),1560)
            self.assertEqual(len(np.unique(dates)),1560)
