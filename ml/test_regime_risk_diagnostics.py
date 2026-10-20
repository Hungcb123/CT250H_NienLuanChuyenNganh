"""Rolling threshold causality, model isolation, and fixed-tree experiment tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import experiment_regime_risk as risk
import regime_risk_diagnostics as diag
from test_regime_risk import FakeModel, fixture


class DiagnosticsTests(unittest.TestCase):
    def test_current_and_future_scores_excluded(self):
        dates = pd.bdate_range('2020-01-01', periods=200)
        before = np.linspace(.01, .99, 200)
        after = before.copy()
        after[150:] = 100
        a = diag.rolling_thresholds(dates, before, dates[150:151])
        b = diag.rolling_thresholds(dates, after, dates[150:151])
        for window in diag.WINDOWS:
            key = f'rolling_{window}_threshold'
            np.testing.assert_array_equal(a[key], b[key])
            self.assertAlmostEqual(a[key][0], np.quantile(before[150-window:150], .9, method='higher'))

    def test_history_short_or_unsorted_rejected(self):
        dates = pd.bdate_range('2020-01-01', periods=121)
        with self.assertRaisesRegex(ValueError, '120'):
            diag.rolling_thresholds(dates, np.zeros(121), dates[100:101])
        with self.assertRaisesRegex(ValueError, 'sorted'):
            diag.rolling_thresholds(dates[::-1], np.zeros(121), dates[-1:])

    def test_monotonic_drift_does_not_guarantee_ten_percent(self):
        dates = pd.bdate_range('2020-01-01', periods=200)
        scores = np.arange(200) / 200
        thresholds = diag.rolling_thresholds(dates, scores, dates[120:])
        # A trending score can exceed its trailing p90 on EVERY day.
        self.assertTrue((scores[120:] > thresholds['rolling_120_threshold']).all())

    def test_fixed_mode_never_tunes_and_scores_current_model_history(self):
        frame = fixture()
        core, calibration = risk.split_calibration(frame, np.arange(500))
        job = dict(names=['x'], folds=[dict(fold=3, risk_inner=[], blocks=[dict(core=core, calibration=calibration, validation=np.arange(530, 580))])])
        with patch.object(risk, 'select_params', side_effect=AssertionError('Fixed mode must not tune')), patch.object(risk.exp.base, 'create_model', return_value=FakeModel()):
            records, audits = risk.run_policy('fixed_5pct', frame, job, {}, fixed_params=True)
        self.assertEqual(audits[0]['best_params'], diag.FIXED_PARAMS)
        self.assertIn('calibration_score_mean', audits[0])
        self.assertEqual(audits[0]['n_trials'], 0)
        for window in diag.WINDOWS:
            self.assertIn(f'rolling_{window}_threshold', records)
            self.assertIn(f'rolling_{window}_alarm', records)
        changed = frame.copy()
        changed.loc[531:, 'x'] = 100
        with patch.object(risk.exp.base, 'create_model', return_value=FakeModel()):
            future, _ = risk.run_policy('fixed_5pct', changed, job, {}, fixed_params=True)
        self.assertEqual(records.rolling_120_threshold.iloc[0], future.rolling_120_threshold.iloc[0])
        with tempfile.TemporaryDirectory() as tmp:
            risk.write_rolling_outputs(records, Path(tmp))
            result = pd.read_csv(Path(tmp) / 'threshold_comparison.csv')
            self.assertEqual(set(result.threshold_scheme), {'static', 'rolling_60', 'rolling_120'})

    def test_negative_ic_and_all_positive_days_are_not_false_negatives(self):
        frame = fixture(40).iloc[:10].copy()
        frame['future_return'] = np.linspace(-.1, .1, 10)
        frame['risk_score'] = np.linspace(0, 1, 10)
        frame['common_bear'] = frame.future_return < -.05
        frame['alarm'] = [True] + [False] * 9
        frame['policy'], frame['outer_fold'], frame['refit_block'] = 'vol_1sigma', 3, 1
        result = diag.fold_diagnostics(frame)
        self.assertAlmostEqual(result.spearman_score_vs_forward_loss.iloc[0], -1)
        runs = diag.event_runs(frame, frame.Date)
        self.assertEqual(runs.n_positive_days.sum(), 3)
        self.assertEqual(runs.n_static_alarm_hits.sum(), 1)
        index = frame[['Date']].assign(Price=100 + np.arange(10))
        with tempfile.TemporaryDirectory() as tmp:
            diag.write_diagnostics(frame, [dict(policy='vol_1sigma', outer_fold=3, refit_block=1)], index, tmp)
            positive = pd.read_csv(Path(tmp) / 'fold3_positive_days.csv')
            self.assertEqual(len(positive), 3)
            self.assertEqual(positive.static_false_negative.sum(), 2)
            self.assertTrue((Path(tmp) / 'fold3_price_diagnostics.png').exists())

    def test_audit_fixed_mode_never_fits_and_metadata_truthful(self):
        reference = risk.labels.ROOT / 'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():
            self.skipTest('Local reviewed snapshot unavailable')
        with tempfile.TemporaryDirectory() as tmp, patch.object(risk, 'run_policy', side_effect=AssertionError('Audit must not fit')):
            plan = risk.main(['--reference-report', str(reference), '--fixed-params', '--audit-only', '--output-dir', str(Path(tmp) / 'audit')])
        self.assertEqual(plan['parameter_mode'], 'fixed_shallow')
        self.assertEqual(plan['rolling_windows'], [60, 120])
        self.assertEqual(plan['fixed_params']['max_depth'], 3)


if __name__ == '__main__':
    unittest.main()


class FullRiskOrchestrationTest(unittest.TestCase):
    def test_full_fixed_pipeline_with_fake_models_writes_all_diagnostics(self):
        reference = risk.labels.ROOT / 'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():
            self.skipTest('Local reviewed snapshot unavailable')
        with tempfile.TemporaryDirectory() as tmp, patch.object(risk, 'select_params', side_effect=AssertionError('No tuning in fixed mode')), patch.object(risk.exp.base, 'create_model', side_effect=lambda *args: FakeModel()):
            output = Path(tmp) / 'out'
            risk.main(['--reference-report', str(reference), '--fixed-params', '--output-dir', str(output)])
            comparison = pd.read_csv(output / 'threshold_comparison.csv')
            self.assertEqual(len(comparison), 3 * 3 * 5)
            self.assertTrue((output / 'diagnostics/refit_drift.csv').exists())
            self.assertTrue((output / 'fold3_feature_context.csv').exists())
            self.assertIn('fixed_shallow', (output / 'comparison.md').read_text())
            drift = pd.read_csv(output / 'diagnostics/refit_drift.csv')
            self.assertFalse(drift[['calibration_score_mean', 'prediction_score_mean']].isna().any().any())
