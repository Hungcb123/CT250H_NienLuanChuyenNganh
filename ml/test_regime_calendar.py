"""Calendar encodings must be as-of invariant and contain no absolute era."""
import unittest
import pandas as pd
import numpy as np
import experiment_regime_calendar as study


class CalendarFeatureTests(unittest.TestCase):
    def test_future_calendar_extension_does_not_change_past_and_same_season_repeats(self):
        dates=pd.bdate_range('2020-01-01',periods=200)
        expected=study.calendar_features(dates[:120])
        actual=study.calendar_features(dates).iloc[:120]
        pd.testing.assert_frame_equal(expected,actual)
        repeated=study.calendar_features(pd.to_datetime(['2018-01-01','2024-01-01'])).drop(columns='Date')
        np.testing.assert_array_equal(repeated.iloc[0],repeated.iloc[1])


if __name__=='__main__':unittest.main()
