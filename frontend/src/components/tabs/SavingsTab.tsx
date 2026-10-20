import { useState, useEffect } from 'react';
import {
  PiggyBank, PlusCircle, Percent, RefreshCw, X, TrendingUp, Calculator, Calendar, ArrowUpRight, Sparkles, Building2
} from 'lucide-react';
import { SavingsDepositItem, OpenSavingsPayload, CompoundSimulationResult, BankComparisonItem } from '../../types';
import {
  getSavingsDeposits,
  openSavingsDeposit,
  toggleAutoRollover,
  settleSavingsDeposit,
  simulateCompoundSavings,
  getBankRates,
  syncExternalMarket
} from '../../services/api';
import { formatVND } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

interface SavingsTabProps {
  onRefresh?: () => void;
}

const DEFAULT_TERM_RATE_MAP: Record<number, number> = {
  1: 3.20,
  3: 3.80,
  6: 5.50,
  12: 5.80
};

export function SavingsTab({ onRefresh }: SavingsTabProps) {
  const toast = useToast();
  const [deposits, setDeposits] = useState<SavingsDepositItem[]>([]);
  const [bankRates, setBankRates] = useState<BankComparisonItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [ratesLoading, setRatesLoading] = useState(true);
  const [syncingMarket, setSyncingMarket] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Modal form state
  const [bankName, setBankName] = useState('Vietcombank');
  const [principalAmount, setPrincipalAmount] = useState<string>('50000000');
  const [termMonths, setTermMonths] = useState<number>(6);
  const [interestRate, setInterestRate] = useState<string>('5.50');
  const [autoRollover, setAutoRollover] = useState(true);

  // Compound Simulator state (SRS 4.3 & 7.3)
  const [simPrincipal, setSimPrincipal] = useState<number>(50000000);
  const [simMonthly, setSimMonthly] = useState<number>(5000000);
  const [simRate, setSimRate] = useState<number>(6.5);
  const [simYears, setSimYears] = useState<number>(10);
  const [simulationResult, setSimulationResult] = useState<CompoundSimulationResult | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);

  const runSimulation = async () => {
    setSimLoading(true);
    try {
      const res = await simulateCompoundSavings({
        principal: simPrincipal,
        monthlyContribution: simMonthly,
        annualRate: simRate,
        years: simYears
      });
      setSimulationResult(res);
    } catch (e) {
      console.error("Simulation failed", e);
    } finally {
      setSimLoading(false);
    }
  };

  useEffect(() => {
    runSimulation();
  }, [simPrincipal, simMonthly, simRate, simYears]);

  const fetchDeposits = async () => {
    setLoading(true);
    try {
      const data = await getSavingsDeposits();
      setDeposits(data);
    } catch (e) {
      console.error("Failed to load savings deposits", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchBankRates = async () => {
    setRatesLoading(true);
    try {
      const rates = await getBankRates();
      setBankRates(rates);
    } catch (e) {
      console.error("Failed to load bank rates", e);
    } finally {
      setRatesLoading(false);
    }
  };

  useEffect(() => {
    fetchDeposits();
    fetchBankRates();
  }, []);

  const getRateFor = (bank: string, term: number): number => {
    const found = bankRates.find((b) => b.bankName.toLowerCase().includes(bank.toLowerCase()) || bank.toLowerCase().includes(b.bankName.toLowerCase()));
    if (found && found.ratesByTerm && found.ratesByTerm[String(term)]) {
      return Number(found.ratesByTerm[String(term)]);
    }
    return DEFAULT_TERM_RATE_MAP[term] || 5.50;
  };

  const handleBankChange = (newBank: string) => {
    setBankName(newBank);
    setInterestRate(String(getRateFor(newBank, termMonths)));
  };

  const handleTermChange = (term: number) => {
    setTermMonths(term);
    setInterestRate(String(getRateFor(bankName, term)));
  };

  const handleSelectBankFromTable = (selectedBank: string, term: number) => {
    setBankName(selectedBank);
    setTermMonths(term);
    setInterestRate(String(getRateFor(selectedBank, term)));
    setShowModal(true);
  };

  const handleSyncMarket = async () => {
    setSyncingMarket(true);
    try {
      await syncExternalMarket();
      await fetchBankRates();
      await fetchDeposits();
      onRefresh?.();
      toast.success("Đã đồng bộ biểu lãi suất ngân hàng và giá thị trường mới nhất!", "Đồng bộ thành công");
    } catch (err: any) {
      toast.error("Không thể kết nối dịch vụ ngoài: " + (err.message || err), "Lỗi đồng bộ");
    } finally {
      setSyncingMarket(false);
    }
  };

  const handleOpenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(principalAmount);
    if (isNaN(amount) || amount < 1000000) {
      toast.warning("Số tiền gửi tối thiểu là 1.000.000 VND", "Số tiền không hợp lệ");
      return;
    }

    const numRate = parseFloat(String(interestRate));
    if (isNaN(numRate) || numRate <= 0) {
      toast.warning("Lãi suất phải lớn hơn 0%", "Lãi suất không hợp lệ");
      return;
    }
    if (numRate > 30) {
      toast.warning("Lãi suất tối đa hợp lệ là 30%/năm", "Lãi suất quá cao");
      return;
    }

    setSubmitting(true);
    try {
      const payload: OpenSavingsPayload = {
        bankName,
        principalAmount: amount,
        interestRate: numRate,
        termMonths,
        autoRollover
      };
      await openSavingsDeposit(payload);
      setShowModal(false);
      await fetchDeposits();
      onRefresh?.();
      toast.success(
        `Mở sổ tiết kiệm ${bankName} thành công! Số tiền ${formatVND(amount)} đã được ghi nhận vào tài khoản.`,
        "Mở sổ tiết kiệm thành công"
      );
    } catch (err: any) {
      toast.error("Lỗi khi mở sổ tiết kiệm: " + (err.message || err), "Thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (deposit: SavingsDepositItem) => {
    try {
      const nextStatus = !deposit.autoRollover;
      await toggleAutoRollover(deposit.id, nextStatus);
      setDeposits((prev) =>
        prev.map((d) => (d.id === deposit.id ? { ...d, autoRollover: nextStatus } : d))
      );
      toast.info(`Chế độ tự động tái tục: ${nextStatus ? 'BẬT' : 'TẮT'}`, "Cập nhật thành công");
    } catch (err: any) {
      toast.error("Lỗi cập nhật tái tục: " + (err.message || err), "Cập nhật thất bại");
    }
  };

  const handleSettle = async (deposit: SavingsDepositItem) => {
    const totalEst = deposit.principalAmount + deposit.accruedInterest;
    const confirm = window.confirm(
      `Bạn có chắc chắn muốn tất toán sổ tiết kiệm ${deposit.bankName}?\n` +
      `Gốc: ${formatVND(deposit.principalAmount)}\n` +
      `Lãi lũy kế: ${formatVND(deposit.accruedInterest)}\n` +
      `Tổng hoàn về ví VND: ${formatVND(totalEst)}`
    );
    if (!confirm) return;

    try {
      await settleSavingsDeposit(deposit.id);
      await fetchDeposits();
      onRefresh?.();
      toast.success(
        `Tất toán sổ tiết kiệm thành công! Đã chuyển ${formatVND(totalEst)} về ví VND_WALLET.`,
        "Tất toán thành công"
      );
    } catch (err: any) {
      toast.error("Lỗi khi tất toán: " + (err.message || err), "Tất toán thất bại");
    }
  };

  const currentInterestRateNum = parseFloat(String(interestRate)) || 0;
  const estimatedMaturityInterest =
    ((parseFloat(principalAmount) || 0) * (currentInterestRateNum / 100) * termMonths) / 12;

  const totalActivePrincipal = deposits
    .filter((d) => d.status === 'ACTIVE')
    .reduce((sum, d) => sum + d.principalAmount, 0);

  const totalActiveAccrued = deposits
    .filter((d) => d.status === 'ACTIVE')
    .reduce((sum, d) => sum + d.accruedInterest, 0);

  return (
    <div className="space-y-6">
      {/* Header Summary */}
      <div className="vnx-panel px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-text-primary">Sổ tiết kiệm</h2>
          <p className="text-xs text-text-secondary mt-0.5">Theo dõi tiền gửi, lãi tích lũy và ngày đáo hạn.</p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <button
            type="button"
            onClick={handleSyncMarket}
            disabled={syncingMarket}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border-subtle bg-surface-container hover:bg-surface-container-high transition-all text-xs font-semibold text-text-primary "
            title="Đồng bộ biểu lãi suất các ngân hàng từ thị trường ngoài"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncingMarket ? 'animate-spin text-accent-emerald' : 'text-text-muted'}`} />
            <span>{syncingMarket ? 'Đang đồng bộ...' : 'Đồng bộ biểu lãi suất'}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-all text-xs font-bold "
          >
            <PlusCircle className="w-4 h-4" />
            <span>Mở sổ tiết kiệm mới</span>
          </button>
        </div>
      </div>

      {/* KPI Cards for Savings */}
      <div className="vnx-stat-strip grid grid-cols-1 sm:grid-cols-3 gap-0">
        <div className="vnx-stat p-4">
          <div className="flex items-center justify-between text-text-muted mb-1 text-xs font-semibold">
            <span>Tổng Tiền Gốc Đang Gửi</span>
            <PiggyBank className="w-4 h-4 text-accent-emerald" />
          </div>
          <div className="text-xl font-extrabold text-text-primary tracking-tight">
            {formatVND(totalActivePrincipal)}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">
            {deposits.filter((d) => d.status === 'ACTIVE').length} sổ đang hoạt động
          </span>
        </div>

        <div className="vnx-stat p-4">
          <div className="flex items-center justify-between text-text-muted mb-1 text-xs font-semibold">
            <span>Lãi Lũy Kế Tạm Tính</span>
            <Percent className="w-4 h-4 text-accent-gold" />
          </div>
          <div className="text-xl font-extrabold text-accent-gold tracking-tight">
            +{formatVND(totalActiveAccrued)}
          </div>
          <span className="text-[11px] text-accent-emerald font-semibold mt-1 block">
            Cập nhật realtime theo ngày
          </span>
        </div>

        <div className="vnx-stat p-4">
          <div className="flex items-center justify-between text-text-muted mb-1 text-xs font-semibold">
            <span>Cơ Chế Tái Tục</span>
            <RefreshCw className="w-4 h-4 text-accent-blue" />
          </div>
          <div className="text-xl font-extrabold text-text-primary tracking-tight">
            Lãi Kép Tự Động
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">
            Nhập lãi vào gốc kỳ tiếp theo
          </span>
        </div>
      </div>

      {/* Live Bank Rates Comparison Section */}
      <div className="vnx-panel p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-3">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-accent-emerald" />
            <h3 className="text-sm font-bold text-text-primary">
              Biểu Lãi Suất Tiết Kiệm Các Ngân Hàng Thương Mại
            </h3>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30">
              Live Feed
            </span>
          </div>
          <span className="text-[11px] text-text-muted">
            Chọn ngân hàng tối ưu để tự động áp dụng lãi suất tốt nhất khi mở sổ
          </span>
        </div>

        {ratesLoading ? (
          <div className="py-6 text-center text-xs text-text-muted">
            <div className="w-5 h-5 border-2 border-accent-emerald border-t-transparent rounded-full animate-spin mx-auto mb-1.5"></div>
            Đang tải biểu lãi suất các ngân hàng...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-border-subtle text-text-secondary bg-surface-container-low/60">
                  <th className="py-2.5 px-3 font-semibold">Ngân hàng</th>
                  <th className="py-2.5 px-3 text-right font-semibold">1 Tháng</th>
                  <th className="py-2.5 px-3 text-right font-semibold">3 Tháng</th>
                  <th className="py-2.5 px-3 text-right font-semibold">6 Tháng</th>
                  <th className="py-2.5 px-3 text-right font-semibold">12 Tháng</th>
                  <th className="py-2.5 px-3 text-center font-semibold">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle/60 font-mono-num">
                {bankRates.map((bank) => {
                  const r1 = bank.ratesByTerm?.['1'] || 0;
                  const r3 = bank.ratesByTerm?.['3'] || 0;
                  const r6 = bank.ratesByTerm?.['6'] || 0;
                  const r12 = bank.ratesByTerm?.['12'] || 0;

                  return (
                    <tr key={bank.bankCode} className="hover:bg-surface-container-low/50 transition-colors">
                      <td className="py-2.5 px-3 font-sans font-bold text-text-primary flex items-center gap-2">
                        <span className="w-6 h-6 rounded-md bg-surface-container flex items-center justify-center text-[10px] font-extrabold text-accent-emerald border border-border-subtle">
                          {bank.bankCode}
                        </span>
                        <span>{bank.bankName}</span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className="text-text-primary font-medium">{r1.toFixed(2)}%</span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className="text-text-primary font-medium">{r3.toFixed(2)}%</span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`font-bold ${r6 >= 5.2 ? 'text-accent-emerald' : 'text-text-primary'}`}>
                          {r6.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`font-bold ${r12 >= 5.7 ? 'text-accent-gold' : 'text-text-primary'}`}>
                          {r12.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center font-sans">
                        <button
                          type="button"
                          onClick={() => handleSelectBankFromTable(bank.bankName, 6)}
                          className="px-2.5 py-1 rounded bg-accent-emerald-light hover:bg-accent-emerald/20 text-accent-emerald font-bold text-[11px] transition-all border border-accent-emerald/30 inline-flex items-center gap-1"
                        >
                          <PlusCircle className="w-3 h-3" />
                          <span>Gửi sổ</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Deposits List */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-text-primary">Danh sách Sổ tiền gửi</h3>

        {loading ? (
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-12 text-center text-xs text-text-muted">
            <div className="w-6 h-6 border-2 border-accent-emerald border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            Đang tải danh sách sổ tiết kiệm...
          </div>
        ) : deposits.length === 0 ? (
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-12 text-center space-y-3">
            <p className="text-xs text-text-muted">Chưa có sổ tiết kiệm nào được mở.</p>
            <button
              onClick={() => setShowModal(true)}
              className="px-4 py-2 rounded-lg bg-accent-emerald text-white text-xs font-bold hover:bg-accent-emerald/90 transition-all inline-flex items-center gap-1.5"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Mở sổ đầu tiên ngay</span>
            </button>
          </div>
        ) : (
          deposits.map((dep) => (
            <div
              key={dep.id}
              className="vnx-savings-row py-5 space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-subtle pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-accent-gold-light flex items-center justify-center text-accent-gold font-bold text-sm shrink-0">
                    {dep.bankName.slice(0, 3).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-text-primary">{dep.bankName}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        dep.status === 'ACTIVE'
                          ? 'bg-accent-emerald-light text-accent-emerald'
                          : 'bg-surface-container-high text-text-secondary'
                      }`}>
                        {dep.status}
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary mt-0.5">
                      Kỳ hạn: <strong>{dep.termMonths} Tháng</strong> • Lãi suất: <strong>{dep.interestRate}%/năm</strong>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 sm:text-right">
                  <div>
                    <span className="text-[10px] text-text-muted uppercase font-bold block">Tiền gửi gốc</span>
                    <span className="text-base font-extrabold text-text-primary block">
                      {formatVND(dep.principalAmount)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-text-muted uppercase font-bold block">Lãi lũy kế</span>
                    <span className="text-sm font-bold text-accent-gold block">
                      +{formatVND(dep.accruedInterest)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Progress and Dates */}
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between items-center text-[11px] text-text-secondary">
                  <span>Ngày gửi: {new Date(dep.startDate).toLocaleDateString('vi-VN')}</span>
                  <span>
                    Đáo hạn: <strong>{new Date(dep.maturityDate).toLocaleDateString('vi-VN')}</strong>
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-surface-container-high rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-accent-emerald h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, dep.progressPercent || 0)}%` }}
                  ></div>
                </div>

                <div className="flex justify-between items-center text-[10px] text-text-muted">
                  <span>Đã trôi qua: {dep.daysElapsed} ngày / {dep.totalDays} ngày</span>
                  <span>{dep.progressPercent}% thời gian kỳ hạn</span>
                </div>
              </div>

              {/* Controls footer */}
              {dep.status === 'ACTIVE' && (
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border-subtle text-xs">
                  {/* Auto rollover switch */}
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={dep.autoRollover}
                      onChange={() => handleToggle(dep)}
                      className="w-4 h-4 rounded text-accent-emerald border-border-subtle focus:ring-accent-emerald"
                    />
                    <span className="font-semibold text-text-primary text-[11px]">
                      Tự động tái tục lãi kép khi đáo hạn (Auto-Rollover)
                    </span>
                  </label>

                  {/* Settle button */}
                  <button
                    onClick={() => handleSettle(dep)}
                    className="px-3 py-1.5 rounded-lg border border-accent-rose/30 text-accent-rose hover:bg-accent-rose-light text-[11px] font-bold transition-all ml-auto"
                  >
                    Tất toán sổ trước hạn
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Simulator: Mô Phỏng Tích Sản & Động Cơ Lãi Kép (SRS Section 4.3 & 7.3) */}
      <div className="vnx-panel p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border-subtle pb-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-accent-emerald-light text-accent-emerald">
                <Calculator className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-text-primary tracking-tight">
                Mô Phỏng Tích Sản & Lãi Kép Dòng Tiền Đều
              </h3>
              <span className="px-2 py-0.5 rounded-full bg-accent-emerald-light text-accent-emerald text-[10px] font-bold border border-accent-emerald/30 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                SRS 4.3 & 7.3
              </span>
            </div>
            <p className="text-xs text-text-secondary mt-1">
              Mô hình hóa dòng tiền tương lai với công thức tích sản định kỳ:
              <span className="font-mono text-accent-emerald font-semibold ml-1">
                FV = P·(1+r/12)¹²ᵗ + PMT·[((1+r/12)¹²ᵗ - 1) / (r/12)]
              </span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-container border border-border-subtle text-text-muted">
              Đồng bộ deterministic với Copilot Tool Calling
            </span>
          </div>
        </div>

        {/* Input Parameters Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Vốn ban đầu P */}
          <div className="vnx-detail p-4     space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-text-secondary">Vốn gốc ban đầu (P)</label>
              <span className="font-bold font-mono text-accent-emerald text-sm">
                {formatVND(simPrincipal)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="500000000"
              step="5000000"
              value={simPrincipal}
              onChange={(e) => setSimPrincipal(Number(e.target.value))}
              className="w-full accent-accent-emerald cursor-pointer"
            />
            <div className="flex gap-1.5 flex-wrap pt-1">
              {[10000000, 50000000, 100000000, 200000000].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSimPrincipal(val)}
                  className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                    simPrincipal === val
                      ? 'bg-accent-emerald text-white border-accent-emerald font-bold'
                      : 'border-border-subtle bg-surface-container text-text-muted hover:text-text-primary'
                  }`}
                >
                  {val >= 100000000 ? `${val / 100000000}00tr` : `${val / 1000000}tr`}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Tiền góp hàng tháng PMT */}
          <div className="vnx-detail p-4     space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-text-secondary">Tích lũy mỗi tháng (PMT)</label>
              <span className="font-bold font-mono text-accent-emerald text-sm">
                {formatVND(simMonthly)}
              </span>
            </div>
            <input
              type="range"
              min="1000000"
              max="50000000"
              step="1000000"
              value={simMonthly}
              onChange={(e) => setSimMonthly(Number(e.target.value))}
              className="w-full accent-accent-emerald cursor-pointer"
            />
            <div className="flex gap-1.5 flex-wrap pt-1">
              {[2000000, 5000000, 10000000, 20000000].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSimMonthly(val)}
                  className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                    simMonthly === val
                      ? 'bg-accent-emerald text-white border-accent-emerald font-bold'
                      : 'border-border-subtle bg-surface-container text-text-muted hover:text-text-primary'
                  }`}
                >
                  {val / 1000000}tr/tháng
                </button>
              ))}
            </div>
          </div>

          {/* 3. Lãi suất r */}
          <div className="vnx-detail p-4     space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-text-secondary">Lãi suất kỳ vọng (r)</label>
              <span className="font-bold font-mono text-accent-gold text-sm">
                {simRate}% / năm
              </span>
            </div>
            <input
              type="range"
              min="3"
              max="15"
              step="0.5"
              value={simRate}
              onChange={(e) => setSimRate(Number(e.target.value))}
              className="w-full accent-accent-gold cursor-pointer"
            />
            <div className="flex gap-1.5 flex-wrap pt-1">
              {[5.5, 6.5, 8.0, 10.0].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSimRate(val)}
                  className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                    simRate === val
                      ? 'bg-accent-gold text-white border-accent-gold font-bold'
                      : 'border-border-subtle bg-surface-container text-text-muted hover:text-text-primary'
                  }`}
                >
                  {val}%
                </button>
              ))}
            </div>
          </div>

          {/* 4. Thời gian t (Năm) */}
          <div className="vnx-detail p-4     space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-text-secondary">Thời gian tích sản (t)</label>
              <span className="font-bold font-mono text-accent-blue text-sm">
                {simYears} Năm ({simYears * 12} tháng)
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              step="1"
              value={simYears}
              onChange={(e) => setSimYears(Number(e.target.value))}
              className="w-full accent-accent-blue cursor-pointer"
            />
            <div className="flex gap-1.5 flex-wrap pt-1">
              {[3, 5, 10, 15, 20].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSimYears(val)}
                  className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                    simYears === val
                      ? 'bg-accent-blue text-white border-accent-blue font-bold'
                      : 'border-border-subtle bg-surface-container text-text-muted hover:text-text-primary'
                  }`}
                >
                  {val} năm
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Metric Summary Cards */}
        {simulationResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Tổng vốn góp */}
              <div className="vnx-detail p-4    ">
                <div className="text-text-muted text-[11px] font-semibold mb-1 flex items-center justify-between">
                  <span>Tổng Vốn Đã Góp</span>
                  <Calendar className="w-3.5 h-3.5 text-text-muted" />
                </div>
                <div className="text-lg font-bold font-mono text-text-primary">
                  {formatVND(simulationResult.totalContributed)}
                </div>
                <div className="text-[11px] text-text-muted mt-1">
                  Gốc: {formatVND(simulationResult.initialPrincipal)} + {simYears * 12} kỳ góp
                </div>
              </div>

              {/* Card 2: Lãi kép tích lũy */}
              <div className="vnx-detail p-4    ">
                <div className="text-accent-emerald text-[11px] font-semibold mb-1 flex items-center justify-between">
                  <span>Tiền Lãi Sinh Sôi (Lãi Kép)</span>
                  <TrendingUp className="w-3.5 h-3.5 text-accent-emerald" />
                </div>
                <div className="text-lg font-extrabold font-mono text-accent-emerald">
                  +{formatVND(simulationResult.totalInterestEarned)}
                </div>
                <div className="text-[11px] text-accent-emerald font-medium mt-1">
                  {(
                    (simulationResult.totalInterestEarned /
                      (simulationResult.futureValue || 1)) *
                    100
                  ).toFixed(1)}
                  % cấu thành tổng tài sản
                </div>
              </div>

              {/* Card 3: Tổng tài sản tương lai FV */}
              <div className="vnx-detail p-4     ">
                <div className="text-text-muted text-[11px] font-semibold mb-1 flex items-center justify-between">
                  <span>Tổng Tài Sản Đáo Hạn (FV)</span>
                  <ArrowUpRight className="w-3.5 h-3.5 text-accent-gold" />
                </div>
                <div className="text-xl font-black font-mono text-accent-gold tracking-tight">
                  {formatVND(simulationResult.futureValue)}
                </div>
                <div className="text-[11px] text-text-secondary mt-1">
                  Sau {simYears} năm ({simYears * 12} tháng)
                </div>
              </div>

              {/* Card 4: Bội số tài sản */}
              <div className="vnx-detail p-4    ">
                <div className="text-accent-blue text-[11px] font-semibold mb-1 flex items-center justify-between">
                  <span>Bội Số Tăng Trưởng</span>
                  <Sparkles className="w-3.5 h-3.5 text-accent-blue" />
                </div>
                <div className="text-xl font-black font-mono text-accent-blue tracking-tight">
                  x{simulationResult.wealthMultiplier.toFixed(2)} lần
                </div>
                <div className="text-[11px] text-accent-blue font-medium mt-1">
                  Hiệu ứng kỳ quan thứ 8
                </div>
              </div>
            </div>

            {/* Visual Ratio Bar */}
            <div className="vnx-detail p-4     space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-text-secondary">Cơ cấu tài sản tích lũy (FV)</span>
                <span className="text-[11px] text-text-muted">
                  Vốn gốc:{' '}
                  {(
                    (simulationResult.totalContributed /
                      (simulationResult.futureValue || 1)) *
                    100
                  ).toFixed(1)}
                  % | Lãi kép:{' '}
                  {(
                    (simulationResult.totalInterestEarned /
                      (simulationResult.futureValue || 1)) *
                    100
                  ).toFixed(1)}
                  %
                </span>
              </div>
              <div className="h-3 w-full bg-surface-container rounded-full overflow-hidden flex">
                <div
                  className="bg-accent-blue h-full transition-all duration-500"
                  style={{
                    width: `${
                      (simulationResult.totalContributed /
                        (simulationResult.futureValue || 1)) *
                      100
                    }%`
                  }}
                  title="Vốn góp"
                />
                <div
                  className="bg-accent-emerald h-full transition-all duration-500"
                  style={{
                    width: `${
                      (simulationResult.totalInterestEarned /
                        (simulationResult.futureValue || 1)) *
                      100
                    }%`
                  }}
                  title="Tiền lãi sinh sôi"
                />
              </div>
              <div className="flex items-center gap-4 text-[11px] pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-accent-blue inline-block" />
                  <span className="text-text-muted">
                    Vốn nộp: {formatVND(simulationResult.totalContributed)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-accent-emerald inline-block" />
                  <span className="text-accent-emerald font-semibold">
                    Lãi sinh sôi: +{formatVND(simulationResult.totalInterestEarned)}
                  </span>
                </div>
              </div>
            </div>

            {/* Yearly Breakdown Table */}
            <div className="border border-border-subtle rounded-xl overflow-hidden bg-surface-container-lowest">
              <div className="p-3 bg-surface-container-low border-b border-border-subtle flex items-center justify-between">
                <span className="text-xs font-bold text-text-primary">
                  Bảng chi tiết tăng trưởng theo từng năm (Lũy kế {simulationResult.yearlyBreakdown.length} năm)
                </span>
                <span className="text-[11px] text-text-muted font-mono">
                  {simLoading ? 'Đang tính toán...' : 'Đã khớp dữ liệu'}
                </span>
              </div>
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-surface-container text-text-secondary uppercase text-[10px] tracking-wider sticky top-0">
                    <tr>
                      <th className="px-3 py-2">Năm</th>
                      <th className="px-3 py-2 text-right">Số dư đầu năm</th>
                      <th className="px-3 py-2 text-right">Vốn góp trong năm</th>
                      <th className="px-3 py-2 text-right">Lũy kế vốn góp</th>
                      <th className="px-3 py-2 text-right">Lãi sinh trong năm</th>
                      <th className="px-3 py-2 text-right">Lũy kế tiền lãi</th>
                      <th className="px-3 py-2 text-right">Số dư cuối năm (FV)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle font-mono">
                    {simulationResult.yearlyBreakdown.map((row) => (
                      <tr key={row.year} className="hover:bg-surface-container-low/50">
                        <td className="px-3 py-2 font-bold text-text-primary">Năm {row.year}</td>
                        <td className="px-3 py-2 text-right text-text-muted">{formatVND(row.startBalance)}</td>
                        <td className="px-3 py-2 text-right text-text-secondary">{formatVND(row.yearlyContribution)}</td>
                        <td className="px-3 py-2 text-right text-accent-blue">{formatVND(row.cumulativeContribution)}</td>
                        <td className="px-3 py-2 text-right font-semibold text-accent-emerald">+{formatVND(row.interestEarnedThisYear)}</td>
                        <td className="px-3 py-2 text-right text-accent-emerald">{formatVND(row.cumulativeInterest)}</td>
                        <td className="px-3 py-2 text-right font-extrabold text-accent-gold">{formatVND(row.endBalance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal: Mở sổ tiết kiệm mới */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl max-w-md w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-bold text-text-primary">Mở Sổ Tiết Kiệm Mới</h3>
                <p className="text-xs text-text-secondary">Trích tiền khả dụng từ ví VND (sinh bút toán kép Nợ/Có)</p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleOpenSubmit} className="space-y-4 text-xs">
              {/* Ngân hàng */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">Ngân hàng phát hành</label>
                <select
                  value={bankName}
                  onChange={(e) => handleBankChange(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald"
                >
                  {bankRates.length > 0 ? (
                    bankRates.map((b) => (
                      <option key={b.bankCode} value={b.bankName}>
                        {b.bankName} ({b.bankCode})
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="Vietcombank">Vietcombank (VCB)</option>
                      <option value="BIDV">BIDV</option>
                      <option value="VietinBank">VietinBank (CTG)</option>
                      <option value="Agribank">Agribank (AGR)</option>
                      <option value="MB Bank">MB Bank (MBB)</option>
                      <option value="Techcombank">Techcombank (TCB)</option>
                      <option value="ACB">ACB</option>
                      <option value="HDBank">HDBank (HDB)</option>
                    </>
                  )}
                </select>
              </div>

              {/* Số tiền gửi */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">Số tiền gửi (VND)</label>
                <input
                  type="number"
                  min="1000000"
                  step="1000000"
                  value={principalAmount}
                  onChange={(e) => setPrincipalAmount(e.target.value)}
                  placeholder="Ví dụ: 50000000..."
                  required
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald font-mono"
                />
              </div>

              {/* Kỳ hạn */}
              <div>
                <label className="block font-semibold text-text-primary mb-1">Kỳ hạn gửi</label>
                <div className="grid grid-cols-4 gap-2">
                  {[1, 3, 6, 12].map((term) => (
                    <button
                      key={term}
                      type="button"
                      onClick={() => handleTermChange(term)}
                      className={`py-2 rounded-lg font-bold border text-center transition-all ${
                        termMonths === term
                          ? 'border-accent-emerald bg-accent-emerald-light text-accent-emerald'
                          : 'border-border-subtle bg-surface-container hover:bg-surface-container-high text-text-secondary'
                      }`}
                    >
                      {term} Tháng
                      <span className="block text-[10px] font-normal">{getRateFor(bankName, term)}%/năm</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Lãi suất */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block font-semibold text-text-primary text-xs">
                    Lãi suất áp dụng (%/năm)
                  </label>
                  {currentInterestRateNum !== getRateFor(bankName, termMonths) && (
                    <button
                      type="button"
                      onClick={() => setInterestRate(String(getRateFor(bankName, termMonths)))}
                      className="text-[11px] text-accent-blue hover:underline cursor-pointer font-medium"
                    >
                      Dùng lãi suất chuẩn ({getRateFor(bankName, termMonths)}%)
                    </button>
                  )}
                </div>
                <div className="relative">
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="30"
                    value={interestRate}
                    onChange={(e) => setInterestRate(e.target.value)}
                    placeholder="Ví dụ: 6.2..."
                    required
                    className="w-full px-3 py-2 pr-16 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald font-mono font-bold text-sm"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-text-muted pointer-events-none">
                    %/năm
                  </div>
                </div>
                <p className="text-[11px] text-text-muted mt-1">
                  * Tự động điền theo biểu niêm yết, bạn có thể tự nhập theo lãi suất đàm phán hoặc ưu đãi riêng.
                </p>
              </div>

              {/* Tiền lãi dự kiến khi đáo hạn */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-accent-emerald-light/30 border border-accent-emerald/30">
                <span className="text-text-primary font-medium">Lãi dự kiến khi đáo hạn:</span>
                <span className="font-extrabold text-accent-emerald text-sm">
                  +{formatVND(estimatedMaturityInterest)}
                </span>
              </div>

              {/* Checkbox Auto-Rollover */}
              <label className="flex items-center gap-2 cursor-pointer select-none pt-1">
                <input
                  type="checkbox"
                  checked={autoRollover}
                  onChange={(e) => setAutoRollover(e.target.checked)}
                  className="w-4 h-4 rounded text-accent-emerald border-border-subtle focus:ring-accent-emerald"
                />
                <span className="text-text-primary font-semibold text-[11px]">
                  Bật tự động tái tục gốc + lãi khi đáo hạn (Lãi kép)
                </span>
              </label>

              {/* Action buttons */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border-subtle">
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
                  {submitting ? 'Đang trích tiền...' : 'Xác nhận Mở sổ'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
