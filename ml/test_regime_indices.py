import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import experiment_regime_indices as study
import prepare_regime_indices as prepare


class IndexTests(unittest.TestCase):
    def test_provider_alias_and_close_only_validation(self):
        payload=[dict(symbol='VNMIDCAP',t=[1577984400],c=[100.],o=[0.])]
        frame=prepare.close_response(payload,'vci','VNMIDCAP','2020-01-01','2020-01-31')
        self.assertEqual(frame.Close.iloc[0],100.)
        self.assertEqual(list(frame),['Date','Close'])
        with self.assertRaisesRegex(ValueError,'symbol'):
            prepare.close_response(payload,'vci','VNSMALLCAP','2020-01-01','2020-01-31')
        payload[0]['c']=[0.]
        with self.assertRaisesRegex(ValueError,'Invalid'):
            prepare.close_response(payload,'vci','VNMIDCAP','2020-01-01','2020-01-31')

    def test_no_prelaunch_fill_and_no_future_feature_effect(self):
        n=200
        index=pd.DataFrame(dict(Date=pd.bdate_range('2010-01-01',periods=n),Price=100+np.sin(np.arange(n)/10)))
        groups={symbol:pd.DataFrame(dict(Date=index.Date.iloc[40:].to_numpy(),Close=200+np.sin(np.arange(n-40)/10))) for symbol in study.SYMBOLS}
        before=study.index_features(index,groups)
        self.assertTrue(before[study.NAMES].iloc[:40].isna().all().all())
        changed={s:f.copy() for s,f in groups.items()}
        for f in changed.values():f.loc[f.Date>=index.Date.iloc[150],'Close']*=2
        after=study.index_features(index,changed)
        pd.testing.assert_frame_equal(before.iloc[:150],after.iloc[:150])
        # A gap invalidates windows rather than silently filling prices.
        gap={s:f.loc[f.Date!=index.Date.iloc[100]].copy() for s,f in groups.items()}
        result=study.index_features(index,gap)
        self.assertTrue(result.VN30_SpreadROC20.iloc[100:121].isna().all())

    def test_real_snapshot_hash_and_frozen_dates(self):
        reference=study.study.risk.labels.ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists() or not study.INDEX_DIR.exists():self.skipTest('Snapshot missing')
        args=study.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        candidates,index,plan=study.prepare(args)
        self.assertEqual(len(candidates),4)
        expected=None
        for _,_,_,frame,job,names in candidates:
            dates=np.concatenate([frame.Date.iloc[b['validation']].to_numpy() for outer in job['folds'] for b in outer['blocks']])
            self.assertEqual(len(dates),1560)
            if expected is None:expected=dates
            else:np.testing.assert_array_equal(dates,expected)
