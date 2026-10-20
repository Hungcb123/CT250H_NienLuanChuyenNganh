# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4949 | 0.4006 | 0.3023 | 0.4367 | 0.2702 |
| adaptive_pool_smoothed | 0.4973 | 0.3974 | 0.3233 | 0.4244 | 0.2672 |
| adaptive504_smoothed | 0.4940 | 0.3855 | 0.3263 | 0.4182 | 0.2551 |
| adaptive252_raw | 0.4926 | 0.4024 | 0.3274 | 0.4150 | 0.2521 |
| adaptive504_raw | 0.4967 | 0.3863 | 0.3328 | 0.4225 | 0.2594 |

Preset primary screens:
```json
[
  {
    "candidate": "adaptive_pool_smoothed",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "adaptive504_smoothed",
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
    "candidate": "adaptive_pool_smoothed",
    "block_sessions": 20,
    "delta": 0.0023646016979674833,
    "low": -0.014899237635798606,
    "high": 0.01714127791864218
  },
  {
    "candidate": "adaptive_pool_smoothed",
    "block_sessions": 60,
    "delta": 0.0023646016979674833,
    "low": -0.018174973390148473,
    "high": 0.01631843902638542
  },
  {
    "candidate": "adaptive504_smoothed",
    "block_sessions": 20,
    "delta": -0.0009003082954085473,
    "low": -0.02461065533491719,
    "high": 0.020131374133303022
  },
  {
    "candidate": "adaptive504_smoothed",
    "block_sessions": 60,
    "delta": -0.0009003082954085473,
    "low": -0.028024430823426413,
    "high": 0.018702878783543056
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
