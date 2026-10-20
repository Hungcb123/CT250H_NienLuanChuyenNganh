import { useEffect, useState } from 'react';
import { TechnicalPriceChart } from '../charts/TechnicalPriceChart';
import { PriceBar } from '../../utils/technicalIndicators';
import { GoldPriceItem } from '../../types';
import { formatVND } from '../../utils/formatters';

export function GoldMarket() {
  const [ticker, setTicker] = useState('GOLD_SJC');
  const [quotes, setQuotes] = useState<GoldPriceItem[]>([]);
  const [bars, setBars] = useState<PriceBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true); setError('');
      try {
        const [quoteResponse, historyResponse] = await Promise.all([
          fetch('/api/v1/market/gold-prices'), fetch('/api/v1/market/gold-history?ticker=' + ticker)
        ]);
        if (!quoteResponse.ok || !historyResponse.ok) throw Error('Chưa tải được dữ liệu vàng. Vui lòng thử lại.');
        const [quoteData, historyData] = await Promise.all([quoteResponse.json(), historyResponse.json()]);
        if (!Array.isArray(quoteData.data) || !Array.isArray(historyData.data)) throw Error('Dữ liệu vàng chưa sẵn sàng.');
        if (active) { setQuotes(quoteData.data); setBars(historyData.data); }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : 'Không tải được dữ liệu vàng.'); }
      finally { if (active) setLoading(false); }
    };
    void load();
    const timer = window.setInterval(load, 60_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [ticker, retry]);
  const quote = quotes.find(q => q.ticker === ticker);
  return <section aria-label="Thị trường vàng" className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-1" aria-label="Loại vàng">{[['GOLD_SJC', 'Vàng SJC'], ['GOLD_RING_9999', 'Nhẫn 9999']].map(([key, label]) =>
        <button key={key} type="button" aria-pressed={ticker === key} onClick={() => setTicker(key)} className={`rounded-md px-3 py-2 text-sm ${ticker === key ? 'bg-accent-emerald-light font-semibold text-accent-emerald' : 'text-text-secondary hover:bg-surface-container'}`}>{label}</button>)}</div>

    </div>
    {loading ? <p role="status" className="py-12 text-center text-sm text-text-secondary">Đang tải dữ liệu vàng…</p>
      : error ? <p role="alert" className="py-8 text-sm text-text-secondary">{error} <button type="button" onClick={() => setRetry(n => n + 1)} className="text-accent-emerald underline">Thử lại</button></p>
      : <>
        {quote && <dl className="grid grid-cols-2 gap-5 border-b border-border-subtle pb-5">
          <div><dt className="text-xs text-text-secondary">Giá mua vào (₫/chỉ)</dt><dd className="mt-2 text-xl font-semibold tabular-nums text-text-primary">{formatVND(quote.buyPrice)}</dd></div>
          <div><dt className="text-xs text-text-secondary">Giá bán ra (₫/chỉ)</dt><dd className="mt-2 text-xl font-semibold tabular-nums text-text-primary">{formatVND(quote.sellPrice)}</dd></div>
        </dl>}
        <div className="bg-surface-container-lowest p-4 sm:p-6"><TechnicalPriceChart key={ticker} bars={bars} name={ticker === 'GOLD_SJC' ? 'Vàng SJC' : 'Nhẫn 9999'} unit="₫/chỉ" />
          <p className="mt-3 text-xs text-text-secondary">Lịch sử giá bán ra đã lưu · {quote?.source ?? 'Cơ sở dữ liệu'} · {quote?.tradeDate ?? bars[bars.length - 1]?.date ?? 'Chưa có ngày cập nhật'}</p>
        </div>
      </>}

  </section>;
}
