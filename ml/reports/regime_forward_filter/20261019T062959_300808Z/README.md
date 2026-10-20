# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4949 | 0.4006 | 0.3023 | 0.4367 | 0.2702 |
| filter1 | 0.4710 | 0.3469 | 0.2512 | 0.4148 | 0.2427 |
| filter2 | 0.4813 | 0.3603 | 0.2712 | 0.4242 | 0.2550 |
| filter4 | 0.4927 | 0.3964 | 0.2958 | 0.4328 | 0.2678 |
| filter2_shrink | 0.4910 | 0.3884 | 0.2927 | 0.4308 | 0.2651 |

Preset primary screens:
```json
[
  {
    "candidate": "filter2",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "filter2_shrink",
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
    "candidate": "filter2",
    "block_sessions": 20,
    "delta": -0.013578808336291881,
    "low": -0.028425742453274918,
    "high": 0.0030149810156398955
  },
  {
    "candidate": "filter2",
    "block_sessions": 60,
    "delta": -0.013578808336291881,
    "low": -0.029931876254169897,
    "high": 0.0011172564635334268
  },
  {
    "candidate": "filter2_shrink",
    "block_sessions": 20,
    "delta": -0.003960267171158827,
    "low": -0.014370477302007858,
    "high": 0.007146895555845654
  },
  {
    "candidate": "filter2_shrink",
    "block_sessions": 60,
    "delta": -0.003960267171158827,
    "low": -0.01392741044130036,
    "high": 0.005522976942386573
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
