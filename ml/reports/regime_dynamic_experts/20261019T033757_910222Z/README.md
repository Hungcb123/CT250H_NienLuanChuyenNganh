# Adaptive label experiment — 19 October 2026

Historical development only. The two target definitions are different tasks; their F1 scores do not measure the same prediction objective.

Dynamic target: compare T+20 log return with plus/minus the standard deviation of the last 20 completed daily log returns times sqrt(20), ddof=1, k=1. Equality belongs to the neutral class. Thresholds use only completed prices at decision time. This measures a move relative to recent volatility; it does not claim that every small positive move is bullish or identify a sideways market independently.

Same 1,560 evaluation dates and four folds. Classifiers retrained for each target with identical frozen per-fold parameters. No new parameter tuning. Cached return quantiles reused only because regression targets, features, source hashes and refit cohorts are unchanged; all class mappings and training priors recomputed for each target. Scores remain decision scores, not calibrated probabilities.

| Target | Candidate | Mean macro F1 | Worst-fold macro F1 | Mean MCC |
|---|---|---:|---:|---:|
| fixed_5pct | legacy_trend | 0.3860 | 0.3728 | 0.1108 |
| fixed_5pct | legacy_risk | 0.3898 | 0.3341 | 0.1383 |
| fixed_5pct | legacy_equal | 0.3957 | 0.3600 | 0.1437 |
| fixed_5pct | blend_expanding | 0.4376 | 0.3410 | 0.1794 |
| fixed_5pct | delayed_selector | 0.4205 | 0.3838 | 0.1412 |
| vol_1sigma | legacy_trend | 0.4391 | 0.3945 | 0.1917 |
| vol_1sigma | legacy_risk | 0.4302 | 0.3423 | 0.1998 |
| vol_1sigma | legacy_equal | 0.4488 | 0.3908 | 0.2150 |
| vol_1sigma | blend_expanding | 0.4893 | 0.4000 | 0.2622 |
| vol_1sigma | delayed_selector | 0.4789 | 0.3721 | 0.2309 |

Adaptive 50/50 expanding blend: mean F1 0.4893, worst 0.4000, versus adaptive equal-classifier baseline 0.4488 / 0.3908. This is a development research lead, not a deployment acceptance. Per-class mean F1 remains uneven: bear 0.2946, neutral 0.7424, bull 0.4310. The result is not 48.93% classification accuracy.

Paired circular-block bootstrap (1,000 repeats) of blend-minus-equal mean-fold F1: 20-session interval [0.00025, 0.07276]; 60-session interval [-0.00031, 0.07031]. Dependence sensitivity and repeated development reuse prevent a robust independent improvement claim. The selector has lower mean and worst-fold scores than this blend on the adaptive target; its intervals against equal classifiers include zero.

Upper threshold median 4.61%, 10th percentile 2.57%, below 5% on 55.45% of dates. Compared to fixed labels, 124 neutral dates become bullish and 113 bullish dates become neutral. Label class counts: fixed 191 bear / 982 neutral / 387 bull; adaptive 208 / 954 / 398. The change does not just inflate bullish counts.

Parity: original trend and risk classifier scores reproduce at 1e-12 tolerance on all 1,560 dates; original selector decisions reproduce 1,560/1,560. Ten replay-prefix checks corrupt unavailable labels without changing decisions. Four new regression tests cover causal thresholds, dynamic mapping, equality semantics and future-label exclusion. Frozen candidate contract and application model were not replaced.

Run from repository root:

```bash
python3 ml/experiment_regime_dynamic_experts.py --audit-only
python3 ml/experiment_regime_dynamic_experts.py
python3 -m unittest discover -s ml -p 'test_regime_dynamic_experts.py' -v
```

Full runs write a new timestamped directory; no existing run is overwritten. Dataset and code hashes plus preset rules are saved in plan.json before training.
