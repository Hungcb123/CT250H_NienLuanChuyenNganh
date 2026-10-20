# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4973 | 0.3974 | 0.3233 | 0.4244 | 0.2672 |
| gate_supplement | 0.4823 | 0.3800 | 0.2878 | 0.4188 | 0.2512 |
| gate_replace | 0.4727 | 0.3656 | 0.2585 | 0.4161 | 0.2461 |

Preset primary screens:
```json
[
  {
    "candidate": "gate_supplement",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "gate_replace",
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
    "candidate": "gate_supplement",
    "block_sessions": 20,
    "delta": -0.014944219836792616,
    "low": -0.028808340590843143,
    "high": 0.001668896090704941
  },
  {
    "candidate": "gate_supplement",
    "block_sessions": 60,
    "delta": -0.014944219836792616,
    "low": -0.026618234008975235,
    "high": 0.004475037513597174
  },
  {
    "candidate": "gate_replace",
    "block_sessions": 20,
    "delta": -0.024568597287944527,
    "low": -0.04684750361030758,
    "high": 4.726546049071071e-05
  },
  {
    "candidate": "gate_replace",
    "block_sessions": 60,
    "delta": -0.024568597287944527,
    "low": -0.04293532687074201,
    "high": 0.004329154002098807
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
