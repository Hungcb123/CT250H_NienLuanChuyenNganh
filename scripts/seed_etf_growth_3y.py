#!/usr/bin/env python3
"""Three-year GROWTH demo: equity sleeve holds only E1VFVN30.

ETF and VNINDEX prices are DNSE observations. SJC uses a declared constant
assumption; savings use a declared fixed 5.5% annual simple rate. This is a
simulation, not an actual investment record or a validated strategy backtest.
"""
import argparse
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_HALF_EVEN
import hashlib,json,sys
from pathlib import Path
from zoneinfo import ZoneInfo
import bcrypt
import pandas as pd
from seed_demo_data import Portfolio,Quotes,portfolio_sql,psql,sql,rounded,PASSWORD,ROOT
sys.path.insert(0,str(ROOT/'ml'))
from regime_live_data import dnse_bars,completed_session
D=Decimal
NAME='demo_etf_growth_3y'
WEIGHTS=tuple(map(D,['.60','.20','.15','.05']))

class EtfGrowthPortfolio(Portfolio):
    def open_quarterly_savings(self,day,principal):
        from seed_demo_data import add_months
        account=f'SAVINGS_ETF_{len(self.deposits)+1:02d}'
        self.post(day,'SAVINGS_DEPOSIT','Tiết kiệm mô phỏng 3 tháng, lãi suất giả định 5.5%/năm',[(account,principal),('VND_WALLET',-principal)])
        self.deposits.append(dict(account=account,bank='Vietcombank (mô phỏng)',principal=principal,rate=D('5.5'),term=3,start=day,maturity=add_months(day,3),settled=True))
    def settle_early_for_final_allocation(self,day):
        for deposit in self.deposits:
            principal=self.balances.get(deposit['account'],D(0))
            if principal<=0:continue
            interest=rounded(principal*D('.003')*D((day-deposit['start']).days)/365)
            self.post(day,'SAVINGS_SETTLEMENT','Tất toán trước hạn mô phỏng, lãi suất giả định 0.3%/năm để tái cân bằng cuối kỳ',
                      [(deposit['account'],-principal),('VND_WALLET',principal+interest),('INTEREST_INCOME',-interest)])
            deposit['closed']=True;deposit['settlement_interest']=interest
    def allocate(self,day):
        nav,_,_,savings,_=self.values(day)
        desired={'E1VFVN30':int(nav*WEIGHTS[0]/self.quotes.at('E1VFVN30',day)/100)*100,
                 'GOLD_SJC':int(nav*WEIGHTS[1]/self.gold_price)}
        for side in (-1,1):
            for ticker,target in desired.items():
                change=target-int(self.balances.get('ASSET_'+ticker,0))
                if change*side>0:self.trade(day,ticker,change)
        if savings==0:
            principal=(nav*WEIGHTS[2]).quantize(D('1'),rounding=ROUND_HALF_EVEN)
            if self.balances.get('VND_WALLET',0)>=principal:self.open_quarterly_savings(day,principal)

def sources(directory,start,end):
    directory.mkdir(parents=True,exist_ok=True)
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest['start']!=str(start) or manifest['end']!=str(end):raise ValueError('Cache date range mismatch; use another --data-dir')
        for symbol in ('E1VFVN30','VNINDEX'):
            if hashlib.sha256((directory/(symbol+'.csv')).read_bytes()).hexdigest()!=manifest['files'][symbol]:raise ValueError('Source checksum mismatch')
        return {s:pd.read_csv(directory/(s+'.csv'),parse_dates=['Date']) for s in ('E1VFVN30','VNINDEX')},manifest
    frames={};receipts=[];hashes={}
    for symbol in ('E1VFVN30','VNINDEX'):
        pieces=[];begin=start
        while begin<=end:
            finish=min(begin+timedelta(days=89),end)
            frame,receipt=dnse_bars(symbol,begin,finish)
            pieces.append(frame);receipts.append(receipt);begin=finish+timedelta(days=1)
        frame=pd.concat(pieces,ignore_index=True).sort_values('Date').reset_index(drop=True)
        if frame.Date.duplicated().any():raise ValueError('Duplicate source session')
        frame.to_csv(directory/(symbol+'.csv'),index=False)
        hashes[symbol]=hashlib.sha256((directory/(symbol+'.csv')).read_bytes()).hexdigest();frames[symbol]=frame
    calendars={symbol:set(frame.Date.dt.strftime('%Y-%m-%d')) for symbol,frame in frames.items()}
    excluded=sorted(calendars['E1VFVN30'] ^ calendars['VNINDEX'])
    manifest=dict(start=str(start),end=str(end),provider='DNSE',files=hashes,requests=receipts,excluded_noncommon_sessions=excluded,
                  etf_price_unit='VND (DNSE stock OHLC multiplied by 1000)',returns='Unadjusted quoted closes; no invented dividends')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    return frames,manifest

def build(frames,gold):
    quotes=Quotes({s:{row.Date.date():D(str(row.Close)) for row in f.itertuples()} for s,f in frames.items()})
    days=sorted({row.date() for row in frames['VNINDEX'].Date} & {row.date() for row in frames['E1VFVN30'].Date})
    if len(days)<700:raise ValueError('Insufficient common observed sessions for three-year demo')
    p=EtfGrowthPortfolio(NAME,quotes,gold)
    p.inject(days[0],10_000_000_000)
    previous_month=None
    for i,day in enumerate(days):
        p.settle_due(day)
        if i>0 and day==days[-1]:p.settle_early_for_final_allocation(day)
        month=(day.year,day.month)
        if previous_month is not None and month!=previous_month:p.inject(day,50_000_000)
        if i==0 or month!=previous_month or day==days[-1] or not any(p.balances.get(d['account'],0)>0 for d in p.deposits):p.allocate(day)
        p.snapshots.append((day,*map(rounded,p.values(day)),quotes.at('VNINDEX',day)))
        previous_month=month
    assert not any(a.startswith('ASSET_') and a not in ('ASSET_E1VFVN30','ASSET_GOLD_SJC') for a in p.balances)
    assert all(p.balances.get(d['account'],0)==0 for d in p.deposits if d['maturity']<=days[-1])
    return p

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--container',default='equifolio-postgres');parser.add_argument('--database',default='equifolio')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'ml/data/live/demo_etf_growth_3y')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    today=completed_session(datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')))
    start=today.replace(year=today.year-3)
    frames,manifest=sources(args.data_dir,start,today)
    gold=D(psql(args.container,args.database,"SELECT price FROM market_prices WHERE ticker='GOLD_SJC' ORDER BY trade_date DESC LIMIT 1"))
    p=build(frames,gold)
    statements=['BEGIN;',"SELECT pg_advisory_xact_lock(hashtext('equifolio_demo_seed_v1'));","SET LOCAL lock_timeout='10s';"]
    # Actual observed market quotes only; existing vintages are never overwritten.
    for symbol,frame in frames.items():
        rows=[(symbol,row.Date.date(),D(str(row.Close)))for row in frame.itertuples()]
        for i in range(0,len(rows),300):
            statements.append('INSERT INTO market_prices(ticker,trade_date,price) VALUES '+','.join('('+','.join(map(sql,row))+')'for row in rows[i:i+300])+' ON CONFLICT(ticker,trade_date) DO NOTHING;')
    statements.append(portfolio_sql(p,'GROWTH',85,D('2.35'),WEIGHTS,today,bcrypt.hashpw(PASSWORD.encode(),bcrypt.gensalt(rounds=10)).decode()))
    statements.append(f"INSERT INTO equity_investment_preferences(user_id,mode,etf_weight) SELECT id,'ETF',1 FROM users WHERE username={sql(NAME)} AND email={sql(NAME+'@demo.equifolio.test')} ON CONFLICT(user_id) DO NOTHING;")
    statements.append(f"INSERT INTO allocation_preferences(user_id,mode,horizon_sessions) SELECT id,'SAA',20 FROM users WHERE username={sql(NAME)} AND email={sql(NAME+'@demo.equifolio.test')} ON CONFLICT(user_id) DO NOTHING;")
    statements.append('COMMIT;')
    script='\n'.join(statements)
    if args.output:args.output.write_text(script)
    if args.apply:psql(args.container,args.database,script=script)
    nav,stock,gold_value,savings,cash=p.snapshots[-1][1:6]
    summary=dict(mode='applied' if args.apply else 'preview',username=NAME,start=str(p.snapshots[0][0]),end=str(p.snapshots[-1][0]),snapshots=len(p.snapshots),transactions=len(p.transactions),targets=dict(zip(['ETF','GOLD','SAVINGS','CASH'],map(str,WEIGHTS))),actual_weights={k:float(v/nav) for k,v in zip(['ETF','GOLD','SAVINGS','CASH'],[stock,gold_value,savings,cash])},assumptions=dict(gold_constant_vnd=str(gold),savings_rate_percent='5.5',early_settlement_rate_percent='0.3',ETF_source='DNSE unadjusted closes',simulated=True),source_manifest=str(args.data_dir/'manifest.json'))
    (args.data_dir/'portfolio_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
