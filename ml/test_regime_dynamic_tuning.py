"""Timing and metric-schema regressions for adaptive-target nested selection."""
import unittest

import numpy as np
import pandas as pd

import experiment_regime_dynamic_tuning as study


class DynamicTuningTests(unittest.TestCase):
    def test_objective_accepts_actual_classifier_metric_schema(self):
        metric = study.exp.base.classification_metrics([0,1,2,0,1,2], [0,1,2,1,1,2], [0,1,2])
        value = study.dynamic_inner_score([metric, metric])
        self.assertTrue(np.isfinite(value))
        self.assertGreater(value, 0.)

    def test_sparse_calendar_is_purged_by_actual_outcome_date(self):
        dates = pd.bdate_range('2010-01-01', periods=380)
        ids = np.arange(300)[np.arange(300)%7 != 0]
        frame = pd.DataFrame({'Date': dates[ids], 'label_end_date': dates[ids+20], 'label': ids%3})
        folds = study.exp.base.purged_folds(frame, 3)
        study.assert_dynamic_inner_timing(frame, folds, dates[-1])
        train, valid = folds[0]
        self.assertLess(frame.label_end_date.iloc[train].max(), frame.Date.iloc[valid].min())
        corrupted = frame.copy()
        corrupted.loc[train[-1], 'label_end_date'] = frame.Date.iloc[valid[0]]
        with self.assertRaisesRegex(ValueError, 'Inner labels overlap'):
            study.assert_dynamic_inner_timing(corrupted, folds, dates[-1])

    def test_outer_boundary_rejects_a_label_maturing_on_that_date(self):
        dates = pd.bdate_range('2010-01-01', periods=300)
        frame = pd.DataFrame({'Date': dates[:240], 'label_end_date': dates[20:260], 'label': np.arange(240)%3})
        folds = study.exp.base.purged_folds(frame, 3)
        with self.assertRaisesRegex(ValueError, 'unavailable outer outcome'):
            study.assert_dynamic_inner_timing(frame, folds, frame.label_end_date.max())


if __name__ == '__main__':
    unittest.main()
