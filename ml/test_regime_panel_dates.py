import unittest
import numpy as np
import pandas as pd
import experiment_regime_panel as study


class FrozenPanelDatesTests(unittest.TestCase):
    def test_extra_close_only_dates_cannot_expand_validation_cohort(self):
        dates=pd.bdate_range('2020-01-01',periods=12)
        target=pd.DataFrame(dict(Date=dates))
        reference=pd.DataFrame(dict(Date=dates[[1,2,4,7,8,10]]))
        mapped=study.map_frozen_dates(target,reference,[np.arange(3),np.arange(3,6)])
        np.testing.assert_array_equal(mapped[0],[1,2,4])
        np.testing.assert_array_equal(mapped[1],[7,8,10])
        self.assertEqual(sum(len(f) for f in mapped),6)

    def test_absent_frozen_date_is_rejected(self):
        dates=pd.bdate_range('2020-01-01',periods=5)
        with self.assertRaisesRegex(ValueError,'Missing frozen'):
            study.map_frozen_dates(pd.DataFrame(dict(Date=dates[:3])),pd.DataFrame(dict(Date=dates)),[np.arange(5)])


if __name__=='__main__':unittest.main()
