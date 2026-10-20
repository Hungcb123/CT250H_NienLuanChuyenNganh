# Broad adaptive-target search — 19 October 2026

**Highest observed mean macro F1: 0.4925, versus retained baseline 0.4893. No candidate meets the preset improvement screen.** The practical forecasting objective is not complete.

Same T+20 volatility-adjusted labels and 1,560 frozen dates in all experiments. Numbers are the mean of four fold macro F1 scores, not accuracy. The macro-only selector is a replay of the same fitted components, not independent supporting evidence.

| Preset branch/candidate | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| Retained baseline | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| Information inputs / inner_selected_blend | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| Information inputs / combined_blend | 0.4605 | 0.3333 | 0.2442 | 0.4014 | 0.2329 |
| Long history and asset transfer / extended_target_blend | 0.4675 | 0.3817 | 0.2729 | 0.4064 | 0.2300 |
| Long history and asset transfer / extended_pooled_blend | 0.4703 | 0.3831 | 0.2690 | 0.4142 | 0.2390 |
| Diverse model families / inner_supplement_blend | 0.4873 | 0.4000 | 0.2926 | 0.4216 | 0.2628 |
| Diverse model families / inner_replacement_blend | 0.4840 | 0.4000 | 0.3103 | 0.4032 | 0.2485 |
| Focal and smoothed losses / inner_supplement_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| Focal and smoothed losses / inner_replacement_blend | 0.4893 | 0.4000 | 0.2946 | 0.4310 | 0.2622 |
| CDF and 19 quantiles / linear19_blend | 0.4867 | 0.4010 | 0.2980 | 0.4249 | 0.2551 |
| CDF and 19 quantiles / linear19_supplement | 0.4871 | 0.3971 | 0.2950 | 0.4279 | 0.2568 |
| Pure inner macro selection / macro_information_blend | 0.4925 | 0.4000 | 0.2905 | 0.4416 | 0.2684 |
| Pure inner macro selection / macro_families_supplement | 0.4829 | 0.4000 | 0.2860 | 0.4173 | 0.2555 |
| Full inner fusion selection / fusion_macro | 0.4335 | 0.2401 | 0.2487 | 0.3504 | 0.1953 |
| Full inner fusion selection / fusion_robust | 0.3974 | 0.2401 | 0.1577 | 0.3776 | 0.1589 |

## Interpretation

The information selector chooses the feature group using three purged inner folds. Its choices are VIX / size indices / core / consensus OHLCV for outer folds 1–4. It changes only the trend-classifier quarter of the final score: 25% selected trend classifier + 25% original risk classifier + 50% original expanding return-density score. Other constituent models and fusion weights are unchanged.

Mean F1 gains only 0.00320 (0.32 percentage points), with 60-session paired-block interval [-0.01347, 0.02307]. Bear F1 drops from 0.2946 to 0.2905 while bull F1 improves from 0.4310 to 0.4416. Worst fold remains 0.4000. This is a research challenger, not a proven better live model. It is NOT a 49.25% accuracy or confidence claim.

Information experiments keep disputed fields missing, use two-broker OHLC/volume consensus, and lag VIX observation dates by two calendar days. Historical release vintages remain uncertified. The extended-data quantile experiment increases first-boundary target rows from 761 (matched historical dates) to 2,469 (accepted history from 2010). The pooled version adds 1,018 auxiliary rows but preserves unit total date mass. Transfer improves its weak matched target-only density control, yet the resulting blend remains below the incumbent.

Eight fixed new model families were tested with training-only scaling/class costs: CatBoost, histogram boosting, RandomForest, ExtraTrees, RBF SVC, MLP, shrinkage LDA and KNN. These fixed configurations do not exhaust every architecture/hyperparameter combination. MLP reached its iteration cap in some fits.

Loss experiments include matched custom cross-entropy, label smoothing at 0.05/0.10 and focal gamma1/2. The classifier labels are never changed for evaluation. Analytic focal/smoothed gradients and curvature in non-clipped regions pass independent numerical differentiation checks. Custom-objective schema follows [LightGBM documentation](https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMClassifier.html); focal loss was originally developed for [dense object detection](https://arxiv.org/abs/1708.02002), with no assumed financial efficacy.

Distribution experiments compare coarse nine atoms with linear inverse-CDF interpolation, fixed Gaussian smoothing and 19 quantile knots. Exact source cohorts are preserved when reusing the old nine point sets. More knots do not improve the complete ensemble.

The final selector retrains both density branches separately before every inner boundary, scores the COMPLETE fused pipeline for each candidate, and only then applies its choices to archived outer forecasts. It performs worse; the outer results cannot be used to rescue a different fusion.

Verification: full regime suite 190 tests passed. Source/data hashes match every saved plan. Model/application files were not replaced. Chronological validation reduces direct leakage but cannot undo selection bias from repeated study design on these same outer periods.

## Reproduce

Run from repository root; each command writes a new timestamped run and retains existing reports. Scripts that replay component archives require the source directories pinned in their plans.

```bash
python3 ml/experiment_regime_dynamic_information.py
python3 ml/experiment_regime_volatility_transfer.py
python3 ml/experiment_regime_dynamic_families.py
python3 ml/experiment_regime_dynamic_losses.py
python3 ml/experiment_regime_quantile_resolution.py
python3 ml/experiment_regime_inner_macro_selection.py
python3 ml/experiment_regime_fusion_selection.py
python3 -m unittest discover -s ml -p 'test_regime*.py'
```

## Detailed runs

- Information inputs: `ml/reports/regime_dynamic_information/20261019T052057_760569Z/README.md`
- Long history and asset transfer: `ml/reports/regime_volatility_transfer/20261019T052340_598397Z/README.md`
- Diverse model families: `ml/reports/regime_dynamic_families/20261019T052530_594387Z/README.md`
- Focal and smoothed losses: `ml/reports/regime_dynamic_losses/20261019T052808_023744Z/README.md`
- CDF and 19 quantiles: `ml/reports/regime_quantile_resolution/20261019T053037_944295Z/README.md`
- Pure inner macro selection: `ml/reports/regime_inner_macro_selection/20261019T053327_320402Z/README.md`
- Full inner fusion selection: `ml/reports/regime_fusion_selection/20261019T053538_900664Z/README.md`
