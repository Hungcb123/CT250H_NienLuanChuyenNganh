"""Regression checks for adaptive target semantics and causal replay."""
import unittest

import numpy as np
import pandas as pd

import experiment_regime_dynamic_experts as study


class DynamicTargetIntegrationTests(unittest.TestCase):
    def test_same_return_atoms_change_class_with_known_market_volatility(self):
        points = np.array([[-.04, 0., .04], [-.04, 0., .04]])
        mass = study.dynamic_quantile_mass(points, [1/3]*3, [-.02, -.08], [.02, .08])
        np.testing.assert_allclose(mass, [[1/3, 1/3, 1/3], [0., 1., 0.]])

    def test_fixed_boundaries_reproduce_original_quadrature_including_equality(self):
        points = np.array([[np.log(.95), 0., np.log(1.05)], [-.2, .01, .2]])
        weights = [.2, .6, .2]
        expected, _ = study.density.quantile_class_mass(points, weights)
        actual = study.dynamic_quantile_mass(points, weights, np.full(2, np.log(.95)), np.full(2, np.log(1.05)))
        np.testing.assert_allclose(actual, expected)
        np.testing.assert_allclose(actual[0], [0., 1., 0.])

    def test_future_price_changes_outcome_but_never_current_threshold(self):
        rng = np.random.default_rng(7)
        dates = pd.bdate_range('2020-01-01', periods=140)
        index = pd.DataFrame({'Date': dates, 'Price': 100*np.exp(np.cumsum(rng.normal(0, .004, len(dates))))})
        original = study.labels.build_label_book(index)
        changed = index.copy()
        changed.loc[81:, 'Price'] *= 1.5
        altered = study.labels.build_label_book(changed)
        np.testing.assert_allclose(original.horizon_sigma.iloc[:81], altered.horizon_sigma.iloc[:81], equal_nan=True)
        self.assertNotEqual(original.vol_label.iloc[80], altered.vol_label.iloc[80])

    def test_unmatured_dynamic_labels_cannot_change_selector_decisions(self):
        dates = pd.bdate_range('2020-01-01', periods=240)
        base = pd.DataFrame({'Date': dates[:220], 'label_end_date': dates[20:], 'label': np.arange(220)%3})
        scores = {name: np.tile([0., 1., 0.], (220, 1)) for name in study.selector.POOl}
        scores['density_all'] = np.eye(3)[base.label.to_numpy()]
        expected, _ = study.selector.delayed_expert_predictions(base, scores, dates)
        end = 190
        prefix = base.iloc[:end].copy()
        prefix.loc[prefix.label_end_date >= prefix.Date.iloc[-1], 'label'] = 99
        actual, _ = study.selector.delayed_expert_predictions(prefix, {k: v[:end] for k, v in scores.items()}, dates[:end])
        np.testing.assert_array_equal(actual, expected[:end])


if __name__ == '__main__':
    unittest.main()
