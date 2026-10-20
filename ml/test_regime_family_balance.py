import unittest
import experiment_regime_family_balance as study


class BalancedSelectionTests(unittest.TestCase):
    def trial(self,number,value,weight='balanced'):
        return dict(number=number,value=value,state='COMPLETE',model_parameters={'class_weight':weight},inner_folds=[dict(latest_train_label_end='2020-01-01',validation_start='2020-01-02')])

    def test_selection_uses_only_best_balanced_inner_score(self):
        tuning=dict(trials=[self.trial(0,.9,None),self.trial(1,.3),self.trial(2,.4)])
        chosen=study.select_balanced_trial(tuning,'SVC')
        self.assertEqual(chosen['trial_number'],2)
        self.assertEqual(chosen['eligible_trials'],2)

    def test_ties_are_deterministic_by_trial_number(self):
        tuning=dict(trials=[self.trial(5,.4),self.trial(2,.4)])
        self.assertEqual(study.select_balanced_trial(tuning,'ExtraTrees')['trial_number'],2)

    def test_missing_balanced_trial_never_triggers_extra_search(self):
        with self.assertRaisesRegex(ValueError,'No balanced'):
            study.select_balanced_trial(dict(trials=[self.trial(0,.9,None)]),'SVC')

    def test_noncausal_inner_source_is_rejected(self):
        trial=self.trial(0,.4)
        trial['inner_folds'][0]['latest_train_label_end']='2020-01-02'
        with self.assertRaisesRegex(ValueError,'Noncausal'):
            study.select_balanced_trial(dict(trials=[trial]),'SVC')

    def test_catboost_weight_field_matches_saved_parameters(self):
        trial=self.trial(0,.4);trial['model_parameters']={'auto_class_weights':'Balanced'}
        self.assertEqual(study.select_balanced_trial(dict(trials=[trial]),'CatBoost')['trial_number'],0)


if __name__=='__main__':unittest.main()
