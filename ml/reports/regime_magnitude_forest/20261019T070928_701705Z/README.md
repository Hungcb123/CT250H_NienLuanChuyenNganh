# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5121 | 0.3911 | 0.3165 | 0.4784 | 0.2959 |
| magnitude_shrink | 0.5134 | 0.3925 | 0.3229 | 0.4736 | 0.2959 |
| magnitude_replace | 0.5078 | 0.3870 | 0.3202 | 0.4614 | 0.2860 |

Preset primary screens:
```json
[
  {
    "candidate": "magnitude_shrink",
    "fold_wins": 3,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "magnitude_replace",
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
    "candidate": "magnitude_shrink",
    "block_sessions": 20,
    "delta": 0.0012488012946695326,
    "low": -0.005918604793407258,
    "high": 0.007823807699267741
  },
  {
    "candidate": "magnitude_shrink",
    "block_sessions": 60,
    "delta": 0.0012488012946695326,
    "low": -0.004465583416355759,
    "high": 0.005750691745046921
  },
  {
    "candidate": "magnitude_replace",
    "block_sessions": 20,
    "delta": -0.004336813248170701,
    "low": -0.014232934289337007,
    "high": 0.004131890899682619
  },
  {
    "candidate": "magnitude_replace",
    "block_sessions": 60,
    "delta": -0.004336813248170701,
    "low": -0.016551424841014517,
    "high": 0.002539070232857915
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
