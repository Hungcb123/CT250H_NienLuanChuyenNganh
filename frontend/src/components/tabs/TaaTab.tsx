import { useState } from 'react';
import {
  Sparkles, TrendingUp, Shield, RefreshCw, CheckCircle2,
  AlertTriangle, ArrowRight, Check, RotateCcw
} from 'lucide-react';
import { RebalancePlan, UserProfile, PortfolioValuation } from '../../types';
import { formatVND } from '../../utils/formatters';
import { updatePortfolioTargets } from '../../services/api';
import { useToast } from '../../context/ToastContext';

interface TaaTabProps {
  plan: RebalancePlan | null;
  profile?: UserProfile | null;
  valuation?: PortfolioValuation | null;
  onRefreshData?: () => Promise<void> | void;
  onConfirmRebalance?: () => Promise<void> | void;
  executing?: boolean;
}

export function TaaTab({
  plan,
  profile,
  valuation,
  onRefreshData,
  onConfirmRebalance,
  executing = false,
}: TaaTabProps) {
  const toast = useToast();
  const [isApplyingTAA, setIsApplyingTAA] = useState(false);
  const [isResettingSAA, setIsResettingSAA] = useState(false);

  // Targets from plan targetAllocations or defaults
  const currentStockTarget = ((plan?.targetAllocations?.STOCK ?? 0.40) * 100);
  const currentGoldTarget = ((plan?.targetAllocations?.GOLD ?? 0.20) * 100);
  const currentSavingsTarget = ((plan?.targetAllocations?.SAVINGS ?? 0.30) * 100);
  const currentCashTarget = ((plan?.targetAllocations?.CASH ?? 0.10) * 100);

  // Real allocations from valuation
  const realStockWeight = (valuation?.currentAllocations?.STOCK ?? 0) * 100;
  const realGoldWeight = (valuation?.currentAllocations?.GOLD ?? 0) * 100;
  const realSavingsWeight = (valuation?.currentAllocations?.SAVINGS ?? 0) * 100;
  const realCashWeight = (valuation?.currentAllocations?.CASH ?? 0) * 100;

  const isTAAActive = Math.abs(currentStockTarget - 50.0) < 1.0;

  // Handle 1-Click Apply TAA (+10% Stock, funded from Savings)
  const handleApplyTAA = async () => {
    setIsApplyingTAA(true);
    try {
      await updatePortfolioTargets({
        stock: 0.50,
        gold: 0.20,
        savings: 0.20,
        cash: 0.10,
      });
      toast.success(
        'Đã kích hoạt tỷ trọng chiến thuật TAA: Cổ phiếu 50% (+10%), Vàng 20%, Tiết kiệm 20%, Tiền mặt 10%!',
        'Áp dụng TAA thành công'
      );
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err: any) {
      toast.error(err.message || 'Lỗi áp dụng TAA', 'Thất bại');
    } finally {
      setIsApplyingTAA(false);
    }
  };

  // Handle Reset to Strategic Asset Allocation (SAA)
  const handleResetSAA = async () => {
    setIsResettingSAA(true);
    try {
      await updatePortfolioTargets({
        stock: 0.40,
        gold: 0.20,
        savings: 0.30,
        cash: 0.10,
      });
      toast.success(
        'Đã khôi phục tỷ trọng chiến lược SAA chuẩn: Cổ phiếu 40%, Vàng 20%, Tiết kiệm 30%, Tiền mặt 10%!',
        'Khôi phục SAA thành công'
      );
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err: any) {
      toast.error(err.message || 'Lỗi khôi phục SAA', 'Thất bại');
    } finally {
      setIsResettingSAA(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header Banner */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 lg:p-8 shadow-xs relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-3xl">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-accent-emerald-light border border-accent-emerald/30 flex items-center justify-center text-accent-emerald shadow-2xs">
                <Sparkles className="w-4 h-4" />
              </span>
              <span className="text-xs uppercase tracking-wider font-extrabold text-accent-emerald">
                Tactical Asset Allocation (TAA)
              </span>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald font-bold border border-accent-emerald/30">
                Machine Learning ONNX T+20
              </span>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-text-primary tracking-tight">
              Phân Bổ Chiến Thuật Động (TAA) & Điều Phối Dòng Vốn
            </h2>
            <p className="text-xs text-text-secondary leading-relaxed">
              Chiến lược TAA chủ động tinh chỉnh trọng số tài sản trong chu kỳ ngắn hạn ($T+20$) dựa trên tín hiệu nhận diện pha thị trường của mô hình học máy ONNX, trong khi vẫn neo chặt vào khuôn khổ kiểm soát rủi ro của danh mục Markowitz MVO và Khung an toàn (Safety Collar ±15%).
            </p>
          </div>

          {/* Model Signal Pill */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle flex flex-col items-start gap-2 shrink-0 lg:min-w-[260px]">
            <div className="flex items-center justify-between w-full">
              <span className="text-[10px] uppercase font-bold text-text-muted">Tín Hiệu Radar ML</span>
              <span className="flex h-2 w-2 rounded-full bg-accent-emerald animate-pulse"></span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-accent-emerald shrink-0" />
              <div>
                <span className="text-sm font-black text-accent-emerald block leading-tight">
                  Tích Lũy Tăng Trưởng
                </span>
                <span className="text-[11px] text-text-secondary font-mono-num">
                  Xác suất T+20: <strong className="text-accent-emerald">78.4% Tăng</strong>
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Strategy Comparison: SAA vs TAA */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SAA Card */}
        <div className={`p-6 rounded-2xl border transition-all ${
          !isTAAActive
            ? 'bg-surface-container-lowest border-accent-blue/40 shadow-sm'
            : 'bg-surface-container-lowest border-border-subtle opacity-90'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-accent-blue" />
              <h3 className="text-sm font-bold text-text-primary">Chiến Lược Dài Hạn (SAA)</h3>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
              !isTAAActive
                ? 'bg-accent-blue-light text-accent-blue border border-accent-blue/30'
                : 'bg-surface-container-high text-text-muted'
            }`}>
              {!isTAAActive ? 'Đang kích hoạt' : 'Chuẩn MiFID II'}
            </span>
          </div>
          <p className="text-xs text-text-secondary mb-4 leading-relaxed">
            Dựa trên kết quả khảo sát khẩu vị rủi ro cá nhân (Khẩu vị: <strong>{profile?.riskProfile || 'Bảo thủ'}</strong>, λ = {profile?.riskAversionLambda?.toFixed(2) || '3.88'}). Đảm bảo bảo toàn vốn và tăng trưởng ổn định đa năm.
          </p>

          <div className="grid grid-cols-4 gap-2 mb-5 text-center">
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Cổ phiếu</span>
              <span className="text-xs font-mono-num font-bold text-accent-blue">40.0%</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Vàng SJC</span>
              <span className="text-xs font-mono-num font-bold text-accent-gold">20.0%</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiết kiệm</span>
              <span className="text-xs font-mono-num font-bold text-indigo-500">30.0%</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiền mặt</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">10.0%</span>
            </div>
          </div>

          <button
            onClick={handleResetSAA}
            disabled={isResettingSAA || !isTAAActive}
            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              !isTAAActive
                ? 'bg-surface-container-high text-text-muted cursor-not-allowed border border-border-subtle'
                : 'bg-surface-container-low hover:bg-surface-container text-text-primary border border-border-subtle cursor-pointer active:scale-98'
            }`}
          >
            {isResettingSAA ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Đang Khôi Phục SAA...
              </>
            ) : !isTAAActive ? (
              <>
                <Check className="w-3.5 h-3.5 text-accent-blue" />
                Đang Sử Dụng Tỷ Trọng Chuẩn SAA
              </>
            ) : (
              <>
                <RotateCcw className="w-3.5 h-3.5" />
                Khôi Phục Chuẩn SAA (40% CP | 20% Vàng)
              </>
            )}
          </button>
        </div>

        {/* TAA Card */}
        <div className={`p-6 rounded-2xl border transition-all ${
          isTAAActive
            ? 'bg-surface-container-lowest border-accent-emerald shadow-sm'
            : 'bg-surface-container-lowest border-accent-emerald/40'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent-emerald" />
              <h3 className="text-sm font-bold text-text-primary">Chiến Thuật Học Máy (TAA)</h3>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
              isTAAActive
                ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30'
                : 'bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30'
            }`}>
              {isTAAActive ? 'Đang kích hoạt' : 'Khuyến nghị T+20'}
            </span>
          </div>
          <p className="text-xs text-text-secondary mb-4 leading-relaxed">
            Dựa trên xác suất <strong>78.4% tăng trưởng</strong> của rổ VN30. Tận dụng dòng tiền tiết kiệm thanh khoản để gia tăng <strong>+10% cổ phiếu</strong>, trong khi vẫn giữ nguyên mốc neo phòng hộ an toàn của <strong>Vàng SJC (20%)</strong>.
          </p>

          <div className="grid grid-cols-4 gap-2 mb-5 text-center">
            <div className="p-2.5 rounded-lg bg-accent-emerald/5 border border-accent-emerald/30">
              <span className="text-[10px] text-text-muted block font-medium">Cổ phiếu</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">50.0% (+10%)</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Vàng SJC</span>
              <span className="text-xs font-mono-num font-bold text-accent-gold">20.0% (Giữ)</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiết kiệm</span>
              <span className="text-xs font-mono-num font-bold text-indigo-500">20.0% (-10%)</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiền mặt</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">10.0%</span>
            </div>
          </div>

          <button
            onClick={handleApplyTAA}
            disabled={isApplyingTAA || isTAAActive}
            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              isTAAActive
                ? 'bg-surface-container-high text-accent-emerald font-bold cursor-not-allowed border border-border-subtle'
                : 'bg-accent-emerald hover:bg-emerald-600 text-white cursor-pointer shadow-sm active:scale-98'
            }`}
          >
            {isApplyingTAA ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Đang Cập Nhật Tỷ Trọng TAA...
              </>
            ) : isTAAActive ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald" />
                Đã Kích Hoạt TAA (50% Cổ Phiếu)
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Áp Dụng TAA (+10% Cổ Phiếu VN30)
              </>
            )}
          </button>
        </div>
      </section>

      {/* 3. Multi-Asset Breakdown & Roles */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-4">
          <div>
            <h3 className="text-base font-bold text-text-primary tracking-tight">
              Phân Rã 4 Lớp Tài Sản & Cơ Chế Phòng Hộ
            </h3>
            <p className="text-xs text-text-secondary">
              Mỗi lớp tài sản đảm nhiệm vai trò riêng biệt trong cấu trúc tài chính toàn diện
            </p>
          </div>
          <span className="text-xs font-bold text-accent-emerald bg-accent-emerald-light px-3 py-1 rounded-full border border-accent-emerald/20 self-start sm:self-auto">
            Khung kiểm soát Collar: ±15% Max Drift
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Asset 1: Cổ phiếu VN30 */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary">Cổ Phiếu VN30</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent-blue-light text-accent-blue">
                Risk-On Growth
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Tỷ trọng thực tế:</span>
                <span className="font-mono-num font-bold text-text-primary">{realStockWeight.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Mục tiêu hiện hành:</span>
                <span className="font-mono-num font-bold text-accent-blue">{currentStockTarget.toFixed(1)}%</span>
              </div>
            </div>
            <p className="text-[11px] text-text-secondary leading-snug pt-1 border-t border-border-subtle">
              Động cơ tạo Alpha sinh lời chính. Khi mô hình ONNX dự báo xác suất tăng 78.4%, tỷ trọng được nâng lên 50%.
            </p>
          </div>

          {/* Asset 2: Vàng SJC */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary">Vàng Miếng SJC</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent-gold-light text-accent-gold">
                Safe-Haven (ρ = -0.15)
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Tỷ trọng thực tế:</span>
                <span className="font-mono-num font-bold text-text-primary">{realGoldWeight.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Mục tiêu hiện hành:</span>
                <span className="font-mono-num font-bold text-accent-gold">{currentGoldTarget.toFixed(1)}%</span>
              </div>
            </div>
            <p className="text-[11px] text-text-secondary leading-snug pt-1 border-t border-border-subtle">
              Tài sản phòng hộ rủi ro lạm phát và sốc địa chính trị. Tương quan âm nhẹ với cổ phiếu, luôn giữ vững 20%.
            </p>
          </div>

          {/* Asset 3: Tiền gửi tiết kiệm */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary">Tiền Gửi Tiết Kiệm</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-400">
                Funding Reserve
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Tỷ trọng thực tế:</span>
                <span className="font-mono-num font-bold text-text-primary">{realSavingsWeight.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Mục tiêu hiện hành:</span>
                <span className="font-mono-num font-bold text-indigo-500">{currentSavingsTarget.toFixed(1)}%</span>
              </div>
            </div>
            <p className="text-[11px] text-text-secondary leading-snug pt-1 border-t border-border-subtle">
              Lãi suất cố định 5.5%/năm. Đóng vai trò bể chứa vốn để trích chuyển sang cổ phiếu khi có cơ hội TAA.
            </p>
          </div>

          {/* Asset 4: Tiền mặt khả dụng */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary">Tiền Mặt Ví VND</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent-emerald-light text-accent-emerald">
                Liquidity Buffer
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Tỷ trọng thực tế:</span>
                <span className="font-mono-num font-bold text-text-primary">{realCashWeight.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Mục tiêu hiện hành:</span>
                <span className="font-mono-num font-bold text-accent-emerald">{currentCashTarget.toFixed(1)}%</span>
              </div>
            </div>
            <p className="text-[11px] text-text-secondary leading-snug pt-1 border-t border-border-subtle">
              Đệm thanh khoản tức thời 10% để thực thi các lệnh tái cơ cấu và đảm bảo khả năng chi trả tức thì.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Execution Plan & Action Card */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-4">
          <div>
            <h3 className="text-base font-bold text-text-primary tracking-tight">
              Kế Hoạch Tái Cơ Cấu Danh Mục (Rebalance Execution Plan)
            </h3>
            <p className="text-xs text-text-secondary">
              Các lệnh giao dịch cụ thể được tính toán tự động để khớp tỷ trọng thực tế về mục tiêu
            </p>
          </div>

          {plan?.driftDetected ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/15 text-amber-500 text-xs font-bold border border-amber-500/30">
              <AlertTriangle className="w-3.5 h-3.5" />
              Độ lệch lớn nhất: +{plan.maxDriftPercent.toFixed(1)}% (Cần Tái Cơ Cấu)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/30">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Danh mục nằm trong vùng cân bằng tối ưu
            </span>
          )}
        </div>

        {plan?.actions && plan.actions.length > 0 ? (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border-subtle text-text-muted">
                    <th className="py-2.5 px-3 font-semibold">Loại Lệnh</th>
                    <th className="py-2.5 px-3 font-semibold">Tài Sản</th>
                    <th className="py-2.5 px-3 font-semibold">Khối Lượng</th>
                    <th className="py-2.5 px-3 font-semibold">Giá Dự Tính</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Tổng Giá Trị</th>
                    <th className="py-2.5 px-3 font-semibold">Ghi Chú</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {plan.actions.map((act, idx) => (
                    <tr key={idx} className="hover:bg-surface-container-low/50 transition-colors">
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          act.actionType === 'BUY'
                            ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/20'
                            : act.actionType === 'SELL'
                            ? 'bg-accent-rose-light text-accent-rose border border-accent-rose/20'
                            : 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20'
                        }`}>
                          {act.actionType === 'OPEN_SAVINGS' ? 'GỬI TIẾT KIỆM' : act.actionType}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-bold text-text-primary font-mono-num">
                        {act.ticker}
                      </td>
                      <td className="py-3 px-3 font-mono-num text-text-primary font-semibold">
                        {act.roundedQuantity.toLocaleString()} {act.ticker === 'GOLD_SJC' ? 'chỉ' : 'CP'}
                      </td>
                      <td className="py-3 px-3 font-mono-num text-text-secondary">
                        {formatVND(act.estimatedPrice)}
                      </td>
                      <td className="py-3 px-3 font-mono-num font-bold text-text-primary text-right">
                        {formatVND(act.estimatedTotalMoney)}
                      </td>
                      <td className="py-3 px-3 text-text-muted text-[11px]">
                        {act.note}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Execute Button */}
            <div className="pt-3 border-t border-border-subtle flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-text-secondary">
                Tổng cộng <strong>{plan.actions.length} lệnh</strong> điều phối tài sản sẽ được ghi nhận vào Sổ Cái Kép ACID.
              </span>
              <button
                onClick={onConfirmRebalance}
                disabled={executing}
                className={`py-3 px-6 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer ${
                  executing
                    ? 'bg-accent-emerald/50 text-white cursor-not-allowed'
                    : 'bg-accent-emerald hover:bg-emerald-600 text-white active:scale-98'
                }`}
              >
                {executing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Đang thực hiện tái cơ cấu...</span>
                  </>
                ) : (
                  <>
                    <ArrowRight className="w-4 h-4" />
                    <span>Thực Hiện Tái Cơ Cấu Danh Mục Ngay</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-accent-emerald-light border border-accent-emerald/30 text-accent-emerald flex items-center justify-center mx-auto">
              <Check className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-bold text-text-primary">Danh Mục Đang Ở Trạng Thái Cân Bằng Tối Ưu</h4>
            <p className="text-xs text-text-muted max-w-md mx-auto">
              Tất cả các lớp tài sản đều nằm trong ngưỡng an toàn ({plan?.maxDriftPercent.toFixed(1) || '0.0'}% drift &lt; 5%). Không cần thực hiện lệnh mua bán.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
