# Common T+20 loss-risk development comparison

Outcome: simple return < -5%. LightGBM / trend / 3y. Parameter mode: fixed_shallow.
Risk scores are NOT calibrated event probabilities. No final holdout, export or profit claim.

| Policy | Actual alarm rate | TP | FP | FN | Precision | Recall | AP |
|---|---|---|---|---|---|---|---|
| fixed_5pct | 16.8% | 35 | 227 | 156 | 13.4% | 18.3% | 0.172 |
| vol_1sigma | 17.9% | 36 | 243 | 155 | 12.9% | 18.8% | 0.194 |
| binary_5pct | 19.4% | 33 | 269 | 158 | 10.9% | 17.3% | 0.164 |

Causal thresholds target 10% on historical calibration; realized outer alarm counts can differ.
retrospective_equal_count.csv forces identical floor(10% * fold size) alarm counts using WHOLE fold scores.
That is a ranking diagnostic with future distribution information, NEVER an executable threshold/backtest.
Read individual folds/year_metrics.csv. Overlapping samples are not independent crash events.
paired_block_sensitivity.csv: paired circular 20/60-session block bootstrap intervals for causal precision/recall differences.
Intervals are descriptive, conditional on historical selections; they do not remove repeated development reuse or structural change.
