import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
import export_regime_multiclass_scores as study


class NativeScoresTests(unittest.TestCase):
    def test_prior_unbalance_matches_balanced_probability_identity(self):
        prior=np.array([.1,.7,.2]);physical=np.array([[.2,.5,.3],[.1,.8,.1]])
        weighted=physical/prior;weighted/=weighted.sum(axis=1,keepdims=True)
        np.testing.assert_allclose(study.prior_unbalance(weighted,prior),physical)

    def test_invalid_prior_never_silently_fills(self):
        with self.assertRaisesRegex(ValueError,'Invalid prior'):
            study.prior_unbalance([[.2,.5,.3]],[0,.7,.3])

    def test_selector_event_is_held_without_using_future_event(self):
        dates=pd.bdate_range('2020-01-01',periods=5)
        events=pd.DataFrame(dict(Date=dates[[0,3]],selected=['a','b']))
        np.testing.assert_array_equal(study.held_choices(dates,events),['a','a','a','b','b'])
        with self.assertRaisesRegex(ValueError,'before first'):
            study.held_choices(dates,events.iloc[1:])

    def test_frozen_native_source_change_blocks_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract=Path(tmp)/'contract.json';contract.write_text('{}')
            (Path(tmp)/'native_runtime_lock.json').write_text(json.dumps(dict(contract_sha256=study.native.sha(contract),native_source_sha256='0'*64)))
            with self.assertRaisesRegex(ValueError,'Native source changed'):
                study.verify_native_artifacts(contract)


if __name__=='__main__':unittest.main()
