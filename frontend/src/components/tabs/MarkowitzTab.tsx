import { RebalancePlan } from '../../types';
import { formatVND } from '../../utils/formatters';

interface MarkowitzTabProps {
  plan: RebalancePlan | null;
}

export function MarkowitzTab({ plan }: MarkowitzTabProps) {
  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
      <div className="border-b border-border-subtle pb-4">
        <h2 className="text-lg font-bold text-text-primary tracking-tight">Bộ Tối Ưu Hóa Danh Mục Markowitz (MVO & TAA)</h2>
        <p className="text-xs text-text-secondary">Kết hợp hệ số ngại rủi ro cá nhân (λ = 3.88) với dự báo xu hướng máy học chu kỳ T+20</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
          <span className="text-xs text-text-muted uppercase font-bold">Mô Hình Toán Học</span>
          <div className="text-sm font-bold text-text-primary mt-1 font-mono">max U = w^T μ - 0.5 λ w^T Σ w</div>
          <p className="text-[11px] text-text-secondary mt-1">Giải bài toán Quadratic Programming tìm vector tỷ trọng tối ưu</p>
        </div>
        <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
          <span className="text-xs text-text-muted uppercase font-bold">Ràng Buộc Sàn HOSE</span>
          <div className="text-sm font-bold text-accent-emerald mt-1">Lô Chẵn 100 Cổ Phiếu</div>
          <p className="text-[11px] text-text-secondary mt-1">Tự động làm tròn khối lượng khớp lệnh thực tế, chuyển tiền lẻ về ví</p>
        </div>
        <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
          <span className="text-xs text-text-muted uppercase font-bold">Biên Độ An Toàn (Collars)</span>
          <div className="text-sm font-bold text-accent-gold mt-1">±15% Quanh SAA</div>
          <p className="text-[11px] text-text-secondary mt-1">Ngăn chặn rủi ro tất tay (All-in), duy trì đệm thanh khoản tiền gửi</p>
        </div>
      </div>

      {/* Rebalance Plan Summary */}
      <div className="p-5 rounded-xl border border-accent-emerald/30 bg-accent-emerald-light/30">
        <h4 className="text-sm font-bold text-text-primary mb-2">Đề Xuất Kế Hoạch Tái Cơ Cấu TAA</h4>
        <p className="text-xs text-text-secondary leading-relaxed mb-4">
          {plan?.executiveSummary || 'Hệ thống đang theo dõi độ lệch danh mục so với mốc neo mục tiêu.'}
        </p>
        <div className="space-y-2">
          {plan?.actions.map((act, i) => (
            <div key={i} className="p-3 rounded-lg bg-white border border-border-subtle flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                  act.actionType === 'SELL' ? 'bg-accent-rose-light text-accent-rose' : 'bg-accent-emerald-light text-accent-emerald'
                }`}>
                  {act.actionType}
                </span>
                <span className="font-bold text-text-primary">{act.ticker}</span>
                <span className="text-text-muted">({act.assetName})</span>
              </div>
              <div className="text-right">
                <span className="font-bold text-text-primary">{act.roundedQuantity.toLocaleString()} đơn vị</span>
                <span className="block text-[11px] text-text-muted">Ước tính: {formatVND(act.estimatedTotalMoney)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
