import unittest
import numpy as np
import pandas as pd
from regime_pipeline import close_features, strategy_backtest

class PipelineTests(unittest.TestCase):
    def test_no_future_values_in_features(self):
        values=np.linspace(100,200,200)
        before=close_features(values[:120])
        values[120:]=999999
        np.testing.assert_array_equal(before,close_features(values[:120]))

    def test_fixed_window_and_flat_values(self):
        values=np.linspace(100,200,200)
        np.testing.assert_array_equal(close_features(values),close_features(values[-120:]))
        self.assertEqual(close_features(np.ones(120)*100)[0],50)
        with self.assertRaises(ValueError): close_features(np.zeros(120))

    def test_signal_applies_only_to_next_interval(self):
        dates=pd.date_range('2025-01-01',periods=4)
        r=np.array([.1,.05,-.1,.02])
        a=strategy_backtest(dates,r,[0,0,0,0],[1,1,1,1])
        b=strategy_backtest(dates,r,[0,0,1,0],[1,1,1,1])
        self.assertEqual(a['curves']['TAA'][:3],b['curves']['TAA'][:3])
        self.assertNotEqual(a['curves']['TAA'][3],b['curves']['TAA'][3])

    def test_low_confidence_preserves_saa_and_costs_apply(self):
        dates=pd.date_range('2025-01-01',periods=4)
        result=strategy_backtest(dates,np.zeros(4),[1]*4,[.4]*4)
        self.assertEqual(result['curves']['TAA'],result['curves']['SAA'])
        self.assertLess(result['curves']['BUY_HOLD'][-1]['nav'],1)

if __name__=='__main__': unittest.main()
