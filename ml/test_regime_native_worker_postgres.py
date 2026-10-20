"""Exercise actual frozen model, feature builder and PostgreSQL publication."""
from datetime import datetime
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
from zoneinfo import ZoneInfo

import numpy as np

try:
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from serve_regime_shock import NativeRegimeWorker
except ImportError:
    psycopg = None


@unittest.skipUnless(psycopg and os.environ.get('REGIME_TEST_DSN'), 'Requires real PostgreSQL integration DSN')
class NativeWorkerPostgresTests(unittest.TestCase):
    def test_real_frozen_model_roundtrip_restart_and_freshness(self):
        root = Path(__file__).resolve().parent
        artifact = root/'artifacts/regime_shock_candidate_20261019T090555_259289Z'
        schema = 'native_worker_test_'+uuid.uuid4().hex
        base = os.environ['REGIME_TEST_DSN']
        dsn = make_conninfo(base, options='-csearch_path='+schema)
        with psycopg.connect(base) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            with psycopg.connect(dsn) as conn:
                conn.execute((root.parent/'backend/src/main/resources/db/migration/V8__regime_prediction_ledger.sql').read_text())
            now = datetime(2026, 10, 1, 16, 0, tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
            worker = NativeRegimeWorker(artifact, root/'data/research/brokers_2010_20261001_reviewed', dsn)
            result = worker.predict(now=now)
            expected = json.loads((artifact/'preview.json').read_text())
            np.testing.assert_allclose(result['class_scores'], expected['class_scores'], atol=1e-12)
            restarted = NativeRegimeWorker(artifact, worker.data_dir, dsn)
            with patch.object(restarted.bundle, 'predict_components', side_effect=AssertionError('Duplicate re-inference')):
                self.assertEqual(result, restarted.predict(now=now))
            with self.assertRaisesRegex(ValueError, 'STALE_OR_INCOMPLETE_SESSION'):
                worker.predict(now=datetime(2026,10,19,16,0,tzinfo=ZoneInfo('Asia/Ho_Chi_Minh')))
            with psycopg.connect(dsn) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_predictions').fetchone()[0], 1)
        finally:
            with psycopg.connect(base) as conn:
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__ == '__main__':
    unittest.main()
