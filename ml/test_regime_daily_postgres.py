"""Real frozen model and PostgreSQL daily-cache restart test (opt-in DSN)."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import numpy as np
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from serve_regime_shock import NativeRegimeWorker
from regime_daily_runtime import DailyRegimeRuntime
from regime_live_data import TZ, live_completed_features
from regime_shock_features import completed_shock_features


@unittest.skipUnless(os.environ.get('REGIME_TEST_DSN'), 'Requires disposable PostgreSQL REGIME_TEST_DSN')
class DailyPostgresTests(unittest.TestCase):
    def test_original_feature_parity_publication_restart_and_no_duplicate_compute(self):
        root=Path(__file__).resolve().parent
        seed=root/'data/research/brokers_2010_20261001_reviewed'
        artifact=root/'artifacts/regime_shock_candidate_20261019T090555_259289Z'
        schema='daily_regime_test_'+uuid.uuid4().hex
        base=os.environ['REGIME_TEST_DSN']
        with psycopg.connect(base) as conn:conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        dsn=make_conninfo(base,options='-csearch_path='+schema)
        try:
            with psycopg.connect(dsn) as conn:
                conn.execute((root.parent/'backend/src/main/resources/db/migration/V8__regime_prediction_ledger.sql').read_text())
            with tempfile.TemporaryDirectory() as temp:
                snapshot=Path(temp)
                for name in ['VNINDEX.csv','E1VFVN30.csv']:shutil.copyfile(seed/name,snapshot/name)
                for symbol in ['VN30','VNMID','VNSML']:
                    shutil.copyfile(root/'data/research/market_indices_20261001_v3'/(symbol+'.csv'),snapshot/(symbol+'.csv'))
                shutil.copyfile(root/'data/research/global_risk/sources/VIX_History.csv',snapshot/'VIX.csv')
                (snapshot/'VNINDEX_OHLCV.csv').write_text('Date,Open,High,Low,Close,Volume\n')
                original,_=completed_shock_features(seed)
                live,_=live_completed_features(snapshot,seed)
                for column in original.select_dtypes(include=[np.number]).columns:
                    np.testing.assert_allclose(live[column],original[column],rtol=0,atol=0,equal_nan=True,err_msg=column)
                worker=NativeRegimeWorker(artifact,seed,dsn)
                store=SimpleNamespace(seed_dir=seed,sync=Mock(return_value=snapshot))
                runtime=DailyRegimeRuntime(worker,store)
                now=datetime(2026,10,1,16,tzinfo=TZ)
                response=runtime.refresh(now)
                expected=json.loads((artifact/'preview.json').read_text())
                np.testing.assert_allclose(response['class_scores'],expected['class_scores'],atol=1e-12)
                restarted=NativeRegimeWorker(artifact,seed,dsn)
                repeated=DailyRegimeRuntime(restarted,store)
                with patch.object(store,'sync',side_effect=AssertionError('duplicate API fetch')),patch.object(restarted.bundle,'predict_components',side_effect=AssertionError('duplicate inference')):
                    self.assertEqual(response,repeated.refresh(now))
                with psycopg.connect(dsn) as conn:
                    self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_predictions').fetchone()[0],1)
        finally:
            with psycopg.connect(base) as conn:
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__=='__main__':unittest.main()
