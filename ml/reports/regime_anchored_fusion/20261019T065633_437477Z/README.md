# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5085 | 0.3770 | 0.3225 | 0.4564 | 0.2847 |
| anchored_pool | 0.5053 | 0.3825 | 0.3452 | 0.4300 | 0.2682 |
| anchored_adaptive | 0.4980 | 0.3973 | 0.3615 | 0.3989 | 0.2537 |
| anchored252_diagnostic | 0.4942 | 0.3998 | 0.3595 | 0.3917 | 0.2466 |
| anchored504_diagnostic | 0.4958 | 0.3792 | 0.3498 | 0.4044 | 0.2531 |

Preset primary screens:
```json
[
  {
    "candidate": "anchored_pool",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "anchored_adaptive",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  }
]
```

Paired circular-block intervals are descriptive sensitivity on repeatedly inspected history, not multiple-testing-adjusted independent inference. No outer-best diagnostic is automatically promoted.

```json
[
  {
    "candidate": "anchored_pool",
    "block_sessions": 20,
    "delta": -0.003221813663058959,
    "low": -0.021303279368939696,
    "high": 0.01589831692065516
  },
  {
    "candidate": "anchored_pool",
    "block_sessions": 60,
    "delta": -0.003221813663058959,
    "low": -0.021455318092023667,
    "high": 0.015108262597249088
  },
  {
    "candidate": "anchored_adaptive",
    "block_sessions": 20,
    "delta": -0.01051571538742474,
    "low": -0.041459222346303636,
    "high": 0.01774379296985172
  },
  {
    "candidate": "anchored_adaptive",
    "block_sessions": 60,
    "delta": -0.01051571538742474,
    "low": -0.04155134620267721,
    "high": 0.01856776907544039
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
