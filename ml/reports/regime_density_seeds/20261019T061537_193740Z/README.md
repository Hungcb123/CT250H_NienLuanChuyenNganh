# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| stable63 | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| info_seed5 | 0.4932 | 0.4024 | 0.2965 | 0.4402 | 0.2675 |
| info_seed5_shrink | 0.4917 | 0.3986 | 0.2910 | 0.4406 | 0.2669 |
| stable_seed5 | 0.4881 | 0.4024 | 0.3008 | 0.4258 | 0.2574 |
| seed42_diagnostic | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| seed7_diagnostic | 0.4896 | 0.4024 | 0.3044 | 0.4268 | 0.2570 |
| seed21_diagnostic | 0.4927 | 0.4039 | 0.3020 | 0.4360 | 0.2640 |
| seed84_diagnostic | 0.4901 | 0.3996 | 0.2876 | 0.4419 | 0.2655 |
| seed126_diagnostic | 0.4879 | 0.4010 | 0.2896 | 0.4381 | 0.2584 |

Preset primary screens:
```json
[
  {
    "candidate": "info_seed5",
    "fold_wins": 3,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "info_seed5_shrink",
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
    "candidate": "info_seed5",
    "block_sessions": 20,
    "delta": 0.0007227710415944055,
    "low": -0.006835043322949377,
    "high": 0.009474856267333062
  },
  {
    "candidate": "info_seed5",
    "block_sessions": 60,
    "delta": 0.0007227710415944055,
    "low": -0.007019398931261908,
    "high": 0.010034149653682652
  },
  {
    "candidate": "info_seed5_shrink",
    "block_sessions": 20,
    "delta": -0.0007867134982756374,
    "low": -0.006842172615413276,
    "high": 0.0060382712020376796
  },
  {
    "candidate": "info_seed5_shrink",
    "block_sessions": 60,
    "delta": -0.0007867134982756374,
    "low": -0.006934741889688229,
    "high": 0.006065228745863979
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
