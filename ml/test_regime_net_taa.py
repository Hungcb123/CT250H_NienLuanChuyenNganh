import unittest
import numpy as np
import pandas as pd
from evaluate_regime_net_taa import simulate_net_taa


class NetTaaTests(unittest.TestCase):
    def test_teacher_example_and_one_full_session_execution_lag(self):
        prices = pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01', periods=4), Close=[100., 200., 220., 220.]))
        scores = {prices.Date.iloc[0]: [.30, .34, .36]}
        rows, _ = simulate_net_taa(prices, scores, 0, 0, 'net_score', cost=0)
        self.assertAlmostEqual(rows.target.iloc[0], .359)
        self.assertAlmostEqual(rows.net_return.iloc[0], .359*.1)
        self.assertEqual(rows.execution_date.iloc[0], '2020-01-02')
        self.assertEqual(rows.outcome_date.iloc[0], '2020-01-03')

    def test_cost_and_drift_even_when_target_does_not_change(self):
        prices = pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01', periods=5), Close=[100., 100., 110., 110., 110.]))
        rows, _ = simulate_net_taa(prices, {}, 0, 2, 'saa', cost=.002)
        self.assertEqual(rows.turnover.iloc[0], 0.)
        self.assertGreater(rows.turnover.iloc[1], 0.)
        self.assertLess(rows.net_return.iloc[1], 0.)
        self.assertGreater(rows.cost_fraction.iloc[1], 0.)


if __name__ == '__main__':
    unittest.main()
