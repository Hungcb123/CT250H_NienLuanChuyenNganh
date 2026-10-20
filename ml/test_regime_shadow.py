import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import regime_shadow as shadow
import regime_shadow_ledger as ledger


class LedgerTests(unittest.TestCase):
    def test_append_duplicate_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl'
            ledger.append_record(path,dict(record_id='a',risk_score=.3))
            ledger.append_record(path,dict(record_id='b',risk_score=.4))
            self.assertEqual(len(ledger.read_ledger(path)),2)
            with self.assertRaisesRegex(ValueError,'already emitted'):
                ledger.append_record(path,dict(record_id='a',risk_score=.9))
            path.write_text(path.read_text().replace('0.3','0.7'))
            with self.assertRaisesRegex(ValueError,'changed'):
                ledger.read_ledger(path)

    def test_concurrent_appends_preserve_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl'
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda i:ledger.append_record(path,dict(record_id=str(i),value=i)),range(20)))
            records=ledger.read_ledger(path)
            self.assertEqual(len(records),20)
            self.assertEqual(len({r['record_id'] for r in records}),20)


class RuntimeTests(unittest.TestCase):
    def test_same_day_after_close_and_freeze_required(self):
        frozen='2026-10-17T16:33:35+00:00'
        shadow.prospective_timing('2026-10-19','2026-10-19T08:30:00+00:00',frozen)
        for decision,emitted in [('2026-10-16','2026-10-19T08:30:00+00:00'),
                                  ('2026-10-19','2026-10-19T07:30:00+00:00'),
                                  ('2026-10-17','2026-10-17T08:30:00+00:00')]:
            with self.assertRaises(ValueError):shadow.prospective_timing(decision,emitted,frozen)
        with self.assertRaisesRegex(ValueError,'freeze'):
            shadow.prospective_timing('2026-10-16','2026-10-16T08:30:00+00:00',frozen)

    def test_frozen_contract_and_unmatured_forecast_features(self):
        contract=shadow.read_contract()
        index,audit=shadow.load_index()
        frame=shadow.feature_frame(index,contract)
        self.assertEqual(frame.Date.max(),index.Date.max())
        self.assertTrue(frame.label.iloc[-20:].isna().all())
        self.assertTrue(frame.label_end_date.iloc[-20:].isna().all())
        boundary=shadow.refit_boundary(index.Date,pd.Timestamp('2026-09-03'),contract)
        for window in contract['experts']:
            core,cal=shadow.partition(frame,boundary,window,contract)
            self.assertEqual(len(cal),40)
            self.assertLess(core.label_end_date.max(),cal.Date.min())
            self.assertLess(cal.label_end_date.max(),boundary)

    def test_source_hash_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract=json.loads(shadow.CONTRACT.read_text())
            contract['source_component_sha256']['train_regime_v2.py']='0'*64
            path=Path(tmp)/'contract.json';path.write_text(json.dumps(contract))
            with self.assertRaisesRegex(ValueError,'Frozen source changed'):shadow.read_contract(path)

    def test_saved_native_models_reproduce_research_predictions(self):
        contract=shadow.read_contract();index,_=shadow.load_index()
        with tempfile.TemporaryDirectory() as tmp:
            records=shadow.replay(index,contract,shadow.CONTRACT,'2025-02-10','2025-02-14',Path(tmp)/'cache')
            report=shadow.write_parity(records,contract,Path(tmp)/'parity.json')
            self.assertTrue(report['passed'])
            self.assertEqual(report['n_decisions'],5)
            self.assertTrue(all(r['mode']=='research_backcast' for r in records))
            # Cached model identity and byte hashes are also checked on a second load.
            again=shadow.replay(index,contract,shadow.CONTRACT,'2025-02-10','2025-02-14',Path(tmp)/'cache')
            np.testing.assert_allclose([r['risk_score'] for r in records],[r['risk_score'] for r in again],rtol=0,atol=0)

    def test_runtime_freeze_rejects_narrow_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'parity.json';path.write_text(json.dumps(dict(passed=True,n_decisions=5)))
            with self.assertRaisesRegex(ValueError,'full latest-fold'):
                shadow.freeze_runtime(shadow.CONTRACT,path)


class ExtendedSnapshotTests(unittest.TestCase):
    def test_verified_extension_and_source_archive_tamper_detection(self):
        import shutil
        roots=shadow.ROOT/'data/research/regime_shadow'
        choices=list(roots.glob('*/manifest.json'))
        choices=[p for p in choices if json.loads(p.read_text()).get('status')=='accepted']
        if not choices:self.skipTest('No collected extension')
        path=choices[-1].parent
        index,audit=shadow.load_index(path/'VNINDEX.csv')
        self.assertGreater(index.Date.max(),pd.Timestamp('2026-10-01'))
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'snapshot';shutil.copytree(path,target)
            manifest=json.loads((target/'manifest.json').read_text())
            raw=target/manifest['sources']['vci']['response']
            raw.write_text(raw.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'source changed'):
                shadow.load_index(target/'VNINDEX.csv')


class FutureBoundaryTests(unittest.TestCase):
    def test_future_prices_do_not_change_predictions_and_reference_matches(self):
        contract=shadow.read_contract();index,_=shadow.load_index()
        with tempfile.TemporaryDirectory() as tmp:
            records=shadow.replay(index,contract,shadow.CONTRACT,'2025-02-10','2025-02-14',Path(tmp)/'cache')
            changed=index.copy()
            changed.loc[changed.Date>pd.Timestamp('2025-02-14'),'Price']*=1.1
            again=shadow.replay(changed,contract,shadow.CONTRACT,'2025-02-10','2025-02-14',Path(tmp)/'cache')
            np.testing.assert_array_equal([r['risk_score'] for r in records],[r['risk_score'] for r in again])
            path=shadow.ROOT/'reports/regime_ensemble/20261017T162100_738897Z/3y_standardized_predictions.csv'
            reference=pd.read_csv(path,parse_dates=['Date'])
            for record in records:
                expected=reference.loc[reference.Date==pd.Timestamp(record['Date'])].iloc[0]
                baseline=record['baselines']['3y']
                self.assertAlmostEqual(baseline['risk_score'],expected.risk_score,places=12)
                self.assertAlmostEqual(baseline['threshold'],expected.threshold,places=12)
                self.assertEqual(baseline['alarm'],expected.alarm)


class InitializationTests(unittest.TestCase):
    def test_late_start_reconstructs_all_intermediate_archived_state(self):
        contract=shadow.read_contract();index,_=shadow.load_index()
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'cache'
            whole=shadow.replay(index,contract,shadow.CONTRACT,'2026-09-04','2026-10-01',cache)
            tail=shadow.replay(index,contract,shadow.CONTRACT,'2026-10-01','2026-10-01',cache)
            self.assertEqual(len(tail),1)
            self.assertEqual(tail[0]['risk_score'],whole[-1]['risk_score'])
            self.assertEqual(tail[0]['threshold'],whole[-1]['threshold'])
            self.assertEqual(tail[0]['n_prior_scores'],whole[-1]['n_prior_scores'])
