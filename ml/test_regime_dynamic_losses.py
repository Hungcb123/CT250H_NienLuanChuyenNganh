"""Numerical differentiation and real custom-objective integration checks."""
import unittest
import numpy as np
import pandas as pd
from scipy.special import logsumexp
import experiment_regime_dynamic_losses as study


class DynamicLossTests(unittest.TestCase):
    def test_analytic_gradients_match_independent_finite_differences(self):
        raw=np.array([[.2,-.3,.7],[-1.,.2,.4],[.3,.5,-.1]])
        y=np.array([0,1,2]);alpha=np.array([.8,1.2,2.])
        delta=1e-5
        for gamma,smoothing in [(0.,0.),(0.,.1),(1.,0.),(2.,0.)]:
            def loss(z):
                logp=z-logsumexp(z,axis=1,keepdims=True)
                if gamma:
                    u=np.exp(logp[np.arange(3),y])
                    return -np.sum(alpha[y]*(1-u)**gamma*logp[np.arange(3),y])
                target=(1-smoothing)*np.eye(3)[y]+smoothing/3
                return -np.sum(alpha[y,None]*target*logp)
            gradient,hessian=study.multiclass_loss_derivatives(y,raw,alpha,gamma,smoothing)
            numeric=np.zeros_like(raw);curvature=np.zeros_like(raw)
            for i,j in np.ndindex(raw.shape):
                plus,minus=raw.copy(),raw.copy();plus[i,j]+=delta;minus[i,j]-=delta
                numeric[i,j]=(loss(plus)-loss(minus))/(2*delta)
                gp,_=study.multiclass_loss_derivatives(y,plus,alpha,gamma,smoothing)
                gm,_=study.multiclass_loss_derivatives(y,minus,alpha,gamma,smoothing)
                curvature[i,j]=(gp[i,j]-gm[i,j])/(2*delta)
            np.testing.assert_allclose(gradient,numeric,atol=1e-8,rtol=1e-7)
            np.testing.assert_allclose(hessian/1.5,curvature,atol=1e-8,rtol=1e-7)

    def test_extreme_logits_produce_finite_positive_newton_surrogate(self):
        gradient,hessian=study.multiclass_loss_derivatives([0,2],[[1000.,-1000.,0.],[1000.,0.,-1000.]],[1.,1.,1.],2.)
        self.assertTrue(np.isfinite(gradient).all() and np.isfinite(hessian).all())
        self.assertTrue((hessian>0).all())

    def test_lightgbm_custom_loss_ignores_validation_outcomes(self):
        dates=pd.bdate_range('2020-01-01',periods=400)
        x=np.linspace(-3,3,240)
        train=pd.DataFrame({'Date':dates[:240],'label_end_date':dates[20:260],'x':x,'label':np.digitize(x,[-1,1])})
        valid=pd.DataFrame({'Date':dates[300:303],'x':[-2.,0.,2.],'label':[99,99,99]})
        for loss in ['ce','focal2','smooth10']:
            actual=study.fit_dynamic_loss(train,valid,['x'],loss)
            other=study.fit_dynamic_loss(train,valid.assign(label=-99),['x'],loss)
            np.testing.assert_allclose(actual,other,atol=1e-12,rtol=1e-12)
            np.testing.assert_array_equal(actual.argmax(axis=1),[0,1,2])


if __name__=='__main__':unittest.main()
