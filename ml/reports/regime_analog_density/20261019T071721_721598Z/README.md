# Historical development experiment

Previously inspected historical DEVELOPMENT only; no independent acceptance or deployment

Same frozen T+20 volatility-adjusted labels and evaluation dates. Macro F1 is the mean of four fold scores, not accuracy. Scores are not certified calibrated probabilities.

| Candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.5134 | 0.3925 | 0.3229 | 0.4736 | 0.2959 |
| analog_shrink | 0.5145 | 0.3937 | 0.3202 | 0.4799 | 0.2978 |
| analog_half | 0.5104 | 0.3809 | 0.3115 | 0.4791 | 0.2920 |

Preset primary screens:
```json
[
  {
    "candidate": "analog_shrink",
    "fold_wins": 2,
    "point_screen": false,
    "provisional_robust_evidence": false
  },
  {
    "candidate": "analog_half",
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
    "candidate": "analog_shrink",
    "block_sessions": 20,
    "delta": 0.0010903191898651299,
    "low": -0.008160750491081847,
    "high": 0.009605136250561249
  },
  {
    "candidate": "analog_shrink",
    "block_sessions": 60,
    "delta": 0.0010903191898651299,
    "low": -0.008292149413995887,
    "high": 0.008293287681647688
  },
  {
    "candidate": "analog_half",
    "block_sessions": 20,
    "delta": -0.0029559458074649436,
    "low": -0.022641469996751085,
    "high": 0.012780911317937464
  },
  {
    "candidate": "analog_half",
    "block_sessions": 60,
    "delta": -0.0029559458074649436,
    "low": -0.024422695522609728,
    "high": 0.010987294611326076
  }
]
```

See plan.json for source hashes, feature timing, preset models and primary definitions. Forecast CSV files contain date/label-end metadata and decision scores for later causal audits.
