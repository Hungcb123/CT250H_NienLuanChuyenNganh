# Target-definition development study

LightGBM + close-etf/trend + 3y. Same dates, features and refits; labels differ.
**Native F1 values below describe different tasks and must not be ranked against each other.**

| Policy | Own-label mean F1 | Own-label majority F1 | Own-label MCC | Own-label worst F1 |
|---|---|---|---|---|
| fixed_5pct | 0.386 | 0.256 | 0.111 | 0.373 |
| vol_1sigma | 0.423 | 0.253 | 0.174 | 0.360 |

## Common yardstick: actual simple return below -5% after 20 market sessions

| Policy | True bearish samples | Correct alarms (TP) | False alarms (FP) | Missed (FN) | Precision | Recall |
|---|---|---|---|---|---|---|
| fixed_5pct | 191 | 58 | 220 | 133 | 20.9% | 30.4% |
| vol_1sigma | 191 | 36 | 120 | 155 | 23.1% | 18.8% |

The shared yardstick is not the volatility-label ground truth. It asks whether a relative bearish signal detects the original absolute loss goal.
Overlapping labelled days are not independent crashes or trades. No fees/execution/backtest were modeled.
No final holdout was scored and no winner is automatically selected.
