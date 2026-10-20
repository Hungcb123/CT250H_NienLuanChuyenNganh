import unittest
import numpy as np
import experiment_regime_fresh_followup as followup


class FollowupTests(unittest.TestCase):
    def test_preflight_retains_dates_and_calibration_lengths(self):
        reference=followup.fresh.study.risk.labels.ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():self.skipTest('Snapshot missing')
        args=followup.fresh.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        candidates,index,plan=followup.prepare(args)
        self.assertEqual(len(candidates),4)
        for (name,frame,job,names),(_,window,ncal,refit) in zip(candidates,followup.CONFIGS):
            dates=[]
            for outer in job['folds']:
                for block in outer['blocks']:
                    core,cal,valid=[frame.iloc[block[k]] for k in ['core','calibration','validation']]
                    self.assertEqual(len(cal),ncal)
                    self.assertLess(core.label_end_date.max(),cal.Date.min())
                    self.assertLess(cal.label_end_date.max(),valid.Date.min())
                    dates.extend(valid.Date)
            self.assertEqual(len(dates),1560)
            self.assertEqual(len(np.unique(dates)),1560)
