import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

import regime_multiclass_native as native


class NativeTests(unittest.TestCase):
    def fixture(self):
        calendar=pd.bdate_range('2020-01-01',periods=360)
        frame=pd.DataFrame(dict(Date=calendar[:300],label_end_date=calendar[20:320],label=np.arange(300)%3,
             future_log_return=np.take([-.08,0.,.08],np.arange(300)%3),horizon_sigma=.1,x=np.sin(np.arange(300))))
        index=pd.DataFrame(dict(Date=calendar,Price=100+np.arange(360)*.1))
        contract=dict(feature_schemas={'trend':['x'],'risk':['x']},density_features=['x'],model_refit=dict(
            density_train_windows=['3y','expanding'],quantiles=[.1,.5,.9],quantile_atom_weights=[.25,.5,.25],
            density_parameters=dict(objective='quantile',n_estimators=3,max_depth=2,num_leaves=3,min_child_samples=10,verbosity=-1,n_jobs=2)))
        params={g:dict(n_estimators=3,max_depth=2,num_leaves=3,min_child_samples=10,class_weight='balanced',verbosity=-1,n_jobs=2) for g in ['trend','risk']}
        return frame,index,contract,params

    def test_partition_excludes_boundary_label_and_future_mutations(self):
        frame,index,_,_=self.fixture();boundary=index.Date.iloc[260]
        first=native.native_partition(frame,boundary,['x'],'3y')
        self.assertLess(first.label_end_date.max(),boundary)
        frame.loc[frame.label_end_date>=boundary,'future_log_return']=999.
        second=native.native_partition(frame,boundary,['x'],'3y')
        pd.testing.assert_frame_equal(first,second)

    def test_latest_twenty_feature_rows_do_not_receive_fake_labels(self):
        dates=pd.bdate_range('2020-01-01',periods=380)
        price=100*np.exp(.08*np.sin(np.arange(380)/12))
        index=pd.DataFrame(dict(Date=dates,Price=price))
        etf=pd.DataFrame(dict(Date=dates,Price=price*.2))
        frame=native.feature_frame_native(index,etf)
        self.assertTrue(frame.label.iloc[-20:].isna().all())
        self.assertTrue(frame.label_end_date.iloc[-20:].isna().all())
        self.assertTrue(np.isfinite(frame[native.features.CLOSE_V1_NAMES].iloc[-20:]).all().all())

    def test_native_bundle_roundtrip_and_expert_simplex(self):
        frame,index,contract,params=self.fixture();boundary=index.Date.iloc[260];check=frame.iloc[260:265]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'contract.json';path.write_text(json.dumps(contract))
            key,meta,models=native.fit_native_bundle(frame,index,index,boundary,params,contract,path,Path(tmp)/'cache',check)
            scores,mass=native.infer_native_experts(check,meta,models,contract)
            self.assertEqual(len(models),14)
            self.assertEqual(len(meta['components']),6)
            for item in meta['components']:
                self.assertLess(pd.Timestamp(item['train_label_end']),boundary)
                self.assertLessEqual(item['roundtrip_max_error'],1e-12)
            for values in list(scores.values())+list(mass.values()):
                np.testing.assert_allclose(values.sum(axis=1),1.)
                self.assertTrue((values>=0).all())
            again,_,_=native.fit_native_bundle(frame,index,index,boundary,params,contract,path,Path(tmp)/'cache',check)
            self.assertEqual(key,again)

    def test_changed_native_metadata_and_booster_are_rejected(self):
        frame,index,contract,params=self.fixture();boundary=index.Date.iloc[260]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'contract.json';path.write_text(json.dumps(contract))
            key,meta,_=native.fit_native_bundle(frame,index,index,boundary,params,contract,path,Path(tmp)/'cache',frame.iloc[260:265])
            directory=Path(tmp)/'cache'/key;metadata=directory/'bundle.json';original=metadata.read_text()
            metadata.write_text(original+' ')
            with self.assertRaisesRegex(ValueError,'metadata changed'):native.load_native_bundle(directory,{})
            metadata.write_text(original)
            booster=directory/meta['components'][0]['models'][0]['file'];booster.write_text(booster.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'booster changed'):native.load_native_bundle(directory,{})

    def test_independent_selector_agrees_with_fixed_class_sklearn_f1(self):
        dates=pd.bdate_range('2020-01-01',periods=220)
        history=pd.DataFrame(dict(Date=dates[:180],label_end_date=dates[20:200],label=np.arange(180)%3))
        pool=['legacy_equal','legacy_trend','legacy_risk','density_all','density_expanding']
        for name in pool:history[name]=1
        history['density_all']=history.label
        contract=dict(selector=dict(history_rows=126,min_class_count=5,improvement_margin=.03),selector_pool=pool)
        chosen,audit=native.native_choose(history,dates[180],contract)
        self.assertEqual(chosen,'density_all')
        known=history.loc[history.label_end_date<dates[180]].tail(126)
        for name in pool:
            self.assertAlmostEqual(audit['scores'][name],f1_score(known.label,known[name],labels=[0,1,2],average='macro',zero_division=0))
        history.loc[history.label_end_date>=dates[180],'label']=99
        again,other=native.native_choose(history,dates[180],contract)
        self.assertEqual(chosen,again);self.assertEqual(audit,other)


if __name__=='__main__':unittest.main()
