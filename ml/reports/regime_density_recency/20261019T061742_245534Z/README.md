# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| info_decay_pool | 0.4581 | 0.3730 | 0.2350 | 0.4040 | 0.2325 |
| info_decay_shrink | 0.4769 | 0.3833 | 0.2761 | 0.4224 | 0.2442 |
| hl126_diagnostic | 0.4534 | 0.3752 | 0.2406 | 0.3890 | 0.2217 |
| hl126_oldprior_diagnostic | 0.4213 | 0.3672 | 0.2068 | 0.3283 | 0.1919 |
| hl252_diagnostic | 0.4719 | 0.3698 | 0.2564 | 0.4228 | 0.2480 |
| hl252_oldprior_diagnostic | 0.4554 | 0.3621 | 0.2243 | 0.4068 | 0.2314 |

Preset primary screens:
```json
[
  {
    "candidate": "info_decay_pool",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "info_decay_shrink",
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
    "candidate": "info_decay_pool",
    "block_sessions": 20,
    "delta": -0.0344320653835225,
    "low": -0.06255900970162913,
    "high": -0.00613425333567944
  },
  {
    "candidate": "info_decay_pool",
    "block_sessions": 60,
    "delta": -0.0344320653835225,
    "low": -0.06624138985937228,
    "high": -0.0035367736318605487
  },
  {
    "candidate": "info_decay_shrink",
    "block_sessions": 20,
    "delta": -0.01559786746795977,
    "low": -0.03326853161783822,
    "high": 0.0019542010232218195
  },
  {
    "candidate": "info_decay_shrink",
    "block_sessions": 60,
    "delta": -0.01559786746795977,
    "low": -0.035982985780786236,
    "high": 0.003765172955868056
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
