import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch
import experiment_regime_quantile as study
from test_regime_risk import fixture


class QuantileTests(unittest.TestCase):
    def test_dense_target_and_sigma_reconstruction_only_core_fit(self):
        frame=fixture()
        frame['future_log_return']=np.log1p(frame.future_return)
        frame['horizon_sigma']=.05
        core,cal=study.study.risk.split_calibration(frame,np.arange(500))
        block=dict(core=core,calibration=cal,validation=np.arange(530,580))
        jobs=[dict(fold=1,blocks={'3y':[block],'expanding':[block]})]
        seen=[]
        class Fake:
            def fit(self,X,y):seen.append(y.copy());return self
            def predict(self,X):return np.full(len(X),-.1)
        with patch.object(study,'make_model',side_effect=lambda:Fake()):
            records,audits=study.run(frame,jobs,['x'])
        self.assertEqual(len(records),8*50)
        np.testing.assert_allclose(seen[0],frame.future_log_return.iloc[core])
        np.testing.assert_allclose(seen[1],frame.future_log_return.iloc[core]/.05)
        normalized=records.loc[records.policy=='3y_normalized_fixed_loss5']
        np.testing.assert_allclose(normalized.risk_score,.005)
        self.assertFalse(normalized.alarm.any())
        self.assertTrue(records.loc[records.policy=='3y_raw_fixed_loss5','alarm'].all())

    def test_quantile_model_has_no_class_weights(self):
        model=study.make_model()
        self.assertEqual(model.get_params()['objective'],'quantile')
        self.assertEqual(model.get_params()['alpha'],.1)
        self.assertIsNone(model.get_params().get('class_weight'))
