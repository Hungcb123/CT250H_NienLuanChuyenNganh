# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| matched_target | 0.3770 | 0.3233 | 0.1831 | 0.3421 | 0.1374 |
| matched_target_blend | 0.4607 | 0.3885 | 0.2680 | 0.3942 | 0.2190 |
| extended_target | 0.4626 | 0.3911 | 0.3017 | 0.4500 | 0.2510 |
| extended_target_blend | 0.4675 | 0.3817 | 0.2729 | 0.4064 | 0.2300 |
| extended_pooled | 0.4599 | 0.3784 | 0.3114 | 0.4423 | 0.2553 |
| extended_pooled_blend | 0.4703 | 0.3831 | 0.2690 | 0.4142 | 0.2390 |

Preset primary screens:
```json
[
  {
    "candidate": "extended_pooled_blend",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "extended_target_blend",
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
    "candidate": "extended_pooled_blend",
    "block_sessions": 20,
    "delta": -0.018985624440489957,
    "low": -0.03929433008461601,
    "high": 0.0027785166025472764
  },
  {
    "candidate": "extended_pooled_blend",
    "block_sessions": 60,
    "delta": -0.018985624440489957,
    "low": -0.038801364461727335,
    "high": 0.0025503952135941432
  },
  {
    "candidate": "extended_target_blend",
    "block_sessions": 20,
    "delta": -0.02185639721898941,
    "low": -0.03808481995597252,
    "high": -0.001227213164563639
  },
  {
    "candidate": "extended_target_blend",
    "block_sessions": 60,
    "delta": -0.02185639721898941,
    "low": -0.036995077920620345,
    "high": -0.002494667785566325
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
