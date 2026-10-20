import unittest
import numpy as np
import experiment_regime_ensemble as study


class EnsembleTests(unittest.TestCase):
    def test_standardization_does_not_fit_prediction_distribution(self):
        cal=np.linspace(.1,.8,40)
        a,b,meta=study.standardize_scores(cal,[.2,.4])
        c,d,changed=study.standardize_scores(cal,[.99,.99])
        np.testing.assert_array_equal(a,c)
        self.assertEqual(meta,changed)
        self.assertTrue(np.isfinite(d).all())

    def test_weighting_only_calibration_and_shrinks_rare_events(self):
        y=np.array([1,0,1,0,0,0,0,0,0,0])
        weights,ap=study.calibration_weights(y,[y,1-y])
        self.assertGreater(weights[0],weights[1])
        self.assertLess(weights[0],.9)
        np.testing.assert_allclose(study.calibration_weights(np.zeros(10),[y,1-y])[0],[.5,.5])

    def test_snapshot_pairing_and_timing(self):
        reference=study.study.risk.labels.ROOT/'reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json'
        if not reference.exists():self.skipTest('Snapshot missing')
        args=study.study.risk.labels.parse_args(['--reference-report',str(reference),'--audit-only'])
        frame,jobs,names,index,plan=study.prepare(args)
        n=0
        for outer in jobs:
            for a,b in zip(outer['blocks']['3y'],outer['blocks']['expanding']):
                np.testing.assert_array_equal(a['calibration'],b['calibration'])
                np.testing.assert_array_equal(a['validation'],b['validation'])
                cal,valid=frame.iloc[a['calibration']],frame.iloc[a['validation']]
                self.assertLess(cal.label_end_date.max(),valid.Date.min())
                n+=len(valid)
        self.assertEqual(n,1560)
