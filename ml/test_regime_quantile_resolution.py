"""Independent distribution cases for quantile reconstruction semantics."""
import unittest
import numpy as np
import experiment_regime_quantile_resolution as study


class QuantileResolutionTests(unittest.TestCase):
    def test_linear_inverse_cdf_recovers_analytic_uniform_event_mass(self):
        result=study.quantile_event_masses([[0.,1.,2.]],[.25,.5,.75],[0.],[2.])
        np.testing.assert_allclose(result,[[.25,.5,.25]],atol=1e-12)

    def test_repeated_knots_are_atoms_and_boundary_equality_is_neutral(self):
        points=np.ones((3,3))
        result=study.quantile_event_masses(points,[.25,.5,.75],[-1.,1.,1.01],[1.,2.,2.])
        np.testing.assert_array_equal(result,[[0.,1.,0.],[0.,1.,0.],[1.,0.,0.]])

    def test_kernel_reconstruction_is_invariant_to_return_units(self):
        points=np.array([[-.04,0.,.04],[-.1,0.,.1]])
        levels=[.25,.5,.75];sigma=np.array([.03,.06])
        first=study.quantile_event_masses(points,levels,-sigma,sigma,'kernel',sigma)
        second=study.quantile_event_masses(points*100,levels,-sigma*100,sigma*100,'kernel',sigma*100)
        np.testing.assert_allclose(first,second,atol=1e-12)


if __name__=='__main__':unittest.main()
