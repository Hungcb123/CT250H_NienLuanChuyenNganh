# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| calendar_full | 0.4444 | 0.3491 | 0.2571 | 0.3804 | 0.2016 |
| calendar_regularized | 0.4855 | 0.3780 | 0.3055 | 0.4242 | 0.2536 |
| calendar_classifier_only | 0.4903 | 0.3550 | 0.3153 | 0.4291 | 0.2532 |
| calendar_density_only | 0.4705 | 0.3901 | 0.2797 | 0.4111 | 0.2362 |

Preset primary screens:
```json
[
  {
    "candidate": "calendar_full",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "calendar_regularized",
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
    "candidate": "calendar_full",
    "block_sessions": 20,
    "delta": -0.04807353152980387,
    "low": -0.0818838774410319,
    "high": -0.011795121626774612
  },
  {
    "candidate": "calendar_full",
    "block_sessions": 60,
    "delta": -0.04807353152980387,
    "low": -0.08495236159512842,
    "high": -0.015243128142138466
  },
  {
    "candidate": "calendar_regularized",
    "block_sessions": 20,
    "delta": -0.007000453560926545,
    "low": -0.03767839423906944,
    "high": 0.01985156970096366
  },
  {
    "candidate": "calendar_regularized",
    "block_sessions": 60,
    "delta": -0.007000453560926545,
    "low": -0.04024727155163627,
    "high": 0.019257222222706597
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
