"""Causality, fair comparisons and model orchestration; no market model fitting."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import experiment_regime_risk as risk


class FakeModel:
    def fit(self, X, y):
        self.classes_ = np.unique(y)
        return self

    def predict_proba(self, X):
        values = np.asarray(X)[:, 0]
        scores = .15 + .7 * (values - np.floor(values))
        if len(self.classes_) == 2:
            return np.column_stack([1 - scores, scores])
        return np.column_stack([scores, (1 - scores) * .6, (1 - scores) * .4])


def fixture(n=600):
    dates = pd.bdate_range('2010-01-01', periods=n)
    return pd.DataFrame(dict(Date=dates, label_end_date=dates + pd.offsets.BDay(20),
                             future_return=np.where(np.arange(n) % 5 == 0, -.08, .02),
                             label=np.arange(n) % 3, x=np.arange(n) * .137))


class RiskTests(unittest.TestCase):
    def test_calibration_purges_label_overlap(self):
        frame = fixture()
        core, cal = risk.split_calibration(frame, np.arange(500))
        self.assertEqual(len(cal), 100)
        self.assertLess(frame.label_end_date.iloc[core].max(), frame.Date.iloc[cal].min())
        self.assertFalse(np.intersect1d(core, cal).size)

    def test_future_values_do_not_change_split_or_threshold(self):
        frame = fixture()
        before = risk.split_calibration(frame, np.arange(500))
        changed = frame.copy()
        changed.loc[500:, ['x', 'future_return']] = 999
        after = risk.split_calibration(changed, np.arange(500))
        for a, b in zip(before, after):
            np.testing.assert_array_equal(a, b)
        self.assertEqual(risk.alarm_threshold(np.zeros(100)), 0)
        self.assertFalse((np.zeros(100) > risk.alarm_threshold(np.zeros(100))).any())

    def test_probability_column_uses_class_code(self):
        class Reordered:
            classes_ = np.array([2, 0, 1])
            def predict_proba(self, X):
                return np.tile([.1, .7, .2], (len(X), 1))
        np.testing.assert_allclose(risk.risk_score(Reordered(), np.zeros((3, 1)), 'fixed_5pct'), .7)
        np.testing.assert_allclose(risk.risk_score(Reordered(), np.zeros((3, 1)), 'binary_5pct'), .2)

    def test_metrics_counts(self):
        metrics = risk.binary_metrics([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertEqual((metrics['tp'], metrics['fp'], metrics['fn'], metrics['tn']), (1, 1, 1, 1))
        self.assertIsNone(risk.binary_metrics([0, 0], [0, 0])['precision'])

    def test_run_policy_same_model_calibration_and_outer_no_refit(self):
        frame = fixture()
        core, cal = risk.split_calibration(frame, np.arange(500))
        job = dict(names=['x'], folds=[dict(fold=1, risk_inner=[], blocks=[dict(core=core, calibration=cal, validation=np.arange(530, 580))])])
        models = []
        def factory(*args):
            model = FakeModel()
            models.append(model)
            return model
        with patch.object(risk, 'select_params', return_value=({}, {})), patch.object(risk.exp.base, 'create_model', side_effect=factory):
            records, audits = risk.run_policy('fixed_5pct', frame, job, {})
        self.assertEqual(len(models), 1)
        self.assertEqual(len(records), 50)
        expected = risk.alarm_threshold(risk.risk_score(models[0], frame.iloc[cal][['x']].to_numpy(), 'fixed_5pct'))
        self.assertAlmostEqual(audits[0]['threshold'], expected, places=5)
        np.testing.assert_array_equal(records.alarm, records.risk_score > records.threshold)

    def test_noncausal_block_rejected(self):
        frame = fixture()
        job = dict(names=['x'], folds=[dict(fold=1, risk_inner=[], blocks=[dict(core=np.arange(400), calibration=np.arange(400, 500), validation=np.arange(500, 550))])])
        with patch.object(risk, 'select_params', return_value=({}, {})):
            with self.assertRaisesRegex(ValueError, 'Noncausal'):
                risk.run_policy('fixed_5pct', frame, job, {})

    def test_equal_count_and_paired_bootstrap(self):
        rows = []
        for policy in risk.POLICIES:
            for fold in [1, 2]:
                for i in range(40):
                    rows.append(dict(policy=policy, Date=pd.Timestamp('2020-01-01') + pd.Timedelta(days=(fold-1)*40+i),
                                     outer_fold=fold, common_bear=i % 4 == 0, alarm=i < 4, risk_score=i / 40))
        records = pd.DataFrame(rows)
        equal = risk.equal_count_diagnostic(records)
        self.assertTrue(all(row['alarms'] == (8 if row['fold'] == 'all' else 4) for row in equal))
        intervals = risk.bootstrap_deltas(records, repeats=20)
        self.assertTrue(all(row['delta_low'] == row['delta_high'] == 0 for row in intervals))
        with tempfile.TemporaryDirectory() as tmp:
            risk.write_outputs(records, Path(tmp))
            self.assertTrue((Path(tmp) / 'comparison.md').exists())
            self.assertTrue((Path(tmp) / 'year_metrics.csv').exists())


if __name__ == '__main__':
    unittest.main()


class RiskPreflightTests(unittest.TestCase):
    def test_real_snapshot_preflight_and_audit_never_fit(self):
        reference = risk.labels.ROOT / 'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():
            self.skipTest('Reviewed local snapshot not available')
        args = risk.labels.parse_args(['--reference-report', str(reference), '--audit-only'])
        variants, _, plan = risk.prepare(args)
        self.assertFalse(plan['errors'])
        self.assertEqual([p for p, _, _ in variants], risk.POLICIES)
        reference_dates = variants[0][1].Date
        for policy, frame, job in variants:
            self.assertTrue(frame.Date.equals(reference_dates))
            for outer in job['folds']:
                core = frame.iloc[outer['blocks'][0]['core']].reset_index(drop=True)
                for train, valid in outer['risk_inner']:
                    self.assertLess(core.label_end_date.iloc[train].max(), core.Date.iloc[valid].min())
                    self.assertEqual(core.label.iloc[train].nunique(), 2 if policy == 'binary_5pct' else 3)
        with tempfile.TemporaryDirectory() as tmp, patch.object(risk, 'run_policy', side_effect=AssertionError('Audit must not fit')):
            risk.main(['--reference-report', str(reference), '--audit-only', '--output-dir', str(Path(tmp) / 'audit')])
