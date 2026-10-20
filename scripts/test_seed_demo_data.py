import unittest
from datetime import date
from decimal import Decimal
from seed_demo_data import Portfolio, Quotes

class DemoPostingTest(unittest.TestCase):
    def test_roundtrip_books_fees_taxes_and_credit_balances(self):
        day=date(2026,10,19)
        p=Portfolio('test',Quotes({'FPT':{day:Decimal('10000')}}),Decimal('1000000'))
        p.inject(day,10_000_000)
        p.trade(day,'FPT',100)
        p.trade(day,'FPT',-100)
        self.assertEqual(p.balances['VND_WALLET'],Decimal('9997000'))
        self.assertEqual(p.balances['TRADING_COSTS'],Decimal('3000'))
        self.assertEqual(p.balances['EQUITY_CAPITAL'],Decimal('-10000000'))
        self.assertEqual(p.balances['ASSET_FPT'],0)
        # A stock movement is valued at the recorded quote; all postings balance in VND.
        for _,_,_,entries,_ in p.transactions:
            total=sum((amount*10000 if account=='ASSET_FPT' else amount for account,amount in entries),Decimal(0))
            self.assertEqual(total,0)
    def test_income_remains_credit_normal(self):
        p=Portfolio('test',Quotes({}),Decimal('1000000'))
        p.post(date(2026,10,19),'DIVIDEND_CASH','demo',[('VND_WALLET',Decimal('1500000')),('INTEREST_INCOME',Decimal('-1500000'))])
        self.assertEqual(p.balances['INTEREST_INCOME'],Decimal('-1500000'))

if __name__=='__main__':unittest.main()
