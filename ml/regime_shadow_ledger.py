"""Append-only local research evidence log with duplicate and hash-chain checks.

Local hashes detect accidental edits; timestamps are local-clock attestations,
not independent notarization or protection against the machine's owner.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path

GENESIS='0'*64


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def verify_lines(lines):
    previous=GENESIS;records=[];ids=set()
    for line in lines:
        record=json.loads(line)
        digest=record.pop('_record_hash')
        if record.get('_prev_hash')!=previous:raise ValueError('Broken ledger chain')
        if hashlib.sha256(canonical(record).encode()).hexdigest()!=digest:raise ValueError('Ledger record changed')
        if record['record_id'] in ids:raise ValueError('Duplicate ledger record')
        ids.add(record['record_id']);previous=digest
        record['_record_hash']=digest;records.append(record)
    return records


def read_ledger(path):
    path=Path(path)
    if not path.exists():return []
    with path.open() as handle:
        fcntl.flock(handle,fcntl.LOCK_SH)
        return verify_lines(handle.readlines())


def append_record(path,record):
    if '_record_hash' in record or '_prev_hash' in record:raise ValueError('Reserved hash fields')
    if not record.get('record_id'):raise ValueError('Need immutable record_id')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+',encoding='utf-8') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX);handle.seek(0)
        existing=verify_lines(handle.readlines())
        if any(r['record_id']==record['record_id'] for r in existing):raise ValueError('Record already emitted; refusing overwrite')
        value=dict(record,_prev_hash=existing[-1]['_record_hash'] if existing else GENESIS)
        value['_record_hash']=hashlib.sha256(canonical(value).encode()).hexdigest()
        handle.write(canonical(value)+'\n');handle.flush();os.fsync(handle.fileno())
    return value
