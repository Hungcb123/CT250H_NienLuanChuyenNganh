import unittest
import numpy as np
import pandas as pd
import experiment_regime_history as history


class HistoryProtocolTests(unittest.TestCase):
    def test_close_only_history_retains_exact_frozen_dates_and_purging(self):
        root = history.study.risk.labels.ROOT
        reference = root / 'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():
            self.skipTest('Local snapshot missing')
        args = history.study.risk.labels.parse_args(['--reference-report', str(reference), '--audit-only'])
        candidates, _, plan = history.prepare_history(args)
        old, _, _ = history.study.prepare_candidates(args)
        expected = pd.DatetimeIndex(np.concatenate([old[0][3].Date.iloc[b['validation']].to_numpy() for outer in old[0][4]['folds'] for b in outer['blocks']]))
        self.assertLess(pd.Timestamp(plan['cohort_start']), pd.Timestamp('2012-01-01'))
        for _, policy, _, frame, job, names in candidates:
            dates = []
            self.assertFalse(any(name.startswith('ETF_') for name in names))
            for outer in job['folds']:
                for block in outer['blocks']:
                    core, calibration, validation = [frame.iloc[block[key]] for key in ['core','calibration','validation']]
                    self.assertLess(core.label_end_date.max(), calibration.Date.min())
                    self.assertLess(calibration.label_end_date.max(), validation.Date.min())
                    self.assertEqual(core.label.nunique(), 2 if policy == 'binary_5pct' else 3)
                    dates.extend(validation.Date)
            self.assertTrue(pd.DatetimeIndex(dates).equals(expected))
