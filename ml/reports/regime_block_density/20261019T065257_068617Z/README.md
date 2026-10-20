# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4973 | 0.3974 | 0.3233 | 0.4244 | 0.2672 |
| bagged_adaptive | 0.4767 | 0.3963 | 0.3180 | 0.3796 | 0.2273 |
| bagged_shrink | 0.4914 | 0.4031 | 0.3263 | 0.4095 | 0.2511 |
| bagged_static | 0.4828 | 0.3897 | 0.3028 | 0.4080 | 0.2409 |
| bag7_diagnostic | 0.4769 | 0.3757 | 0.2727 | 0.4231 | 0.2364 |
| bag21_diagnostic | 0.4913 | 0.3642 | 0.2941 | 0.4345 | 0.2700 |
| bag42_diagnostic | 0.4700 | 0.4082 | 0.3033 | 0.3827 | 0.2229 |
| bag84_diagnostic | 0.4441 | 0.3425 | 0.2530 | 0.3793 | 0.1865 |
| bag126_diagnostic | 0.4468 | 0.3280 | 0.2337 | 0.3845 | 0.2085 |

Preset primary screens:
```json
[
  {
    "candidate": "bagged_adaptive",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "bagged_shrink",
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
    "candidate": "bagged_adaptive",
    "block_sessions": 20,
    "delta": -0.02061485490106163,
    "low": -0.046174249621360075,
    "high": 0.01220630554267057
  },
  {
    "candidate": "bagged_adaptive",
    "block_sessions": 60,
    "delta": -0.02061485490106163,
    "low": -0.04390801509492203,
    "high": 0.011347534642850285
  },
  {
    "candidate": "bagged_shrink",
    "block_sessions": 20,
    "delta": -0.005852581609276153,
    "low": -0.019299136598167156,
    "high": 0.007669774318943288
  },
  {
    "candidate": "bagged_shrink",
    "block_sessions": 60,
    "delta": -0.005852581609276153,
    "low": -0.019776915555409745,
    "high": 0.010143538933279742
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
