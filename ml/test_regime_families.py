import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import optuna
import pandas as pd
from sklearn.dummy import DummyClassifier

import experiment_regime_families as study


class FamilyTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2020-01-01',periods=140)
        return pd.DataFrame(dict(Date=dates[:100],label_end_date=dates[20:120],label=np.arange(100)%3,
                                future_return=0.,x=np.sin(np.arange(100)))),dates

    def test_boundary_equality_is_rejected_before_fitting(self):
        frame,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'Unmatured'):
            study.assert_family_split(frame,np.arange(31),np.arange(50,60))
        study.assert_family_split(frame,np.arange(30),np.arange(50,60))

    def test_svc_scaler_uses_only_training_rows(self):
        frame,_=self.fixture()
        params=study.family_parameters('SVC',optuna.trial.FixedTrial(dict(kernel='rbf',C=1.,class_weight='balanced',gamma_mode='numeric',gamma=.01)))
        model=study.build_family('SVC',params)
        X=frame[['x']].iloc[:60].to_numpy();model.fit(X,frame.label.iloc[:60])
        model.predict(np.array([[1e9],[-1e9]]))
        np.testing.assert_allclose(model[0].mean_,X.mean(axis=0))
        self.assertFalse(model[-1].probability)

    def test_catboost_both_predeclared_losses_fit_without_file_output(self):
        frame,_=self.fixture()
        for loss in ['MultiClass','MultiClassOneVsAll']:
            params=study.family_parameters('CatBoost',optuna.trial.FixedTrial(dict(loss_function=loss,iterations=200,depth=3,learning_rate=.03,l2_leaf_reg=3.,auto_class_weights='Balanced')))
            self.assertFalse(params['allow_writing_files'])
            model=study.build_family('CatBoost',params)
            model.fit(frame[['x']].iloc[:60].to_numpy(),frame.label.iloc[:60])
            pred=np.asarray(model.predict(frame[['x']].iloc[60:65].to_numpy())).reshape(-1)
            self.assertEqual(len(pred),5)
            self.assertTrue(set(pred)<={0,1,2})

    def test_tuner_uses_exact_budget_and_purged_splits(self):
        frame,_=self.fixture();folds=[(np.arange(30),np.arange(50,60))]
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        with patch.object(study,'build_family',return_value=DummyClassifier(strategy='prior')):
            result=study.tune_family(frame,['x'],folds,'ExtraTrees',2)
        self.assertEqual(result['n_trials'],2)
        self.assertEqual(len(result['trials']),2)
        for trial in result['trials']:
            for fold in trial['inner_folds']:
                self.assertLess(pd.Timestamp(fold['latest_train_label_end']),pd.Timestamp(fold['validation_start']))

    def test_outer_labels_cannot_affect_refit_predictions(self):
        frame,_=self.fixture()
        job=dict(names=['x'],folds=[dict(fold=1,tune=np.arange(60),inner=[],blocks=[dict(train=np.arange(60),validation=np.arange(80,85))])])
        chosen=dict(n_trials=1,parameters={})
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'tune_family',return_value=chosen),patch.object(study,'build_family',side_effect=lambda *args:DummyClassifier(strategy='prior')):
            study.run_family_study(frame,job,'ExtraTrees',1,Path(tmp))
            first=pd.read_csv(Path(tmp)/'ExtraTrees_predictions.csv')
            frame.loc[80:84,'label']=2
            study.run_family_study(frame,job,'ExtraTrees',1,Path(tmp))
            second=pd.read_csv(Path(tmp)/'ExtraTrees_predictions.csv')
        np.testing.assert_array_equal(first.prediction,second.prediction)

    def test_acceptance_must_pass_both_original_controls(self):
        controls=[dict(candidate='a',mean_f1=.3,worst_f1=.2,mean_mcc=.1,folds=[dict(f1_macro=.3)]*4),
                  dict(candidate='b',mean_f1=.4,worst_f1=.35,mean_mcc=.2,folds=[dict(f1_macro=.4)]*4)]
        result=dict(candidate='new',mean_f1=.43,worst_f1=.34,mean_mcc=.3,folds=[dict(f1_macro=.43)]*4,pooled=dict(f1_macro=.43))
        with tempfile.TemporaryDirectory() as tmp:
            comparison=study.write_family_comparison([result],controls,Path(tmp))
            self.assertTrue(comparison[0]['comparisons'][0]['passed'])
            self.assertFalse(comparison[0]['development_screen_both_controls'])
            self.assertEqual(len(json.loads((Path(tmp)/'report.json').read_text())['controls']),2)


if __name__=='__main__':unittest.main()
