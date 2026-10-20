"""Source reconciliation, provenance, and holdout reuse tests. No model training."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

import prepare_regime_data as data
import research_protocol as protocol
import train_regime_v2 as pipeline


def bars(closes=(100, 101, 102), start='2020-01-06'):
    close = np.array(closes, dtype=float)
    return pd.DataFrame({'Date': pd.bdate_range(start, periods=len(close)), 'Open': close,
                         'High': close + 1, 'Low': close - 1, 'Close': close, 'Volume': 1000})


class SourceTests(unittest.TestCase):
    def test_daily_epoch_uses_market_timezone_and_requested_range(self):
        timestamps = [int(pd.Timestamp('2020-01-05 17:00Z').timestamp()),
                      int(pd.Timestamp('2020-01-06 17:00Z').timestamp())]
        payload = [{'symbol': 'VNINDEX', 't': timestamps, 'o': [100, 101], 'h': [101, 102],
                    'l': [99, 100], 'c': [100, 101], 'v': [10, 20]}]
        frame = data.normalize_response(payload, 'vci', 'VNINDEX', '2020-01-06', '2020-01-06')
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.Date.iloc[0], pd.Timestamp('2020-01-06'))
        self.assertEqual(frame.Close.iloc[0], 100)
        with self.assertRaisesRegex(ValueError, 'one response'):
            data.normalize_response(payload, 'vci', 'E1VFVN30', '2020-01-06', '2020-01-07')

    def test_duplicate_or_nonfinite_broker_data_is_rejected(self):
        payload = {'symbol': 'VNINDEX', 'data_day': [
            {'t': '2020-01-06 07:00', 'o': 100, 'h': 101, 'l': 99, 'c': 100, 'v': 100}]}
        duplicate = copy.deepcopy(payload)
        duplicate['data_day'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            data.normalize_response(duplicate, 'kbs', 'VNINDEX', '2020-01-01', '2020-01-10')
        payload['data_day'][0]['c'] = float('inf')
        with self.assertRaisesRegex(ValueError, 'invalid Close'):
            data.normalize_response(payload, 'kbs', 'VNINDEX', '2020-01-01', '2020-01-10')

    def test_conflicts_use_documented_majority_not_averaging(self):
        vci, kbs, vnd = bars(), bars((100, 103, 102)), bars((100, 103, 102))
        review = {'schema_version': 1, 'nontrading_dates': {}, 'reviewed_closes': {}}
        frame, decisions = data.reconcile_index({'vci_VNINDEX': vci, 'kbs_VNINDEX': kbs, 'vnd_VNINDEX': vnd}, review)
        self.assertEqual(frame.Close.iloc[1], 103)
        self.assertEqual(decisions[1]['decision'], 'broker_majority')
        self.assertEqual(decisions[1]['vci'], 101)
        self.assertTrue(decisions[1]['changed_primary'])
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            data.reconcile_index({'vci_VNINDEX': vci, 'kbs_VNINDEX': kbs}, review)

    def test_cited_tie_resolution_and_closed_sessions_preserve_calendar(self):
        vci, kbs = bars(), bars((100, 103, 102))
        review = {'schema_version': 1,
                  'nontrading_dates': {'2020-01-08': {'source': 'https://exchange.example/closure'}},
                  'reviewed_closes': {'2020-01-07': {'close': 101, 'source': 'https://broker.example/daily'}}}
        frame, decisions = data.reconcile_index({'vci_VNINDEX': vci, 'kbs_VNINDEX': kbs}, review)
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.Close.tolist(), [100, 101])
        self.assertEqual(decisions[1]['source'], 'https://broker.example/daily')
        self.assertEqual(decisions[2]['decision'], 'excluded_nontrading_session')
        review['reviewed_closes']['2020-01-07']['close'] = 999
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            data.reconcile_index({'vci_VNINDEX': vci, 'kbs_VNINDEX': kbs}, review)

    def test_provenance_is_bound_to_exact_canonical_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'VNINDEX.csv'
            original = bars()
            data.write_canonical(path, original, 'VNINDEX', {}, {})
            loaded, audit = pipeline.load_market_data(path)
            self.assertEqual(audit['adjustment_status'], 'price_index_points')
            self.assertEqual(loaded.Close.tolist(), [100, 101, 102])
            # Keep source volume/OHLC out of close-only index training.
            self.assertNotIn('Volume', loaded)
            path.write_text(path.read_text().replace('101.0', '101.5'))
            with self.assertRaisesRegex(ValueError, 'provenance hash'):
                pipeline.load_market_data(path)

    def test_snapshot_replay_checks_original_response_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sources').mkdir()
            (root / 'sources/vci_VNINDEX.json').write_text('corrupt')
            manifest = {'requested_start': '2020-01-01', 'requested_end': '2020-01-10',
                        'sources': {'vci_VNINDEX': {'response': 'sources/vci_VNINDEX.json', 'response_sha256': 'wrong'}}}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            out = root / 'replay'
            out.mkdir()
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                data.load_saved_broker(root, 'vci', 'VNINDEX', '2020-01-01', '2020-01-10', out)


class ProtocolTests(unittest.TestCase):
    def test_last_observed_label_end_controls_new_holdout_not_prediction_end(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reports = root / 'reports/run'
            reports.mkdir(parents=True)
            report = {'mode': 'final_holdout', 'best_per_horizon': {'120': {'holdout': {
                'start': '2025-03-20', 'end': '2026-04-08', 'final_label_end': '2026-10-01'}}}}
            (reports / 'regime_v2_report.json').write_text(json.dumps(report))
            exposure = protocol.observed_exposure(root / 'registry.json', root / 'reports')
            self.assertEqual(exposure['latest_observed_label_date'], '2026-10-01')
            with self.assertRaisesRegex(ValueError, 'already been inspected'):
                protocol.assert_unseen_holdout('2026-05-01', exposure)
            protocol.assert_unseen_holdout('2026-10-02', exposure)

    def test_registry_persists_exposure_outside_default_report_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            protocol.record_exposure(root / 'registry.json', root / 'elsewhere/report.json', 20,
                                     '2025-01-01', '2026-10-01')
            exposure = protocol.observed_exposure(root / 'registry.json', root / 'empty')
            self.assertEqual(exposure['latest_observed_label_date'], '2026-10-01')

    def test_development_mode_uses_all_mature_rows_and_blocks_old_final_holdout(self):
        n = 1300
        dates = pd.bdate_range('2015-01-01', periods=n)
        prices = 100 * np.exp(.25 * np.sin(np.arange(n) / 25))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pd.DataFrame({'Date': dates, 'Close': prices}).to_csv(root / 'VNINDEX.csv', index=False)
            registry = root / 'registry.json'
            protocol.record_exposure(registry, root / 'seen.json', 20, dates[800], dates[-1])
            common = ['--data-dir', str(root), '--exposure-registry', str(registry),
                      '--prior-reports-dir', str(root / 'prior'), '--horizons', '20']
            datasets, audit = pipeline.prepare_run(pipeline.parse_args(common + ['--development-only']))
            development, holdout, _, _ = datasets['close', 20]
            self.assertEqual(len(development), n - 59 - 20)
            self.assertTrue(holdout.empty)
            self.assertFalse(audit['errors'])
            self.assertIsNone(audit['holdout_start'])
            _, final_audit = pipeline.prepare_run(pipeline.parse_args(common))
            self.assertTrue(any('already been inspected' in error for error in final_audit['errors']))
            _, quick_audit = pipeline.prepare_run(pipeline.parse_args(common + ['--quick']))
            self.assertFalse(any('already been inspected' in error for error in quick_audit['errors']))

    def test_development_mode_never_fits_final_model_scores_or_exports(self):
        names = pipeline.CLOSE_V1_NAMES
        frame = bars((100, 101, 102))
        for name in names:
            frame[name] = 1.0
        frame['label'] = [0, 1, 2]
        frame['label_end_date'] = frame.Date
        candidate = {'model_name': 'RandomForest', 'validation_f1_macro': .4,
                     'validation_mcc': .1, 'best_params': {}}
        audit = {'holdout_start': None, 'calendar': {'exchange_calendar_verified': False},
                 'datasets': [], 'errors': []}
        datasets = {('close', 20): (frame, frame.iloc[:0], names, [])}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(pipeline, 'prepare_run', return_value=(datasets, audit)), \
             patch.object(pipeline, 'tune_and_evaluate', return_value=candidate), \
             patch.object(pipeline, 'fit_selected_candidate') as fit, \
             patch.object(pipeline, 'evaluate_holdout') as evaluate, \
             patch.object(pipeline, 'export_onnx') as export, \
             patch.object(pipeline, 'plot_comparison_chart'):
            report = pipeline.main(['--development-only', '--horizons', '20', '--models', 'RandomForest',
                                    '--output-dir', str(Path(temp) / 'out')])
            self.assertEqual(report['mode'], 'development_only')
            for method in [fit, evaluate, export]:
                method.assert_not_called()

    def test_predeclared_horizons_do_not_block_each_other(self):
        names = pipeline.CLOSE_V1_NAMES
        dev = bars((100, 101, 102), '2020-01-06')
        holdout = bars((101, 102, 103), '2020-02-03')
        for frame in [dev, holdout]:
            for name in names:
                frame[name] = 1.0
            frame['label'], frame['future_return'] = [0, 1, 2], 0.0
            frame['label_end_date'] = frame.Date + pd.Timedelta(days=10)
        datasets = {('close', h): (dev, holdout, names, []) for h in [20, 60]}
        audit = {'holdout_start': '2020-02-03', 'calendar': {'exchange_calendar_verified': False},
                 'datasets': [], 'errors': []}
        candidate = {'model_name': 'RandomForest', 'validation_f1_macro': .4,
                     'validation_mcc': .1, 'best_params': {}}
        model = Mock()
        model.predict.return_value = np.array([0, 1, 2])
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(pipeline, 'prepare_run', return_value=(datasets, audit)), \
             patch.object(pipeline, 'tune_and_evaluate', side_effect=lambda *a, **k: dict(candidate)), \
             patch.object(pipeline, 'fit_selected_candidate', return_value=(model, None)), \
             patch.object(pipeline, 'plot_comparison_chart'):
            root = Path(temp)
            report = pipeline.main(['--horizons', '20', '60', '--models', 'RandomForest', '--skip-onnx',
                                    '--output-dir', str(root / 'out'), '--exposure-registry', str(root / 'registry.json'),
                                    '--prior-reports-dir', str(root / 'reports')])
            self.assertEqual(set(report['best_per_horizon']), {'20', '60'})
            registry = json.loads((root / 'registry.json').read_text())
            self.assertEqual({e['horizon'] for e in registry['exposures']}, {20, 60})


if __name__ == '__main__':
    unittest.main()
