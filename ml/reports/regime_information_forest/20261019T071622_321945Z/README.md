# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5134 | 0.3925 | 0.3229 | 0.4736 | 0.2959 |
| context_shrink | 0.4900 | 0.3820 | 0.2816 | 0.4538 | 0.2688 |
| context_forest_replace | 0.4869 | 0.3925 | 0.2801 | 0.4436 | 0.2678 |
| combined_context_diagnostic | 0.5001 | 0.3884 | 0.2988 | 0.4602 | 0.2822 |

Preset primary screens:
```json
[
  {
    "candidate": "context_shrink",
    "fold_wins": 0,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "context_forest_replace",
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
    "candidate": "context_shrink",
    "block_sessions": 20,
    "delta": -0.023405100161874803,
    "low": -0.03739879735080342,
    "high": -0.008543917243954502
  },
  {
    "candidate": "context_shrink",
    "block_sessions": 60,
    "delta": -0.023405100161874803,
    "low": -0.03382260727333003,
    "high": -0.008156022573920592
  },
  {
    "candidate": "context_forest_replace",
    "block_sessions": 20,
    "delta": -0.026529323069724997,
    "low": -0.0436110136524065,
    "high": -0.007716037799942148
  },
  {
    "candidate": "context_forest_replace",
    "block_sessions": 60,
    "delta": -0.026529323069724997,
    "low": -0.03672322812522428,
    "high": -0.008656576889351262
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
