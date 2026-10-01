import { useState, useMemo } from 'react';
import {
  ComposedChart, Area, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { TrendingUp, TrendingDown, Eye, BarChart2 } from 'lucide-react';
import {
  VNINDEX_SUMMARY,
  VNINDEX_DAILY_SERIES,
  VNINDEX_MACRO_5Y
} from '../../data/vnindexData';

interface VNIndexChartProps {
  height?: number;
  showControls?: boolean;
  compact?: boolean;
}

type TimeframeType = '1M' | '3M' | '6M' | '1Y' | 'ALL';

export function VNIndexChart({
  height = 320,
  showControls = true,
  compact = false
}: VNIndexChartProps) {
  const [timeframe, setTimeframe] = useState<TimeframeType>('6M');
  const [showMA20, setShowMA20] = useState(true);
  const [showMA50, setShowMA50] = useState(true);
  const [showVolume, setShowVolume] = useState(true);

  // Filter data based on selected timeframe
  const chartData = useMemo(() => {
    if (timeframe === 'ALL') {
      return VNINDEX_MACRO_5Y.map(d => ({
        ...d,
        ma50: null,
        changePercent: 0
      }));
    }
    const daysMap: Record<Exclude<TimeframeType, 'ALL'>, number> = {
      '1M': 22,
      '3M': 66,
      '6M': 130,
      '1Y': 250
    };
    const count = daysMap[timeframe] || 130;
    return VNINDEX_DAILY_SERIES.slice(-count);
  }, [timeframe]);

  // Calculate high/low for current visible range
  const { minVal, maxVal, maxVol } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    let mv = 0;
    chartData.forEach(d => {
      if (d.close < min) min = d.close;
      if (d.close > max) max = d.close;
      if (d.volumeM > mv) mv = d.volumeM;
    });
    return {
      minVal: Math.floor(min * 0.98),
      maxVal: Math.ceil(max * 1.02),
      maxVol: mv > 0 ? mv * 3.5 : 1000 // scale down volume bars to fit lower 25% of chart
    };
  }, [chartData]);

  const isPositive = VNINDEX_SUMMARY.changePercent >= 0;

  return (
    <div className="w-full">
      {/* Chart Header Bar */}
      {!compact && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-black text-text-primary tracking-tight">
                  {VNINDEX_SUMMARY.currentPoints.toLocaleString('vi-VN', { minimumFractionDigits: 2 })}
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${
                    isPositive
                      ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30'
                      : 'bg-accent-rose-light text-accent-rose border border-accent-rose/30'
                  }`}
                >
                  {isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                  {VNINDEX_SUMMARY.changePoints > 0 ? '+' : ''}{VNINDEX_SUMMARY.changePoints.toFixed(2)} ({isPositive ? '+' : ''}{VNINDEX_SUMMARY.changePercent.toFixed(2)}%)
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-[11px] text-text-muted">
                <span>Khối lượng: <strong className="text-text-primary">{(VNINDEX_SUMMARY.latestVolume / 1e6).toFixed(1)}M CP</strong></span>
                <span>•</span>
                <span>52T: <strong className="text-text-primary">{VNINDEX_SUMMARY.low52w.toFixed(0)} - {VNINDEX_SUMMARY.high52w.toFixed(0)}</strong></span>
                <span>•</span>
                <span>Ngày: <strong className="text-text-primary">{VNINDEX_SUMMARY.latestDate}</strong></span>
              </div>
            </div>
          </div>

          {/* Timeframe & Overlays Controls */}
          {showControls && (
            <div className="flex flex-wrap items-center gap-2">
              {/* Technical Indicator Toggles */}
              <div className="flex items-center gap-1 bg-surface-container-low p-1 rounded-lg border border-border-subtle text-xs">
                <button
                  type="button"
                  onClick={() => setShowMA20(!showMA20)}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 ${
                    showMA20 ? 'bg-amber-50 text-amber-700 border border-amber-200 shadow-2xs' : 'text-text-muted hover:text-text-primary'
                  }`}
                  title="Đường trung bình động 20 phiên (Ngắn hạn)"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                  MA20
                </button>
                <button
                  type="button"
                  onClick={() => setShowMA50(!showMA50)}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 ${
                    showMA50 ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs' : 'text-text-muted hover:text-text-primary'
                  }`}
                  title="Đường trung bình động 50 phiên (Trung hạn)"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                  MA50
                </button>
                <button
                  type="button"
                  onClick={() => setShowVolume(!showVolume)}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all flex items-center gap-1 ${
                    showVolume ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs' : 'text-text-muted hover:text-text-primary'
                  }`}
                  title="Khối lượng giao dịch"
                >
                  <BarChart2 className="w-3 h-3 text-emerald-600" />
                  Vol
                </button>
              </div>

              {/* Timeframe Selector */}
              <div className="flex items-center gap-1 bg-surface-container-low p-1 rounded-lg border border-border-subtle text-xs">
                {(['1M', '3M', '6M', '1Y', 'ALL'] as TimeframeType[]).map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() => setTimeframe(tf)}
                    className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                      timeframe === tf
                        ? 'bg-surface-container-lowest text-text-primary shadow-xs border border-border-subtle'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {tf === 'ALL' ? '5 Năm' : tf}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main Chart */}
      <div style={{ height: `${height}px` }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <defs>
              <linearGradient id="vniGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#059669" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#059669" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="displayDate"
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              yAxisId="price"
              stroke="#94a3b8"
              fontSize={11}
              domain={[minVal, maxVal]}
              tickLine={false}
              tickFormatter={(v) => Math.round(v).toString()}
            />
            <YAxis
              yAxisId="volume"
              orientation="right"
              domain={[0, maxVol]}
              hide={true}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#ffffff',
                borderColor: '#e2e8f0',
                borderRadius: '0.5rem',
                fontSize: '12px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
              }}
              formatter={(value: any, name: string) => {
                if (name === 'Điểm số VN-Index') {
                  return [`${Number(value).toFixed(2)} điểm`, name];
                }
                if (name === 'MA20') {
                  return [`${Number(value).toFixed(2)}`, 'MA20 (Ngắn hạn)'];
                }
                if (name === 'MA50') {
                  return [`${Number(value).toFixed(2)}`, 'MA50 (Trung hạn)'];
                }
                if (name === 'Khối lượng (M)') {
                  return [`${Number(value).toFixed(1)} triệu CP`, 'Khối lượng'];
                }
                return [value, name];
              }}
              labelFormatter={(label) => `Phiên giao dịch: ${label}`}
            />

            {/* Volume Bars */}
            {showVolume && (
              <Bar
                yAxisId="volume"
                dataKey="volumeM"
                name="Khối lượng (M)"
                fill="#cbd5e1"
                opacity={0.4}
                barSize={3}
              />
            )}

            {/* VN-Index Price Area */}
            <Area
              yAxisId="price"
              type="monotone"
              dataKey="close"
              name="Điểm số VN-Index"
              stroke="#059669"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#vniGradient)"
            />

            {/* Moving Average 20 */}
            {showMA20 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="ma20"
                name="MA20"
                stroke="#d97706"
                strokeWidth={1.5}
                dot={false}
                strokeDasharray="3 3"
              />
            )}

            {/* Moving Average 50 */}
            {showMA50 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="ma50"
                name="MA50"
                stroke="#6366f1"
                strokeWidth={1.5}
                dot={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend & Technical Notes Footer */}
      {!compact && (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 mt-2 border-t border-border-subtle text-[11px] text-text-muted">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-1 bg-accent-emerald rounded"></span>
              <span>VN-Index Close</span>
            </span>
            {showMA20 && (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-amber-500 border-t border-dashed border-amber-500"></span>
                <span>MA20 ({VNINDEX_SUMMARY.ma20.toFixed(1)})</span>
              </span>
            )}
            {showMA50 && (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-indigo-500"></span>
                <span>MA50 ({VNINDEX_SUMMARY.ma50.toFixed(1)})</span>
              </span>
            )}
            {showVolume && (
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 bg-slate-300 rounded-xs"></span>
                <span>Volume</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-text-secondary">
            <Eye className="w-3.5 h-3.5 text-accent-emerald" />
            <span>Trạng thái: <strong>Kiểm định MA50 • Chế độ Bullish (+1)</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}
