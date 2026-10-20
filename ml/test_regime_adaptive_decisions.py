"""Leakage regressions for delayed outcome-based adapters."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_adaptive_decisions as study


class AdaptiveDecisionTests(unittest.TestCase):
    def test_corrupting_unknown_outcomes_cannot_change_prefix_scores(self):
        dates=pd.bdate_range('2020-01-01',periods=260)
        y=np.arange(220)%3
        base=pd.DataFrame({'Date':dates[:220],'label_end_date':dates[20:240],'label':y})
        scores=.2*np.ones((220,3));scores[np.arange(220),y]=.6
        features=np.column_stack([np.sin(np.arange(220)/10),np.cos(np.arange(220)/20)])
        expected,states=study.replay_adaptive_decisions(base,scores,features,dates)
        self.assertTrue(any(s['ready'] for s in states))
        self.assertTrue(all(pd.Timestamp(s['latest_label_end'])<pd.Timestamp(s['Date']) for s in states if s['latest_label_end']))
        end=190;prefix=base.iloc[:end].copy()
        prefix.loc[prefix.label_end_date>=prefix.Date.iloc[-1],'label']=99
        actual,_=study.replay_adaptive_decisions(prefix,scores[:end],features[:end],dates[:end])
        for name in expected:
            np.testing.assert_allclose(actual[name],expected[name][:end],atol=1e-12,rtol=1e-12)

    def test_no_mature_history_uses_incumbent_without_fitting(self):
        dates=pd.bdate_range('2020-01-01',periods=110)
        base=pd.DataFrame({'Date':dates[:80],'label_end_date':dates[20:100],'label':np.arange(80)%3})
        scores=np.tile([.2,.5,.3],(80,1))
        actual,states=study.replay_adaptive_decisions(base,scores,np.zeros((80,2)),dates)
        self.assertFalse(any(s['ready'] for s in states))
        for value in actual.values():np.testing.assert_allclose(value,scores,atol=1e-12)


if __name__=='__main__':unittest.main()
