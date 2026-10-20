import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

import numpy as np
import pandas as pd

import evaluate_regime_shadow as evaluate
import run_regime_shadow_daily as runner


class OutcomeTests(unittest.TestCase):
    def fixture(self):
        index=pd.DataFrame(dict(Date=pd.bdate_range('2026-01-05',periods=50),Price=np.linspace(100,80,50)))
        lock=dict(runtime_sha256='runtime',runtime_frozen_at='2025-12-01T00:00:00+00:00')
        def prediction(i):
            date=index.Date.iloc[i]
            return dict(kind='prediction',mode='prospective',Date=str(date.date()),decision_close=float(index.Price.iloc[i]),candidate_id='candidate',
                        runtime_sha256='runtime',contract_sha256='contract',emitted_at=str(date.date())+'T08:30:00+00:00',_record_hash=str(i))
        return index,lock,prediction

    def test_only_matured_actual_twenty_sessions_are_scored(self):
        index,lock,p=self.fixture()
        outcomes,pending=evaluate.outcome_candidates([p(0),p(40)],index,lock,'candidate','contract','snapshot',now='2026-06-01T00:00:00+00:00')
        self.assertEqual(len(outcomes),1);self.assertEqual(pending,1)
        self.assertEqual(outcomes[0]['label_end_date'],str(index.Date.iloc[20].date()))
        self.assertTrue(outcomes[0]['common_bear'])

    def test_backcast_and_revised_close_rejected(self):
        index,lock,p=self.fixture();record=p(0);record['mode']='research_backcast'
        with self.assertRaisesRegex(ValueError,'Backcast'):
            evaluate.outcome_candidates([record],index,lock,'candidate','contract','snapshot')
        record=p(0);record['decision_close']+=1
        with self.assertRaisesRegex(ValueError,'revised'):
            evaluate.outcome_candidates([record],index,lock,'candidate','contract','snapshot')

    def test_overlapping_bear_days_are_not_independent_clusters(self):
        index,_,_=self.fixture()
        rows=pd.DataFrame(dict(Date=index.Date.iloc[[0,1,2,25]],common_bear=True))
        self.assertEqual(evaluate.independent_interval_clusters(rows,index),2)

    def test_empty_sample_never_passes(self):
        result=evaluate.screening(pd.DataFrame(),pd.DataFrame(),{})
        self.assertEqual(result['status'],'insufficient_prospective_evidence')
        self.assertEqual(result['n_matured'],0)


class RunnerTests(unittest.TestCase):
    def test_weekend_never_downloads_or_emits(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'validate_operations'),patch.object(runner.collect,'collect',side_effect=AssertionError('No weekend download')),patch.object(runner.shadow,'main',side_effect=AssertionError('No weekend emission')):
            result=runner.run_once(Path(tmp),now=datetime(2026,10,17,16,tzinfo=timezone.utc))
        self.assertEqual(result['status'],'outside_completed_session_window')

    def test_preclose_never_downloads_or_emits(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'validate_operations'),patch.object(runner.collect,'collect',side_effect=AssertionError('No preclose download')):
            result=runner.run_once(Path(tmp),now=datetime(2026,10,19,6,tzinfo=timezone.utc))
        self.assertEqual(result['status'],'outside_completed_session_window')

    def test_owned_cron_block_is_idempotent_and_preserves_other_jobs(self):
        existing='MAILTO=\"\"\n0 1 * * * /some/other/job\n'
        first=runner.cron_text(existing,'/python /research.py','candidate')
        second=runner.cron_text(first,'/python /research.py','candidate')
        self.assertEqual(first,second)
        self.assertTrue(second.startswith(existing))
        self.assertEqual(second.count('*/15'),1)

    def test_protocol_hash_change_blocks_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact=Path(tmp)
            (artifact/'contract.json').write_text('{}')
            (artifact/'operations_lock.json').write_text(json.dumps(dict(contract_sha256=runner.shadow.sha(artifact/'contract.json'),file_sha256={},artifact_sha256={'prospective_protocol.json':'0'*64})))
            (artifact/'prospective_protocol.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'artifact changed'):
                runner.validate_operations(artifact)


class ProspectivePowerTests(unittest.TestCase):
    def test_perfect_small_sample_still_insufficient(self):
        index=pd.DataFrame(dict(Date=pd.bdate_range('2026-01-05',periods=20)))
        rows=pd.DataFrame(dict(Date=index.Date,common_bear=[True]*2+[False]*18,alarm=[True]*2+[False]*18,baseline_alarm=False))
        protocol=dict(min_matured_sessions=240,min_bear_samples=20,min_nonoverlapping_positive_clusters=3,precision_min=.25,recall_min=.3,alarm_rate_max=.15)
        with patch.object(evaluate.risk,'bootstrap_deltas',side_effect=AssertionError('Too little data for interval screen')):
            result=evaluate.screening(rows,index,protocol)
        self.assertEqual(result['status'],'insufficient_prospective_evidence')
        self.assertTrue(result['point_screen_pass'])
        self.assertFalse(result['paired_screen_pass'])

    def test_endpoint_not_yet_closed_stays_pending(self):
        helper=OutcomeTests();index,lock,p=helper.fixture()
        outcomes,pending=evaluate.outcome_candidates([p(0)],index,lock,'candidate','contract','snapshot',now='2026-01-05T09:00:00+00:00')
        self.assertEqual(outcomes,[]);self.assertEqual(pending,1)


class StrictLossBoundaryTests(unittest.TestCase):
    def test_exact_minus_five_percent_is_not_a_bear_event(self):
        helper=OutcomeTests();index,lock,p=helper.fixture()
        index.loc[0,'Price']=100.;index.loc[20,'Price']=95.
        outcomes,pending=evaluate.outcome_candidates([p(0)],index,lock,'candidate','contract','snapshot',now='2026-06-01T00:00:00+00:00')
        self.assertFalse(outcomes[0]['common_bear'])
        self.assertEqual(outcomes[0]['future_return'],-.05)
        index.loc[20,'Price']=94.99
        outcomes,pending=evaluate.outcome_candidates([p(0)],index,lock,'candidate','contract','snapshot',now='2026-06-01T00:00:00+00:00')
        self.assertTrue(outcomes[0]['common_bear'])
