import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import experiment_regime_candidates as study
from test_regime_risk import fixture


class CandidateTests(unittest.TestCase):
    def test_feature_causality(self):
        market = pd.DataFrame({'Date': pd.bdate_range('2010-01-01', periods=400), 'Price':100*np.exp(np.sin(np.arange(400)/20)*.1)})
        before = study.reversal_features(market)
        market.loc[250:, 'Price'] *= 2
        after = study.reversal_features(market)
        pd.testing.assert_frame_equal(before.iloc[:250], after.iloc[:250])

    def test_svm_binary_margin_orientation(self):
        class Fake:
            classes_ = np.array([0, 1])
            def decision_function(self, X):
                return np.array([-1., 2.])
        np.testing.assert_array_equal(study.score_model(Fake(), np.zeros((2, 1)), 'svm', 'binary_5pct'), [-1, 2])
        np.testing.assert_array_equal(study.score_model(Fake(), np.zeros((2, 1)), 'svm', 'vol_1sigma'), [1, -2])

    def test_pipeline_uses_only_core_training_and_scaling(self):
        frame = fixture()
        frame['horizon_sigma'], frame['future_log_return'] = .05, np.log1p(frame.future_return)
        core, cal = study.risk.split_calibration(frame, np.arange(500))
        job = dict(folds=[dict(fold=1, blocks=[dict(core=core, calibration=cal, validation=np.arange(530, 580))])])
        frame['label'] = (frame.future_return < -.05).astype(int)
        seen = []
        factory = study.make_model
        def model(family):
            result = factory(family)
            seen.append(result)
            return result
        with patch.object(study, 'make_model', side_effect=model):
            records, audits = study.run_candidate('test', 'binary_5pct', 'logistic', frame, job, ['x'])
        self.assertEqual(len(records), 50)
        self.assertAlmostEqual(seen[0].named_steps['standardscaler'].mean_[0], frame.x.iloc[core].mean())
        self.assertEqual(audits[0]['n_core'], len(core))
        self.assertTrue(np.isfinite(records.risk_score).all())

    def test_snapshot_all_candidates_share_dates(self):
        reference = study.risk.labels.ROOT / 'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():
            self.skipTest('Local snapshot missing')
        args = study.risk.labels.parse_args(['--reference-report', str(reference), '--audit-only'])
        candidates, _, plan = study.prepare_candidates(args)
        self.assertEqual(len(candidates), 6)
        self.assertFalse(plan['errors'])
        for candidate in candidates:
            self.assertTrue(candidate[3].Date.equals(candidates[0][3].Date))
            self.assertTrue(np.isfinite(candidate[3][candidate[-1]].to_numpy()).all())
