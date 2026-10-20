import unittest
import numpy as np
from experiment_regime_analog_density import analog_return_mass


class AnalogDensityTests(unittest.TestCase):
    def test_new_queries_cannot_change_train_scaling_or_previous_scores(self):
        rng=np.random.default_rng(71)
        x=rng.normal(size=(180,6));v=rng.normal(size=(7,6));y=rng.normal(size=180)
        low=np.full(7,-1.);high=np.ones(7)
        mass,details=analog_return_mass(x,v,y,low,high,neighbors=50)
        altered=np.vstack([v,np.full((2,6),1e8),np.full((2,6),-1e8)])
        larger,other=analog_return_mass(x,altered,y,np.full(11,-1.),np.ones(11),neighbors=50)
        np.testing.assert_allclose(mass,larger[:7],rtol=0,atol=1e-15)
        self.assertEqual(details['center'],other['center'])
        self.assertEqual(details['scale'],other['scale'])
        self.assertLessEqual(details['mean_effective_neighbors'],50.)
        np.testing.assert_allclose(mass.sum(axis=1),1.,atol=1e-15)

    def test_identical_states_zero_iqr_and_equality_neutral(self):
        x=np.zeros((5,3));v=np.zeros((2,3));y=np.array([-2.,-1.,0.,1.,2.])
        mass,details=analog_return_mass(x,v,y,np.full(2,-1.),np.ones(2),neighbors=100)
        np.testing.assert_allclose(mass,[[.2,.6,.2]]*2,atol=1e-15)
        self.assertEqual(details['scale'],[1.,1.,1.])
        self.assertEqual(details['n_neighbors'],5)
        self.assertAlmostEqual(details['min_effective_neighbors'],5.)
        with self.assertRaises(ValueError):
            analog_return_mass(x,np.full((2,3),np.nan),y,np.full(2,-1.),np.ones(2))


if __name__=='__main__':unittest.main()
