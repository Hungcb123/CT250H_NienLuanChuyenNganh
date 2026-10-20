"""Local model HTTP worker for Java; PostgreSQL owns the daily prediction state.

POST /v1/predict accepts no client features, dates, paths or model parameters.
Only server-reviewed market files and the locked candidate contract are used.
"""
from datetime import datetime, time, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import psycopg
from psycopg.conninfo import make_conninfo

from regime_postgres_ledger import PostgresRegimeLedger, PredictionConflict
from regime_shock_features import completed_shock_features
from regime_shock_native import ShockNativeBundle, shock_file_digest
from regime_shock_score_runtime import RECIPE_ID


ROOT = Path(__file__).resolve().parent


class NativeRegimeWorker:
    def __init__(self, artifact, data_dir, dsn):
        self.artifact, self.data_dir = Path(artifact), Path(data_dir)
        checksums = json.loads((self.artifact/'checksums.json').read_text())
        for filename, digest in checksums.items():
            path = (self.artifact/filename).resolve()
            if self.artifact.resolve() not in path.parents or shock_file_digest(path) != digest:
                raise ValueError('Candidate checksum mismatch')
        self.contract = json.loads((self.artifact/'contract.json').read_text())
        # Training forecast archives are provenance, not serving dependencies.
        # Verify locked Python sources relative to this checkout for relocation.
        for filename, digest in {**self.contract['source_receipts'], **self.contract['provenance']}.items():
            if not filename.endswith('.py'):
                continue
            if '/ml/' not in filename.replace('\\', '/'):
                raise ValueError('Unsupported source receipt path')
            relative = filename.replace('\\', '/').split('/ml/', 1)[1]
            resolved = (ROOT/relative).resolve()
            if ROOT not in resolved.parents or shock_file_digest(resolved) != digest:
                raise ValueError('Frozen inference source changed')
        self.feature_loader = completed_shock_features
        self.bundle = ShockNativeBundle(self.artifact/'native')
        self.bundle_hash = shock_file_digest(self.artifact/'native/bundle.json')
        self.ledger = PostgresRegimeLedger(dsn)
        self.policy = dict(asset='VNINDEX', mode='live', candidate_id=self.contract['candidate_id'],
                           recipe_id=RECIPE_ID, parameters=self.contract['fusion_parameters'],
                           serving_version=os.environ.get('REGIME_POLICY_VERSION', 'postgres-net-v1'),
                           feature_code_sha256=shock_file_digest(ROOT/'regime_shock_features.py'))

    def predict(self, now=None):
        now = now or datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))
        frame, _ = self.feature_loader(self.data_dir)
        session = frame.Date.iloc[-1].date()
        expected = now.date()
        if now.timetz().replace(tzinfo=None) < time(15, 30):
            expected -= timedelta(days=1)
        while expected.weekday() >= 5:
            expected -= timedelta(days=1)
        # Conservative weekday rule: a holiday without an explicit reviewed
        # calendar is unavailable, never silently advertised as a current call.
        if session != expected:
            raise ValueError('STALE_OR_INCOMPLETE_SESSION')
        start = np.flatnonzero(frame.Date.eq(self.bundle.meta['boundary']))
        if len(start) != 1 or len(frame)-1 < start[0] or len(frame)-1-start[0] >= 63:
            raise ValueError('REFIT_REQUIRED')
        fields = list(dict.fromkeys(n for item in self.bundle.meta['models'] for n in item['features']))
        row = frame.iloc[[-1]]
        metadata = dict(session=str(session), features={n: None if not np.isfinite(row[n].iloc[0]) else float(row[n].iloc[0]) for n in fields},
                        horizon_sigma=float(row.horizon_sigma.iloc[0]))
        digest = hashlib.sha256(json.dumps(metadata, sort_keys=True, allow_nan=False).encode()).hexdigest()
        previous = str(frame.Date.iloc[-2].date())
        def compute():
            parts = self.bundle.predict_components({n: row[n].to_numpy() for n in fields}, row.horizon_sigma.to_numpy())
            return {name: score[0] for name, score in parts.items()}
        return self.ledger.publish(self.policy, str(session), previous, digest, self.bundle_hash, compute)


def run_native_regime_server():
    artifact = os.environ.get('REGIME_ARTIFACT', str(ROOT/'artifacts/regime_shock_candidate_20261019T090555_259289Z'))
    data = os.environ.get('REGIME_DATA_DIR', str(ROOT/'data/research/brokers_2010_20261001_reviewed'))
    dsn = os.environ.get('REGIME_DATABASE_URL') or make_conninfo(
        host=os.environ.get('DB_HOST', 'localhost'), port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'equifolio'), user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'))
    token = os.environ.get('REGIME_API_TOKEN', '')
    host = os.environ.get('REGIME_HOST', '127.0.0.1')
    if host not in ['127.0.0.1', 'localhost', '::1'] and not token:
        raise SystemExit('REGIME_API_TOKEN is required for a non-loopback bind')
    worker = NativeRegimeWorker(artifact, data, dsn)
    daily = None
    if os.environ.get('REGIME_DAILY_ENABLED', 'true').lower() == 'true':
        import logging
        from regime_live_data import LiveDataStore
        from regime_long_horizons import MultiHorizonDailyRuntime
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        store = LiveDataStore(data, os.environ.get('REGIME_LIVE_DATA_DIR', str(ROOT/'data/live/regime')))
        daily = MultiHorizonDailyRuntime(worker, store, retry_seconds=int(os.environ.get('REGIME_RETRY_SECONDS', '900')))
        daily.start()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_json(self, status, payload):
            body = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if self.path != '/health':
                self.send_json(404, dict(status='NOT_FOUND')); return
            self.send_json(200, dict(status='MODEL_LOADED', model_id=worker.contract['candidate_id'],
                                     probability_calibrated=False, daily=daily.state if daily else None))

        def do_POST(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            if parsed.path != '/v1/predict':
                self.send_json(404, dict(status='NOT_FOUND')); return
            if token and not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+token):
                self.send_json(401, dict(status='UNAUTHORIZED')); return
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
                self.send_json(400, dict(status='REQUEST_BODY_NOT_ALLOWED')); return
            try:
                query = parse_qs(parsed.query)
                horizon = int(query.get('horizon', ['20'])[0])
                if horizon not in (20,60,120):
                    self.send_json(400, dict(status='UNSUPPORTED_HORIZON')); return
                if horizon != 20 and not daily:
                    self.send_json(503, dict(status='DAILY_UPDATE_PENDING')); return
                if daily:
                    result = daily.cached_horizon(horizon)
                    if result is None:
                        self.send_json(503, dict(status=daily.state['status'] if daily.state['status'] != 'READY' else 'DAILY_UPDATE_PENDING'))
                        return
                else:
                    result = worker.predict()
                self.send_json(200, result)
            except PredictionConflict:
                self.send_json(409, dict(status='PUBLISHED_SESSION_CONFLICT'))
            except ValueError as error:
                status = str(error) if str(error) in ['STALE_OR_INCOMPLETE_SESSION', 'REFIT_REQUIRED'] else 'INVALID_MODEL_INPUT'
                self.send_json(503, dict(status=status))
            except psycopg.Error:
                self.send_json(503, dict(status='LEDGER_UNAVAILABLE'))
            except Exception:
                self.send_json(503, dict(status='INFERENCE_UNAVAILABLE'))
    print('Native regime worker listening on '+host+':'+os.environ.get('REGIME_PORT', '8091'), flush=True)
    server = ThreadingHTTPServer((host, int(os.environ.get('REGIME_PORT', '8091'))), Handler)
    try:
        server.serve_forever()
    finally:
        if daily:
            daily.close()
        server.server_close()


if __name__ == '__main__':
    run_native_regime_server()
