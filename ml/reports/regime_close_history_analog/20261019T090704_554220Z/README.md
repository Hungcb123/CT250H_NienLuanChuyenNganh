# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| matched_half | 0.5114 | 0.3906 | 0.3170 | 0.4762 | 0.2945 |
| extended_half | 0.5143 | 0.3935 | 0.3226 | 0.4793 | 0.2977 |

Preset primary screens:
```json
[
  {
    "candidate": "matched_half",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "extended_half",
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
    "candidate": "matched_half",
    "block_sessions": 20,
    "delta": -0.00306088518730685,
    "low": -0.008855925750645557,
    "high": 0.0009357216316055509
  },
  {
    "candidate": "matched_half",
    "block_sessions": 60,
    "delta": -0.00306088518730685,
    "low": -0.009652216009931014,
    "high": 0.0007521046505549795
  },
  {
    "candidate": "extended_half",
    "block_sessions": 20,
    "delta": -0.000182793477117138,
    "low": -0.00574168121572209,
    "high": 0.005802354382970795
  },
  {
    "candidate": "extended_half",
    "block_sessions": 60,
    "delta": -0.000182793477117138,
    "low": -0.004975979529177119,
    "high": 0.004554614638221426
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
