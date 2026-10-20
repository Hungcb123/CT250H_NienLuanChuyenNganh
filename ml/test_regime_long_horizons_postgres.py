"""Opt-in PostgreSQL publication/restart check for independent long horizons."""
import os
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from regime_long_horizons import MultiHorizonDailyRuntime

@unittest.skipUnless(os.environ.get('REGIME_TEST_DSN'),'Requires disposable PostgreSQL')
class LongHorizonPostgresTest(unittest.TestCase):
    def test_publication_restart_isolation_and_cached_requests(self):
        base=os.environ['REGIME_TEST_DSN']
        schema='long_horizon_test_'+uuid.uuid4().hex
        with psycopg.connect(base) as conn: conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        dsn=make_conninfo(base,options='-csearch_path='+schema,client_encoding='UTF8')
        try:
            root=Path(__file__).resolve().parent.parent
            with psycopg.connect(dsn) as conn:
                conn.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
                conn.execute((root/'backend/src/main/resources/db/migration/V10__allocation_preferences.sql').read_text())
                conn.execute("INSERT INTO users VALUES (1),(2)")
                conn.execute("INSERT INTO allocation_preferences(user_id,mode,horizon_sessions) VALUES (1,'TAA',60),(2,'SAA',120)")
            runtime=object.__new__(MultiHorizonDailyRuntime)
            runtime.worker=SimpleNamespace(ledger=SimpleNamespace(dsn=dsn))
            runtime.store=SimpleNamespace(sync=Mock(return_value=Path('/mock-snapshot')))
            runtime.lock_key=314159
            now=datetime(2026,10,19,16,tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
            runtime.clock=lambda:now
            def fit(snapshot,horizon,expected): return dict(horizon_sessions=horizon,session=expected.isoformat(),status='READY')
            with patch('regime_long_horizons.fit_forecast',side_effect=fit) as infer:
                for horizon in (60,120): runtime.refresh_horizon(horizon,now)
                self.assertEqual(infer.call_count,2)
            runtime.store.sync=Mock(side_effect=AssertionError('duplicate source fetch'))
            with patch('regime_long_horizons.fit_forecast',side_effect=AssertionError('duplicate training')):
                for horizon in (60,120):
                    runtime.refresh_horizon(horizon,now)
                    self.assertEqual(runtime.cached_horizon(horizon,now)['horizon_sessions'],horizon)
            with psycopg.connect(dsn) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM ml_long_horizon_predictions').fetchone()[0],2)
                self.assertEqual(conn.execute('SELECT mode,horizon_sessions FROM allocation_preferences WHERE user_id=1').fetchone(),('TAA',60))
                self.assertEqual(conn.execute('SELECT mode,horizon_sessions FROM allocation_preferences WHERE user_id=2').fetchone(),('SAA',120))
        finally:
            with psycopg.connect(base) as conn: conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

if __name__=='__main__': unittest.main()
