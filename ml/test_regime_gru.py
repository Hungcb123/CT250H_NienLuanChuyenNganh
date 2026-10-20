"""As-of preprocessing and real CPU model/checkpoint integration."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import experiment_regime_gru as study


class TemporalGRUTests(unittest.TestCase):
    def test_training_normalizer_and_prefix_inputs_ignore_future_features(self):
        values=np.arange(40,dtype=float).reshape(20,2);values[3,0]=np.nan
        positions=[5,7,9]
        first,stats=study.prepare_temporal_inputs(values,positions,4)
        changed=values.copy();changed[10:]*=1000
        other,other_stats=study.prepare_temporal_inputs(changed,positions,4)
        np.testing.assert_array_equal(first,other)
        for k in stats:np.testing.assert_array_equal(stats[k],other_stats[k])
        self.assertEqual(first.shape,(3,4,4))
        self.assertTrue(np.isfinite(first).all())

    def test_real_cpu_training_checkpoint_and_unknown_validation_labels(self):
        dates=pd.bdate_range('2020-01-01',periods=200)
        values=np.column_stack([np.sin(np.arange(200)/10),np.cos(np.arange(200)/7)])
        train=pd.DataFrame({'Date':dates[:90],'label_end_date':dates[20:110],'label':np.digitize(values[:90,0],[-.3,.3])})
        valid=pd.DataFrame({'Date':dates[150:153],'label':[99,99,99]})
        with tempfile.TemporaryDirectory() as folder:
            first,audit=study.fit_temporal_gru(train,valid,values,dates,['a','b'],4,7,2,torch.device('cpu'),Path(folder)/'first.pt')
            second,_=study.fit_temporal_gru(train,valid.assign(label=-99),values,dates,['a','b'],4,7,2,torch.device('cpu'),Path(folder)/'second.pt')
            np.testing.assert_allclose(first,second,atol=1e-12)
            self.assertEqual(first.shape,(3,3))
            self.assertLess(pd.Timestamp(audit['latest_label_end']),valid.Date.min())

    def test_unknown_training_outcome_is_rejected(self):
        train=pd.DataFrame({'label_end_date':[pd.Timestamp('2020-01-01')]})
        valid=pd.DataFrame({'Date':[pd.Timestamp('2020-01-01')]})
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.fit_temporal_gru(train,valid,None,None,[],1,1,1,torch.device('cpu'),None)


if __name__=='__main__':unittest.main()
