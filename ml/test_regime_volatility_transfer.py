"""Calendar and dependence checks for asset-pooled continuous supervision."""
import unittest
import numpy as np
import pandas as pd
import experiment_regime_volatility_transfer as study


class VolatilityTransferTests(unittest.TestCase):
    def test_no_prelaunch_prices_and_horizon_survives_a_missing_session(self):
        calendar=pd.bdate_range('2020-01-01',periods=420)
        rng=np.random.default_rng(5)
        observations=pd.DataFrame({'Date':calendar[60:], 'Price':100*np.exp(np.cumsum(rng.normal(0,.01,360)))})
        observations=observations.loc[observations.Date!=calendar[230]]
        rows,_=study.build_volatility_panel(calendar,observations,'ETF')
        self.assertGreaterEqual(rows.Date.min(),calendar[60+59])
        positions=calendar.get_indexer(rows.Date)
        np.testing.assert_array_equal(rows.label_end_date.to_numpy(),calendar[positions+20].to_numpy())
        self.assertNotIn(calendar[230],rows.Date.to_list())

    def test_correlated_assets_share_unit_date_mass_and_exclude_unknown_targets(self):
        dates=pd.bdate_range('2020-01-01',periods=300)
        core=pd.DataFrame({'Date':dates[:250],'label_end_date':dates[20:270],
            'label':np.arange(250)%3,'target_z':np.arange(250)/100.,'symbol':'VNINDEX'})
        auxiliary=pd.concat([core.assign(symbol=s) for s in ['VN30','VNMID','ETF']],ignore_index=True)
        train,weights,prior,audit=study.volatility_training_panel(core,auxiliary,dates[220],core.Date,'extended_pooled')
        np.testing.assert_allclose(pd.Series(weights).groupby(train.Date).sum(),1.)
        self.assertLess(train.label_end_date.max(),dates[220])
        self.assertEqual(audit['n_target'],200)
        np.testing.assert_allclose(weights[train.symbol.eq('VNINDEX')],.5)
        changed=auxiliary.copy();changed.loc[changed.label_end_date>=dates[220],'target_z']=99.
        other,w,p,_=study.volatility_training_panel(core,changed,dates[220],core.Date,'extended_pooled')
        pd.testing.assert_frame_equal(train,other)
        np.testing.assert_array_equal(weights,w);np.testing.assert_array_equal(prior,p)


if __name__=='__main__':unittest.main()
