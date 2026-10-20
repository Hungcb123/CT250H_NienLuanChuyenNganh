"""Download separate cross-broker index-close snapshot; no constituent backfill.

Consensus only where VCI and VND both report the same close. Disagreements and
pre-launch dates remain absent. Does not modify the reviewed VNINDEX snapshot.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import pandas as pd
import prepare_regime_data as source

SYMBOLS=['VN30','VNMID','VNSML']
ROOT=Path(__file__).resolve().parent


def close_response(payload,provider,provider_symbol,start,end):
    if provider=='vci':
        if not isinstance(payload,list) or len(payload)!=1 or payload[0].get('symbol')!=provider_symbol:
            raise ValueError('Wrong VCI close symbol')
        payload=payload[0]
    if not isinstance(payload,dict) or not all(k in payload for k in ['t','c']):raise ValueError('Missing close/date arrays')
    frame=pd.DataFrame({'epoch':payload['t'],'Close':payload['c']})
    frame['Date']=pd.to_datetime(pd.to_numeric(frame.epoch),unit='s',utc=True).dt.tz_convert('Asia/Ho_Chi_Minh').dt.tz_localize(None).dt.normalize()
    frame=frame.loc[frame.Date.between(pd.Timestamp(start),pd.Timestamp(end)),['Date','Close']].sort_values('Date').reset_index(drop=True)
    frame['Close']=pd.to_numeric(frame.Close)
    if frame.empty or frame.Date.duplicated().any() or (frame.Date.dt.dayofweek>=5).any() or not frame.Close.map(lambda x:pd.notna(x) and float('-inf')<x<float('inf') and x>0).all():
        raise ValueError('Invalid close-only source data')
    return frame


def download(provider,symbol,start,end,output):
    alias={'VN30':'VN30','VNMID':'VNMIDCAP','VNSML':'VNSMALLCAP'}[symbol] if provider=='vci' else symbol
    body=None
    if provider=='vci':
        params=None
        body={'timeFrame':'ONE_DAY','symbols':[alias],
              'to':int((pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize('Asia/Ho_Chi_Minh').timestamp()),
              'countBack':int((pd.Timestamp(end)-pd.Timestamp(start)).days*5/7)+366}
        url=source.VCI_URL
    else:
        params={'resolution':'D','symbol':symbol,'from':int(pd.Timestamp(start).tz_localize('Asia/Ho_Chi_Minh').timestamp()),
                'to':int((pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize('Asia/Ho_Chi_Minh').timestamp())}
        url=source.VND_URL
    request=urllib.request.Request(url+('?' + urllib.parse.urlencode(params) if params else ''),
                                  data=json.dumps(body).encode() if body else None,
                                  headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:raw=response.read()
    path=output/f'{provider}_{symbol}.json';path.write_bytes(raw)
    payload=json.loads(raw)
    frame=close_response(payload,provider,alias,start,end)
    frame.to_csv(output/f'{provider}_{symbol}.csv',index=False)
    item=payload[0] if provider=='vci' else payload
    invalid_unused={field:sum(float(v)<=0 for v in item.get(field,[])) for field in ['o','h','l']}
    metadata=dict(provider=provider,canonical_symbol=symbol,provider_symbol=alias,url=url,params=params,body=body,
                  response='sources/'+path.name,response_sha256=hashlib.sha256(raw).hexdigest(),
                  downloaded_at=datetime.now(timezone.utc).isoformat(),rows=len(frame),
                  start=str(frame.Date.min().date()),end=str(frame.Date.max().date()),
                  validation='Close/date only; OHLC/volume fields excluded from all derived files/features',
                  invalid_nonpositive_unused_fields=invalid_unused)
    return frame,metadata


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--start',default='2010-01-01')
    parser.add_argument('--end',default='2026-10-01')
    args=parser.parse_args(argv)
    if pd.Timestamp(args.end)>=pd.Timestamp.now(tz='Asia/Ho_Chi_Minh').tz_localize(None).normalize():raise ValueError('Only completed dates')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    directory=args.output_dir/'sources';directory.mkdir()
    frames={};manifest=dict(requested_start=args.start,requested_end=args.end,sources={},errors={},canonical={})
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(download,p,s,args.start,args.end,directory):(p,s) for s in SYMBOLS for p in ['vci','vnd']}
        for task in as_completed(jobs):
            provider,symbol=jobs[task];key=f'{provider}_{symbol}'
            try:
                frame,metadata=task.result();frames[key]=frame;manifest['sources'][key]=metadata
                print(key,len(frame),flush=True)
            except Exception as exc:manifest['errors'][key]=str(exc);print(key,'ERROR',exc,flush=True)
    for symbol in SYMBOLS:
        if any(f'{p}_{symbol}' not in frames for p in ['vci','vnd']):continue
        a,b=[frames[f'{p}_{symbol}'][['Date','Close']] for p in ['vci','vnd']]
        joined=a.merge(b,on='Date',how='outer',suffixes=('_vci','_vnd'),validate='one_to_one').sort_values('Date')
        accepted=(joined.Close_vci-joined.Close_vnd).abs()<=.011
        # Use midpoint of agreeing reports; no filling across disagreement or launch dates.
        canonical=joined.loc[accepted,['Date']].copy();canonical['Close']=(joined.loc[accepted,'Close_vci']+joined.loc[accepted,'Close_vnd'])/2
        path=args.output_dir/f'{symbol}.csv';canonical.to_csv(path,index=False)
        joined['accepted']=accepted;joined.to_csv(args.output_dir/f'{symbol}_agreement.csv',index=False)
        manifest['canonical'][symbol]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(canonical),
                                           start=str(canonical.Date.min().date()),end=str(canonical.Date.max().date()),
                                           unresolved_or_single_source_rows=int((~accepted).sum()),policy='two-broker close agreement <= .011; no price fill')
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Snapshot: '+str(args.output_dir.resolve()))
    return manifest


if __name__=='__main__':main()
