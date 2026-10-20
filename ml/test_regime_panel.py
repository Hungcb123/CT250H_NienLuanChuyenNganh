import unittest
import numpy as np
import pandas as pd

import experiment_regime_panel as study


class PanelTests(unittest.TestCase):
    def fixture(self):
        calendar=pd.bdate_range('2018-01-01',periods=400)
        target=pd.DataFrame(dict(Date=calendar[:280],label_end_date=calendar[20:300],label=np.arange(280)%3,symbol='VNINDEX'))
        first=target.copy();first['symbol']='VN30'
        second=target.iloc[::2].copy();second['symbol']='VNMID'
        return target,pd.concat([first,second],ignore_index=True),calendar

    def test_every_asset_label_must_mature_before_global_boundary(self):
        target,aux,cal=self.fixture()
        train,weights,audit=study.training_panel(target,aux,cal[240],'3y',True)
        self.assertTrue((train.label_end_date<cal[240]).all())
        self.assertTrue((train.Date<cal[240]).all())
        self.assertLess(pd.Timestamp(audit['auxiliary_latest_label_end']),cal[240])
        self.assertTrue(np.isfinite(weights).all())

    def test_auxiliary_outcomes_not_yet_known_cannot_affect_training(self):
        target,aux,cal=self.fixture()
        first,weights,audit=study.training_panel(target,aux,cal[240],'3y',True)
        aux.loc[aux.label_end_date>=cal[240],'label']=2
        second,other_weights,other=study.training_panel(target,aux,cal[240],'3y',True)
        pd.testing.assert_frame_equal(first,second)
        np.testing.assert_array_equal(weights,other_weights)
        self.assertEqual(audit,other)

    def test_base_date_mass_and_weighted_class_mass_are_controlled(self):
        target,aux,cal=self.fixture()
        train,weights,audit=study.training_panel(target,aux,cal[240],'3y',True)
        self.assertAlmostEqual(audit['base_mass'],audit['unique_dates'])
        mass=np.bincount(train.label.to_numpy(),weights=weights,minlength=3)
        np.testing.assert_allclose(mass,np.repeat(audit['unique_dates']/3,3))
        self.assertGreater(audit['n_auxiliary'],audit['n_target'])

    def test_target_only_costs_equal_standard_balanced_class_costs(self):
        target,aux,cal=self.fixture()
        train,weights,audit=study.training_panel(target,aux,cal[240],'expanding',False)
        counts=np.bincount(train.label,minlength=3)
        expected=len(train)/(3*counts[train.label.to_numpy()])
        np.testing.assert_allclose(weights,expected)
        self.assertEqual(audit['n_auxiliary'],0)

    def test_missing_source_day_does_not_compress_twenty_session_label(self):
        calendar=pd.bdate_range('2018-01-01',periods=310)
        prices=100*np.exp(.001*np.arange(310)+.01*np.sin(np.arange(310)/9))
        source=pd.DataFrame(dict(Date=calendar,Price=prices)).drop(index=250)
        rows,names=study.panel_features(calendar,source,'AUX')
        row=rows.loc[rows.Date==calendar[240]].iloc[0]
        self.assertEqual(row.label_end_date,calendar[260])
        self.assertAlmostEqual(row.future_return,prices[260]/prices[240]-1)
        self.assertFalse((rows.Date==calendar[250]).any())
        self.assertEqual(len(names),12)

    def test_relative_features_are_invariant_to_price_units(self):
        calendar=pd.bdate_range('2018-01-01',periods=310)
        price=100*np.exp(.0003*np.arange(310)+.04*np.sin(np.arange(310)/13))
        source=pd.DataFrame(dict(Date=calendar,Price=price))
        first,names=study.panel_features(calendar,source,'A')
        source.Price*=100
        second,_=study.panel_features(calendar,source,'B')
        np.testing.assert_allclose(first[names],second[names],atol=1e-5,rtol=1e-5)
        np.testing.assert_array_equal(first.label,second.label)

    def test_unlisted_history_is_not_filled(self):
        calendar=pd.bdate_range('2018-01-01',periods=310)
        source=pd.DataFrame(dict(Date=calendar[100:],Price=np.arange(210,dtype=float)+100))
        rows,_=study.panel_features(calendar,source,'NEW')
        self.assertFalse((rows.Date<calendar[159]).any())
        self.assertGreater(len(rows),0)


if __name__=='__main__':unittest.main()
