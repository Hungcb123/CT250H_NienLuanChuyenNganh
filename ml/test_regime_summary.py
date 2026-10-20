import unittest
import pandas as pd
import summarize_regime_research as summary


class GateTests(unittest.TestCase):
    def test_gate_does_not_accept_high_pooled_score_with_failed_fold(self):
        gate=dict(causal_precision_min=.25,causal_recall_min=.3,causal_alarm_rate_max=.15,folds_ap_above_prevalence_min=3,no_fold_auroc_below=.45)
        folds=pd.DataFrame(dict(fold=['1','2','3','4'],average_precision=[.2,.3,.1,.3],prevalence=[.1,.1,.1,.1],roc_auc=[.6,.6,.2,.7]))
        pooled=dict(precision=.4,recall=.4,alarm_rate=.1)
        result=summary.gate_result(pooled,folds,gate)
        self.assertFalse(result['passes_development_screen'])
        self.assertIn('fold_auc',result['failed_gates'])

    def test_audit_rejects_wrong_summary_counts(self):
        predictions=pd.DataFrame(dict(Date=pd.date_range('2020-01-01',periods=4),future_return=[-.1,0,0,0],common_bear=[True,False,False,False],alarm=[True,True,False,False],outer_fold=[1]*4))
        actual=summary.risk.binary_metrics(predictions.common_bear,predictions.alarm)
        actual['fold']='all';actual['tp']=99
        with self.assertRaisesRegex(ValueError,'contradicts'):
            summary.audit_metrics(pd.DataFrame([actual]),predictions,'static',predictions.Date)
