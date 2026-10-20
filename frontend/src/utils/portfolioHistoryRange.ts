export type PortfolioTimeframe = '1W' | '1M' | '3M' | 'YTD' | '1Y' | 'ALL';
const DAY = 86_400_000;

/** UTC midnight represents a Vietnam calendar date, without browser-zone shifts. */
export function portfolioHistoryRange(timeframe: PortfolioTimeframe, dates: string[], now = Date.now()): [number, number] {
  const vietnam = new Date(now + 7 * 3_600_000);
  const year = vietnam.getUTCFullYear(), month = vietnam.getUTCMonth(), day = vietnam.getUTCDate();
  const end = Date.UTC(year, month, day);
  const subtractMonths = (months: number) => {
    const first = new Date(Date.UTC(year, month - months, 1));
    const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    return Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), Math.min(day, lastDay));
  };
  const start = timeframe === '1W' ? end - 7 * DAY
    : timeframe === '1M' ? subtractMonths(1)
    : timeframe === '3M' ? subtractMonths(3)
    : timeframe === '1Y' ? subtractMonths(12)
    : timeframe === 'YTD' ? Date.UTC(year, 0, 1)
    : dates.length ? Math.min(...dates.map(date => Date.parse(date))) : end - 7 * DAY;
  return [Math.min(start, end), end];
}

export function historyDateLabel(timestamp: number): string {
  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' }).format(timestamp);
}
