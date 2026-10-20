# Controlled development comparison

Same dates and labels for all candidates. Nested tuning + periodic refits. Historical development only; no fresh test claim.

| Candidate | Mean F1 ± fold SD | Worst F1 | MCC | Folds > majority | Bear TP / FP / FN |
|---|---|---|---|---|---|
| t20_LightGBM_baseline_expanding | 0.365 ± 0.035 | 0.320 | 0.063 | 4 | 38 / 208 / 153 |
| t20_LightGBM_long_expanding | 0.373 ± 0.088 | 0.278 | 0.086 | 3 | 32 / 153 / 159 |

TP = correctly predicted bearish samples; FP = bearish false alarms; FN = missed bearish samples.
Fold SD is descriptive dispersion, not a confidence interval. Overlapping labels are not independent events.
Compare against the baseline candidate from this run, not an older non-nested score.
