"""Forecast filters must be causal and cannot bridge absent sessions."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_forecast_smoothing as study


class ForecastSmoothingTests(unittest.TestCase):
    def test_future_scores_cannot_change_prefix_and_missing_sessions_reset(self):
        calendar=pd.bdate_range('2020-01-01',periods=12)
        dates=calendar[[0,1,4,5,6,7]]
        scores=np.array([[.8,.1,.1],[.1,.8,.1],[.1,.1,.8],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
        expected=study.causal_forecast_ema(dates,scores,calendar,5)
        changed=scores.copy();changed[4:]=[.9,.05,.05]
        actual=study.causal_forecast_ema(dates,changed,calendar,5)
        np.testing.assert_array_equal(actual[:4],expected[:4])
        np.testing.assert_array_equal(expected[2],scores[2])


if __name__=='__main__':unittest.main()
