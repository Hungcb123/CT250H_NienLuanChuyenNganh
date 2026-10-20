import unittest
import numpy as np
import pandas as pd
import experiment_regime_expert_selection as study


class ExpertSelectionTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2020-01-01',periods=220)
        rows=pd.DataFrame(dict(Date=dates[:180],label_end_date=dates[20:200],label=np.arange(180)%3))
        for name in study.POOl:rows[name]=1
        rows['density_all']=rows.label
        return rows,dates

    def test_known_past_quality_can_select_different_expert(self):
        rows,dates=self.fixture()
        name,audit=study.select_past_expert(rows,dates[200])
        self.assertEqual(name,'density_all')
        self.assertEqual(audit['n'],126)
        self.assertLess(pd.Timestamp(audit['latest_label_end']),dates[200])

    def test_unknown_outcomes_cannot_change_selection(self):
        rows,dates=self.fixture()
        first,info=study.select_past_expert(rows,dates[180])
        rows.loc[rows.label_end_date>=dates[180],'label']=1
        second,other=study.select_past_expert(rows,dates[180])
        self.assertEqual(first,second);self.assertEqual(info,other)

    def test_class_history_and_warmup_fall_back_to_original(self):
        rows,dates=self.fixture()
        self.assertEqual(study.select_past_expert(rows.iloc[:50],dates[200])[0],'legacy_equal')
        rows['label']=1
        self.assertEqual(study.select_past_expert(rows,dates[200])[0],'legacy_equal')

    def test_no_margin_means_no_switch(self):
        rows,dates=self.fixture()
        for name in study.POOl:rows[name]=rows.label
        self.assertEqual(study.select_past_expert(rows,dates[200])[0],'legacy_equal')

    def test_delayed_selector_uses_only_prior_rows_and_holds_expert(self):
        rows,dates=self.fixture()
        base=rows.copy();base['majority']=1
        matrices={name:np.eye(3)[rows[name].to_numpy()] for name in study.POOl}
        prediction,choices=study.delayed_expert_predictions(base,matrices,dates)
        self.assertEqual(len(prediction),len(rows))
        self.assertTrue((prediction[:140]==1).all())
        for choice in choices:
            if choice['latest_label_end']:
                self.assertLess(pd.Timestamp(choice['latest_label_end']),pd.Timestamp(choice['Date']))


if __name__=='__main__':unittest.main()
