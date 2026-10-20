# CatBoost joint return-quantile follow-up — 19 October 2026

Result: no improvement; keep original adaptive-target LightGBM blend. Same 1,560 historical development dates. No application model was replaced.

Two expanding CatBoost regressors learn nine quantiles jointly: raw and volatility-normalized future log return. Original 19 trend/ETF features, fixed 400 iterations/depth4/learning-rate0.03/L2=5, seed42, CPU2. No early stopping or validation outcomes are passed to model.fit. Forecast quantiles are sorted and mapped to the same known +/-1 sigma boundaries; training-class balancing is recomputed on strictly mature rows.

Primary: 50% original classifier scores + 25% original density + 25% new CatBoost density. Each density equally averages raw/normalized targets. Secondary: replace the density half completely with CatBoost. No weight search.

| Candidate | Mean fold macro F1 | Worst fold F1 | Mean bear F1 | Mean bull F1 |
|---|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 |
| new_density | 0.4056 | 0.2747 | 0.1495 | 0.3562 |
| new_density_blend | 0.4660 | 0.3799 | 0.2590 | 0.4146 |
| expanded_density_blend | 0.4785 | 0.3956 | 0.2691 | 0.4288 |

Both new blends fail the predeclared improvement screen. Event probabilities are not calibrated; these are class-balanced decision scores. Repeatedly inspected history, no independent-test claim.

Two real-backend tests verify nine-output integration, exclusion of validation future outcomes and strict mature training supervision. Source hashes remain unchanged from the pre-run plan.

Run from repository root:
```bash
python3 ml/experiment_regime_joint_quantiles.py
```

The inherited specification contains the old quantile levels/quadrature; the actual learner parameters are the explicit JOINT_PARAMETERS recorded in this run’s plan. No old LightGBM learner parameters are used to fit CatBoost.

```json
[
  {
    "candidate": "new_density_blend",
    "block": 20,
    "delta": -0.023329051944475487,
    "low": -0.05270734783390849,
    "high": 0.006352768942290437
  },
  {
    "candidate": "new_density_blend",
    "block": 60,
    "delta": -0.023329051944475487,
    "low": -0.05100647366907437,
    "high": 0.007030002712926376
  },
  {
    "candidate": "expanded_density_blend",
    "block": 20,
    "delta": -0.010771870316949317,
    "low": -0.027546451221181635,
    "high": 0.006142077079106293
  },
  {
    "candidate": "expanded_density_blend",
    "block": 60,
    "delta": -0.010771870316949317,
    "low": -0.02628463926997633,
    "high": 0.004650743270092982
  }
]
```
