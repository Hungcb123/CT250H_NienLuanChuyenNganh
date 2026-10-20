import tempfile
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

import experiment_regime_multiclass_reuse as study


class ReuseTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2020-01-01',periods=40)
        rows=pd.DataFrame(dict(Date=dates[:20],label_end_date=dates[20:40],label=np.arange(20)%3,
            future_return=0.,argmax=0,majority=1,outer_fold=1,refit_block=1,causal_macro_weights=0))
        rows[study.study.PROB_COLUMNS]=[.6,.3,.1]
        return rows

    def test_equal_view_combination_is_fixed_and_unlabelled_history_stays_unused(self):
        first=self.fixture();second=first.copy();second[study.study.PROB_COLUMNS]=[.1,.2,.7]
        combined,audit=study.equal_views(first,second)
        np.testing.assert_allclose(combined[study.study.PROB_COLUMNS],np.tile([.35,.25,.4],(20,1)))
        self.assertTrue((combined.argmax==2).all())
        self.assertTrue((combined.causal_macro_weights==2).all())
        self.assertEqual(audit[0]['history']['n'],0)

    def test_equal_view_rejects_a_different_outcome_or_date_cohort(self):
        first=self.fixture();second=first.copy();second.loc[0,'label']=2
        with self.assertRaises(AssertionError):study.equal_views(first,second)

    def test_legacy_parity_requires_exact_predictions(self):
        rows=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'legacy.csv'
            rows.assign(prediction=rows.argmax).to_csv(path,index=False)
            result=study.parity_check(rows,path)
            self.assertTrue(result['passed']);self.assertEqual(result['prediction_matches'],20)
            changed=rows.copy();changed.loc[0,'argmax']=2
            with self.assertRaises(AssertionError):study.parity_check(changed,path)


if __name__=='__main__':unittest.main()
