import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np
import pandas as pd
from regime_long_horizons import fit_forecast

class LongHorizonTest(unittest.TestCase):
    def test_separate_mature_labels_and_response_horizons(self):
        dates=pd.bdate_range('2018-01-01',periods=1400)
        price=100*np.exp(.0004*np.arange(len(dates))+.3*np.sin(np.arange(len(dates))/70))
        raw=pd.DataFrame({'Date':dates,'Close':price})
        with TemporaryDirectory() as directory:
            path=Path(directory)
            for name in ('VNINDEX','E1VFVN30'): raw.to_csv(path/(name+'.csv'),index=False)
            for horizon in (60,120):
                result=fit_forecast(path,horizon,dates[-1].date())
                receipt=result['training_receipt']
                self.assertEqual(result['horizon_sessions'],horizon)
                self.assertTrue(result['experimental'])
                self.assertEqual(result['validation_status'],'NOT_EVALUATED')
                self.assertEqual(receipt['training_last_session'],str(dates[-horizon-1].date()))
                self.assertEqual(receipt['max_label_end_date'],str(dates[-1].date()))
                self.assertAlmostEqual(sum(result['class_scores']),1)
                self.assertEqual(result['signal'],int(np.argmax(result['class_scores']))-1)
                self.assertAlmostEqual(result['net_score'],result['class_scores'][2]-result['class_scores'][0])
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED_HORIZON'): fit_forecast(path,20,dates[-1].date())
            with self.assertRaisesRegex(ValueError,'STALE_OR_INCOMPLETE_SESSION'): fit_forecast(path,60,date(2026,10,19))

if __name__=='__main__': unittest.main()
