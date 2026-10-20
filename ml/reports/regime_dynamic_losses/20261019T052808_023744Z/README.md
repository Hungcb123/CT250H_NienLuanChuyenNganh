# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| legacy_equal | 0.4488 | 0.3908 | 0.2461 | 0.4134 | 0.2150 |
| ce | 0.4040 | 0.3165 | 0.1859 | 0.3808 | 0.1654 |
| smooth05 | 0.4102 | 0.3241 | 0.1941 | 0.3877 | 0.1740 |
| smooth10 | 0.4023 | 0.3163 | 0.1902 | 0.3736 | 0.1655 |
| focal1 | 0.4120 | 0.3215 | 0.1742 | 0.3874 | 0.1856 |
| focal2 | 0.4098 | 0.3335 | 0.1768 | 0.3817 | 0.1849 |
| legacy_equal_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| ce_blend | 0.4661 | 0.3466 | 0.2572 | 0.4262 | 0.2440 |
| smooth05_blend | 0.4751 | 0.3480 | 0.2719 | 0.4339 | 0.2531 |
| smooth10_blend | 0.4765 | 0.3495 | 0.2818 | 0.4237 | 0.2551 |
| focal1_blend | 0.4873 | 0.3752 | 0.2706 | 0.4444 | 0.2823 |
| focal2_blend | 0.4794 | 0.3579 | 0.2574 | 0.4331 | 0.2715 |
| inner_supplement_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| inner_replacement_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |

Preset primary screens:
```json
[
  {
    "candidate": "inner_supplement_blend",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "inner_replacement_blend",
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
    "candidate": "inner_supplement_blend",
    "block_sessions": 20,
    "delta": 0.0,
    "low": 0.0,
    "high": 0.0
  },
  {
    "candidate": "inner_supplement_blend",
    "block_sessions": 60,
    "delta": 0.0,
    "low": 0.0,
    "high": 0.0
  },
  {
    "candidate": "inner_replacement_blend",
    "block_sessions": 20,
    "delta": 0.0,
    "low": 0.0,
    "high": 0.0
  },
  {
    "candidate": "inner_replacement_blend",
    "block_sessions": 60,
    "delta": 0.0,
    "low": 0.0,
    "high": 0.0
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
