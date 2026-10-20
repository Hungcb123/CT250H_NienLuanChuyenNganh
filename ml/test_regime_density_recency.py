"""Calendar-based decay must not turn sparse rows into fictitious sessions."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_density_recency as study


class DensityRecencyTests(unittest.TestCase):
    def test_decay_uses_full_market_calendar_and_ignores_future_calendar_extension(self):
        calendar=pd.bdate_range('2020-01-01',periods=40)
        dates=calendar[[0,5,10]]
        actual=study.causal_recency_weights(dates,calendar[15],calendar[:20],5)
        self.assertAlmostEqual(actual[-1]/actual[0],4.)
        self.assertAlmostEqual(actual.mean(),1.)
        longer=study.causal_recency_weights(dates,calendar[15],calendar,5)
        np.testing.assert_array_equal(actual,longer)

    def test_current_or_future_observation_is_rejected(self):
        calendar=pd.bdate_range('2020-01-01',periods=20)
        with self.assertRaisesRegex(ValueError,'boundary'):
            study.causal_recency_weights(calendar[[0,10]],calendar[10],calendar,5)


if __name__=='__main__':unittest.main()
