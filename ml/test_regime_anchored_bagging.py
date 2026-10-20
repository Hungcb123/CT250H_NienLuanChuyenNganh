"""Bootstrap mass and causal adaptation around a known inner prior."""
import unittest
import numpy as np
import pandas as pd
from experiment_regime_block_density import moving_block_counts
from experiment_regime_anchored_fusion import replay_anchored_fusion,GRID


class AnchoredBaggingTests(unittest.TestCase):
    def test_block_counts_are_reproducible_mass_on_existing_rows(self):
        y=np.repeat([0,1,2],[90,90,20])
        first,attempts=moving_block_counts(len(y),20,42,y)
        other,again=moving_block_counts(len(y),20,42,y)
        np.testing.assert_array_equal(first,other);self.assertEqual(attempts,again)
        self.assertEqual(len(first),len(y));self.assertEqual(first.sum(),len(y))
        self.assertTrue((first>=0).all() and (first==np.floor(first)).all())
        self.assertTrue((np.bincount(y,weights=first,minlength=3)>=10).all())

    def test_online_changes_leave_unavailable_outcomes_unused(self):
        dates=pd.bdate_range('2020-01-01',periods=280);n=240;y=np.arange(n)%3
        base=pd.DataFrame({'Date':dates[:n],'label_end_date':dates[20:20+n],'label':y,'outer_fold':1})
        c=np.full((n,3),.2);c[np.arange(n),y]=.6
        d=np.full((n,3),.1);d[np.arange(n),(y+1)%3]=.8
        anchor={1:GRID.index((.75,1.,1.))}
        expected,_,history=replay_anchored_fusion(base,c,d,dates,anchor)
        self.assertTrue(any(r['choice']!=r['anchor'] for r in history))
        end=210;prefix=base.iloc[:end].copy();cutoff=prefix.Date.iloc[-1]
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        actual,_,_=replay_anchored_fusion(prefix,c[:end],d[:end],dates[:end],anchor)
        for key in actual:np.testing.assert_allclose(actual[key],expected[key][:end],atol=1e-12,rtol=1e-12)


if __name__=='__main__':unittest.main()
