import { useEffect, useState } from 'react';
import type { PortfolioHistoryResponse, RiskMetrics } from '../../types';
import { getPortfolioHistory } from '../../services/api';
import { historyDateLabel, portfolioHistoryRange } from '../../utils/portfolioHistoryRange';

const percent = (value: number | null | undefined) => value != null && Number.isFinite(value)
  ? `${value > 0 ? '+' : ''}${value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%` : '—';
const tone = (value: number | null | undefined) => value == null || !Number.isFinite(value) || value === 0
  ? 'text-text-primary' : value > 0 ? 'text-accent-emerald' : 'text-accent-rose';
const dates = (history: PortfolioHistoryResponse | null) => history?.points.length
  ? `${historyDateLabel(Date.parse(history.points[0].date))} – ${historyDateLabel(Date.parse(history.points[history.points.length - 1].date))}` : '';

export function PortfolioReturnSummary({ risk, refreshKey, readyForYear }: {
  risk: RiskMetrics | null;
  refreshKey?: unknown;
  readyForYear: boolean;
}) {
  const [year, setYear] = useState<PortfolioHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => { setYear(null); setLoading(true); setError(false); }, [refreshKey, retry]);
  useEffect(() => {
    // Wait for the selected-period request: the legacy history endpoint also
    // creates today's snapshot, so concurrent first reads could race an insert.
    if (!readyForYear || year || error) return;
    let active = true;
    getPortfolioHistory('1Y').then(result => { if (active) setYear(result); })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [readyForYear, refreshKey, retry, year, error]);
  const coversYear = (value: PortfolioHistoryResponse | null) => {
    const [start, end] = portfolioHistoryRange('1Y', []);
    const first = value?.points[0], last = value?.points[value.points.length - 1];
    const day = 86_400_000;
    return !!first && !!last && value!.points.length >= 2 && value!.timeframe === '1Y'
      && Date.parse(first.date) >= start && Date.parse(first.date) <= start + 7 * day
      && Date.parse(last.date) <= end && Date.parse(last.date) >= end - 7 * day;
  };
  const completeYear = coversYear(year);
  const yearReturn = completeYear ? year?.portfolioReturnPercent : null;
  const benchmarkReturn = completeYear && year!.points.every(point => point.vnindex > 0) ? year?.vniReturnPercent : null;
  const annualized = completeYear && risk?.riskRating === 'HISTORICAL' ? risk.annualizedReturnPercent : null;
  const description = loading ? 'Đang tải' : error ? 'Chưa tải được' : completeYear
    ? `${dates(year)}. VNINDEX: ${percent(benchmarkReturn)}. Đã điều chỉnh tiền nạp/rút.` : 'Chưa đủ lịch sử 1 năm';
  return <span aria-label="Tóm tắt lợi suất" className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-secondary">
    <span aria-hidden="true">·</span>
    <span data-testid="one-year-return" title={description} className="whitespace-nowrap">
      1 năm: <strong className={`font-mono-num ${tone(yearReturn)}`}>{loading ? '…' : percent(yearReturn)}</strong>
      {error && <button type="button" aria-label="Thử lại lợi suất 1 năm" className="ml-1 underline text-accent-blue" onClick={() => setRetry(value => value + 1)}>Thử lại</button>}
    </span>
    <span aria-hidden="true">·</span>
    <span data-testid="annualized-return" className="whitespace-nowrap" title={`Lãi kép quy đổi năm từ toàn bộ lịch sử, đã điều chỉnh tiền nạp/rút.${risk?.interpretation?.includes('mô phỏng') ? ' Dữ liệu mô phỏng kiểm thử.' : ''}`}>
      Quy đổi năm: <strong className={`font-mono-num ${tone(annualized)}`}>{percent(annualized)}</strong>
    </span>
  </span>;
}
