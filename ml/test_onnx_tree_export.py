import unittest
import numpy as np
import lightgbm as lgb
import onnxruntime as ort
from onnx_tree_export import convert_lightgbm_float32


class Float32ThresholdTest(unittest.TestCase):
    def test_adjacent_float32_values_follow_native_double_thresholds(self):
        rng=np.random.default_rng(42)
        x=rng.normal(size=(600,2)).astype(np.float32)
        y=np.where(x[:,0]<-.3,0,np.where(x[:,1]>.4,2,1))
        model=lgb.LGBMClassifier(n_estimators=20,num_leaves=7,min_child_samples=5,
                                  verbosity=-1,n_jobs=2).fit(x,y)
        samples=[row.copy() for row in x]
        def visit(node):
            if 'split_feature' not in node:return
            value=np.float32(node['threshold'])
            for adjacent in [np.nextafter(value,np.float32(-np.inf)),value,np.nextafter(value,np.float32(np.inf))]:
                row=np.zeros(2,dtype=np.float32);row[node['split_feature']]=adjacent;samples.append(row)
            visit(node['left_child']);visit(node['right_child'])
        for tree in model.booster_.dump_model()['tree_info']:visit(tree['tree_structure'])
        values=np.asarray(samples,dtype=np.float32)
        converted=convert_lightgbm_float32(model,2)
        options=ort.SessionOptions();options.intra_op_num_threads=2
        session=ort.InferenceSession(converted.SerializeToString(),options)
        actual=session.run([session.get_outputs()[1].name],{'input':values})[0]
        expected=model.predict_proba(values)
        np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=0)
        np.testing.assert_array_equal(actual.argmax(axis=1),expected.argmax(axis=1))


if __name__=='__main__':unittest.main()
