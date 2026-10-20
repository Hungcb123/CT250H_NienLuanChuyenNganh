from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

import experiment_regime_information as study


class InformationTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2020-01-01',periods=10)
        return pd.DataFrame(dict(Date=dates[:4],label_end_date=dates[5:9],label=[0,1,2,1],future_return=[-.06,0.,.06,0.])),dates

    def test_missing_extra_features_never_remove_validation_dates(self):
        frame,dates=self.fixture()
        book=pd.DataFrame(dict(Date=dates[[0,2]],extra=[1.,3.]))
        merged=study.merge_information(frame,book)
        self.assertEqual(len(merged),4)
        np.testing.assert_array_equal(merged.label,frame.label)
        self.assertTrue(merged.extra.iloc[[1,3]].isna().all())

    def test_future_book_row_is_not_filled_backwards(self):
        frame,dates=self.fixture()
        book=pd.DataFrame(dict(Date=dates[[4]],extra=[99.]))
        merged=study.merge_information(frame,book)
        self.assertTrue(merged.extra.isna().all())

    def test_duplicate_source_dates_are_rejected(self):
        frame,dates=self.fixture()
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            study.merge_information(frame,pd.DataFrame(dict(Date=[dates[0],dates[0]],extra=[1.,2.])))

    def test_information_cannot_replace_target_labels(self):
        frame,dates=self.fixture()
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            study.merge_information(frame,pd.DataFrame(dict(Date=dates[:4],label=2)))

    def test_incomplete_tuning_budget_is_rejected_before_ranking(self):
        frame,dates=self.fixture()
        frame['VIX_ObservationDate']=frame.Date-pd.Timedelta(days=2)
        frame['VIX_AvailableDate']=frame.Date
        for name in study.global_risk.VIX_NAMES:frame[name]=1.
        prepared=(frame,[('control',{})],dict(optuna=dict(n_trials=15,timeout_seconds=10)),pd.DataFrame(dict(Date=dates)))
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'prepare_information',return_value=prepared),patch.object(study.exp,'run_candidate',return_value=(dict(inner_tuning=[dict(n_trials=1)]),None)):
            with self.assertRaisesRegex(ValueError,'Unequal trial budget'):
                study.main(['--output-dir',str(Path(tmp)/'out')])


if __name__=='__main__':unittest.main()
