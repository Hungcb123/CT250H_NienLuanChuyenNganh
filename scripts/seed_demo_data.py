#!/usr/bin/env python3
"""Add isolated, replayed demo portfolios. Never resets or changes existing users.

Uses repository CSV closes and existing DB quotes, not synthetic market history.
Demo SJC valuations use a fixed assumed quote (no SJC history is fabricated).
Requires Python bcrypt and local PostgreSQL Docker container.
"""
import argparse
import bisect
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path
import subprocess
import sys
import bcrypt

ROOT = Path(__file__).resolve().parents[1]
D = Decimal
MARKER = 'DEMO_DATA_V1'
PASSWORD = 'Demo@123456'
STOCKS = ['FPT', 'HPG', 'TCB', 'VCB', 'MBB', 'ACB', 'VNM', 'SSI', 'MWG', 'GAS', 'CTG', 'VPB']
SCENARIOS = [
    ('demo_balanced', 'BALANCED', 50, 5, (.35, .35, .20, .10), (.35, .35, .20, .10)),
    ('demo_growth', 'GROWTH', 85, 2, (.72, .08, .10, .10), (.45, .20, .20, .15)),
    ('demo_defensive', 'CONSERVATIVE', 20, 9, (.15, .45, .30, .10), (.20, .40, .30, .10)),
]


def sql(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def rounded(value):
    return D(value).quantize(D('.0001'), rounding=ROUND_HALF_EVEN)


def psql(container, database, statement=None, script=None):
    command = ['docker', 'exec', '-i', container, 'psql', '-X', '-U', 'postgres', '-d', database, '-v', 'ON_ERROR_STOP=1', '-At']
    if statement is not None:
        command += ['-c', statement]
    result = subprocess.run(command, input=script, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


class Quotes:
    def __init__(self, values):
        self.values = values
        self.days = {ticker: sorted(rows) for ticker, rows in values.items()}

    def at(self, ticker, day):
        days = self.days.get(ticker, [])
        i = bisect.bisect_right(days, day) - 1
        if i < 0:
            raise ValueError(f'No quote at or before {day} for {ticker}')
        return self.values[ticker][days[i]]


@dataclass
class Portfolio:
    name: str
    quotes: Quotes
    gold_price: Decimal
    balances: dict = field(default_factory=dict)
    transactions: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    deposits: list = field(default_factory=list)
    serial: int = 0

    def post(self, day, kind, description, entries):
        self.serial += 1
        for account, amount in entries:
            self.balances[account] = rounded(self.balances.get(account, D(0)) + amount)
        assert self.balances.get('VND_WALLET', 0) >= 0, 'Demo wallet must never go negative'
        assert all(v >= 0 for k, v in self.balances.items() if k.startswith('ASSET_')), 'No short selling'
        self.transactions.append((day, kind, description, entries, self.serial))

    def inject(self, day, amount):
        amount = D(amount)
        self.post(day, 'CAPITAL_INJECTION', 'Nạp vốn kiểm thử', [('VND_WALLET', amount), ('EQUITY_CAPITAL', -amount)])

    def trade(self, day, ticker, quantity):
        if not quantity:
            return
        price = self.gold_price if ticker == 'GOLD_SJC' else self.quotes.at(ticker, day)
        qty = D(quantity)
        gross = (abs(qty) * price).quantize(D(1), rounding=ROUND_HALF_EVEN)
        fee = (gross * D('.001')).quantize(D(1), rounding=ROUND_HALF_EVEN)
        tax = fee if qty < 0 else D(0)
        cash = -gross-fee if qty > 0 else gross-fee-tax
        if cash < 0 and -cash > self.balances.get('VND_WALLET', 0):
            return
        self.post(day, 'TRADE_BUY' if qty > 0 else 'TRADE_SELL',
                  f'{"MUA" if qty > 0 else "BÁN"} {abs(qty)} {ticker} @ {price} ₫; phí {fee}, thuế {tax}',
                  [('ASSET_' + ticker, qty), ('VND_WALLET', cash), ('TRADING_COSTS', fee+tax)])

    def values(self, day):
        stock = sum((qty*self.quotes.at(account[6:], day) for account, qty in self.balances.items()
                     if account.startswith('ASSET_') and account != 'ASSET_GOLD_SJC'), D(0))
        gold = self.balances.get('ASSET_GOLD_SJC', D(0))*self.gold_price
        savings = sum((amount for account, amount in self.balances.items() if account.startswith('SAVINGS_')), D(0))
        cash = self.balances.get('VND_WALLET', D(0))
        return stock+gold+savings+cash, stock, gold, savings, cash

    def open_savings(self, day, principal, term, bank, settled=False):
        principal = D(principal)
        account = f'SAVINGS_DEMO_{len(self.deposits)+1:02d}'
        rate = D('4.8') + D(len(self.deposits) % 5)*D('.35')
        maturity = add_months(day, term)
        self.post(day, 'SAVINGS_DEPOSIT', f'Mở sổ {bank}, {term} tháng, {rate}%/năm',
                  [(account, principal), ('VND_WALLET', -principal)])
        self.deposits.append(dict(account=account, bank=bank, principal=principal, rate=rate,
                                  term=term, start=day, maturity=maturity, settled=settled))

    def settle_due(self, day):
        for deposit in self.deposits:
            account = deposit['account']
            if deposit['settled'] and deposit['maturity'] <= day and self.balances.get(account, 0):
                principal = deposit['principal']
                interest = rounded(principal*deposit['rate']/100*D((deposit['maturity']-deposit['start']).days)/365)
                self.post(day, 'SAVINGS_SETTLEMENT', f'Tất toán sổ {deposit["bank"]}',
                          [(account, -principal), ('VND_WALLET', principal+interest), ('INTEREST_INCOME', -interest)])

    def rebalance(self, day, weights, adjust_savings=False):
        nav, _, _, savings, _ = self.values(day)
        desired = {}
        for ticker in STOCKS:
            price = self.quotes.at(ticker, day)
            desired[ticker] = int(nav*D(str(weights[0]))/len(STOCKS)/price/100)*100
        desired['GOLD_SJC'] = int(nav*D(str(weights[1]))/self.gold_price)
        # Sell first, so purchases are funded; round stock quantities to 100-share lots.
        for ticker, target in desired.items():
            delta = target-int(self.balances.get('ASSET_'+ticker, 0))
            if delta < 0:
                self.trade(day, ticker, delta)
        for ticker, target in desired.items():
            delta = target-int(self.balances.get('ASSET_'+ticker, 0))
            if delta > 0:
                self.trade(day, ticker, delta)
        extra = (nav*D(str(weights[2]))-savings).quantize(D('1000000'))
        if adjust_savings and extra > D('1000000') and self.balances['VND_WALLET'] > extra:
            self.open_savings(day, extra, 12, 'Vietcombank')


def add_months(day, months):
    import calendar
    month = day.month-1+months
    year = day.year+month//12
    month = month % 12+1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def build_portfolio(name, quotes, gold, weights, today, history_days=400):
    portfolio = Portfolio(name, quotes, gold)
    start = today-timedelta(days=history_days)
    days = [start+timedelta(days=i) for i in range(history_days+1) if (start+timedelta(days=i)).weekday() < 5 or start+timedelta(days=i) == today]
    portfolio.inject(days[0], 2_000_000_000)
    for n, bank in enumerate(['Vietcombank', 'BIDV', 'Techcombank', 'MB Bank']):
        principal = D(2_000_000_000)*D(str(weights[2]))/4
        portfolio.open_savings(days[0], principal, 3 if n == 0 else 18, bank, settled=n == 0)
    portfolio.rebalance(days[0], weights)
    for i, day in enumerate(days):
        portfolio.settle_due(day)
        if i and i % 21 == 0:
            portfolio.inject(day, 15_000_000)
            portfolio.rebalance(day, weights)
        if i and i % 7 == 0:
            ticker = STOCKS[(i//7) % len(STOCKS)]
            current = portfolio.balances.get('ASSET_'+ticker, 0)
            portfolio.trade(day, ticker, -100 if i % 14 == 0 and current >= 200 else 100)
        if i and i % 42 == 0:
            # Cash dividends are income, not external contributions. Use income contra-account.
            dividend = D(1_500_000 + i*1_000)
            portfolio.post(day, 'DIVIDEND_CASH', 'Cổ tức tiền mặt kiểm thử sau thuế',
                           [('VND_WALLET', dividend), ('INTEREST_INCOME', -dividend)])
        if i == len(days)-1:
            portfolio.rebalance(day, weights, adjust_savings=True)
        portfolio.snapshots.append((day, *map(rounded, portfolio.values(day)), quotes.at('VNINDEX', day)))
    return portfolio


def account_ticker(account):
    return account[6:] if account.startswith('ASSET_') else 'VND'


def portfolio_sql(portfolio, profile, score, risk_lambda, targets, today, password_hash):
    name = portfolio.name
    out = [f'DO $seed$ DECLARE uid BIGINT; txid BIGINT; BEGIN',
           f'IF EXISTS(SELECT 1 FROM users WHERE username={sql(name)}) THEN RAISE NOTICE \'Skip existing user %\', {sql(name)}; RETURN; END IF;',
           f'INSERT INTO users(username,email,password_hash,risk_score,risk_aversion_lambda,risk_profile,created_at) VALUES({sql(name)},{sql(name+"@demo.equifolio.test")},{sql(password_hash)},{score},{risk_lambda},{sql(profile)},{sql(portfolio.snapshots[0][0])}) RETURNING id INTO uid;']
    for asset_class, weight in zip(['STOCK', 'GOLD', 'SAVINGS', 'CASH'], targets):
        out.append(f'INSERT INTO portfolio_targets(user_id,asset_class,target_weight) VALUES(uid,{sql(asset_class)},{weight});')
    for account, balance in portfolio.balances.items():
        out.append(f'INSERT INTO accounts(user_id,account_code,asset_type,balance,created_at) VALUES(uid,{sql(account)},{sql(account_ticker(account))},{sql(balance)},{sql(portfolio.snapshots[0][0])});')
    for day, kind, description, entries, serial in portfolio.transactions:
        # Ordered timestamps ensure cost-basis replay matches the in-memory event order.
        timestamp = f'{day} 09:{serial//60:02d}:{serial%60:02d}+07'
        code = f'{MARKER}_{name}_{serial:04d}'
        out.append(f'INSERT INTO transactions(transaction_code,user_id,type,status,description,created_at) VALUES({sql(code)},uid,{sql(kind)},\'POSTED\',{sql("[DEMO] "+description)},{sql(timestamp)}) RETURNING id INTO txid;')
        for account, amount in entries:
            monetary = amount
            if account.startswith('ASSET_'):
                ticker = account[6:]
                price = portfolio.gold_price if ticker == 'GOLD_SJC' else portfolio.quotes.at(ticker, day)
                monetary = (amount*price).quantize(D(1), rounding=ROUND_HALF_EVEN)
            out.append(f'INSERT INTO entries(transaction_id,account_id,amount,monetary_value,created_at) SELECT txid,id,{sql(amount)},{sql(monetary)},{sql(timestamp)} FROM accounts WHERE user_id=uid AND account_code={sql(account)};')
    for row in portfolio.snapshots:
        day, nav, stock, gold, savings, cash, benchmark = row
        out.append('INSERT INTO portfolio_snapshots(user_id,snapshot_date,total_nav,stock_value,gold_value,savings_value,cash_value,vnindex_value,snapshot_source) VALUES(uid,' + ','.join(map(sql, [day, nav, stock, gold, savings, cash, benchmark, 'DEMO'])) + ');')
    for dep in portfolio.deposits:
        status = 'SETTLED' if dep.get('closed', False) or (dep['settled'] and dep['maturity'] <= today) else 'ACTIVE'
        days = max(0, (min(today, dep['maturity'])-dep['start']).days)
        accrued = dep.get('settlement_interest', rounded(dep['principal']*dep['rate']/100*D(days)/365))
        values = [dep['bank'], dep['principal'], dep['rate'], dep['term'], dep['start'], dep['maturity'], status != 'SETTLED', accrued, status, dep['start']]
        out.append('INSERT INTO savings_deposits(user_id,account_id,bank_name,principal_amount,interest_rate,term_months,start_date,maturity_date,auto_rollover,accrued_interest,status,created_at) SELECT uid,id,' + ','.join(map(sql, values)) + f' FROM accounts WHERE user_id=uid AND account_code={sql(dep["account"])};')
    for n, title in enumerate(['Quỹ dự phòng', 'Mua nhà', 'Học phí', 'Nghỉ hưu', 'Du lịch', 'Mua xe']):
        target = [100_000_000, 2_000_000_000, 300_000_000, 5_000_000_000, 50_000_000, 800_000_000][n]
        out.append('INSERT INTO financial_goals(user_id,title,target_amount,allocated_amount,monthly_contribution,annual_rate,target_date) VALUES(uid,' + ','.join(map(sql, [f'[Demo] {title}', target, D(target)*D('.25'), D(target)/100, D('5.5'), add_months(today, [6, 60, 24, 180, 9, 36][n])])) + ');')
    topics = ['Sổ cái kép', 'Phân bổ tài sản SAA', 'Tái cân bằng danh mục', 'Lãi kép', 'Rủi ro cổ phiếu', 'Mục tiêu tích lũy', 'Đọc chỉ số Sharpe', 'Dữ liệu mô phỏng']
    for n, topic in enumerate(topics):
        content = f'{topic}: Đây là tài liệu kiểm thử của {name}. Danh mục demo mô phỏng giao dịch, nạp vốn, tiết kiệm và cổ tức. Lợi suất quá khứ trong bộ dữ liệu mẫu không chứng minh hiệu quả đầu tư. Kiểm tra mục tiêu phân bổ và dòng tiền trước khi xác nhận kế hoạch.'
        meta = f"jsonb_build_object('owner',uid,'title',{sql(topic)},'source','DEMO_DATA_V1','chunk',0,'dataset','DEMO')"
        out.append(f"INSERT INTO vector_store(content,metadata,search_tsv) VALUES({sql(content)},{meta},to_tsvector('simple',unaccent({sql(content)})));")
    out.append('END $seed$;')
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', default='equifolio-postgres')
    parser.add_argument('--database', default='equifolio')
    parser.add_argument('--extended', action='store_true', help='Create three separate *_extended demo accounts with 800 calendar days of history.')
    parser.add_argument('--apply', action='store_true', help='Atomically insert into local DB. Existing users/quotes are preserved.')
    parser.add_argument('--output', type=Path, help='Optional reviewable SQL output')
    args = parser.parse_args()
    today = datetime.now().astimezone().date()
    cutoff = today-timedelta(days=900)
    values = {}
    imported = []
    allowed = [p.stem for p in (ROOT/'ml/data/raw').glob('*.csv') if p.stem not in ('GC',)]
    metadata = json.loads((ROOT/'ml/data/market_metadata.json').read_text())
    for ticker in sorted(allowed):
        rows = {}
        with (ROOT/'ml/data/raw'/f'{ticker}.csv').open() as source:
            for row in csv.DictReader(source):
                day = date.fromisoformat(row['Date'][:10])
                price = D(row['Close'])
                if cutoff <= day <= today and price.is_finite() and price > 0:
                    rows[day] = rounded(price)
        if rows:
            values[ticker] = rows
            imported.extend((ticker, day, price) for day, price in rows.items())
    db_rows = psql(args.container, args.database, "SELECT coalesce(json_agg(row_to_json(q)), '[]') FROM (SELECT ticker,trade_date,price FROM market_prices WHERE trade_date>="+sql(cutoff)+" AND trade_date<="+sql(today)+") q")
    for row in json.loads(db_rows):
        if row['ticker'] in values:
            values[row['ticker']][date.fromisoformat(row['trade_date'])] = D(str(row['price']))
    gold = D(psql(args.container, args.database, "SELECT price FROM market_prices WHERE ticker='GOLD_SJC' ORDER BY trade_date DESC LIMIT 1"))
    quotes = Quotes(values)
    statements = ['BEGIN;', "SELECT pg_advisory_xact_lock(hashtext('equifolio_demo_seed_v1'));", "SET LOCAL lock_timeout='10s';"]
    for ticker in values:
        asset_class = 'INDEX' if ticker == 'VNINDEX' else 'STOCK'
        info = metadata.get(ticker, {})
        name = (info.get('name') or info.get('longName') or ticker)[:100] if isinstance(info, dict) else ticker
        statements.append(f'INSERT INTO assets(ticker,name,asset_class) VALUES({sql(ticker)},{sql(name)},{sql(asset_class)}) ON CONFLICT(ticker) DO NOTHING;')
    for start in range(0, len(imported), 500):
        statements.append('INSERT INTO market_prices(ticker,trade_date,price) VALUES '+','.join('('+','.join(map(sql, row))+')' for row in imported[start:start+500])+' ON CONFLICT(ticker,trade_date) DO NOTHING;')
    password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
    summary = []
    for name, profile, score, risk_lambda, weights, targets in SCENARIOS:
        if args.extended:
            name += '_extended'
        portfolio = build_portfolio(name, quotes, gold, weights, today, history_days=800 if args.extended else 400)
        statements.append(portfolio_sql(portfolio, profile, score, risk_lambda, targets, today, password_hash))
        summary.append(dict(username=name, transactions=len(portfolio.transactions), snapshots=len(portfolio.snapshots), savings=len(portfolio.deposits), goals=6, documents=8, nav=str(portfolio.snapshots[-1][1])))
    statements.append('COMMIT;')
    script = '\n'.join(statements)
    if args.output:
        args.output.write_text(script, encoding='utf-8')
    if args.apply:
        output = psql(args.container, args.database, script=script)
        print('Applied demo seed atomically. Existing users and quotes were preserved.')
    print(json.dumps(dict(mode='applied' if args.apply else 'preview', marketRowsConsidered=len(imported), accounts=summary), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, AssertionError) as error:
        print(f'Seed failed: {error}', file=sys.stderr)
        sys.exit(1)
