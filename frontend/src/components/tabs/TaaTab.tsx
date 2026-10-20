import { useState } from 'react';
import { saveAllocationPreference } from '../../services/api';
import {
  Sparkles, Shield, RefreshCw, CheckCircle2,
  AlertTriangle, ArrowRight, Check
} from 'lucide-react';
import { RebalancePlan, UserProfile, PortfolioValuation } from '../../types';
import { formatVND } from '../../utils/formatters';
import { regimeLabel, regimeScore, regimeScoreLabel } from '../../utils/regimeDisplay';
import { CustomTargetsModal } from '../profile/CustomTargetsModal';
import { RegimeIndicator } from '../market/RegimeIndicator';
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
  const [saaOpen, setSaaOpen] = useState(false);
  const [savingPreference, setSavingPreference] = useState(false);
  const changePreference = async (mode: 'SAA' | 'TAA', horizon: number) => {
    setSavingPreference(true);
    try {
      await saveAllocationPreference(mode, horizon);
      await onRefreshData?.();
      toast.success('Đã lưu chế độ. Xem kế hoạch và xác nhận để thực hiện giao dịch.');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Không lưu được chế độ'); }
    finally { setSavingPreference(false); }
  };
  const [isApplyingTAA, setIsApplyingTAA] = useState(false);

  if (!plan) return (
    <section className="vnx-panel p-6 space-y-3">
      <h2 className="text-lg font-bold text-text-primary">Chưa có dữ liệu kế hoạch</h2>
      <p className="text-sm text-text-secondary">Tải dữ liệu danh mục để xem tỷ trọng và kế hoạch tái cân bằng.</p>
      {onRefreshData && <button onClick={() => void onRefreshData()} className="rounded-lg border border-border-subtle px-3 py-2 text-sm text-text-primary hover:bg-surface-container">Tải lại dữ liệu</button>}
    </section>
  );

  const currentStockTarget = ((plan?.targetAllocations?.STOCK ?? 0.40) * 100);
  const currentGoldTarget = ((plan?.targetAllocations?.GOLD ?? 0.20) * 100);
  const currentSavingsTarget = ((plan?.targetAllocations?.SAVINGS ?? 0.30) * 100);
  const currentCashTarget = ((plan?.targetAllocations?.CASH ?? 0.10) * 100);

  // SAA targets (mỏ neo gốc từ khảo sát)
  const saaStock = ((plan?.saaTargets?.STOCK ?? plan?.targetAllocations?.STOCK ?? 0.35) * 100);
  const saaGold = ((plan?.saaTargets?.GOLD ?? plan?.targetAllocations?.GOLD ?? 0.35) * 100);
  const saaSavings = ((plan?.saaTargets?.SAVINGS ?? plan?.targetAllocations?.SAVINGS ?? 0.20) * 100);
  const saaCash = ((plan?.saaTargets?.CASH ?? plan?.targetAllocations?.CASH ?? 0.10) * 100);

  // ML predictions
  const stockPrediction = plan?.mlPredictions?.find(p => p.assetClass === 'STOCK');
  const goldPrediction = plan?.mlPredictions?.find(p => p.assetClass === 'GOLD');
  const nativeStock = !!stockPrediction?.nativeForecast;

  // Real allocations from valuation
  const realStockWeight = (valuation?.currentAllocations?.STOCK ?? 0) * 100;
  const realGoldWeight = (valuation?.currentAllocations?.GOLD ?? 0) * 100;
  const realSavingsWeight = (valuation?.currentAllocations?.SAVINGS ?? 0) * 100;
  const realCashWeight = (valuation?.currentAllocations?.CASH ?? 0) * 100;

  const isTAAActive = plan.taaEnabled === true;
  const horizon = plan.horizonSessions ?? 20;
  const handleApplyTAA = async () => {
    setIsApplyingTAA(true);
    try { await onConfirmRebalance?.(); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Không mở được kế hoạch', 'Thất bại'); }
    finally { setIsApplyingTAA(false); }
  };

  return (
    <div className="space-y-6 pb-12">
      <section className="vnx-panel px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-text-primary">Tín hiệu thị trường</h2>
          <p className="text-xs text-text-secondary mt-0.5">Theo dõi dự báo và chọn phân bổ SAA hoặc TAA.</p>
        </div>
        <div className="shrink-0">
          <RegimeIndicator prediction={stockPrediction} />
          {plan?.taaEnabled === false && <p className="text-[11px] text-text-secondary mt-1">Đang dùng SAA</p>}
        </div>
      </section>

      <section aria-label="Chọn chế độ phân bổ" className="vnx-panel p-5 space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <fieldset disabled={savingPreference} className="flex flex-wrap gap-2">
            <legend className="text-sm font-semibold text-text-primary mb-2">Chế độ phân bổ</legend>
            {(['SAA', 'TAA'] as const).map(mode => <button key={mode} type="button"
              aria-pressed={(mode === 'TAA') === isTAAActive}
              onClick={() => void changePreference(mode, horizon)}
              className={`rounded-lg border px-4 py-2 text-sm font-semibold disabled:opacity-50 focus-visible:outline focus-visible:outline-2 ${((mode === 'TAA') === isTAAActive) ? 'bg-accent-emerald text-white border-accent-emerald' : 'border-border-subtle text-text-primary'}`}>
              Dùng {mode}
            </button>)}
          </fieldset>
          <label className="text-sm text-text-primary flex flex-col gap-2">Kỳ hạn dự báo
            <select aria-label="Kỳ hạn dự báo" disabled={savingPreference} value={horizon}
              onChange={event => void changePreference(isTAAActive ? 'TAA' : 'SAA', Number(event.target.value))}
              className="rounded-lg border border-border-subtle bg-surface-container-lowest px-3 py-2 disabled:opacity-50">
              {[20,60,120].map(value => <option key={value} value={value}>T+{value} phiên{value === 20 ? '' : ' · Thử nghiệm'}</option>)}
            </select>
          </label>
          {savingPreference && <span role="status" className="text-sm text-text-secondary">Đang lưu và tải kế hoạch…</span>}
        </div>
        <p className="text-xs text-text-secondary">Đổi chế độ không tự mua bán. T+60/T+120 dùng model riêng đang thử nghiệm, chưa có kết quả kiểm định; chưa có dự báo hợp lệ thì giữ SAA.</p>
        {isTAAActive && stockPrediction?.nativeForecast?.available === false && <p role="status" className="text-sm text-text-secondary">Đã bật TAA T+{horizon}, đang giữ SAA vì chưa có dự báo hợp lệ. Backend sẽ công bố dự báo sau khi đồng bộ và chạy model.</p>}
      </section>

      {plan.equityNotice && <p role="status" className="text-sm text-text-secondary">{plan.equityNotice}</p>}

      {/* 2. Strategy Comparison: SAA vs TAA */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SAA Card */}
        <div className="vnx-panel p-4 sm:p-6">
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

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5 text-left">
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Cổ phiếu</span>
              <span className="text-xs font-mono-num font-bold text-accent-blue">{saaStock.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Vàng SJC</span>
              <span className="text-xs font-mono-num font-bold text-accent-gold">{saaGold.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiết kiệm</span>
              <span className="text-xs font-mono-num font-bold text-indigo-500">{saaSavings.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiền mặt</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">{saaCash.toFixed(1)}%</span>
            </div>
          </div>

          <p className="text-xs text-text-secondary mb-3">SAA là tỷ trọng chiến lược bạn đã lưu. Chọn lại tỷ trọng tại đây; giao dịch chỉ diễn ra sau khi xác nhận kế hoạch.</p>
          <button type="button" onClick={() => setSaaOpen(true)} className="px-4 py-2 rounded-lg bg-accent-blue text-white text-sm font-semibold hover:opacity-90">Chỉnh tỷ trọng SAA</button>
        </div>

        {/* TAA Card */}
        <div className="vnx-panel p-4 sm:p-6">
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
              {isTAAActive ? `Đang bật · T+${horizon}` : 'Chưa bật TAA'}
            </span>
          </div>
          <p className="text-xs text-text-secondary mb-4 leading-relaxed">
            {nativeStock
              ? 'VNINDEX dùng lớp có score cao nhất để chọn hướng điều chỉnh ±10 điểm % cổ phiếu. Khi TAA tắt hoặc dự báo không hợp lệ, giữ SAA. Score chưa được hiệu chỉnh thành xác suất.'
              : 'Chỉ điều chỉnh từ ONNX hợp lệ và đúng loại tài sản. Model GC quốc tế không áp dụng cho vàng SJC.'}
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5 text-left">
            <div className="p-2.5 rounded-lg bg-accent-emerald/5 border border-accent-emerald/30">
              <span className="text-[10px] text-text-muted block font-medium">Cổ phiếu</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">{currentStockTarget.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Vàng SJC</span>
              <span className="text-xs font-mono-num font-bold text-accent-gold">{currentGoldTarget.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiết kiệm</span>
              <span className="text-xs font-mono-num font-bold text-indigo-500">{currentSavingsTarget.toFixed(1)}%</span>
            </div>
            <div className="py-3 border-b border-border-subtle">
              <span className="text-[10px] text-text-muted block font-medium">Tiền mặt</span>
              <span className="text-xs font-mono-num font-bold text-accent-emerald">{currentCashTarget.toFixed(1)}%</span>
            </div>
          </div>

          <button onClick={handleApplyTAA} disabled={isApplyingTAA || executing || !plan?.planToken || !plan.actions?.length}
            className="w-full py-2.5 px-4 rounded-xl text-sm font-semibold bg-accent-emerald text-white disabled:opacity-50 focus-visible:outline focus-visible:outline-2">
            {isApplyingTAA ? 'Đang mở kế hoạch…' : 'Xem và xác nhận kế hoạch tái cân bằng'}
          </button>
        </div>
      </section>

      {/* 2.5 ML Regime Predictions & 3-Column Allocation Comparison */}
      {plan?.mlPredictions && plan.mlPredictions.length > 0 && (
        <section className="vnx-panel p-6 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-accent-emerald" />
                <h3 className="text-base font-bold text-text-primary tracking-tight">
                  {`Dự Báo VNINDEX T+${horizon} & So Sánh Tỷ Trọng`}
                </h3>
              </div>
              <p className="text-xs text-text-secondary mt-1">
                {nativeStock ? 'Sử dụng dữ liệu phiên đã đóng cửa; lưu trạng thái dự báo giữa các phiên.' : 'Suy luận từ các chỉ báo giá đóng cửa theo hợp đồng ONNX.'}
              </p>
            </div>
            <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 self-start sm:self-auto">
              {nativeStock ? 'Score chưa hiệu chỉnh' : 'ONNX Runtime'}
            </span>
          </div>

          {/* Cards for ML Signal */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {plan.mlPredictions.map((ml) => (
              <div
                key={ml.assetClass}
                className={`p-4 rounded-xl border transition-all ${
                  ml.signal === 1
                    ? 'bg-accent-emerald/5 border-accent-emerald/30'
                    : ml.signal === -1
                    ? 'bg-accent-rose/5 border-accent-rose/30'
                    : 'bg-surface-container-low border-border-subtle'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-sm text-text-primary">
                    {ml.assetClass === 'STOCK' ? '📈 Cổ Phiếu (VNINDEX)' : '🥇 Vàng Miếng (SJC)'}
                  </span>
                  <span title={ml.modelName} className="text-[10px] font-mono font-medium text-text-muted px-2 py-0.5 rounded bg-surface-container border border-border-subtle">
                    {ml.nativeForecast ? `T+${ml.horizonSessions ?? 20}${(ml.horizonSessions ?? 20) === 20 ? ' · Ensemble' : ' · Thử nghiệm'}` : ml.modelName}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded-lg bg-surface-container-lowest border border-border-subtle">
                    <span className="text-[10px] text-text-muted block font-medium">Tín hiệu</span>
                    <strong
                      className={`text-xs block mt-0.5 ${
                        ml.signal === 1
                          ? 'text-accent-emerald'
                          : ml.signal === -1
                          ? 'text-accent-rose'
                          : 'text-amber-500'
                      }`}
                    >
                      {regimeLabel(ml)}
                    </strong>
                  </div>

                  <div className="p-2 rounded-lg bg-surface-container-lowest border border-border-subtle">
                    <span className="text-[10px] text-text-muted block font-medium">{regimeScoreLabel(ml)}</span>
                    <strong className="text-xs text-text-primary block mt-0.5 font-mono-num">
                      {regimeScore(ml)}
                    </strong>
                  </div>

                  <div className="p-2 rounded-lg bg-surface-container-lowest border border-border-subtle">
                    <span className="text-[10px] text-text-muted block font-medium">Dịch chuyển Δw</span>
                    <strong
                      className={`text-xs block mt-0.5 font-mono-num ${
                        ml.deltaWeight > 0
                          ? 'text-accent-emerald'
                          : ml.deltaWeight < 0
                          ? 'text-accent-rose'
                          : 'text-text-muted'
                      }`}
                    >
                      {ml.deltaWeight > 0 ? '+' : ''}
                      {(ml.deltaWeight * 100).toFixed(1)}%
                    </strong>
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-border-subtle flex items-center justify-between text-[11px] text-text-secondary">
                  <span>Trạng thái dự báo:</span>
                  <span className="font-semibold text-text-primary">{regimeLabel(ml)}</span>
                </div>
                {ml.nativeForecast?.available && (
                  <p className="mt-2 text-[11px] text-text-secondary break-words">
                    Ngày {ml.nativeForecast.session} · Giảm / đi ngang / tăng: {ml.nativeForecast.classScores.map(v => v.toFixed(3)).join(' / ')}.
                    {' '}TAA dùng hướng của lớp có score cao nhất; điểm xu hướng chỉ để tham khảo, chưa phải xác suất.
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* 3-Column Allocation Table */}
          <div className="overflow-x-auto rounded-xl border border-border-subtle">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-surface-container-low border-b border-border-subtle text-text-secondary">
                  <th className="text-left py-3 px-4 font-bold">Lớp Tài Sản</th>
                  <th className="text-center py-3 px-4 font-bold">SAA (Mỏ neo khảo sát)</th>
                  <th className="text-center py-3 px-4 font-bold text-accent-emerald">Mục tiêu theo chế độ đã chọn</th>
                  <th className="text-center py-3 px-4 font-bold">Tỷ Trọng Thực Tế</th>
                  <th className="text-center py-3 px-4 font-bold">Độ Lệch (Drift)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {(['STOCK', 'GOLD', 'SAVINGS', 'CASH'] as const).map((cls) => {
                  const saaVal = (plan?.saaTargets?.[cls] ?? 0) * 100;
                  const taaVal = (plan?.taaTargets?.[cls] ?? plan?.targetAllocations?.[cls] ?? 0) * 100;
                  const actualVal = (plan?.currentAllocations?.[cls] ?? 0) * 100;
                  const drift = actualVal - taaVal;

                  return (
                    <tr key={cls} className="hover:bg-surface-container-low/50 transition-colors">
                      <td className="py-3 px-4 font-bold text-text-primary">
                        {cls === 'STOCK'
                          ? '📈 Cổ Phiếu VN30'
                          : cls === 'GOLD'
                          ? '🥇 Vàng Miếng SJC'
                          : cls === 'SAVINGS'
                          ? '🏦 Tiền Gửi Tiết Kiệm'
                          : '💵 Tiền Mặt Khả Dụng'}
                      </td>
                      <td className="text-center py-3 px-4 font-mono-num font-semibold text-text-secondary">
                        {saaVal.toFixed(1)}%
                      </td>
                      <td
                        className={`text-center py-3 px-4 font-mono-num font-bold ${
                          taaVal > saaVal
                            ? 'text-accent-emerald'
                            : taaVal < saaVal
                            ? 'text-accent-rose'
                            : 'text-text-primary'
                        }`}
                      >
                        {taaVal.toFixed(1)}%
                        {taaVal !== saaVal && (
                          <span className="text-[10px] ml-1 opacity-75">
                            ({taaVal > saaVal ? '+' : ''}{(taaVal - saaVal).toFixed(1)}%)
                          </span>
                        )}
                      </td>
                      <td className="text-center py-3 px-4 font-mono-num font-semibold text-text-primary">
                        {actualVal.toFixed(1)}%
                      </td>
                      <td
                        className={`text-center py-3 px-4 font-mono-num font-bold ${
                          Math.abs(drift) > 5.0 ? 'text-accent-rose' : 'text-text-muted'
                        }`}
                      >
                        {drift > 0 ? '+' : ''}
                        {drift.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 3. Multi-Asset Breakdown & Roles */}
      <section className="vnx-panel p-6 space-y-4">
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
          <div className="vnx-detail p-4     space-y-3">
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
              {stockPrediction?.nativeForecast
                ? stockPrediction.nativeForecast.available
                  ? `Dự báo VNINDEX sau ${horizon} phiên, dữ liệu ngày ${stockPrediction.nativeForecast.session}. Điểm quyết định chưa hiệu chỉnh thành xác suất.`
                  : 'Dự báo chưa khả dụng. Danh mục giữ tỷ trọng chiến lược.'
                : stockPrediction ? `Mô hình ONNX: ${regimeLabel(stockPrediction)} (${regimeScore(stockPrediction)}).` : 'Chưa có dự báo để điều chỉnh tỷ trọng.'}
            </p>
          </div>

          {/* Asset 2: Vàng SJC */}
          <div className="vnx-detail p-4     space-y-3">
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
              Tài sản phòng hộ rủi ro lạm phát và sốc địa chính trị. {goldPrediction ? `Mô hình ONNX: ${goldPrediction.regimeName} (${(goldPrediction.confidence * 100).toFixed(0)}%).` : 'Tương quan âm nhẹ với cổ phiếu, luôn giữ vững mỏ neo.'}
            </p>
          </div>

          {/* Asset 3: Tiền gửi tiết kiệm */}
          <div className="vnx-detail p-4     space-y-3">
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
          <div className="vnx-detail p-4     space-y-3">
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
      <section className="vnx-panel p-6 space-y-5">
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
          ) : !plan ? (
            <span className="text-xs text-text-muted">Chưa có kế hoạch để đánh giá</span>
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
                    <th className="py-2.5 px-3 font-semibold text-right">Phí & Thuế</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Dòng Tiền Ròng</th>
                    <th className="py-2.5 px-3 font-semibold">Ghi Chú</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {plan.actions.map((act, idx) => {
                    const feeAndTax = (act.estimatedFee || 0) + (act.estimatedTax || 0);
                    const netCash = act.netMoney !== undefined ? act.netMoney : act.estimatedTotalMoney;
                    return (
                      <tr key={idx} className="hover:bg-surface-container-low/50 transition-colors">
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            act.actionType === 'BUY'
                              ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/20'
                              : act.actionType === 'SELL'
                              ? 'bg-accent-rose-light text-accent-rose border border-accent-rose/20'
                              : act.actionType === 'SETTLE_SAVINGS'
                              ? 'bg-amber-500/15 text-amber-500 border border-amber-500/20'
                              : 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20'
                          }`}>
                            {act.actionType === 'OPEN_SAVINGS' ? 'GỬI TIẾT KIỆM' :
                             act.actionType === 'SETTLE_SAVINGS' ? 'TẤT TOÁN SỔ' : act.actionType}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-bold text-text-primary font-mono-num">
                          {act.actionType === 'SETTLE_SAVINGS' ? `Sổ #${act.ticker}` : act.ticker}
                        </td>
                        <td className="py-3 px-3 font-mono-num text-text-primary font-semibold">
                          {act.actionType === 'SETTLE_SAVINGS' || act.actionType === 'OPEN_SAVINGS'
                            ? '-'
                            : `${act.roundedQuantity.toLocaleString()} ${act.ticker === 'GOLD_SJC' || act.assetClass === 'GOLD' ? 'chỉ' : 'CP'}`}
                        </td>
                        <td className="py-3 px-3 font-mono-num text-text-secondary">
                          {formatVND(act.estimatedPrice)}
                        </td>
                        <td className="py-3 px-3 font-mono-num font-bold text-text-primary text-right">
                          {formatVND(act.estimatedTotalMoney)}
                        </td>
                        <td className="py-3 px-3 font-mono-num text-text-muted text-right text-[11px]">
                          {feeAndTax > 0 ? formatVND(feeAndTax) : '-'}
                        </td>
                        <td className="py-3 px-3 font-mono-num font-bold text-right text-xs">
                          <span className={act.actionType === 'SELL' || act.actionType === 'SETTLE_SAVINGS' ? 'text-accent-emerald' : act.actionType === 'BUY' ? 'text-accent-rose' : 'text-text-primary'}>
                            {act.actionType === 'SELL' || act.actionType === 'SETTLE_SAVINGS' ? '+' : act.actionType === 'BUY' ? '-' : ''}{formatVND(Math.abs(netCash))}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-text-muted text-[11px]">
                          {act.note}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Fee & Tax Transparency Summary Bar */}
            {((plan.totalEstimatedFees || 0) > 0 || (plan.totalEstimatedTax || 0) > 0) && (
              <div className="vnx-detail grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5     text-xs">
                <div>
                  <span className="text-text-muted text-[11px] block">Phí Môi Giới (0.1% Mua/Bán):</span>
                  <span className="font-mono-num font-bold text-text-primary">{formatVND(plan.totalEstimatedFees || 0)}</span>
                </div>
                <div>
                  <span className="text-text-muted text-[11px] block">Thuế TNCN Bán CK (0.1%):</span>
                  <span className="font-mono-num font-bold text-text-primary">{formatVND(plan.totalEstimatedTax || 0)}</span>
                </div>
                <div>
                  <span className="text-text-muted text-[11px] block">Tác Động Tiền Mặt Ròng:</span>
                  <span className={`font-mono-num font-bold ${(plan.netCashImpact || 0) >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                    {(plan.netCashImpact || 0) >= 0 ? '+' : ''}{formatVND(plan.netCashImpact || 0)}
                  </span>
                </div>
              </div>
            )}

            {/* Execute Button */}
            <div className="pt-3 border-t border-border-subtle flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-text-secondary">
                Tổng cộng <strong>{plan.actions.length} lệnh</strong> điều phối tài sản sẽ được ghi nhận vào Sổ Cái Kép ACID (đã khấu trừ phí & thuế).
              </span>
              <button
                onClick={onConfirmRebalance}
                disabled={executing || !plan.planToken}
                className={`py-3 px-6 rounded-xl font-bold text-xs flex items-center justify-center gap-2  transition-all cursor-pointer ${
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
            <div className={`w-12 h-12 rounded-full border flex items-center justify-center mx-auto ${plan.driftDetected ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'bg-accent-emerald-light border-accent-emerald/30 text-accent-emerald'}`}>
              {plan.driftDetected ? <AlertTriangle className="w-6 h-6" /> : <Check className="w-6 h-6" />}
            </div>
            <h4 className="text-sm font-bold text-text-primary">{!plan ? 'Chưa có dữ liệu kế hoạch' : plan.driftDetected ? 'Danh mục còn lệch, chưa có lệnh khả thi' : 'Danh mục nằm trong ngưỡng tái cân bằng'}</h4>
            <p className="text-xs text-text-muted max-w-md mx-auto">
              {!plan ? 'Tải dữ liệu danh mục để xem kế hoạch.' : plan.driftDetected
                ? `Độ lệch lớn nhất ${plan.maxDriftPercent.toFixed(1)}%. Tiền khả dụng hoặc quy mô lô giao dịch chưa đủ để tạo lệnh.`
                : `Độ lệch lớn nhất ${plan.maxDriftPercent.toFixed(1)}%, không vượt ngưỡng 5%. Chưa cần tái cân bằng.`}
            </p>
          </div>
        )}
      </section>
      <CustomTargetsModal
        isOpen={saaOpen}
        onClose={() => setSaaOpen(false)}
        currentTargets={{ stock: saaStock / 100, gold: saaGold / 100, savings: saaSavings / 100, cash: saaCash / 100 }}
        onSuccess={async () => {
          await onRefreshData?.();
          toast.success('Đã lưu tỷ trọng SAA. Xem kế hoạch mới trước khi xác nhận giao dịch.', 'Cập nhật SAA');
        }}
      />
    </div>
  );
}
