import { useState, useEffect } from 'react';
import {
  Shield, Wallet, Receipt, LineChart, PiggyBank, Bot,
  TrendingUp, CheckCircle, Award, AlertTriangle, RefreshCw
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import {
  getPortfolioValuation, getRebalancePlan, getUserProfile,
  PortfolioValuation, RebalancePlan, UserProfile
} from './services/api';

// Performance chart data
const performanceData = [
  { month: 'T1', nav: 1280 },
  { month: 'T2', nav: 1310 },
  { month: 'T3', nav: 1295 },
  { month: 'T4', nav: 1340 },
  { month: 'T5', nav: 1390 },
  { month: 'T6', nav: 1370 },
  { month: 'T7', nav: 1410 },
  { month: 'T8', nav: 1435 },
  { month: 'T9', nav: 1450.28 },
];

const DONUT_COLORS = ['#059669', '#d97706', '#0284c7'];

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'ledger' | 'markowitz' | 'savings' | 'survey' | 'copilot'>('overview');
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [plan, setPlan] = useState<RebalancePlan | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmedExecution, setConfirmedExecution] = useState(false);

  // Survey state
  const [surveyScores, setSurveyScores] = useState<number[]>([14, 14, 14, 14, 12]);

  const loadData = async () => {
    setLoading(true);
    const [valData, planData, profData] = await Promise.all([
      getPortfolioValuation(),
      getRebalancePlan(),
      getUserProfile(),
    ]);
    setValuation(valData);
    setPlan(planData);
    setProfile(profData);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const donutData = valuation ? [
    { name: 'Cổ phiếu VN30', value: Math.round((valuation.currentAllocations.STOCK || 0.55) * 100) },
    { name: 'Vàng SJC', value: Math.round((valuation.currentAllocations.GOLD || 0.18) * 100) },
    { name: 'Tiết kiệm & Tiền mặt', value: Math.round((valuation.currentAllocations.CASH_SAVINGS || 0.27) * 100) },
  ] : [];

  const handleConfirmRebalance = () => {
    setConfirmedExecution(true);
    setTimeout(() => {
      alert("Hệ thống Sổ cái kép đã ghi nhận bút toán tái cơ cấu! Trạng thái danh mục đã được cân bằng lại.");
    }, 300);
  };

  const formatVND = (amount: number) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  };

  return (
    <div className="min-h-screen bg-surface flex text-text-primary">
      {/* ==================== SIDEBAR ==================== */}
      <aside className="w-72 bg-surface-container-lowest border-r border-border-subtle flex flex-col justify-between h-screen fixed top-0 left-0 z-40 select-none">
        <div className="p-6">
          {/* Brand Header */}
          <div className="flex items-center gap-3 pb-6 border-b border-border-subtle">
            <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center border border-border-subtle shadow-sm text-accent-emerald">
              <Shield className="w-6 h-6 fill-accent-emerald/20 text-accent-emerald" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary tracking-tight">EquiFolio</h1>
              <p className="text-[11px] text-text-muted uppercase tracking-wider font-semibold">Swiss Wealth Architecture</p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="mt-6 space-y-1.5">
            <button
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'overview'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <Wallet className={`w-5 h-5 ${activeTab === 'overview' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>Tổng quan tài sản</span>
            </button>

            <button
              onClick={() => setActiveTab('ledger')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'ledger'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <Receipt className={`w-5 h-5 ${activeTab === 'ledger' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>Sổ cái kép ACID</span>
            </button>

            <button
              onClick={() => setActiveTab('markowitz')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'markowitz'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <LineChart className={`w-5 h-5 ${activeTab === 'markowitz' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>Tối ưu Markowitz</span>
            </button>

            <button
              onClick={() => setActiveTab('savings')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'savings'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <PiggyBank className={`w-5 h-5 ${activeTab === 'savings' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>Sổ tiết kiệm & Lãi kép</span>
            </button>

            <button
              onClick={() => setActiveTab('survey')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'survey'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <Award className={`w-5 h-5 ${activeTab === 'survey' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>Khảo sát rủi ro (SAA)</span>
            </button>

            <button
              onClick={() => setActiveTab('copilot')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'copilot'
                  ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
              }`}
            >
              <Bot className={`w-5 h-5 ${activeTab === 'copilot' ? 'text-accent-emerald' : 'text-text-muted'}`} />
              <span>AI Copilot Cố vấn</span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-6 border-t border-border-subtle bg-surface-container-lowest">
          <div className="p-3 rounded-lg bg-surface-container-low border border-border-subtle mb-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></span>
              <span>PostgreSQL 16 + pgvector</span>
            </div>
            <p className="text-[11px] text-text-muted mt-1">Lõi Sổ cái kép ACID sẵn sàng</p>
          </div>
          <p className="text-[11px] text-text-muted text-center">CT250H • Niên Luận Chuyên Ngành</p>
        </div>
      </aside>

      {/* ==================== MAIN CONTENT WRAPPER ==================== */}
      <div className="ml-72 flex-1 flex flex-col min-h-screen">
        {/* Top Header */}
        <header className="h-16 px-8 bg-surface-container-lowest border-b border-border-subtle flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-4">
            <span className="text-base font-bold text-text-primary tracking-tight">EquiFolio Wealth Terminal</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-surface-container border border-border-subtle text-text-muted">
              v1.0.0-PROD
            </span>
          </div>

          <div className="flex items-center gap-4">
            {/* Live NAV Status & Refresh */}
            <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container border border-border-subtle">
              <span className={`w-2 h-2 rounded-full ${loading ? 'bg-amber-500 animate-ping' : 'bg-accent-emerald'}`}></span>
              <span className="text-xs font-semibold text-text-secondary">
                NAV: {valuation ? formatVND(valuation.totalNetWorth) : '1,450,280,000 ₫'}
              </span>
              <button 
                onClick={loadData}
                disabled={loading}
                title="Làm mới dữ liệu từ API"
                className="ml-1 p-0.5 rounded hover:bg-surface-container-high transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-text-muted hover:text-accent-emerald ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            {/* User Profile Capsule */}
            <div className="flex items-center gap-2 pl-3 border-l border-border-subtle">
              <div className="w-8 h-8 rounded-full bg-accent-emerald-light border border-accent-emerald/30 flex items-center justify-center text-accent-emerald font-bold text-xs">
                AN
              </div>
              <div className="text-left hidden sm:block">
                <p className="text-xs font-bold text-text-primary leading-tight">Alex Nguyen</p>
                <p className="text-[10px] text-accent-emerald font-semibold">Khách hàng Private VIP</p>
              </div>
            </div>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <main className="p-8 space-y-6 flex-1">
          {/* ==================== TAB 1: OVERVIEW DASHBOARD ==================== */}
          {activeTab === 'overview' && (
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

                {/* KPI 2: Tiền mặt */}
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

                {/* KPI 3: Tiết kiệm & Lãi kép */}
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

                {/* KPI 4: ONNX ML Monitor */}
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

              {/* Main Content Grid: Chart (Left) + Donut & Copilot (Right) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column (8 cols): Performance Chart & Holdings Table */}
                <div className="lg:col-span-8 space-y-6">
                  {/* Chart Card */}
                  <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">Đường Cong Hiệu Suất Tài Sản Ròng</h3>
                        <p className="text-xs text-text-secondary">Tăng trưởng bền vững theo chu kỳ 9 tháng gần nhất</p>
                      </div>
                      <span className="text-xs font-semibold px-2.5 py-1 bg-surface-container-low rounded-lg text-text-secondary border border-border-subtle">
                        YTD 2026
                      </span>
                    </div>
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={performanceData}>
                          <defs>
                            <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#059669" stopOpacity={0.25} />
                              <stop offset="95%" stopColor="#059669" stopOpacity={0.0} />
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} />
                          <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} domain={['dataMin - 50', 'dataMax + 50']} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.5rem', fontSize: '12px' }}
                            formatter={(value: any) => [`${value} Triệu ₫`, 'Tổng NAV']}
                          />
                          <Area type="monotone" dataKey="nav" stroke="#059669" strokeWidth={2.5} fillOpacity={1} fill="url(#colorNav)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
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

                {/* Right Column (4 cols): Donut & Copilot Widget */}
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
                          onClick={handleConfirmRebalance}
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
          )}

          {/* ==================== TAB 2: LEDGER JOURNAL ==================== */}
          {activeTab === 'ledger' && (
            <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
              <div className="flex items-center justify-between border-b border-border-subtle pb-4">
                <div>
                  <h2 className="text-lg font-bold text-text-primary tracking-tight">Nhật Ký Sổ Cái Kép (Double-Entry Journal)</h2>
                  <p className="text-xs text-text-secondary">Tuân thủ nghiêm ngặt bất biến kế toán ngân hàng: Σ Debit - Σ Credit = 0</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/30">
                  <CheckCircle className="w-4 h-4" />
                  <span>Bảo toàn tính toán 100% ACID</span>
                </div>
              </div>

              {/* Ledger Entries Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
                      <th className="pb-3 font-semibold">Mã Giao Dịch</th>
                      <th className="pb-3 font-semibold">Tài Khoản Ghi Nợ (Debit +)</th>
                      <th className="pb-3 font-semibold">Tài Khoản Ghi Có (Credit -)</th>
                      <th className="pb-3 font-semibold text-right">Số Tiền (VND)</th>
                      <th className="pb-3 font-semibold text-center">Trạng Thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    <tr className="hover:bg-surface-container-low">
                      <td className="py-3 font-mono font-bold text-text-primary">TX_INIT_CAPITAL</td>
                      <td className="py-3 font-semibold text-accent-emerald">VND_WALLET (+85.280.000)</td>
                      <td className="py-3 font-semibold text-accent-rose">EQUITY_CAPITAL (-85.280.000)</td>
                      <td className="py-3 text-right font-bold">85,280,000 ₫</td>
                      <td className="py-3 text-center"><span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">POSTED</span></td>
                    </tr>
                    <tr className="hover:bg-surface-container-low">
                      <td className="py-3 font-mono font-bold text-text-primary">TX_BUY_HPG_01</td>
                      <td className="py-3 font-semibold text-accent-emerald">STOCK_HPG (+16.000 CP)</td>
                      <td className="py-3 font-semibold text-accent-rose">VND_WALLET (-456.000.000)</td>
                      <td className="py-3 text-right font-bold">456,000,000 ₫</td>
                      <td className="py-3 text-center"><span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">POSTED</span></td>
                    </tr>
                    <tr className="hover:bg-surface-container-low">
                      <td className="py-3 font-mono font-bold text-text-primary">TX_BUY_GOLD_SJC</td>
                      <td className="py-3 font-semibold text-accent-emerald">GOLD_SJC (+31.7 Chỉ)</td>
                      <td className="py-3 font-semibold text-accent-rose">VND_WALLET (-266.600.000)</td>
                      <td className="py-3 text-right font-bold">266,600,000 ₫</td>
                      <td className="py-3 text-center"><span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">POSTED</span></td>
                    </tr>
                    <tr className="hover:bg-surface-container-low">
                      <td className="py-3 font-mono font-bold text-text-primary">TX_DEPOSIT_VCB</td>
                      <td className="py-3 font-semibold text-accent-emerald">SAVINGS_VCB (+300.000.000)</td>
                      <td className="py-3 font-semibold text-accent-rose">VND_WALLET (-300.000.000)</td>
                      <td className="py-3 text-right font-bold">300,000,000 ₫</td>
                      <td className="py-3 text-center"><span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">POSTED</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ==================== TAB 3: MARKOWITZ OPTIMIZER ==================== */}
          {activeTab === 'markowitz' && (
            <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
              <div className="border-b border-border-subtle pb-4">
                <h2 className="text-lg font-bold text-text-primary tracking-tight">Bộ Tối Ưu Hóa Danh Mục Markowitz (MVO & TAA)</h2>
                <p className="text-xs text-text-secondary">Kết hợp hệ số ngại rủi ro cá nhân (λ = 3.88) với dự báo xu hướng máy học chu kỳ T+20</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
                  <span className="text-xs text-text-muted uppercase font-bold">Mô Hình Toán Học</span>
                  <div className="text-sm font-bold text-text-primary mt-1 font-mono">max U = w^T μ - 0.5 λ w^T Σ w</div>
                  <p className="text-[11px] text-text-secondary mt-1">Giải bài toán Quadratic Programming tìm vector tỷ trọng tối ưu</p>
                </div>
                <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
                  <span className="text-xs text-text-muted uppercase font-bold">Ràng Buộc Sàn HOSE</span>
                  <div className="text-sm font-bold text-accent-emerald mt-1">Lô Chẵn 100 Cổ Phiếu</div>
                  <p className="text-[11px] text-text-secondary mt-1">Tự động làm tròn khối lượng khớp lệnh thực tế, chuyển tiền lẻ về ví</p>
                </div>
                <div className="p-4 rounded-lg bg-surface-container-low border border-border-subtle">
                  <span className="text-xs text-text-muted uppercase font-bold">Biên Độ An Toàn (Collars)</span>
                  <div className="text-sm font-bold text-accent-gold mt-1">±15% Quanh SAA</div>
                  <p className="text-[11px] text-text-secondary mt-1">Ngăn chặn rủi ro tất tay (All-in), duy trì đệm thanh khoản tiền gửi</p>
                </div>
              </div>

              {/* Rebalance Plan Summary */}
              <div className="p-5 rounded-xl border border-accent-emerald/30 bg-accent-emerald-light/30">
                <h4 className="text-sm font-bold text-text-primary mb-2">Đề Xuất Kế Hoạch Tái Cơ Cấu TAA</h4>
                <p className="text-xs text-text-secondary leading-relaxed mb-4">
                  {plan?.executiveSummary}
                </p>
                <div className="space-y-2">
                  {plan?.actions.map((act, i) => (
                    <div key={i} className="p-3 rounded-lg bg-white border border-border-subtle flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          act.actionType === 'SELL' ? 'bg-accent-rose-light text-accent-rose' : 'bg-accent-emerald-light text-accent-emerald'
                        }`}>
                          {act.actionType}
                        </span>
                        <span className="font-bold text-text-primary">{act.ticker}</span>
                        <span className="text-text-muted">({act.assetName})</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-text-primary">{act.roundedQuantity.toLocaleString()} đơn vị</span>
                        <span className="block text-[11px] text-text-muted">Ước tính: {formatVND(act.estimatedTotalMoney)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ==================== TAB 4: SAVINGS & COMPOUND INTEREST ==================== */}
          {activeTab === 'savings' && (
            <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
              <div className="flex items-center justify-between border-b border-border-subtle pb-4">
                <div>
                  <h2 className="text-lg font-bold text-text-primary tracking-tight">Sổ Tiền Gửi Tiết Kiệm & Động Cơ Lãi Kép</h2>
                  <p className="text-xs text-text-secondary">Batch Job tự động tính lãi tích lũy hàng ngày và tái tục gốc + lãi khi đáo hạn</p>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold text-accent-emerald bg-accent-emerald-light px-3 py-1 rounded-full border border-accent-emerald/30">
                    Lãi kép tự động (Auto-Rollover)
                  </span>
                </div>
              </div>

              {/* Savings Details */}
              <div className="p-5 rounded-xl border border-border-subtle bg-surface-container-low flex flex-col md:flex-row items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-text-primary">Vietcombank - Sổ 01</span>
                    <span className="px-2 py-0.5 rounded bg-accent-emerald-light text-accent-emerald text-[10px] font-bold">ACTIVE</span>
                  </div>
                  <p className="text-xs text-text-secondary mt-1">Kỳ hạn: 6 Tháng • Lãi suất: 5.50%/năm • Đáo hạn: 12/04/2026</p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-text-muted uppercase font-bold">Số tiền gốc</span>
                  <div className="text-lg font-extrabold text-text-primary">300,000,000 ₫</div>
                  <span className="text-xs text-accent-gold font-bold">Lãi lũy kế: +4,075,000 ₫</span>
                </div>
              </div>
            </div>
          )}

          {/* ==================== TAB 5: SURVEY (RISK PROFILING) ==================== */}
          {activeTab === 'survey' && (
            <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
              <div className="border-b border-border-subtle pb-4">
                <h2 className="text-lg font-bold text-text-primary tracking-tight">Bộ Khảo Sát Khẩu Vị Rủi Ro Chuẩn Hóa (MiFID II)</h2>
                <p className="text-xs text-text-secondary">5 câu hỏi đo lường Năng lực tài chính khách quan và Tâm lý chịu đựng sụt giảm chủ quan</p>
              </div>

              <div className="space-y-4">
                {[
                  {
                    q: "1. Kỳ hạn đầu tư dự kiến",
                    desc: "Thời gian bạn dự kiến duy trì đầu tư mà không cần rút vốn chi tiêu?",
                    score: surveyScores[0],
                    options: [
                      { text: "Dưới 1 năm", val: 0 },
                      { text: "1 đến 3 năm", val: 7 },
                      { text: "3 đến 5 năm", val: 14 },
                      { text: "Trên 5 năm", val: 20 },
                    ]
                  },
                  {
                    q: "2. Tính ổn định dòng tiền",
                    desc: "Tình hình tài chính và quỹ dự phòng khẩn cấp hàng tháng?",
                    score: surveyScores[1],
                    options: [
                      { text: "Không có quỹ dự phòng", val: 0 },
                      { text: "Dư <10% & Dự phòng mỏng", val: 7 },
                      { text: "Dư 20-40% & Quỹ 6 tháng", val: 14 },
                      { text: "Dư >40% & Quỹ >12 tháng", val: 20 },
                    ]
                  },
                  {
                    q: "3. Mục tiêu tài chính ưu tiên",
                    desc: "Mục tiêu quan trọng nhất đối với danh mục tài sản này?",
                    score: surveyScores[2],
                    options: [
                      { text: "Bảo toàn vốn tuyệt đối", val: 0 },
                      { text: "Bù đắp lạm phát nhẹ", val: 7 },
                      { text: "Tăng trưởng cân bằng vốn", val: 14 },
                      { text: "Tối đa hóa tài sản dài hạn", val: 20 },
                    ]
                  },
                  {
                    q: "4. Thử nghiệm khi giảm -15%",
                    desc: "Phản ứng của bạn nếu danh mục sụt giảm -15% trong 1 tháng?",
                    score: surveyScores[3],
                    options: [
                      { text: "Bán cắt lỗ toàn bộ", val: 0 },
                      { text: "Lo lắng, bán một nửa", val: 7 },
                      { text: "Bình tĩnh, giữ kỷ luật", val: 14 },
                      { text: "Mua thêm quyết liệt", val: 20 },
                    ]
                  },
                  {
                    q: "5. Kinh nghiệm thực tế",
                    desc: "Kinh nghiệm đầu tư cổ phiếu, vàng và các kênh tài sản?",
                    score: surveyScores[4],
                    options: [
                      { text: "Chưa từng đầu tư", val: 0 },
                      { text: "Chỉ gửi tiết kiệm ngân hàng", val: 6 },
                      { text: "Đã đầu tư chứng khoán >1 năm", val: 12 },
                      { text: "Chuyên sâu thị trường >3 năm", val: 20 },
                    ]
                  },
                ].map((item, qIdx) => (
                  <div key={qIdx} className="p-4 rounded-lg border border-border-subtle bg-surface-container-low text-xs space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-bold text-text-primary text-sm">{item.q}</span>
                        <p className="text-text-secondary mt-0.5">{item.desc}</p>
                      </div>
                      <span className="px-3 py-1 rounded-full bg-surface-container text-xs font-bold text-accent-emerald border border-border-subtle">
                        {item.score} / 20đ
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                      {item.options.map((opt, oIdx) => (
                        <button
                          key={oIdx}
                          type="button"
                          onClick={() => {
                            const updated = [...surveyScores];
                            updated[qIdx] = opt.val;
                            setSurveyScores(updated);
                          }}
                          className={`p-2.5 rounded-lg border text-left text-xs transition-all ${
                            item.score === opt.val
                              ? 'border-accent-emerald bg-accent-emerald-light/40 text-accent-emerald font-bold shadow-xs'
                              : 'border-border-subtle bg-surface-container-lowest text-text-secondary hover:border-slate-300'
                          }`}
                        >
                          <div className="font-semibold">{opt.text}</div>
                          <div className="text-[10px] text-text-muted mt-0.5">+{opt.val} điểm</div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {(() => {
                const totalScore = surveyScores.reduce((acc: number, curr: number) => acc + curr, 0);
                const lambdaRisk = (10.0 - 0.09 * totalScore).toFixed(2);
                let profileLabel = 'Thận Trọng (Conservative)';
                let saaSummary = '20% Cổ phiếu • 20% Vàng • 60% Tiết kiệm';
                if (totalScore >= 75) {
                  profileLabel = 'Tăng Trưởng (Aggressive)';
                  saaSummary = '60% Cổ phiếu • 25% Vàng • 15% Tiết kiệm';
                } else if (totalScore >= 50) {
                  profileLabel = 'Cân Bằng (Balanced)';
                  saaSummary = '35% Cổ phiếu • 35% Vàng • 30% Tiết kiệm';
                }
                return (
                  <div className="p-5 rounded-xl border border-accent-emerald/30 bg-accent-emerald-light/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-bold text-text-primary">Kết Quả Khảo Sát Tổng Hợp</h4>
                      <p className="text-xs text-text-secondary mt-1">
                        Tổng điểm: <span className="font-bold text-accent-emerald">{totalScore}/100</span> • Hệ số ngại rủi ro λ = <span className="font-bold">{lambdaRisk}</span> • Nhóm <span className="font-bold text-text-primary">{profileLabel}</span>
                      </p>
                    </div>
                    <div className="text-left sm:text-right">
                      <span className="text-xs font-bold px-3 py-1.5 rounded-lg bg-accent-emerald text-white inline-block">
                        Tỷ trọng SAA: {saaSummary}
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* ==================== TAB 6: COPILOT ==================== */}
          {activeTab === 'copilot' && (
            <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
              <div className="border-b border-border-subtle pb-4">
                <h2 className="text-lg font-bold text-text-primary tracking-tight">Trợ Lý Tài Chính Thông Minh (Financial Copilot)</h2>
                <p className="text-xs text-text-secondary">Trò chuyện tự nhiên, tra cứu Hybrid Search RRF tài chính và hỗ trợ ra quyết định an toàn</p>
              </div>

              <div className="space-y-4">
                {/* Message 1: User */}
                <div className="flex gap-3 max-w-xl">
                  <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center font-bold text-xs">AN</div>
                  <div className="p-3.5 rounded-2xl rounded-tl-none bg-surface-container-low border border-border-subtle text-xs text-text-primary">
                    Tại sao hệ thống lại khuyên tao nên bán bớt cổ phiếu HPG để mua thêm Vàng SJC lúc này?
                  </div>
                </div>

                {/* Message 2: Copilot */}
                <div className="flex gap-3 max-w-2xl ml-auto flex-row-reverse">
                  <div className="w-8 h-8 rounded-full bg-accent-emerald text-white flex items-center justify-center font-bold text-xs">AI</div>
                  <div className="p-4 rounded-2xl rounded-tr-none bg-accent-emerald-light/40 border border-accent-emerald/30 text-xs text-text-primary space-y-2">
                    <p className="font-semibold text-accent-emerald">Chào anh Alex,</p>
                    <p className="leading-relaxed">
                      Lý do hệ thống đề xuất tái cơ cấu xuất phát từ 2 căn cứ khoa học:
                    </p>
                    <ol className="list-decimal pl-4 space-y-1 text-text-secondary">
                      <li>
                        <strong>Lệch tỷ trọng tự nhiên (Drift Detection):</strong> Đợt tăng giá vừa qua đã đẩy tỷ trọng Cổ phiếu của anh lên <strong>55.1%</strong>, vượt xa mốc mục tiêu <strong>35.0%</strong> đã thống nhất trong hồ sơ rủi ro ban đầu.
                      </li>
                      <li>
                        <strong>Tín hiệu chu kỳ liên thị trường:</strong> Mô hình LightGBM ONNX nhận thấy tỷ lệ Vàng/VN-Index đang ở vùng đáy chu kỳ và bắt đầu có dấu hiệu đảo chiều tích lũy. Việc chốt lời bớt 2.800 cp HPG (lô chẵn 100) để chuyển sang 9 chỉ Vàng SJC giúp anh khóa lợi nhuận và phòng hộ lạm phát.
                      </li>
                    </ol>
                    <p className="text-[11px] text-text-muted mt-2">
                      *Tư vấn tuân thủ nguyên tắc Zero-Trust: Em chỉ đưa ra khuyến nghị, anh vui lòng xem lại trước khi đặt lệnh ngoài app TCBS nhé!
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
