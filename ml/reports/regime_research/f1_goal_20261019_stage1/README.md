# Active F1 goal: stage 1 — 19 October 2026

Objective: tiếp tục đi, mọi giá có F1 tốt hơn. Status remains ACTIVE; this stage is progress, not goal completion.

The previous goal turn was progress: seven completed experiments and a saved 0.492508 challenger. This turn adds five causal studies and an independently recalculated, slightly higher development F1. No genuine external blocker is present.

| Variant | Mean fold macro F1 | Worst fold F1 | Bear F1 | Bull F1 |
|---|---:|---:|---:|---:|
| Previous information challenger | 0.492508 | 0.400013 | 0.290485 | 0.441610 |
| Equal five-seed density ensemble | 0.493231 | 0.402441 | 0.296520 | 0.440245 |
| Five-seed ensemble + 50% current / 50% causal EMA5 scores | 0.494927 | 0.400628 | 0.302320 | 0.436668 |

Same 1,560 dates and adaptive T+20 +/-1 trailing-volatility-unit labels. Mean fold macro F1 is not accuracy. The higher score is historical development evidence, not an independent test or calibrated confidence estimate. Versus 0.492508, improvement is 0.002419 (0.242 percentage points). Bear F1 improves, bull F1 declines slightly; no predeclared +1pt/directional/stability screen passes.

Methods: refit cadence20/5 (worse), fixed seeds7/21/42/84/126 (small gain), fixed decay half-lives126/252 (worse), six causal calendar features (worse), and causal score smoothing (small gain). No seed was chosen using outer performance. Labels were never smoothed or shifted. Score filters reset over missing sessions.

The seed model retains the fixed inner-selected trend information classifier and risk classifier, and averages the original raw/normalized expanding quantile density over five seeds. Each density uses nine LightGBM quantile heads. The EMA candidate blends its current scores equally with its span5 causal EMA. It consumes current/past forecasts only.

Independent audit recomputes sigma and T+20 endpoints directly from the raw accepted Date/Close file, verifies all1,560 labels and label-end dates, and recalculates four fold metrics using sklearn rather than the training report helper. Exact report parity passes.24 coincident-first-refit checks also reproduce the original classifiers/densities at1e-12 tolerance.

Verification: full193-test regime suite passed, plus one new causal forecast-filter test. The existing24-test schedule/return/label component suite also passed. All current run source hashes are unchanged from their pre-run plans.

Descriptive paired circular-block sensitivity vs previous0.492508 model:
```json
[
  {
    "block": 20,
    "delta": 0.0024191608636431328,
    "low": -0.013856384343169957,
    "high": 0.015517056268421344
  },
  {
    "block": 60,
    "delta": 0.0024191608636431328,
    "low": -0.01431068082394633,
    "high": 0.016831087851877022
  }
]
```

Next: investigate temporal decision structure and ensemble-level selection using only available past outcomes. Preserve this small gain as a research candidate; do not repeatedly maximize arbitrary thresholds on outer history or replace the application model.

Run commands:
```bash
python3 ml/experiment_regime_dynamic_refresh.py
python3 ml/experiment_regime_density_seeds.py
python3 ml/experiment_regime_density_recency.py
python3 ml/experiment_regime_calendar.py
python3 ml/experiment_regime_forecast_smoothing.py
```

The smoothing default source is the frozen five-seed run named in its plan. It does not auto-select a newer/better run.
