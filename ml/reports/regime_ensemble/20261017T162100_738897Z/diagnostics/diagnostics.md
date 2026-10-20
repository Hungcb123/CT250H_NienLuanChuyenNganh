# Risk diagnostics

Spearman IC correlates risk score with NEGATIVE forward simple return (higher = larger loss).
AP below base rate is a warning on these samples, not proof of feature inversion or a causal explanation.
Positive-day runs group consecutive index decision dates; they are not independent crash events.
fold3_positive_days.csv includes ALL positive days and flags actual static-threshold false negatives.
Legacy refit reports have no calibration mean/std; those values cannot be recovered from p90 alone.
Price plots describe outcomes; they do not establish exhaustion, macro news or SHAP explanations.
