# Active F1 goal: stage 2 — 19 October 2026

Goal remains ACTIVE. Previous goal turn was progress; this turn supplies further experiments and verified small observed F1 growth. No independent improvement acceptance.

| Pipeline | Mean macro F1 | Worst fold | Mean bear F1 | Mean bull F1 |
|---|---:|---:|---:|---:|
| Previous best | 0.494927 | 0.400628 | 0.302320 | 0.436668 |
| Causal adaptive fusion | 0.497292 | 0.397404 | 0.323324 | 0.424419 |
| Fixed hysteresis | 0.483304 | 0.399048 | 0.297249 | 0.411619 |
| Forward state filter | 0.481349 | 0.360325 | 0.271195 | 0.424244 |
| Ten-session GRU supplement | 0.454616 | 0.366504 | 0.250442 | 0.388504 |
| Component winner gate | 0.482348 | 0.379954 | 0.287753 | 0.418762 |

The highest observed score is now 0.497291980842, up0.0023646 (0.236 percentage points) versus0.494927379144. It learns coarse classifier/density mixing weights and score temperatures ONLY from mature historical OOF outcomes, pools two fixed history windows with a conservative baseline and uses the same causal EMA5 mixture. No ground-truth labels are smoothed or redefined.

Bear F1 improves to0.3233, but bull F1 drops to0.4244 and worst fold drops to0.3974. All preset +1pt/worst/directional/MCC/three-fold screens fail; descriptive20/60-session block intervals contain0. This is progress on observed development F1, not a completed claim of a reliably better model.

The GRU experiment uses a one-layer hidden8 network, class-balanced loss, fixed40 epochs, AdamW, three fixed seeds and matched sequence lengths1/10. CPU preprocessing learns medians/means/scales on past training windows only, includes missing-feature flags and never fills prices. Actual training used the available GPU with deterministic settings. All168 checkpoints pass stored-hash/timing checks and save/reload predictions are identical (max error0). The tested10-session network does not improve the ensemble; this does not establish a universal limit for all sequence models.

The winner gate is a small depth2 LightGBM trained only on mature past rows where one component was correct and the other was wrong. It also fails to improve. Hysteresis and forward filtering mostly lag transitions.

Verification: full201-test regime suite passed; one newly added real fitted gate test also passed.7 focused timing/normalization/metric-schema/CPU-checkpoint tests passed. Every saved candidate in all five new runs was independently rescored from its forecast CSV against raw full-calendar sigma/targets; all1560 labels and T+20 endpoints match, and mean fold F1 reproduces at1e-15. Every saved source hash remains unchanged.

Descriptive fusion intervals:
```json
[
  {
    "candidate": "adaptive_pool_smoothed",
    "block_sessions": 20,
    "delta": 0.0023646016979674833,
    "low": -0.014899237635798606,
    "high": 0.01714127791864218
  },
  {
    "candidate": "adaptive_pool_smoothed",
    "block_sessions": 60,
    "delta": 0.0023646016979674833,
    "low": -0.018174973390148473,
    "high": 0.01631843902638542
  },
  {
    "candidate": "adaptive504_smoothed",
    "block_sessions": 20,
    "delta": -0.0009003082954085473,
    "low": -0.02461065533491719,
    "high": 0.020131374133303022
  },
  {
    "candidate": "adaptive504_smoothed",
    "block_sessions": 60,
    "delta": -0.0009003082954085473,
    "low": -0.028024430823426413,
    "high": 0.018702878783543056
  }
]
```

Next action: assess complete-ensemble calibration using forecasts generated within purged training folds with matched refit cadence. Keep goal active and preserve fixed target/cohort; do not choose arbitrary outer weights or claim a fresh historical holdout.

Reproduce:
```bash
python3 ml/experiment_regime_state_decisions.py
python3 ml/experiment_regime_forward_filter.py
python3 ml/experiment_regime_temporal_fusion.py
python3 ml/experiment_regime_gru.py
python3 ml/experiment_regime_component_gate.py
```

GRU default requires the pinned component archive directories. Check plan.json before reproducing; new experiments do not silently replace or select source runs.
