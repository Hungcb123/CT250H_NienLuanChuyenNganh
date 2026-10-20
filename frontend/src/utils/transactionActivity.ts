import { TransactionItem } from '../types';
export interface TransactionActivity {
  id: string; date: string; action: string; detail: string;
  value: number | null; category: 'trade' | 'cash' | 'savings' | 'dividend' | 'other'; status: string;
}
export function transactionActivity(tx: TransactionItem): TransactionActivity[] {
  const entries = tx.entries ?? [];
  const wallet = entries.filter(e => e.accountCode === 'VND_WALLET').reduce((sum, e) => sum + e.amount, 0);
  const assets = entries.filter(e => e.assetTicker && e.assetTicker !== 'VND' && !['TRADING_COSTS', 'EQUITY_CAPITAL'].includes(e.accountCode));
  const base = { date: tx.createdAt, status: tx.status };
  const item = (action: string, detail: string, value: number | null, category: TransactionActivity['category']): TransactionActivity[] =>
    [{ ...base, id: String(tx.id), action, detail, value, category }];
  const quantity = (n: number) => Math.abs(n).toLocaleString('vi-VN', { maximumFractionDigits: 4 });
  const name = (ticker: string) => ticker === 'GOLD_SJC' ? 'Vàng SJC' : ticker;
  if (['TRADE_BUY', 'TRADE_SELL', 'BUY', 'SELL', 'REBALANCE'].includes(tx.type) && assets.length) {
    return assets.filter(e => e.amount !== 0).map((e, index) => ({
      ...base, id: `${tx.id}-${index}`, action: e.amount > 0 ? 'Mua' : 'Bán',
      detail: `${name(e.assetTicker)} · ${quantity(e.amount)}${e.assetTicker.includes('GOLD') ? ' chỉ' : ' cổ phiếu'}${tx.type === 'REBALANCE' ? ' · Tái cân bằng' : ''}`,
      value: e.monetaryValue == null ? null : Math.abs(e.monetaryValue), category: 'trade',
    }));
  }
  if (tx.type === 'CAPITAL_WITHDRAWAL') return item('Rút tiền', 'Rút khỏi danh mục', Math.abs(wallet), 'cash');
  if (tx.type === 'CAPITAL_INJECTION') {
    if (!assets.length) return item('Nạp tiền', 'Nạp vào danh mục', Math.abs(wallet), 'cash');
    return assets.map((e, index) => ({ ...base, id: `${tx.id}-${index}`, action: 'Thêm tài sản',
      detail: `${name(e.assetTicker)} · ${quantity(e.amount)}${e.assetTicker.includes('GOLD') ? ' chỉ' : ' cổ phiếu'}`,
      value: e.monetaryValue == null ? null : Math.abs(e.monetaryValue), category: 'other' }));
  }
  if (tx.type === 'SAVINGS_DEPOSIT') return item('Gửi tiết kiệm', tx.description || 'Mở sổ tiết kiệm', Math.abs(wallet), 'savings');
  if (tx.type === 'SAVINGS_SETTLE') return item('Tất toán tiết kiệm', 'Nhận gốc và lãi về tiền mặt', Math.abs(wallet), 'savings');
  if (tx.type === 'DIVIDEND_CASH') return item('Nhận cổ tức', assets[0]?.assetTicker || tx.description || 'Cổ tức tiền mặt', Math.abs(wallet), 'dividend');
  if (tx.type === 'DIVIDEND_STOCK') return item('Nhận cổ phiếu', assets.map(e => `${name(e.assetTicker)} · ${quantity(e.amount)} cổ phiếu`).join(', '), null, 'dividend');
  if (tx.type.includes('ROLLOVER')) return item('Tái tục tiết kiệm', 'Tiếp tục kỳ hạn tiết kiệm', tx.totalAmount || null, 'savings');
  return item('Giao dịch khác', 'Cập nhật tài sản trong danh mục', tx.totalAmount || null, 'other');
}
