export interface PriceBar { date: string; close: number; volumeM?: number }
export function technicalIndicators(input: PriceBar[]) {
  const series = input.filter(p => Number.isFinite(p.close) && p.close > 0).slice().sort((a, b) => a.date.localeCompare(b.date));
  let gain = 0, loss = 0;
  return series.map((bar, index) => {
    const delta = index ? bar.close - series[index - 1].close : 0;
    if (index > 0 && index <= 14) { gain += Math.max(delta, 0) / 14; loss += Math.max(-delta, 0) / 14; }
    else if (index > 14) { gain = (gain * 13 + Math.max(delta, 0)) / 14; loss = (loss * 13 + Math.max(-delta, 0)) / 14; }
    const ma = (period: number) => index + 1 < period ? null : series.slice(index + 1 - period, index + 1).reduce((sum, p) => sum + p.close, 0) / period;
    return { ...bar, ma20: ma(20), ma50: ma(50), ma200: ma(200),
      rsi: index < 14 ? null : gain === 0 && loss === 0 ? 50 : loss === 0 ? 100 : 100 - 100 / (1 + gain / loss) };
  });
}
