# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| shock_shrink | 0.5137 | 0.4031 | 0.3142 | 0.4835 | 0.3005 |
| shock_half | 0.5085 | 0.3925 | 0.3109 | 0.4757 | 0.2915 |

Preset primary screens:
```json
[
  {
    "candidate": "shock_shrink",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "shock_half",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  }
]
```

Paired circular-block intervals are descriptive sensitivity on repeatedly inspected history, not multiple-testing-adjusted independent inference. No outer-best diagnostic is automatically promoted.

```json
[
  {
    "candidate": "shock_shrink",
    "block_sessions": 20,
    "delta": -0.0007432514500523846,
    "low": -0.010330795902118063,
    "high": 0.008322305747742459
  },
  {
    "candidate": "shock_shrink",
    "block_sessions": 60,
    "delta": -0.0007432514500523846,
    "low": -0.008316626812792447,
    "high": 0.008387806809826294
  },
  {
    "candidate": "shock_half",
    "block_sessions": 20,
    "delta": -0.005989662872098456,
    "low": -0.023934585176215297,
    "high": 0.01688412379778518
  },
  {
    "candidate": "shock_half",
    "block_sessions": 60,
    "delta": -0.005989662872098456,
    "low": -0.019163586394190486,
    "high": 0.015907568848951704
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
