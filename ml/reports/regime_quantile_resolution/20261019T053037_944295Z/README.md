# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| linear9 | 0.4811 | 0.3019 | 0.3547 | 0.3670 | 0.2217 |
| linear9_blend | 0.4859 | 0.3969 | 0.2940 | 0.4257 | 0.2562 |
| linear9_supplement | 0.4870 | 0.3955 | 0.2941 | 0.4265 | 0.2591 |
| kernel9 | 0.4860 | 0.2942 | 0.3651 | 0.3684 | 0.2304 |
| kernel9_blend | 0.4856 | 0.3957 | 0.2933 | 0.4276 | 0.2555 |
| kernel9_supplement | 0.4879 | 0.3957 | 0.2945 | 0.4295 | 0.2598 |
| linear19 | 0.4777 | 0.2878 | 0.3379 | 0.3733 | 0.2218 |
| linear19_blend | 0.4867 | 0.4010 | 0.2980 | 0.4249 | 0.2551 |
| linear19_supplement | 0.4871 | 0.3971 | 0.2950 | 0.4279 | 0.2568 |

Preset primary screens:
```json
[
  {
    "candidate": "linear19_blend",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "linear19_supplement",
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
    "candidate": "linear19_blend",
    "block_sessions": 20,
    "delta": -0.0026567679081339612,
    "low": -0.010124043308326487,
    "high": 0.00565577908067804
  },
  {
    "candidate": "linear19_blend",
    "block_sessions": 60,
    "delta": -0.0026567679081339612,
    "low": -0.010142591056394075,
    "high": 0.006469563484883489
  },
  {
    "candidate": "linear19_supplement",
    "block_sessions": 20,
    "delta": -0.002234456907862059,
    "low": -0.006573331785817879,
    "high": 0.002496448878282441
  },
  {
    "candidate": "linear19_supplement",
    "block_sessions": 60,
    "delta": -0.002234456907862059,
    "low": -0.0059096497711165295,
    "high": 0.0025929537001562887
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
