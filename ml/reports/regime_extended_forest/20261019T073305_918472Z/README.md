# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| extended_shrink | 0.5090 | 0.3921 | 0.2976 | 0.4848 | 0.2983 |
| extended_replace | 0.5113 | 0.4019 | 0.3126 | 0.4788 | 0.2978 |

Preset primary screens:
```json
[
  {
    "candidate": "extended_shrink",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "extended_replace",
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
    "candidate": "extended_shrink",
    "block_sessions": 20,
    "delta": -0.005486228895399181,
    "low": -0.023338225381846864,
    "high": 0.008715861796790953
  },
  {
    "candidate": "extended_shrink",
    "block_sessions": 60,
    "delta": -0.005486228895399181,
    "low": -0.016982217174484414,
    "high": 0.008079723471741598
  },
  {
    "candidate": "extended_replace",
    "block_sessions": 20,
    "delta": -0.003180274825641538,
    "low": -0.02379931072327719,
    "high": 0.013983484806317741
  },
  {
    "candidate": "extended_replace",
    "block_sessions": 60,
    "delta": -0.003180274825641538,
    "low": -0.018159648392025617,
    "high": 0.013597802553264095
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
