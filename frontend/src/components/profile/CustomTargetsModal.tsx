import React, { useState, useEffect } from 'react';
import { X, Sliders, CheckCircle, AlertTriangle, Sparkles, Scale, ShieldCheck, TrendingUp } from 'lucide-react';
import { updatePortfolioTargets } from '../../services/api';

interface CustomTargetsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTargets: {
    stock: number;
    gold: number;
    savings: number;
    cash: number;
  };
  onSuccess: () => Promise<void> | void;
}

export function CustomTargetsModal({
  isOpen,
  onClose,
  currentTargets,
  onSuccess,
}: CustomTargetsModalProps) {
  const [stock, setStock] = useState<number>(Math.round(currentTargets.stock * 100));
  const [gold, setGold] = useState<number>(Math.round(currentTargets.gold * 100));
  const [savings, setSavings] = useState<number>(Math.round(currentTargets.savings * 100));
  const [cash, setCash] = useState<number>(Math.round(currentTargets.cash * 100));
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStock(Math.round(currentTargets.stock * 100));
      setGold(Math.round(currentTargets.gold * 100));
      setSavings(Math.round(currentTargets.savings * 100));
      setCash(Math.round(currentTargets.cash * 100));
      setErrorMsg(null);
    }
  }, [isOpen, currentTargets]);

  if (!isOpen) return null;

  const total = stock + gold + savings + cash;
  const isValid = total === 100;

  const applyPreset = (s: number, g: number, sav: number, c: number) => {
    setStock(s);
    setGold(g);
    setSavings(sav);
    setCash(c);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      setErrorMsg(`Tổng tỷ trọng phải bằng chính xác 100% (Hiện tại: ${total}%)`);
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    try {
      await updatePortfolioTargets({
        stock: stock / 100,
        gold: gold / 100,
        savings: savings / 100,
        cash: cash / 100
      });
      await onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi khi lưu tỷ trọng mục tiêu');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        className="bg-surface-container-lowest rounded-2xl shadow-2xl border border-border-subtle w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-5 border-b border-border-subtle flex items-center justify-between bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent-emerald flex items-center justify-center text-white shadow-xs">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-text-primary tracking-tight">
                Tùy Chỉnh Tỷ Trọng Mục Tiêu SAA
              </h3>
              <p className="text-xs text-text-secondary font-medium">
                Mốc neo cân bằng 4 lớp tài sản: Cổ phiếu · Vàng · Tiết kiệm · Tiền mặt
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-text-muted hover:text-text-primary hover:bg-surface-container transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Quick Presets */}
          <div>
            <label className="block text-xs font-bold text-text-muted mb-2 uppercase tracking-wider">
              Khuyến Nghị Theo Khẩu Vị Rủi Ro (Presets)
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => applyPreset(15, 25, 45, 15)}
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl border border-border-subtle bg-surface-container-low hover:bg-surface-container text-text-primary text-xs font-bold transition-all cursor-pointer shadow-2xs"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span>Bảo thủ</span>
              </button>
              <button
                type="button"
                onClick={() => applyPreset(35, 35, 20, 10)}
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl border border-accent-emerald/40 bg-accent-emerald-light hover:bg-accent-emerald/20 text-accent-emerald text-xs font-bold transition-all cursor-pointer shadow-2xs"
              >
                <Scale className="w-3.5 h-3.5 text-accent-emerald shrink-0" />
                <span>Cân bằng</span>
              </button>
              <button
                type="button"
                onClick={() => applyPreset(60, 20, 15, 5)}
                className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl border border-border-subtle bg-surface-container-low hover:bg-surface-container text-text-primary text-xs font-bold transition-all cursor-pointer shadow-2xs"
              >
                <TrendingUp className="w-3.5 h-3.5 text-accent-gold shrink-0" />
                <span>Tăng trưởng</span>
              </button>
            </div>
          </div>

          {/* Allocation Preview Bar */}
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-bold text-text-primary">Trực quan hóa tỷ trọng:</span>
              <span className={`px-2 py-0.5 rounded-full font-bold text-[11px] font-mono-num flex items-center gap-1 ${
                isValid ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30' : 'bg-accent-gold-light text-accent-gold border border-accent-gold/30'
              }`}>
                {isValid ? (
                  <>
                    <CheckCircle className="w-3.5 h-3.5 text-accent-emerald" />
                    Tổng: 100% (Hợp lệ)
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-accent-gold" />
                    Tổng: {total}% ({total > 100 ? `Thừa +${total - 100}%` : `Thiếu -${100 - total}%`})
                  </>
                )}
              </span>
            </div>
            <div className="h-4 w-full rounded-full bg-surface-container overflow-hidden flex border border-border-subtle">
              <div 
                style={{ width: `${Math.max(0, Math.min(100, stock))}%` }} 
                className="bg-accent-emerald transition-all duration-150" 
                title={`Cổ phiếu: ${stock}%`} 
              />
              <div 
                style={{ width: `${Math.max(0, Math.min(100, gold))}%` }} 
                className="bg-accent-gold transition-all duration-150" 
                title={`Vàng: ${gold}%`} 
              />
              <div 
                style={{ width: `${Math.max(0, Math.min(100, savings))}%` }} 
                className="bg-indigo-500 transition-all duration-150" 
                title={`Tiết kiệm: ${savings}%`} 
              />
              <div 
                style={{ width: `${Math.max(0, Math.min(100, cash))}%` }} 
                className="bg-sky-500 transition-all duration-150" 
                title={`Tiền mặt: ${cash}%`} 
              />
            </div>
          </div>

          {/* Sliders Grid */}
          <div className="space-y-4 pt-1">
            {/* 1. Cổ phiếu VN30 */}
            <div className="p-3.5 rounded-xl border border-accent-emerald/30 bg-surface-container-low space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-accent-emerald"></span>
                  <span className="text-xs font-bold text-text-primary">Cổ phiếu VN30 (Tăng trưởng)</span>
                </div>
                <div className="flex items-center gap-1 font-mono-num">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={stock}
                    onChange={(e) => setStock(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                    className="w-14 px-2 py-0.5 rounded-lg border border-border-subtle text-right font-bold text-xs bg-surface-container text-text-primary focus:outline-accent-emerald"
                  />
                  <span className="text-xs text-text-muted font-bold">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={stock}
                onChange={(e) => setStock(Number(e.target.value))}
                className="w-full accent-accent-emerald cursor-pointer"
              />
            </div>

            {/* 2. Vàng SJC */}
            <div className="p-3.5 rounded-xl border border-accent-gold/30 bg-surface-container-low space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-accent-gold"></span>
                  <span className="text-xs font-bold text-text-primary">Vàng SJC 999.9 (Phòng vệ vĩ mô)</span>
                </div>
                <div className="flex items-center gap-1 font-mono-num">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={gold}
                    onChange={(e) => setGold(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                    className="w-14 px-2 py-0.5 rounded-lg border border-border-subtle text-right font-bold text-xs bg-surface-container text-text-primary focus:outline-accent-gold"
                  />
                  <span className="text-xs text-text-muted font-bold">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={gold}
                onChange={(e) => setGold(Number(e.target.value))}
                className="w-full accent-accent-gold cursor-pointer"
              />
            </div>

            {/* 3. Tiền gửi tiết kiệm */}
            <div className="p-3.5 rounded-xl border border-indigo-500/30 bg-surface-container-low space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-indigo-500"></span>
                  <div>
                    <span className="text-xs font-bold text-text-primary">Tiền gửi tiết kiệm (Lãi suất Rf)</span>
                    <span className="text-[10px] text-text-muted block">Sinh lời cố định 5.0% - 7.0%/năm</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 font-mono-num">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={savings}
                    onChange={(e) => setSavings(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                    className="w-14 px-2 py-0.5 rounded-lg border border-border-subtle text-right font-bold text-xs bg-surface-container text-text-primary focus:outline-indigo-500"
                  />
                  <span className="text-xs text-text-muted font-bold">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={savings}
                onChange={(e) => setSavings(Number(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
            </div>

            {/* 4. Tiền mặt khả dụng */}
            <div className="p-3.5 rounded-xl border border-sky-500/30 bg-surface-container-low space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-sky-500"></span>
                  <div>
                    <span className="text-xs font-bold text-text-primary">Tiền mặt khả dụng (T+0)</span>
                    <span className="text-[10px] text-text-muted block">Thanh khoản tức thì, vốn chờ giải ngân</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 font-mono-num">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={cash}
                    onChange={(e) => setCash(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                    className="w-14 px-2 py-0.5 rounded-lg border border-border-subtle text-right font-bold text-xs bg-surface-container text-text-primary focus:outline-sky-500"
                  />
                  <span className="text-xs text-text-muted font-bold">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={cash}
                onChange={(e) => setCash(Number(e.target.value))}
                className="w-full accent-sky-500 cursor-pointer"
              />
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-accent-rose-light border border-accent-rose/30 text-accent-rose text-xs font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-accent-rose" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border-subtle">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2.5 rounded-xl border border-border-subtle text-text-secondary font-bold text-xs hover:bg-surface-container transition-colors cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={!isValid || submitting}
              className="px-5 py-2.5 rounded-xl bg-accent-emerald hover:opacity-90 text-white font-bold text-xs transition-all shadow-xs disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 cursor-pointer"
            >
              {submitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  Đang lưu...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  Lưu Tỷ Trọng Mục Tiêu SAA
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
