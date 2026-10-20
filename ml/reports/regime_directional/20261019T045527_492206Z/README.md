# regime_directional — 19 October 2026

Inspected historical DEVELOPMENT only. Keep the frozen adaptive blend; no primary candidate passes the predeclared improvement screen. Same 1,560 dates and T+20 +/-1 trailing-volatility-unit labels. No target or mixture-weight search.

| Candidate | Mean fold macro F1 | Worst fold F1 | Mean bear F1 | Mean bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| multiclass_core | 0.4082 | 0.3206 | 0.1930 | 0.3934 | 0.1746 |
| ovr_core | 0.4056 | 0.2978 | 0.2228 | 0.3566 | 0.1598 |
| hierarchical_core | 0.3902 | 0.2780 | 0.1896 | 0.2872 | 0.1474 |
| multiclass_directional | 0.4143 | 0.3074 | 0.2160 | 0.3546 | 0.1733 |
| ovr_directional | 0.4072 | 0.3035 | 0.2237 | 0.3318 | 0.1561 |
| hierarchical_directional | 0.3814 | 0.2833 | 0.1621 | 0.2833 | 0.1371 |
| inner_selected | 0.3942 | 0.2978 | 0.1827 | 0.3368 | 0.1504 |
| equal_pool | 0.4127 | 0.2992 | 0.2194 | 0.3364 | 0.1734 |
| multiclass_core_blend | 0.4632 | 0.3716 | 0.2599 | 0.4206 | 0.2462 |
| ovr_core_blend | 0.4621 | 0.3773 | 0.2652 | 0.4055 | 0.2380 |
| hierarchical_core_blend | 0.4271 | 0.3249 | 0.2335 | 0.3211 | 0.1944 |
| multiclass_directional_blend | 0.4541 | 0.3665 | 0.2534 | 0.3912 | 0.2219 |
| ovr_directional_blend | 0.4457 | 0.3552 | 0.2671 | 0.3573 | 0.2028 |
| hierarchical_directional_blend | 0.4170 | 0.3115 | 0.2147 | 0.3111 | 0.1796 |
| inner_selected_blend | 0.4510 | 0.3716 | 0.2415 | 0.3879 | 0.2273 |
| equal_pool_blend | 0.4440 | 0.3543 | 0.2496 | 0.3636 | 0.2088 |
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |

## Preset design

- primary: inner_selected_blend: choose among six by purged-inner directional robustness objective, then fixed half old blend + half specialist scores
- secondary: equal_pool_blend: equal all SIX specialists then fixed half old blend. Individual variants are diagnostic only, no outer winner promotion.
- selection: 0.5*mean inner macroF1 + .25*worst inner macroF1 + .25*min(mean inner bearF1, mean inner bullF1); deterministic config order for ties
- parameters: {'n_estimators': 150, 'learning_rate': 0.03, 'max_depth': 3, 'num_leaves': 7, 'min_child_samples': 50, 'colsample_bytree': 0.7, 'reg_alpha': 0.1, 'reg_lambda': 1.0, 'random_state': 42, 'n_jobs': 2, 'verbosity': -1, 'class_weight': 'balanced'}
- score_semantics: Balanced-head and hierarchical scores are decision scores, NOT calibrated probabilities.
- assumptions: No new target threshold, weight grid, missing-date removal, OHLC/volume data, independent holdout or deployment. Repeatedly inspected historical development.

Feature additions: volatility-normalized momentum at 3/5/10/20/60 sessions, current and lagged shocks against previous known volatility, negative-return shares, downside energy share, short/long volatility ratio, normalized drawdowns, skew and momentum acceleration. All are trailing close-based features; feature set was fixed before fitting. Frozen training/evaluation rows are retained.

The standalone variants are diagnostic. No outer-best variant is automatically promoted. Error analysis by fold/year/fixed volatility buckets is in error_analysis.csv; selection/refit logs and code/data hashes are archived. Decision scores are not calibrated event probabilities. Application models are unchanged.

The specialist study compares matched shallow LightGBM classifiers, one-vs-rest heads and a movement/direction hierarchy with/without added inputs. Its primary model chooses architecture/features using three purged inner folds at each outer boundary. The density follow-up keeps the old quantile learner parameters and adds inputs to expanding raw/normalized return regressors; its primary averages old/new densities before the fixed classifier mix.

Paired circular-block intervals, 1,000 resamples within folds; all historical inference remains sensitive to repeated development inspection:

```json
[
  {
    "candidate": "inner_selected_blend",
    "block": 20,
    "delta": -0.038311670850912305,
    "low": -0.07015584515621585,
    "high": 0.0012471362959708568
  },
  {
    "candidate": "inner_selected_blend",
    "block": 60,
    "delta": -0.038311670850912305,
    "low": -0.07102795798275897,
    "high": 0.007796850398287081
  },
  {
    "candidate": "equal_pool_blend",
    "block": 20,
    "delta": -0.04533765990913374,
    "low": -0.07525409453322501,
    "high": -0.006814149014540537
  },
  {
    "candidate": "equal_pool_blend",
    "block": 60,
    "delta": -0.04533765990913374,
    "low": -0.07704627473194313,
    "high": -0.0016708480832549717
  }
]
```
