# Common T+20 loss-risk development comparison

Outcome: simple return < -5%. LightGBM / trend / 3y. All candidates newly tuned on common inner AP.
Risk scores are NOT calibrated event probabilities. No final holdout, export or profit claim.

| Policy | Actual alarm rate | TP | FP | FN | Precision | Recall | AP |
|---|---|---|---|---|---|---|---|
| fixed_5pct | 20.4% | 43 | 276 | 148 | 13.5% | 22.5% | 0.174 |
| vol_1sigma | 20.8% | 55 | 270 | 136 | 16.9% | 28.8% | 0.182 |
| binary_5pct | 20.9% | 41 | 285 | 150 | 12.6% | 21.5% | 0.142 |

Causal thresholds target 10% on historical calibration; realized outer alarm counts can differ.
retrospective_equal_count.csv forces identical floor(10% * fold size) alarm counts using WHOLE fold scores.
That is a ranking diagnostic with future distribution information, NEVER an executable threshold/backtest.
Read individual folds/year_metrics.csv. Overlapping samples are not independent crash events.
paired_block_sensitivity.csv: paired circular 20/60-session block bootstrap intervals for causal precision/recall differences.
Intervals are descriptive, conditional on historical selections; they do not remove repeated development reuse or structural change.
