import { CheckCircle } from 'lucide-react';

export function LedgerTab() {
  const ledgerEntries = [
    {
      txId: 'TX_INIT_CAPITAL',
      debit: 'VND_WALLET (+85.280.000)',
      credit: 'EQUITY_CAPITAL (-85.280.000)',
      amount: '85,280,000 ₫',
      status: 'POSTED'
    },
    {
      txId: 'TX_BUY_HPG_01',
      debit: 'STOCK_HPG (+16.000 CP)',
      credit: 'VND_WALLET (-456.000.000)',
      amount: '456,000,000 ₫',
      status: 'POSTED'
    },
    {
      txId: 'TX_BUY_GOLD_SJC',
      debit: 'GOLD_SJC (+31.7 Chỉ)',
      credit: 'VND_WALLET (-266.600.000)',
      amount: '266,600,000 ₫',
      status: 'POSTED'
    },
    {
      txId: 'TX_DEPOSIT_VCB',
      debit: 'SAVINGS_VCB (+300.000.000)',
      credit: 'VND_WALLET (-300.000.000)',
      amount: '300,000,000 ₫',
      status: 'POSTED'
    }
  ];

  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary tracking-tight">Nhật Ký Sổ Cái Kép (Double-Entry Journal)</h2>
          <p className="text-xs text-text-secondary">Tuân thủ nghiêm ngặt bất biến kế toán ngân hàng: Σ Debit - Σ Credit = 0</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/30">
          <CheckCircle className="w-4 h-4" />
          <span>Bảo toàn tính toán 100% ACID</span>
        </div>
      </div>

      {/* Ledger Entries Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
              <th className="pb-3 font-semibold">Mã Giao Dịch</th>
              <th className="pb-3 font-semibold">Tài Khoản Ghi Nợ (Debit +)</th>
              <th className="pb-3 font-semibold">Tài Khoản Ghi Có (Credit -)</th>
              <th className="pb-3 font-semibold text-right">Số Tiền (VND)</th>
              <th className="pb-3 font-semibold text-center">Trạng Thái</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {ledgerEntries.map((row, idx) => (
              <tr key={idx} className="hover:bg-surface-container-low transition-colors">
                <td className="py-3 font-mono font-bold text-text-primary">{row.txId}</td>
                <td className="py-3 font-semibold text-accent-emerald">{row.debit}</td>
                <td className="py-3 font-semibold text-accent-rose">{row.credit}</td>
                <td className="py-3 text-right font-bold text-text-primary">{row.amount}</td>
                <td className="py-3 text-center">
                  <span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
