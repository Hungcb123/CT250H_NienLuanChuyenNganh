"""Independent checks for the custom operators that generic converters miss."""
from types import SimpleNamespace
import unittest

import numpy as np
import onnx
from onnx import TensorProto as T, helper as h
import onnxruntime as ort
from sklearn.ensemble import RandomForestRegressor

from export_regime_shock_onnx import ShockGraph
from regime_shock_native import ShockNativeBundle


class ShockOnnxExportTest(unittest.TestCase):
    def run_graph(self, builder, output, features, sigma):
        graph = h.make_graph(builder.nodes, 'test', [
            h.make_tensor_value_info('features', T.DOUBLE, [None, features.shape[1]]),
            h.make_tensor_value_info('sigma', T.DOUBLE, [None, 1])],
            [h.make_tensor_value_info(output, T.DOUBLE, [None, 3])], builder.constants)
        model = h.make_model(graph, opset_imports=[h.make_opsetid('', 15),
                             h.make_opsetid('ai.onnx.ml', 3)], ir_version=8)
        onnx.checker.check_model(model)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        return ort.InferenceSession(model.SerializeToString(), options).run(
            None, {'features': features, 'sigma': sigma[:, None]})[0]

    def test_forest_uses_empirical_leaf_atoms_and_float32_thresholds(self):
        x = np.arange(40, dtype=np.float32)[:, None]/7
        atoms = np.sin(x[:, 0]).astype(float)
        model = RandomForestRegressor(n_estimators=3, max_depth=3, random_state=7).fit(x, atoms)
        item = dict(file='forest', kind='forest', features=['x'], leaf_key='leaves', normalized=False)
        prior = np.array([.2, .5, .3])
        bundle = SimpleNamespace(meta=dict(models=[item], density_prior=prior),
                                 models={'forest': model}, empirical=dict(raw_returns=atoms, leaves=model.apply(x)))
        builder = ShockGraph(bundle)
        output = builder.forest(item, 'sigma')
        points = [0., 3., 6., np.nan]
        for tree in model.estimators_:
            for threshold in tree.tree_.threshold[tree.tree_.children_left != -1]:
                rounded = np.float32(threshold)
                points.extend([np.nextafter(rounded, np.float32(-np.inf)), rounded,
                               np.nextafter(rounded, np.float32(np.inf))])
        features = np.array(points, dtype=float)[:, None]
        sigma = np.full(len(features), abs(atoms[9]))  # exact equality is sideway
        expected = ShockNativeBundle._balanced(ShockNativeBundle._leaf_mass(
            bundle.empirical['leaves'], model.apply(features.astype(np.float32)), atoms, -sigma, sigma), prior)
        np.testing.assert_allclose(self.run_graph(builder, output, features, sigma), expected, atol=1e-12, rtol=0)

    def test_analog_stable_ties_zero_bandwidth_and_return_boundaries(self):
        # More than 100 equidistant rows exercises TopK's lower-index tie rule.
        population = np.r_[np.zeros(101), np.ones(4)][:, None]
        atoms = np.resize(np.array([-1., 0., 1.]), len(population))
        prior = np.array([.2, .5, .3])
        bundle = SimpleNamespace(meta=dict(models=[dict(features=['x'])], density_prior=prior,
                                           analog_views={'test': ['x']}),
                                 empirical=dict(test_center=np.array([0.]), test_scale=np.array([1.]),
                                                test_scaled=population, raw_returns=atoms,
                                                normalized_returns=atoms))
        builder = ShockGraph(bundle)
        output = builder.analog('sigma')
        features = np.array([[0.], [.5], [2.]])
        sigma = np.array([1., .5, 2.])
        expected = []
        for row, boundary in zip(features, sigma):
            distance = np.abs(population[:, 0]-row[0])
            ids = np.argsort(distance, kind='stable')[:100]
            nearest = distance[ids]
            bandwidth = np.median(nearest)
            weight = ((nearest == 0).astype(float) if bandwidth == 0
                      else np.exp(-.5*(nearest/bandwidth)**2))
            weight /= weight.sum()
            parts = []
            for threshold in [boundary, 1.]:
                a = atoms[ids]
                mass = np.array([weight[a < -threshold].sum(), weight[np.abs(a) <= threshold].sum(),
                                 weight[a > threshold].sum()])
                score = mass/prior
                parts.append(score/score.sum())
            expected.append(np.mean(parts, axis=0))
        np.testing.assert_allclose(self.run_graph(builder, output, features, sigma), expected, atol=1e-12, rtol=0)


if __name__ == '__main__':
    unittest.main()
