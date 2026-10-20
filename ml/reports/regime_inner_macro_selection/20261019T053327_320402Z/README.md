# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| macro_information_blend | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| macro_families_supplement | 0.4829 | 0.4000 | 0.2860 | 0.4173 | 0.2555 |
| macro_families_replacement | 0.4710 | 0.4000 | 0.2700 | 0.3989 | 0.2422 |
| macro_losses_supplement | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| macro_losses_replacement | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |

Preset primary screens:
```json
[
  {
    "candidate": "macro_information_blend",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "macro_families_supplement",
    "fold_wins": 1,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "macro_families_replacement",
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
    "candidate": "macro_information_blend",
    "block_sessions": 20,
    "delta": 0.003199362085201274,
    "low": -0.015123881888112041,
    "high": 0.022391385274478596
  },
  {
    "candidate": "macro_information_blend",
    "block_sessions": 60,
    "delta": 0.003199362085201274,
    "low": -0.013465279037247611,
    "high": 0.023073702664862073
  },
  {
    "candidate": "macro_families_supplement",
    "block_sessions": 20,
    "delta": -0.006395127277830703,
    "low": -0.02207015469575926,
    "high": 0.007454938192138183
  },
  {
    "candidate": "macro_families_supplement",
    "block_sessions": 60,
    "delta": -0.006395127277830703,
    "low": -0.01949470597154367,
    "high": 0.007963863545540408
  },
  {
    "candidate": "macro_families_replacement",
    "block_sessions": 20,
    "delta": -0.018345736542583535,
    "low": -0.044209600608045574,
    "high": 0.005474389881254648
  },
  {
    "candidate": "macro_families_replacement",
    "block_sessions": 60,
    "delta": -0.018345736542583535,
    "low": -0.04036047917080412,
    "high": 0.006172265964999092
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
