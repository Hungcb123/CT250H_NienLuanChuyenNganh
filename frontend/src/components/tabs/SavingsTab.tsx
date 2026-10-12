import { useState, useEffect } from 'react';
import {
  PiggyBank, PlusCircle, Percent, RefreshCw, X, TrendingUp, Calculator, Calendar, ArrowUpRight, Sparkles
} from 'lucide-react';
import { SavingsDepositItem, OpenSavingsPayload, CompoundSimulationResult } from '../../types';
import {
  getSavingsDeposits,
  openSavingsDeposit,
  toggleAutoRollover,
  settleSavingsDeposit,
  simulateCompoundSavings
} from '../../services/api';
import { formatVND } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

interface SavingsTabProps {
  onRefresh?: () => void;
}

const TERM_RATE_MAP: Record<number, number> = {
  1: 3.20,
  3: 3.80,
  6: 5.50,
  12: 5.80
};

export function SavingsTab({ onRefresh }: SavingsTabProps) {
  const toast = useToast();
  const [deposits, setDeposits] = useState<SavingsDepositItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Modal form state
  const [bankName, setBankName] = useState('Vietcombank');
  const [principalAmount, setPrincipalAmount] = useState<string>('50000000');
  const [termMonths, setTermMonths] = useState<number>(6);
  const [interestRate, setInterestRate] = useState<number>(5.50);
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

  useEffect(() => {
    fetchDeposits();
  }, []);

  const handleTermChange = (term: number) => {
    setTermMonths(term);
    setInterestRate(TERM_RATE_MAP[term] || 5.50);
  };

  const handleOpenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(principalAmount);
    if (isNaN(amount) || amount < 1000000) {
      toast.warning("Số tiền gửi tối thiểu là 1.000.000 VND", "Số tiền không hợp lệ");
      return;
    }

    setSubmitting(true);
    try {
      const payload: OpenSavingsPayload = {
        bankName,
        principalAmount: amount,
        interestRate,
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

  const estimatedMaturityInterest =
    ((parseFloat(principalAmount) || 0) * (interestRate / 100) * termMonths) / 12;

  const totalActivePrincipal = deposits
    .filter((d) => d.status === 'ACTIVE')
    .reduce((sum, d) => sum + d.principalAmount, 0);

  const totalActiveAccrued = deposits
    .filter((d) => d.status === 'ACTIVE')
    .reduce((sum, d) => sum + d.accruedInterest, 0);

  return (
    <div className="space-y-6">
      {/* Header Summary */}
      <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-text-primary tracking-tight">
              Sổ Tiền Gửi Tiết Kiệm & Động Cơ Lãi Kép
            </h2>
            <span className="px-2 py-0.5 rounded bg-accent-gold-light text-accent-gold text-[10px] font-bold border border-accent-gold/30">
              Auto-Compound Engine
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Batch Job tự động tính lãi tích lũy hàng ngày và tái tục gốc + lãi khi đáo hạn (Auto-Rollover)
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-all text-xs font-bold shadow-sm self-start md:self-auto"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Mở sổ tiết kiệm mới</span>
        </button>
      </div>

      {/* KPI Cards for Savings */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-4 shadow-xs">
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

        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-4 shadow-xs">
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

        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-4 shadow-xs">
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
              className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-xs space-y-4 hover:border-border-highlight transition-all"
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
      <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-sm space-y-6">
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
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2">
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
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2">
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
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2">
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
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2">
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
              <div className="p-4 rounded-xl bg-surface-container border border-border-subtle">
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
              <div className="p-4 rounded-xl bg-accent-emerald-light/20 border border-accent-emerald/30">
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
              <div className="p-4 rounded-xl bg-surface-container-high border border-border-subtle shadow-xs">
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
              <div className="p-4 rounded-xl bg-accent-blue-light/20 border border-accent-blue/30">
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
            <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2">
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
                  onChange={(e) => setBankName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-container-lowest text-text-primary focus:outline-hidden focus:border-accent-emerald"
                >
                  <option value="Vietcombank">Vietcombank (VCB)</option>
                  <option value="Techcombank">Techcombank (TCB)</option>
                  <option value="MBBank">MBBank (MB)</option>
                  <option value="BIDV">BIDV</option>
                  <option value="ACB">ACB</option>
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
                      <span className="block text-[10px] font-normal">{TERM_RATE_MAP[term]}%/năm</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Lãi suất */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-low border border-border-subtle">
                <span className="text-text-secondary font-medium">Lãi suất áp dụng:</span>
                <span className="font-bold text-accent-gold text-sm">{interestRate}%/năm</span>
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
