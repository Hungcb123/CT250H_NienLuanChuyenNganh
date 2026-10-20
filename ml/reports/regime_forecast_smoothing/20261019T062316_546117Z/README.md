# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4932 | 0.4024 | 0.2965 | 0.4402 | 0.2675 |
| ema3 | 0.4948 | 0.4003 | 0.3038 | 0.4370 | 0.2659 |
| ema5 | 0.4909 | 0.3969 | 0.2947 | 0.4311 | 0.2612 |
| ema10 | 0.4726 | 0.3575 | 0.2473 | 0.4204 | 0.2477 |
| ema5_shrink | 0.4949 | 0.4006 | 0.3023 | 0.4367 | 0.2702 |

Preset primary screens:
```json
[
  {
    "candidate": "ema5",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "ema5_shrink",
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
    "candidate": "ema5",
    "block_sessions": 20,
    "delta": -0.0023123189032058233,
    "low": -0.026746451066412307,
    "high": 0.01862108115481617
  },
  {
    "candidate": "ema5",
    "block_sessions": 60,
    "delta": -0.0023123189032058233,
    "low": -0.027439608362235857,
    "high": 0.01862158988134533
  },
  {
    "candidate": "ema5_shrink",
    "block_sessions": 20,
    "delta": 0.0016963898220487272,
    "low": -0.013165449485800724,
    "high": 0.013385884704788378
  },
  {
    "candidate": "ema5_shrink",
    "block_sessions": 60,
    "delta": 0.0016963898220487272,
    "low": -0.012912373884392706,
    "high": 0.01371199653091227
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
