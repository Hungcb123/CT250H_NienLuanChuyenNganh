from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

import experiment_regime_return_distribution as study


class ReturnDistributionTests(unittest.TestCase):
    def test_quadrature_mass_is_three_class_simplex(self):
        p,points=study.quantile_class_mass([[.1,-.1,0]],np.array([.2,.6,.2]))
        np.testing.assert_allclose(p,[[.2,.6,.2]])
        np.testing.assert_allclose(points,[[-.1,0,.1]])
        np.testing.assert_allclose(p.sum(axis=1),1.)

    def test_exact_threshold_equality_stays_sideway(self):
        p,_=study.quantile_class_mass([[np.log(.95),0,np.log(1.05)]],[.2,.6,.2])
        np.testing.assert_allclose(p,[[0,1,0]])

    def test_invalid_weights_and_nonfinite_forecasts_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'weights'):
            study.quantile_class_mass([[-.1,0,.1]],[.2,-.1,.9])
        with self.assertRaisesRegex(ValueError,'predictions'):
            study.quantile_class_mass([[np.nan,0,.1]],[.2,.6,.2])

    def test_sigma_is_trailing_and_does_not_use_future_prices(self):
        dates=pd.bdate_range('2020-01-01',periods=80)
        prices=100*np.exp(.001*np.arange(80)+.01*np.sin(np.arange(80)))
        first=pd.DataFrame(dict(Date=dates,Price=prices))
        expected=study.trailing_horizon_sigma(first)
        first.loc[51:,'Price']*=3
        actual=study.trailing_horizon_sigma(first)
        np.testing.assert_array_equal(expected.horizon_sigma.iloc[:51],actual.horizon_sigma.iloc[:51])
        manual=np.log(prices[30:51])[1:]-np.log(prices[30:51])[:-1]
        self.assertAlmostEqual(expected.horizon_sigma.iloc[50],manual.std(ddof=1)*np.sqrt(20))

    def test_unmatured_regression_labels_are_rejected_before_fit(self):
        train=pd.DataFrame(dict(label_end_date=pd.to_datetime(['2020-02-01'])))
        valid=pd.DataFrame(dict(Date=pd.to_datetime(['2020-02-01'])))
        with patch.object(study,'LGBMRegressor',side_effect=AssertionError('must not fit')):
            with self.assertRaisesRegex(ValueError,'Unmatured'):
                study.fit_return_quantiles(train,valid,[],False,{})

    def test_normalized_model_uses_known_sigma_and_restores_return_units(self):
        train=pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01',periods=3),label_end_date=pd.bdate_range('2020-01-06',periods=3),future_log_return=[.02,.04,.06],horizon_sigma=.02,x=1.))
        valid=pd.DataFrame(dict(Date=pd.to_datetime(['2020-02-01']),horizon_sigma=.1,x=1.))
        targets=[]
        class FakeModel:
            def __init__(self,**kwargs):self.alpha=kwargs['alpha']
            def fit(self,X,y):targets.append(y.copy())
            def predict(self,X):return np.full(len(X),self.alpha-.5)
        spec=dict(parameters={},quantile_levels=[.1,.5,.9],quantile_atom_weights=[.25,.5,.25])
        with patch.object(study,'LGBMRegressor',FakeModel):
            p,q,_=study.fit_return_quantiles(train,valid,['x'],True,spec)
        for y in targets:np.testing.assert_allclose(y,[1,2,3])
        np.testing.assert_allclose(q,[[-.04,0,.04]])
        np.testing.assert_allclose(p,[[0,1,0]])

    def test_prediction_decisions_and_probabilities_survive_summary_export(self):
        dates=pd.bdate_range('2020-01-01',periods=32)
        rows=pd.DataFrame(dict(Date=dates[:12],label_end_date=dates[20:32],label=np.arange(12)%3,future_return=0.,
                              prediction_raw=np.arange(12)%3,prediction_prior_balanced=np.arange(12)%3,baseline_prediction=1,outer_fold=np.repeat([1,2,3,4],3)))
        rows[study.PROBS]=np.eye(3)[rows.label]
        rows[study.BASE_PROBS]=1/3
        results=study.summarize_return_forecasts('test',rows)
        control=dict(candidate='control',mean_f1=.5,worst_f1=.5,mean_mcc=.1,folds=[dict(f1_macro=.5)]*4)
        with tempfile.TemporaryDirectory() as tmp:
            study.write_return_report(results,[control],Path(tmp))
            table=pd.read_csv(Path(tmp)/'comparison.csv')
        self.assertEqual(len(table),2)
        self.assertTrue((table.mean_f1==1).all())
        self.assertTrue((table.development_screen_both_controls).all())


if __name__=='__main__':unittest.main()
