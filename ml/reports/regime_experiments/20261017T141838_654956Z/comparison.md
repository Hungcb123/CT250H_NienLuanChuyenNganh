# Controlled development comparison

Same dates and labels for all candidates. Nested tuning + periodic refits. Historical development only; no fresh test claim.

| Candidate | Mean F1 ± fold SD | Worst F1 | MCC | Folds > majority | Bear TP / FP / FN |
|---|---|---|---|---|---|
| t20_LightGBM_baseline_expanding | 0.355 ± 0.039 | 0.302 | 0.047 | 4 | 33 / 204 / 158 |
| t20_LightGBM_trend_expanding | 0.380 ± 0.088 | 0.319 | 0.083 | 4 | 42 / 144 / 149 |
| t20_LightGBM_risk_expanding | 0.371 ± 0.061 | 0.297 | 0.092 | 3 | 33 / 172 / 158 |
| t20_LightGBM_long_expanding | 0.381 ± 0.088 | 0.264 | 0.101 | 3 | 32 / 150 / 159 |
| t20_LightGBM_baseline_3y | 0.364 ± 0.048 | 0.310 | 0.070 | 4 | 56 / 229 / 135 |
| t20_LightGBM_trend_3y | 0.386 ± 0.012 | 0.373 | 0.111 | 4 | 58 / 220 / 133 |
| t20_LightGBM_risk_3y | 0.390 ± 0.050 | 0.334 | 0.138 | 4 | 47 / 319 / 144 |
| t20_LightGBM_long_3y | 0.363 ± 0.047 | 0.316 | 0.099 | 4 | 50 / 291 / 141 |
| t20_LightGBM_baseline_5y | 0.382 ± 0.033 | 0.336 | 0.087 | 4 | 48 / 241 / 143 |
| t20_LightGBM_trend_5y | 0.384 ± 0.086 | 0.294 | 0.085 | 3 | 40 / 154 / 151 |
| t20_LightGBM_risk_5y | 0.372 ± 0.056 | 0.325 | 0.090 | 4 | 40 / 202 / 151 |
| t20_LightGBM_long_5y | 0.370 ± 0.072 | 0.300 | 0.095 | 4 | 30 / 143 / 161 |

TP = correctly predicted bearish samples; FP = bearish false alarms; FN = missed bearish samples.
Fold SD is descriptive dispersion, not a confidence interval. Overlapping labels are not independent events.
Compare against the baseline candidate from this run, not an older non-nested score.
