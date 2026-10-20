"""Temporal decisions must reset over gaps and exclude unknown transitions."""
import unittest
import numpy as np
import pandas as pd
from experiment_regime_state_decisions import causal_state_decisions
from experiment_regime_forward_filter import mature_transition_matrix


class StateFilterTests(unittest.TestCase):
    def test_confirmation_requires_consecutive_evidence_and_resets_at_gap(self):
        calendar=pd.bdate_range('2020-01-01',periods=10)
        dates=calendar[[0,1,2,5,6]]
        scores=np.eye(3)[[1,2,1,0,2]]
        actual=causal_state_decisions(dates,scores,calendar,confirmation=2)
        np.testing.assert_array_equal(actual,[1,1,1,0,0])
        changed=scores.copy();changed[3:]=np.eye(3)[[2,2]]
        altered=causal_state_decisions(dates,changed,calendar,confirmation=2)
        np.testing.assert_array_equal(altered[:3],actual[:3])

    def test_transition_counts_never_bridge_missing_labels_or_include_boundary_outcome(self):
        dates=pd.bdate_range('2020-01-01',periods=60)
        book=pd.DataFrame({'Date':dates[:9],'label_end_date':dates[20:29],
            'vol_label':pd.Series([0,1,pd.NA,pd.NA,2,2,1,0,1],dtype='Int64')})
        matrix,audit=mature_transition_matrix(book,dates[28])
        self.assertEqual(audit['n_history'],6)
        self.assertEqual(audit['raw_pair_counts'][1][2],0)
        self.assertLess(pd.Timestamp(audit['latest_label_end']),dates[28])
        np.testing.assert_allclose(matrix.sum(axis=1),1.)


if __name__=='__main__':unittest.main()
