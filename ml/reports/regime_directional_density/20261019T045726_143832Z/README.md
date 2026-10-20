# regime_directional_density — 19 October 2026

Inspected historical DEVELOPMENT only. Keep the frozen adaptive blend; no primary candidate passes the predeclared improvement screen. Same 1,560 dates and T+20 +/-1 trailing-volatility-unit labels. No target or mixture-weight search.

| Candidate | Mean fold macro F1 | Worst fold F1 | Mean bear F1 | Mean bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| incumbent | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| new_density | 0.4435 | 0.2943 | 0.2585 | 0.3679 | 0.1863 |
| new_density_blend | 0.4776 | 0.3924 | 0.2926 | 0.4071 | 0.2372 |
| expanded_density_blend | 0.4886 | 0.4024 | 0.2971 | 0.4270 | 0.2591 |

## Preset design

- primary: expanded_density_blend: classifier/old density/new density weights .5/.25/.25. Equal raw/normalized heads in each density.
- secondary: new_density_blend: .5 classifier + .5 new density
- parameters: Original fixed quantile specification unchanged, nine quantiles per model; only features change
- caveats: All dates are repeatedly inspected development. No threshold or weight tuning, calibrated probability, independent test or automatic deployment.
- assumptions: ['All variants use identical dates and labels; adding a feature cannot remove a frozen validation date.', 'Parameters are selected once at each outer fold start using purged inner folds only.', 'The model is refitted periodically using labels known strictly before each prediction block.', 'Rolling windows are calendar years measured from the prediction block start.', 'Each refit uses the same fixed parameters until the next outer fold.', 'A drawdown feature measures current distance below the trailing peak.', 'No confidence threshold, new label definition, financial backtest, or ONNX deployment.']

Feature additions: volatility-normalized momentum at 3/5/10/20/60 sessions, current and lagged shocks against previous known volatility, negative-return shares, downside energy share, short/long volatility ratio, normalized drawdowns, skew and momentum acceleration. All are trailing close-based features; feature set was fixed before fitting. Frozen training/evaluation rows are retained.

The standalone variants are diagnostic. No outer-best variant is automatically promoted. Error analysis by fold/year/fixed volatility buckets is in error_analysis.csv; selection/refit logs and code/data hashes are archived. Decision scores are not calibrated event probabilities. Application models are unchanged.

The specialist study compares matched shallow LightGBM classifiers, one-vs-rest heads and a movement/direction hierarchy with/without added inputs. Its primary model chooses architecture/features using three purged inner folds at each outer boundary. The density follow-up keeps the old quantile learner parameters and adds inputs to expanding raw/normalized return regressors; its primary averages old/new densities before the fixed classifier mix.

Paired circular-block intervals, 1,000 resamples within folds; all historical inference remains sensitive to repeated development inspection:

```json
[
  {
    "candidate": "new_density_blend",
    "block": 20,
    "delta": -0.011689028188255846,
    "low": -0.027869295203939496,
    "high": 0.00437233728583956
  },
  {
    "candidate": "new_density_blend",
    "block": 60,
    "delta": -0.011689028188255846,
    "low": -0.023770568669531585,
    "high": 0.0023097922285103423
  },
  {
    "candidate": "expanded_density_blend",
    "block": 20,
    "delta": -0.0007130756985864184,
    "low": -0.010138664171888797,
    "high": 0.00868529202073891
  },
  {
    "candidate": "expanded_density_blend",
    "block": 60,
    "delta": -0.0007130756985864184,
    "low": -0.010327508440477615,
    "high": 0.008353532581736855
  }
]
```
