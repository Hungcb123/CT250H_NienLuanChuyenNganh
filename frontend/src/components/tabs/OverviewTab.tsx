import { useState, useEffect } from 'react';
import {
  Sparkles,
  ChevronDown, ChevronUp, ArrowUpRight, X, ArrowRight, RefreshCw
} from 'lucide-react';
import {
  ComposedChart, ReferenceLine, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid
} from 'recharts';
import {
  PortfolioValuation, RebalancePlan, UserProfile, TransactionItem, SavingsDepositItem,
  PortfolioHistoryResponse, RiskMetrics
} from '../../types';
import { formatVND } from '../../utils/formatters';
import { portfolioHistoryRange, historyDateLabel } from '../../utils/portfolioHistoryRange';
import { TradingDrawer } from '../trading/TradingDrawer';
import { CustomTargetsModal } from '../profile/CustomTargetsModal';
import { useTheme } from '../../context/ThemeContext';
import {
  getTransactions, getSavingsDeposits,
  getPortfolioHistory, getRiskMetrics
} from '../../services/api';
import { RegimeIndicator } from '../market/RegimeIndicator';

interface OverviewTabProps {
  valuation: PortfolioValuation | null;
  plan: RebalancePlan | null;
  profile: UserProfile | null;
  confirmedExecution: boolean;
  onConfirmRebalance: () => void;
  executing?: boolean;
  onNavigateToSurvey?: () => void;
  onTradeSuccess?: () => Promise<void> | void;
}

type TimeframeOption = '1W' | '1M' | '3M' | 'YTD' | '1Y' | 'ALL';

export function OverviewTab({
  valuation,
  plan,
  profile: _profile,
  confirmedExecution,
  onConfirmRebalance,
  executing = false,
  onNavigateToSurvey,
  onTradeSuccess = () => {}
}: OverviewTabProps) {
  const { isDark } = useTheme();
  const [chartMode, setChartMode] = useState<'compare' | 'nav' | null>(null);
  const portfolioChartSelected = chartMode === 'compare' || chartMode === 'nav';
  const [timeframe, setTimeframe] = useState<TimeframeOption>('YTD');
  const [tradeDrawerOpen, setTradeDrawerOpen] = useState(false);
  const [selectedTradeTicker, setSelectedTradeTicker] = useState('HPG');
  const [selectedTradeAction, setSelectedTradeAction] = useState<'BUY' | 'SELL'>('BUY');
  const [customTargetsOpen, setCustomTargetsOpen] = useState(false);
  const [onboardingDismissed, setOnboardingDismissed] = useState<boolean>(() => {
    return localStorage.getItem('equifolio_onboarding_dismissed') === 'true';
  });

  // Holdings data is independent of the optional performance chart.
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [savingsDeposits, setSavingsDeposits] = useState<SavingsDepositItem[]>([]);
  const [historyData, setHistoryData] = useState<PortfolioHistoryResponse | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyRetry, setHistoryRetry] = useState(0);

  useEffect(() => {
    let active = true;
    const fetchAux = async () => {
      try {
        const [txs, deps] = await Promise.all([
          getTransactions(),
          getSavingsDeposits()
        ]);
        if (active) {
          setTransactions(txs || []);
          setSavingsDeposits(deps || []);

        }
      } catch (err) {
        console.error("Failed to load transactions/savings in OverviewTab", err);
      }
    };
    fetchAux();
    return () => { active = false; };
  }, [valuation]);

  useEffect(() => {
    if (!portfolioChartSelected) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let hasLoaded = false;
    setLoadingHistory(true);
    setHistoryData(null);
    setHistoryError(null);
    const load = async () => {
      try {
        const history = await getPortfolioHistory(timeframe);
        if (!active) return;
        hasLoaded = true;
        setHistoryData(history);
        setHistoryError(null);
        if (history.updating || history.status === 'PREPARING') timer = setTimeout(load, 5000);
      } catch {
        if (!active) return;
        if (!hasLoaded) setHistoryError('Chưa tải được lịch sử cho khoảng thời gian này. Vui lòng thử lại.');
        else timer = setTimeout(load, 15000);
      } finally {
        if (active) setLoadingHistory(false);
      }
    };
    void load();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [portfolioChartSelected, timeframe, valuation, historyRetry]);

  useEffect(() => {
    let active = true;
    getRiskMetrics().then(risk => { if (active) setRiskMetrics(risk); })
      .catch(() => { if (active) setRiskMetrics(null); });
    return () => { active = false; };
  }, [valuation, historyData?.dataVersion]);

  const annualizedReturn = riskMetrics?.riskRating === 'HISTORICAL'
    && Number.isFinite(riskMetrics.annualizedReturnPercent)
    ? riskMetrics.annualizedReturnPercent : null;

  const hasAssets = valuation && valuation.totalNetWorth > 0;
  const stockPct = Math.round((valuation?.currentAllocations.STOCK || 0) * 100);
  const goldPct = Math.round((valuation?.currentAllocations.GOLD || 0) * 100);
  const savingsPct = Math.round((valuation?.currentAllocations.SAVINGS || 0) * 100);
  const cashAllocationPct = Math.round((valuation?.currentAllocations.CASH || 0) * 100);

  const targetStock = Math.round(((plan?.taaTargets?.STOCK ?? plan?.targetAllocations?.STOCK) ?? 0.35) * 100);
  const targetGold = Math.round(((plan?.taaTargets?.GOLD ?? plan?.targetAllocations?.GOLD) ?? 0.35) * 100);
  const targetSavings = Math.round(((plan?.taaTargets?.SAVINGS ?? plan?.targetAllocations?.SAVINGS) ?? 0.20) * 100);
  const targetCash = Math.round(((plan?.taaTargets?.CASH ?? plan?.targetAllocations?.CASH) ?? 0.10) * 100);

  // Accurate Holdings computation: real cost basis, actual deposit details, and zero fake profits
  const resolvedHoldings = (valuation?.holdings || []).map((h) => {
    if (h.assetClass === 'CASH' || h.accountCode === 'VND_WALLET') {
      return {
        ticker: 'VND',
        assetName: 'Tiền mặt khả dụng',
        assetClass: 'CASH',
        quantityDisplay: '-',
        costPriceDisplay: '-',
        currentPriceDisplay: formatVND(h.marketValue),
        pnlAmount: 0,
        pnlPercent: 0,
        isGain: true,
        isZero: true,
        rateNote: '',
        actionType: 'CASH' as const,
        actionNote: 'Khả dụng',
        rawCost: h.marketValue,
        rawMarket: h.marketValue
      };
    }

    if (h.assetClass === 'SAVINGS' || h.accountCode.startsWith('SAVINGS_')) {
      // Match savings deposit by principal amount or account code
      const deposit = savingsDeposits.find(d => Math.abs(d.principalAmount - h.marketValue) < 1000);
      const bankName = deposit?.bankName || 'Ngân hàng';
      const termMonths = deposit?.termMonths || 6;
      const rate = deposit?.interestRate || 5.5;
      const accrued = deposit?.accruedInterest || 0;
      const principal = deposit?.principalAmount || h.marketValue;
      const maturity = deposit?.maturityDate ? `Đến hạn ${deposit.maturityDate}` : `Kỳ hạn ${termMonths}T`;

      return {
        ticker: bankName,
        assetName: `Sổ tiết kiệm ${bankName} (${termMonths} tháng)`,
        assetClass: 'SAVINGS',
        quantityDisplay: '1 sổ',
        costPriceDisplay: formatVND(principal),
        currentPriceDisplay: formatVND(principal + accrued),
        pnlAmount: accrued,
        pnlPercent: accrued > 0 && principal > 0 ? (accrued / principal) * 100 : 0,
        isGain: accrued > 0,
        isZero: accrued === 0,
        rateNote: `Lãi ${rate}%/năm`,
        actionType: 'SAVINGS' as const,
        actionNote: maturity,
        rawCost: principal,
        rawMarket: principal + accrued
      };
    }

    // STOCK & GOLD: Calculate true acquisition cost from double-entry ledger transactions
    let totalCostPaid = 0;
    let totalQuantityBought = 0;

    for (const tx of transactions) {
      if (tx.type === 'TRADE_BUY' || tx.type === 'CAPITAL_INJECTION') {
        const assetEntry = tx.entries?.find(e =>
          (e.assetTicker === h.ticker || e.accountCode === h.accountCode) && e.amount > 0
        );
        const cashEntry = tx.entries?.find(e =>
          (e.assetTicker === 'VND' || e.accountCode === 'VND_WALLET' || e.accountCode === 'EQUITY_CAPITAL') && e.amount < 0
        );

        if (assetEntry && cashEntry) {
          totalCostPaid += Math.abs(cashEntry.amount);
          totalQuantityBought += assetEntry.amount;
        }
      }
    }

    // Prefer backend WAC (Weighted Average Cost) and unrealized P&L from LedgerService
    const costPrice = (h.costPrice !== undefined && h.costPrice > 0)
      ? h.costPrice
      : (totalQuantityBought > 0 ? Math.round(totalCostPaid / totalQuantityBought) : h.currentPrice);

    const currentPrice = h.currentPrice;
    const pnlAmount = h.unrealizedPnL !== undefined 
      ? h.unrealizedPnL 
      : ((currentPrice - costPrice) * h.quantity);
    const pnlPercent = h.unrealizedPnLPercent !== undefined 
      ? h.unrealizedPnLPercent 
      : (costPrice > 0 ? ((currentPrice - costPrice) / costPrice) * 100 : 0);

    return {
      ticker: h.ticker,
      assetName: h.assetName,
      assetClass: h.assetClass,
      quantityDisplay: h.quantity.toLocaleString('vi-VN'),
      costPriceDisplay: formatVND(costPrice),
      currentPriceDisplay: formatVND(currentPrice),
      pnlAmount,
      pnlPercent,
      isGain: pnlPercent > 0,
      isZero: pnlPercent === 0,
      rateNote: '',
      actionType: 'TRADE' as const,
      actionNote: '',
      rawCost: costPrice * h.quantity,
      rawMarket: currentPrice * h.quantity
    };
  });

  const totalInvestedCost = valuation?.totalCostBasis ?? resolvedHoldings.reduce((sum, item) => {
    return item.assetClass !== 'CASH' ? sum + item.rawCost : sum;
  }, 0);
  const totalUnrealizedPnL = valuation?.totalUnrealizedPnL ?? resolvedHoldings.reduce((sum, item) => {
    return sum + item.pnlAmount;
  }, 0);
  const portfolioPnLPercent = valuation?.totalPnLPercent ?? (totalInvestedCost > 0 
    ? (totalUnrealizedPnL / totalInvestedCost) * 100 
    : 0);

  const donutData = hasAssets ? [
    {
      name: 'Cổ phiếu VN30',
      value: stockPct,
      targetValue: targetStock,
      amount: valuation?.stockValue || 0,
      fill: '#10b981', // Emerald
      assetClass: 'STOCK'
    },
    {
      name: 'Vàng SJC',
      value: goldPct,
      targetValue: targetGold,
      amount: valuation?.goldValue || 0,
      fill: '#f59e0b', // Amber
      assetClass: 'GOLD'
    },
    {
      name: 'Tiết kiệm ngân hàng',
      value: savingsPct,
      targetValue: targetSavings,
      amount: valuation?.savingsValue || 0,
      fill: '#6366f1', // Indigo
      assetClass: 'SAVINGS'
    },
    {
      name: 'Tiền mặt khả dụng',
      value: cashAllocationPct,
      targetValue: targetCash,
      amount: valuation?.cashBalance || 0,
      fill: '#0ea5e9', // Sky
      assetClass: 'CASH'
    },
  ].filter(d => d.value > 0) : [];


  const cashPct = valuation && valuation.totalNetWorth > 0
    ? (valuation.cashBalance / valuation.totalNetWorth) * 100
    : 0;

  const chartRange = portfolioHistoryRange(timeframe, historyData?.points.map(point => point.date) ?? []);
  const currentChartData = (historyData?.points && historyData.points.length > 0)
    ? historyData.points.filter(pt => Date.parse(pt.date) >= chartRange[0] && Date.parse(pt.date) <= chartRange[1]).map(pt => ({
        timestamp: Date.parse(pt.date),
        date: pt.date.length >= 10 ? `${pt.date.substring(8, 10)}/${pt.date.substring(5, 7)}` : pt.date,
        navReturn: pt.navReturn ?? 0,
        vniReturn: pt.vniReturn ?? 0,
        navVal: pt.nav / 1_000_000,
        vniVal: Number((pt.vnindex ?? 0).toFixed(1))
      }))
    : [];
  const lastPoint = currentChartData[currentChartData.length - 1] || { navReturn: 0, vniReturn: 0, navVal: 0, vniVal: 0, date: '' };
  const benchmarkAvailable = !!historyData?.points.length && historyData.points.every(point => point.vnindex > 0);
  const alpha = benchmarkAvailable && historyData?.alphaPercent != null ? historyData.alphaPercent : null;
  const returnLabel = (value: number) => `${value > 0 ? '+' : ''}${value.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`;
  const resultReady = !loadingHistory && !historyError && currentChartData.length > 0;

  return (
    <div className="space-y-6">
      {/* 0. New Investor Onboarding Banner */}
      {!onboardingDismissed && (
        <section className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative overflow-hidden transition-all">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-accent-emerald flex items-center justify-center text-white shrink-0">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[11px] font-bold text-accent-emerald uppercase tracking-wider">
                    Thiết lập danh mục cá nhân
                  </span>
                </div>
                <h3 className="text-sm font-extrabold text-text-primary tracking-tight">
                  Chào mừng bạn đến với VNxCapital
                </h3>
                <p className="text-xs text-text-secondary mt-0.5 max-w-3xl leading-relaxed">
                  Hệ thống đang hiển thị danh mục mẫu để bạn trải nghiệm. Để cá nhân hóa khẩu vị rủi ro và xác lập danh mục đầu tư mục tiêu cho riêng bạn, hãy hoàn thành bài khảo sát ngắn.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 shrink-0 w-full md:w-auto">
              <button
                type="button"
                onClick={onNavigateToSurvey}
                className="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-accent-emerald hover:opacity-90 text-white font-bold text-xs shadow-xs transition-all cursor-pointer"
              >
                <span>Làm Khảo sát (1 phút)</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setOnboardingDismissed(true);
                  localStorage.setItem('equifolio_onboarding_dismissed', 'true');
                }}
                className="px-3 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-text-secondary hover:text-text-primary font-semibold text-xs border border-border-subtle transition-colors cursor-pointer"
              >
                Đóng
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setOnboardingDismissed(true);
              localStorage.setItem('equifolio_onboarding_dismissed', 'true');
            }}
            title="Đóng thông báo"
            className="absolute top-3 right-3 p-1 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-container transition-colors cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </section>
      )}


      <section className="border-b border-border-subtle pb-5" aria-label="Tổng quan tài sản">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-4">
          <h2 className="text-lg font-semibold text-text-primary">Tổng quan tài sản</h2>
        </div>
        <dl className="grid grid-cols-1 min-[400px]:grid-cols-2 xl:grid-cols-[1.5fr_1fr_1fr_1fr] gap-x-5 gap-y-4">
          <div className="min-w-0">
            <dt className="text-xs text-text-secondary mb-2">Tổng tài sản ròng</dt>
            <dd className="text-2xl sm:text-3xl font-semibold tracking-tight tabular-nums text-text-primary break-words">{valuation ? formatVND(valuation.totalNetWorth) : '—'}</dd>
            <dd className="mt-2 text-xs text-text-secondary" title="Lãi kép quy đổi năm từ toàn bộ lịch sử, đã điều chỉnh tiền nạp/rút.">
              Lợi suất quy đổi năm:{' '}
              <strong className={annualizedReturn == null || annualizedReturn === 0 ? 'text-text-primary' : annualizedReturn > 0 ? 'text-accent-emerald' : 'text-accent-rose'}>
                {annualizedReturn == null ? '—' : `${annualizedReturn > 0 ? '+' : ''}${annualizedReturn.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%/năm`}
              </strong>
            </dd>
          </div>
          <div className="min-w-0 xl:border-l xl:border-border-subtle xl:pl-5">
            <dt className="text-xs text-text-secondary mb-2">Lãi / lỗ tạm tính</dt>
            <dd className={`text-base font-semibold tabular-nums break-words ${totalUnrealizedPnL < 0 ? 'text-accent-rose' : totalUnrealizedPnL > 0 ? 'text-accent-emerald' : 'text-text-primary'}`}>{totalUnrealizedPnL > 0 ? '+' : ''}{formatVND(totalUnrealizedPnL)}</dd>
            <dd className="text-xs text-text-secondary mt-1">
              <span className={portfolioPnLPercent > 0 ? 'text-accent-emerald' : portfolioPnLPercent < 0 ? 'text-accent-rose' : 'text-text-primary'}>{portfolioPnLPercent > 0 ? '+' : ''}{portfolioPnLPercent.toFixed(1)}%</span>
            </dd>
          </div>
          <div className="min-w-0 xl:border-l xl:border-border-subtle xl:pl-5">
            <dt className="text-xs text-text-secondary mb-2">Tiền khả dụng</dt>
            <dd className="text-base font-semibold tabular-nums text-text-primary break-words">{valuation ? formatVND(valuation.cashBalance) : '—'}</dd>
            <dd className="text-xs text-text-secondary mt-1">{cashPct.toFixed(1)}% tổng tài sản</dd>
          </div>
          <div className="min-w-0 xl:border-l xl:border-border-subtle xl:pl-5">
            <dt className="text-xs text-text-secondary mb-2">Tiết kiệm</dt>
            <dd className="text-base font-semibold tabular-nums text-text-primary break-words">{valuation ? formatVND(valuation.savingsValue) : '—'}</dd>
            <dd className="text-xs text-text-secondary mt-1">{savingsDeposits.length} sổ tiền gửi</dd>
          </div>
        </dl>
      </section>

      {/* 3. Main Operational Grid: Charts & Holdings vs Donut & Copilot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols): Market Ticker + Realistic Chart + Holdings */}
        <div className="lg:col-span-8 space-y-5 min-w-0">
          <section className="bg-surface-container-lowest p-4 sm:px-6 sm:py-4" aria-label="Hiệu suất danh mục">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-text-primary">Hiệu suất danh mục</h3>
              <button type="button" aria-expanded={portfolioChartSelected} aria-controls="portfolio-performance"
                onClick={() => { if (portfolioChartSelected) setChartMode(null); else { setTimeframe('YTD'); setChartMode('compare'); } }}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-2 text-xs font-medium text-text-secondary hover:bg-surface-container hover:text-text-primary">
                {portfolioChartSelected ? 'Thu gọn' : 'Xem biểu đồ'}
                {portfolioChartSelected ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>
            </div>
            {portfolioChartSelected && <div id="portfolio-performance" className="mt-4">
              {historyData?.updating && <p role="status" className="mb-3 text-xs text-text-secondary">
                {historyData.status === 'PREPARING' ? 'Đang chuẩn bị dữ liệu hiệu suất ở nền…' : 'Đang cập nhật hiệu suất. Biểu đồ hiển thị bản hoàn tất gần nhất.'}
              </p>}

              {resultReady && <div className="mb-4">
                <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                  <span className="inline-flex items-center gap-2 text-text-secondary"><span aria-hidden="true" className="h-0.5 w-4 bg-accent-emerald" />
                    Danh mục <strong className="tabular-nums font-semibold text-text-primary">{chartMode === 'compare' ? returnLabel(lastPoint.navReturn) : formatVND(lastPoint.navVal * 1_000_000)}</strong>
                  </span>
                  {chartMode === 'compare' && benchmarkAvailable && <span className="inline-flex items-center gap-2 text-text-secondary"><span aria-hidden="true" className="w-4 border-t border-dashed border-text-secondary" />
                    VN-Index <strong className="tabular-nums font-semibold text-text-primary">{returnLabel(lastPoint.vniReturn)}</strong>
                  </span>}
                </div>
                {chartMode === 'compare' && alpha != null && <p className="mt-2 text-xs text-text-secondary">
                  {alpha === 0 ? 'Ngang bằng VN-Index' : `${alpha > 0 ? 'Cao hơn' : 'Thấp hơn'} VN-Index ${Math.abs(alpha).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} điểm %`}
                </p>}
                {chartMode === 'compare' && !benchmarkAvailable && <p className="mt-2 text-xs text-text-secondary">Chưa có dữ liệu VN-Index cùng kỳ để so sánh.</p>}
              </div>}
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex gap-1 rounded-md bg-surface-container-low p-1" aria-label="Chế độ biểu đồ">
                  {(['compare', 'nav'] as const).map(mode => <button key={mode} type="button" aria-pressed={chartMode === mode}
                    onClick={() => setChartMode(mode)} className={`rounded px-2.5 py-1.5 text-xs font-medium ${chartMode === mode ? 'bg-surface-container-high text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
                    {mode === 'compare' ? 'Lợi suất (%)' : 'Giá trị (₫)'}
                  </button>)}
                </div>
                <div className="flex flex-wrap gap-1" aria-label="Khoảng thời gian">
                  {(['1W', '1M', '3M', 'YTD', '1Y', 'ALL'] as TimeframeOption[]).map(tf => <button key={tf} type="button"
                    aria-pressed={timeframe === tf} onClick={() => setTimeframe(tf)}
                    className={`rounded px-2 py-1.5 text-xs ${timeframe === tf ? 'bg-accent-emerald-light font-semibold text-accent-emerald' : 'text-text-secondary hover:bg-surface-container'}`}>
                    {{ '1W': '1 tuần', '1M': '1T', '3M': '3T', YTD: 'Từ đầu năm', '1Y': '1N', ALL: 'Tất cả' }[tf]}
                  </button>)}
                </div>
              </div>
              {loadingHistory ? <div role="status" className="flex h-64 items-center justify-center gap-2 text-sm text-text-secondary"><RefreshCw className="h-4 w-4 animate-spin" />Đang tải lịch sử…</div>
                : historyError ? <p role="alert" className="py-8 text-sm text-text-secondary">{historyError}{' '}<button type="button" onClick={() => setHistoryRetry(value => value + 1)} className="underline text-accent-emerald">Thử lại</button></p>
                : !currentChartData.length ? <p role="status" className="py-8 text-sm text-text-secondary">{historyData?.status === 'PREPARING' ? 'Biểu đồ sẽ xuất hiện khi dữ liệu sẵn sàng.' : 'Chưa có lịch sử danh mục trong khoảng đã chọn.'}</p>
                : <>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart key={`${timeframe}-${chartMode}`} data={currentChartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke={isDark ? '#27272a' : '#f1f5f9'}
                      />
                      <XAxis
                        dataKey="timestamp"
                        type="number"
                        scale="time"
                        domain={[chartRange[0], Math.max(chartRange[0] + 1, chartRange[1])]}
                        allowDataOverflow
                        ticks={[0, 0.25, 0.5, 0.75, 1].map(ratio => chartRange[0] + (chartRange[1] - chartRange[0]) * ratio)}
                        tickFormatter={value => historyDateLabel(Number(value))}
                        minTickGap={35}
                        stroke={isDark ? '#71717a' : '#94a3b8'}
                        fontSize={11}
                        tickLine={false}
                      />
                      <YAxis
                        stroke={isDark ? '#71717a' : '#94a3b8'}
                        fontSize={11}
                        tickLine={false}
                        domain={chartMode === 'compare' ? ['dataMin - 1', 'dataMax + 1'] : ['dataMin - 30', 'dataMax + 30']}
                        tickFormatter={(v) => (chartMode === 'compare' ? `${v}%` : `${v}M`)}
                      />
                      <Tooltip
                        labelFormatter={value => historyDateLabel(Number(value))}
                        contentStyle={{
                          backgroundColor: isDark ? '#18181b' : '#ffffff',
                          borderColor: isDark ? '#27272a' : '#e2e8f0',
                          borderRadius: '0.75rem',
                          fontSize: '12px',
                          color: isDark ? '#f4f4f5' : '#0f172a',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.25)'
                        }}
                        formatter={(value: any, name: string) => [
                          chartMode === 'compare' ? `${value > 0 ? '+' : ''}${Number(value).toFixed(2)}%` : `${value} Triệu ₫`,
                          name
                        ]}
                      />

                      {chartMode === 'compare' && <ReferenceLine y={0} ifOverflow="extendDomain" stroke={isDark ? '#71717a' : '#94a3b8'} />}
                      <Line isAnimationActive={false} type="linear" dataKey={chartMode === 'compare' ? 'navReturn' : 'navVal'}
                        name="Danh mục" stroke="#059669" strokeWidth={2} dot={false} />
                      {/* 2. VN-Index Benchmark Comparison Line */}
                      {chartMode === 'compare' && benchmarkAvailable && (
                        <Line
                          isAnimationActive={false}
                          type="linear"
                          dataKey="vniReturn"
                          name="VN-Index"
                          stroke={isDark ? '#a1a1aa' : '#64748b'}
                          strokeWidth={1.75}
                          strokeDasharray="4 4"
                          dot={false}
                        />
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                </>}
              {resultReady && <p data-testid="history-range" className="mt-3 text-xs text-text-secondary">
                {historyDateLabel(chartRange[0])} – {historyDateLabel(chartRange[1])}
                {chartMode === 'compare' ? ' · Đã điều chỉnh tiền nạp/rút' : ' · Giá trị danh mục gồm tiền nạp/rút'}
                {historyData?.generatedAt && <span className="mt-1 block">
                  {historyData.provisional ? 'Tạm tính' : 'Đã chốt'} · Cập nhật {new Date(historyData.generatedAt).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}
                  {historyData.priceAsOf ? ` · Giá tham chiếu đến ${historyData.priceAsOf.split('-').reverse().join('/')}` : ''}
                </span>}
              </p>}
            </div>}
          </section>

          {/* Holdings Table Card (7 Standard Financial Columns) */}
          <div className="bg-surface-container-lowest p-4 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold text-text-primary">Danh mục đang nắm giữ</h3>
                <p className="text-xs text-text-secondary mt-0.5">Giá vốn tính từ sổ lệnh khớp thực tế • Giá thị trường cập nhật thời gian thực</p>
              </div>
              <button
                onClick={() => {
                  setSelectedTradeTicker('HPG');
                  setSelectedTradeAction('BUY');
                  setTradeDrawerOpen(true);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-emerald hover:opacity-90 text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
              >
                <ArrowUpRight className="w-3.5 h-3.5" />
                Đặt Lệnh Nhanh
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px] font-bold">
                    <th className="pb-3">Mã tài sản</th>
                    <th className="pb-3">Loại</th>
                    <th className="pb-3 text-right">Khối lượng</th>
                    <th className="pb-3 text-right">Giá vốn</th>
                    <th className="pb-3 text-right">Giá thị trường</th>
                    <th className="pb-3 text-right">Lãi/Lỗ (%)</th>
                    <th className="pb-3 text-right">Hành động</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle/60">
                  {resolvedHoldings.length > 0 ? (
                    resolvedHoldings.map((h, i) => (
                      <tr key={i} className="hover:bg-surface-container-low/70 transition-colors">
                        <td className="py-3.5 font-bold text-text-primary">
                          <span className="font-mono-num font-extrabold text-sm">{h.ticker}</span>
                          <span className="block text-[11px] font-normal text-text-muted mt-0.5">{h.assetName}</span>
                        </td>
                        <td className="py-3.5">
                          <span className="text-[11px] font-semibold text-text-secondary">
                            {h.assetClass === 'STOCK' ? 'Cổ phiếu' :
                             h.assetClass === 'GOLD' ? 'Vàng SJC' :
                             h.assetClass === 'SAVINGS' ? 'Tiết kiệm' : 'Tiền mặt'}
                          </span>
                        </td>
                        <td className="py-3.5 text-right font-medium font-mono-num text-text-secondary">
                          {h.quantityDisplay}
                        </td>
                        <td className="py-3.5 text-right font-medium font-mono-num text-text-muted">
                          {h.costPriceDisplay}
                        </td>
                        <td className="py-3.5 text-right font-medium font-mono-num text-text-primary">
                          {h.currentPriceDisplay}
                        </td>
                        <td className="py-3.5 text-right font-mono-num">
                          {h.assetClass === 'CASH' ? (
                            <span className="text-text-muted">0.0%</span>
                          ) : h.assetClass === 'SAVINGS' ? (
                            <div>
                              <span className={h.pnlAmount > 0 ? 'text-accent-emerald font-bold' : 'text-text-muted font-semibold'}>
                                {h.pnlAmount > 0 ? `+${formatVND(h.pnlAmount)}` : '0 ₫'}
                              </span>
                              <span className="block text-[10px] text-text-muted">
                                {h.rateNote}
                              </span>
                            </div>
                          ) : h.isZero ? (
                            <div>
                              <span className="text-text-muted font-semibold">0.0%</span>
                              <span className="block text-[10px] text-text-muted">0 ₫</span>
                            </div>
                          ) : (
                            <div>
                              <span className={`font-bold ${h.isGain ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                                {h.isGain ? '+' : ''}{h.pnlPercent.toFixed(1)}%
                              </span>
                              <span className={`block text-[10px] ${h.isGain ? 'text-accent-emerald/80' : 'text-accent-rose/80'}`}>
                                {h.isGain ? '+' : ''}{formatVND(h.pnlAmount)}
                              </span>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 text-right">
                          {h.actionType === 'TRADE' ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => {
                                  setSelectedTradeTicker(h.ticker);
                                  setSelectedTradeAction('BUY');
                                  setTradeDrawerOpen(true);
                                }}
                                className="px-2.5 py-1 rounded bg-accent-emerald hover:opacity-90 text-white font-bold text-[11px] transition-opacity cursor-pointer shadow-2xs"
                              >
                                Mua
                              </button>
                              <button
                                onClick={() => {
                                  setSelectedTradeTicker(h.ticker);
                                  setSelectedTradeAction('SELL');
                                  setTradeDrawerOpen(true);
                                }}
                                className="px-2.5 py-1 rounded bg-accent-rose hover:opacity-90 text-white font-bold text-[11px] transition-opacity cursor-pointer shadow-2xs"
                              >
                                Bán
                              </button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-text-muted">
                              {h.actionNote}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-text-muted">
                        <div className="flex flex-col items-center justify-center gap-1.5">
                          <p className="font-semibold text-text-primary text-xs">Danh mục chưa có tài sản nào</p>
                          <p className="text-[11px] text-text-muted">
                            Bạn hãy sang tab <strong>Sổ cái kép</strong> để nạp vốn hoặc khai báo tài sản ban đầu.
                          </p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <aside className="lg:col-span-4 space-y-8 lg:border-l lg:border-border-subtle lg:pl-6">
          <section aria-label="Phân bổ tài sản">
            <div className="flex items-center justify-between gap-3 mb-2">
              <h3 className="text-base font-semibold text-text-primary">Phân bổ tài sản</h3>
              <button type="button" onClick={() => setCustomTargetsOpen(true)} className="text-xs text-text-primary underline underline-offset-4 hover:text-accent-emerald">Chỉnh mục tiêu</button>
            </div>
            <p className="text-xs text-text-secondary mb-4">Thực tế so với mục tiêu SAA · vạch đứng là mục tiêu</p>
            {donutData.length ? <div className="space-y-4">{donutData.map(item => <div key={item.assetClass}>
              <div className="flex justify-between gap-3 text-sm mb-2"><span className="text-text-primary">{item.name}</span><strong className="font-semibold tabular-nums text-text-primary">{item.value}% <span className="font-normal text-text-secondary">/ {item.targetValue}%</span></strong></div>
              <div className="relative h-2 bg-surface-container-highest" role="img" aria-label={`${item.name}: ${item.value}%, mục tiêu ${item.targetValue}%`}>
                <div className="h-full bg-text-primary/70" style={{width: `${Math.min(100, Math.max(0, item.value))}%`}} />
                <span className="absolute -top-1 h-4 w-px bg-text-primary" style={{left: `${Math.min(100, Math.max(0, item.targetValue))}%`}} />
              </div>
              <p className="text-xs text-text-secondary tabular-nums mt-2">{formatVND(item.amount)}</p>
            </div>)}</div> : <p className="text-sm text-text-secondary py-8">Chưa có tài sản để hiển thị phân bổ.</p>}
          </section>
          <section className="border-t border-border-subtle pt-6" aria-label="Cần chú ý">
            <h3 className="text-base font-semibold text-text-primary mb-4">Cần chú ý</h3>
            <p className="text-sm text-text-primary leading-relaxed">{!plan ? 'Chưa có dữ liệu đánh giá danh mục.' : plan.driftDetected ? `Danh mục lệch mục tiêu tối đa ${plan.maxDriftPercent}%. Xem kế hoạch trước khi điều chỉnh.` : confirmedExecution ? 'Đã tái cân bằng danh mục.' : 'Chưa cần tái cân bằng danh mục.'}</p>
            <div className="mt-5 pt-4 border-t border-border-subtle space-y-2">
              <RegimeIndicator prediction={plan?.mlPredictions?.find(p => p.assetClass === 'STOCK')} />
              <p className="text-xs text-text-secondary">{plan?.taaEnabled === false ? 'Đang phân bổ theo SAA.' : plan ? 'Đang phân bổ theo TAA.' : 'Chưa có kế hoạch phân bổ.'}</p>
            </div>
            {!!plan?.actions?.length && <div className="mt-5">
              <p className="text-xs text-text-secondary mb-3">{plan.actions.length} điều chỉnh được đề xuất · Chưa thực hiện giao dịch</p>
              <button type="button" onClick={onConfirmRebalance} disabled={executing || !plan.planToken} className="px-4 py-2 rounded-md bg-text-primary text-surface-container-lowest text-sm font-semibold disabled:opacity-50">{executing ? 'Đang xử lý…' : 'Xem kế hoạch tái cân bằng'}</button>
            </div>}
          </section>
        </aside>
      </div>

      {/* Trading Drawer Slide Panel */}
      <TradingDrawer
        isOpen={tradeDrawerOpen}
        onClose={() => setTradeDrawerOpen(false)}
        valuation={valuation}
        initialTicker={selectedTradeTicker}
        initialAction={selectedTradeAction}
        onTradeSuccess={async () => {
          await onTradeSuccess();
        }}
      />

      {/* Custom SAA Targets Modal */}
      <CustomTargetsModal
        isOpen={customTargetsOpen}
        onClose={() => setCustomTargetsOpen(false)}
        currentTargets={{
          stock: plan?.saaTargets?.STOCK ?? plan?.targetAllocations.STOCK ?? 0.35,
          gold: plan?.saaTargets?.GOLD ?? plan?.targetAllocations.GOLD ?? 0.35,
          savings: plan?.saaTargets?.SAVINGS ?? plan?.targetAllocations.SAVINGS ?? 0.20,
          cash: plan?.saaTargets?.CASH ?? plan?.targetAllocations.CASH ?? 0.10
        }}
        onSuccess={async () => {
          await onTradeSuccess();
        }}
      />
    </div>
  );
}
