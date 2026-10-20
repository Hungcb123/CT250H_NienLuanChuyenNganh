"""Auxiliary path targets must retain full-calendar windows and incomplete NaNs."""
import unittest
import numpy as np
import pandas as pd
from experiment_regime_path_forest import future_path_training_targets


class PathTargetTests(unittest.TestCase):
    def test_complete_future_paths_and_unavailable_tail(self):
        index = pd.DataFrame(dict(Date=pd.bdate_range('2020-01-01', periods=5),
                                  Price=[100., 90., 110., 80., 120.]))
        actual = future_path_training_targets(index, horizon=2)
        np.testing.assert_array_equal(actual.Date, index.Date)
        np.testing.assert_allclose(actual.future_path_min[:3], [np.log(.9), np.log(80/90), np.log(80/110)])
        np.testing.assert_allclose(actual.future_path_max[:3], [np.log(1.1), np.log(110/90), np.log(120/110)])
        self.assertTrue(actual.iloc[-2:][['future_path_min', 'future_path_max']].isna().all().all())
        with self.assertRaises(ValueError):
            future_path_training_targets(index, horizon=0)


if __name__ == '__main__':
    unittest.main()
