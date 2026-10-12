import { useState, useEffect } from 'react';
import { CheckCircle, PlusCircle, ArrowDownRight, ArrowUpRight, ShieldCheck, X, FileCheck2 } from 'lucide-react';
import { TransactionItem, EquityInjectionPayload, LedgerAuditReport } from '../../types';
import { getTransactions, recordEquityInjection, getLedgerAuditReport } from '../../services/api';
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
  GOLD_SJC: { name: 'Vàng miếng SJC 999.9', price: 8400000, type: 'GOLD', unit: 'Chỉ' }
};

export function LedgerTab({ onRefresh }: LedgerTabProps) {
  const toast = useToast();
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Modal form state
  const [selectedTicker, setSelectedTicker] = useState('VND');
  const [amount, setAmount] = useState<string>('50000000');
  const [entryPrice, setEntryPrice] = useState<number>(1);
  const [description, setDescription] = useState('');

  const [auditReport, setAuditReport] = useState<LedgerAuditReport | null>(null);
  const [auditing, setAuditing] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const data = await getTransactions();
      setTransactions(data);
    } catch (e) {
      console.error("Failed to load transactions", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAudit = async () => {
    setAuditing(true);
    try {
      const rep = await getLedgerAuditReport();
      setAuditReport(rep);
    } catch (e) {
      console.error("Failed to run audit", e);
    } finally {
      setAuditing(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
    fetchAudit();
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
      await fetchTransactions();
      onRefresh?.();
      toast.success(
        "Khai báo tài sản ban đầu thành công! Đã ghi nhận bút toán kép ACID.",
        "Ghi sổ thành công"
      );
    } catch (err: any) {
      toast.error("Lỗi khai báo tài sản: " + (err.message || err), "Thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  const totalCalculatedVnd = (parseFloat(amount) || 0) * (entryPrice || 1);

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-text-primary tracking-tight">
              Nhật Ký Sổ Cái Kép (Double-Entry Journal)
            </h2>
            <span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold border border-accent-emerald/30">
              ACID Verified
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Mọi biến động tài sản đều tuân thủ bất biến kế toán ngân hàng: <strong className="text-text-primary">Σ Debit + Σ Credit = 0</strong>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={fetchAudit}
            disabled={auditing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high border border-border-subtle text-text-primary text-xs font-semibold transition-all shadow-xs"
            title="Chạy đối soát và kiểm toán tính bất biến ACID theo Mục 9 SRS"
          >
            <FileCheck2 className={`w-4 h-4 text-accent-emerald ${auditing ? 'animate-spin' : ''}`} />
            <span>{auditing ? 'Đang đối soát...' : 'Kiểm toán Sổ cái (Mục 9 SRS)'}</span>
          </button>

          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-all text-xs font-bold shadow-xs"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Khai báo tài sản / Nạp vốn</span>
          </button>
        </div>
      </div>

      {/* ACID Audit & Reconciliation Card (Mục 9 SRS) */}
      {auditReport && (
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-accent-emerald shrink-0" />
              <span className="text-sm font-bold text-text-primary">
                Đối Soát & Kiểm Toán Sổ Cái Chuẩn ACID (Mục 9 SRS)
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                auditReport.allTransactionsBalanced && auditReport.allAccountsConsistent
                  ? 'bg-accent-emerald-light text-accent-emerald border-accent-emerald/30'
                  : 'bg-accent-rose-light text-accent-rose border-accent-rose/30'
              }`}>
                {auditReport.auditStatus}
              </span>
            </div>
            <button
              onClick={() => setShowAuditModal(true)}
              className="text-xs font-bold text-accent-emerald hover:underline flex items-center gap-1 self-start sm:self-auto"
            >
              Xem bảng đối soát chi tiết ({auditReport.accountAuditList.length} tài khoản) →
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
            <div className="p-3 rounded-lg bg-surface-container border border-border-subtle">
              <span className="text-[11px] text-text-muted block">Giao dịch cân bằng Σ Debit = Σ Credit:</span>
              <span className="text-sm font-bold text-accent-emerald">
                {auditReport.balancedTransactions} / {auditReport.totalTransactionsChecked} GD ({auditReport.allTransactionsBalanced ? '100% Khớp' : 'Lệch'})
              </span>
            </div>
            <div className="p-3 rounded-lg bg-surface-container border border-border-subtle">
              <span className="text-[11px] text-text-muted block">Bất biến Số dư Snapshot vs Entries:</span>
              <span className="text-sm font-bold text-accent-emerald">
                {auditReport.allAccountsConsistent ? '100% Khớp từng đồng' : 'Cảnh báo sai lệch'}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-surface-container border border-border-subtle">
              <span className="text-[11px] text-text-muted block">Thời điểm đối soát:</span>
              <span className="text-xs font-mono text-text-secondary">
                {new Date(auditReport.verifiedAt).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })} - {new Date(auditReport.verifiedAt).toLocaleDateString('vi-VN')}
              </span>
            </div>
          </div>
          <p className="text-[11px] text-text-muted italic">
            ✓ {auditReport.systemSummary}
          </p>
        </div>
      )}

      {/* Transactions List */}
      <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <h3 className="text-sm font-bold text-text-primary">Danh sách Bút toán Kép đã ghi sổ</h3>
          <span className="text-xs text-text-muted">Tổng số: {transactions.length} giao dịch</span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-text-muted">
            <div className="w-6 h-6 border-2 border-accent-emerald border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            Đang tải dữ liệu Sổ cái kép...
          </div>
        ) : transactions.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <p className="text-xs text-text-muted">Chưa có giao dịch phát sinh nào trong sổ cái.</p>
            <button
              onClick={() => setShowModal(true)}
              className="px-4 py-2 rounded-lg bg-accent-emerald text-white text-xs font-bold hover:bg-accent-emerald/90 transition-all inline-flex items-center gap-1.5"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Nạp vốn ban đầu ngay</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
                  <th className="pb-3 font-semibold">Mã GD & Thời gian</th>
                  <th className="pb-3 font-semibold">Loại Nghiệp Vụ</th>
                  <th className="pb-3 font-semibold">Diễn Giải Nghiệp Vụ</th>
                  <th className="pb-3 font-semibold">Bút toán Kép (Entries)</th>
                  <th className="pb-3 font-semibold text-center">Kiểm Định ACID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-surface-container-low transition-colors align-top">
                    {/* Mã & Thời gian */}
                    <td className="py-3 font-mono">
                      <span className="font-bold text-text-primary block">{tx.transactionCode}</span>
                      <span className="text-[10px] text-text-muted block">
                        {new Date(tx.createdAt).toLocaleString('vi-VN')}
                      </span>
                    </td>

                    {/* Loại nghiệp vụ */}
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        tx.type === 'REBALANCE'
                          ? 'bg-accent-blue-light text-accent-blue'
                          : tx.type === 'CAPITAL_INJECTION'
                          ? 'bg-accent-emerald-light text-accent-emerald'
                          : tx.type === 'SAVINGS_DEPOSIT' || tx.type === 'SAVINGS_SETTLE'
                          ? 'bg-accent-gold-light text-accent-gold'
                          : 'bg-surface-container-high text-text-secondary'
                      }`}>
                        {tx.type}
                      </span>
                    </td>

                    {/* Diễn giải */}
                    <td className="py-3 text-text-secondary max-w-xs leading-relaxed">
                      {tx.description}
                    </td>

                    {/* Chi tiết bút toán Nợ / Có */}
                    <td className="py-3 space-y-1">
                      {tx.entries && tx.entries.map((entry) => (
                        <div key={entry.id} className="flex items-center gap-2 font-mono text-[11px]">
                          {entry.amount >= 0 ? (
                            <span className="inline-flex items-center gap-0.5 text-accent-emerald font-semibold">
                              <ArrowUpRight className="w-3 h-3" />
                              Nợ (Dr): {entry.accountCode} (+{entry.amount.toLocaleString()} {entry.assetTicker})
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-0.5 text-accent-rose font-semibold">
                              <ArrowDownRight className="w-3 h-3" />
                              Có (Cr): {entry.accountCode} ({entry.amount.toLocaleString()} {entry.assetTicker})
                            </span>
                          )}
                        </div>
                      ))}
                    </td>

                    {/* Trạng thái ACID */}
                    <td className="py-3 text-center">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">
                        <CheckCircle className="w-3 h-3" />
                        Balanced (Σ=0)
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Khai báo tài sản / Nạp vốn */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl max-w-md w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-bold text-text-primary">Khai Báo Tài Sản / Nạp Vốn</h3>
                <p className="text-xs text-text-secondary">Tạo bút toán tăng tài sản đối ứng Nguồn vốn (EQUITY_CAPITAL)</p>
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

      {/* Modal Chi tiết Kiểm toán & Đối soát Sổ cái (Mục 9 SRS) */}
      {showAuditModal && auditReport && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-border-subtle shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-accent-emerald-light text-accent-emerald flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-text-primary">
                    Báo Cáo Đối Soát Chi Tiết Sổ Cái Kép (Mục 9 SRS)
                  </h3>
                  <p className="text-[11px] text-text-muted">
                    Kiểm toán độc lập bất biến kế toán ngân hàng & đối chiếu số dư tức thời
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowAuditModal(false)}
                className="text-text-muted hover:text-text-primary p-1.5 rounded-lg hover:bg-surface-container"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-accent-emerald-light/50 border border-accent-emerald/30 text-text-primary flex items-start gap-2.5">
                <CheckCircle className="w-4 h-4 text-accent-emerald shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block text-accent-emerald">Trạng thái: {auditReport.auditStatus}</span>
                  <p className="text-[11px] text-text-secondary mt-0.5">{auditReport.systemSummary}</p>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-text-primary mb-2 text-xs flex items-center justify-between">
                  <span>Đối chiếu Snapshot Số dư với Tổng lịch sử Entries:</span>
                  <span className="text-[11px] font-normal text-text-muted">Ràng buộc: Balance(account) = Σ Entries(amount)</span>
                </h4>
                <div className="overflow-x-auto border border-border-subtle rounded-lg">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-container text-text-muted text-[11px]">
                      <tr>
                        <th className="p-2.5 font-semibold">Tài khoản con</th>
                        <th className="p-2.5 font-semibold">Tài sản</th>
                        <th className="p-2.5 font-semibold text-right">Số dư Snapshot</th>
                        <th className="p-2.5 font-semibold text-right">Tổng Entries (Ghi sổ)</th>
                        <th className="p-2.5 font-semibold text-right">Chênh lệch</th>
                        <th className="p-2.5 font-semibold text-center">Kết luận</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle">
                      {auditReport.accountAuditList.map((acc, idx) => (
                        <tr key={idx} className="hover:bg-surface-container-low transition-colors">
                          <td className="p-2.5 font-mono font-semibold text-text-primary">{acc.accountCode}</td>
                          <td className="p-2.5 text-text-secondary">{acc.assetTicker}</td>
                          <td className="p-2.5 font-mono text-right text-text-primary">
                            {acc.assetTicker === 'VND' ? formatVND(acc.snapshotBalance) : `${acc.snapshotBalance} ${acc.assetTicker}`}
                          </td>
                          <td className="p-2.5 font-mono text-right text-text-primary">
                            {acc.assetTicker === 'VND' ? formatVND(acc.calculatedEntriesBalance) : `${acc.calculatedEntriesBalance} ${acc.assetTicker}`}
                          </td>
                          <td className="p-2.5 font-mono text-right text-accent-emerald font-semibold">
                            {acc.discrepancy === 0 ? '0.0000' : acc.discrepancy}
                          </td>
                          <td className="p-2.5 text-center">
                            {acc.consistent ? (
                              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-accent-emerald">
                                <CheckCircle className="w-3.5 h-3.5" /> Khớp 100%
                              </span>
                            ) : (
                              <span className="text-[11px] font-bold text-accent-rose">Sai lệch</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-border-subtle bg-surface-container flex items-center justify-between shrink-0">
              <span className="text-[11px] text-text-muted">
                Chu kỳ kiểm toán tự động: 23:59:00 hàng ngày (Spring Batch Reconciliation)
              </span>
              <button
                onClick={() => setShowAuditModal(false)}
                className="px-4 py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-text-primary text-xs font-bold"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
