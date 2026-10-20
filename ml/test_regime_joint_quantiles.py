"""Real CatBoost integration: validation outcomes cannot enter joint forecasts."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_joint_quantiles as study


class JointQuantileTests(unittest.TestCase):
    def test_future_validation_outcome_is_ignored_by_joint_regressor(self):
        dates=pd.bdate_range('2020-01-01',periods=200)
        x=np.linspace(-2,2,90)
        train=pd.DataFrame({'Date':dates[:90],'label_end_date':dates[20:110],
            'x':x,'future_log_return':.03*np.sin(x),'horizon_sigma':.04})
        valid=pd.DataFrame({'Date':dates[150:153],'x':[-1.,0.,1.],
            'horizon_sigma':[.03,.04,.05],'future_log_return':[99.,99.,99.]})
        specification={'quantile_levels':[.05,.15,.25,.35,.5,.65,.75,.85,.95]}
        _,first,_=study.fit_joint_return_quantiles(train,valid,['x'],True,specification)
        changed=valid.assign(future_log_return=-99.)
        _,second,_=study.fit_joint_return_quantiles(train,changed,['x'],True,specification)
        self.assertEqual(first.shape,(3,9))
        self.assertTrue(np.isfinite(first).all())
        np.testing.assert_allclose(first,second,rtol=1e-12,atol=1e-12)

    def test_joint_fit_rejects_unknown_training_outcome(self):
        train=pd.DataFrame({'label_end_date':[pd.Timestamp('2020-02-01')]})
        valid=pd.DataFrame({'Date':[pd.Timestamp('2020-02-01')]})
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.fit_joint_return_quantiles(train,valid,[],False,{})


if __name__=='__main__':unittest.main()
