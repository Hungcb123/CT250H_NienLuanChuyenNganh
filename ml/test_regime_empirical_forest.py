import unittest
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from experiment_regime_empirical_forest import empirical_leaf_mass


class EmpiricalForestTests(unittest.TestCase):
    def test_leaf_specific_distribution_and_neutral_equalities(self):
        train = np.array([[1,4],[1,4],[2,4],[2,5],[2,5]])
        valid = np.array([[1,4],[2,5]])
        values = np.array([-2.,-1.,0.,1.,2.])
        mass = empirical_leaf_mass(train, valid, values, np.array([-1.,0.]), np.array([1.,1.]))
        np.testing.assert_allclose(mass, [[5/12,7/12,0.],[0.,7/12,5/12]])
        shifted = empirical_leaf_mass(train, valid, values, np.array([-3.,-3.]), np.array([-2.,-2.]))
        self.assertFalse(np.allclose(mass, shifted))
        np.testing.assert_allclose(shifted.sum(axis=1), 1.)

    def test_real_forest_matches_explicit_observation_weights(self):
        rng = np.random.default_rng(71)
        x = rng.normal(size=(150,3)); y = 2*x[:,0]+rng.normal(size=150)
        xv = rng.normal(size=(7,3))
        model = ExtraTreesRegressor(n_estimators=7, min_samples_leaf=12, random_state=42).fit(x,y)
        train, valid = model.apply(x), model.apply(xv)
        low, high = np.linspace(-2.,0.,7), np.linspace(.1,2.,7)
        actual = empirical_leaf_mass(train, valid, y, low, high)
        expected = []
        for j in range(len(xv)):
            weight = np.zeros(len(x))
            for t in range(train.shape[1]):
                match = train[:,t] == valid[j,t]
                weight[match] += 1./match.sum()/train.shape[1]
            expected.append([weight[y<low[j]].sum(), weight[(y>=low[j])&(y<=high[j])].sum(), weight[y>high[j]].sum()])
        np.testing.assert_allclose(actual, expected, atol=1e-12)
        with self.assertRaisesRegex(ValueError, 'no mature observations'):
            empirical_leaf_mass(train, valid+100000, y, low, high)


if __name__ == '__main__':
    unittest.main()
