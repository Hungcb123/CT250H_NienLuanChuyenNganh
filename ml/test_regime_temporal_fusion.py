"""Fixed-class metric vectorization and delayed fusion leakage checks."""
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
import experiment_regime_temporal_fusion as study


class TemporalFusionTests(unittest.TestCase):
    def test_vectorized_macro_matches_sklearn_with_absent_classes(self):
        rng=np.random.default_rng(8)
        for actual in [rng.integers(0,3,83),np.ones(83,dtype=int)]:
            predictions=rng.integers(0,3,size=(45,83))
            expected=[f1_score(actual,p,labels=[0,1,2],average='macro',zero_division=0) for p in predictions]
            np.testing.assert_allclose(study.macro_scores_many(actual,predictions),expected,atol=1e-12)

    def test_learned_fusion_ignores_unavailable_outcomes(self):
        dates=pd.bdate_range('2020-01-01',periods=260);y=np.arange(220)%3
        base=pd.DataFrame({'Date':dates[:220],'label_end_date':dates[20:240],'label':y})
        classifier=np.full((220,3),.2);classifier[np.arange(220),y]=.6
        density=np.full((220,3),.1);density[np.arange(220),(y+1)%3]=.8
        expected,audit=study.choose_temporal_fusion(base,classifier,density,dates)
        self.assertTrue(any(s['choice']!=0 for s in audit))
        end=190;prefix=base.iloc[:end].copy()
        prefix.loc[prefix.label_end_date>=prefix.Date.iloc[-1],'label']=99
        actual,_=study.choose_temporal_fusion(prefix,classifier[:end],density[:end],dates[:end])
        for window in expected:np.testing.assert_allclose(actual[window],expected[window][:end],atol=1e-12)


if __name__=='__main__':unittest.main()
