import unittest
import numpy as np
from scipy.stats import logistic
from experiment_regime_soft_margin import soft_margin_memberships


class SoftMarginTests(unittest.TestCase):
    def test_extreme_returns_remain_nonnegative_and_symmetric(self):
        z=np.array([-1e6,-100.,-20.,-1.,0.,1.,20.,100.,1e6])
        mass=soft_margin_memberships(z)
        self.assertTrue(np.isfinite(mass).all())
        self.assertTrue((mass>=0).all())
        np.testing.assert_allclose(mass.sum(axis=1),1.,atol=1e-15)
        np.testing.assert_allclose(mass,mass[::-1,::-1],atol=1e-15)
        np.testing.assert_array_equal(mass[0],[1.,0.,0.])
        np.testing.assert_array_equal(mass[-1],[0.,0.,1.])

    def test_interval_masses_match_distribution_cdf(self):
        z=np.linspace(-3.,3.,301)
        for width in [.1,.25,1.]:
            low=logistic.cdf(-1.,loc=z,scale=width)
            high=logistic.cdf(1.,loc=z,scale=width)
            expected=np.column_stack([low,high-low,logistic.sf(1.,loc=z,scale=width)])
            np.testing.assert_allclose(soft_margin_memberships(z,width),expected,atol=3e-16)
        for bad,width in [(np.array([np.nan]),.25),(np.zeros((2,2)),.25),(z,0.)]:
            with self.assertRaises(ValueError):soft_margin_memberships(bad,width)


if __name__=='__main__':unittest.main()
