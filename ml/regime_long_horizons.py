"""Experimental long-horizon baselines; causal labels, daily DB publication.

These are distinct from the reviewed T+20 ensemble. No validation or calibrated
probability claim is made. GET/POST handlers only read published predictions.
"""
import hashlib
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb
from lightgbm import LGBMClassifier

from regime_daily_runtime import DailyRegimeRuntime
from regime_live_data import completed_session
from train_regime_v2 import build_feature_matrix, create_labels, load_market_data, HORIZONS

POLICY = 'experimental-close-etf-lgbm-v1'
CODE_HASH = hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes() + __import__('pathlib').Path(__import__('train_regime_v2').__file__).read_bytes()).hexdigest()


def fit_forecast(snapshot, horizon, expected):
    if horizon not in (60, 120):
        raise ValueError('UNSUPPORTED_HORIZON')
    index, _ = load_market_data(snapshot / 'VNINDEX.csv')
    etf, _ = load_market_data(snapshot / 'E1VFVN30.csv')
    frame, names = build_feature_matrix(index, etf, 'close-etf')
    frame = frame.loc[frame.Date <= pd.Timestamp(expected)].reset_index(drop=True)
    if frame.empty or frame.Date.iloc[-1].date() != expected:
        raise ValueError('STALE_OR_INCOMPLETE_SESSION')
    train = create_labels(frame, horizon, names)
    if len(train) < 500 or train.label.nunique() != 3:
        raise ValueError('INSUFFICIENT_MATURE_LABELS')
    if not (train.label_end_date <= pd.Timestamp(expected)).all():
        raise ValueError('IMMATURE_LABEL')
    latest = frame[names].iloc[[-1]]
    if not np.isfinite(latest.to_numpy()).all():
        raise ValueError('INVALID_MODEL_INPUT')
    model = LGBMClassifier(n_estimators=180, num_leaves=15, max_depth=5,
                          learning_rate=.03, min_child_samples=60,
                          reg_lambda=2., class_weight='balanced', random_state=42,
                          n_jobs=2, verbosity=-1, deterministic=True, force_col_wise=True)
    model.fit(train[names], train.label)
    scores = model.predict_proba(latest)[0]
    data_hash = hashlib.sha256((snapshot / 'VNINDEX.csv').read_bytes() + (snapshot / 'E1VFVN30.csv').read_bytes()).hexdigest()
    receipt = dict(policy=POLICY, code_sha256=CODE_HASH, horizon=horizon,
                   training_rows=len(train), training_last_session=str(train.Date.iloc[-1].date()),
                   max_label_end_date=str(train.label_end_date.max().date()), input_sha256=data_hash,
                   bear_threshold=HORIZONS[horizon]['bear_threshold'], bull_threshold=HORIZONS[horizon]['bull_threshold'])
    digest = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return dict(status='READY', asset='VNINDEX', mode='live', horizon_sessions=horizon,
                session=expected.isoformat(), model_id=f'{POLICY}-T{horizon}',
                class_scores=scores.tolist(), net_score=float(scores[2]-scores[0]),
                signal=int(np.argmax(scores))-1, ema_reset=False, bundle_sha256=digest,
                score_semantics='class_balanced_decision_scores_not_probabilities',
                experimental=True, validation_status='NOT_EVALUATED', training_receipt=receipt)


class MultiHorizonDailyRuntime(DailyRegimeRuntime):
    def cached_horizon(self, horizon, now=None):
        if horizon == 20:
            return self.cached(now)
        with psycopg.connect(self.worker.ledger.dsn, connect_timeout=5) as conn:
            row = conn.execute('SELECT response FROM ml_long_horizon_predictions WHERE policy=%s AND horizon_sessions=%s AND session_date=%s',
                               (POLICY+'-'+CODE_HASH, horizon, completed_session(now or self.clock()))).fetchone()
            return row[0] if row else None

    def refresh(self, now=None):
        now = now or self.clock()
        try:
            return super().refresh(now)
        finally:
            # A T+20 refit/error does not prevent independent long-horizon work.
            for horizon in (60,120):
                try:
                    self.refresh_horizon(horizon, now)
                except Exception:
                    logging.getLogger(__name__).exception('Long-horizon daily update failed: T+%s', horizon)

    def refresh_horizon(self, horizon, now):
        expected = completed_session(now)
        key = int(hashlib.sha256(f'{POLICY}-{CODE_HASH}-{horizon}'.encode()).hexdigest()[:15],16)
        with psycopg.connect(self.worker.ledger.dsn, connect_timeout=5, autocommit=True) as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(%s)', (key,)).fetchone()[0]:
                return
            try:
                if self.cached_horizon(horizon, now):
                    return
                # Serialize source sync with the T+20 runtime across processes.
                if not conn.execute('SELECT pg_try_advisory_lock(%s)', (self.lock_key,)).fetchone()[0]:
                    return
                try:
                    snapshot = self.store.sync(expected)
                finally:
                    conn.execute('SELECT pg_advisory_unlock(%s)', (self.lock_key,))
                result = fit_forecast(snapshot, horizon, expected)
                conn.execute('INSERT INTO ml_long_horizon_predictions(policy,horizon_sessions,session_date,response) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                             (POLICY+'-'+CODE_HASH, horizon, expected, Jsonb(result)))
            finally:
                conn.execute('SELECT pg_advisory_unlock(%s)', (key,))
