"""Leakage and orchestration regressions; estimators are mocked, no training jobs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

import train_regime_v2 as pipeline


def market_frame(n=900, start='2020-01-01'):
    dates = pd.bdate_range(start, periods=n)
    prices = 100 * np.exp(0.20 * np.sin(np.arange(n) / 25) + np.arange(n) * .0002)
    return pd.DataFrame({'Date': dates, 'Close': prices, 'Price': prices, 'Volume': 1000})


class CausalityTests(unittest.TestCase):
    def test_label_horizon_preserved_across_missing_features(self):
        raw = market_frame(200)
        features, names = pipeline.build_feature_matrix(raw)
        features.loc[80, names[0]] = np.nan
        labels = pipeline.create_labels(features, 20, names)
        row = labels.loc[labels.Date == raw.Date.iloc[70]].iloc[0]
        self.assertEqual(row.label_end_date, raw.Date.iloc[90])
        self.assertAlmostEqual(row.future_return, raw.Price.iloc[90] / raw.Price.iloc[70] - 1)
        self.assertNotIn(raw.Date.iloc[80], set(labels.Date))
        self.assertEqual(labels.Date.max(), raw.Date.iloc[-21])

    def test_future_prices_do_not_change_any_prior_feature(self):
        raw = market_frame(250)
        etf = market_frame(250)
        etf['Price'] *= np.exp(.02 * np.sin(np.arange(250) / 3))
        original, names = pipeline.build_feature_matrix(raw, etf, 'close-etf')
        changed = raw.copy()
        changed_etf = etf.copy()
        changed.loc[151:, 'Price'] *= 3
        changed_etf.loc[151:, 'Price'] *= 7
        after, _ = pipeline.build_feature_matrix(changed, changed_etf, 'close-etf')
        pd.testing.assert_frame_equal(original.loc[:150, names], after.loc[:150, names])

    def test_etf_missing_and_zero_volume_bars_are_not_filled(self):
        raw = market_frame(200)
        etf = raw.iloc[40:].copy()
        etf = etf.loc[etf.index != 100]
        etf.loc[150, 'Volume'] = 0
        features = pipeline.compute_etf_features(raw, etf)
        self.assertTrue(features.loc[:69, 'ETF_Corr30_VNINDEX'].isna().all())
        self.assertTrue(features.loc[100:130, 'ETF_Corr30_VNINDEX'].isna().all())
        self.assertTrue(features.loc[150:180, 'ETF_Corr30_VNINDEX'].isna().all())
        self.assertTrue(np.isfinite(features.loc[190]).all())

    def test_correlation_uses_identical_sessions(self):
        raw = market_frame(100)
        etf = raw.copy()
        etf['Price'] *= np.exp(.03 * np.cos(np.arange(100) / 4))
        features = pipeline.compute_etf_features(raw, etf)
        i = 70
        expected = np.corrcoef(np.diff(np.log(raw.Price.iloc[i-30:i+1])),
                               np.diff(np.log(etf.Price.iloc[i-30:i+1])))[0, 1]
        self.assertAlmostEqual(features.loc[i, 'ETF_Corr30_VNINDEX'], expected, places=9)
        flat = etf.copy()
        flat['Price'] = 100
        self.assertTrue(pipeline.compute_etf_features(raw, flat)['ETF_Corr30_VNINDEX'].isna().all())

    def test_holdout_and_cv_purge_use_label_end_dates_with_sparse_rows(self):
        raw = market_frame(1100)
        features, names = pipeline.build_feature_matrix(raw)
        labels = pipeline.create_labels(features, 60, names)
        labels = labels.iloc[::3].reset_index(drop=True)
        boundary = raw.Date.iloc[850]
        development, holdout, purged = pipeline.partition_holdout(labels, boundary)
        self.assertGreater(purged, 0)
        self.assertTrue((development.label_end_date < boundary).all())
        self.assertTrue((holdout.Date >= boundary).all())
        for train, validation in pipeline.purged_folds(development, 3):
            self.assertLess(development.label_end_date.iloc[train].max(), development.Date.iloc[validation[0]])

    def test_missing_class_fails_preflight(self):
        frame = market_frame(200)
        frame['label'] = 1
        frame['label_end_date'] = frame.Date.shift(-20)
        with self.assertRaisesRegex(ValueError, 'lacks one'):
            pipeline.purged_folds(frame.iloc[:-20], 2)

    def test_macro_f1_always_counts_all_three_classes(self):
        metrics = pipeline.classification_metrics([1, 1], [1, 1], np.array([1, 1]))
        self.assertAlmostEqual(metrics['f1_macro'], 1 / 3)
        self.assertEqual(np.asarray(metrics['confusion_matrix']).shape, (3, 3))


class DataAuditTests(unittest.TestCase):
    def test_bad_csvs_fail_instead_of_silent_cleanup(self):
        original = market_frame(20)[['Date', 'Close', 'Volume']]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'prices.csv'
            for mutate in [lambda d: pd.concat([d, d.iloc[:1]]),
                           lambda d: d.assign(Close=np.nan),
                           lambda d: d.assign(Close=-1),
                           lambda d: d.assign(Date=pd.Timestamp('2099-01-01'))]:
                with self.subTest(mutate=mutate):
                    mutate(original.copy()).to_csv(path, index=False)
                    with self.assertRaises(ValueError):
                        pipeline.load_market_data(path, today='2025-01-01')

    def test_adjustments_provenance_and_zero_volume_are_explicit(self):
        frame = market_frame(20)[['Date', 'Close', 'Volume']].iloc[::-1].copy()
        frame.iloc[0, frame.columns.get_loc('Volume')] = 0
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'prices.csv'
            frame.to_csv(path, index=False)
            loaded, audit = pipeline.load_market_data(path)
            self.assertTrue(loaded.Date.is_monotonic_increasing)
            self.assertFalse(audit['input_was_sorted'])
            self.assertEqual(audit['zero_volume_rows'], 1)
            self.assertEqual(audit['adjustment_status'], 'raw_close_adjustments_unverified')
            self.assertEqual(len(audit['sha256']), 64)
            frame['Adj Close'] = frame.Close * .9
            frame.to_csv(path, index=False)
            loaded, audit = pipeline.load_market_data(path)
            np.testing.assert_array_equal(loaded.Price, loaded['Adj Close'])

    def test_calendar_validation_detects_missing_index_sessions(self):
        raw = market_frame(100)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'calendar.csv'
            raw[['Date']].to_csv(path, index=False)
            self.assertTrue(pipeline.audit_calendar(raw, calendar_path=path)['exchange_calendar_verified'])
            with self.assertRaisesRegex(ValueError, 'disagree'):
                pipeline.audit_calendar(raw.drop(index=50), calendar_path=path)


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'run'
        raw = market_frame(1100)
        frame, self.names = pipeline.build_feature_matrix(raw)
        labeled = pipeline.create_labels(frame, 20, self.names)
        self.development, self.holdout, _ = pipeline.partition_holdout(labeled, raw.Date.iloc[850])
        self.folds = pipeline.purged_folds(self.development, 3)
        self.datasets = {('close', 20): (self.development, self.holdout, self.names, self.folds)}
        self.audit = {'holdout_start': str(raw.Date.iloc[850].date()),
                      'calendar': {'exchange_calendar_verified': False}, 'datasets': [], 'errors': []}

    def run_main(self, extra):
        return pipeline.main(['--output-dir', str(self.output), '--horizons', '20',
                              '--exposure-registry', str(Path(self.temp.name) / 'exposures.json'),
                              '--prior-reports-dir', str(Path(self.temp.name) / 'prior'),
                              '--models', 'LogisticRegression', 'RandomForest', *extra])

    def test_audit_only_never_tunes_fits_scores_or_exports(self):
        with patch.object(pipeline, 'prepare_run', return_value=(self.datasets, self.audit)), \
             patch.object(pipeline, 'tune_and_evaluate') as tune, \
             patch.object(pipeline, 'fit_selected_candidate') as fit, \
             patch.object(pipeline, 'evaluate_holdout') as evaluate, \
             patch.object(pipeline, 'export_onnx') as export:
            self.run_main(['--audit-only'])
            for method in [tune, fit, evaluate, export]:
                method.assert_not_called()

    def test_quick_never_consumes_holdout(self):
        candidate = {'model_name': 'RandomForest', 'best_params': {}, 'validation_f1_macro': .4,
                     'validation_mcc': .2, 'validation_folds': []}
        with patch.object(pipeline, 'prepare_run', return_value=(self.datasets, self.audit)), \
             patch.object(pipeline, 'tune_and_evaluate', side_effect=lambda *a, **k: copy.deepcopy(candidate)), \
             patch.object(pipeline, 'fit_selected_candidate') as fit, \
             patch.object(pipeline, 'evaluate_holdout') as evaluate, \
             patch.object(pipeline, 'export_onnx') as export, \
             patch.object(pipeline, 'plot_comparison_chart'):
            report = self.run_main(['--quick'])
            fit.assert_not_called()
            evaluate.assert_not_called()
            export.assert_not_called()
            self.assertEqual(report['optuna']['n_trials'], 5)
            self.assertEqual(report['best_per_horizon']['20']['holdout'], 'not_scored_in_quick_mode')

    def test_only_development_winner_reaches_holdout(self):
        seen = []

        def tune(name, development, names, folds, **kwargs):
            self.assertIs(development, self.development)
            self.assertLess(development.label_end_date.max(), self.holdout.Date.min())
            return {'model_name': name, 'best_params': {},
                    'validation_f1_macro': .6 if name == 'RandomForest' else .3,
                    'validation_mcc': .2, 'validation_folds': []}

        def fit(result, development, names):
            seen.append(result['model_name'])
            return Mock(), None

        with patch.object(pipeline, 'prepare_run', return_value=(self.datasets, self.audit)), \
             patch.object(pipeline, 'tune_and_evaluate', side_effect=tune), \
             patch.object(pipeline, 'fit_selected_candidate', side_effect=fit), \
             patch.object(pipeline, 'evaluate_holdout', return_value=({'f1_macro': .1, 'mcc': 0}, pd.DataFrame())) as evaluate, \
             patch.object(pipeline, 'plot_comparison_chart'):
            report = self.run_main(['--skip-onnx'])
            self.assertEqual(seen, ['RandomForest'])
            evaluate.assert_called_once()
            self.assertIs(evaluate.call_args.args[3], self.holdout)
            self.assertEqual(report['best_per_horizon']['20']['model'], 'RandomForest')
            saved = json.loads((self.output / 'regime_v2_report.json').read_text())
            self.assertEqual(saved['best_per_horizon']['20']['holdout']['f1_macro'], .1)


class TuningAndExportTests(unittest.TestCase):
    def test_optuna_objective_fits_scaler_on_training_rows_only(self):
        raw = market_frame(1100)
        frame, names = pipeline.build_feature_matrix(raw)
        labeled = pipeline.create_labels(frame, 20, names)
        development, _, _ = pipeline.partition_holdout(labeled, raw.Date.iloc[850])
        folds = pipeline.purged_folds(development, 3)
        fits = []
        predictions = []

        class RecordingEstimator:
            def fit(self, X, y):
                fits.append((X.copy(), y.copy()))
                return self

            def predict(self, X):
                predictions.append(X.copy())
                return np.ones(len(X), dtype=int)

        with patch.object(pipeline, 'create_model', side_effect=lambda *a: RecordingEstimator()):
            result = pipeline.tune_and_evaluate('LogisticRegression', development, names, folds,
                                                 n_trials=1, timeout=10)
        X = development[names].to_numpy(dtype=np.float32)
        self.assertEqual(len(fits), len(folds))
        self.assertEqual(result['optuna_n_trials'], 1)
        for (train, validation), (seen_X, seen_y), seen_validation in zip(folds, fits, predictions):
            expected = pipeline.StandardScaler().fit(X[train])
            np.testing.assert_allclose(seen_X, expected.transform(X[train]))
            np.testing.assert_allclose(seen_validation, expected.transform(X[validation]))
            np.testing.assert_array_equal(seen_y, development.label.iloc[train])
        json.dumps(result)  # report must be serializable without numpy conversions

    def test_logistic_onnx_embeds_scaler_without_training(self):
        # Construct known coefficients directly: no .fit() and no training data.
        model = pipeline.LogisticRegression()
        model.classes_ = np.array([0, 1, 2])
        model.n_features_in_ = 12
        model.coef_ = np.linspace(-.2, .2, 36).reshape(3, 12)
        model.intercept_ = np.array([.1, -.1, .2])
        model.n_iter_ = np.array([1])
        scaler = pipeline.StandardScaler()
        scaler.mean_ = np.arange(12, dtype=float)
        scaler.scale_ = np.arange(1, 13, dtype=float)
        scaler.var_ = scaler.scale_ ** 2
        scaler.n_features_in_ = 12
        scaler.n_samples_seen_ = 100
        samples = np.random.default_rng(42).normal(5, 2, size=(32, 12)).astype(np.float32)
        with tempfile.TemporaryDirectory() as temp:
            path = pipeline.export_onnx(model, 'LogisticRegression', 20, pipeline.CLOSE_V1_NAMES,
                                        scaler, samples, Path(temp), '2024-01-01', 'close-v3-research')
            self.assertTrue(path.exists())
            import onnxruntime as ort
            session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
            self.assertEqual(session.get_modelmeta().custom_metadata_map['scaling'], 'embedded')
            fixture = json.loads(path.with_suffix('.fixture.json').read_text())
            self.assertEqual(fixture['feature_names'], pipeline.CLOSE_V1_NAMES)


if __name__ == '__main__':
    unittest.main()
