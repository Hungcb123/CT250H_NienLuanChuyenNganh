import unittest
import numpy as np
import experiment_regime_distribution as study


class DistributionTests(unittest.TestCase):
    def test_higher_known_volatility_raises_fixed_loss_risk(self):
        labels=np.array([0,0,1,1,2,2]);z=np.array([-3,-1.2,-.5,.5,1.2,3.])
        q=np.tile([.2,.6,.2],(3,1))
        s=study.mixture_risk(q,[0,1,2],labels,z,[.01,.05,.2],False)
        self.assertTrue((np.diff(s)>=0).all())
        self.assertLess(s[0],s[-1])

    def test_prior_correction_and_class_column_mapping(self):
        labels=np.array([0,1,1,1,2]);z=np.array([-2.,-.5,0,.5,2.])
        raw=np.array([[1/3,1/3,1/3]])
        probability=study.mixture_risk(raw,[0,1,2],labels,z,[.04],True)
        # Balanced outputs become observed prior [.2,.6,.2]; cutoff -1.28 is in class0 only.
        self.assertAlmostEqual(probability[0],.2)
        permuted=study.mixture_risk(raw[:,[2,0,1]],[2,0,1],labels,z,[.04],True)
        np.testing.assert_array_equal(probability,permuted)

    def test_invalid_distribution_or_volatility_rejected(self):
        with self.assertRaisesRegex(ValueError,'volatility'):
            study.mixture_risk([[.3,.4,.3]],[0,1,2],[0,1,2],[-2,0,2],[0],True)
        with self.assertRaisesRegex(ValueError,'probabilities'):
            study.mixture_risk([[.4,.4,.4]],[0,1,2],[0,1,2],[-2,0,2],[.03],True)

    def test_future_volatility_does_not_change_previous_risk(self):
        q=np.tile([.2,.6,.2],(3,1));sigma=np.array([.02,.04,.06])
        y=np.array([0,1,2]);z=np.array([-2,0,2.])
        before=study.mixture_risk(q,[0,1,2],y,z,sigma)
        sigma[1:]=100
        after=study.mixture_risk(q,[0,1,2],y,z,sigma)
        self.assertEqual(before[0],after[0])
