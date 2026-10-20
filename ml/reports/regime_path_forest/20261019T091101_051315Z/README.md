# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5137 | 0.4031 | 0.3142 | 0.4835 | 0.3005 |
| path_shrink | 0.5112 | 0.4031 | 0.3082 | 0.4820 | 0.2975 |

Preset primary screens:
```json
[
  {
    "candidate": "path_shrink",
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
    "candidate": "path_shrink",
    "block_sessions": 20,
    "delta": -0.002554439532265418,
    "low": -0.006684137118746235,
    "high": 0.0005611187398657122
  },
  {
    "candidate": "path_shrink",
    "block_sessions": 60,
    "delta": -0.002554439532265418,
    "low": -0.005685509752482251,
    "high": 0.00048614177736003566
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
