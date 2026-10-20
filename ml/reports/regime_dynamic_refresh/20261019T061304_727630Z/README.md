# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| stable63 | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| classifier20_only | 0.4864 | 0.3837 | 0.3086 | 0.4112 | 0.2517 |
| classifier5_only | 0.4732 | 0.3821 | 0.2796 | 0.4014 | 0.2385 |
| density20_only | 0.4869 | 0.4000 | 0.3001 | 0.4259 | 0.2564 |
| both20 | 0.4781 | 0.3823 | 0.2846 | 0.4123 | 0.2474 |
| fast_class_ensemble | 0.4784 | 0.3934 | 0.2840 | 0.4136 | 0.2481 |
| mixed_density20 | 0.4811 | 0.3837 | 0.2954 | 0.4097 | 0.2476 |

Preset primary screens:
```json
[
  {
    "candidate": "both20",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "fast_class_ensemble",
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
    "candidate": "both20",
    "block_sessions": 20,
    "delta": -0.014438108782581394,
    "low": -0.04083452328647922,
    "high": 0.012421811126165697
  },
  {
    "candidate": "both20",
    "block_sessions": 60,
    "delta": -0.014438108782581394,
    "low": -0.0352841787257136,
    "high": 0.010765634754561352
  },
  {
    "candidate": "fast_class_ensemble",
    "block_sessions": 20,
    "delta": -0.014152991262616987,
    "low": -0.04302860304859938,
    "high": 0.014200232220801077
  },
  {
    "candidate": "fast_class_ensemble",
    "block_sessions": 60,
    "delta": -0.014152991262616987,
    "low": -0.037102777130096166,
    "high": 0.012461596715925524
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
