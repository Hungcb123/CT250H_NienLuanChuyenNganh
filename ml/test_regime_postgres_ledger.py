"""Real PostgreSQL tests in a unique disposable schema, never app tables."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import time
import unittest
import uuid

import numpy as np

try:
    import psycopg
    from psycopg.conninfo import make_conninfo
    from psycopg import sql
    from regime_postgres_ledger import PostgresRegimeLedger, PredictionConflict
except ImportError:
    psycopg = None

from regime_shock_score_runtime import RECIPE, RECIPE_ID


@unittest.skipUnless(psycopg and os.environ.get('REGIME_TEST_DSN'), 'Set REGIME_TEST_DSN for isolated PostgreSQL integration tests')
class PostgresLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dsn = os.environ['REGIME_TEST_DSN']
        cls.schema = 'regime_test_'+uuid.uuid4().hex
        with psycopg.connect(cls.base_dsn) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        cls.dsn = make_conninfo(cls.base_dsn, options='-csearch_path='+cls.schema)
        path = Path(__file__).resolve().parents[1]/'backend/src/main/resources/db/migration/V8__regime_prediction_ledger.sql'
        with psycopg.connect(cls.dsn) as conn:
            conn.execute(path.read_text())

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.base_dsn) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute('TRUNCATE ml_regime_predictions,ml_regime_streams')
        self.ledger = PostgresRegimeLedger(self.dsn)
        self.policy = dict(recipe_id=RECIPE_ID, mode='historical', asset='VNINDEX',
                           candidate_id='test', parameters=[.5, 1., 1.])

    @staticmethod
    def components(values):
        return {name: values for name in ['classifier', *RECIPE['density_weights']]}

    def publish(self, day, prev, values, **kwargs):
        return self.ledger.publish(self.policy, day, prev, '1'*64, '2'*64,
                                   lambda: self.components(values), **kwargs)

    def test_restart_and_idempotency_preserve_original_response(self):
        first = self.publish('2026-10-01', '2026-09-30', [.3, .34, .36])
        np.testing.assert_allclose(first['class_scores'], [.3, .34, .36], atol=1e-14)
        other = PostgresRegimeLedger(self.dsn)
        repeated = other.publish(self.policy, '2026-10-01', '2026-09-30', '1'*64, '2'*64,
                                 lambda: self.fail('Duplicate must not infer again'))
        self.assertEqual(first, repeated)
        self.ledger = other
        second = self.publish('2026-10-02', '2026-10-01', [.5, .4, .1])
        expected_ema = np.array([.5, .4, .1])/3+2*np.array([.3, .34, .36])/3
        np.testing.assert_allclose(second['ema_scores'], expected_ema, atol=1e-14)
        np.testing.assert_allclose(second['class_scores'], .5*np.array([.5, .4, .1])+.5*expected_ema)
        self.assertFalse(second['ema_reset'])

    def test_concurrent_requests_compute_once(self):
        calls = []; lock = threading.Lock()
        def compute():
            with lock:
                calls.append(1)
            time.sleep(.05)
            return self.components([.3, .34, .36])
        def request(_):
            return self.ledger.publish(self.policy, '2026-10-01', '2026-09-30', '1'*64, '2'*64, compute)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(8)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(row == results[0] for row in results))

    def test_changed_inputs_and_out_of_order_rejected(self):
        first = self.publish('2026-10-02', '2026-10-01', [.3, .34, .36])
        for digest, bundle, previous in [('3'*64, '2'*64, '2026-10-01'), ('1'*64, '3'*64, '2026-10-01'), ('1'*64, '2'*64, '2026-09-30')]:
            with self.assertRaises(PredictionConflict):
                self.ledger.publish(self.policy, '2026-10-02', previous, digest, bundle, lambda: self.fail('No inference'))
        with self.assertRaises(PredictionConflict):
            self.publish('2026-10-01', '2026-09-30', [.3, .34, .36])
        self.assertEqual(first, self.publish('2026-10-02', '2026-10-01', [.3, .34, .36]))

    def test_failed_compute_and_invalid_scores_leave_no_state(self):
        def fail():
            raise RuntimeError('failed model')
        with self.assertRaises(RuntimeError):
            self.ledger.publish(self.policy, '2026-10-01', '2026-09-30', '1'*64, '2'*64, fail)
        with self.assertRaises(ValueError):
            self.publish('2026-10-01', '2026-09-30', [float('nan'), .3, .7])
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_streams').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_predictions').fetchone()[0], 0)

    def test_prediction_and_state_update_are_atomic(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute("CREATE FUNCTION reject_state() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test state failure'; END $$")
            conn.execute('CREATE TRIGGER fail_update BEFORE UPDATE ON ml_regime_streams FOR EACH ROW EXECUTE FUNCTION reject_state()')
        try:
            with self.assertRaises(psycopg.Error):
                self.publish('2026-10-01', '2026-09-30', [.3, .34, .36])
            with psycopg.connect(self.dsn) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_predictions').fetchone()[0], 0)
                self.assertEqual(conn.execute('SELECT count(*) FROM ml_regime_streams').fetchone()[0], 0)
        finally:
            with psycopg.connect(self.dsn) as conn:
                conn.execute('DROP TRIGGER fail_update ON ml_regime_streams')
                conn.execute('DROP FUNCTION reject_state()')

    def test_missing_session_resets_and_historical_stream_is_separate(self):
        self.publish('2026-10-01', '2026-09-30', [.3, .34, .36])
        result = self.publish('2026-10-05', '2026-10-02', [.5, .4, .1])
        self.assertTrue(result['ema_reset'])
        np.testing.assert_allclose(result['class_scores'], [.5, .4, .1])
        self.policy = dict(self.policy, mode='live')
        live = self.publish('2026-10-01', '2026-09-30', [.1, .2, .7])
        self.assertNotEqual(live['stream_id'], result['stream_id'])


if __name__ == '__main__':
    unittest.main()
