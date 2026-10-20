# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| control_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| ohlcv_blend | 0.4824 | 0.3884 | 0.2958 | 0.4153 | 0.2483 |
| vix_blend | 0.4616 | 0.3607 | 0.2450 | 0.4022 | 0.2421 |
| indices_blend | 0.4765 | 0.3528 | 0.2713 | 0.4137 | 0.2546 |
| combined_blend | 0.4605 | 0.3333 | 0.2442 | 0.4014 | 0.2329 |
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| inner_selected_blend | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |

Preset primary screens:
```json
[
  {
    "candidate": "inner_selected_blend",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "combined_blend",
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
    "candidate": "inner_selected_blend",
    "block_sessions": 20,
    "delta": 0.003199362085201274,
    "low": -0.015123881888112041,
    "high": 0.022391385274478596
  },
  {
    "candidate": "inner_selected_blend",
    "block_sessions": 60,
    "delta": 0.003199362085201274,
    "low": -0.013465279037247611,
    "high": 0.023073702664862073
  },
  {
    "candidate": "combined_blend",
    "block_sessions": 20,
    "delta": -0.028850119451495515,
    "low": -0.05495021991871276,
    "high": 0.001264469084101916
  },
  {
    "candidate": "combined_blend",
    "block_sessions": 60,
    "delta": -0.028850119451495515,
    "low": -0.05157691159148359,
    "high": 0.0020572017022271964
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
