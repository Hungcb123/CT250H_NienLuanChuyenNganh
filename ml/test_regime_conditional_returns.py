import unittest
import numpy as np
import pandas as pd
from scipy.special import ndtr
import experiment_regime_conditional_returns as study


class ConditionalReturnTests(unittest.TestCase):
    def test_classes_match_log_return_barriers_and_sum_to_one(self):
        p=study.conditional_return_probabilities([0.],[.01])
        sd=.01*np.sqrt(20)
        np.testing.assert_allclose(p[0,0],ndtr(np.log(.95)/sd))
        np.testing.assert_allclose(p[0,2],ndtr(-np.log(1.05)/sd))
        np.testing.assert_allclose(p.sum(axis=1),1.)

    def test_future_prices_do_not_change_current_predictors(self):
        dates=pd.bdate_range('2020-01-01',periods=400)
        price=100*np.exp(.001*np.arange(400)+.02*np.sin(np.arange(400)))
        source=pd.DataFrame(dict(Date=dates,Price=price))
        first=study.conditional_inputs(source)
        source.loc[301:,'Price']*=3
        second=study.conditional_inputs(source)
        pd.testing.assert_frame_equal(first.iloc[:301],second.iloc[:301])

    def test_larger_zero_drift_volatility_reduces_sideway_probability(self):
        p=study.conditional_return_probabilities([0.,0.],[.005,.03])
        self.assertGreater(p[0,1],p[1,1])
        self.assertTrue((p>=0).all())

    def test_positive_drift_raises_bull_probability(self):
        p=study.conditional_return_probabilities([0.,.001],[.01,.01])
        self.assertGreater(p[1,2],p[0,2]);self.assertLess(p[1,0],p[0,0])

    def test_undefined_variance_is_not_silently_filled(self):
        with self.assertRaisesRegex(ValueError,'Invalid past'):
            study.conditional_return_probabilities([0.],[0.])


if __name__=='__main__':unittest.main()
