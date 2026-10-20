"""Startup/daily catch-up with database serialization and cached request responses."""
from datetime import datetime
import hashlib
import json
import logging
import threading
from zoneinfo import ZoneInfo

import psycopg

from regime_live_data import completed_session, live_completed_features, SOURCE_POLICY

log = logging.getLogger(__name__)


class DailyRegimeRuntime:
    def __init__(self, worker, store, *, retry_seconds=900, poll_seconds=60, clock=None):
        self.worker, self.store = worker, store
        self.retry_seconds, self.poll_seconds = retry_seconds, poll_seconds
        self.clock = clock or (lambda: datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')))
        worker.feature_loader = lambda directory: live_completed_features(directory, store.seed_dir)
        worker.policy = dict(worker.policy, live_source_policy=SOURCE_POLICY,
                             live_feature_code_sha256=hashlib.sha256(__import__('pathlib').Path(__import__('regime_live_data').__file__).read_bytes()).hexdigest())
        self.stream_key = hashlib.sha256(json.dumps(worker.policy, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.lock_key = int(self.stream_key[:15], 16)
        self.stop = threading.Event()
        self.thread = None
        self.state = dict(status='DAILY_UPDATE_PENDING', session=None)

    def cached(self, now=None, connection=None):
        expected = completed_session(now or self.clock())
        def read(conn):
            row = conn.execute('SELECT response FROM ml_regime_predictions WHERE stream_key=%s AND session_date=%s AND bundle_sha256=%s',
                               (self.stream_key, expected, self.worker.bundle_hash)).fetchone()
            return row[0] if row else None
        if connection is not None:
            return read(connection)
        with psycopg.connect(self.worker.ledger.dsn, connect_timeout=5) as conn:
            return read(conn)

    def refresh(self, now=None):
        now = now or self.clock()
        expected = completed_session(now)
        # Session lock spans download, staging and publication across worker instances.
        with psycopg.connect(self.worker.ledger.dsn, connect_timeout=5, autocommit=True) as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(%s)', (self.lock_key,)).fetchone()[0]:
                return None
            try:
                existing = self.cached(now, conn)
                if existing:
                    self.state = dict(status='READY', session=existing['session'], cached=True)
                    return existing
                self.state = dict(status='SYNCING', session=expected.isoformat())
                snapshot = self.store.sync(expected)
                self.worker.data_dir = snapshot
                self.state = dict(status='PREDICTING', session=expected.isoformat())
                result = self.worker.predict(now=now)
                self.state = dict(status='READY', session=result['session'], cached=False)
                log.info('Daily regime prediction published for session %s', result['session'])
                return result
            finally:
                conn.execute('SELECT pg_advisory_unlock(%s)', (self.lock_key,))

    def run(self):
        while not self.stop.is_set():
            delay = self.poll_seconds
            try:
                self.refresh()
            except Exception as error:
                code = str(error)
                allowed = {'STALE_OR_INCOMPLETE_SESSION', 'MISSING_WEEKDAY_SESSION', 'REFIT_REQUIRED',
                           'LIVE_DATA_AHEAD_OF_COMPLETED_SESSION'}
                self.state = dict(status=code if code in allowed else 'DAILY_UPDATE_FAILED',
                                  session=completed_session(self.clock()).isoformat(), error_type=type(error).__name__)
                log.exception('Daily regime update failed; will retry in %s seconds', self.retry_seconds)
                delay = self.retry_seconds
            self.stop.wait(delay)

    def start(self):
        self.thread = threading.Thread(target=self.run, name='regime-daily-update', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
