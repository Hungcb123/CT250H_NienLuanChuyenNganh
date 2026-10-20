"""Transactional daily score ledger. No mutation of frozen research helpers."""
from datetime import date
import hashlib
import json

import psycopg
from psycopg.types.json import Jsonb

from regime_shock_score_runtime import RECIPE_ID, ShockScoreRuntime


class PredictionConflict(ValueError):
    pass


class PostgresRegimeLedger:
    def __init__(self, dsn):
        self.dsn = dsn

    def publish(self, policy, session, previous_session, input_sha256, bundle_sha256, compute):
        """Lock the stream through inference and atomically commit prediction+EMA.

        Repeated equal inputs return the ORIGINAL response. Revised inputs/model
        for an already published session require a distinct versioned policy.
        compute() is called only for a new session and returns six components.
        """
        if policy.get('recipe_id') != RECIPE_ID or policy.get('mode') not in ['live', 'historical']:
            raise ValueError('Invalid versioned policy')
        current = date.fromisoformat(session)
        previous = date.fromisoformat(previous_session) if previous_session else None
        if previous is not None and previous >= current:
            raise ValueError('Invalid predecessor')
        for digest in [input_sha256, bundle_sha256]:
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Expected SHA256 fingerprint')
        key = hashlib.sha256(json.dumps(policy, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with psycopg.connect(self.dsn, connect_timeout=5, client_encoding='UTF8') as conn:
            conn.execute("SET LOCAL lock_timeout='15s'")
            conn.execute("INSERT INTO ml_regime_streams(stream_key,asset,mode,policy) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                         (key, policy['asset'], policy['mode'], Jsonb(policy)))
            last, state = conn.execute("SELECT last_session,state FROM ml_regime_streams WHERE stream_key=%s FOR UPDATE", (key,)).fetchone()
            existing = conn.execute("SELECT input_sha256,bundle_sha256,previous_market_session,response FROM ml_regime_predictions WHERE stream_key=%s AND session_date=%s", (key, current)).fetchone()
            if existing:
                if existing[:3] != (input_sha256, bundle_sha256, previous):
                    raise PredictionConflict('Published session has different inputs; use a new policy version')
                return existing[3]
            if last is not None and current <= last:
                raise PredictionConflict('Cannot append an out-of-order session')
            components = compute()
            runtime = ShockScoreRuntime(key)
            if state is not None:
                runtime.restore_state(state)
                if runtime.last_date != last.isoformat():
                    raise PredictionConflict('Stream date and EMA state disagree')
            cold = ShockScoreRuntime(key)
            raw = cold.predict(session, previous_session, components, policy['parameters'])['class_scores']
            result = runtime.predict(session, previous_session, components, policy['parameters'])
            stored_state = runtime.dump_state()
            result.update(status='READY', asset=policy['asset'], mode=policy['mode'],
                          model_id=policy['candidate_id'], raw_scores=raw, ema_scores=stored_state['ema'],
                          net_score=result['class_scores'][2]-result['class_scores'][0],
                          score_semantics='class_balanced_decision_scores_not_probabilities',
                          input_sha256=input_sha256, bundle_sha256=bundle_sha256,
                          independent_prospective_prediction=False)
            published = conn.execute("INSERT INTO ml_regime_predictions(stream_key,session_date,previous_market_session,input_sha256,bundle_sha256,raw_scores,ema_scores,final_scores,response) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING published_at",
                                     (key, current, previous, input_sha256, bundle_sha256, Jsonb(raw), Jsonb(stored_state['ema']), Jsonb(result['class_scores']), Jsonb(result))).fetchone()[0]
            result['published_at'] = published.isoformat()
            conn.execute("UPDATE ml_regime_predictions SET response=%s WHERE stream_key=%s AND session_date=%s", (Jsonb(result), key, current))
            conn.execute("UPDATE ml_regime_streams SET last_session=%s,state=%s WHERE stream_key=%s", (current, Jsonb(stored_state), key))
            return result
