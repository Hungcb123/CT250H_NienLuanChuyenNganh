"""Export the frozen shock_shrink ensemble, including empirical distributions.

No refit, distillation, quantization or new parameter selection. The graph accepts
completed features, horizon sigma and explicit EMA state; callers own calendars,
input validation and persistence. Outputs are decision scores, not probabilities.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

import numpy as np
import onnx
from onnx import TensorProto as T, helper as h, numpy_helper as nh
import onnxruntime as ort
from onnx_tree_export import convert_lightgbm_float32

from regime_shock_native import ShockNativeBundle, shock_file_digest
from regime_shock_score_runtime import RECIPE_ID, ShockScoreRuntime


class ShockGraph:
    """Small ONNX builder; all distribution arithmetic remains float64."""

    def __init__(self, bundle):
        self.bundle = bundle
        self.features = list(dict.fromkeys(n for m in bundle.meta['models'] for n in m['features']))
        self.nodes, self.constants = [], []
        self.serial = 0

    def name(self):
        self.serial += 1
        return 'v'+str(self.serial)

    def const(self, value, dtype=np.float64):
        name = self.name()
        self.constants.append(nh.from_array(np.asarray(value, dtype=dtype), name))
        return name

    def op(self, kind, *args, outputs=1, **attrs):
        names = [self.name() for _ in range(outputs)]
        self.nodes.append(h.make_node(kind, list(args), names, **attrs))
        return names[0] if outputs == 1 else names

    def cast(self, x, to=T.DOUBLE):
        return self.op('Cast', x, to=to)

    def gather(self, x, ids, axis=0):
        return self.op('Gather', x, self.const(ids, np.int64), axis=axis)

    def reduce(self, kind, x, axes, keepdims=1):
        # Opset 15: ReduceSum uses a tensor for axes; ReduceMean an attribute.
        if kind == 'ReduceSum':
            return self.op(kind, x, self.const(axes, np.int64), keepdims=keepdims)
        return self.op(kind, x, axes=axes, keepdims=keepdims)

    def unsqueeze(self, x, axes):
        return self.op('Unsqueeze', x, self.const(axes, np.int64))

    def scale(self, x, factor):
        return self.op('Mul', x, self.const(factor))

    def normalize(self, x):
        return self.op('Div', x, self.reduce('ReduceSum', x, [1]))

    def balanced(self, x):
        return self.normalize(self.op('Div', x, self.const(self.bundle.meta['density_prior'])))

    def mean(self, values):
        return self.scale(self.op('Sum', *values), 1/len(values))

    def select(self, names, float32=False):
        x = self.gather('features', [self.features.index(n) for n in names], axis=1)
        return self.cast(x, T.FLOAT) if float32 else x

    def lightgbm(self, item):
        model = self.bundle.models[item['file']]
        converted = convert_lightgbm_float32(model, len(item['features']))
        prefix = self.name()+'_'
        converted = onnx.compose.add_prefix(converted, prefix)
        x = self.select(item['features'], float32=True)
        self.nodes.append(h.make_node('Identity', [x], [converted.graph.input[0].name]))
        self.nodes.extend(converted.graph.node)
        self.constants.extend(converted.graph.initializer)
        out = converted.graph.output[1 if item['kind'] == 'classifier' else 0].name
        return self.cast(out)

    def forest(self, item, sigma):
        """Export apply(), NOT predict(): scores use empirical atoms in each leaf."""
        model = self.bundle.models[item['file']]
        attrs = defaultdict(list)
        for tree_id, estimator in enumerate(model.estimators_):
            tree = estimator.tree_
            for node_id in range(tree.node_count):
                leaf = tree.children_left[node_id] == -1
                threshold = np.float32(tree.threshold[node_id])
                # sklearn compares float32 input with a double threshold. Round
                # downward to preserve <= at the adjacent representable inputs.
                if float(threshold) > tree.threshold[node_id]:
                    threshold = np.nextafter(threshold, np.float32(-np.inf))
                fields = dict(nodes_treeids=tree_id, nodes_nodeids=node_id,
                              nodes_featureids=0 if leaf else int(tree.feature[node_id]),
                              nodes_modes='LEAF' if leaf else 'BRANCH_LEQ',
                              nodes_values=float(threshold),
                              nodes_truenodeids=0 if leaf else int(tree.children_left[node_id]),
                              nodes_falsenodeids=0 if leaf else int(tree.children_right[node_id]),
                              nodes_missing_value_tracks_true=int(tree.missing_go_to_left[node_id]))
                for key, value in fields.items():
                    attrs[key].append(value)
                if leaf:
                    for key, value in dict(target_treeids=tree_id, target_nodeids=node_id,
                                           target_ids=tree_id, target_weights=float(node_id)).items():
                        attrs[key].append(value)
        leaves = self.op('TreeEnsembleRegressor', self.select(item['features'], True),
                         domain='ai.onnx.ml', n_targets=len(model.estimators_),
                         aggregate_function='SUM', post_transform='NONE', **attrs)
        population = self.bundle.empirical[item['leaf_key']].astype(np.int32)
        matches = self.cast(self.op('Equal', self.unsqueeze(self.cast(leaves, T.INT32), [1]),
                                    self.const(population, np.int32)))
        # Normalize separately inside each tree, then average the trees. This
        # reproduces the empirical forest rather than the regressor leaf mean.
        weights = self.reduce('ReduceMean', self.op('Div', matches,
                              self.reduce('ReduceSum', matches, [1])), [2], keepdims=0)
        atoms = self.const(self.bundle.empirical['normalized_returns' if item['normalized'] else 'raw_returns'])
        boundary = self.const(1.) if item['normalized'] else sigma
        bear = self.op('Less', atoms, self.op('Neg', boundary))
        bull = self.op('Greater', atoms, boundary)
        # Native leaf masses use 1 - upper CDF; preserve that operation order.
        lo = self.reduce('ReduceSum', self.op('Mul', weights, self.cast(bear)), [1])
        upper = self.reduce('ReduceSum', self.op('Mul', weights, self.cast(self.op('Not', bull))), [1])
        hi = self.op('Sub', self.const(1.), upper)
        middle = self.op('Sub', self.op('Sub', self.const(1.), lo), hi)
        mass = self.op('Max', self.op('Concat', lo, middle, hi, axis=1), self.const(0.))
        return self.balanced(mass)

    def analog(self, sigma):
        scores = []
        empirical = self.bundle.empirical
        for view, names in self.bundle.meta['analog_views'].items():
            x = self.op('Div', self.op('Sub', self.select(names), self.const(empirical[view+'_center'])),
                        self.const(empirical[view+'_scale']))
            # Direct differences preserve cdist's distance better than the
            # cancellation-prone ||x||^2 + ||y||^2 - 2*x*y identity.
            delta = self.op('Sub', self.unsqueeze(x, [1]), self.const(empirical[view+'_scaled']))
            distance = self.op('Sqrt', self.reduce('ReduceSum', self.op('Mul', delta, delta), [2], keepdims=0))
            k = min(100, len(empirical[view+'_scaled']))
            nearest, ids = self.op('TopK', distance, self.const([k], np.int64),
                                   axis=1, largest=0, sorted=1, outputs=2)
            median = self.mean([self.gather(nearest, [i], 1) for i in [(k-1)//2, k//2]])
            zero = self.op('Equal', median, self.const(0.))
            safe = self.op('Where', zero, self.const(1.), median)
            ratio = self.op('Div', nearest, safe)
            weight = self.op('Exp', self.scale(self.op('Mul', ratio, ratio), -.5))
            weight = self.normalize(self.op('Where', zero, self.cast(self.op('Equal', nearest, self.const(0.))), weight))
            for normalized in [False, True]:
                atoms = self.op('Gather', self.const(empirical['normalized_returns' if normalized else 'raw_returns']), ids, axis=0)
                boundary = self.const(1.) if normalized else sigma
                scores.append(self.balanced(self.mass(atoms, boundary, weight)))
        return self.mean(scores)

    def mass(self, atoms, boundary, weight):
        bear = self.op('Less', atoms, self.op('Neg', boundary))
        bull = self.op('Greater', atoms, boundary)
        side = self.op('Not', self.op('Or', bear, bull))
        return self.normalize(self.op('Concat', *[
            self.reduce('ReduceSum', self.op('Mul', self.cast(mask), weight), [1])
            for mask in [bear, side, bull]], axis=1))

    def build(self):
        sigma = self.unsqueeze('horizon_sigma', [1])
        groups, quantiles = defaultdict(list), defaultdict(list)
        for item in self.bundle.meta['models']:
            print('Export', item['file'], flush=True)
            if item['kind'] == 'forest':
                groups[item['group']].append(self.forest(item, sigma))
            else:
                out = self.lightgbm(item)
                if item['kind'] == 'classifier':
                    groups['classifier'].append(out)
                else:
                    quantiles[item['seed'], item['normalized']].append((item['alpha'], out))
        for (_, normalized), values in sorted(quantiles.items()):
            points = self.op('Concat', *[v for _, v in sorted(values)], axis=1)
            if normalized:
                points = self.op('Mul', points, sigma)
            points, _ = self.op('TopK', points, self.const([len(values)], np.int64),
                                axis=1, largest=0, sorted=1, outputs=2)
            groups['quantile'].append(self.balanced(self.mass(points, sigma, self.const(self.bundle.meta['quantile_atom_weights']))))
        parts = {key: self.mean(value) for key, value in groups.items()}
        parts['analog'] = self.analog(sigma)
        basic = self.op('Sum', self.scale(parts['quantile'], .5), self.scale(parts['forest'], .25), self.scale(parts['magnitude'], .25))
        analog = self.op('Add', self.scale(basic, .75), self.scale(parts['analog'], .25))
        density = self.op('Add', self.scale(analog, .75), self.scale(parts['shock'], .25))
        weight = self.gather('parameters', 0)
        c = self.normalize(self.op('Pow', parts['classifier'], self.op('Div', self.const(1.), self.gather('parameters', 1))))
        d = self.normalize(self.op('Pow', density, self.op('Div', self.const(1.), self.gather('parameters', 2))))
        raw = self.op('Add', self.op('Mul', self.op('Sub', self.const(1.), weight), c), self.op('Mul', weight, d))
        ema = self.op('Where', 'contiguous', self.op('Add', self.op('Div', raw, self.const(3.)), self.scale('previous_ema', 2/3)), raw)
        scores = self.op('Add', self.scale(raw, .5), self.scale(ema, .5))
        signal = self.op('Sub', self.op('ArgMax', scores, axis=1, keepdims=0), self.const(1, np.int64))
        outputs = []
        for name, value, dtype, shape in [('class_scores', scores, T.DOUBLE, [None, 3]),
                                          ('signal', signal, T.INT64, [None]),
                                          ('ema', ema, T.DOUBLE, [None, 3]),
                                          *[(k, v, T.DOUBLE, [None, 3]) for k, v in parts.items()]]:
            self.nodes.append(h.make_node('Identity', [value], [name]))
            outputs.append(h.make_tensor_value_info(name, dtype, shape))
        inputs = [h.make_tensor_value_info(name, dtype, shape) for name, dtype, shape in [
            ('features', T.DOUBLE, [None, len(self.features)]), ('horizon_sigma', T.DOUBLE, [None]),
            ('parameters', T.DOUBLE, [3]), ('previous_ema', T.DOUBLE, [None, 3]), ('contiguous', T.BOOL, [])]]
        model = h.make_model(h.make_graph(self.nodes, 'shock_shrink', inputs, outputs, self.constants),
                             opset_imports=[h.make_opsetid('', 15), h.make_opsetid('ai.onnx.ml', 3)],
                             ir_version=8, producer_name='equifolio-shock-export')
        h.set_model_props(model, {'recipe_id': RECIPE_ID, 'features': json.dumps(self.features),
                                  'score_semantics': 'class_balanced_decision_scores_not_probabilities',
                                  'source_bundle_sha256': shock_file_digest(Path(self.bundle.directory)/'bundle.json')})
        onnx.checker.check_model(model)
        return model


def export_shock_onnx(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent/'data/research/brokers_2010_20261001_reviewed')
    parser.add_argument('--benchmark-runs', type=int, default=20)
    args = parser.parse_args(argv)
    if args.output_dir.exists() or args.benchmark_runs < 1:
        parser.error('output-dir must be new and benchmark-runs must be positive')
    bundle = ShockNativeBundle(args.bundle)
    bundle.directory = args.bundle
    builder = ShockGraph(bundle)
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='onnx_build_', dir=args.output_dir.parent))
    try:
        model = builder.build()
        path = temporary/'shock_regime.onnx'
        onnx.save(model, path)
        from regime_shock_features import completed_shock_features
        frame, _ = completed_shock_features(args.data_dir)
        # Test all finite available feature rows, including historical rows.
        # This checks conversion, not out-of-sample predictive performance.
        valid = np.isfinite(frame[builder.features].to_numpy(dtype=float)).all(axis=1)
        valid &= np.isfinite(frame.horizon_sigma) & (frame.horizon_sigma > 0)
        frame = frame.loc[valid].copy()
        if len(frame) < 100:
            raise ValueError('Insufficient parity rows')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
        parameters = np.array([.75, .75, 1.5])
        errors = defaultdict(float)
        matched = 0
        # Bound the forest membership tensor's memory when checking history.
        for start in range(0, len(frame), 8):
            if start % 80 == 0:
                print(f'Parity {start}/{len(frame)}', flush=True)
            rows = frame.iloc[start:start+8]
            features = {n: rows[n].to_numpy() for n in builder.features}
            native = bundle.predict_components(features, rows.horizon_sigma.to_numpy())
            feed = dict(features=rows[builder.features].to_numpy(dtype=np.float64),
                        horizon_sigma=rows.horizon_sigma.to_numpy(dtype=np.float64), parameters=parameters,
                        previous_ema=np.zeros((len(rows), 3)), contiguous=np.array(False))
            actual = dict(zip([o.name for o in session.get_outputs()], session.run(None, feed)))
            for name, expected in native.items():
                errors[name] = max(errors[name], float(np.max(np.abs(actual[name]-expected))))
                np.testing.assert_allclose(actual[name], expected, atol=1e-5, rtol=0, err_msg=name)
            for i in range(len(rows)):
                reference = ShockScoreRuntime('onnx-parity')
                expected = reference.predict('2026-10-01', None, {n: v[i] for n, v in native.items()}, parameters)
                np.testing.assert_allclose(actual['class_scores'][i], expected['class_scores'], atol=1e-5, rtol=0)
                errors['class_scores'] = max(errors['class_scores'], float(np.max(np.abs(actual['class_scores'][i]-expected['class_scores']))))
                if actual['signal'][i] != expected['signal']:
                    raise AssertionError('ONNX changed a predicted label')
                matched += 1
        # Check carried EMA as well as cold starts, using a real sequence.
        reference = ShockScoreRuntime('onnx-sequence')
        state = np.zeros((1, 3))
        sequence = frame.tail(32)
        native = bundle.predict_components({n: sequence[n].to_numpy() for n in builder.features}, sequence.horizon_sigma.to_numpy())
        previous = None
        for i, (_, row) in enumerate(sequence.iterrows()):
            date = str(row.Date.date())
            expected = reference.predict(date, previous, {n: v[i] for n, v in native.items()}, parameters)
            feed = dict(features=row[builder.features].to_numpy(dtype=np.float64)[None, :],
                        horizon_sigma=np.array([row.horizon_sigma]), parameters=parameters,
                        previous_ema=state, contiguous=np.array(previous is not None))
            scores, signal, state = session.run(['class_scores', 'signal', 'ema'], feed)
            np.testing.assert_allclose(scores[0], expected['class_scores'], atol=1e-5, rtol=0)
            np.testing.assert_allclose(state[0], reference.ema, atol=1e-5, rtol=0)
            assert signal[0] == expected['signal']
            previous = date
        # Warm both engines; compare identical feature-to-component work, no HTTP.
        last = frame.iloc[[-1]]
        features = {n: last[n].to_numpy() for n in builder.features}
        sigma = last.horizon_sigma.to_numpy()
        native_call = lambda: bundle.predict_components(features, sigma)
        names = list(native)
        onnx_call = lambda: session.run(names, feed)
        timings = {}
        for name, call in [('python_native', native_call), ('onnxruntime_cpu', onnx_call)]:
            call()
            samples = []
            for _ in range(args.benchmark_runs):
                before = perf_counter(); call(); samples.append((perf_counter()-before)*1000)
            timings[name] = dict(median_ms=float(np.median(samples)), p95_ms=float(np.percentile(samples, 95)))
        contract = dict(schema=1, recipe_id=RECIPE_ID, features=builder.features,
                        source_bundle_sha256=shock_file_digest(args.bundle/'bundle.json'),
                        boundary=bundle.meta['boundary'], parameters=parameters.tolist(),
                        class_order=['bearish', 'sideway', 'bullish'], class_scores_are_probabilities=False,
                        state_policy='Caller validates sessions and sets contiguous only for the actual predecessor; persist returned ema after success.',
                        inputs={v.name: str(v.type) for v in session.get_inputs()},
                        parity=dict(rows=matched, matching_labels=matched, max_absolute_errors=dict(errors),
                                    ema_sequence_rows=len(sequence), tolerance=1e-5,
                                    predictive_accuracy_evaluation=False),
                        benchmark=dict(runs=args.benchmark_runs, threads=2, includes_feature_engineering=False, timings=timings))
        (temporary/'contract.json').write_text(json.dumps(contract, indent=2)+'\n')
        # Store Python reference outputs (not ONNX outputs) for cross-language
        # contract tests. The final sequence feed still holds its incoming EMA.
        cold = ShockScoreRuntime('onnx-fixture').predict(
            str(last.Date.iloc[0].date()), None,
            {n: v[-1] for n, v in native.items()}, parameters)
        fixtures = []
        for contiguous, incoming, result in [(False, np.zeros((1, 3)), cold),
                                              (True, feed['previous_ema'], expected)]:
            fixtures.append(dict(features=last[builder.features].to_numpy(dtype=np.float64).tolist(),
                                 horizon_sigma=sigma.tolist(), parameters=parameters.tolist(),
                                 previous_ema=incoming.tolist(), contiguous=contiguous,
                                 class_scores=[result['class_scores']], signal=[result['signal']],
                                 components={n: [v[-1].tolist()] for n, v in native.items()}))
        (temporary/'parity_fixture.json').write_text(json.dumps(fixtures, indent=2)+'\n')
        checksums = {p.name: shock_file_digest(p) for p in temporary.iterdir()}
        (temporary/'checksums.json').write_text(json.dumps(checksums, indent=2)+'\n')
        temporary.rename(args.output_dir)
        print(json.dumps(contract, indent=2))
    except BaseException:
        shutil.rmtree(temporary)
        raise


if __name__ == '__main__':
    export_shock_onnx()
