# Adaptive-target tuning follow-up — 19 October 2026

Result: no new candidate improves the frozen adaptive blend. Keep the previous development baseline; do not promote these candidates.

Same T+20 volatility labels, same 1,560 dates and four outer folds. No label or mixture-weight changes. Each group/outer fold has 24 trials and three purged inner folds: 192 trials, 576 inner fits. Trial zero reuses that fold’s previous classifier parameters. Original search space and balanced class weights are unchanged. No trial uses an outcome ending on or after its outer boundary.

Optimization: 50% mean inner macro F1 + 25% worst inner macro F1 + 25% the lower of the mean bear/bull F1. The macro candidate is the trial with the highest mean inner macro F1 from the same trial pool, not an independently optimized macro search. Each rule combines equal trend/risk classifier scores with unchanged expanding quantile experts at fixed 50/50 weight.

| Candidate | Mean fold macro F1 | Worst-fold macro F1 | Mean bear F1 | Mean bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| frozen_legacy_equal | 0.4488 | 0.3908 | 0.2461 | 0.4134 | 0.2150 |
| frozen_blend_expanding | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| robust_equal | 0.4414 | 0.3439 | 0.2212 | 0.4099 | 0.2110 |
| robust_blend | 0.4775 | 0.3619 | 0.2790 | 0.4097 | 0.2518 |
| macro_equal | 0.4408 | 0.3381 | 0.2190 | 0.4064 | 0.2126 |
| macro_blend | 0.4830 | 0.3714 | 0.2776 | 0.4221 | 0.2643 |

Every new candidate fails the predeclared improvement screen. Robust blend: -0.01176 mean macro F1 versus frozen blend; paired 60-session block interval [-0.02604, 0.00471]. Macro blend: -0.00635, interval [-0.02028, 0.00967]. No independent-test or statistical superiority claim is made.

The baseline’s main weakness is missed bearish labels in folds 3 and 4: 3/45 and 8/70 detected respectively. Bullish precision is also low in those folds (0.309 and 0.313). The detailed error_analysis.csv shows support, signals, hits, misses, false alarms, precision/recall and F1 by fold, year and fixed volatility buckets (<3%, 3–5%, >5% upper threshold). Rows with no true samples cannot support a class-recall conclusion. These are overlapping endpoint labels, not independent crashes or trades.

Inner scores improve for many searches, but this does not transfer to the inspected outer history. That supports rejecting these tuned variants; it does not prove that no better learner or input exists. Further search on the same outer dates would increase selection bias. The application model and the earlier frozen candidate remain unchanged.

Next research priority: investigate features or causal specialist heads using an inner-only protocol, and evaluate genuinely new matured outcomes. Do not change volatility thresholds or blend weights to chase this outer score.

Run from repository root:

```bash
python3 ml/experiment_regime_dynamic_tuning.py --audit-only
python3 ml/experiment_regime_dynamic_tuning.py --trials 24
python3 -m unittest discover -s ml -p 'test_regime_dynamic_tuning.py' -v
```

All searches and source/data hashes are recorded in plan.json; trials and per-fold parameters are archived. Historical development only, no confidence calibration or deployment.
