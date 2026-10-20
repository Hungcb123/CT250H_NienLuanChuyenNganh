"""Actual estimator interface and validation-outcome exclusion checks."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_dynamic_families as study


class DynamicFamilyTests(unittest.TestCase):
    def test_non_tree_estimators_ignore_validation_outcomes_and_preserve_class_order(self):
        dates=pd.bdate_range('2020-01-01',periods=400)
        x=np.linspace(-3,3,240)
        train=pd.DataFrame({'Date':dates[:240],'label_end_date':dates[20:260],
            'x':x,'label':np.digitize(x,[-1,1])})
        valid=pd.DataFrame({'Date':dates[300:303],'x':[-2.,0.,2.],'label':[99,99,99]})
        for family in ['SVC_RBF','MLP','ShrinkageLDA','KNN','HistGBM','CatBoost']:
            with self.subTest(family=family):
                scores=study.fit_dynamic_family(train,valid,['x'],family)
                other=study.fit_dynamic_family(train,valid.assign(label=-99),['x'],family)
                self.assertEqual(scores.shape,(3,3))
                np.testing.assert_allclose(scores,other,atol=1e-10,rtol=1e-10)
                np.testing.assert_array_equal(scores.argmax(axis=1),[0,1,2])

    def test_training_outcome_on_boundary_is_rejected(self):
        train=pd.DataFrame({'label_end_date':[pd.Timestamp('2020-02-01')]})
        valid=pd.DataFrame({'Date':[pd.Timestamp('2020-02-01')]})
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.fit_dynamic_family(train,valid,[],'CatBoost')


if __name__=='__main__':unittest.main()
