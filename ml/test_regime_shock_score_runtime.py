"""Serving invariants for the frozen shock ensemble composition layer."""
import json
import unittest

import numpy as np

from regime_shock_score_runtime import RECIPE, ShockScoreRuntime


class ShockRuntimeTests(unittest.TestCase):
    def test_restart_matches_independent_batch_and_keeps_weekend_continuity(self):
        random = np.random.default_rng(8)
        names = ['classifier', *RECIPE['density_weights']]
        matrices = {name: random.dirichlet([2, 2, 2], size=6) for name in names}
        density = sum(RECIPE['density_weights'][name]*matrices[name]
                      for name in RECIPE['density_weights'])
        classifier = matrices['classifier']**(1/.75)
        classifier /= classifier.sum(axis=1, keepdims=True)
        density = density**(1/1.5); density /= density.sum(axis=1, keepdims=True)
        raw = .25*classifier + .75*density
        # Thursday, Friday, Monday, Tuesday, omitted Wednesday, Thursday, Friday.
        dates = ['2026-10-01', '2026-10-02', '2026-10-05', '2026-10-06', '2026-10-08', '2026-10-09']
        previous = ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-05', '2026-10-07', '2026-10-08']
        ema = []; runtime = ShockScoreRuntime('test-model-v1'); actual = []
        for i, session in enumerate(dates):
            smooth = raw[i] if i in [0, 4] else raw[i]/3 + 2*ema[-1]/3
            ema.append(smooth)
            state = json.loads(json.dumps(runtime.dump_state()))
            runtime = ShockScoreRuntime('test-model-v1'); runtime.restore_state(state)
            result = runtime.predict(session, previous[i], {k: v[i] for k, v in matrices.items()}, [.75, .75, 1.5])
            self.assertEqual(result['ema_reset'], i in [0, 4])
            self.assertIsNone(result['calibrated_probability'])
            actual.append(result['class_scores'])
        np.testing.assert_allclose(actual, .5*raw + .5*np.array(ema), atol=1e-14)

    def test_invalid_inputs_and_duplicate_cannot_advance_state(self):
        runtime = ShockScoreRuntime('test-model-v1')
        components = {name: [.2, .5, .3] for name in ['classifier', *RECIPE['density_weights']]}
        runtime.predict('2026-10-01', '2026-09-30', components, [.75, .75, 1])
        state = runtime.dump_state()
        for session, previous, parts, params in [
            ('2026-10-01', '2026-09-30', components, [.75, .75, 1]),
            ('2026-10-02', '2026-10-02', components, [.75, .75, 1]),
            ('2026-10-02', '2026-10-01', {**components, 'shock': [np.nan, 0, 1]}, [.75, .75, 1]),
            ('2026-10-02', '2026-10-01', {**components, 'label': 2}, [.75, .75, 1]),
            ('2026-10-02', '2026-10-01', components, [.75, 0, 1]),
        ]:
            with self.assertRaises(ValueError):
                runtime.predict(session, previous, parts, params)
            self.assertEqual(state, runtime.dump_state())
        other = ShockScoreRuntime('other-model-version')
        with self.assertRaises(ValueError):
            other.restore_state(state)
        self.assertIsNone(other.last_date)
        for patch in [{'ema': [0, 0, 0]}, {'recipe_id': 'wrong'}, {'last_date': 'invalid'}]:
            with self.assertRaises(ValueError):
                runtime.restore_state({**state, **patch})
            self.assertEqual(state, runtime.dump_state())


if __name__ == '__main__':
    unittest.main()
