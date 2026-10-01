export function SavingsTab() {
  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary tracking-tight">Sổ Tiền Gửi Tiết Kiệm & Động Cơ Lãi Kép</h2>
          <p className="text-xs text-text-secondary">Batch Job tự động tính lãi tích lũy hàng ngày và tái tục gốc + lãi khi đáo hạn</p>
        </div>
        <div className="text-right">
          <span className="text-xs font-bold text-accent-emerald bg-accent-emerald-light px-3 py-1 rounded-full border border-accent-emerald/30">
            Lãi kép tự động (Auto-Rollover)
          </span>
        </div>
      </div>

      {/* Savings Details */}
      <div className="p-5 rounded-xl border border-border-subtle bg-surface-container-low flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-text-primary">Vietcombank - Sổ 01</span>
            <span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">ACTIVE</span>
          </div>
          <p className="text-xs text-text-secondary mt-1">Kỳ hạn: 6 Tháng • Lãi suất: 5.50%/năm • Đáo hạn: 12/04/2026</p>
        </div>
        <div className="text-right">
          <span className="text-xs text-text-muted uppercase font-bold">Số tiền gốc</span>
          <div className="text-lg font-extrabold text-text-primary">300,000,000 ₫</div>
          <span className="text-xs text-accent-gold font-bold">Lãi lũy kế: +4,075,000 ₫</span>
        </div>
      </div>
    </div>
  );
}
