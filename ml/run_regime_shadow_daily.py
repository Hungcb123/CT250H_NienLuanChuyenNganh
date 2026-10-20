"""Local scheduled research collection, prospective emission and outcome scoring.

No trading/backend deployment, no notifications. Weekend/preclose ticks do no
network calls. Requires the machine/WSL and cron service to remain running.
"""
import argparse
from datetime import datetime,timezone,time,timedelta
import fcntl
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys

import regime_shadow as shadow
import regime_shadow_ledger as ledger
import collect_regime_shadow_data as collect
import evaluate_regime_shadow as evaluate

OPS_FILES=['run_regime_shadow_daily.py','evaluate_regime_shadow.py','research_protocol.py']


def freeze_operations(artifact):
    artifact=Path(artifact)
    shadow.read_contract(artifact/'contract.json');shadow.check_runtime_lock(artifact/'contract.json')
    if ledger.read_ledger(artifact/'prospective_predictions.jsonl'):raise ValueError('Operation protocol must freeze before first prospective prediction')
    lock=dict(created_at=datetime.now(timezone.utc).isoformat(),contract_sha256=shadow.sha(artifact/'contract.json'),
              file_sha256={name:shadow.sha(shadow.ROOT/name) for name in OPS_FILES},
              artifact_sha256={name:shadow.sha(artifact/name) for name in ['runtime_lock.json','prospective_protocol.json','environment_lock.json']},
              interpreter=sys.executable,status='research_only_not_deployed')
    with (artifact/'operations_lock.json').open('x') as handle:json.dump(lock,handle,indent=2);handle.write('\n')
    return lock


def validate_operations(artifact):
    artifact=Path(artifact)
    lock=json.loads((artifact/'operations_lock.json').read_text())
    if lock['contract_sha256']!=shadow.sha(artifact/'contract.json'):raise ValueError('Operations contract changed')
    for name,digest in lock['file_sha256'].items():
        if shadow.sha(shadow.ROOT/name)!=digest:raise ValueError('Scheduled code changed: '+name)
    for name,digest in lock['artifact_sha256'].items():
        if shadow.sha(artifact/name)!=digest:raise ValueError('Frozen operations artifact changed: '+name)
    environment=json.loads((artifact/'environment_lock.json').read_text())
    if platform.python_version()!=environment['python']:raise ValueError('Frozen Python version changed')
    for package,expected in environment['packages'].items():
        if version(package)!=expected:raise ValueError('Frozen dependency version changed: '+package)
    shadow.read_contract(artifact/'contract.json');shadow.check_runtime_lock(artifact/'contract.json')
    return lock


def atomic_state(path,state):
    path=Path(path);temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2)+'\n');temporary.replace(path)
    return state


def run_once(artifact=shadow.CONTRACT.parent,now=None):
    artifact=Path(artifact);validate_operations(artifact)
    current=now or datetime.now(shadow.TZ)
    if current.tzinfo is None:raise ValueError('Need timezone-aware runner clock')
    local=current.astimezone(shadow.TZ);date=str(local.date())
    with (artifact/'daily_runner.lock').open('a+') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return dict(status='already_running')
        path=artifact/'daily_state.json';state=json.loads(path.read_text()) if path.exists() else {}
        state.update(checked_at=datetime.now(timezone.utc).isoformat(),local_date=date)
        if local.weekday()>=5 or local.time()<time(15,5):
            state['status']='outside_completed_session_window';return atomic_state(path,state)
        if state.get('last_completed_date')==date:
            state['status']='already_completed_today';return atomic_state(path,state)
        if state.get('next_attempt_at') and pd_timestamp(state['next_attempt_at'])>pd_timestamp(current):
            state['status']='waiting_retry_backoff';return atomic_state(path,state)
        try:
            latest=collect.latest_snapshot()
            # Reuse an already accepted same-day snapshot after a prior process
            # interruption; avoid refetching/revising an emitted source snapshot.
            if latest is None or str(shadow.load_index(latest)[0].Date.max().date())!=date:
                stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
                directory=shadow.ROOT/'data/research/regime_shadow'/('daily_'+stamp)
                collect.collect(directory,date);latest=directory/'VNINDEX.csv'
            index,audit=shadow.load_index(latest)
            if str(index.Date.max().date())!=date:
                state.update(status='waiting_for_completed_session_data',latest_session=str(index.Date.max().date()),
                             next_attempt_at=(current+timedelta(hours=1)).isoformat())
                return atomic_state(path,state)
            prediction=shadow.main(['--contract',str(artifact/'contract.json'),'--data',str(latest),'--emit'])
            result=evaluate.evaluate(latest,artifact/'contract.json')
            state.update(status='completed',last_completed_date=date,source_snapshot=str(latest.resolve()),
                         source_snapshot_sha256=audit['sha256'],prediction_record_id=prediction['record_id'],
                         prospective_predictions=result['predictions'],matured_outcomes=result['n_matured'],
                         evidence_status=result['status'],next_attempt_at=None)
            return atomic_state(path,state)
        except Exception as exc:
            state.update(status='error',error_type=type(exc).__name__,error=str(exc),next_attempt_at=(current+timedelta(hours=1)).isoformat())
            atomic_state(path,state)
            raise


def pd_timestamp(value):
    import pandas as pd
    return pd.Timestamp(value)


def cron_text(existing,command,candidate_id):
    begin='# BEGIN regime-shadow research '+candidate_id
    end='# END regime-shadow research '+candidate_id
    if existing.count(begin)!=existing.count(end) or existing.count(begin)>1:raise ValueError('Ambiguous owned cron block')
    if begin in existing:
        pattern=re.escape(begin)+r'\n[\s\S]*?'+re.escape(end)+r'\n?'
        existing=re.sub(pattern,'',existing,count=1)
    block=begin+'\n*/15 * * * * '+command+'\n'+end+'\n'
    return existing+('' if not existing or existing.endswith('\n') else '\n')+block


def install_cron(artifact=shadow.CONTRACT.parent):
    artifact=Path(artifact);validate_operations(artifact)
    service=subprocess.run(['systemctl','is-active','cron'],capture_output=True,text=True)
    if service.returncode!=0 or service.stdout.strip()!='active':raise ValueError('Cron service is not active; no schedule installed')
    existing=subprocess.run(['crontab','-l'],capture_output=True,text=True)
    if existing.returncode not in [0,1]:raise ValueError('Cannot inspect user crontab')
    before=existing.stdout if existing.returncode==0 else ''
    candidate=shadow.read_contract(artifact/'contract.json')['candidate_id']
    script=shadow.ROOT/'run_regime_shadow_daily.py'
    log=artifact/'daily.log'
    command='('+shlex.quote(sys.executable)+' '+shlex.quote(str(script))+' --artifact '+shlex.quote(str(artifact))+' >> '+shlex.quote(str(log))+' 2>&1) 2>> /tmp/regime-shadow-cron-errors.log'
    after=cron_text(before,command,candidate)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    backup=artifact/('cron_before_'+stamp+'.txt')
    with backup.open('x') as handle:handle.write(before)
    backup.chmod(0o600)
    subprocess.run(['crontab','-'],input=after,text=True,check=True,capture_output=True)
    check=subprocess.run(['crontab','-l'],capture_output=True,text=True,check=True)
    if check.stdout!=after:raise ValueError('Installed crontab differs from reviewable schedule')
    receipt=dict(installed_at=datetime.now(timezone.utc).isoformat(),cron_service='active',interpreter=sys.executable,
                 command=command,interval_minutes=15,script_sha256=shadow.sha(script),operations_lock_sha256=shadow.sha(artifact/'operations_lock.json'),
                 original_crontab_backup=str(backup),limitation='Runs only while this machine/WSL and cron are active; no external notifications or model deployment')
    atomic_state(artifact/'schedule_receipt.json',receipt)
    return receipt


def status(artifact=shadow.CONTRACT.parent):
    artifact=Path(artifact);lock=validate_operations(artifact)
    candidate=shadow.read_contract(artifact/'contract.json')['candidate_id']
    table=subprocess.run(['crontab','-l'],capture_output=True,text=True)
    service=subprocess.run(['systemctl','is-active','cron'],capture_output=True,text=True)
    return dict(candidate_id=candidate,operations_frozen=True,scheduled=('# BEGIN regime-shadow research '+candidate) in table.stdout,
                cron_active=service.returncode==0 and service.stdout.strip()=='active',
                prospective_predictions=len(ledger.read_ledger(artifact/'prospective_predictions.jsonl')),
                realized_outcomes=len(ledger.read_ledger(artifact/'prospective_outcomes.jsonl')),
                daily_state=json.loads((artifact/'daily_state.json').read_text()) if (artifact/'daily_state.json').exists() else None)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,default=shadow.CONTRACT.parent)
    parser.add_argument('--freeze-operations',action='store_true')
    parser.add_argument('--install-cron',action='store_true')
    parser.add_argument('--status',action='store_true')
    args=parser.parse_args(argv)
    if args.freeze_operations:result=freeze_operations(args.artifact)
    elif args.install_cron:result=install_cron(args.artifact)
    elif args.status:result=status(args.artifact)
    else:result=run_once(args.artifact)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':main()
