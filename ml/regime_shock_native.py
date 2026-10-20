"""Native feature-to-component inference for shock_shrink research bundles.

No report/label access at inference. Load only trusted locally produced bundles:
joblib forest objects are Python serialization, not a public upload format.
Scores are decision scores, not calibrated probabilities. No web deployment.
"""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
from scipy.spatial.distance import cdist

from regime_shock_score_runtime import RECIPE_ID


def shock_file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ShockNativeBundle:
    """Immutable loaded models plus the mature empirical return populations."""

    def __init__(self, directory):
        directory = Path(directory)
        raw = (directory/'bundle.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != (directory/'bundle.sha256').read_text().strip():
            raise ValueError('Bundle metadata digest mismatch')
        meta = json.loads(raw)
        if meta['schema'] != 1 or meta['recipe_id'] != RECIPE_ID:
            raise ValueError('Unsupported native shock bundle')
        for package, expected in meta['environment'].items():
            if version(package) != expected:
                raise ValueError('Native dependency version changed: '+package)
        # Verify every file BEFORE deserializing any Python object.
        for filename, digest in meta['files'].items():
            if Path(filename).name != filename or shock_file_digest(directory/filename) != digest:
                raise ValueError('Native bundle payload mismatch: '+filename)
        self.meta = meta
        self.models = {}
        for item in meta['models']:
            self.models[item['file']] = (joblib.load(directory/item['file']) if item['kind'] == 'forest'
                                        else lgb.Booster(model_file=str(directory/item['file'])))
        with np.load(directory/'empirical.npz', allow_pickle=False) as archive:
            self.empirical = {key: archive[key] for key in archive.files}

    @staticmethod
    def _balanced(mass, prior):
        score = mass/np.asarray(prior)
        score /= score.sum(axis=1, keepdims=True)
        if not np.isfinite(score).all() or (score < 0).any():
            raise ValueError('Invalid native component score')
        return score

    @staticmethod
    def _leaf_mass(train_leaves, valid_leaves, atoms, low, high):
        result = np.zeros((len(valid_leaves), 3))
        for tree in range(train_leaves.shape[1]):
            for leaf in np.unique(valid_leaves[:, tree]):
                selected = np.flatnonzero(valid_leaves[:, tree] == leaf)
                values = np.sort(atoms[train_leaves[:, tree] == leaf])
                if not len(values):
                    raise ValueError('No mature leaf observations')
                bear = np.searchsorted(values, low[selected], side='left')/len(values)
                bull = 1-np.searchsorted(values, high[selected], side='right')/len(values)
                result[selected] += np.column_stack([bear, 1-bear-bull, bull])
        return np.maximum(result/train_leaves.shape[1], 0.)

    def predict_components(self, features, horizon_sigma):
        """features maps ordered schema names to equal-length completed-close arrays."""
        sigma = np.asarray(horizon_sigma, dtype=float)
        if sigma.ndim != 1 or not len(sigma) or not np.isfinite(sigma).all() or (sigma <= 0).any():
            raise ValueError('Invalid completed-close horizon sigma')
        prior = self.meta['density_prior']
        groups = {key: [] for key in ['classifier', 'quantile', 'forest', 'magnitude', 'shock']}
        quantiles = {}
        for item in self.meta['models']:
            names = item['features']
            x = np.column_stack([features[name] for name in names]).astype(np.float32)
            if len(x) != len(sigma) or np.isinf(x).any():
                raise ValueError('Invalid feature shape or infinity')
            model = self.models[item['file']]
            if item['kind'] == 'classifier':
                groups['classifier'].append(np.asarray(model.predict(x, num_threads=2)))
            elif item['kind'] == 'quantile':
                quantiles.setdefault((item['seed'], item['normalized']), []).append(
                    (item['alpha'], np.asarray(model.predict(x, num_threads=2))))
            else:
                atoms = self.empirical['normalized_returns' if item['normalized'] else 'raw_returns']
                boundary = np.ones(len(sigma)) if item['normalized'] else sigma
                leaves = self.empirical[item['leaf_key']]
                mass = self._leaf_mass(leaves, model.apply(x), atoms, -boundary, boundary)
                groups[item['group']].append(self._balanced(mass, prior))
        weights = np.asarray(self.meta['quantile_atom_weights'])
        for (_, normalized), predictions in sorted(quantiles.items()):
            points = np.column_stack([v for _, v in sorted(predictions, key=lambda p: p[0])])
            if normalized:
                points *= sigma[:, None]
            points.sort(axis=1)
            bear = points < -sigma[:, None]; bull = points > sigma[:, None]
            mass = np.column_stack([(mask*weights).sum(axis=1) for mask in [bear, ~(bear | bull), bull]])
            groups['quantile'].append(self._balanced(mass, prior))
        analogs = []
        for view, names in self.meta['analog_views'].items():
            x = np.column_stack([features[name] for name in names]).astype(float)
            if x.shape != (len(sigma), len(names)) or not np.isfinite(x).all():
                raise ValueError('Analog features must all be finite')
            center, scale = self.empirical[view+'_center'], self.empirical[view+'_scale']
            distance = cdist((x-center)/scale, self.empirical[view+'_scaled'], metric='euclidean')
            ids = np.argsort(distance, axis=1, kind='stable')[:, :min(100, distance.shape[1])]
            nearest = np.take_along_axis(distance, ids, axis=1)
            bandwidth = np.median(nearest, axis=1)
            safe = np.where(bandwidth > 0, bandwidth, 1.)
            weight = np.exp(-.5*(nearest/safe[:, None])**2)
            weight[bandwidth == 0] = (nearest[bandwidth == 0] == 0).astype(float)
            weight /= weight.sum(axis=1, keepdims=True)
            for normalized in [False, True]:
                atoms = self.empirical['normalized_returns' if normalized else 'raw_returns'][ids]
                boundary = np.ones(len(sigma)) if normalized else sigma
                masks = [atoms < -boundary[:, None],
                         (atoms >= -boundary[:, None]) & (atoms <= boundary[:, None]),
                         atoms > boundary[:, None]]
                mass = np.column_stack([(weight*mask).sum(axis=1) for mask in masks])
                mass /= mass.sum(axis=1, keepdims=True)
                analogs.append(self._balanced(mass, prior))
        result = {name: np.mean(parts, axis=0) for name, parts in groups.items()}
        result['analog'] = np.mean(analogs, axis=0)
        for score in result.values():
            if score.shape != (len(sigma), 3) or not np.isfinite(score).all() or (score < 0).any():
                raise ValueError('Invalid loaded component output')
            np.testing.assert_allclose(score.sum(axis=1), 1., rtol=0, atol=1e-12)
        return result
