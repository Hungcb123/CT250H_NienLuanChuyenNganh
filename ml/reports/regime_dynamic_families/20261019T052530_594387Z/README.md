# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| legacy_equal | 0.4488 | 0.3908 | 0.2461 | 0.4134 | 0.2150 |
| CatBoost | 0.3885 | 0.3064 | 0.1860 | 0.3345 | 0.1397 |
| HistGBM | 0.4000 | 0.3284 | 0.1737 | 0.3584 | 0.1580 |
| RandomForest | 0.3557 | 0.2400 | 0.1459 | 0.3024 | 0.0863 |
| ExtraTrees | 0.3895 | 0.2803 | 0.1987 | 0.3580 | 0.1408 |
| SVC_RBF | 0.3620 | 0.2455 | 0.1392 | 0.2671 | 0.0718 |
| MLP | 0.3376 | 0.2674 | 0.1135 | 0.3110 | 0.0675 |
| ShrinkageLDA | 0.3579 | 0.2537 | 0.2310 | 0.3074 | 0.1394 |
| KNN | 0.3374 | 0.2951 | 0.2193 | 0.3832 | 0.1097 |
| legacy_equal_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| CatBoost_blend | 0.4514 | 0.3518 | 0.2565 | 0.3893 | 0.2159 |
| HistGBM_blend | 0.4478 | 0.3624 | 0.2322 | 0.3974 | 0.2137 |
| RandomForest_blend | 0.4371 | 0.3249 | 0.2283 | 0.3744 | 0.2002 |
| ExtraTrees_blend | 0.4771 | 0.3809 | 0.2930 | 0.4223 | 0.2464 |
| SVC_RBF_blend | 0.3844 | 0.2682 | 0.1559 | 0.2879 | 0.1091 |
| MLP_blend | 0.3507 | 0.2671 | 0.0991 | 0.3267 | 0.0871 |
| ShrinkageLDA_blend | 0.4197 | 0.2401 | 0.2426 | 0.3382 | 0.1912 |
| KNN_blend | 0.4765 | 0.3618 | 0.2748 | 0.4483 | 0.2625 |
| inner_supplement_blend | 0.4873 | 0.4000 | 0.2926 | 0.4216 | 0.2628 |
| inner_replacement_blend | 0.4840 | 0.4000 | 0.3103 | 0.4032 | 0.2485 |
| family_pool_blend | 0.4702 | 0.3606 | 0.2699 | 0.4187 | 0.2384 |
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |

Preset primary screens:
```json
[
  {
    "candidate": "inner_supplement_blend",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "inner_replacement_blend",
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
    "candidate": "inner_supplement_blend",
    "block_sessions": 20,
    "delta": -0.0019950941277060985,
    "low": -0.019681300687821868,
    "high": 0.014431650835093396
  },
  {
    "candidate": "inner_supplement_blend",
    "block_sessions": 60,
    "delta": -0.0019950941277060985,
    "low": -0.01732568297336304,
    "high": 0.01573450278398127
  },
  {
    "candidate": "inner_replacement_blend",
    "block_sessions": 20,
    "delta": -0.005270981474364389,
    "low": -0.04112921083460153,
    "high": 0.028068402516165467
  },
  {
    "candidate": "inner_replacement_blend",
    "block_sessions": 60,
    "delta": -0.005270981474364389,
    "low": -0.031039785305205344,
    "high": 0.02451819754581621
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
