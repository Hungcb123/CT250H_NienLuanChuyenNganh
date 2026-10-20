import React, { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
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

  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, [isOpen]);

  if (!isOpen) return null;

  const total = stock + gold + savings + cash;
  const isValid = total === 100 && [stock, gold, savings, cash].every(value => Number.isInteger(value) && value >= 0 && value <= 100);

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

  const rows = [
    { key: 'stock', label: 'Cổ phiếu VN30', value: stock, set: setStock },
    { key: 'gold', label: 'Vàng SJC', value: gold, set: setGold },
    { key: 'savings', label: 'Tiết kiệm', value: savings, set: setSavings },
    { key: 'cash', label: 'Tiền mặt', value: cash, set: setCash },
  ] as const;
  const presets = [
    { label: 'Bảo thủ', values: [15, 25, 45, 15] },
    { label: 'Cân bằng', values: [35, 35, 20, 10] },
    { label: 'Tăng trưởng', values: [60, 20, 15, 5] },
  ];

  return (
    <div className="!m-0 fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-3 sm:p-6">
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="targets-title" aria-describedby="targets-description"
        tabIndex={-1} className="w-full max-w-lg max-h-[90dvh] overflow-y-auto rounded-xl bg-surface-container-lowest text-text-primary shadow-xl outline-none"
        onKeyDown={event => {
          if (event.key === 'Escape' && !submitting) onClose();
          if (event.key === 'Tab') {
            const controls = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)');
            if (!controls?.length) return;
            const first = controls[0], last = controls[controls.length - 1];
            if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
              event.preventDefault(); last.focus();
            } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogRef.current)) {
              event.preventDefault(); first.focus();
            }
          }
        }}>
        <div className="flex items-start justify-between gap-4 px-5 pt-5 sm:px-6">
          <div>
            <h3 id="targets-title" className="text-lg font-semibold">Phân bổ mục tiêu</h3>
            <p id="targets-description" className="mt-1 text-sm text-text-secondary">Thiết lập tỷ trọng dài hạn cho danh mục.</p>
          </div>
          <button type="button" onClick={onClose} disabled={submitting} aria-label="Đóng" className="rounded-md p-2 text-text-secondary hover:bg-surface-container disabled:opacity-50"><X className="h-4 w-4" /></button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 pb-5 sm:px-6 sm:pb-6">
          <fieldset disabled={submitting} className="mt-6">
            <legend className="mb-2 text-xs text-text-secondary">Mẫu phân bổ</legend>
            <div className="flex flex-wrap gap-2">
              {presets.map(preset => {
                const selected = [stock, gold, savings, cash].every((value, index) => value === preset.values[index]);
                return <button key={preset.label} type="button" aria-pressed={selected}
                  onClick={() => applyPreset(preset.values[0], preset.values[1], preset.values[2], preset.values[3])}
                  className={`rounded-md px-3 py-2 text-sm transition-colors ${selected ? 'bg-accent-emerald-light text-accent-emerald font-semibold' : 'bg-surface-container-low text-text-secondary hover:bg-surface-container-high'}`}>{preset.label}</button>;
              })}
            </div>
          </fieldset>
          <table className="mt-6 w-full text-sm">
            <thead><tr className="border-b border-border-subtle text-xs text-text-secondary">
              <th scope="col" className="pb-3 text-left font-normal">Loại tài sản</th>
              <th scope="col" className="pb-3 text-right font-normal">Đang áp dụng</th>
              <th scope="col" className="pb-3 text-right font-normal">Mục tiêu</th>
            </tr></thead>
            <tbody className="divide-y divide-border-subtle">
              {rows.map(row => <tr key={row.key}>
                <th scope="row" className="py-3 pr-4 text-left font-medium">
                  <label htmlFor={`target-${row.key}`}>{row.label}</label>
                  <input type="range" min="0" max="100" step="1" value={row.value} disabled={submitting}
                    aria-label={`Tỷ trọng ${row.label}`} aria-valuetext={`${row.value}%`}
                    onChange={event => row.set(Number(event.target.value))}
                    className="mt-2 block h-6 w-full min-w-20 max-w-48 cursor-pointer accent-accent-emerald disabled:cursor-not-allowed disabled:opacity-50" />
                </th>
                <td className="py-3 text-right tabular-nums text-text-secondary">{Math.round(currentTargets[row.key] * 100)}%</td>
                <td className="py-3 pl-3 text-right">
                  <div className="inline-flex items-center gap-1.5">
                    <input id={`target-${row.key}`} type="number" min="0" max="100" step="1" required disabled={submitting}
                      value={row.value} onChange={event => row.set(Math.max(0, Math.min(100, Number(event.target.value) || 0)))}
                      className="w-16 rounded-md border border-border-subtle bg-surface px-2 py-2 text-right tabular-nums focus:outline-accent-emerald disabled:opacity-50" />
                    <span className="text-text-secondary">%</span>
                  </div>
                </td>
              </tr>)}
            </tbody>
            <tfoot><tr className="border-t border-border-subtle font-semibold">
              <th scope="row" colSpan={2} className="pt-3 text-left">Tổng</th>
              <td className={`pt-3 text-right tabular-nums ${isValid ? 'text-text-primary' : 'text-accent-rose'}`}>{total}%</td>
            </tr></tfoot>
          </table>
          <p aria-live="polite" className="mt-2 min-h-5 text-xs text-accent-rose">{total < 100 ? `Cần phân bổ thêm ${100 - total}%` : total > 100 ? `Vượt ${total - 100}%` : !isValid ? 'Nhập tỷ trọng là số nguyên từ 0 đến 100.' : ''}</p>
          {errorMsg && <p role="alert" className="mt-2 text-sm text-accent-rose">{errorMsg}</p>}
          <div className="mt-4 flex justify-end gap-2 border-t border-border-subtle pt-4">
            <button type="button" onClick={onClose} disabled={submitting} className="rounded-md px-4 py-2 text-sm text-text-secondary hover:bg-surface-container disabled:opacity-50">Hủy</button>
            <button type="submit" disabled={!isValid || submitting} className="rounded-md bg-accent-emerald px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">{submitting ? 'Đang lưu…' : 'Lưu mục tiêu'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
