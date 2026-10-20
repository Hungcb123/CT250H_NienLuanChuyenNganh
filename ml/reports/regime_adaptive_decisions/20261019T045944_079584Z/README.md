# Delayed decision adaptation — 19 October 2026

Result: reject pooled adapter as an improvement; retain frozen adaptive-target blend. Same 1,560 historical development dates; no independent test or deployment.

Every 20 market sessions, use only archived out-of-fit labels ending strictly before the refresh. Two fixed history lengths (252/504), at least 126 mature rows and five examples per class. Coarse decision weights use the old fixed grid and penalty; logistic adapters use training-only scaling, C=0.1 and balanced class weights. Inputs are CLR incumbent scores and known log-volatility/normalized past20 return. No unavailable outcome may enter training.

Primary model: 50% incumbent plus 50% equal four adapters. Standalone adapters are diagnostic, not an outer-selected replacement. Warmup or insufficient class history returns incumbent scores. No score is asserted to be a calibrated event probability.

| Candidate | Mean fold macro F1 | Worst fold F1 | Mean bear F1 | Mean bull F1 |
|---|---:|---:|---:|---:|
| weights_252 | 0.4886 | 0.3937 | 0.3171 | 0.4221 |
| logistic_252 | 0.3674 | 0.2638 | 0.1798 | 0.3186 |
| weights_504 | 0.4569 | 0.4000 | 0.2101 | 0.4273 |
| logistic_504 | 0.4154 | 0.3385 | 0.1671 | 0.4201 |
| pooled_adapter | 0.4719 | 0.3780 | 0.2691 | 0.4145 |
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 |

All five replay-prefix tests pass after corrupting unavailable outcomes. The full scores, fitted adapter states and error analysis are archived.

The primary adapter fails the predeclared point screen. Do not change its weights or pick a standalone window based on these outer results.

```json
[
  {
    "block": 20,
    "delta": -0.017386834207510304,
    "low": -0.04017921364254544,
    "high": 0.008802993904407646
  },
  {
    "block": 60,
    "delta": -0.017386834207510304,
    "low": -0.039902484586081456,
    "high": 0.014534232233959306
  }
]
```

Run:
```bash
python3 ml/experiment_regime_adaptive_decisions.py
```
