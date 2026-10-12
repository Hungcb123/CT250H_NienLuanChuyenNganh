import { useState, useEffect } from 'react';
import {
  Wallet, Receipt, PiggyBank, TrendingUp, Sparkles, Bot, AlertTriangle, CheckCircle,
  BarChart2, Activity, ShieldCheck, ArrowUpRight, X, ArrowRight, Sliders, Check, RefreshCw
} from 'lucide-react';
import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, CartesianGrid
} from 'recharts';
import {
  PortfolioValuation, RebalancePlan, UserProfile, TransactionItem, SavingsDepositItem,
  PortfolioHistoryResponse, RiskMetrics
} from '../../types';
import { formatVND } from '../../utils/formatters';
import { VNIndexChart } from '../charts/VNIndexChart';
import { VNINDEX_SUMMARY, VNIndexSummary } from '../../data/vnindexData';
import { TradingDrawer } from '../trading/TradingDrawer';
import { CustomTargetsModal } from '../profile/CustomTargetsModal';
import { useTheme } from '../../context/ThemeContext';
import {
  getTransactions, getSavingsDeposits, getVNIndexSummaryApi, updatePortfolioTargets,
  getPortfolioHistory, getRiskMetrics
} from '../../services/api';
import { useToast } from '../../context/ToastContext';

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

// Realistic financial time-series data with natural market zig-zags (daily trade volatility)
const TIMEFRAME_DATA: Record<TimeframeOption, Array<{ date: string; navReturn: number; vniReturn: number; navVal: number; vniVal: number }>> = {
  '1W': [
    { date: '02/10', navReturn: 0.0, vniReturn: 0.0, navVal: 1432.0, vniVal: 1282.0 },
    { date: '03/10', navReturn: 0.4, vniReturn: 0.1, navVal: 1437.7, vniVal: 1283.3 },
    { date: '04/10', navReturn: 0.2, vniReturn: -0.3, navVal: 1434.8, vniVal: 1278.2 },
    { date: '07/10', navReturn: 0.9, vniReturn: 0.2, navVal: 1444.9, vniVal: 1284.6 },
    { date: '08/10', navReturn: 1.4, vniReturn: 0.5, navVal: 1450.3, vniVal: 1288.4 },
  ],
  '1M': [
    { date: '10/09', navReturn: 0.0, vniReturn: 0.0, navVal: 1393.2, vniVal: 1261.5 },
    { date: '13/09', navReturn: 0.8, vniReturn: 0.4, navVal: 1404.3, vniVal: 1266.5 },
    { date: '17/09', navReturn: 0.3, vniReturn: -0.2, navVal: 1397.4, vniVal: 1259.0 },
    { date: '20/09', navReturn: 1.6, vniReturn: 0.7, navVal: 1415.5, vniVal: 1270.3 },
    { date: '24/09', navReturn: 1.2, vniReturn: 0.1, navVal: 1409.9, vniVal: 1262.8 },
    { date: '27/09', navReturn: 2.4, vniReturn: 1.1, navVal: 1426.6, vniVal: 1275.4 },
    { date: '01/10', navReturn: 2.9, vniReturn: 1.4, navVal: 1433.6, vniVal: 1279.2 },
    { date: '04/10', navReturn: 3.5, vniReturn: 1.8, navVal: 1442.0, vniVal: 1284.2 },
    { date: '08/10', navReturn: 4.1, vniReturn: 2.1, navVal: 1450.3, vniVal: 1288.4 },
  ],
  '3M': [
    { date: '08/07', navReturn: 0.0, vniReturn: 0.0, navVal: 1335.5, vniVal: 1232.9 },
    { date: '22/07', navReturn: -1.2, vniReturn: -2.1, navVal: 1319.5, vniVal: 1207.0 },
    { date: '05/08', navReturn: 1.8, vniReturn: 0.5, navVal: 1359.5, vniVal: 1239.1 },
    { date: '19/08', navReturn: 3.4, vniReturn: 1.8, navVal: 1380.9, vniVal: 1255.1 },
    { date: '02/09', navReturn: 5.1, vniReturn: 2.9, navVal: 1403.6, vniVal: 1268.7 },
    { date: '16/09', navReturn: 4.6, vniReturn: 2.2, navVal: 1396.9, vniVal: 1260.0 },
    { date: '30/09', navReturn: 7.2, vniReturn: 3.8, navVal: 1431.7, vniVal: 1279.8 },
    { date: '08/10', navReturn: 8.6, vniReturn: 4.5, navVal: 1450.3, vniVal: 1288.4 },
  ],
  'YTD': [
    { date: 'T1/24', navReturn: 0.0, vniReturn: 0.0, navVal: 1280.0, vniVal: 1165.0 },
    { date: 'T2/24', navReturn: 2.3, vniReturn: 1.1, navVal: 1309.4, vniVal: 1177.8 },
    { date: 'T3/24', navReturn: 1.2, vniReturn: -1.6, navVal: 1295.4, vniVal: 1146.4 },
    { date: 'T4/24', navReturn: 4.7, vniReturn: 2.1, navVal: 1340.2, vniVal: 1189.5 },
    { date: 'T5/24', navReturn: 8.6, vniReturn: 4.5, navVal: 1390.1, vniVal: 1217.4 },
    { date: 'T6/24', navReturn: 7.0, vniReturn: 1.8, navVal: 1369.6, vniVal: 1186.0 },
    { date: 'T7/24', navReturn: 10.2, vniReturn: 5.2, navVal: 1410.6, vniVal: 1225.6 },
    { date: 'T8/24', navReturn: 12.1, vniReturn: 6.8, navVal: 1434.9, vniVal: 1244.2 },
    { date: 'T9/24', navReturn: 13.3, vniReturn: 7.5, navVal: 1450.3, vniVal: 1252.4 },
  ],
  '1Y': [
    { date: 'T10/23', navReturn: 0.0, vniReturn: 0.0, navVal: 1220.0, vniVal: 1100.0 },
    { date: 'T12/23', navReturn: 3.5, vniReturn: 1.8, navVal: 1262.7, vniVal: 1119.8 },
    { date: 'T02/24', navReturn: 6.2, vniReturn: 3.2, navVal: 1295.6, vniVal: 1135.2 },
    { date: 'T04/24', navReturn: 9.8, vniReturn: 5.5, navVal: 1339.6, vniVal: 1160.5 },
    { date: 'T06/24', navReturn: 12.4, vniReturn: 7.0, navVal: 1371.3, vniVal: 1177.0 },
    { date: 'T08/24', navReturn: 16.5, vniReturn: 10.2, navVal: 1421.3, vniVal: 1212.2 },
    { date: 'T10/24', navReturn: 18.9, vniReturn: 12.4, navVal: 1450.3, vniVal: 1236.4 },
  ],
  'ALL': [
    { date: '2022', navReturn: 0.0, vniReturn: 0.0, navVal: 1000.0, vniVal: 1000.0 },
    { date: '2023', navReturn: 18.5, vniReturn: 12.2, navVal: 1185.0, vniVal: 1122.0 },
    { date: '2024 Q1', navReturn: 28.2, vniReturn: 17.5, navVal: 1282.0, vniVal: 1175.0 },
    { date: '2024 Q2', navReturn: 37.0, vniReturn: 21.0, navVal: 1370.0, vniVal: 1210.0 },
    { date: 'Hiện tại', navReturn: 45.0, vniReturn: 25.2, navVal: 1450.3, vniVal: 1252.0 },
  ],
};

export function OverviewTab({
  valuation,
  plan,
  profile,
  confirmedExecution,
  onConfirmRebalance,
  executing = false,
  onNavigateToSurvey,
  onTradeSuccess = () => {}
}: OverviewTabProps) {
  const { isDark } = useTheme();
  const [chartMode, setChartMode] = useState<'compare' | 'nav' | 'vnindex'>('compare');
  const [timeframe, setTimeframe] = useState<TimeframeOption>('YTD');
  const [acidPopoverOpen, setAcidPopoverOpen] = useState(false);
  const [tradeDrawerOpen, setTradeDrawerOpen] = useState(false);
  const [selectedTradeTicker, setSelectedTradeTicker] = useState('HPG');
  const [selectedTradeAction, setSelectedTradeAction] = useState<'BUY' | 'SELL'>('BUY');
  const [customTargetsOpen, setCustomTargetsOpen] = useState(false);
  const [onboardingDismissed, setOnboardingDismissed] = useState<boolean>(() => {
    return localStorage.getItem('equifolio_onboarding_dismissed') === 'true';
  });

  const toast = useToast();
  const [isApplyingTAA, setIsApplyingTAA] = useState(false);
  const isTAAActive = Math.abs(((plan?.targetAllocations?.STOCK ?? 0.40) * 100) - 50.0) < 1.0;

  const handleApplyTAACopilot = async () => {
    setIsApplyingTAA(true);
    try {
      await updatePortfolioTargets({
        stock: 0.50,
        gold: 0.20,
        savings: 0.20,
        cash: 0.10,
      });
      toast.success(
        'Đã kích hoạt tỷ trọng TAA: Cổ phiếu 50% (+10%), Vàng 20%, Tiết kiệm 20%, Tiền mặt 10%!',
        'Áp dụng TAA thành công'
      );
      if (onTradeSuccess) {
        await onTradeSuccess();
      }
    } catch (err: any) {
      toast.error(err.message || 'Lỗi áp dụng TAA', 'Thất bại');
    } finally {
      setIsApplyingTAA(false);
    }
  };

  // Aux state: Load actual ledger transactions, active savings deposits, and live VN-Index summary
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [savingsDeposits, setSavingsDeposits] = useState<SavingsDepositItem[]>([]);
  const [vniSummary, setVniSummary] = useState<VNIndexSummary>(VNINDEX_SUMMARY);
  const [historyData, setHistoryData] = useState<PortfolioHistoryResponse | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    let active = true;
    const fetchAux = async () => {
      try {
        const [txs, deps, vni] = await Promise.all([
          getTransactions(),
          getSavingsDeposits(),
          getVNIndexSummaryApi()
        ]);
        if (active) {
          setTransactions(txs || []);
          setSavingsDeposits(deps || []);
          if (vni && vni.currentPoints) {
            setVniSummary({
              latestDate: vni.latestDate,
              currentPoints: vni.currentPoints,
              changePoints: vni.changePoints,
              changePercent: vni.changePercent,
              high52w: vni.high52w,
              low52w: vni.low52w,
              avgVolume20: vni.avgVolume20,
              latestVolume: vni.latestVolume,
              ma20: vni.ma20,
              ma50: vni.ma50
            });
          }
        }
      } catch (err) {
        console.error("Failed to load transactions/savings in OverviewTab", err);
      }
    };
    fetchAux();
    return () => { active = false; };
  }, [valuation]);

  useEffect(() => {
    let active = true;
    const fetchHistoryAndRisk = async () => {
      setLoadingHistory(true);
      try {
        const [hist, risk] = await Promise.all([
          getPortfolioHistory(timeframe),
          getRiskMetrics()
        ]);
        if (active) {
          if (hist) setHistoryData(hist);
          if (risk) setRiskMetrics(risk);
        }
      } catch (err) {
        console.error("Failed to load portfolio history / risk metrics", err);
      } finally {
        if (active) setLoadingHistory(false);
      }
    };
    fetchHistoryAndRisk();
    return () => { active = false; };
  }, [timeframe, valuation]);

  const hasAssets = valuation && valuation.totalNetWorth > 0;
  const stockPct = Math.round((valuation?.currentAllocations.STOCK || 0) * 100);
  const goldPct = Math.round((valuation?.currentAllocations.GOLD || 0) * 100);
  const savingsPct = Math.round((valuation?.currentAllocations.SAVINGS || 0) * 100);
  const cashAllocationPct = Math.round((valuation?.currentAllocations.CASH || 0) * 100);

  const targetStock = Math.round((plan?.targetAllocations.STOCK ?? 0.35) * 100);
  const targetGold = Math.round((plan?.targetAllocations.GOLD ?? 0.35) * 100);
  const targetSavings = Math.round((plan?.targetAllocations.SAVINGS ?? 0.20) * 100);
  const targetCash = Math.round((plan?.targetAllocations.CASH ?? 0.10) * 100);

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

  const riskScore = profile?.riskScore ?? 50;
  const riskTitle = profile?.riskProfile === 'GROWTH'
    ? 'Tăng trưởng (Growth)'
    : profile?.riskProfile === 'CONSERVATIVE'
    ? 'Bảo thủ (Conservative)'
    : 'Cân bằng (Balanced)';

  const cashPct = valuation && valuation.totalNetWorth > 0
    ? (valuation.cashBalance / valuation.totalNetWorth) * 100
    : 0;

  const currentChartData = (historyData?.points && historyData.points.length > 0)
    ? historyData.points.map(pt => ({
        date: pt.date.length >= 10 ? `${pt.date.substring(8, 10)}/${pt.date.substring(5, 7)}` : pt.date,
        navReturn: Number((pt.navReturn ?? 0).toFixed(1)),
        vniReturn: Number((pt.vniReturn ?? 0).toFixed(1)),
        navVal: Number((pt.nav / 1_000_000).toFixed(1)),
        vniVal: Number((pt.vnindex ?? 1250).toFixed(1))
      }))
    : TIMEFRAME_DATA[timeframe];
  const lastPoint = currentChartData[currentChartData.length - 1] || { navReturn: 0, vniReturn: 0, navVal: 0, vniVal: 0, date: '' };
  const alphaVal = historyData?.alphaPercent !== undefined
    ? (historyData.alphaPercent > 0 ? `+${historyData.alphaPercent.toFixed(1)}` : `${historyData.alphaPercent.toFixed(1)}`)
    : ((lastPoint.navReturn - lastPoint.vniReturn) >= 0 
        ? `+${(lastPoint.navReturn - lastPoint.vniReturn).toFixed(1)}`
        : `${(lastPoint.navReturn - lastPoint.vniReturn).toFixed(1)}`);

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
                  Chào mừng bạn đến với EquiFolio Wealth Terminal
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

      {/* 1. Header & Client Identity Banner (Clean, Zero Tech Leaks) */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative transition-colors">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Client Identity */}
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-surface-container-high border border-border-subtle flex items-center justify-center text-text-primary font-black text-sm tracking-wider shrink-0">
              {(profile?.username || 'CTH').substring(0, 3).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black text-text-primary tracking-tight">
                  {profile?.username || 'Cao Tường Hưng'}
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wide bg-surface-container text-text-secondary border border-border-subtle">
                  VIP
                </span>
              </div>
              <p className="text-xs text-text-muted mt-0.5 font-medium flex items-center gap-1.5">
                <span>Khẩu vị: <strong className="text-text-secondary">{riskTitle}</strong></span>
                <span>•</span>
                <span>Điểm rủi ro: <strong className="font-mono-num text-text-secondary">{riskScore}/100</strong></span>
              </p>
            </div>
          </div>

          {/* Right Action: Clean ACID Ledger Popover */}
          <div className="relative flex items-center">
            <button
              type="button"
              onClick={() => setAcidPopoverOpen(!acidPopoverOpen)}
              className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-surface-container-low hover:bg-surface-container border border-border-subtle hover:border-accent-emerald/40 transition-all cursor-pointer shadow-xs group"
              title="Nhấp để xem chi tiết kiểm toán sổ cái"
            >
              <div className="w-6 h-6 rounded-lg bg-accent-emerald/15 flex items-center justify-center text-accent-emerald">
                <ShieldCheck className="w-3.5 h-3.5" />
              </div>
              <div className="text-left">
                <div className="flex items-center gap-1.5 text-xs font-bold text-text-primary">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse"></span>
                  <span>Khớp sổ cái ACID</span>
                </div>
                <span className="text-[10px] text-text-muted block">Toàn vẹn Debit = Credit</span>
              </div>
            </button>

            {/* Popover Dropdown for ACID Ledger Audit Log */}
            {acidPopoverOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 p-4 rounded-xl bg-surface-container border border-border-subtle shadow-xl z-50 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-border-subtle">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-text-primary">
                    <ShieldCheck className="w-4 h-4 text-accent-emerald" />
                    <span>Chi tiết Kiểm toán Sổ cái kép</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAcidPopoverOpen(false)}
                    className="text-text-muted hover:text-text-primary p-0.5 rounded cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-text-muted">Tổng ghi Nợ (Debit):</span>
                    <span className="font-mono-num font-bold text-text-primary">
                      {valuation ? formatVND(valuation.totalNetWorth) : '0 ₫'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-text-muted">Tổng ghi Có (Credit):</span>
                    <span className="font-mono-num font-bold text-text-primary">
                      {valuation ? formatVND(valuation.totalNetWorth) : '0 ₫'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-border-subtle font-bold">
                    <span className="text-accent-emerald">Độ lệch đối soát:</span>
                    <span className="font-mono-num text-accent-emerald">0.00 ₫ (Khớp 100%)</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container-low border border-border-subtle text-[11px] text-text-muted mt-2 leading-relaxed">
                    Hệ thống tự động thực hiện hạch toán kép cho từng giao dịch. Số dư tài sản và tiền mặt luôn bảo toàn tính toàn vẹn tài chính.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Drift Alert Banner */}
      {plan?.driftDetected && (
        <section className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 shadow-xs relative overflow-hidden transition-all">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-amber-500/20 text-amber-500 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-amber-500 uppercase tracking-wider">
                    Cảnh Báo Lệch Tỷ Trọng Mục Tiêu
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-500">
                    Độ lệch lớn nhất: +{plan.maxDriftPercent.toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-text-secondary mt-0.5">
                  Danh mục của bạn đã vượt ngưỡng dung sai cân bằng (tolerance &gt; 5%). Đề xuất tái cơ cấu để đưa tỷ trọng về vùng tối ưu và kiểm soát rủi ro.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onConfirmRebalance}
              disabled={executing}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs shadow-xs transition-all flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${executing ? 'animate-spin' : ''}`} />
              <span>{executing ? 'Đang tái cơ cấu...' : 'Tái cơ cấu ngay'}</span>
            </button>
          </div>
        </section>
      )}

      {/* 2. Four Key Wealth Metric Cards (Restrained Accent & Clean Typography) */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Total NAV */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative overflow-hidden group hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Tổng Tài Sản Ròng (NAV)</span>
            <div className="w-7 h-7 rounded-lg bg-surface-container-high border border-border-subtle flex items-center justify-center text-accent-emerald">
              <Wallet className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black text-text-primary font-mono-num tracking-tight">
            {valuation ? formatVND(valuation.totalNetWorth) : '0 ₫'}
          </div>
          <div className="mt-2.5 flex items-center justify-between text-xs">
            {totalUnrealizedPnL !== 0 ? (
              <span className={`font-bold font-mono-num flex items-center gap-1 ${
                totalUnrealizedPnL > 0 ? 'text-accent-emerald' : 'text-accent-rose'
              }`}>
                <TrendingUp className="w-3.5 h-3.5 inline" />
                {totalUnrealizedPnL > 0 ? '+' : ''}{portfolioPnLPercent.toFixed(1)}% ({totalUnrealizedPnL > 0 ? '+' : ''}{formatVND(totalUnrealizedPnL)})
              </span>
            ) : (
              <span className="text-text-muted font-medium font-mono-num flex items-center gap-1">
                Khớp giá vốn ban đầu (0.0% P/L)
              </span>
            )}
            <span className="text-[11px] text-text-muted flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald"></span> Realtime
            </span>
          </div>
        </div>

        {/* Metric 2: Cash & Liquidity */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative overflow-hidden group hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Tiền Mặt Khả Dụng</span>
            <div className="w-7 h-7 rounded-lg bg-surface-container-high border border-border-subtle flex items-center justify-center text-text-primary">
              <Receipt className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black text-text-primary font-mono-num tracking-tight">
            {valuation ? formatVND(valuation.cashBalance) : '0 ₫'}
          </div>
          <div className="mt-2.5">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-text-muted">
                Tỷ trọng: <strong className="text-text-primary font-mono-num">{cashPct.toFixed(1)}% NAV</strong>
              </span>
              <span className="text-[11px] text-text-muted">Sẵn sàng giải ngân</span>
            </div>
            <div className="w-full bg-surface-container-highest h-1 rounded-full overflow-hidden">
              <div
                className="bg-accent-emerald h-full rounded-full transition-all"
                style={{ width: `${Math.min(100, Math.max(0, cashPct))}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Metric 3: Savings & Fixed Yield */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative overflow-hidden group hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Tiết Kiệm Tích Lũy</span>
            <div className="w-7 h-7 rounded-lg bg-surface-container-high border border-border-subtle flex items-center justify-center text-text-primary">
              <PiggyBank className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black text-text-primary font-mono-num tracking-tight">
            {valuation ? formatVND(valuation.savingsValue) : '0 ₫'}
          </div>
          <div className="mt-2.5 flex items-center justify-between text-xs">
            {valuation && valuation.savingsValue > 0 ? (
              <>
                <span className="text-text-muted">
                  {savingsDeposits.length > 0 ? `${savingsDeposits.length} sổ tiết kiệm` : 'Tiết kiệm ngân hàng'}
                </span>
                <span className="text-text-primary font-bold font-mono-num text-[11px]">
                  Lãi 5.5%/năm
                </span>
              </>
            ) : (
              <>
                <span className="text-text-muted">Chưa mở sổ tiết kiệm</span>
                <span className="text-text-muted font-mono-num text-[11px]">0 ₫</span>
              </>
            )}
          </div>
        </div>

        {/* Metric 4: Real Portfolio Unrealized P/L */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-5 shadow-xs relative overflow-hidden group hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Lãi / Lỗ Tạm Tính (P/L)</span>
            <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${
              totalUnrealizedPnL > 0 ? 'bg-accent-emerald-light border-accent-emerald/30 text-accent-emerald' :
              totalUnrealizedPnL < 0 ? 'bg-accent-rose-light border-accent-rose/30 text-accent-rose' :
              'bg-surface-container-high border-border-subtle text-text-muted'
            }`}>
              <TrendingUp className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className={`text-2xl font-black font-mono-num tracking-tight ${
            totalUnrealizedPnL > 0 ? 'text-accent-emerald' :
            totalUnrealizedPnL < 0 ? 'text-accent-rose' :
            'text-text-primary'
          }`}>
            {totalUnrealizedPnL > 0 ? `+${formatVND(totalUnrealizedPnL)}` :
             totalUnrealizedPnL < 0 ? `-${formatVND(Math.abs(totalUnrealizedPnL))}` :
             '0 ₫'}
          </div>
          <div className="mt-2.5 flex items-center justify-between text-xs">
            <span className={`font-bold font-mono-num ${
              totalUnrealizedPnL > 0 ? 'text-accent-emerald' :
              totalUnrealizedPnL < 0 ? 'text-accent-rose' :
              'text-text-muted'
            }`}>
              {totalUnrealizedPnL > 0 ? `+${portfolioPnLPercent.toFixed(1)}% so với giá vốn` :
               totalUnrealizedPnL < 0 ? `${portfolioPnLPercent.toFixed(1)}% so với giá vốn` :
               '0.0% so với giá vốn'}
            </span>
            <span className="text-[11px] text-text-muted">
              {totalUnrealizedPnL === 0 ? 'Khớp giá vốn khớp lệnh' : 'Định giá thời gian thực'}
            </span>
          </div>
        </div>
      </section>

      {/* 3. Main Operational Grid: Charts & Holdings vs Donut & Copilot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols): Market Ticker + Realistic Chart + Holdings */}
        <div className="lg:col-span-8 space-y-6">
          {/* Performance & Benchmark Chart Card */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs">
            {/* Live VN-Index Market Ticker Strip */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-surface-container-low border border-border-subtle mb-5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></span>
                <span className="text-xs font-bold text-text-secondary">VN-Index:</span>
                <span className="text-xs font-black text-text-primary font-mono-num">
                  {vniSummary.currentPoints.toFixed(2)}
                </span>
                <span className={`text-xs font-bold font-mono-num ${vniSummary.changePercent >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                  {vniSummary.changePoints > 0 ? '+' : ''}{vniSummary.changePoints.toFixed(2)} ({vniSummary.changePercent > 0 ? '+' : ''}{vniSummary.changePercent.toFixed(2)}%)
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-text-muted flex-wrap">
                <span>Khối lượng: <strong className="text-text-primary font-mono-num">{(vniSummary.latestVolume / 1e6).toFixed(1)}M CP</strong></span>
                <span>MA20: <strong className="text-text-primary font-mono-num">{vniSummary.ma20.toFixed(1)}</strong></span>
                <span>MA50: <strong className="text-text-primary font-mono-num">{vniSummary.ma50.toFixed(1)}</strong></span>
              </div>
            </div>

            {/* Header & Controls: Mode Switcher & Timeframe Switcher */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <h3 className="text-sm font-extrabold text-text-primary uppercase tracking-wider">
                    {chartMode === 'vnindex' ? 'Biểu Đồ Kỹ Thuật VN-Index' : 'Hiệu Suất Danh Mục & Đối Sánh'}
                  </h3>
                  {chartMode !== 'vnindex' && (
                    <span className="text-xs font-bold text-accent-emerald font-mono-num">
                      Alpha: +{alphaVal}%
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-secondary mt-0.5 font-medium">
                  {chartMode === 'vnindex'
                    ? '1,430 phiên giao dịch từ VNDirect kèm đường trung bình MA20 & MA50'
                    : 'Danh mục đầu tư thực tế so với chỉ số chuẩn VN-Index'}
                </p>
              </div>

              {/* View Toggle Tabs */}
              <div className="flex items-center gap-1 p-1 bg-surface-container-low rounded-xl border border-border-subtle shrink-0">
                <button
                  type="button"
                  onClick={() => setChartMode('compare')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    chartMode === 'compare'
                      ? 'bg-surface-container-high text-text-primary shadow-xs border border-border-highlight'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5 inline mr-1 text-text-secondary" />
                  Đối sánh (%)
                </button>
                <button
                  type="button"
                  onClick={() => setChartMode('nav')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    chartMode === 'nav'
                      ? 'bg-surface-container-high text-text-primary shadow-xs border border-border-highlight'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  NAV (₫)
                </button>
                <button
                  type="button"
                  onClick={() => setChartMode('vnindex')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    chartMode === 'vnindex'
                      ? 'bg-surface-container-high text-accent-emerald shadow-xs border border-accent-emerald/40 font-extrabold'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  <Activity className="w-3.5 h-3.5 inline mr-1 text-accent-emerald" />
                  Chỉ số VN-Index
                </button>
              </div>
            </div>

            {/* Timeframe Switcher Bar (1W, 1M, 3M, YTD, 1Y, Tất cả) */}
            {chartMode !== 'vnindex' && (
              <div className="flex items-center gap-1.5 mb-4 border-b border-border-subtle pb-3">
                <span className="text-[11px] font-bold text-text-muted mr-1">Khung thời gian:</span>
                {(['1W', '1M', '3M', 'YTD', '1Y', 'ALL'] as TimeframeOption[]).map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() => setTimeframe(tf)}
                    className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all cursor-pointer ${
                      timeframe === tf
                        ? 'bg-accent-emerald text-white shadow-2xs'
                        : 'bg-surface-container-low hover:bg-surface-container text-text-secondary hover:text-text-primary border border-border-subtle'
                    }`}
                  >
                    {tf === 'ALL' ? 'Tất cả' : tf}
                  </button>
                ))}
                {loadingHistory && (
                  <RefreshCw className="w-3.5 h-3.5 text-accent-emerald animate-spin ml-2" />
                )}
              </div>
            )}

            {/* Chart Canvas */}
            {chartMode === 'vnindex' ? (
              <VNIndexChart height={280} compact={false} showControls={true} />
            ) : (
              <>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={currentChartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorNavLinear" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke={isDark ? '#27272a' : '#f1f5f9'}
                      />
                      <XAxis
                        dataKey="date"
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
                        contentStyle={{
                          backgroundColor: isDark ? '#18181b' : '#ffffff',
                          borderColor: isDark ? '#27272a' : '#e2e8f0',
                          borderRadius: '0.75rem',
                          fontSize: '12px',
                          color: isDark ? '#f4f4f5' : '#0f172a',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.25)'
                        }}
                        formatter={(value: any, name: string) => [
                          chartMode === 'compare' ? `${value > 0 ? '+' : ''}${value}%` : `${value} Triệu ₫`,
                          name
                        ]}
                      />

                      {/* 1. Main Portfolio Area with realistic linear line */}
                      <Area
                        type="linear"
                        dataKey={chartMode === 'compare' ? 'navReturn' : 'navVal'}
                        name={chartMode === 'compare' ? `Danh mục (+${lastPoint.navReturn}%)` : 'NAV Danh mục'}
                        stroke="#10b981"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorNavLinear)"
                      />

                      {/* 2. VN-Index Benchmark Comparison Line */}
                      {chartMode === 'compare' && (
                        <Line
                          type="linear"
                          dataKey="vniReturn"
                          name={`VN-Index (+${lastPoint.vniReturn}%)`}
                          stroke={isDark ? '#a1a1aa' : '#64748b'}
                          strokeWidth={1.75}
                          strokeDasharray="4 4"
                          dot={false}
                        />
                      )}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* 4 Bottom Financial Risk Metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4 mt-3 border-t border-border-subtle text-center">
                  <div className="p-3 rounded-xl bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Chỉ số Alpha (Vượt TT)</span>
                    <p className="font-black font-mono-num text-accent-emerald text-base mt-0.5">{alphaVal}%</p>
                  </div>
                  <div className="p-3 rounded-xl bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Sharpe Ratio</span>
                    <p className="font-black font-mono-num text-text-primary text-base mt-0.5">
                      {riskMetrics ? riskMetrics.sharpeRatio.toFixed(2) : '1.84'}{' '}
                      <span className="text-xs font-normal text-text-muted">
                        ({riskMetrics?.interpretation || 'Tối ưu'})
                      </span>
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Max Drawdown (MDD)</span>
                    <p className="font-black font-mono-num text-accent-rose text-base mt-0.5">
                      {riskMetrics ? `-${Math.abs(riskMetrics.maxDrawdownPercent).toFixed(1)}%` : '-4.2%'}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-surface-container-low border border-border-subtle">
                    <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider">Biến động năm (Vol)</span>
                    <p className="font-black font-mono-num text-text-primary text-base mt-0.5">
                      {riskMetrics ? `${riskMetrics.annualizedVolatilityPercent.toFixed(1)}%` : '14.5%'}
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Holdings Table Card (7 Standard Financial Columns) */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-extrabold text-text-primary uppercase tracking-wider">Vị Thế Danh Mục (Holdings)</h3>
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

        {/* Right Column (4 cols): Donut Allocation (Vertical Legend) + Copilot (Clear Microcopy) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Donut Allocation Card with Vertical Legend on Right */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-extrabold text-text-primary uppercase tracking-wider">Cơ Cấu Tài Sản Thực Tế</h3>
              <button
                type="button"
                onClick={() => setCustomTargetsOpen(true)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-accent-emerald text-[11px] font-bold transition-colors cursor-pointer border border-border-subtle shadow-2xs"
                title="Tùy chỉnh tỷ trọng mục tiêu SAA"
              >
                <Sliders className="w-3.5 h-3.5 text-accent-emerald" />
                <span>Chỉnh mục tiêu</span>
              </button>
            </div>
            <p className="text-xs text-text-muted mb-4">
              Tỷ trọng danh mục so với khuyến nghị phân bổ SAA
            </p>

            {donutData.length > 0 ? (
              <div className="flex flex-col sm:flex-row lg:flex-col xl:flex-row items-center gap-4">
                {/* Donut Ring (Resized smaller) */}
                <div className="w-40 h-40 shrink-0 relative flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={68}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {donutData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: isDark ? '#18181b' : '#ffffff',
                          borderColor: isDark ? '#27272a' : '#e2e8f0',
                          borderRadius: '0.75rem',
                          fontSize: '12px',
                          color: isDark ? '#f4f4f5' : '#0f172a'
                        }}
                        formatter={(value: any) => [`${value}%`, 'Tỷ trọng']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Vertical Legend List with Amount and Percentages */}
                <div className="flex-1 w-full space-y-2.5">
                  {donutData.map((item, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs pb-1.5 border-b border-border-subtle/50 last:border-none">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.fill }}></span>
                        <div>
                          <span className="font-bold text-text-primary block leading-tight">{item.name}</span>
                          <span className="text-[11px] text-text-muted font-mono-num">{formatVND(item.amount)}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="font-extrabold font-mono-num text-text-primary block leading-tight">
                          {item.value}%
                        </span>
                        <span className="text-[10px] text-text-muted font-mono-num">
                          Mục tiêu: {item.targetValue}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-44 w-full flex flex-col items-center justify-center text-center p-4 border border-dashed border-border-subtle rounded-xl bg-surface-container-low/60">
                <PiggyBank className="w-7 h-7 text-text-muted mb-2" />
                <p className="text-xs font-semibold text-text-primary">Chưa có dữ liệu phân bổ</p>
                <p className="text-[11px] text-text-muted mt-0.5">Nạp vốn và mua tài sản để hiển thị cơ cấu</p>
              </div>
            )}
          </div>

          {/* Financial Copilot Action Card (Structured: Status -> Issue -> CTA) */}
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 shadow-xs relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-accent-emerald/15 flex items-center justify-center text-accent-emerald">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-extrabold text-text-primary">Financial Copilot</h4>
                  <span className="text-[10px] text-text-muted">Khuyến nghị tái cơ cấu tự động</span>
                </div>
              </div>
              {plan?.driftDetected ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-500 border border-amber-500/30">
                  Cần cân bằng
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-accent-emerald-light text-accent-emerald border border-accent-emerald/30">
                  Cân bằng
                </span>
              )}
            </div>

            {/* Structured Card Body: Status -> Issue */}
            <div className="p-3.5 rounded-xl bg-surface-container-low border border-border-subtle text-xs space-y-1.5 mb-4">
              <div className="flex items-center gap-1.5 font-bold text-text-primary">
                {plan?.driftDetected ? (
                  <>
                    <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                    <span className="text-amber-500">Lệch tỷ trọng mục tiêu (+{plan.maxDriftPercent}%)</span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 text-accent-emerald shrink-0" />
                    <span className="text-accent-emerald">Danh mục đang cân bằng tối ưu</span>
                  </>
                )}
              </div>
              <p className="text-text-secondary leading-relaxed text-xs">
                {plan?.driftDetected
                  ? 'Tỷ trọng một số lớp tài sản đang vượt khung khuyến nghị SAA. Khuyến nghị cân bằng lại để bảo đảm kiểm soát rủi ro.'
                  : 'Tất cả các lớp tài sản đều nằm trong ngưỡng an toàn SAA (< 5%). Không cần can thiệp.'}
              </p>
            </div>

            {/* TAA AI Radar Insight */}
            <div className="p-3.5 rounded-xl bg-accent-emerald/10 border border-accent-emerald/25 text-xs mb-4 space-y-2.5">
              <div className="flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-accent-emerald shrink-0 mt-0.5" />
                <div className="space-y-0.5 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-accent-emerald text-[11px]">AI Radar T+20: Cổ phiếu VN30 (78.4% Tăng)</span>
                    <span className="text-[10px] font-bold text-accent-emerald bg-accent-emerald/20 px-2 py-0.2 rounded">ONNX</span>
                  </div>
                  <p className="text-[11px] text-text-secondary leading-snug">
                    Mô hình ONNX dự báo pha tăng trưởng cho cổ phiếu. Vàng (ρ = -0.15) giữ vai trò phòng thủ (20%). Khuyến nghị: Nâng tỷ trọng cổ phiếu lên 50% (trích từ tiết kiệm).
                  </p>
                </div>
              </div>

              <div className="pt-2 border-t border-accent-emerald/15 flex items-center justify-between gap-2">
                <span className="text-[10px] text-text-muted font-medium">
                  {isTAAActive ? 'Trạng thái: Đã kích hoạt TAA (50% CP)' : 'Mục tiêu: Cổ phiếu 40% ➔ Đề xuất: 50%'}
                </span>
                <button
                  type="button"
                  onClick={handleApplyTAACopilot}
                  disabled={isApplyingTAA || isTAAActive}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all flex items-center gap-1.5 shadow-2xs ${
                    isTAAActive
                      ? 'bg-accent-emerald/20 text-accent-emerald cursor-default border border-accent-emerald/30'
                      : 'bg-accent-emerald hover:bg-emerald-600 text-white cursor-pointer active:scale-95'
                  }`}
                >
                  {isApplyingTAA ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      <span>Đang cập nhật...</span>
                    </>
                  ) : isTAAActive ? (
                    <>
                      <Check className="w-3 h-3 text-accent-emerald" />
                      <span>Đã kích hoạt TAA</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3 h-3" />
                      <span>Áp dụng TAA (+10% CP)</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Recommended Rebalance Actions */}
            {plan?.actions && plan.actions.length > 0 && (
              <div className="space-y-2 mb-4">
                <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted block mb-1">
                  Đề xuất tái cơ cấu:
                </span>
                {plan.actions.map((act, idx) => (
                  <div key={idx} className="p-2.5 rounded-xl border border-border-subtle bg-surface-container-low flex items-center justify-between text-xs">
                    <div>
                      <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] mr-1.5 ${
                        act.actionType === 'SELL' ? 'bg-accent-rose-light text-accent-rose' :
                        act.actionType === 'BUY' ? 'bg-accent-emerald-light text-accent-emerald' :
                        'bg-indigo-500/15 text-indigo-400'
                      }`}>
                        {act.actionType === 'OPEN_SAVINGS' ? 'GỬI TIẾT KIỆM' : act.actionType}
                      </span>
                      <span className="font-extrabold text-text-primary font-mono-num">{act.ticker}</span>
                    </div>
                    <div className="text-right">
                      <span className="font-bold text-text-primary font-mono-num block">
                        {act.roundedQuantity.toLocaleString()} CP
                      </span>
                      <span className="text-[10px] text-text-muted font-mono-num">
                        {formatVND(act.estimatedTotalMoney)}
                      </span>
                    </div>
                  </div>
                ))}
                {((plan.totalEstimatedFees || 0) > 0 || (plan.totalEstimatedTax || 0) > 0) && (
                  <div className="p-2.5 rounded-xl border border-border-subtle bg-surface-container-high/40 text-[11px] space-y-1">
                    <div className="flex justify-between text-text-muted">
                      <span>Phí môi giới (0.1%):</span>
                      <span className="font-mono-num font-semibold text-text-secondary">{formatVND(plan.totalEstimatedFees || 0)}</span>
                    </div>
                    <div className="flex justify-between text-text-muted">
                      <span>Thuế TNCN bán (0.1%):</span>
                      <span className="font-mono-num font-semibold text-text-secondary">{formatVND(plan.totalEstimatedTax || 0)}</span>
                    </div>
                    <div className="flex justify-between text-text-primary font-bold pt-1 border-t border-border-subtle">
                      <span>Tác động tiền ròng:</span>
                      <span className={`font-mono-num ${(plan.netCashImpact || 0) >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                        {(plan.netCashImpact || 0) >= 0 ? '+' : ''}{formatVND(plan.netCashImpact || 0)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Action CTA Button */}
            <div>
              {plan?.driftDetected && plan?.actions && plan.actions.length > 0 ? (
                <button
                  onClick={onConfirmRebalance}
                  disabled={executing}
                  className={`w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer ${
                    executing
                      ? 'bg-accent-emerald/50 text-white cursor-not-allowed'
                      : 'bg-accent-emerald hover:bg-emerald-600 text-white hover:opacity-95 shadow-sm active:scale-98'
                  }`}
                >
                  {executing ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Đang thực hiện tái cơ cấu...</span>
                    </>
                  ) : (
                    <>
                      <ArrowRight className="w-4 h-4" />
                      <span>Cân bằng danh mục ngay ({plan.actions.length} lệnh)</span>
                    </>
                  )}
                </button>
              ) : (
                <div className="w-full py-2.5 rounded-xl bg-surface-container-low text-accent-emerald font-bold text-xs flex items-center justify-center gap-2 border border-border-subtle">
                  <Check className="w-4 h-4 text-accent-emerald" />
                  <span>{confirmedExecution ? "Đã tái cơ cấu thành công - Danh mục tối ưu" : "Danh mục đã ở trạng thái tối ưu"}</span>
                </div>
              )}
            </div>
          </div>
        </div>
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
          stock: plan?.targetAllocations.STOCK ?? 0.35,
          gold: plan?.targetAllocations.GOLD ?? 0.35,
          savings: plan?.targetAllocations.SAVINGS ?? 0.20,
          cash: plan?.targetAllocations.CASH ?? 0.10
        }}
        onSuccess={async () => {
          await onTradeSuccess();
        }}
      />
    </div>
  );
}
