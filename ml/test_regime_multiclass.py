import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

import experiment_regime_multiclass as study


class MulticlassTests(unittest.TestCase):
    def test_ordinal_crossing_projects_to_simplex(self):
        probability=study.ordered_probabilities([.2,.8,.6],[.7,.4,.6])
        np.testing.assert_allclose(probability,[[.55,0,.45],[.2,.4,.4],[.4,0,.6]])
        self.assertTrue((probability>=0).all())
        np.testing.assert_allclose(probability.sum(axis=1),1.)

    def test_unknown_outcomes_cannot_change_decision_weights(self):
        dates=pd.bdate_range('2020-01-01',periods=260)
        rows=pd.DataFrame(dict(Date=dates[:180],label_end_date=dates[20:200],label=np.arange(180)%3))
        rows[study.PROB_COLUMNS]=np.tile([.15,.25,.6],(180,1))
        first,info=study.causal_decision_weights(rows,dates[200])
        contaminated=rows.copy()
        future=rows.iloc[:50].copy()
        future['Date']=dates[199];future['label_end_date']=dates[220]
        future['label']=0;future[study.PROB_COLUMNS]=[.99,.005,.005]
        second,second_info=study.causal_decision_weights(pd.concat([contaminated,future],ignore_index=True),dates[200])
        np.testing.assert_array_equal(first,second)
        self.assertEqual(info,second_info)
        self.assertLess(pd.Timestamp(info['latest_label_end']),dates[200])

    def test_small_or_single_class_archive_falls_back_to_argmax(self):
        dates=pd.bdate_range('2020-01-01',periods=220)
        rows=pd.DataFrame(dict(Date=dates[:130],label_end_date=dates[20:150],label=1))
        rows[study.PROB_COLUMNS]=[.1,.8,.1]
        weights,info=study.causal_decision_weights(rows,dates[200])
        np.testing.assert_array_equal(weights,np.ones(3))
        self.assertEqual(info['n'],130)

    def test_replay_rejects_unmatured_training_label(self):
        dates=pd.bdate_range('2020-01-01',periods=50)
        frame=pd.DataFrame(dict(Date=dates[:30],label_end_date=dates[20:50],label=np.arange(30)%3,future_return=0.,x=1.))
        job=dict(names=['x'],folds=[dict(fold=1,blocks=[dict(train=np.arange(15),validation=np.arange(15,20))])])
        with self.assertRaisesRegex(ValueError,'Noncausal'):
            study.run_multiclass(frame,job,'gbm',False)

    def test_refit_predictions_do_not_use_current_labels_for_decisions(self):
        dates=pd.bdate_range('2020-01-01',periods=60)
        frame=pd.DataFrame(dict(Date=dates[:40],label_end_date=dates[20:60],label=np.arange(40)%3,future_return=0.,x=1.))
        job=dict(names=['x'],folds=[dict(fold=1,blocks=[dict(train=np.arange(10),validation=np.arange(30,35))])])
        with patch.object(study,'fit_probabilities',return_value=np.tile([.2,.3,.5],(5,1))):
            first,audit=study.run_multiclass(frame,job,'gbm',False)
            frame.loc[30:34,'label']=0
            second,_=study.run_multiclass(frame,job,'gbm',False)
        np.testing.assert_array_equal(first.argmax,second.argmax)
        np.testing.assert_array_equal(first.causal_macro_weights,second.causal_macro_weights)
        self.assertEqual(audit[0]['decision_history']['n'],0)

    def test_fixed_and_ordinal_learners_return_three_ordered_classes(self):
        rng=np.random.default_rng(42)
        train=pd.DataFrame(dict(x=rng.normal(size=180),label=np.arange(180)%3))
        for family in ['gbm','ordinal','logistic']:
            probability=study.fit_probabilities(train,train.iloc[:5],['x'],family,False)
            self.assertEqual(probability.shape,(5,3))
            np.testing.assert_allclose(probability.sum(axis=1),1.)


if __name__=='__main__':unittest.main()
