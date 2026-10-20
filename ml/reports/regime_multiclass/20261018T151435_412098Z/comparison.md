# Three-class T+20 forecasting: development evidence

Fixed +/-5% labels, identical 1560 previously inspected dates. No unseen-test or deployment claim.

| Candidate | Mean F1 | Worst F1 | Mean MCC | Better folds vs control | Screen |
|---|---:|---:|---:|---:|---|
| gbm_balanced_3y/argmax | 0.3412 | 0.3122 | 0.0307 | 0/4 | False |
| gbm_balanced_3y/causal_macro_weights | 0.3327 | 0.2687 | 0.0197 | 2/4 | False |
| gbm_unweighted_3y/argmax | 0.3432 | 0.2855 | 0.0342 | 2/4 | False |
| gbm_unweighted_3y/causal_macro_weights | 0.3170 | 0.2899 | -0.0009 | 0/4 | False |
| ordinal_unweighted_3y/argmax | 0.3228 | 0.2556 | 0.0026 | 2/4 | False |
| ordinal_unweighted_3y/causal_macro_weights | 0.3278 | 0.2605 | 0.0099 | 1/4 | False |
| logistic_balanced_3y/argmax | 0.2868 | 0.2621 | 0.0006 | 0/4 | False |
| logistic_balanced_3y/causal_macro_weights | 0.3075 | 0.2736 | -0.0089 | 0/4 | False |
| logistic_unweighted_3y/argmax | 0.3076 | 0.3018 | 0.0153 | 0/4 | False |
| logistic_unweighted_3y/causal_macro_weights | 0.3166 | 0.2933 | 0.0056 | 2/4 | False |
| gbm_balanced_expanding/argmax | 0.3666 | 0.3347 | 0.0669 | 3/4 | True |
| gbm_balanced_expanding/causal_macro_weights | 0.3657 | 0.3182 | 0.0745 | 3/4 | True |
| gbm_unweighted_expanding/argmax | 0.3347 | 0.2516 | 0.0523 | 2/4 | False |
| gbm_unweighted_expanding/causal_macro_weights | 0.3457 | 0.2818 | 0.0346 | 2/4 | False |
| ordinal_unweighted_expanding/argmax | 0.3320 | 0.2544 | 0.0476 | 1/4 | False |
| ordinal_unweighted_expanding/causal_macro_weights | 0.3522 | 0.2889 | 0.0634 | 2/4 | False |
| logistic_balanced_expanding/argmax | 0.2992 | 0.2366 | -0.0025 | 1/4 | False |
| logistic_balanced_expanding/causal_macro_weights | 0.3131 | 0.2541 | 0.0369 | 1/4 | False |
| logistic_unweighted_expanding/argmax | 0.3083 | 0.2693 | 0.0478 | 1/4 | False |
| logistic_unweighted_expanding/causal_macro_weights | 0.3143 | 0.2617 | 0.0277 | 1/4 | False |
