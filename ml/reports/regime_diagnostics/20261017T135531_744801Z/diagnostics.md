# Regime fold diagnostics

Source: /mnt/d/Project_CT250H_NienLuanChuyenNganh/ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json

Derived from existing validation matrices; no model fitted. These are selection scores, not new test scores.

| H | Features / model | Fold | F1 | Baseline | MCC | Bear TP / FP / FN |
|---|---|---|---|---|---|---|
| 20 | close / LightGBM | 1 | 0.282 | 0.234 | 0.003 | 10 / 141 / 15 |
| 20 | close / LightGBM | 2 | 0.436 | 0.254 | 0.176 | 22 / 56 / 48 |
| 20 | close / LightGBM | 3 | 0.309 | 0.299 | 0.005 | 9 / 70 / 27 |
| 20 | close / LightGBM | 4 | 0.417 | 0.235 | 0.135 | 16 / 52 / 44 |
| 20 | close / XGBoost | 1 | 0.310 | 0.234 | 0.022 | 6 / 61 / 19 |
| 20 | close / XGBoost | 2 | 0.406 | 0.254 | 0.114 | 13 / 13 / 57 |
| 20 | close / XGBoost | 3 | 0.317 | 0.299 | -0.036 | 4 / 24 / 32 |
| 20 | close / XGBoost | 4 | 0.326 | 0.235 | 0.008 | 7 / 24 / 53 |
| 20 | close-etf / LightGBM | 1 | 0.301 | 0.234 | 0.026 | 14 / 136 / 11 |
| 20 | close-etf / LightGBM | 2 | 0.456 | 0.254 | 0.194 | 16 / 46 / 54 |
| 20 | close-etf / LightGBM | 3 | 0.349 | 0.299 | 0.055 | 7 / 63 / 29 |
| 20 | close-etf / LightGBM | 4 | 0.435 | 0.235 | 0.211 | 10 / 64 / 50 |
| 20 | close-etf / XGBoost | 1 | 0.371 | 0.234 | 0.036 | 8 / 19 / 17 |
| 20 | close-etf / XGBoost | 2 | 0.425 | 0.254 | 0.216 | 8 / 9 / 62 |
| 20 | close-etf / XGBoost | 3 | 0.300 | 0.299 | -0.049 | 0 / 14 / 36 |
| 20 | close-etf / XGBoost | 4 | 0.332 | 0.235 | 0.088 | 4 / 16 / 56 |
| 60 | close / LightGBM | 1 | 0.263 | 0.219 | -0.038 | 0 / 76 / 0 |
| 60 | close / LightGBM | 2 | 0.284 | 0.249 | -0.016 | 8 / 5 / 100 |
| 60 | close / LightGBM | 3 | 0.342 | 0.303 | 0.089 | 8 / 66 / 9 |
| 60 | close / LightGBM | 4 | 0.377 | 0.275 | 0.156 | 0 / 36 / 2 |
| 60 | close / XGBoost | 1 | 0.228 | 0.219 | -0.106 | 0 / 30 / 0 |
| 60 | close / XGBoost | 2 | 0.240 | 0.249 | -0.050 | 0 / 0 / 108 |
| 60 | close / XGBoost | 3 | 0.393 | 0.303 | 0.115 | 4 / 19 / 13 |
| 60 | close / XGBoost | 4 | 0.382 | 0.275 | 0.179 | 0 / 7 / 2 |
| 60 | close-etf / LightGBM | 1 | 0.292 | 0.219 | 0.050 | 0 / 46 / 0 |
| 60 | close-etf / LightGBM | 2 | 0.324 | 0.249 | 0.030 | 12 / 20 / 96 |
| 60 | close-etf / LightGBM | 3 | 0.261 | 0.303 | -0.082 | 2 / 49 / 15 |
| 60 | close-etf / LightGBM | 4 | 0.429 | 0.275 | 0.299 | 0 / 18 / 2 |
| 60 | close-etf / XGBoost | 1 | 0.305 | 0.219 | 0.154 | 0 / 32 / 0 |
| 60 | close-etf / XGBoost | 2 | 0.295 | 0.249 | 0.032 | 6 / 10 / 102 |
| 60 | close-etf / XGBoost | 3 | 0.282 | 0.303 | -0.066 | 1 / 25 / 16 |
| 60 | close-etf / XGBoost | 4 | 0.414 | 0.275 | 0.281 | 0 / 7 / 2 |
| 120 | close / LightGBM | 1 | 0.288 | 0.190 | 0.152 | 0 / 10 / 0 |
| 120 | close / LightGBM | 2 | 0.247 | 0.258 | 0.051 | 0 / 2 / 107 |
| 120 | close / LightGBM | 3 | 0.252 | 0.322 | -0.117 | 0 / 35 / 0 |
| 120 | close / LightGBM | 4 | 0.422 | 0.249 | 0.291 | 0 / 10 / 0 |
| 120 | close / XGBoost | 1 | 0.279 | 0.190 | 0.226 | 0 / 0 / 0 |
| 120 | close / XGBoost | 2 | 0.226 | 0.258 | -0.022 | 0 / 0 / 107 |
| 120 | close / XGBoost | 3 | 0.282 | 0.322 | -0.128 | 0 / 3 / 0 |
| 120 | close / XGBoost | 4 | 0.409 | 0.249 | 0.375 | 0 / 3 / 0 |
| 120 | close-etf / LightGBM | 1 | 0.239 | 0.190 | 0.071 | 0 / 50 / 0 |
| 120 | close-etf / LightGBM | 2 | 0.217 | 0.258 | -0.009 | 0 / 0 / 107 |
| 120 | close-etf / LightGBM | 3 | 0.229 | 0.322 | -0.198 | 0 / 20 / 0 |
| 120 | close-etf / LightGBM | 4 | 0.384 | 0.249 | 0.209 | 0 / 31 / 0 |
| 120 | close-etf / XGBoost | 1 | 0.247 | 0.190 | 0.184 | 0 / 0 / 0 |
| 120 | close-etf / XGBoost | 2 | 0.234 | 0.258 | -0.041 | 0 / 0 / 107 |
| 120 | close-etf / XGBoost | 3 | 0.303 | 0.322 | -0.090 | 0 / 0 / 0 |
| 120 | close-etf / XGBoost | 4 | 0.321 | 0.249 | 0.258 | 0 / 0 / 0 |
