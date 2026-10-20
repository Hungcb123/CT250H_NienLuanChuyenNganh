"""Stateful shock_shrink SCORE composition, independent of labels and reports.

This is the composition layer, not a trained feature-to-score model bundle.
All six inputs must come from separately validated mature component models.
The output is a class-balanced decision score, NOT a calibrated probability.
"""
from datetime import date
import hashlib
import json

import numpy as np


RECIPE = {
    'candidate': 'shock_shrink', 'schema': 1, 'horizon_sessions': 20,
    'label': 'log_return_vs_20day_sample_vol_times_sqrt20',
    'classes': ['bearish', 'sideway', 'bullish'],
    'density_weights': {'quantile': .28125, 'forest': .140625,
                        'magnitude': .140625, 'analog': .1875, 'shock': .25},
    'classifier': 'equal_selected_trend_and_risk',
    'smoothing': {'span': 5, 'current_weight': .5, 'ema_weight': .5},
    'score_semantics': 'class_balanced_decision_scores_not_probabilities',
}
RECIPE_ID = hashlib.sha256(json.dumps(RECIPE, sort_keys=True).encode()).hexdigest()


class ShockScoreRuntime:
    """One stream per asset/candidate/calendar; persist after successful sessions."""

    def __init__(self, stream_id):
        if not isinstance(stream_id, str) or not stream_id.strip():
            raise ValueError('A versioned model stream_id is required')
        self.stream_id = stream_id
        self.last_date = None
        self.ema = None

    @staticmethod
    def _score(value):
        score = np.asarray(value, dtype=float)
        if (score.shape != (3,) or not np.isfinite(score).all()
                or (score < 0).any() or not np.isclose(score.sum(), 1., atol=1e-10, rtol=0)):
            raise ValueError('Expected three finite nonnegative normalized scores')
        return score.copy()

    def predict(self, session, previous_market_session, components, parameters):
        """Caller supplies actual exchange predecessor, not previous prediction date.

        parameters=(density_weight, classifier_temperature, density_temperature)
        must be selected using mature data outside this serving layer.
        An omitted prediction for a market session resets EMA on the next call.
        """
        current = date.fromisoformat(session)
        previous = None if previous_market_session is None else date.fromisoformat(previous_market_session)
        if previous is not None and previous >= current:
            raise ValueError('Invalid market session predecessor')
        if self.last_date is not None and current <= date.fromisoformat(self.last_date):
            raise ValueError('Duplicate or out-of-order forecast; state unchanged')
        if set(components) != {'classifier', *RECIPE['density_weights']}:
            raise ValueError('Missing or unexpected component scores')
        parts = {name: self._score(value) for name, value in components.items()}
        p = np.asarray(parameters, dtype=float)
        if p.shape != (3,) or not np.isfinite(p).all() or not 0 <= p[0] <= 1 or (p[1:] <= 0).any():
            raise ValueError('Invalid fusion parameters')
        # Preserve the archived nesting and floating-point operation order.
        basic = .5*parts['quantile'] + .25*parts['forest'] + .25*parts['magnitude']
        analog = .75*basic + .25*parts['analog']
        density = .75*analog + .25*parts['shock']
        c = parts['classifier']**(1/p[1]); d = density**(1/p[2])
        if not np.isfinite(c).all() or not np.isfinite(d).all() or c.sum() <= 0 or d.sum() <= 0:
            raise ValueError('Fusion temperature caused invalid scores')
        raw = (1-p[0])*(c/c.sum()) + p[0]*(d/d.sum())
        contiguous = self.last_date is not None and previous_market_session == self.last_date
        ema = raw.copy() if not contiguous else raw/3 + (2/3)*self.ema
        result = .5*raw + .5*ema
        # Commit state only after validation/composition succeed.
        self.last_date, self.ema = session, ema
        return {'session': session, 'signal': int(result.argmax())-1,
                'class_scores': result.tolist(), 'calibrated_probability': None,
                'horizon_sessions': 20, 'ema_reset': not contiguous,
                'stream_id': self.stream_id, 'recipe_id': RECIPE_ID}

    def dump_state(self):
        return {'schema': 1, 'recipe_id': RECIPE_ID, 'stream_id': self.stream_id,
                'last_date': self.last_date,
                'ema': None if self.ema is None else self.ema.tolist()}

    def restore_state(self, state):
        if (set(state) != {'schema', 'recipe_id', 'stream_id', 'last_date', 'ema'}
                or state['schema'] != 1 or state['recipe_id'] != RECIPE_ID
                or state['stream_id'] != self.stream_id):
            raise ValueError('Incompatible persisted forecast state')
        if state['last_date'] is None:
            if state['ema'] is not None:
                raise ValueError('EMA without a session')
            latest, ema = None, None
        else:
            latest = date.fromisoformat(state['last_date']).isoformat()
            ema = self._score(state['ema'])
        self.last_date, self.ema = latest, ema
