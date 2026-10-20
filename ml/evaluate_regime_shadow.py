"""Append realized T+20 outcomes to frozen prospective forecasts; no refitting.

Backcasts never enter this ledger or score. Screening does not deploy a model
or certify that an adaptive strategy will remain profitable.
"""
import argparse
from datetime import datetime,timezone,time
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

import regime_shadow as shadow
import regime_shadow_ledger as ledger
import experiment_regime_risk as risk
import research_protocol as exposure_tracker


def outcome_candidates(predictions,index,lock,candidate_id,contract_sha,snapshot_sha,now=None):
    now=pd.Timestamp(now or datetime.now(timezone.utc))
    calendar=pd.DatetimeIndex(index.Date)
    results=[];pending=0
    for record in predictions:
        if record.get('kind')!='prediction' or record.get('mode')!='prospective':raise ValueError('Backcast/nonprediction in prospective ledger')
        if record['candidate_id']!=candidate_id or record['runtime_sha256']!=lock['runtime_sha256'] or record['contract_sha256']!=contract_sha:raise ValueError('Forecast belongs to a different frozen candidate/runtime')
        shadow.prospective_timing(record['Date'],record['emitted_at'],lock['runtime_frozen_at'])
        if pd.Timestamp(record['emitted_at'])>now:raise ValueError('Future emission timestamp')
        decision=pd.Timestamp(record['Date']);position=calendar.get_indexer([decision])[0]
        if position<0:
            if decision>calendar.max():pending+=1;continue
            raise ValueError('Previously emitted session disappeared')
        start=float(index.Price.iloc[position])
        if not np.isclose(start,record['decision_close'],rtol=0,atol=1e-12):raise ValueError('Previously emitted close was revised')
        end_position=position+20
        if end_position>=len(calendar):pending+=1;continue
        end=calendar[end_position]
        available=pd.Timestamp(datetime.combine(end.date(),time(15,5),tzinfo=shadow.TZ))
        if now<available:pending+=1;continue
        # Use the emitted close, not a later reserialization of that value.
        start=float(record['decision_close']);end_price=float(index.Price.iloc[end_position])
        decimal_start,decimal_end=Decimal(str(start)),Decimal(str(end_price))
        forward=float(decimal_end/decimal_start-Decimal('1'))
        bearish=decimal_end<decimal_start*Decimal('.95')
        results.append(dict(kind='outcome',record_id='outcome:'+record['_record_hash'],prediction_hash=record['_record_hash'],
                            candidate_id=candidate_id,Date=str(decision.date()),label_end_date=str(end.date()),
                            decision_close=start,end_close=end_price,future_return=forward,common_bear=bool(bearish),
                            source_snapshot_sha256=snapshot_sha,recorded_at=now.isoformat()))
    return results,pending


def independent_interval_clusters(rows,index):
    calendar=pd.DatetimeIndex(index.Date)
    positive=rows.loc[rows.common_bear].sort_values('Date')
    clusters=0;last_end=-1
    for date in positive.Date:
        start=calendar.get_indexer([pd.Timestamp(date)])[0]
        if start<0:raise ValueError('Missing positive decision date')
        if start>last_end:clusters+=1
        last_end=max(last_end,start+20)
    return clusters


def screening(rows,index,protocol):
    if rows.empty:return dict(status='insufficient_prospective_evidence',n_matured=0,positive_clusters=0,metrics=None,intervals=[])
    metrics=risk.binary_metrics(rows.common_bear,rows.alarm)
    reference=risk.binary_metrics(rows.common_bear,rows.baseline_alarm)
    clusters=independent_interval_clusters(rows,index)
    enough=len(rows)>=protocol['min_matured_sessions'] and metrics['support']>=protocol['min_bear_samples'] and clusters>=protocol['min_nonoverlapping_positive_clusters']
    point_pass=(metrics['precision'] is not None and metrics['precision']>=protocol['precision_min'] and metrics['recall']>=protocol['recall_min'] and metrics['alarm_rate']<=protocol['alarm_rate_max'])
    intervals=[];paired_pass=False
    if enough:
        current=rows[['Date','common_bear','alarm']].copy();current['policy']='challenger';current['outer_fold']=1
        baseline=current.copy();baseline['policy']='fixed_5pct';baseline['alarm']=rows.baseline_alarm.to_numpy()
        # Transient reference alias required by existing helper; actual emitted
        # reference is the standalone 3y expert, not an absolute-label model.
        intervals=risk.bootstrap_deltas(pd.concat([baseline,current],ignore_index=True),repeats=protocol['bootstrap_repeats'])
        for row in intervals:row['reference']=protocol['reference']
        paired_pass=all(row['delta_low'] is not None and row['delta_low']>(0. if row['metric']=='precision' else protocol['recall_noninferiority_margin']) for row in intervals)
    status='eligible_for_independent_review_not_auto_deploy' if enough and point_pass and paired_pass else ('prospective_screen_failed' if enough else 'insufficient_prospective_evidence')
    return dict(status=status,n_matured=len(rows),positive_clusters=clusters,metrics=metrics,reference_metrics=reference,
                point_screen_pass=bool(point_pass),paired_screen_pass=bool(paired_pass),intervals=intervals,
                caveat='Positive clusters are disjoint labeled intervals, not proof of independent economic shocks. No profit/fees/backtest claim.')


def evaluate(data,contract_path=shadow.CONTRACT):
    contract_path=Path(contract_path);artifact=contract_path.parent
    contract=shadow.read_contract(contract_path);lock=shadow.check_runtime_lock(contract_path)
    protocol=json.loads((artifact/'prospective_protocol.json').read_text())
    if protocol['contract_sha256']!=shadow.sha(contract_path) or protocol['runtime_sha256']!=lock['runtime_sha256']:raise ValueError('Protocol/candidate mismatch')
    index,audit=shadow.load_index(data)
    predictions=ledger.read_ledger(artifact/lock['prospective_ledger'])
    candidates,pending=outcome_candidates(predictions,index,lock,contract['candidate_id'],shadow.sha(contract_path),audit['sha256'])
    if predictions:
        features=shadow.feature_frame(index,contract).set_index('Date')
        for record in predictions:
            date=pd.Timestamp(record['Date'])
            if date not in features.index:continue
            X=features.loc[date,contract['feature_schema']].to_numpy(dtype=float).reshape(1,-1)
            import hashlib
            if hashlib.sha256(X.tobytes()).hexdigest()!=record['feature_sha256']:raise ValueError('Historical forecast features changed')
    outcome_path=artifact/'prospective_outcomes.jsonl'
    existing=ledger.read_ledger(outcome_path);known={r['record_id']:r for r in existing}
    for record in candidates:
        if record['record_id'] in known:
            old=known[record['record_id']]
            for key in ['prediction_hash','Date','label_end_date','decision_close','end_close','future_return','common_bear']:
                numeric=key in ['decision_close','end_close','future_return']
                same=np.isclose(old[key],record[key],rtol=0,atol=1e-12) if numeric else old[key]==record[key]
                if not same:raise ValueError('Previously scored outcome changed: '+key)
            continue
        ledger.append_record(outcome_path,record)
    outcomes=ledger.read_ledger(outcome_path)
    by_hash={r['_record_hash']:r for r in predictions};rows=[]
    for outcome in outcomes:
        if outcome.get('kind')!='outcome' or outcome['prediction_hash'] not in by_hash:raise ValueError('Orphan/nonoutcome in realized ledger')
        prediction=by_hash[outcome['prediction_hash']]
        rows.append(dict(Date=pd.Timestamp(prediction['Date']),common_bear=outcome['common_bear'],
                         alarm=prediction['alarm'],baseline_alarm=prediction['baselines'][protocol['reference']]['alarm']))
    frame=pd.DataFrame(rows,columns=['Date','common_bear','alarm','baseline_alarm'])
    result=screening(frame,index,protocol)
    result.update(candidate_id=contract['candidate_id'],predictions=len(predictions),pending_outcomes=pending,
                  latest_reviewed_session=str(index.Date.max().date()),protocol_sha256=shadow.sha(artifact/'prospective_protocol.json'),
                  predictions_ledger_sha256=shadow.sha(artifact/lock['prospective_ledger']) if predictions else None,
                  outcomes_ledger_sha256=shadow.sha(outcome_path) if outcomes else None,
                  evaluated_at=datetime.now(timezone.utc).isoformat())
    temporary=artifact/'prospective_status.tmp';temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(artifact/'prospective_status.json')
    # Record newly observed prices/labels so another training script cannot
    # later reuse this period as an untouched historical final test.
    registry=shadow.ROOT/'holdout_exposure.json'
    consumed=exposure_tracker.observed_exposure(registry,shadow.ROOT/'reports/regime_v2')['latest_observed_label_date']
    latest=index.Date.max()
    if consumed is None or latest>pd.Timestamp(consumed):
        calendar=pd.DatetimeIndex(index.Date)
        prior=calendar.searchsorted(pd.Timestamp(consumed),side='right') if consumed else 20
        decision_start=index.Date.iloc[max(0,prior-20)]
        directory=artifact/'exposures';directory.mkdir(exist_ok=True)
        evidence=directory/(str(latest.date())+'_'+audit['sha256'][:8]+'.json')
        if not evidence.exists():
            with evidence.open('x') as handle:json.dump(dict(role='shadow_raw_price_exposure_not_independent_test',source_snapshot_sha256=audit['sha256'],observed_through=str(latest.date()),first_new_mature_decision=str(decision_start.date())),handle,indent=2);handle.write('\n')
        exposure_tracker.record_exposure(registry,evidence,20,decision_start,latest)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--contract',type=Path,default=shadow.CONTRACT)
    args=parser.parse_args(argv)
    print(json.dumps(evaluate(args.data,args.contract),indent=2))


if __name__=='__main__':main()
