# Directional forecast follow-up — 19 October 2026

Four new experiments completed. None passes its preset improvement screen against the frozen adaptive-target blend. The objective of a demonstrably better model remains unmet.

All results below are mean of four fixed macro-F1 folds on 1,560 already-inspected dates. Target: T+20 log return compared with +/- one trailing20 volatility unit. Macro F1 is not accuracy; no change to labels or validation dates.

| Preset primary | Mean macro F1 | Worst-fold F1 | Mean MCC |
|---|---:|---:|---:|
| Retained LightGBM/classifier-density baseline | 0.4893 | 0.4000 | 0.2622 |
| Directional specialists | 0.4510 | 0.3716 | 0.2273 |
| Added inputs for quantiles | 0.4886 | 0.4024 | 0.2591 |
| Delayed decision adapters | 0.4719 | 0.3780 | 0.2476 |
| CatBoost joint quantiles | 0.4785 | 0.3956 | 0.2494 |

The directional-density feature expansion slightly improves the worst fold (0.4024) but reduces mean F1 and MCC; this is not a screen pass. Other primary variants worsen mean and worst-fold F1. No outer-best standalone candidate or retrospective weight combination is promoted.

The baseline still has weak bearish F1 (0.2946 mean) and low bearish recall in folds3/4 (3/45 and 8/70). This is not solved by these alternatives. Negative results do not establish that no predictive information exists; they show that these changes did not provide a reliable gain on this inspected history.

Verification: 178 tests in the full regime suite passed, then two additional real CatBoost backend tests passed. New features have prefix/price-unit invariance checks; all heads reject unavailable supervision; adapter replay passes five real-data prefix checks after corrupting unmatured labels. Each run saves source/data hashes before scoring; every recorded source hash was verified unchanged after completion. No ONNX or backend model replacement.

Practical next step should change the source of evidence rather than optimize thresholds against these same folds: audit genuinely new explanatory data and collect uninspected matured outcomes. Future model choices must stay inside training-only splits. A higher post-hoc outer score by itself would not complete the original objective.

Detailed reports:
- `ml/reports/regime_directional/20261019T045527_492206Z/README.md`
- `ml/reports/regime_directional_density/20261019T045726_143832Z/README.md`
- `ml/reports/regime_adaptive_decisions/20261019T045944_079584Z/README.md`
- `ml/reports/regime_joint_quantiles/20261019T050157_106140Z/README.md`
