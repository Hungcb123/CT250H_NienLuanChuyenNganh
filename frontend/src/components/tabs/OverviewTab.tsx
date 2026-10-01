import { useState } from 'react';
import {
  Wallet, Receipt, PiggyBank, TrendingUp, Bot, AlertTriangle, CheckCircle, BarChart2, Activity
} from 'lucide-react';
import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { PortfolioValuation, RebalancePlan, UserProfile } from '../../types';
import { formatVND } from '../../utils/formatters';
import { VNIndexChart } from '../charts/VNIndexChart';
import { VNINDEX_SUMMARY } from '../../data/vnindexData';

interface OverviewTabProps {
  valuation: PortfolioValuation | null;
  plan: RebalancePlan | null;
  profile: UserProfile | null;
  confirmedExecution: boolean;
  onConfirmRebalance: () => void;
}

// 9-month normalized performance comparison: EquiFolio Portfolio vs VN-Index Benchmark
const PERFORMANCE_DATA = [
  { month: 'T1', navReturn: 0.0, vniReturn: 0.0, navVal: 1280.0, vniVal: 1165.0 },
  { month: 'T2', navReturn: 2.3, vniReturn: 1.1, navVal: 1310.0, vniVal: 1178.0 },
  { month: 'T3', navReturn: 1.2, vniReturn: -1.6, navVal: 1295.0, vniVal: 1146.0 },
  { month: 'T4', navReturn: 4.7, vniReturn: 2.1, navVal: 1340.0, vniVal: 1190.0 },
  { month: 'T5', navReturn: 8.6, vniReturn: 4.5, navVal: 1390.0, vniVal: 1218.0 },
  { month: 'T6', navReturn: 7.0, vniReturn: 1.8, navVal: 1370.0, vniVal: 1186.0 },
  { month: 'T7', navReturn: 10.2, vniReturn: 5.2, navVal: 1410.0, vniVal: 1225.0 },
  { month: 'T8', navReturn: 12.1, vniReturn: 6.8, navVal: 1435.0, vniVal: 1244.0 },
  { month: 'T9', navReturn: 13.3, vniReturn: 7.5, navVal: 1450.3, vniVal: 1252.0 },
];

const DONUT_COLORS = ['#059669', '#d97706', '#0284c7'];

export function OverviewTab({
  valuation,
  plan,
  profile,
  confirmedExecution,
  onConfirmRebalance
}: OverviewTabProps) {
  const [chartMode, setChartMode] = useState<'compare' | 'nav' | 'vnindex'>('compare');

  const donutData = valuation ? [
    { name: 'Cổ phiếu VN30', value: Math.round((valuation.currentAllocations.STOCK || 0.55) * 100) },
    { name: 'Vàng SJC', value: Math.round((valuation.currentAllocations.GOLD || 0.18) * 100) },
    { name: 'Tiết kiệm & Tiền mặt', value: Math.round((valuation.currentAllocations.CASH_SAVINGS || 0.27) * 100) },
  ] : [];

  return (
    <>
      {/* Executive Header Banner */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-text-primary tracking-tight">Nguyễn Tuấn (Alex Nguyen)</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-accent-gold-light text-accent-gold text-xs font-semibold border border-accent-gold/20">
              Private Wealth VIP
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-surface-container-high text-text-secondary text-xs font-medium">
              Risk Score: {profile?.riskScore || 68}/100 (λ = {profile?.riskAversionLambda || 3.88})
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Khẩu vị: Tăng trưởng Cân bằng • Danh mục Đa tài sản tự động tái cơ cấu theo tín hiệu ONNX
          </p>
        </div>

        {/* Real-time ACID Badge */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-lg bg-surface-container-low border border-border-subtle">
            <span className="w-2.5 h-2.5 rounded-full bg-accent-emerald shadow-[0_0_8px_rgba(5,150,105,0.4)]"></span>
            <div className="text-left">
              <p className="text-[10px] uppercase font-bold text-text-muted tracking-wider">Kiểm toán Sổ cái kép</p>
              <p className="text-xs font-bold text-text-primary">
                ACID: Σ Debit - Σ Credit = 0.00 ₫ <span className="text-accent-emerald font-semibold">(100%)</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4 KPI Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* KPI 1: NAV */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Tổng Tài Sản Ròng (NAV)</span>
            <Wallet className="w-5 h-5 text-accent-emerald" />
          </div>
          <div className="text-2xl font-extrabold text-text-primary tracking-tight">
            {valuation ? formatVND(valuation.totalNetWorth) : '1,450,280,000 ₫'}
          </div>
          <div className="mt-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-bold">
              <TrendingUp className="w-3.5 h-3.5" /> +12.4% YTD (+162.5M)
            </span>
            <span className="text-[11px] text-text-muted">Cập nhật realtime</span>
          </div>
        </div>

        {/* KPI 2: Cash Balance */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Tiền Mặt & Thanh Khoản</span>
            <Receipt className="w-5 h-5 text-secondary" />
          </div>
          <div className="text-2xl font-extrabold text-text-primary tracking-tight">
            {valuation ? formatVND(valuation.cashBalance) : '85,280,000 ₫'}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-text-secondary">Tỷ trọng: <strong className="text-text-primary">5.9% NAV</strong></span>
            <span className="text-accent-emerald font-semibold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald"></span> Sẵn sàng giải ngân
            </span>
          </div>
        </div>

        {/* KPI 3: Savings */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Tiết Kiệm & Lãi Kép</span>
            <PiggyBank className="w-5 h-5 text-accent-gold" />
          </div>
          <div className="text-2xl font-extrabold text-text-primary tracking-tight">
            {valuation ? formatVND(valuation.savingsValue) : '300,000,000 ₫'}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-text-secondary">Vietcombank 6T</span>
            <span className="text-accent-gold font-bold">+1,650,000 ₫/tháng</span>
          </div>
        </div>

        {/* KPI 4: ONNX Monitor */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Giám Sát Chu Kỳ ONNX</span>
            <span className="text-[10px] font-bold text-accent-emerald bg-accent-emerald-light px-1.5 py-0.5 rounded">&lt;2ms JVM</span>
          </div>
          <div className="space-y-1.5 mt-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">VN30 Index:</span>
              <span className="font-bold text-accent-emerald flex items-center gap-1">
                +1 Bullish <span className="text-[10px] text-text-muted font-normal">(86.4%)</span>
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">Vàng SJC:</span>
              <span className="font-bold text-accent-gold flex items-center gap-1">
                0 Neutral <span className="text-[10px] text-text-muted font-normal">(64.2%)</span>
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Grid: Chart & Holdings (Left) + Donut & Copilot (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Chart Card */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
            {/* Live VN-Index Market Ticker Strip */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 rounded-lg bg-surface-container-low/70 border border-border-subtle mb-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></span>
                <span className="text-xs font-bold text-text-primary">VN-Index:</span>
                <span className="text-xs font-black text-text-primary font-mono">
                  {VNINDEX_SUMMARY.currentPoints.toFixed(2)}
                </span>
                <span className={`text-xs font-bold font-mono ${VNINDEX_SUMMARY.changePercent >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                  {VNINDEX_SUMMARY.changePoints > 0 ? '+' : ''}{VNINDEX_SUMMARY.changePoints.toFixed(2)} ({VNINDEX_SUMMARY.changePercent > 0 ? '+' : ''}{VNINDEX_SUMMARY.changePercent.toFixed(2)}%)
                </span>
              </div>
              <div className="flex items-center gap-3.5 text-xs text-text-secondary">
                <span>Khối lượng: <strong className="text-text-primary font-mono">{(VNINDEX_SUMMARY.latestVolume / 1e6).toFixed(1)}M CP</strong></span>
                <span>MA20: <strong className="text-text-primary font-mono">{VNINDEX_SUMMARY.ma20.toFixed(1)}</strong></span>
                <span>MA50: <strong className="text-text-primary font-mono">{VNINDEX_SUMMARY.ma50.toFixed(1)}</strong></span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30">
                  +1 Bullish (Tích lũy)
                </span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">
                    {chartMode === 'vnindex' ? 'Biểu Đồ Kỹ Thuật Chỉ Số VN-Index' : 'Hiệu Suất Đầu Tư & Đối Sánh Thị Trường'}
                  </h3>
                  {chartMode !== 'vnindex' && (
                    <span className="px-2 py-0.5 rounded-full bg-accent-emerald-light text-accent-emerald text-[11px] font-bold border border-accent-emerald/30">
                      Alpha: +5.8% vs VN-Index
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-secondary mt-0.5">
                  {chartMode === 'vnindex'
                    ? 'Dữ liệu 1,430 phiên giao dịch từ VNDirect API kèm đường trung bình động MA20 & MA50'
                    : 'Danh mục tối ưu Markowitz (+13.3%) vượt trội so với chỉ số chung VN-Index (+7.5%)'}
                </p>
              </div>

              {/* View Toggle */}
              <div className="flex items-center gap-1 p-1 bg-surface-container-low rounded-lg border border-border-subtle">
                <button
                  type="button"
                  onClick={() => setChartMode('compare')}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    chartMode === 'compare'
                      ? 'bg-surface-container-lowest text-text-primary shadow-xs border border-border-subtle'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5 inline mr-1" />
                  Đối sánh (%)
                </button>
                <button
                  type="button"
                  onClick={() => setChartMode('nav')}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    chartMode === 'nav'
                      ? 'bg-surface-container-lowest text-text-primary shadow-xs border border-border-subtle'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  NAV (₫)
                </button>
                <button
                  type="button"
                  onClick={() => setChartMode('vnindex')}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    chartMode === 'vnindex'
                      ? 'bg-surface-container-lowest text-accent-emerald shadow-xs border border-border-subtle font-bold'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  <Activity className="w-3.5 h-3.5 inline mr-1 text-accent-emerald" />
                  Chỉ số VN-Index
                </button>
              </div>
            </div>

            {chartMode === 'vnindex' ? (
              <VNIndexChart height={280} compact={false} showControls={true} />
            ) : (
              <>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={PERFORMANCE_DATA}>
                      <defs>
                        <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#059669" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#059669" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        domain={chartMode === 'compare' ? [-3, 16] : ['dataMin - 50', 'dataMax + 50']}
                        tickFormatter={(v) => (chartMode === 'compare' ? `${v}%` : `${v}M`)}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.5rem', fontSize: '12px' }}
                        formatter={(value: any, name: string) => [
                          chartMode === 'compare' ? `${value > 0 ? '+' : ''}${value}%` : `${value} Triệu ₫`,
                          name
                        ]}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />

                      {/* 1. Main EquiFolio Portfolio Area */}
                      <Area
                        type="monotone"
                        dataKey={chartMode === 'compare' ? 'navReturn' : 'navVal'}
                        name={chartMode === 'compare' ? 'Danh mục EquiFolio (+13.3%)' : 'Tổng NAV Danh mục'}
                        stroke="#059669"
                        strokeWidth={2.5}
                        fillOpacity={1}
                        fill="url(#colorNav)"
                      />

                      {/* 2. VN-Index Benchmark Comparison Line */}
                      {chartMode === 'compare' && (
                        <Line
                          type="monotone"
                          dataKey="vniReturn"
                          name="Chỉ số VN-Index (+7.5%)"
                          stroke="#64748b"
                          strokeWidth={2}
                          strokeDasharray="4 4"
                          dot={false}
                        />
                      )}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Performance Metric Badges */}
                <div className="grid grid-cols-3 gap-3 pt-4 mt-2 border-t border-border-subtle text-xs text-center">
                  <div className="p-2 rounded bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold">Chỉ số Alpha (Thắng TT)</span>
                    <p className="font-extrabold text-accent-emerald text-sm">+5.8% YTD</p>
                  </div>
                  <div className="p-2 rounded bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold">Hệ số Beta (Độ biến động)</span>
                    <p className="font-extrabold text-text-primary text-sm">0.68 (Phòng thủ tốt)</p>
                  </div>
                  <div className="p-2 rounded bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold">Chỉ số Sharpe Ratio</span>
                    <p className="font-extrabold text-accent-gold text-sm">1.84 (Hiệu quả cao)</p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Holdings Table */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">Vị Thế Danh Mục Đa Tài Sản (Holdings)</h3>
                <p className="text-xs text-text-secondary">Được định giá tự động theo giá đóng cửa thị trường</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
                    <th className="pb-3 font-semibold">Mã / Tài sản</th>
                    <th className="pb-3 font-semibold">Phân loại</th>
                    <th className="pb-3 font-semibold text-right">Khối lượng</th>
                    <th className="pb-3 font-semibold text-right">Giá thị trường</th>
                    <th className="pb-3 font-semibold text-right">Tổng giá trị</th>
                    <th className="pb-3 font-semibold text-right">Tỷ trọng</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {valuation?.holdings.map((h, i) => (
                    <tr key={i} className="hover:bg-surface-container-low transition-colors">
                      <td className="py-3 font-bold text-text-primary">
                        {h.ticker}
                        <span className="block text-[11px] font-normal text-text-muted">{h.assetName}</span>
                      </td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          h.assetClass === 'STOCK' ? 'bg-accent-emerald-light text-accent-emerald' :
                          h.assetClass === 'GOLD' ? 'bg-accent-gold-light text-accent-gold' :
                          'bg-secondary-container text-secondary'
                        }`}>
                          {h.assetClass}
                        </span>
                      </td>
                      <td className="py-3 text-right font-medium">{h.quantity.toLocaleString('vi-VN')}</td>
                      <td className="py-3 text-right font-medium">{formatVND(h.currentPrice)}</td>
                      <td className="py-3 text-right font-bold text-text-primary">{formatVND(h.marketValue)}</td>
                      <td className="py-3 text-right font-bold text-accent-emerald">
                        {(h.allocationPercent * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Donut Allocation */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider mb-1">Cơ Cấu Tài Sản Thực Tế</h3>
            <p className="text-xs text-text-secondary mb-4">So với mốc neo SAA (35% - 35% - 30%)</p>
            <div className="h-56 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {donutData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={DONUT_COLORS[index % DONUT_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => [`${value}%`, 'Tỷ trọng']} />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Financial Copilot Action Card */}
          <div className="bg-surface-container-lowest border-2 border-accent-emerald/30 rounded-xl p-6 shadow-md relative overflow-hidden">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-accent-emerald-light flex items-center justify-center text-accent-emerald">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-text-primary">Financial Copilot</h4>
                <span className="text-[10px] text-accent-emerald font-semibold uppercase tracking-wider">Zero-Trust Advisor</span>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-surface-container-low border border-border-subtle text-xs space-y-2">
              <div className="flex items-center gap-1.5 text-accent-gold font-bold">
                <AlertTriangle className="w-4 h-4" />
                <span>Phát hiện lệch tỷ trọng (+20.1% Cổ phiếu)</span>
              </div>
              <p className="text-text-secondary leading-relaxed">
                Thị trường cổ phiếu vừa tăng mạnh khiến tỷ trọng Cổ phiếu đạt 55.1% (vượt mốc 35%). Khuyến nghị bán bớt 2.800 cp HPG để chốt lời và mua thêm Vàng SJC phòng thủ.
              </p>
            </div>

            {/* Action Items List */}
            <div className="mt-3 space-y-2 text-xs">
              {plan?.actions.map((act, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border border-border-subtle bg-surface flex items-center justify-between">
                  <div>
                    <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] mr-1.5 ${
                      act.actionType === 'SELL' ? 'bg-accent-rose-light text-accent-rose' : 'bg-accent-emerald-light text-accent-emerald'
                    }`}>
                      {act.actionType}
                    </span>
                    <span className="font-semibold text-text-primary">{act.ticker}</span>
                    <span className="text-text-muted text-[11px] block">{act.note}</span>
                  </div>
                  <span className="font-bold text-text-primary">{act.roundedQuantity.toLocaleString()}</span>
                </div>
              ))}
            </div>

            {/* Human in the loop confirmation button */}
            <div className="mt-4">
              {confirmedExecution ? (
                <div className="w-full py-2.5 rounded-lg bg-accent-emerald-light text-accent-emerald font-bold text-xs flex items-center justify-center gap-2 border border-accent-emerald">
                  <CheckCircle className="w-4 h-4" />
                  <span>Đã xác nhận & Cập nhật Sổ cái ACID</span>
                </div>
              ) : (
                <button
                  onClick={onConfirmRebalance}
                  className="w-full py-2.5 px-4 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-all font-bold text-xs flex items-center justify-center gap-2 shadow-sm"
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>Xác nhận đã thực hiện ngoài đời</span>
                </button>
              )}
              <p className="text-[10px] text-text-muted text-center mt-2">
                *Nguyên tắc Human-in-the-Loop: Hệ thống chỉ tạo bút toán sau khi bạn xác nhận đã giao dịch thực tế.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
