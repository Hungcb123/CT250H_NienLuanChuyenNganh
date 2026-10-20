"""Controlled experiments: feature causality and nested/refit isolation; no training."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

import experiment_regime as exp


def synthetic_frame(n=1500):
    dates = pd.bdate_range('2010-01-01', periods=n)
    price = 100 * np.exp(.25 * np.sin(np.arange(n) / 25) + np.arange(n) * .0001)
    return pd.DataFrame({'Date': dates, 'Close': price, 'Price': price})


class FeatureAndMetricTests(unittest.TestCase):
    def test_long_features_are_causal(self):
        original = synthetic_frame(500)
        before = exp.long_features(original)
        changed = original.copy()
        changed.loc[301:, 'Price'] *= 100
        pd.testing.assert_frame_equal(before.loc[:300], exp.long_features(changed).loc[:300])

    def test_formulas_and_warmup_are_explicit(self):
        frame = synthetic_frame(300)
        features = exp.long_features(frame)
        price = frame.Price.to_numpy()
        i = 280
        returns = np.diff(np.log(price))
        self.assertAlmostEqual(features.ROC60.iloc[i], (price[i] / price[i-60] - 1) * 100)
        self.assertAlmostEqual(features.ROC120.iloc[i], (price[i] / price[i-120] - 1) * 100)
        self.assertAlmostEqual(features.DistSMA200.iloc[i], (price[i] / price[i-199:i+1].mean() - 1) * 100)
        self.assertAlmostEqual(features.Drawdown252.iloc[i], (price[i] / price[i-251:i+1].max() - 1) * 100)
        self.assertAlmostEqual(features.HV20_60_Ratio.iloc[i], returns[i-20:i].std(ddof=1) / returns[i-60:i].std(ddof=1))
        expected = np.sqrt(np.mean(np.minimum(returns[i-60:i], 0) ** 2)) * np.sqrt(252) * 100
        self.assertAlmostEqual(features.DownsideHV60.iloc[i], expected)
        self.assertTrue(features.Drawdown252.iloc[:251].isna().all())
        flat = frame.assign(Price=100)
        flat_features = exp.long_features(flat)
        self.assertTrue(flat_features.HV20_60_Ratio.isna().all())
        self.assertEqual(flat_features.DownsideHV60.iloc[-1], 0)

    def test_error_counts_distinguish_false_alarm_rate_from_false_discovery(self):
        result = exp.bear_errors([[2, 3, 5], [7, 8, 9], [11, 12, 13]])
        self.assertEqual((result['bear_hits'], result['bear_false_alarms'], result['bear_missed']), (2, 18, 8))
        self.assertEqual(result['bear_precision'], .1)
        self.assertEqual(result['bear_recall'], .2)
        self.assertAlmostEqual(result['bear_false_alarm_rate'], 18 / 60)
        self.assertEqual(result['bear_false_discovery_rate'], .9)
        absent = exp.bear_errors([[0, 0, 0], [0, 5, 0], [0, 0, 5]])
        self.assertIsNone(absent['bear_recall'])
        self.assertIsNone(absent['bear_precision'])

    def test_refit_schedule_uses_market_sessions_not_sparse_eligible_rows(self):
        calendar = pd.bdate_range('2020-01-01', periods=150)
        keep = np.array([0, 10, 62, 64, 100, 126, 149])
        frame = pd.DataFrame({'Date': calendar[keep]})
        blocks = exp.refit_blocks(frame, np.arange(len(frame)), calendar, 63)
        self.assertEqual([b.tolist() for b in blocks], [[0, 1, 2], [3, 4], [5, 6]])

    def test_rolling_training_is_purged_by_label_end_and_calendar_years(self):
        frame = synthetic_frame()
        frame['label'] = np.arange(len(frame)) % 3
        frame['label_end_date'] = frame.Date.shift(-60)
        boundary = frame.Date.iloc[1300]
        indices = exp.training_indices(frame, boundary, '3y')
        train = frame.iloc[indices]
        self.assertTrue((train.Date >= boundary - pd.DateOffset(years=3)).all())
        self.assertTrue((train.label_end_date < boundary).all())
        expanding = exp.training_indices(frame, boundary, 'expanding')
        self.assertGreater(len(expanding), len(indices))


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        raw = synthetic_frame()
        raw[['Date', 'Close']].to_csv(self.root / 'VNINDEX.csv', index=False)
        features, names = exp.base.build_feature_matrix(raw)
        self.labeled = exp.base.create_labels(features, 20, names)
        folds = []
        for start in [600, 800, 1000, 1200]:
            folds.append({'validation_start': str(raw.Date.iloc[start].date()),
                          'validation_end': str(raw.Date.iloc[start+99].date()), 'n_validation': 100})
        report = {'mode': 'development_only', 'results': [{'horizon': 20, 'feature_set': 'close', 'validation_folds': folds}]}
        self.report_path = self.root / 'regime_v2_report.json'
        self.report_path.write_text(json.dumps(report))
        audit = {'inputs': {'VNINDEX': {'sha256': hashlib.sha256((self.root / 'VNINDEX.csv').read_bytes()).hexdigest()}}}
        (self.root / 'data_audit.json').write_text(json.dumps(audit))
        self.args = exp.parse_args(['--reference-report', str(self.report_path), '--data-dir', str(self.root),
                                   '--base-feature-set', 'close', '--train-windows', 'expanding',
                                   '--output-dir', str(self.root / 'out')])

    def test_all_variants_share_frozen_validation_dates_labels_and_training_dates(self):
        frames, jobs, plan = exp.prepare_experiment(self.args)
        self.assertFalse(plan['errors'])
        self.assertEqual(len(jobs), 4)
        for fold in range(4):
            for block in range(len(jobs[0]['folds'][fold]['blocks'])):
                reference = jobs[0]['folds'][fold]['blocks'][block]
                for job in jobs[1:]:
                    seen = job['folds'][fold]['blocks'][block]
                    np.testing.assert_array_equal(seen['validation'], reference['validation'])
                    np.testing.assert_array_equal(seen['train'], reference['train'])
            tuning = jobs[0]['folds'][fold]
            train = frames[20].iloc[tuning['tune']].reset_index(drop=True)
            outer_start = frames[20].Date.iloc[tuning['blocks'][0]['validation'][0]]
            self.assertLess(train.label_end_date.max(), outer_start)
            for inner_train, inner_validation in tuning['inner']:
                self.assertLess(train.label_end_date.iloc[inner_train].max(), train.Date.iloc[inner_validation[0]])

    def test_data_mutation_is_rejected_against_reference_hash(self):
        path = self.root / 'VNINDEX.csv'
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            exp.prepare_experiment(self.args)

    def test_missing_new_features_cannot_shrink_validation(self):
        features = exp.long_features(synthetic_frame())
        features.loc[600, 'ROC60'] = np.nan
        with patch.object(exp, 'long_features', return_value=features):
            with self.assertRaisesRegex(ValueError, 'missing on frozen validation'):
                exp.prepare_experiment(self.args)

    def test_frozen_fold_count_must_match(self):
        report = json.loads(self.report_path.read_text())
        report['results'][0]['validation_folds'][0]['n_validation'] = 101
        with self.assertRaisesRegex(ValueError, 'expected 101'):
            exp.freeze_reference(self.labeled, report, 20, 'close')

    def test_nested_tuning_and_refits_never_see_unmatured_labels(self):
        frames, jobs, plan = exp.prepare_experiment(self.args)
        frame, job = frames[20], jobs[0]
        tuned_frames, fit_frames = [], []

        def tune(name, development, names, folds, **kwargs):
            tuned_frames.append(development.copy())
            return {'best_params': {}, 'validation_f1_macro': .99, 'optuna_n_trials': 1, 'model_name': name}

        def fit(result, development, names):
            fit_frames.append(development.copy())
            model = Mock()
            model.predict.side_effect = lambda X: np.ones(len(X), dtype=int)
            return model, None

        with patch.object(exp.base, 'tune_and_evaluate', side_effect=tune), \
             patch.object(exp.base, 'fit_selected_candidate', side_effect=fit):
            result, predictions = exp.run_candidate(frame, job, plan['optuna'])
        self.assertEqual(len(tuned_frames), 4)
        self.assertEqual(len(predictions), 400)
        self.assertFalse(predictions.Date.duplicated().any())
        expected_blocks = [block for outer in job['folds'] for block in outer['blocks']]
        self.assertEqual(len(fit_frames), len(expected_blocks))
        for train, block in zip(fit_frames, expected_blocks):
            self.assertLess(train.label_end_date.max(), frame.Date.iloc[block['validation'][0]])
        self.assertLess(result['mean_f1'], .99)  # inner tuning score is never reported as outer evaluation
        self.assertEqual(result['pooled']['bear_false_alarms'], 0)
        self.assertEqual(result['pooled']['bear_missed'], result['pooled']['bear_support'])
        json.dumps(result)

    def test_audit_only_does_not_fit_or_export(self):
        with patch.object(exp, 'run_candidate') as run, patch.object(exp.base, 'export_onnx') as export:
            plan = exp.main(['--reference-report', str(self.report_path), '--data-dir', str(self.root),
                             '--base-feature-set', 'close', '--train-windows', 'expanding',
                             '--audit-only', '--output-dir', str(self.root / 'audit')])
        run.assert_not_called()
        export.assert_not_called()
        self.assertFalse(plan['errors'])
        self.assertFalse((self.root / 'audit/experiment_report.json').exists())

    def test_diagnosis_uses_existing_matrices_without_training(self):
        report = {'results': [{'horizon': 20, 'feature_set': 'close', 'model_name': 'Mock', 'validation_folds': [
            {'validation_start': '2020-01-01', 'validation_end': '2020-12-31',
             'f1_macro': .3, 'baseline_f1': .2, 'mcc': .1,
             'confusion_matrix': [[2, 3, 5], [7, 8, 9], [11, 12, 13]]}]}]}
        self.report_path.write_text(json.dumps(report))
        with patch.object(exp.base, 'fit_selected_candidate') as fit:
            rows = exp.diagnose_existing(self.report_path, self.root / 'diagnostics')
        fit.assert_not_called()
        self.assertEqual(rows[0]['bear_missed'], 8)
        self.assertTrue((self.root / 'diagnostics/fold_errors.csv').exists())


class OutputTests(unittest.TestCase):
    def test_reports_preserve_counts_and_pair_against_same_run_control(self):
        import copy
        records = pd.DataFrame({'Date': pd.bdate_range('2020-01-01', periods=6),
                                'label': [0, 0, 1, 1, 2, 2], 'prediction': [1] * 6,
                                'baseline_prediction': [1] * 6})
        metrics = exp.prediction_metrics(records)
        fold = dict(metrics, fold=1, validation_start='2020-01-01', validation_end='2020-01-08', refits=[])
        control = {'candidate': 't20_LightGBM_baseline_expanding', 'horizon': 20, 'model_name': 'LightGBM',
                   'feature_group': 'baseline', 'train_window': 'expanding', 'mean_f1': metrics['f1_macro'],
                   'std_f1': 0, 'worst_f1': metrics['f1_macro'], 'mean_mcc': metrics['mcc'], 'worst_mcc': metrics['mcc'],
                   'mean_baseline_f1': metrics['baseline_f1'], 'folds_beating_majority': 0,
                   'pooled': metrics, 'folds': [fold], 'per_decision_year': {'2020': metrics}}
        candidate = copy.deepcopy(control)
        candidate.update(candidate='t20_LightGBM_trend_expanding', feature_group='trend')
        records['prediction'] = [0, 1, 0, 1, 2, 2]
        candidate['pooled'] = exp.prediction_metrics(records)
        candidate['mean_f1'] = candidate['worst_f1'] = candidate['pooled']['f1_macro']
        candidate['mean_mcc'] = candidate['worst_mcc'] = candidate['pooled']['mcc']
        candidate['folds'] = [dict(candidate['pooled'], fold=1, validation_start='2020-01-01',
                                    validation_end='2020-01-08', refits=[])]
        candidate['per_decision_year'] = {'2020': candidate['pooled']}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exp.write_summary([control, candidate], root)
            exp.plot_experiments([control, candidate], root)
            deltas = pd.read_csv(root / 'paired_deltas.csv')
            self.assertEqual(deltas.iloc[1]['bear_missed_delta'], -1)
            self.assertEqual(deltas.iloc[1]['bear_false_alarms_delta'], 1)
            self.assertEqual(len(pd.read_csv(root / 'fold_errors.csv')), 2)
            self.assertEqual(len(pd.read_csv(root / 'year_errors.csv')), 2)
            self.assertGreater((root / 'model_comparison_t20.png').stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
