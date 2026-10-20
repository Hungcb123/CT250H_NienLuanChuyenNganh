# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5085 | 0.3770 | 0.3225 | 0.4564 | 0.2847 |
| RandomForest_shrink | 0.5121 | 0.3911 | 0.3165 | 0.4784 | 0.2959 |
| RandomForest_replace_diagnostic | 0.4896 | 0.3652 | 0.2959 | 0.4612 | 0.2746 |
| ExtraTrees_shrink | 0.4994 | 0.3805 | 0.3005 | 0.4587 | 0.2771 |
| ExtraTrees_replace_diagnostic | 0.4801 | 0.3713 | 0.2730 | 0.4509 | 0.2551 |

Preset primary screens:
```json
[
  {
    "candidate": "RandomForest_shrink",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "ExtraTrees_shrink",
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
    "candidate": "RandomForest_shrink",
    "block_sessions": 20,
    "delta": 0.003674744767996563,
    "low": -0.010596233894805596,
    "high": 0.020421625913609093
  },
  {
    "candidate": "RandomForest_shrink",
    "block_sessions": 60,
    "delta": 0.003674744767996563,
    "low": -0.010441356112333247,
    "high": 0.021861827588816194
  },
  {
    "candidate": "ExtraTrees_shrink",
    "block_sessions": 20,
    "delta": -0.00911784798480253,
    "low": -0.027153997108168283,
    "high": 0.009837563415644316
  },
  {
    "candidate": "ExtraTrees_shrink",
    "block_sessions": 60,
    "delta": -0.00911784798480253,
    "low": -0.027426988256313397,
    "high": 0.01160479040891222
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
