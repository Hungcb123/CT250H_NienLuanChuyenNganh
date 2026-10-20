# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5121 | 0.3911 | 0.3165 | 0.4784 | 0.2959 |
| joint_macro | 0.4953 | 0.3554 | 0.3153 | 0.4351 | 0.2670 |
| joint_robust | 0.4771 | 0.3554 | 0.2669 | 0.4334 | 0.2527 |
| joint_shrink | 0.4869 | 0.3637 | 0.2804 | 0.4459 | 0.2660 |

Preset primary screens:
```json
[
  {
    "candidate": "joint_robust",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "joint_shrink",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  }
]
```

Paired circular-block intervals are descriptive sensitivity on repeatedly inspected history, not multiple-testing-adjusted independent inference. No outer-best diagnostic is automatically promoted.

```json
[
  {
    "candidate": "joint_robust",
    "block_sessions": 20,
    "delta": -0.03509280114086538,
    "low": -0.05521416060621182,
    "high": -0.013759018054272421
  },
  {
    "candidate": "joint_robust",
    "block_sessions": 60,
    "delta": -0.03509280114086538,
    "low": -0.05069626650434602,
    "high": -0.010939423482614933
  },
  {
    "candidate": "joint_shrink",
    "block_sessions": 20,
    "delta": -0.025243276737909937,
    "low": -0.042640959007377535,
    "high": -0.008068150816694224
  },
  {
    "candidate": "joint_shrink",
    "block_sessions": 60,
    "delta": -0.025243276737909937,
    "low": -0.038276495836337826,
    "high": -0.007812101823397992
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
