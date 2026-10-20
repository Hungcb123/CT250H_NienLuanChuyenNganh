# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4949 | 0.4006 | 0.3023 | 0.4367 | 0.2702 |
| gru1 | 0.3597 | 0.3127 | 0.1633 | 0.3206 | 0.1141 |
| gru1_supplement | 0.4800 | 0.3897 | 0.2794 | 0.4260 | 0.2542 |
| gru1_replace | 0.4374 | 0.3119 | 0.2222 | 0.3835 | 0.2117 |
| gru10 | 0.3589 | 0.2881 | 0.1765 | 0.2851 | 0.1059 |
| gru10_supplement | 0.4546 | 0.3665 | 0.2504 | 0.3885 | 0.2269 |
| gru10_replace | 0.4349 | 0.3156 | 0.2414 | 0.3705 | 0.2038 |

Preset primary screens:
```json
[
  {
    "candidate": "gru10_supplement",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "gru10_replace",
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
    "candidate": "gru10_supplement",
    "block_sessions": 20,
    "delta": -0.040310949463389145,
    "low": -0.07094254885129465,
    "high": -0.006267154697268769
  },
  {
    "candidate": "gru10_supplement",
    "block_sessions": 60,
    "delta": -0.040310949463389145,
    "low": -0.06949202309641725,
    "high": -0.004936163254195876
  },
  {
    "candidate": "gru10_replace",
    "block_sessions": 20,
    "delta": -0.060023145814069145,
    "low": -0.11679913563553519,
    "high": 0.006395264570859668
  },
  {
    "candidate": "gru10_replace",
    "block_sessions": 60,
    "delta": -0.060023145814069145,
    "low": -0.11172665249080153,
    "high": 0.003501410919405115
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
