"""Causality and class-order checks for real fitted specialist heads."""
import unittest

import numpy as np
import pandas as pd

import experiment_regime_directional as study


class DirectionalSpecialistTests(unittest.TestCase):
    def test_future_price_corruption_never_changes_prefix_features(self):
        dates=pd.bdate_range('2020-01-01',periods=180)
        rng=np.random.default_rng(42)
        index=pd.DataFrame({'Date':dates,'Price':100*np.exp(np.cumsum(rng.normal(0,.01,len(dates))))})
        expected=study.directional_features(index).iloc[:120]
        changed=index.copy()
        changed.loc[120:,'Price']*=np.linspace(2,5,60)
        actual=study.directional_features(changed).iloc[:120]
        pd.testing.assert_frame_equal(actual,expected)

    def test_directional_features_do_not_depend_on_price_units(self):
        dates=pd.bdate_range('2020-01-01',periods=160)
        rng=np.random.default_rng(8)
        index=pd.DataFrame({'Date':dates,'Price':100*np.exp(np.cumsum(rng.normal(0,.01,len(dates))))})
        original=study.directional_features(index).drop(columns='Date')
        scaled=study.directional_features(index.assign(Price=index.Price*1000)).drop(columns='Date')
        np.testing.assert_allclose(original,scaled,rtol=1e-9,atol=1e-9,equal_nan=True)

    def test_fitted_head_class_order_matches_bear_neutral_bull(self):
        dates=pd.bdate_range('2010-01-01',periods=450)
        x=np.linspace(-3,3,300)
        train=pd.DataFrame({'Date':dates[:300],'label_end_date':dates[20:320],
                            'x':x,'label':np.digitize(x,[-1.,1.])})
        valid=pd.DataFrame({'Date':dates[400:403],'x':[-2.,0.,2.]})
        for architecture in ['multiclass','ovr','hierarchical']:
            with self.subTest(architecture=architecture):
                scores=study.fit_directional_heads(train,valid,['x'],architecture)
                np.testing.assert_array_equal(scores.argmax(axis=1),[0,1,2])

    def test_head_fit_rejects_label_maturing_on_prediction_date(self):
        dates=pd.bdate_range('2010-01-01',periods=150)
        train=pd.DataFrame({'Date':dates[:90],'label_end_date':dates[20:110],
                            'x':np.arange(90),'label':np.arange(90)%3})
        valid=pd.DataFrame({'Date':[dates[109]],'x':[1.]})
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.fit_directional_heads(train,valid,['x'],'hierarchical')


if __name__=='__main__':unittest.main()
