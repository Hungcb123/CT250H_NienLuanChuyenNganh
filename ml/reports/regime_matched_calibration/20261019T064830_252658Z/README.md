# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4973 | 0.3974 | 0.3233 | 0.4244 | 0.2672 |
| matched_macro | 0.4913 | 0.3770 | 0.3138 | 0.4202 | 0.2601 |
| matched_robust | 0.5085 | 0.3770 | 0.3225 | 0.4564 | 0.2847 |
| matched_shrink | 0.4937 | 0.3851 | 0.3189 | 0.4208 | 0.2617 |

Preset primary screens:
```json
[
  {
    "candidate": "matched_macro",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "matched_shrink",
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
    "candidate": "matched_macro",
    "block_sessions": 20,
    "delta": -0.0059527302790785,
    "low": -0.016969740404825687,
    "high": 0.004530632637379533
  },
  {
    "candidate": "matched_macro",
    "block_sessions": 60,
    "delta": -0.0059527302790785,
    "low": -0.017084664667272008,
    "high": 0.004692507877851472
  },
  {
    "candidate": "matched_shrink",
    "block_sessions": 20,
    "delta": -0.0035637404749872537,
    "low": -0.009961053352975922,
    "high": 0.0029452174119176298
  },
  {
    "candidate": "matched_shrink",
    "block_sessions": 60,
    "delta": -0.0035637404749872537,
    "low": -0.00890914847226586,
    "high": 0.002430926562104996
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
