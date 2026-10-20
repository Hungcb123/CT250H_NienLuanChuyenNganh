import unittest
import numpy as np
import pandas as pd
import collect_regime_shadow_data as collect


class FreshSourceTests(unittest.TestCase):
    def fixture(self):
        dates=pd.bdate_range('2026-01-01',periods=50)
        base=pd.DataFrame(dict(Date=dates[:40],Price=np.arange(40)+100.))
        source=pd.DataFrame(dict(Date=dates,Close=np.arange(50)+100.))
        return base,source

    def test_extension_preserves_reviewed_prefix(self):
        base,source=self.fixture()
        result,agreement,errors=collect.reconcile(base,{'vci':source,'vnd':source.copy()})
        self.assertFalse(errors)
        np.testing.assert_array_equal(result.Close.iloc[:40],base.Price)
        self.assertEqual(len(result),50)

    def test_calendar_or_new_price_disagreement_quarantines(self):
        base,source=self.fixture()
        changed=source.copy();changed.loc[45,'Close']+=1
        result,_,errors=collect.reconcile(base,{'vci':source,'vnd':changed})
        self.assertIsNone(result);self.assertTrue(errors)
        changed=source.drop(index=45)
        result,_,errors=collect.reconcile(base,{'vci':source,'vnd':changed})
        self.assertIsNone(result);self.assertTrue(errors)

    def test_historical_revision_and_calendar_change_rejected(self):
        base,source=self.fixture()
        changed=source.copy();changed.loc[20,'Close']+=1
        result,_,errors=collect.reconcile(base,{'vci':source,'vnd':changed})
        self.assertIsNone(result);self.assertTrue(any('revision' in e for e in errors))
        result,_,errors=collect.reconcile(base,{'vci':source,'vnd':source.drop(index=20)})
        self.assertIsNone(result);self.assertTrue(any('calendar' in e for e in errors))
