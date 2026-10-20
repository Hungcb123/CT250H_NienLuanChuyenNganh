# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| mahal_half | 0.5082 | 0.3923 | 0.3064 | 0.4766 | 0.2917 |
| mahal_replace | 0.5049 | 0.3844 | 0.3100 | 0.4681 | 0.2843 |
| separated_half | 0.5047 | 0.3923 | 0.3020 | 0.4716 | 0.2877 |
| separated_replace | 0.4975 | 0.3889 | 0.2911 | 0.4611 | 0.2799 |
| joint_half | 0.5070 | 0.3889 | 0.3078 | 0.4721 | 0.2889 |
| joint_replace | 0.4992 | 0.3889 | 0.2961 | 0.4617 | 0.2812 |

Preset primary screens:
```json
[
  {
    "candidate": "mahal_half",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "separated_half",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "joint_half",
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
    "candidate": "mahal_half",
    "block_sessions": 20,
    "delta": -0.006281493312816577,
    "low": -0.014164368523511793,
    "high": 0.000807097144523255
  },
  {
    "candidate": "mahal_half",
    "block_sessions": 60,
    "delta": -0.006281493312816577,
    "low": -0.01156717064137479,
    "high": 0.0009238640209729639
  },
  {
    "candidate": "separated_half",
    "block_sessions": 20,
    "delta": -0.009834462914428799,
    "low": -0.018879794275322003,
    "high": 0.0012927075105304182
  },
  {
    "candidate": "separated_half",
    "block_sessions": 60,
    "delta": -0.009834462914428799,
    "low": -0.016475135212822515,
    "high": 0.00026866147671220894
  },
  {
    "candidate": "joint_half",
    "block_sessions": 20,
    "delta": -0.007525318308403972,
    "low": -0.01657500234069347,
    "high": 0.00277164845534302
  },
  {
    "candidate": "joint_half",
    "block_sessions": 60,
    "delta": -0.007525318308403972,
    "low": -0.014581426838506344,
    "high": 0.0018440927104256648
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
