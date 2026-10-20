# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| volume_shrink | 0.5129 | 0.3937 | 0.3187 | 0.4772 | 0.2952 |
| volume_replace | 0.5129 | 0.3937 | 0.3187 | 0.4772 | 0.2952 |

Preset primary screens:
```json
[
  {
    "candidate": "volume_shrink",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "volume_replace",
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
    "candidate": "volume_shrink",
    "block_sessions": 20,
    "delta": -0.0015739977328280697,
    "low": -0.004377528635453945,
    "high": 0.0006578202267089283
  },
  {
    "candidate": "volume_shrink",
    "block_sessions": 60,
    "delta": -0.0015739977328280697,
    "low": -0.0036192849211047233,
    "high": 0.0006298467234596145
  },
  {
    "candidate": "volume_replace",
    "block_sessions": 20,
    "delta": -0.0015739977328280697,
    "low": -0.004481800204238854,
    "high": 0.0009162428862025389
  },
  {
    "candidate": "volume_replace",
    "block_sessions": 60,
    "delta": -0.0015739977328280697,
    "low": -0.003820161097809817,
    "high": 0.0009513720292968201
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
