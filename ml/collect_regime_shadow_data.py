"""Immutable two-broker Close-only extension of the frozen VNINDEX prefix.

Cross-broker calendar/close disagreement quarantines a snapshot. No historical
price revisions, extrapolation, OHLC substitutions, or fabricated sessions.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,time,timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

import prepare_regime_data as source
from prepare_regime_indices import close_response
import regime_shadow as shadow


def fetch(provider,start,end,directory):
    params=None;body=None
    if provider=='vci':
        url=source.VCI_URL
        body=dict(timeFrame='ONE_DAY',symbols=['VNINDEX'],to=int((pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize(shadow.TZ).timestamp()),
                  countBack=int((pd.Timestamp(end)-pd.Timestamp(start)).days*5/7)+60)
    else:
        url=source.VND_URL
        params=dict(resolution='D',symbol='VNINDEX',**{'from':int(pd.Timestamp(start).tz_localize(shadow.TZ).timestamp()),
                    'to':int((pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize(shadow.TZ).timestamp())})
    request=urllib.request.Request(url+('?' + urllib.parse.urlencode(params) if params else ''),data=json.dumps(body).encode() if body else None,
                                  headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:raw=response.read()
    path=directory/(provider+'_VNINDEX.json');path.write_bytes(raw)
    frame=close_response(json.loads(raw),provider,'VNINDEX',start,end)
    metadata=dict(provider=provider,url=url,params=params,body=body,response='sources/'+path.name,
                  response_sha256=hashlib.sha256(raw).hexdigest(),downloaded_at=datetime.now(timezone.utc).isoformat(),
                  rows=len(frame),start=str(frame.Date.min().date()),end=str(frame.Date.max().date()))
    return frame,metadata


def reconcile(base,frames):
    reviewed=base[['Date','Price']].rename(columns={'Price':'Close'})
    errors=[];end=reviewed.Date.max()
    for provider,frame in frames.items():
        overlap=reviewed.merge(frame,on='Date',suffixes=('_base','_source'),validate='one_to_one')
        if len(overlap)<10:errors.append(provider+': insufficient reviewed overlap')
        mismatch=(overlap.Close_base-overlap.Close_source).abs()>.011
        if mismatch.any():errors.append(provider+': reviewed close revision on '+','.join(overlap.loc[mismatch,'Date'].dt.strftime('%Y-%m-%d')))
        expected=reviewed.loc[reviewed.Date.between(frame.Date.min(),min(end,frame.Date.max())),'Date']
        if not pd.DatetimeIndex(expected).equals(pd.DatetimeIndex(frame.loc[frame.Date<=end,'Date'])):
            errors.append(provider+': calendar differs in reviewed overlap')
    joined=frames['vci'].merge(frames['vnd'],on='Date',how='outer',suffixes=('_vci','_vnd'),validate='one_to_one').sort_values('Date')
    joined['accepted']=(joined.Close_vci-joined.Close_vnd).abs()<=.011
    new=joined.loc[joined.Date>end]
    if not new.accepted.all():errors.append('New close/calendar disagreement on '+','.join(new.loc[~new.accepted,'Date'].dt.strftime('%Y-%m-%d')))
    if errors:return None,joined,errors
    extension=pd.DataFrame(dict(Date=new.Date,Close=(new.Close_vci+new.Close_vnd)/2))
    canonical=pd.concat([reviewed,extension],ignore_index=True)
    if canonical.Date.duplicated().any() or not canonical.Date.is_monotonic_increasing:raise ValueError('Invalid extension ordering')
    return canonical,joined,[]


def collect(output,end=None):
    local=datetime.now(shadow.TZ)
    end=pd.Timestamp(end or local.date())
    if end>pd.Timestamp(local.date()) or (end==pd.Timestamp(local.date()) and local.weekday()<5 and local.time()<time(15,5)):
        raise ValueError('Requested session has not completed')
    frozen,_=shadow.load_index(shadow.BASE_DATA)
    previous=latest_snapshot()
    base,_=shadow.load_index(previous) if previous else (frozen,None)
    if end<base.Date.max():raise ValueError('Shadow collector cannot truncate the reviewed prefix')
    start=frozen.Date.max()-pd.Timedelta(days=35)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    directory=output/'sources';directory.mkdir()
    frames={};manifest=dict(schema_version=1,status='quarantined',base_snapshot_sha256=shadow.BASE_HASH,
                           requested_start=str(start.date()),requested_end=str(end.date()),sources={},errors=[],
                           collector_sha256=shadow.sha(__file__),created_at=datetime.now(timezone.utc).isoformat(),
                           previous_snapshot_sha256=shadow.sha(previous) if previous else shadow.BASE_HASH,
                           previous_latest_session=str(base.Date.max().date()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(fetch,p,start,end,directory):p for p in ['vci','vnd']}
        for future in as_completed(jobs):
            provider=jobs[future]
            try:
                frames[provider],manifest['sources'][provider]=future.result()
            except Exception as exc:manifest['errors'].append(provider+': '+str(exc))
    canonical=None
    if len(frames)==2:
        canonical,agreement,errors=reconcile(base,frames)
        agreement.to_csv(output/'source_agreement.csv',index=False);manifest['errors'].extend(errors)
    if canonical is not None and not manifest['errors']:
        path=output/'VNINDEX.csv';canonical.to_csv(path,index=False)
        manifest.update(status='accepted',canonical_sha256=shadow.sha(path),rows=len(canonical),latest_session=str(canonical.Date.max().date()),
                        extension_rows=len(canonical)-len(base),policy='Frozen reviewed prefix unchanged; new sessions require VCI/VND date and close agreement <= .011')
    manifest_path=output/'manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    if manifest['errors']:raise ValueError('Snapshot quarantined: '+'; '.join(manifest['errors']))
    provenance=dict(schema_version=1,csv_sha256=manifest['canonical_sha256'],manifest_sha256=shadow.sha(manifest_path),
                    base_snapshot_sha256=shadow.BASE_HASH,collector_sha256=manifest['collector_sha256'],
                    source_provenance='reviewed_frozen_prefix_plus_two_broker_close_agreement_extension',
                    calendar_status='cross-broker session agreement; not independently exchange-certified',
                    adjustment_status='price index points; latest broker history snapshot, not original vintages')
    (output/'VNINDEX.provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status','latest_session','extension_rows','canonical_sha256']},indent=2))
    return manifest


def latest_snapshot(directory=None):
    directory=Path(directory or shadow.ROOT/'data/research/regime_shadow')
    choices=[]
    for path in directory.glob('*/manifest.json'):
        record=json.loads(path.read_text())
        if record.get('status')=='accepted' and (path.parent/'VNINDEX.csv').exists():
            choices.append((record['latest_session'],record['created_at'],path.parent/'VNINDEX.csv'))
    return max(choices,key=lambda x:(x[0],x[1]))[2] if choices else None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--end')
    args=parser.parse_args(argv)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    return collect(args.output_dir or shadow.ROOT/'data/research/regime_shadow'/stamp,args.end)


if __name__=='__main__':main()
