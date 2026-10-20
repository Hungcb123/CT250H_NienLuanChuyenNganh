import copy
import unittest
import numpy as np
import pandas as pd
import evaluate_regime_probabilities as study


class ProbabilityTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2020-01-01',periods=420)
        book=pd.DataFrame(dict(Date=dates[:380],label_end_date=dates[20:400],label=np.arange(380)%3))
        rows=book.iloc[80:280].copy().reset_index(drop=True)
        rows['selected_expert']=np.where(np.arange(len(rows))%2,'a','b')
        rows['prediction']=rows.label
        rows['outer_fold']=np.repeat([1,2,3,4],50)
        p=.6*np.eye(3)[rows.label.to_numpy()]+.4/3
        for prefix in ['decision_score_','component_mass_']:
            rows[[prefix+c for c in study.CLASSES]]=p
        config=dict(history_rows=60,min_rows=30,min_class_count=2,refit_market_sessions=20,anchor=str(rows.Date.iloc[0].date()),
                    C=.1,solver='lbfgs',max_iter=2000,class_weight=None,random_state=42)
        return rows,book,dates,dict(calibration=config)

    def test_prior_uses_only_mature_labels_and_laplace_smoothing(self):
        rows,book,dates,_=self.fixture();boundary=dates[100]
        first,info=study.causal_prior(book,boundary,60)
        book.loc[book.label_end_date>=boundary,'label']=99
        second,other=study.causal_prior(book,boundary,60)
        np.testing.assert_array_equal(first,second);self.assertEqual(info,other)
        self.assertLess(pd.Timestamp(info['latest_label_end']),boundary)
        np.testing.assert_allclose(first,(np.asarray(info['counts'])+1)/(info['n']+3))

    def test_calibration_features_never_read_target(self):
        rows,_,_,_=self.fixture()
        first=study.calibration_inputs(rows,'decision_score_',['a','b'])
        rows.label=99
        second=study.calibration_inputs(rows,'decision_score_',['a','b'])
        np.testing.assert_array_equal(first,second)
        np.testing.assert_allclose(first[:,:3].sum(axis=1),0.,atol=1e-12)

    def test_exported_calibrator_probabilities_form_simplex(self):
        rows,_,dates,plan=self.fixture()
        state=study.fit_calibration(rows.iloc[:100],dates[250],'decision_score_',['a','b'],plan['calibration'])
        p=study.predict_calibration(state,study.calibration_inputs(rows.iloc[100:],'decision_score_',['a','b']))
        np.testing.assert_allclose(p.sum(axis=1),1.)
        self.assertTrue((p>=0).all());self.assertEqual(p.shape,(100,3))

    def test_boundary_end_label_is_rejected_before_calibration(self):
        rows,_,_,plan=self.fixture()
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.fit_calibration(rows.iloc[:100],rows.label_end_date.iloc[99],'decision_score_',['a','b'],plan['calibration'])

    def test_probability_stream_prefix_is_invariant_to_unknown_labels(self):
        rows,book,dates,plan=self.fixture();original=rows.copy(deep=True)
        full,_,_=study.run_probability_stream(rows,book,dates,['a','b'],plan)
        prefix=rows.iloc[:160].copy();cutoff=prefix.Date.max()
        prefix.loc[prefix.label_end_date>=cutoff,'label']=99
        changed=book.copy();changed.loc[changed.label_end_date>=cutoff,'label']=99
        partial,_,audits=study.run_probability_stream(prefix,changed,dates[dates<=cutoff],['a','b'],plan)
        for name in full:np.testing.assert_allclose(full[name][:160],partial[name],atol=1e-12,rtol=1e-12)
        pd.testing.assert_frame_equal(rows,original)
        for audit in audits:
            if audit['latest_label_end']:self.assertLess(pd.Timestamp(audit['latest_label_end']),pd.Timestamp(audit['Date']))
            self.assertLess(pd.Timestamp(audit['baseline_training']['latest_label_end']),pd.Timestamp(audit['Date']))

    def test_warmup_uses_competent_causal_prior_and_keeps_all_dates(self):
        rows,book,dates,plan=self.fixture();book.label=1
        predictions,active,_=study.run_probability_stream(rows.iloc[:20],book,dates,['a','b'],plan)
        self.assertFalse(active.any())
        np.testing.assert_array_equal(predictions['cal_raw_decision'],predictions['causal_prior'])
        self.assertEqual(len(predictions['causal_prior']),20)
        self.assertTrue((predictions['causal_prior'][:,1]>.9).all())

    def test_proper_losses_reward_correct_probabilities(self):
        y=np.array([0,1,2]);perfect=study.proper_losses(y,np.eye(3))
        prior=study.proper_losses(y,np.full((3,3),1/3))
        np.testing.assert_allclose(perfect['brier'],0.)
        np.testing.assert_allclose(prior['brier'],2/3)
        np.testing.assert_allclose(prior['log_loss'],np.log(3))

    def test_block_bootstrap_preserves_constant_improvement(self):
        interval=study.bootstrap_probability_delta(np.full(200,.2),np.ones(200,dtype=bool),np.repeat([1,2,3,4],50),20,repeats=40)
        self.assertAlmostEqual(interval['low'],.2);self.assertAlmostEqual(interval['high'],.2)


if __name__=='__main__':unittest.main()
