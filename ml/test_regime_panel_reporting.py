import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import experiment_regime_panel as study


class PanelReportingTests(unittest.TestCase):
    def test_eight_candidate_cli_preserves_metric_dictionary_and_writes_table(self):
        calendar=pd.bdate_range('2020-01-01',periods=32)
        rows=pd.DataFrame(dict(Date=calendar[:12],label_end_date=calendar[20:32],label=np.arange(12)%3,
             future_return=0.,argmax=np.arange(12)%3,causal_macro_weights=np.arange(12)%3,
             majority=1,outer_fold=np.repeat([1,2,3,4],3),refit_block=1))
        rows[study.metrics.PROB_COLUMNS]=np.eye(3)[rows.label]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report'
            with patch.object(study,'prepare_panel',return_value=(None,None,[],[],{})),patch.object(study,'run_panel',return_value=(rows,[])):
                study.main(['--output-dir',str(out)])
            table=pd.read_csv(out/'comparison.csv')
            report=json.loads((out/'report.json').read_text())
            self.assertEqual(len(table),8)
            self.assertEqual(len(report['results']),8)
            self.assertTrue(np.isfinite(table.pooled_f1).all())
            self.assertIsInstance(report['results'][0]['pooled'],dict)
            self.assertTrue(report['results'][1]['pooled_training'])
            self.assertFalse(report['results'][0]['pooled_training'])


if __name__=='__main__':unittest.main()
