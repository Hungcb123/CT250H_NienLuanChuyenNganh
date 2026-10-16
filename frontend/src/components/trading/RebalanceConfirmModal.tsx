import { useState } from 'react';
import {
  X, AlertTriangle, PiggyBank, RefreshCw, ShieldCheck
} from 'lucide-react';
import { RebalancePlan } from '../../types';
import { formatVND } from '../../utils/formatters';

interface RebalanceConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  plan: RebalancePlan | null;
  executing: boolean;
}

export function RebalanceConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  plan,
  executing
}: RebalanceConfirmModalProps) {
  const [acknowledged, setAcknowledged] = useState(false);

  if (!isOpen || !plan) return null;

  const settleActions = plan.actions?.filter(a => a.actionType === 'SETTLE_SAVINGS') || [];
  const sellActions = plan.actions?.filter(a => a.actionType === 'SELL') || [];
  const buyActions = plan.actions?.filter(a => a.actionType === 'BUY') || [];
  const openSavingsActions = plan.actions?.filter(a => a.actionType === 'OPEN_SAVINGS') || [];

  const hasEarlySettlement = settleActions.length > 0;
  const totalSettleMoney = settleActions.reduce((sum, a) => sum + (a.estimatedTotalMoney || 0), 0);
  const totalFeesAndTax = (plan.totalEstimatedFees || 0) + (plan.totalEstimatedTax || 0);

  const handleConfirmClick = async () => {
    await onConfirm();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-surface-container-lowest border border-border-subtle rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-amber-500/15 via-primary/10 to-transparent p-5 pb-4 border-b border-border-subtle relative shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={executing}
            className="absolute top-4 right-4 p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-container transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl text-white shadow-sm ${hasEarlySettlement ? 'bg-amber-500' : 'bg-accent-emerald'}`}>
              {hasEarlySettlement ? <AlertTriangle className="w-5 h-5" /> : <RefreshCw className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-base font-bold text-text-primary">
                Xác nhận Tái cơ cấu danh mục
              </h3>
              <p className="text-xs text-text-muted">
                Điều phối {plan.actions?.length || 0} lệnh tài sản về vùng tỷ trọng tối ưu
              </p>
            </div>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Early Settlement Warning Banner */}
          {hasEarlySettlement && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-500 space-y-2.5">
              <div className="flex items-center gap-2 font-bold text-xs">
                <PiggyBank className="w-4 h-4 shrink-0 text-amber-500" />
                <span>Lưu ý: Kế hoạch yêu cầu tất toán trước hạn {settleActions.length} sổ tiết kiệm</span>
              </div>
              <p className="text-[11px] text-text-secondary leading-relaxed">
                Để có đủ tiền mặt mua Vàng/Cổ phiếu đang thiếu hụt, hệ thống sẽ tất toán sổ tiết kiệm gần ngày đáo hạn nhất với tổng vốn gốc thu hồi là{' '}
                <strong className="text-text-primary font-mono-num font-bold">{formatVND(totalSettleMoney)}</strong>.
                Rút trước ngày đáo hạn có thể khiến bạn chỉ nhận mức lãi suất không kỳ hạn (0.1% - 0.2%/năm) thay vì lãi suất kỳ hạn cam kết ban đầu.
              </p>

              {/* List of savings being settled */}
              <div className="space-y-1.5 pt-1">
                {settleActions.map((act, idx) => (
                  <div key={idx} className="p-2 rounded-lg bg-surface-container-low/70 border border-amber-500/20 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-extrabold text-text-primary block font-mono-num">
                        Sổ #{act.ticker}
                      </span>
                      <span className="text-[10px] text-text-muted">{act.note || act.assetName}</span>
                    </div>
                    <span className="font-bold font-mono-num text-amber-500">
                      +{formatVND(act.estimatedTotalMoney)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Acknowledgment Checkbox */}
              <label className="flex items-start gap-2 pt-1 text-[11px] text-text-primary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={acknowledged}
                  onChange={(e) => setAcknowledged(e.target.checked)}
                  className="mt-0.5 rounded border-border-subtle text-amber-500 focus:ring-amber-500"
                />
                <span className="font-semibold text-text-secondary">
                  Tôi đã hiểu và chấp nhận tất toán trước hạn để nạp tiền vào ví tái cơ cấu danh mục.
                </span>
              </label>
            </div>
          )}

          {/* Action Breakdown Summary */}
          <div className="space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted block">
              Trình tự thực thi liên hoàn 4 pha (ACID Ledger):
            </span>
            <div className="space-y-1.5">
              {sellActions.length > 0 && (
                <div className="p-2.5 rounded-xl bg-surface-container-low border border-border-subtle flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-md bg-accent-rose-light text-accent-rose flex items-center justify-center font-bold text-[10px]">
                      1
                    </span>
                    <span className="text-text-secondary">Bán cổ phiếu/vàng vượt tỷ trọng ({sellActions.length} lệnh):</span>
                  </div>
                  <span className="font-bold font-mono-num text-accent-emerald">
                    +{formatVND(sellActions.reduce((s, a) => s + (a.estimatedTotalMoney || 0), 0))}
                  </span>
                </div>
              )}

              {settleActions.length > 0 && (
                <div className="p-2.5 rounded-xl bg-surface-container-low border border-border-subtle flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-md bg-amber-500/15 text-amber-500 flex items-center justify-center font-bold text-[10px]">
                      2
                    </span>
                    <span className="text-text-secondary">Tất toán sổ tiết kiệm nạp vào ví ({settleActions.length} sổ):</span>
                  </div>
                  <span className="font-bold font-mono-num text-amber-500">
                    +{formatVND(totalSettleMoney)}
                  </span>
                </div>
              )}

              {buyActions.length > 0 && (
                <div className="p-2.5 rounded-xl bg-surface-container-low border border-border-subtle flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-md bg-accent-emerald-light text-accent-emerald flex items-center justify-center font-bold text-[10px]">
                      3
                    </span>
                    <span className="text-text-secondary">Khớp lệnh mua tài sản thiếu hụt ({buyActions.length} lệnh):</span>
                  </div>
                  <span className="font-bold font-mono-num text-accent-rose">
                    -{formatVND(buyActions.reduce((s, a) => s + (a.estimatedTotalMoney || 0), 0))}
                  </span>
                </div>
              )}

              {openSavingsActions.length > 0 && (
                <div className="p-2.5 rounded-xl bg-surface-container-low border border-border-subtle flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-md bg-indigo-500/15 text-indigo-400 flex items-center justify-center font-bold text-[10px]">
                      4
                    </span>
                    <span className="text-text-secondary">Mở sổ tiết kiệm mới từ tiền mặt dôi dư:</span>
                  </div>
                  <span className="font-bold font-mono-num text-indigo-400">
                    -{formatVND(openSavingsActions.reduce((s, a) => s + (a.estimatedTotalMoney || 0), 0))}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Financial Totals */}
          <div className="p-3 rounded-xl bg-surface-container-high/40 border border-border-subtle text-xs space-y-1.5">
            <div className="flex justify-between text-text-muted">
              <span>Ước tính phí giao dịch & thuế TNCN:</span>
              <span className="font-mono-num font-semibold text-text-secondary">
                {formatVND(totalFeesAndTax)}
              </span>
            </div>
            <div className="flex justify-between text-text-muted">
              <span>Độ lệch tỷ trọng tối đa khắc phục:</span>
              <span className="font-mono-num font-bold text-accent-emerald">
                {plan.maxDriftPercent.toFixed(1)}% &rarr; 0.0%
              </span>
            </div>
            <div className="flex justify-between pt-1.5 border-t border-border-subtle font-bold">
              <span className="text-text-primary">Biến động số dư tiền mặt ví:</span>
              <span className={`font-mono-num ${(plan.netCashImpact || 0) >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                {(plan.netCashImpact || 0) >= 0 ? '+' : ''}{formatVND(plan.netCashImpact || 0)}
              </span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-surface-container-low border-t border-border-subtle flex items-center justify-end gap-3 shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={executing}
            className="px-4 py-2 rounded-xl border border-border-subtle hover:bg-surface-container font-semibold text-xs text-text-secondary transition-all cursor-pointer disabled:opacity-50"
          >
            Hủy bỏ
          </button>
          <button
            type="button"
            onClick={handleConfirmClick}
            disabled={executing || (hasEarlySettlement && !acknowledged)}
            className={`px-5 py-2 rounded-xl font-bold text-xs text-white shadow-xs transition-all flex items-center gap-2 cursor-pointer ${
              hasEarlySettlement ? 'bg-amber-500 hover:bg-amber-600' : 'bg-accent-emerald hover:bg-emerald-600'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {executing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <span>Đang thực hiện tái cơ cấu...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Xác nhận & Khớp lệnh ngay</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
