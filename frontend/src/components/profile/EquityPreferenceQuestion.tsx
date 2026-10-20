import { useEffect, useState } from 'react';
import { getEquityPreference, saveEquityPreference } from '../../services/api';
import type { EquityPreference } from '../../types';

const choices = [
  { mode: 'ETF', title: 'ETF theo chỉ số', description: 'Phần cổ phiếu mua ETF VN30 E1VFVN30, thay cho chia vào từng cổ phiếu.' },
  { mode: 'STOCKS', title: 'Cổ phiếu riêng lẻ', description: 'Phân bổ theo tỷ lệ các cổ phiếu riêng lẻ đang nắm giữ. Nếu chưa có, chọn và mua mã ở tab Thị trường trước.' },
  { mode: 'MIXED', title: 'Kết hợp ETF và cổ phiếu', description: 'Chọn tỷ lệ ETF; phần còn lại phân bổ vào các cổ phiếu riêng lẻ đang nắm giữ.' },
] as const;

export function EquityPreferenceQuestion({ onSaved }: { onSaved?: () => Promise<void> | void }) {
  const [draft, setDraft] = useState<EquityPreference>({ mode: 'ETF', etfWeight: 1 });
  const [saved, setSaved] = useState<EquityPreference | null>(null);
  const [mixPercent, setMixPercent] = useState(50);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    getEquityPreference().then(value => {
      if (!active) return;
      setSaved(value);
      if (value) { setDraft(value); if (value.mode === 'MIXED') setMixPercent(Math.round(value.etfWeight * 100)); }
    }).catch(() => { if (active) setError('Chưa tải được lựa chọn. Đăng nhập và thử lại.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);
  const save = async () => {
    setSaving(true); setError(null); setMessage(null);
    try {
      const result = await saveEquityPreference(draft);
      setSaved(result);
      await onSaved?.();
      setMessage('Đã lưu cách đầu tư. Xem và xác nhận kế hoạch tái cân bằng để thực hiện giao dịch.');
    } catch { setError('Không lưu được lựa chọn. Vui lòng thử lại.'); }
    finally { setSaving(false); }
  };
  const dirty = !saved || saved.mode !== draft.mode || saved.etfWeight !== draft.etfWeight;
  return <section aria-label="Cách đầu tư phần cổ phiếu" className="space-y-4 border-b border-border-subtle pb-6">
    <div>
      <h3 className="font-bold text-text-primary">Bạn muốn đầu tư phần cổ phiếu bằng cách nào?</h3>
      <p className="mt-1 text-sm text-text-secondary">SAA/TAA quyết định tổng tỷ trọng cổ phiếu. Lựa chọn này quyết định phần đó mua ETF hay cổ phiếu riêng lẻ.</p>
    </div>
    {loading ? <p role="status" className="text-sm text-text-secondary">Đang tải lựa chọn…</p> : <>
      {!saved && <p className="text-sm text-text-secondary">Chưa lưu lựa chọn. Chọn một phương án và bấm lưu để áp dụng cho kế hoạch mới.</p>}
      <fieldset disabled={saving || (!!error && loading)} className="space-y-2">
        <legend className="sr-only">Cách đầu tư phần cổ phiếu</legend>
        {choices.map(choice => <label key={choice.mode} className={`flex items-start gap-3 border-b py-4 cursor-pointer ${draft.mode === choice.mode ? 'border-text-primary' : 'border-border-subtle'}`}>
          <input type="radio" name="equity-investment-mode" value={choice.mode} checked={draft.mode === choice.mode}
            onChange={() => { setDraft({ mode: choice.mode, etfWeight: choice.mode === 'ETF' ? 1 : choice.mode === 'STOCKS' ? 0 : mixPercent / 100 }); setMessage(null); }}
            className="mt-1 accent-emerald-600" />
          <span><strong className="block text-sm text-text-primary">{choice.title}</strong><span className="block mt-1 text-xs text-text-secondary">{choice.description}</span></span>
        </label>)}
        {draft.mode === 'MIXED' && <label className="block space-y-2 text-sm text-text-primary pt-2">
          <span>Tỷ lệ ETF trong phần cổ phiếu: <strong>{mixPercent}%</strong> · Cổ phiếu riêng lẻ: {100 - mixPercent}%</span>
          <input aria-label="Tỷ lệ ETF trong phần cổ phiếu" type="range" min="1" max="99" step="1" value={mixPercent}
            onChange={event => { const percent = Number(event.target.value); setMixPercent(percent); setDraft({ mode: 'MIXED', etfWeight: percent / 100 }); setMessage(null); }} className="w-full accent-emerald-600" />
          <span className="block text-xs text-text-secondary">Ví dụ tổng cổ phiếu là 40% NAV, ETF chiếm 50% phần này thì ETF là 20% NAV và cổ phiếu riêng lẻ là 20% NAV.</span>
        </label>}
      </fieldset>
      <p className="text-xs text-text-secondary">ETF này mô phỏng VN30; tín hiệu VNINDEX chỉ là tham chiếu và hai chỉ số có thể biến động khác nhau. VN30F1 là hợp đồng tương lai, chưa được hỗ trợ trong lựa chọn này.</p>
      <button type="button" disabled={saving || !dirty} onClick={() => void save()} className="rounded-lg bg-accent-emerald text-white px-4 py-2 text-sm font-semibold disabled:opacity-50 focus-visible:outline focus-visible:outline-2">{saving ? 'Đang lưu…' : 'Lưu cách đầu tư'}</button>
    </>}
    {error && <p role="alert" className="text-sm text-accent-rose">{error} <button type="button" onClick={() => setRetry(value => value + 1)} className="underline">Tải lại</button></p>}
    {message && <p role="status" className="text-sm text-text-secondary">{message}</p>}
  </section>;
}
