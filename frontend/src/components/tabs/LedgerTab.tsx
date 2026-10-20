import { useState, useEffect, useRef } from 'react';
import { PlusCircle, ArrowUpRight, X, Coins } from 'lucide-react';
import { TransactionItem, EquityInjectionPayload, DividendPayload } from '../../types';
import { getTransactions, recordEquityInjection, recordDividend, getAvailableCashBalance, recordCashWithdrawal } from '../../services/api';
import { transactionActivity } from '../../utils/transactionActivity';
import { formatVND } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

interface LedgerTabProps {
  onRefresh?: () => void;
}

const ASSET_PRICE_MAP: Record<string, { name: string; price: number; type: string; unit: string }> = {
  VND: { name: 'Tiền mặt Việt Nam Đồng', price: 1, type: 'CASH', unit: '₫' },
  HPG: { name: 'Cổ phiếu Tập đoàn Hòa Phát', price: 28500, type: 'STOCK', unit: 'CP' },
  TCB: { name: 'Cổ phiếu Techcombank', price: 24200, type: 'STOCK', unit: 'CP' },
  FPT: { name: 'Cổ phiếu CTCP FPT', price: 134000, type: 'STOCK', unit: 'CP' },
  VNM: { name: 'Cổ phiếu Vinamilk', price: 68000, type: 'STOCK', unit: 'CP' },
  GOLD_SJC: { name: 'Vàng miếng SJC 999.9', price: 8950000, type: 'GOLD', unit: 'Chỉ' }
};

export function LedgerTab({ onRefresh }: LedgerTabProps) {
  const toast = useToast();
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Modal form state: Capital Injection
  const [selectedTicker, setSelectedTicker] = useState('VND');
  const [amount, setAmount] = useState<string>('50000000');
  const [entryPrice, setEntryPrice] = useState<number>(1);
  const [description, setDescription] = useState('');

  // Modal form state: Corporate Action / Dividend
  const [showDividendModal, setShowDividendModal] = useState(false);
  const [dividendSubmitting, setDividendSubmitting] = useState(false);
  const [dividendTicker, setDividendTicker] = useState('HPG');
  const [dividendType, setDividendType] = useState<'CASH' | 'STOCK'>('CASH');
  const [dividendTotalCash, setDividendTotalCash] = useState('10000000'); // VND
  const [dividendStockQty, setDividendStockQty] = useState('1000'); // Shares

  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const withdrawRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!withdrawOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, [withdrawOpen]);

  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawNote, setWithdrawNote] = useState('');
  const [withdrawError, setWithdrawError] = useState('');
  const [withdrawing, setWithdrawing] = useState(false);
  const [cashBalance, setCashBalance] = useState<number | null>(null);
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const activities = transactions.flatMap(transactionActivity).filter(row => filter === 'all' || row.category === filter);
  const pages = Math.max(1, Math.ceil(activities.length / 15));
  const currentPage = Math.min(page, pages);
  const visibleActivities = activities.slice((currentPage - 1) * 15, currentPage * 15);
  const loadBalance = async () => {
    try { setCashBalance(await getAvailableCashBalance()); }
    catch { setCashBalance(null); }
  };
  const handleWithdraw = async (event: React.FormEvent) => {
    event.preventDefault();
    const value = Number(withdrawAmount);
    if (!Number.isSafeInteger(value) || value <= 0 || cashBalance == null || value > cashBalance) {
      setWithdrawError('Nhập số tiền nguyên dương trong số dư khả dụng.');
      return;
    }
    setWithdrawing(true); setWithdrawError('');
    try {
      await recordCashWithdrawal({ amount: value, description: withdrawNote.trim() || undefined });
      setWithdrawOpen(false); setWithdrawAmount(''); setWithdrawNote('');
      await Promise.all([fetchTransactions(), loadBalance()]);
      onRefresh?.();
      toast.success('Đã ghi nhận tiền rút khỏi danh mục.', 'Rút tiền');
    } catch (error) {
      setWithdrawError(error instanceof Error ? error.message : 'Không thể rút tiền. Vui lòng thử lại.');
    } finally { setWithdrawing(false); }
  };

  const fetchTransactions = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await getTransactions();
      setTransactions(data);
    } catch (e) {
      setLoadError('Không tải được lịch sử. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
    loadBalance();
  }, []);

  const handleTickerChange = (ticker: string) => {
    setSelectedTicker(ticker);
    const info = ASSET_PRICE_MAP[ticker];
    if (info) {
      setEntryPrice(info.price);
      if (ticker === 'VND') setAmount('50000000');
      else if (info.type === 'STOCK') setAmount('1000');
      else if (info.type === 'GOLD') setAmount('5');
    }
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      toast.warning("Vui lòng nhập số lượng tài sản hợp lệ (> 0)", "Dữ liệu không hợp lệ");
      return;
    }

    setSubmitting(true);
    try {
      const payload: EquityInjectionPayload = {
        ticker: selectedTicker,
        amount: numAmount,
        entryPrice: entryPrice > 0 ? entryPrice : undefined,
        description: description.trim() || `Khai báo nạp tài sản: ${selectedTicker}`
      };
      await recordEquityInjection(payload);
      setShowModal(false);
      setDescription('');
      await Promise.all([fetchTransactions(), loadBalance()]);
      onRefresh?.();
      toast.success(
        "Đã thêm tài sản vào danh mục.",
        "Ghi sổ thành công"
      );
    } catch (err: any) {
      toast.error("Lỗi khai báo tài sản: " + (err.message || err), "Thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDividendSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setDividendSubmitting(true);
    try {
      const val = dividendType === 'CASH' ? parseFloat(dividendTotalCash) : parseFloat(dividendStockQty);
      if (isNaN(val) || val <= 0) {
        toast.warning("Vui lòng nhập giá trị hợp lệ (> 0)", "Dữ liệu không hợp lệ");
        return;
      }
      const payload: DividendPayload = {
        ticker: dividendTicker,
        dividendType: dividendType,
        totalAmount: val,
        taxPercent: dividendType === 'CASH' ? 5.0 : 0.0,
        notes: `Ghi nhận cổ tức ${dividendType === 'CASH' ? 'tiền mặt' : 'cổ phiếu'} mã ${dividendTicker}`
      };
      await recordDividend(payload);
      setShowDividendModal(false);
      await Promise.all([fetchTransactions(), loadBalance()]);
      onRefresh?.();
      toast.success(
        dividendType === 'CASH'
          ? `Ghi nhận cổ tức tiền mặt ${dividendTicker} thành công! Đã khấu trừ 5% thuế TNCN và hạch toán vào ví.`
          : `Ghi nhận cổ phiếu thưởng ${dividendTicker} thành công! Số lượng cổ phiếu đã tăng và giá vốn bình quân (WAC) đã được pha loãng.`,
        "Ghi sổ Cổ tức thành công"
      );
    } catch (err: any) {
      toast.error("Lỗi ghi nhận cổ tức: " + (err.message || err), "Thất bại");
    } finally {
      setDividendSubmitting(false);
    }
  };

  const totalCalculatedVnd = (parseFloat(amount) || 0) * (entryPrice || 1);

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="vnx-panel px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-text-primary">Sổ giao dịch</h2>
          <p className="text-xs text-text-secondary mt-0.5">Theo dõi mua bán tài sản và tiền ra vào danh mục.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button type="button" onClick={() => { setWithdrawError(''); setWithdrawOpen(true); void loadBalance(); }}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-3 py-2 text-xs font-medium text-text-primary hover:bg-surface-container">
            <ArrowUpRight className="h-4 w-4" />Rút tiền
          </button>

          <button
            onClick={() => setShowDividendModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high border border-border-subtle text-text-primary text-xs font-semibold transition-all  cursor-pointer"
            title="Ghi nhận cổ tức tiền mặt (thuế TNCN 5%) hoặc cổ phiếu thưởng"
          >
            <Coins className="w-4 h-4 text-amber-500" />
            <span>Ghi nhận cổ tức</span>
          </button>

          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-all text-xs font-bold  cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nạp tiền / Thêm tài sản</span>
          </button>
        </div>
      </div>

      <section className="bg-surface-container-lowest p-4 sm:p-6" aria-label="Lịch sử giao dịch">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-text-primary">Lịch sử giao dịch</h3>
          <span className="text-xs text-text-secondary">{activities.length} hoạt động</span>
        </div>
        <div className="my-4 flex flex-wrap gap-1" aria-label="Lọc giao dịch">
          {[['all', 'Tất cả'], ['trade', 'Mua / Bán'], ['cash', 'Nạp / Rút'], ['savings', 'Tiết kiệm'], ['dividend', 'Cổ tức'], ['other', 'Khác']].map(([key, label]) =>
            <button key={key} type="button" aria-pressed={filter === key} onClick={() => { setFilter(key); setPage(1); }}
              className={`rounded-md px-3 py-2 text-xs ${filter === key ? 'bg-accent-emerald-light font-semibold text-accent-emerald' : 'text-text-secondary hover:bg-surface-container'}`}>{label}</button>)}
        </div>
        {loading ? <p role="status" className="py-8 text-center text-sm text-text-secondary">Đang tải lịch sử…</p>
          : loadError ? <p role="alert" className="py-6 text-sm text-accent-rose">{loadError} <button onClick={fetchTransactions} className="underline">Thử lại</button></p>
          : !visibleActivities.length ? <p className="py-8 text-center text-sm text-text-secondary">Chưa có giao dịch trong mục này.</p>
          : <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-border-subtle text-xs text-text-secondary"><tr>
                  <th className="py-3 pr-4 font-normal">Thời gian</th><th className="py-3 pr-4 font-normal">Giao dịch</th>
                  <th className="py-3 pr-4 font-normal">Nội dung</th><th className="py-3 text-right font-normal">Số tiền / Giá trị</th>
                </tr></thead>
                <tbody className="divide-y divide-border-subtle">{visibleActivities.map(row => <tr key={row.id} className="align-top">
                  <td className="py-3 pr-4 text-xs tabular-nums text-text-secondary whitespace-nowrap">
                    <span className="block">{new Date(row.date).toLocaleDateString('vi-VN')}</span>
                    <span>{new Date(row.date).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
                  </td>
                  <td className="py-3 pr-4 font-medium text-text-primary">{row.action}
                    {row.status !== 'POSTED' && <span className="mt-1 block text-xs text-text-secondary">{row.status === 'PENDING' ? 'Đang xử lý' : row.status === 'FAILED' ? 'Không thành công' : 'Chưa hoàn tất'}</span>}
                  </td>
                  <td className="max-w-sm py-3 pr-4 text-text-secondary">{row.detail}</td>
                  <td className="py-3 text-right tabular-nums text-text-primary whitespace-nowrap">{row.value == null ? '—' : formatVND(row.value)}</td>
                </tr>)}</tbody>
              </table>
            </div>
            {pages > 1 && <div className="mt-4 flex items-center justify-end gap-3 text-xs text-text-secondary">
              <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)} className="rounded px-2 py-2 hover:bg-surface-container disabled:opacity-40">Trước</button>
              <span>Trang {currentPage} / {pages}</span>
              <button type="button" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)} className="rounded px-2 py-2 hover:bg-surface-container disabled:opacity-40">Sau</button>
            </div>}
          </>}
      </section>

      {withdrawOpen && <div className="!m-0 fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" onKeyDown={event => { if (event.key === 'Escape' && !withdrawing) setWithdrawOpen(false); }}>
        <div ref={withdrawRef} role="dialog" aria-modal="true" aria-labelledby="withdraw-title"
          onKeyDown={event => {
            if (event.key !== 'Tab') return;
            const controls = withdrawRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)');
            if (!controls?.length) return;
            if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls[controls.length - 1].focus(); }
            else if (!event.shiftKey && document.activeElement === controls[controls.length - 1]) { event.preventDefault(); controls[0].focus(); }
          }} className="w-full max-w-md rounded-xl bg-surface-container-lowest p-5 sm:p-6 shadow-xl">
          <div className="flex items-center justify-between gap-4"><h3 id="withdraw-title" className="text-lg font-semibold text-text-primary">Rút tiền</h3>
            <button type="button" aria-label="Đóng" disabled={withdrawing} onClick={() => setWithdrawOpen(false)} className="rounded-md p-2 text-text-secondary hover:bg-surface-container"><X className="h-4 w-4" /></button>
          </div>
          <p className="mt-2 text-sm text-text-secondary">Ghi nhận tiền rút khỏi danh mục. Ứng dụng không thực hiện chuyển khoản ngân hàng.</p>
          <p className="mt-4 text-sm text-text-secondary">Tiền mặt khả dụng: <strong className="text-text-primary">{cashBalance == null ? 'Đang tải hoặc chưa tải được số dư' : formatVND(cashBalance)}</strong></p>
          {cashBalance == null && <button type="button" onClick={loadBalance} className="mt-1 text-xs text-accent-emerald underline">Tải lại số dư</button>}
          <form onSubmit={handleWithdraw} className="mt-4 space-y-4">
            <div><label htmlFor="withdraw-amount" className="mb-1 block text-sm text-text-primary">Số tiền rút (₫)</label>
              <input autoFocus id="withdraw-amount" type="number" min="1" step="1" max={cashBalance ?? 0} required disabled={withdrawing} value={withdrawAmount} onChange={event => setWithdrawAmount(event.target.value)}
                className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-text-primary" />
            </div>
            <div><label htmlFor="withdraw-note" className="mb-1 block text-sm text-text-primary">Ghi chú (tùy chọn)</label>
              <input id="withdraw-note" maxLength={255} disabled={withdrawing} value={withdrawNote} onChange={event => setWithdrawNote(event.target.value)}
                className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-text-primary" />
            </div>
            {withdrawError && <p role="alert" className="text-sm text-accent-rose">{withdrawError}</p>}
            <div className="flex justify-end gap-2 border-t border-border-subtle pt-4">
              <button type="button" disabled={withdrawing} onClick={() => setWithdrawOpen(false)} className="rounded-md px-4 py-2 text-sm text-text-secondary hover:bg-surface-container">Hủy</button>
              <button type="submit" disabled={withdrawing || cashBalance == null || Number(withdrawAmount) <= 0 || Number(withdrawAmount) > cashBalance}
                className="rounded-md bg-accent-emerald px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{withdrawing ? 'Đang ghi nhận…' : 'Xác nhận rút tiền'}</button>
            </div>
          </form>
        </div>
      </div>}

      {/* Modal: Nạp tiền / Thêm tài sản */}
      {showModal && (
        <div className="!m-0 fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl max-w-md w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-bold text-text-primary">Khai Báo Tài Sản / Nạp Vốn</h3>
                <p className="text-xs text-text-secondary">Thêm tiền mặt hoặc tài sản đang sở hữu vào danh mục.</p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleFormSubmit} className="space-y-4 text-xs">
              {/* Chọn tài sản */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">Loại Tài Sản</label>
                <select
                  value={selectedTicker}
                  onChange={(e) => handleTickerChange(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald"
                >
                  <option value="VND">Tiền mặt VND (VND_WALLET)</option>
                  <option value="HPG">Cổ phiếu HPG - Hòa Phát (Lô 100)</option>
                  <option value="TCB">Cổ phiếu TCB - Techcombank (Lô 100)</option>
                  <option value="FPT">Cổ phiếu FPT - Công nghệ FPT (Lô 100)</option>
                  <option value="VNM">Cổ phiếu VNM - Vinamilk (Lô 100)</option>
                  <option value="GOLD_SJC">Vàng miếng SJC 999.9 (Chỉ)</option>
                </select>
              </div>

              {/* Số lượng */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">
                  Số lượng ({ASSET_PRICE_MAP[selectedTicker]?.unit || 'Đơn vị'})
                </label>
                <input
                  type="number"
                  min="1"
                  step={selectedTicker === 'GOLD_SJC' ? '0.1' : '1'}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Nhập số lượng..."
                  required
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald font-mono"
                />
              </div>

              {/* Đơn giá vốn thị trường */}
              {selectedTicker !== 'VND' && (
                <div>
                  <label className="block font-semibold text-text-primary mb-1">
                    Đơn giá vốn tham chiếu (VND)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={entryPrice}
                    onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
                    placeholder="Đơn giá thị trường..."
                    required
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald font-mono"
                  />
                </div>
              )}

              {/* Tổng quy đổi */}
              <div className="p-3 rounded-lg bg-surface-container-low border border-border-subtle flex justify-between items-center">
                <span className="text-text-secondary font-medium">Tổng giá trị quy đổi:</span>
                <span className="text-sm font-bold text-accent-emerald">
                  {formatVND(totalCalculatedVnd)}
                </span>
              </div>

              {/* Diễn giải */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">Diễn giải (Ghi chú)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Ví dụ: Nạp thêm vốn đầu tư định kỳ tháng 10..."
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald"
                />
              </div>

              {/* Nút hành động */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border-subtle">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-lg border border-border-subtle text-text-secondary hover:bg-surface-container font-semibold"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 font-bold flex items-center gap-1.5"
                >
                  {submitting ? 'Đang ghi sổ...' : 'Xác nhận Khai báo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Corporate Action / Dividend Modal */}
      {showDividendModal && (
        <div className="!m-0 fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-border-subtle flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center text-amber-500">
                  <Coins className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-text-primary">
                    Ghi Nhận Cổ Tức & Quyền Tài Sản
                  </h3>
                  <p className="text-[11px] text-text-muted">
                    Cập nhật tiền mặt hoặc cổ phiếu bạn đã nhận.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowDividendModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleDividendSubmit} className="p-5 overflow-y-auto space-y-4 text-xs">
              {/* Asset Picker */}
              <div>
                <label className="font-bold text-text-primary block mb-1.5">
                  Mã Cổ Phiếu Trả Cổ Tức:
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {['HPG', 'TCB', 'FPT', 'VNM'].map((tk) => (
                    <button
                      key={tk}
                      type="button"
                      onClick={() => setDividendTicker(tk)}
                      className={`p-2 rounded-lg border text-xs font-bold font-mono transition-all cursor-pointer ${
                        dividendTicker === tk
                          ? 'bg-accent-emerald text-white border-accent-emerald'
                          : 'bg-surface-container hover:bg-surface-container-high border-border-subtle text-text-secondary'
                      }`}
                    >
                      {tk}
                    </button>
                  ))}
                </div>
              </div>

              {/* Type Switcher */}
              <div>
                <label className="font-bold text-text-primary block mb-1.5">
                  Hình Thức Nhận Cổ Tức:
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setDividendType('CASH')}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      dividendType === 'CASH'
                        ? 'bg-amber-500/10 border-amber-500/40 text-amber-500'
                        : 'bg-surface-container border-border-subtle text-text-secondary'
                    }`}
                  >
                    <span className="font-bold block text-xs">Tiền Mặt (Cash)</span>
                    <span className="text-[10px] text-text-muted block mt-0.5">Khấu trừ thuế TNCN 5%</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDividendType('STOCK')}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      dividendType === 'STOCK'
                        ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-400'
                        : 'bg-surface-container border-border-subtle text-text-secondary'
                    }`}
                  >
                    <span className="font-bold block text-xs">Cổ Phiếu (Stock)</span>
                    <span className="text-[10px] text-text-muted block mt-0.5">Pha loãng giá vốn (WAC)</span>
                  </button>
                </div>
              </div>

              {/* Input for Cash vs Stock */}
              {dividendType === 'CASH' ? (
                <div className="space-y-3">
                  <div>
                    <label className="font-bold text-text-primary block mb-1">
                      Tổng Tiền Cổ Tức Danh Nghĩa (Gross, VNĐ):
                    </label>
                    <input
                      type="number"
                      min="1000"
                      step="1000"
                      value={dividendTotalCash}
                      onChange={(e) => setDividendTotalCash(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-surface-container border border-border-subtle text-text-primary font-mono text-sm focus:outline-hidden focus:border-accent-emerald"
                      placeholder="VD: 10000000"
                      required
                    />
                  </div>

                  {/* Tax calculation box */}
                  <div className="vnx-detail p-3     space-y-1.5 text-[11px]">
                    <div className="flex justify-between text-text-muted">
                      <span>Cổ tức danh nghĩa:</span>
                      <span className="font-mono-num font-semibold text-text-primary">
                        {formatVND(parseFloat(dividendTotalCash) || 0)}
                      </span>
                    </div>
                    <div className="flex justify-between text-accent-rose">
                      <span>Thuế TNCN khấu trừ tại nguồn (5%):</span>
                      <span className="font-mono-num font-semibold">
                        -{formatVND((parseFloat(dividendTotalCash) || 0) * 0.05)}
                      </span>
                    </div>
                    <div className="flex justify-between text-accent-emerald font-bold pt-1 border-t border-border-subtle text-xs">
                      <span>Thực nhận vào Ví VND (Net):</span>
                      <span className="font-mono-num">
                        +{formatVND((parseFloat(dividendTotalCash) || 0) * 0.95)}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="font-bold text-text-primary block mb-1">
                      Số Lượng Cổ Phiếu Nhận Thêm (CP):
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={dividendStockQty}
                      onChange={(e) => setDividendStockQty(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-surface-container border border-border-subtle text-text-primary font-mono text-sm focus:outline-hidden focus:border-accent-emerald"
                      placeholder="VD: 1000"
                      required
                    />
                  </div>

                  <div className="vnx-detail p-3     text-[11px] text-text-muted space-y-1">
                    <div className="font-semibold text-text-primary">Cơ chế pha loãng WAC chuẩn Việt Nam:</div>
                    <p>
                      Số lượng cổ phiếu trong danh mục tăng thêm <strong>{parseInt(dividendStockQty) || 0} CP</strong> mà không thay đổi tổng số vốn đã giải ngân.
                    </p>
                    <p className="text-accent-emerald">
                      Giá vốn bình quân trên mỗi cổ phiếu sẽ tự động giảm xuống, phản ánh chính xác hiệu suất đầu tư thực tế.
                    </p>
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowDividendModal(false)}
                  className="px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-text-secondary text-xs font-semibold cursor-pointer"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={dividendSubmitting}
                  className="px-5 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 text-xs font-bold transition-all  cursor-pointer disabled:opacity-50"
                >
                  {dividendSubmitting ? 'Đang lưu…' : 'Ghi nhận cổ tức'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
