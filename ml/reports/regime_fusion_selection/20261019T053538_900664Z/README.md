# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| fusion_macro | 0.4335 | 0.2401 | 0.2487 | 0.3504 | 0.1953 |
| fusion_robust | 0.3974 | 0.2401 | 0.1577 | 0.3776 | 0.1589 |

Preset primary screens:
```json
[
  {
    "candidate": "fusion_macro",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "fusion_robust",
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
    "candidate": "fusion_macro",
    "block_sessions": 20,
    "delta": -0.05580759061738061,
    "low": -0.08759647426195645,
    "high": -0.025147105380395527
  },
  {
    "candidate": "fusion_macro",
    "block_sessions": 60,
    "delta": -0.05580759061738061,
    "low": -0.08471320846357104,
    "high": -0.021145253417465953
  },
  {
    "candidate": "fusion_robust",
    "block_sessions": 20,
    "delta": -0.09189735960419826,
    "low": -0.1317331020708409,
    "high": -0.04312814031180695
  },
  {
    "candidate": "fusion_robust",
    "block_sessions": 60,
    "delta": -0.09189735960419826,
    "low": -0.12751077812991757,
    "high": -0.032401768507065734
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
