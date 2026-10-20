# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5134 | 0.3925 | 0.3229 | 0.4736 | 0.2959 |
| soft_margin_shrink | 0.5058 | 0.3773 | 0.3137 | 0.4678 | 0.2866 |
| soft_margin_replace | 0.4632 | 0.3575 | 0.2855 | 0.4225 | 0.2388 |

Preset primary screens:
```json
[
  {
    "candidate": "soft_margin_shrink",
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
    "candidate": "soft_margin_shrink",
    "block_sessions": 20,
    "delta": -0.00758242549405852,
    "low": -0.01831507069980283,
    "high": 0.004781206861867086
  },
  {
    "candidate": "soft_margin_shrink",
    "block_sessions": 60,
    "delta": -0.00758242549405852,
    "low": -0.016864860031050484,
    "high": 0.004101445958414732
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
