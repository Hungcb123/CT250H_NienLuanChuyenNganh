"""A learned gate must not consume unobserved outcomes when replayed."""
import unittest
import numpy as np
import pandas as pd
from experiment_regime_component_gate import replay_component_gate


class ComponentGateTests(unittest.TestCase):
    def test_real_fitted_gate_is_prefix_invariant_to_unknown_labels(self):
        dates=pd.bdate_range('2020-01-01',periods=280);n=240;y=np.arange(n)%3
        base=pd.DataFrame({'Date':dates[:n],'label_end_date':dates[20:20+n],'label':y})
        winner=np.arange(n)%2
        cp=np.where(winner==0,y,(y+1)%3);dp=np.where(winner==1,y,(y+1)%3)
        classifier=np.full((n,3),.1);classifier[np.arange(n),cp]=.8
        density=np.full((n,3),.1);density[np.arange(n),dp]=.8
        features=np.column_stack([winner,np.arange(n)%3]).astype(float)
        fallback=.5*(classifier+density)
        expected,audit=replay_component_gate(base,classifier,density,features,dates,fallback)
        self.assertTrue(any(r['ready'] for r in audit))
        self.assertGreater(np.abs(expected-fallback).max(),.005)
        self.assertTrue(all(pd.Timestamp(r['latest_label_end'])<pd.Timestamp(r['Date']) for r in audit if r['latest_label_end']))
        end=210;prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_=replay_component_gate(prefix,classifier[:end],density[:end],features[:end],dates[:end],fallback[:end])
        np.testing.assert_allclose(actual,expected[:end],atol=1e-12,rtol=1e-12)


if __name__=='__main__':unittest.main()
