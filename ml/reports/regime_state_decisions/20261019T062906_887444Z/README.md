# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4949 | 0.4006 | 0.3023 | 0.4367 | 0.2702 |
| hysteresis05 | 0.4833 | 0.3990 | 0.2972 | 0.4116 | 0.2494 |
| confirm2 | 0.4942 | 0.3883 | 0.3045 | 0.4343 | 0.2624 |
| hysteresis025 | 0.4878 | 0.4049 | 0.2946 | 0.4264 | 0.2594 |
| hysteresis10 | 0.4675 | 0.3436 | 0.2386 | 0.4218 | 0.2388 |

Preset primary screens:
```json
[
  {
    "candidate": "hysteresis05",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "confirm2",
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
    "candidate": "hysteresis05",
    "block_sessions": 20,
    "delta": -0.011623848979737617,
    "low": -0.025906098988476036,
    "high": 0.0020088435216677513
  },
  {
    "candidate": "hysteresis05",
    "block_sessions": 60,
    "delta": -0.011623848979737617,
    "low": -0.028730707575628466,
    "high": -9.84092672236666e-06
  },
  {
    "candidate": "confirm2",
    "block_sessions": 20,
    "delta": -0.0007750009292593618,
    "low": -0.016285058549917995,
    "high": 0.014758393639195557
  },
  {
    "candidate": "confirm2",
    "block_sessions": 60,
    "delta": -0.0007750009292593618,
    "low": -0.01717202980898463,
    "high": 0.014664161504620386
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
