"""Daily cache behavior without network or production databases."""
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from regime_daily_runtime import DailyRegimeRuntime
from regime_live_data import TZ


class Connection:
    def __init__(self, rows, locked=True): self.rows, self.locked = rows, locked
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, query, params):
        if 'pg_try_advisory_lock' in query: row = (self.locked,)
        elif 'pg_advisory_unlock' in query: row = (True,)
        else: row = (self.rows.get(params[1].isoformat()),) if params[1].isoformat() in self.rows else None
        return SimpleNamespace(fetchone=lambda: row)


class DailyRuntimeTests(unittest.TestCase):
    def runtime(self):
        worker = SimpleNamespace(policy=dict(asset='VNINDEX', mode='live'), bundle_hash='a'*64,
                                 ledger=SimpleNamespace(dsn='test'), predict=Mock())
        store = SimpleNamespace(seed_dir='seed', sync=Mock(return_value='snapshot'))
        return DailyRegimeRuntime(worker, store), worker, store

    def test_restart_uses_published_session_without_fetch_or_inference(self):
        runtime, worker, store = self.runtime()
        now = datetime(2026, 10, 19, 16, tzinfo=TZ)
        response = dict(session='2026-10-19', status='READY')
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({'2026-10-19': response})):
            self.assertEqual(runtime.refresh(now), response)
            self.assertEqual(runtime.cached(now), response)
        worker.predict.assert_not_called(); store.sync.assert_not_called()

    def test_new_completed_session_fetches_then_predicts(self):
        runtime, worker, store = self.runtime()
        now = datetime(2026, 10, 19, 16, tzinfo=TZ)
        worker.predict.return_value = dict(session='2026-10-19', status='READY')
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({})):
            result = runtime.refresh(now)
        store.sync.assert_called_once_with(now.date())
        worker.predict.assert_called_once_with(now=now)
        self.assertEqual(worker.data_dir, 'snapshot')
        self.assertEqual(result['status'], 'READY')

    def test_saturday_reuses_friday_and_monday_morning_does_not_create_a_session(self):
        runtime, worker, store = self.runtime()
        response = dict(session='2026-10-16', status='READY')
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({'2026-10-16': response})):
            for now in [datetime(2026,10,17,16,tzinfo=TZ),datetime(2026,10,19,9,tzinfo=TZ)]:
                self.assertEqual(runtime.refresh(now),response)
        worker.predict.assert_not_called();store.sync.assert_not_called()

    def test_second_worker_cannot_run_job_while_advisory_lock_is_held(self):
        runtime, worker, store = self.runtime()
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({}, locked=False)):
            self.assertIsNone(runtime.refresh(datetime(2026,10,19,16,tzinfo=TZ)))
        worker.predict.assert_not_called();store.sync.assert_not_called()

    def test_requests_only_read_and_never_infer_even_when_new_session_is_pending(self):
        runtime, worker, store = self.runtime()
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({})):
            self.assertIsNone(runtime.cached(datetime(2026,10,19,16,tzinfo=TZ)))
        worker.predict.assert_not_called();store.sync.assert_not_called()

    def test_download_failure_does_not_call_model(self):
        runtime, worker, store = self.runtime()
        store.sync.side_effect=OSError('API unavailable')
        with patch('regime_daily_runtime.psycopg.connect', return_value=Connection({})):
            with self.assertRaises(OSError):runtime.refresh(datetime(2026,10,19,16,tzinfo=TZ))
        worker.predict.assert_not_called()


if __name__ == '__main__': unittest.main()
