"""Target-definition study regressions. No market-data model fitting."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import experiment_regime_labels as labels


def market(n=2000):
    values = 100 * np.exp(.25 * np.sin(np.arange(n) / 25) + np.arange(n) * .0001)
    return pd.DataFrame({'Date': pd.bdate_range('2010-01-01', periods=n), 'Price': values, 'Close': values})


class LabelDefinitionTests(unittest.TestCase):
    def test_sigma_units_and_horizon_normalization(self):
        index = market(400)
        book = labels.build_label_book(index)
        i = 250
        sigma = np.diff(np.log(index.Price.to_numpy()))[i-20:i].std(ddof=1)
        expected_scale = sigma * np.sqrt(20)
        expected_z = np.log(index.Price.iloc[i+20] / index.Price.iloc[i]) / expected_scale
        self.assertAlmostEqual(book.daily_sigma.iloc[i], sigma)
        self.assertAlmostEqual(book.horizon_sigma.iloc[i], expected_scale)
        self.assertAlmostEqual(book.z_forward.iloc[i], expected_z)
        self.assertAlmostEqual(book.vol_upper_simple_threshold.iloc[i], np.expm1(expected_scale))
        self.assertAlmostEqual(book.vol_lower_simple_threshold.iloc[i], np.expm1(-expected_scale))
        self.assertEqual(book.vol_label.iloc[i], 0 if expected_z < -1 else (2 if expected_z > 1 else 1))
        # Same daily sigma reconstructed from existing annualized, percent HV20.
        features = labels.exp.base.close_features_v1(index.Price.iloc[i-119:i+1].to_numpy())
        self.assertAlmostEqual(features[11] / 100 / np.sqrt(252), sigma, places=7)

    def test_future_price_changes_labels_but_not_past_thresholds(self):
        index = market(400)
        before = labels.build_label_book(index)
        changed = index.copy()
        changed.loc[251:, 'Price'] *= 3
        after = labels.build_label_book(changed)
        columns = ['daily_sigma', 'horizon_sigma', 'vol_upper_simple_threshold', 'vol_lower_simple_threshold']
        pd.testing.assert_frame_equal(before.loc[:250, columns], after.loc[:250, columns])
        self.assertNotEqual(before.future_return.iloc[240], after.future_return.iloc[240])
        self.assertEqual(after.label_end_date.iloc[240], index.Date.iloc[260])

    def test_warmup_zero_volatility_and_unmatured_labels_stay_missing(self):
        book = labels.build_label_book(market(300))
        self.assertTrue(book.vol_label.iloc[:20].isna().all())
        self.assertTrue(book.vol_label.iloc[-20:].isna().all())
        self.assertTrue(book.fixed_label.iloc[-20:].isna().all())
        flat = labels.build_label_book(market(300).assign(Price=100))
        self.assertTrue(flat.vol_label.isna().all())
        self.assertTrue(flat.z_forward.isna().all())
        self.assertTrue(flat.fixed_label.iloc[:-20].eq(1).all())

    def test_feature_gaps_do_not_compress_label_horizon(self):
        index = market(300)
        features, names = labels.exp.base.build_feature_matrix(index)
        features.loc[100, names[0]] = np.nan
        frame = labels.exp.base.create_labels(features, 20, names)
        book = labels.build_label_book(index)
        relabeled = labels.relabel_cohort(frame, book, 'vol_1sigma')
        row = relabeled.loc[relabeled.Date == index.Date.iloc[90]].iloc[0]
        self.assertEqual(row.label_end_date, index.Date.iloc[110])
        self.assertEqual(len(relabeled), len(frame))
        pd.testing.assert_series_equal(relabeled.Date, frame.Date)
        fixed = labels.relabel_cohort(frame, book, 'fixed_5pct')
        pd.testing.assert_series_equal(fixed.label, frame.label)

    def test_missing_sigma_cannot_silently_shrink_shared_cohort(self):
        index = market(300)
        features, names = labels.exp.base.build_feature_matrix(index)
        frame = labels.exp.base.create_labels(features, 20, names)
        book = labels.build_label_book(index)
        book.loc[book.Date == frame.Date.iloc[5], 'vol_label'] = pd.NA
        with self.assertRaisesRegex(ValueError, 'do not silently remove'):
            labels.relabel_cohort(frame, book, 'vol_1sigma')

    def test_common_risk_uses_fixed_loss_definition_for_both_policies(self):
        records = pd.DataFrame({'fixed_label': [0, 0, 1, 2], 'label': [0, 1, 0, 2],
                                'prediction': [0, 1, 0, 2], 'future_return': [-.08, -.06, -.02, .09]})
        metrics = labels.common_outcomes(records)
        common = metrics['absolute_5pct_bear']
        self.assertEqual((common['bear_support'], common['bear_hits'], common['bear_false_alarms'], common['bear_missed']), (2, 1, 1, 1))
        self.assertEqual(metrics['forward_return_by_prediction']['bearish']['mean_forward_return'], -.05)
        self.assertEqual(metrics['forward_return_by_prediction']['bearish']['fraction_return_below_minus5pct'], .5)


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        index = market()
        index[['Date', 'Close']].to_csv(self.root / 'VNINDEX.csv', index=False)
        etf = index[['Date', 'Close']].copy()
        etf['Close'] *= np.exp(.01 * np.cos(np.arange(len(etf)) / 4))
        etf['Volume'] = 1000
        etf.to_csv(self.root / 'E1VFVN30.csv', index=False)
        folds = [{'validation_start': str(index.Date.iloc[start].date()),
                  'validation_end': str(index.Date.iloc[start+149].date()), 'n_validation': 150}
                 for start in [1000, 1250, 1500, 1750]]
        report = {'mode': 'development_only', 'results': [{'horizon': 20, 'feature_set': 'close-etf', 'validation_folds': folds}]}
        self.reference = self.root / 'regime_v2_report.json'
        self.reference.write_text(json.dumps(report))
        inputs = {symbol: {'sha256': hashlib.sha256((self.root / (symbol + '.csv')).read_bytes()).hexdigest()}
                  for symbol in ['VNINDEX', 'E1VFVN30']}
        (self.root / 'data_audit.json').write_text(json.dumps({'inputs': inputs}))
        self.argv = ['--reference-report', str(self.reference), '--data-dir', str(self.root),
                     '--output-dir', str(self.root / 'out')]

    def test_policies_share_features_dates_train_rows_and_causal_splits(self):
        variants, _, plan = labels.prepare_label_experiment(labels.parse_args(self.argv))
        self.assertFalse(plan['errors'])
        self.assertEqual(len(variants), 2)
        fixed, dynamic = variants[0][1], variants[1][1]
        pd.testing.assert_frame_equal(fixed.drop(columns='label'), dynamic.drop(columns='label'))
        self.assertTrue((fixed.label != dynamic.label).any())
        self.assertEqual(plan['policies']['fixed_5pct']['date_hash'], plan['policies']['vol_1sigma']['date_hash'])
        for outer_fixed, outer_dynamic in zip(variants[0][2]['folds'], variants[1][2]['folds']):
            np.testing.assert_array_equal(outer_fixed['tune'], outer_dynamic['tune'])
            tuning = dynamic.iloc[outer_dynamic['tune']].reset_index(drop=True)
            for train, validation in outer_dynamic['inner']:
                self.assertLess(tuning.label_end_date.iloc[train].max(), tuning.Date.iloc[validation[0]])
            for a, b in zip(outer_fixed['blocks'], outer_dynamic['blocks']):
                np.testing.assert_array_equal(a['train'], b['train'])
                np.testing.assert_array_equal(a['validation'], b['validation'])
                self.assertLess(dynamic.label_end_date.iloc[b['train']].max(), dynamic.Date.iloc[b['validation'][0]])

    def test_audit_only_never_runs_training_or_export(self):
        with patch.object(labels.exp, 'run_candidate') as run, patch.object(labels.exp.base, 'export_onnx') as export:
            plan = labels.main(self.argv + ['--audit-only'])
        self.assertFalse(plan['errors'])
        run.assert_not_called()
        export.assert_not_called()
        self.assertTrue((self.root / 'out/label_definitions.csv').exists())
        self.assertFalse((self.root / 'out/label_report.json').exists())

    def test_orchestration_keeps_native_labels_separate_and_no_winner(self):
        def fake_run(frame, job, optuna):
            parts = []
            for outer in job['folds']:
                ids = np.concatenate([block['validation'] for block in outer['blocks']])
                rows = frame.iloc[ids][['Date', 'label_end_date', 'label', 'future_return']].copy()
                rows['prediction'], rows['baseline_prediction'] = 1, 1
                rows['outer_fold'], rows['refit_block'] = outer['fold'], 1
                parts.append(rows)
            result = {'candidate': 'test', 'mean_f1': .3, 'std_f1': 0, 'worst_f1': .2, 'mean_mcc': .1,
                      'mean_baseline_f1': .25, 'folds_beating_majority': 4,
                      'folds': [{'fold': i + 1, 'validation_start': str(p.Date.min().date()),
                                 'validation_end': str(p.Date.max().date()), 'f1_macro': .3, 'baseline_f1': .25, 'mcc': .1}
                                for i, p in enumerate(parts)]}
            return result, pd.concat(parts, ignore_index=True)

        with patch.object(labels.exp, 'run_candidate', side_effect=fake_run), \
             patch.object(labels.exp.base, 'export_onnx') as export:
            report = labels.main(self.argv)
        export.assert_not_called()
        self.assertNotIn('winner', report)
        self.assertEqual([r['label_policy'] for r in report['results']], labels.POLICIES)
        out = self.root / 'out'
        fixed = pd.read_csv(out / 'fixed_5pct_predictions.csv')
        dynamic = pd.read_csv(out / 'vol_1sigma_predictions.csv')
        self.assertTrue((fixed.label == fixed.fixed_label).all())
        self.assertTrue((dynamic.label == dynamic.vol_label).all())
        self.assertTrue((fixed.label != dynamic.label).any())
        pd.testing.assert_series_equal(fixed.fixed_label, dynamic.fixed_label)
        common = pd.read_csv(out / 'common_5pct_risk.csv')
        self.assertEqual(common.bear_support.nunique(), 1)
        self.assertIn('different tasks', (out / 'comparison.md').read_text())
        self.assertEqual(len(pd.read_csv(out / 'fold_metrics.csv')), 8)


if __name__ == '__main__':
    unittest.main()
