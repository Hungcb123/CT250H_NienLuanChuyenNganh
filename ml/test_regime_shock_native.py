"""Native serialization, empirical threshold and maturity boundary checks."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from export_regime_shock_native import export_shock_block
from experiment_regime_analog_density import COMPACT
from regime_shock_native import ShockNativeBundle


class ShockNativeTests(unittest.TestCase):
    def test_empirical_mass_has_strict_tails_and_includes_all_leaf_observations(self):
        # Equality at +/-1 belongs to sideway. Two trees have different leaves.
        leaves = np.array([[1, 5], [1, 5], [1, 6], [2, 6]])
        valid = np.array([[1, 5], [2, 6]])
        actual = ShockNativeBundle._leaf_mass(leaves, valid, np.array([-2., -1., 1., 2.]),
                                              np.array([-1., -1.]), np.array([1., 1.]))
        np.testing.assert_allclose(actual, [[5/12, 7/12, 0], [0, 1/4, 3/4]])
        with self.assertRaises(ValueError):
            ShockNativeBundle._leaf_mass(leaves, np.array([[9, 5]]), np.arange(4.), [-1.], [1.])

    def test_complete_small_bundle_roundtrip_corruption_and_unmatured_rejection(self):
        rng = np.random.default_rng(17)
        names = list(COMPACT)
        train = pd.DataFrame(rng.normal(size=(60, len(names))), columns=names)
        train['shock_extra'] = rng.normal(size=len(train))
        train['Date'] = pd.bdate_range('2020-01-01', periods=len(train))
        train['label_end_date'] = train.Date + pd.offsets.BDay(20)
        train['label'] = np.tile([0, 1, 2], 20)
        train['future_log_return'] = np.choose(train.label, [-.2, 0., .2]) + rng.normal(0, .01, len(train))
        train['horizon_sigma'] = .1
        boundary = train.label_end_date.max()+pd.offsets.BDay(1)
        specs = {g: dict(names=names, parameters=dict(n_estimators=3, num_leaves=4,
                   min_child_samples=3, n_jobs=1, verbosity=-1, random_state=42)) for g in ['trend', 'risk']}
        specification = dict(quantile_levels=[.1, .5, .9], quantile_atom_weights=[.3, .4, .3],
                             parameters=dict(n_estimators=3, num_leaves=4, min_child_samples=3,
                                             n_jobs=1, verbosity=-1, objective='quantile'))
        forest = dict(n_estimators=3, max_depth=2, min_samples_leaf=3, n_jobs=1, random_state=42)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'native'
            bundle = export_shock_block(path, boundary, train, dict(trend=train, risk=train), specs,
                                        names, names+['shock_extra'], specification, forest,
                                        dict(test='synthetic'), seeds=[7])
            features = {name: train[name].to_numpy()[-4:] for name in names+['shock_extra']}
            first = bundle.predict_components(features, [.1]*4)
            second = ShockNativeBundle(path).predict_components(features, [.1]*4)
            self.assertEqual(set(first), {'classifier', 'quantile', 'forest', 'magnitude', 'analog', 'shock'})
            for name in first:
                np.testing.assert_array_equal(first[name], second[name])
                np.testing.assert_allclose(first[name].sum(axis=1), 1.)
            self.assertLess(pd.Timestamp(bundle.meta['training_receipts'][0]['latest_label_end']), boundary)
            # Change a forest payload without changing its metadata checksum.
            payload = next(path.glob('*.joblib'))
            with payload.open('ab') as stream:
                stream.write(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'payload mismatch'):
                ShockNativeBundle(path)
            with self.assertRaisesRegex(ValueError, 'strictly mature'):
                export_shock_block(Path(temporary)/'unmatured', train.label_end_date.max(), train,
                                   dict(trend=train, risk=train), specs, names, names+['shock_extra'],
                                   specification, forest, {}, seeds=[7])
            self.assertFalse((Path(temporary)/'unmatured').exists())


if __name__ == '__main__':
    unittest.main()
