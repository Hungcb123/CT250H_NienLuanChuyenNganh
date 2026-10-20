import unittest
import numpy as np
from experiment_regime_metric_analog import metric_analog_mass


class MetricAnalogTests(unittest.TestCase):
    def test_queries_and_targets_cannot_fit_covariance_or_choose_neighbors(self):
        rng=np.random.default_rng(43);x=rng.normal(size=(140,4))
        x[:,3]=x[:,0]+.1*x[:,1];v=rng.normal(size=(6,4));y=rng.normal(size=140)
        positions=np.arange(140)*2;low=np.full(6,-1.);high=np.ones(6)
        mass,details=metric_analog_mass(x,v,y,low,high,positions)
        full=np.vstack([v,np.full((2,4),1e8)])
        changed,other=metric_analog_mass(x,full,y,np.full(8,-1.),np.ones(8),positions)
        np.testing.assert_allclose(mass,changed[:6],rtol=0,atol=1e-15)
        np.testing.assert_array_equal(details['precision'],other['precision'])
        _,relabeled=metric_analog_mass(x,v,y[::-1],low,high,positions)
        self.assertEqual(details['selection_sha256'],relabeled['selection_sha256'])
        # Independently reconstruct its Mahalanobis distances and atom masses.
        a=(x-np.asarray(details['center']))/np.asarray(details['scale'])
        b=(v-np.asarray(details['center']))/np.asarray(details['scale'])
        delta=b[:,None,:]-a[None,:,:]
        ds=np.sqrt(np.maximum(np.einsum('bnd,de,bne->bn',delta,np.asarray(details['precision']),delta),0.))
        ids=np.argsort(ds,axis=1,kind='stable')[:,:100]
        nearest=np.take_along_axis(ds,ids,axis=1)
        weights=np.exp(-.5*(nearest/np.median(nearest,axis=1)[:,None])**2)
        weights/=weights.sum(axis=1,keepdims=True);atoms=y[ids]
        expected=np.column_stack([(weights*(atoms<-1.)).sum(axis=1),(weights*((atoms>=-1.)&(atoms<=1.))).sum(axis=1),(weights*(atoms>1.)).sum(axis=1)])
        np.testing.assert_allclose(mass,expected,atol=1e-12)

    def test_separation_uses_actual_calendar_positions_and_handles_zero_distance(self):
        x=np.zeros((6,2));v=np.zeros((1,2));y=np.array([0.,-2.,2.,2.,-2.,0.])
        positions=np.array([0,1,2,100,101,102])
        for metric in ['euclidean','mahalanobis']:
            mass,details=metric_analog_mass(x,v,y,np.array([-1.]),np.array([1.]),positions,metric,gap=20)
            np.testing.assert_allclose(mass,[[0.,.5,.5]],atol=1e-15)
            self.assertEqual(details['min_neighbors'],2)
            self.assertEqual(details['minimum_calendar_separation'],100)
        with self.assertRaises(ValueError):
            metric_analog_mass(x,v,y,np.array([-1.]),np.array([1.]),positions[::-1],gap=20)


if __name__=='__main__':unittest.main()
