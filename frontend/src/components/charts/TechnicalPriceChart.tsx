import { useMemo, useState } from 'react';
import { ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';
import { technicalIndicators, PriceBar } from '../../utils/technicalIndicators';
import { useTheme } from '../../context/ThemeContext';

export function TechnicalPriceChart({ bars, name, unit = 'điểm', height = 320, showControls = true, compact = false }: {
  bars: PriceBar[]; name: string; unit?: string; height?: number; showControls?: boolean; compact?: boolean;
}) {
  const { isDark } = useTheme();
  const [range, setRange] = useState('6M');
  const [indicators, setIndicators] = useState(['ma20', 'ma50', 'ma200', 'rsi']);
  const full = useMemo(() => technicalIndicators(bars), [bars]);
  const data = useMemo(() => {
    if (range === 'ALL' || !full.length) return full;
    const end = new Date(full[full.length - 1].date + 'T00:00:00Z');
    const months = ({ '1M': 1, '3M': 3, '6M': 6, '1Y': 12 } as Record<string, number>)[range];
    end.setUTCMonth(end.getUTCMonth() - months);
    return full.filter(p => p.date >= end.toISOString().slice(0, 10));
  }, [full, range]);
  const colors: Record<string, string> = { ma20: '#b7791f', ma50: '#818cf8', ma200: '#e87935' };
  const toggle = (key: string) => setIndicators(current => current.includes(key) ? current.filter(v => v !== key) : [...current, key]);
  const latest = full[full.length - 1];
  const number = (value: number) => value.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
  const tick = (date: string) => date.slice(8, 10) + '/' + date.slice(5, 7);
  const grid = isDark ? '#303342' : '#edf1f5';
  const tooltip = { backgroundColor: isDark ? '#18181b' : '#fff', borderColor: grid, borderRadius: 6, fontSize: 12 };
  if (!latest) return <p role="status" className="py-10 text-center text-sm text-text-secondary">Chưa có lịch sử giá {name}.</p>;
  return <div className="min-w-0">
    {!compact && <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
      <div><h3 className="text-sm font-medium text-text-secondary">{name}</h3><p className="mt-1 text-xl font-semibold tabular-nums text-text-primary">{number(latest.close)} <span className="text-xs font-normal text-text-secondary">{unit}</span></p><p className="mt-1 text-xs text-text-secondary">{latest.date}</p></div>
      {showControls && <div className="flex flex-wrap gap-3">
        <div className="flex flex-wrap gap-1" aria-label="Chỉ báo kỹ thuật">
          {['ma20', 'ma50', 'ma200', 'rsi', ...(bars.some(b => b.volumeM != null) ? ['volume'] : [])].map(key =>
            <button key={key} type="button" aria-pressed={indicators.includes(key)} onClick={() => toggle(key)}
              className={`rounded-md px-2 py-1.5 text-xs ${indicators.includes(key) ? 'bg-surface-container-high font-semibold text-text-primary' : 'text-text-secondary hover:bg-surface-container'}`}>{key === 'rsi' ? 'RSI (14)' : key === 'volume' ? 'Khối lượng' : key.toUpperCase()}</button>)}
        </div>
        <div className="flex flex-wrap gap-1" aria-label="Khoảng thời gian biểu đồ">
          {['1M', '3M', '6M', '1Y', 'ALL'].map(key => <button key={key} type="button" aria-pressed={range === key} onClick={() => setRange(key)}
            className={`rounded-md px-2 py-1.5 text-xs ${range === key ? 'bg-accent-emerald-light font-semibold text-accent-emerald' : 'text-text-secondary hover:bg-surface-container'}`}>{key === 'ALL' ? 'Toàn bộ' : key}</button>)}
        </div>
      </div>}
    </div>}
    <div style={{ height }} aria-label={`Biểu đồ giá ${name}`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} syncId={name} margin={{ top: 8, right: 12, left: unit === '₫/chỉ' ? 12 : 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={grid} strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={tick} minTickGap={40} fontSize={11} tickLine={false} stroke="#94a3b8" />
          <YAxis yAxisId="price" domain={['auto', 'auto']} tickFormatter={v => unit === '₫/chỉ' ? (v / 1e6).toLocaleString('vi-VN') + 'tr' : Math.round(v).toString()} fontSize={11} tickLine={false} stroke="#94a3b8" />
          <YAxis yAxisId="volume" hide domain={[0, (max: number) => max * 4]} />
          <Tooltip contentStyle={tooltip} labelFormatter={label => String(label)} formatter={(value: number, label: string) => [number(value) + (label === 'Khối lượng' ? ' triệu CP' : ' ' + unit), label]} />
          {indicators.includes('volume') && <Bar yAxisId="volume" dataKey="volumeM" name="Khối lượng" fill="#94a3b8" opacity={0.3} isAnimationActive={false} />}
          <Line yAxisId="price" type="linear" dataKey="close" name={name} stroke="#059669" strokeWidth={2} dot={false} isAnimationActive={false} />
          {['ma20', 'ma50', 'ma200'].filter(key => indicators.includes(key)).map(key => <Line key={key} yAxisId="price" dataKey={key} name={key.toUpperCase()} stroke={colors[key]} dot={false} strokeWidth={1.5} connectNulls={false} isAnimationActive={false} />)}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-text-secondary">
      {(['ma20', 'ma50', 'ma200'] as const).filter(key => indicators.includes(key)).map(key => <span key={key} className="inline-flex items-center gap-1.5"><span className="h-0.5 w-3" style={{ backgroundColor: colors[key] }} />{key.toUpperCase()}: {latest[key] == null ? 'Chưa đủ dữ liệu' : number(latest[key]!)}</span>)}
    </div>
    {indicators.includes('rsi') && <div className="mt-5 border-t border-border-subtle pt-3" aria-label="Chỉ số RSI">
      <p className="mb-2 text-xs text-text-secondary">RSI (14): <strong className="tabular-nums text-text-primary">{latest.rsi == null ? 'Chưa đủ 15 điểm dữ liệu' : number(latest.rsi)}</strong><span className="ml-3">Mốc tham chiếu 30 / 70</span></p>
      {latest.rsi != null && <div className="h-28"><ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} syncId={name} margin={{ top: 5, right: 12, left: unit === '₫/chỉ' ? 12 : 0, bottom: 0 }}>
          <XAxis dataKey="date" tickFormatter={tick} minTickGap={40} fontSize={10} tickLine={false} stroke="#94a3b8" />
          <YAxis domain={[0, 100]} ticks={[0, 30, 70, 100]} fontSize={10} tickLine={false} stroke="#94a3b8" />
          <ReferenceLine y={30} stroke="#94a3b8" strokeDasharray="3 3" /><ReferenceLine y={70} stroke="#94a3b8" strokeDasharray="3 3" />
          <Tooltip contentStyle={tooltip} formatter={(value: number) => [number(value), 'RSI (14)']} />
          <Line dataKey="rsi" name="RSI (14)" stroke="#818cf8" strokeWidth={1.5} dot={false} connectNulls={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer></div>}
    </div>}
    {!compact && <p className="mt-3 text-xs text-text-secondary">MA và RSI được tính trên toàn bộ lịch sử trước khi lọc khoảng thời gian.</p>}
  </div>;
}
