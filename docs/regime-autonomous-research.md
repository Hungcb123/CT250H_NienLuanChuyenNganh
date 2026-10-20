# Autonomous regime model research

The user authorized autonomous training and evaluation. The objective remains a useful, robust model; research improvements are not treated as successful deployment.

All existing report dates have been inspected. Scores on them are development evidence, even with purged temporal validation. An eventual frozen candidate needs prospective shadow evaluation for fresh evidence. Production ONNX artifacts are preserved during research.

The research ledger is `ml/reports/regime_research/progress.json`. Provisional research gates are precision >=25%, recall >=30%, realized alarm rate <=15%, AP above prevalence in at least three of four folds and no fold AUROC below 0.45. These gates were set after prior studies and before the next history study; they are an operational screen, not an independent statistical guarantee.

## Studies

- Fixed shallow LightGBM: `ml/reports/regime_risk/20261017T153519_376909Z`. Rolling quantiles reduced alarms but did not improve detection. Rejected as an improvement.
- Six predeclared candidates: `ml/reports/regime_candidates/20261017T154743_717260Z`. Logistic, RBF SVM, Ridge standardized-return prediction and shallow LightGBM, with additional close-based risk/stretch features. Same exact prior evaluation dates and purged core/calibration/refit protocol. No strong improvement.
- Close-only history study: `ml/experiment_regime_history.py`. Removes ETF requirement from TRAINING history, allowing reviewed VNINDEX data since 2010. Retains EXACT same previously frozen prediction dates, confirmed by tests. Compares fixed models with 3y,5y,expanding windows. Source caveats of oldest single-broker history remain. Historical source data is unchanged.

Run the additional studies from the repository root:

```bash
python3 ml/experiment_regime_candidates.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json
python3 ml/experiment_regime_history.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json
```

Both accept `--audit-only` and write new timestamp directories. Candidate hyperparameters are fixed; `--quick` does not reduce fixed fits and is not a different experimental budget. Predictions contain ranking scores, not necessarily probabilities. AP/ROC-AUC on pooled scores across refitted models can obscure local behavior: always inspect each fold and refit.

`threshold_comparison.csv` contains causal static/rolling results; `retrospective_equal_count.csv` is ranking diagnostics using whole future-fold scores, not executable performance. All positive days overlap in T+20 labels and are not independent crashes. No user-facing financial promise or simulated portfolio profitability is inferred.

## Findings after the first autonomous batch

The long-history study completed at `ml/reports/regime_history/20261017T155014_918591Z`. Expanding-history shallow LightGBM is the strongest of that batch at the historical static threshold: precision 21.8%, recall 21.5%, alarm rate 12.1%. It still fails the provisional gates; fold3 AUROC is only 0.253. It is not accepted as a robust model.

Before adding OHLC exhaustion/volume features, archived broker fields were audited (`ml/reports/regime_research/ohlcv_audit`). VCI/KBS close agreement is ~99.75% on overlapping raw rows, but open agreement is ~70.34% and volume agreement only ~55.02%. These are raw-source comparisons before any adjudication; they demonstrate field differences, not which broker is correct. OHLC/volume feature provenance must be resolved before relying on them. No source file or production artifact was changed.

## Data ablation and training freshness

Additional completed studies:

- `ml/reports/regime_ohlcv/20261017T155354_185246Z`: four OHLCV ablations. Only unique largest subsets of at least two agreeing brokers are accepted; disputed source fields remain missing. Source bars must match reviewed close and obey OHLC bounds. Logistic missing-value statistics are fitted only on core rows. No sufficient improvement.
- `ml/reports/regime_global/20261017T160115_134573Z`: four VIX ablations. [Official Cboe historical VIX source](https://www.cboe.com/tradable_products/vix/vix_historical_data), source CSV hash pinned in `ml/data/research/global_risk/VIX.provenance.json`. Features join backward on US observation date +2 calendar days, with maximum stale age 7 days after that availability date. This is a conservative timing assumption, not original release-vintage verification. No sufficient improvement.
- `ml/reports/regime_fresh/20261017T160231_480894Z`: four training-freshness variants. Reserving 20% for calibration had left old core data (first historical block ended July2019 while predictions began March2020). Calibration20/refit20 with 3y window makes fold3 AUROC 0.574 and all four fold APs exceed their base rates. Overall causal precision15.8%, recall30.9%, alarm24.0% still fails gates. Expanding histories rank more strongly overall but fail fold3.

The follow-up script `ml/experiment_regime_fresh_followup.py` compares 3y/5y windows with calibration20/40 and refit5/20. Same predeclared shallow trees; it tests timing sensitivity without Optuna search. All prediction dates remain identical.

Rebuild the prediction-audited comparison:

```bash
python3 ml/summarize_regime_research.py
```

The summarizer verifies alarm counts/precision/recall against individual predictions, the common −5% outcome, and the canonical frozen dates before applying gates. It rejects contradictions. It writes `audited_comparison.csv` and `screening_summary.json` under `ml/reports/regime_research/`. Native F1 for different target definitions and retrospective equal-count scores are excluded from the acceptance screen. A development screen pass alone never proves independent-test performance.

## Frozen research challenger (not accepted for live use)

The inspected-development search now includes group-index features, causal two-history ensembles, class-prior corrected absolute-loss mixtures, archived online quantiles, a fixed recency blend and dense forward-return quantile regression. None passed the full predeclared screen.

The most promising alarm-efficiency challenger is `equal_ensemble_online120`, archived at `ml/reports/regime_online/20261017T162627_969154Z/`. It combines 3y/expanding core-calibration-standardized LightGBM scores equally and applies a strictly prior 120-observation p90. First120 historical predictions retain their existing causal calibration thresholds; no rows are dropped.

Against the original volatility model on the same1560 days: TP56 vs55, FP169 vs270, precision24.89% vs16.92%, recall29.32% vs28.80%, alarm14.42% vs20.83%. This is a historical research comparison, not proof of a reliable improvement. The challenger misses some screening gates and the paired 20/60-session bootstrap intervals for improvements include zero. Artifacts: `ml/reports/regime_research/equal_online120_vs_original_vol/`.

The research-only algorithm contract is pinned in `ml/artifacts/regime_shadow_candidate_20261017/contract.json`, including feature schema, exact core/calibration/label timing, normalization, model parameters, source-code hashes and the record that it is **not live approved**. This freezes a challenger for prospective examination rather than declaring the user goal achieved.

Future validation must separate research backcasts used to initialize score history from predictions actually emitted after the freeze on fresh sessions. A prediction cannot be marked prospective merely because its realized T+20 outcome is new: the algorithm must have been frozen and emitted at the original decision time. Genuinely prospective outcomes require subsequent trading sessions and cannot be manufactured by rerunning inspected history.
